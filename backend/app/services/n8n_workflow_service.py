"""
N8N Workflow Service - Preview, Validation, and Triggering

Gère l'exécution sécurisée des workflows N8N avec:
- Chargement manifest workflows.yaml
- Validation inputs
- Dry-run preview pour danger élevé
- Génération carte de confirmation
- Tracking avec correlation_id
"""

import structlog
import yaml
import httpx
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, validator
from enum import Enum
from pathlib import Path
import uuid
from datetime import datetime

logger = structlog.get_logger()


class DangerLevel(str, Enum):
    """Niveau de danger d'un workflow"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorkflowCategory(str, Enum):
    """Catégorie de workflow"""
    EMERGENCY = "emergency"
    LEGAL = "legal"
    PROCUREMENT = "procurement"
    COMMUNICATION = "communication"
    MAINTENANCE = "maintenance"
    REPORTING = "reporting"


class WorkflowInput(BaseModel):
    """Définition d'un input de workflow"""
    name: str
    type: str  # integer, string, array, object, boolean, date, datetime
    required: bool = False
    default: Any = None
    description: str = ""
    validation: Optional[Dict[str, Any]] = None


class WorkflowOutput(BaseModel):
    """Définition d'un output de workflow"""
    name: str
    type: str
    description: str = ""


class Workflow(BaseModel):
    """Définition complète d'un workflow N8N"""
    id: str
    name: str
    description: str
    webhook_url: str
    category: WorkflowCategory
    danger_level: DangerLevel
    dry_run_supported: bool = False
    requires_confirmation: bool = False
    timeout_seconds: int = 60
    inputs: List[WorkflowInput] = []
    outputs: List[WorkflowOutput] = []
    preview_template: Optional[str] = None


class WorkflowExecutionRequest(BaseModel):
    """Requête d'exécution de workflow"""
    workflow_id: str = Field(..., description="ID du workflow")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Paramètres d'entrée")
    dry_run: bool = Field(False, description="Simuler seulement (si supporté)")
    correlation_id: Optional[str] = Field(None, description="ID de corrélation pour tracking")
    user_id: Optional[int] = Field(None, description="ID utilisateur")


class WorkflowExecutionResult(BaseModel):
    """Résultat d'exécution de workflow"""
    workflow_id: str
    correlation_id: str
    success: bool
    outputs: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    dry_run: bool = False
    preview_data: Optional[Dict[str, Any]] = None
    execution_time_ms: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WorkflowPreview(BaseModel):
    """Preview d'un workflow avant exécution"""
    workflow_id: str
    workflow_name: str
    danger_level: DangerLevel
    requires_confirmation: bool
    estimated_actions: List[str] = []
    affected_entities: Dict[str, Any] = Field(default_factory=dict)
    preview_text: str = ""
    warnings: List[str] = []
    can_execute: bool = True
    blocking_issues: List[str] = []


class N8NWorkflowService:
    """
    Service de gestion des workflows N8N.

    Responsabilités:
    1. Charger et parser workflows.yaml
    2. Valider les inputs selon schema
    3. Générer preview avec dry-run
    4. Exécuter workflows avec tracking
    5. Gérer timeout et erreurs
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize N8N Workflow Service

        Args:
            config_path: Path to workflows.yaml (default: config/workflows.yaml)
        """
        if config_path is None:
            # Default path relative to backend/
            config_path = Path(__file__).parent.parent.parent / "config" / "workflows.yaml"

        self.config_path = Path(config_path)
        self.workflows: Dict[str, Workflow] = {}
        self.n8n_base_url = self._get_n8n_base_url()

        # Charger workflows
        self._load_workflows()

        logger.info(
            "n8n_workflow_service_initialized",
            workflows_count=len(self.workflows),
            config_path=str(self.config_path)
        )

    def _get_n8n_base_url(self) -> str:
        """Get N8N base URL from environment or config"""
        import os
        return os.getenv("N8N_BASE_URL", "http://n8n:5678")

    def _load_workflows(self):
        """Charge les workflows depuis workflows.yaml"""
        if not self.config_path.exists():
            logger.warning(
                "n8n_workflows_config_not_found",
                path=str(self.config_path)
            )
            return

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            workflows_list = config.get("workflows", [])

            for wf_data in workflows_list:
                try:
                    # Convertir inputs/outputs en modèles Pydantic
                    wf_data["inputs"] = [
                        WorkflowInput(**inp) for inp in wf_data.get("inputs", [])
                    ]
                    wf_data["outputs"] = [
                        WorkflowOutput(**out) for out in wf_data.get("outputs", [])
                    ]

                    workflow = Workflow(**wf_data)
                    self.workflows[workflow.id] = workflow

                except Exception as e:
                    logger.error(
                        "n8n_workflow_parse_error",
                        workflow_id=wf_data.get("id"),
                        error=str(e),
                        exc_info=True
                    )

            logger.info(
                "n8n_workflows_loaded",
                count=len(self.workflows),
                workflows=[wf.id for wf in self.workflows.values()]
            )

        except Exception as e:
            logger.error(
                "n8n_workflows_load_error",
                path=str(self.config_path),
                error=str(e),
                exc_info=True
            )

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Récupère un workflow par ID"""
        return self.workflows.get(workflow_id)

    def list_workflows(
        self,
        category: Optional[WorkflowCategory] = None,
        danger_level: Optional[DangerLevel] = None
    ) -> List[Workflow]:
        """
        Liste les workflows disponibles avec filtres optionnels

        Args:
            category: Filtrer par catégorie
            danger_level: Filtrer par niveau de danger

        Returns:
            Liste des workflows
        """
        workflows = list(self.workflows.values())

        if category:
            workflows = [wf for wf in workflows if wf.category == category]

        if danger_level:
            workflows = [wf for wf in workflows if wf.danger_level == danger_level]

        return workflows

    def validate_inputs(
        self,
        workflow: Workflow,
        inputs: Dict[str, Any]
    ) -> tuple[bool, List[str]]:
        """
        Valide les inputs selon le schema du workflow

        Returns:
            (is_valid, errors_list)
        """
        errors = []

        # Vérifier les inputs requis
        for input_def in workflow.inputs:
            if input_def.required and input_def.name not in inputs:
                errors.append(f"Input requis manquant: {input_def.name}")

        # Valider les types et contraintes
        for input_def in workflow.inputs:
            if input_def.name not in inputs:
                continue

            value = inputs[input_def.name]

            # Validation type
            if not self._validate_type(value, input_def.type):
                errors.append(
                    f"Input {input_def.name}: type invalide "
                    f"(attendu: {input_def.type}, reçu: {type(value).__name__})"
                )

            # Validation contraintes
            if input_def.validation:
                validation_errors = self._validate_constraints(
                    input_def.name,
                    value,
                    input_def.validation
                )
                errors.extend(validation_errors)

        return len(errors) == 0, errors

    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Valide le type d'une valeur"""
        type_mapping = {
            "integer": int,
            "string": str,
            "boolean": bool,
            "array": list,
            "object": dict,
            "date": str,  # ISO format string
            "datetime": str  # ISO format string
        }

        expected_py_type = type_mapping.get(expected_type)
        if expected_py_type is None:
            return True  # Type inconnu, on accepte

        return isinstance(value, expected_py_type)

    def _validate_constraints(
        self,
        field_name: str,
        value: Any,
        constraints: Dict[str, Any]
    ) -> List[str]:
        """Valide les contraintes d'un champ"""
        errors = []

        # Enum
        if "enum" in constraints:
            if value not in constraints["enum"]:
                errors.append(
                    f"{field_name}: valeur invalide "
                    f"(autorisées: {', '.join(constraints['enum'])})"
                )

        # Min/Max pour int
        if isinstance(value, int):
            if "min" in constraints and value < constraints["min"]:
                errors.append(f"{field_name}: valeur minimum {constraints['min']}")
            if "max" in constraints and value > constraints["max"]:
                errors.append(f"{field_name}: valeur maximum {constraints['max']}")

        # Min/Max length pour string
        if isinstance(value, str):
            if "min_length" in constraints and len(value) < constraints["min_length"]:
                errors.append(f"{field_name}: longueur minimum {constraints['min_length']}")
            if "max_length" in constraints and len(value) > constraints["max_length"]:
                errors.append(f"{field_name}: longueur maximum {constraints['max_length']}")

        # Min/Max items pour array
        if isinstance(value, list):
            if "min_items" in constraints and len(value) < constraints["min_items"]:
                errors.append(f"{field_name}: minimum {constraints['min_items']} éléments")
            if "max_items" in constraints and len(value) > constraints["max_items"]:
                errors.append(f"{field_name}: maximum {constraints['max_items']} éléments")

        return errors

    async def generate_preview(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
        db = None
    ) -> WorkflowPreview:
        """
        Génère un preview du workflow avant exécution

        Args:
            workflow_id: ID du workflow
            inputs: Paramètres d'entrée
            db: Database session (optionnel, pour enrichir contexte)

        Returns:
            WorkflowPreview avec détails et warnings
        """
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            return WorkflowPreview(
                workflow_id=workflow_id,
                workflow_name="Unknown",
                danger_level=DangerLevel.HIGH,
                requires_confirmation=True,
                can_execute=False,
                blocking_issues=[f"Workflow {workflow_id} non trouvé"]
            )

        logger.info(
            "n8n_generating_preview",
            workflow_id=workflow_id,
            danger_level=workflow.danger_level
        )

        # Valider inputs
        is_valid, errors = self.validate_inputs(workflow, inputs)

        # Estimer les actions (basé sur template)
        estimated_actions = self._estimate_actions(workflow, inputs)

        # Identifier entités affectées
        affected_entities = await self._identify_affected_entities(workflow, inputs, db)

        # Générer texte preview
        preview_text = self._render_preview_text(workflow, inputs, affected_entities)

        # Warnings basés sur danger level
        warnings = []
        if workflow.danger_level in [DangerLevel.HIGH, DangerLevel.CRITICAL]:
            warnings.append("⚠️ Workflow à danger élevé - Vérifiez attentivement avant confirmation")

        if workflow.requires_confirmation:
            warnings.append("✋ Confirmation utilisateur obligatoire")

        # Blocking issues
        blocking_issues = []
        if not is_valid:
            blocking_issues.extend(errors)

        return WorkflowPreview(
            workflow_id=workflow_id,
            workflow_name=workflow.name,
            danger_level=workflow.danger_level,
            requires_confirmation=workflow.requires_confirmation,
            estimated_actions=estimated_actions,
            affected_entities=affected_entities,
            preview_text=preview_text,
            warnings=warnings,
            can_execute=is_valid,
            blocking_issues=blocking_issues
        )

    def _estimate_actions(self, workflow: Workflow, inputs: Dict[str, Any]) -> List[str]:
        """Estime les actions qui seront effectuées"""
        actions = []

        # Basé sur la catégorie
        if workflow.category == WorkflowCategory.EMERGENCY:
            actions.append("🚨 Envoi notifications urgentes")
            actions.append("📞 Contact professionnels d'urgence")
            actions.append("📋 Création ticket incident")

        elif workflow.category == WorkflowCategory.LEGAL:
            actions.append("📨 Envoi documents légaux")
            actions.append("📅 Création événement au calendrier")
            actions.append("📊 Génération rapport de tracking")

        elif workflow.category == WorkflowCategory.PROCUREMENT:
            actions.append("📧 Envoi demandes de devis")
            actions.append("🔗 Génération liens de suivi")

        elif workflow.category == WorkflowCategory.COMMUNICATION:
            actions.append("✉️ Envoi emails résidents")
            actions.append("📱 Envoi SMS si activé")

        elif workflow.category == WorkflowCategory.MAINTENANCE:
            actions.append("🔧 Planification intervention")
            actions.append("📢 Notification résidents")

        return actions

    async def _identify_affected_entities(
        self,
        workflow: Workflow,
        inputs: Dict[str, Any],
        db = None
    ) -> Dict[str, Any]:
        """Identifie les entités qui seront affectées"""
        affected = {}

        # Copropriété
        if "copropriete_id" in inputs and db:
            try:
                from app.models import Copropriete
                from sqlalchemy import select

                stmt = select(Copropriete).where(Copropriete.id == inputs["copropriete_id"])
                result = await db.execute(stmt)
                copro = result.scalar_one_or_none()

                if copro:
                    affected["copropriete"] = {
                        "id": copro.id,
                        "nom": copro.nom,
                        "ville": copro.ville,
                        "nombre_lots": copro.nombre_lots
                    }
            except Exception as e:
                logger.warning("n8n_preview_copro_fetch_error", error=str(e))

        # Résidents
        if "lot_numbers" in inputs:
            affected["lots"] = inputs["lot_numbers"]
            affected["residents_count_estimate"] = len(inputs["lot_numbers"])

        return affected

    def _render_preview_text(
        self,
        workflow: Workflow,
        inputs: Dict[str, Any],
        affected_entities: Dict[str, Any]
    ) -> str:
        """Génère le texte de preview (simple, pas de templating complexe)"""
        lines = [
            f"🔄 Workflow: {workflow.name}",
            f"📂 Catégorie: {workflow.category.value}",
            f"⚠️ Danger: {workflow.danger_level.value.upper()}",
            "",
            "📋 Paramètres:",
        ]

        for key, value in inputs.items():
            lines.append(f"  • {key}: {value}")

        if affected_entities:
            lines.append("")
            lines.append("🎯 Entités affectées:")
            for key, value in affected_entities.items():
                if isinstance(value, dict):
                    lines.append(f"  • {key}: {value.get('nom', value)}")
                else:
                    lines.append(f"  • {key}: {value}")

        return "\n".join(lines)

    async def execute_workflow(
        self,
        request: WorkflowExecutionRequest
    ) -> WorkflowExecutionResult:
        """
        Exécute un workflow N8N

        Args:
            request: Requête d'exécution

        Returns:
            WorkflowExecutionResult
        """
        workflow = self.get_workflow(request.workflow_id)
        if not workflow:
            return WorkflowExecutionResult(
                workflow_id=request.workflow_id,
                correlation_id=request.correlation_id or str(uuid.uuid4()),
                success=False,
                error=f"Workflow {request.workflow_id} non trouvé"
            )

        # Générer correlation_id si absent
        correlation_id = request.correlation_id or str(uuid.uuid4())

        logger.info(
            "n8n_executing_workflow",
            workflow_id=request.workflow_id,
            correlation_id=correlation_id,
            dry_run=request.dry_run
        )

        # Valider inputs
        is_valid, errors = self.validate_inputs(workflow, request.inputs)
        if not is_valid:
            return WorkflowExecutionResult(
                workflow_id=request.workflow_id,
                correlation_id=correlation_id,
                success=False,
                error=f"Inputs invalides: {', '.join(errors)}"
            )

        # Dry-run si demandé et supporté
        if request.dry_run:
            if not workflow.dry_run_supported:
                return WorkflowExecutionResult(
                    workflow_id=request.workflow_id,
                    correlation_id=correlation_id,
                    success=False,
                    error="Dry-run non supporté pour ce workflow"
                )

        # Construire payload N8N
        payload = {
            **request.inputs,
            "_meta": {
                "correlation_id": correlation_id,
                "user_id": request.user_id,
                "dry_run": request.dry_run,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        # Appeler N8N webhook
        start_time = datetime.utcnow()

        try:
            async with httpx.AsyncClient(timeout=workflow.timeout_seconds) as client:
                webhook_url = f"{self.n8n_base_url}{workflow.webhook_url}"

                response = await client.post(
                    webhook_url,
                    json=payload
                )

                execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

                if response.status_code == 200:
                    result_data = response.json()

                    logger.info(
                        "n8n_workflow_success",
                        workflow_id=request.workflow_id,
                        correlation_id=correlation_id,
                        execution_time_ms=execution_time_ms
                    )

                    return WorkflowExecutionResult(
                        workflow_id=request.workflow_id,
                        correlation_id=correlation_id,
                        success=True,
                        outputs=result_data.get("outputs", {}),
                        dry_run=request.dry_run,
                        execution_time_ms=execution_time_ms
                    )
                else:
                    error_msg = f"N8N error: HTTP {response.status_code}"
                    logger.error(
                        "n8n_workflow_http_error",
                        workflow_id=request.workflow_id,
                        status_code=response.status_code,
                        response=response.text
                    )

                    return WorkflowExecutionResult(
                        workflow_id=request.workflow_id,
                        correlation_id=correlation_id,
                        success=False,
                        error=error_msg,
                        execution_time_ms=execution_time_ms
                    )

        except httpx.TimeoutException:
            logger.error(
                "n8n_workflow_timeout",
                workflow_id=request.workflow_id,
                correlation_id=correlation_id,
                timeout=workflow.timeout_seconds
            )

            return WorkflowExecutionResult(
                workflow_id=request.workflow_id,
                correlation_id=correlation_id,
                success=False,
                error=f"Timeout après {workflow.timeout_seconds}s"
            )

        except Exception as e:
            logger.error(
                "n8n_workflow_exception",
                workflow_id=request.workflow_id,
                correlation_id=correlation_id,
                error=str(e),
                exc_info=True
            )

            return WorkflowExecutionResult(
                workflow_id=request.workflow_id,
                correlation_id=correlation_id,
                success=False,
                error=str(e)
            )
