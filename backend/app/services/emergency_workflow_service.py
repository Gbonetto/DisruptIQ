"""
Emergency Workflow Service - V1 Simplified

Manages emergency workflow to-do lists.
V1 Scope: Only 'water_leak' workflow with context enrichment.
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import structlog
import re

from app.models.emergency_workflow import EmergencyWorkflow
from app.services.llm_service import LLMService

logger = structlog.get_logger()


class EmergencyWorkflowService:
    """
    Manages emergency workflow templates and enrichment

    V1 Features:
    - Fetch 'water_leak' workflow template
    - Enrich steps with extracted data from user input
    - Generate email/SMS previews
    - Track usage

    V2+ (Future):
    - Dynamic workflow generation
    - Save as template
    - Multiple workflow types
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm_service = LLMService()

    async def get_workflow(
        self,
        workflow_type: str,
        tenant_id: str = "default"
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve active workflow template for given type

        V1: Only 'water_leak' supported
        Returns None if workflow doesn't exist
        """
        query = select(EmergencyWorkflow).where(
            and_(
                EmergencyWorkflow.tenant_id == tenant_id,
                EmergencyWorkflow.workflow_type == workflow_type,
                EmergencyWorkflow.is_active == True
            )
        )

        result = await self.db.execute(query)
        workflow = result.scalar_one_or_none()

        if workflow:
            logger.info(
                "emergency_workflow_found",
                workflow_type=workflow_type,
                workflow_id=workflow.id
            )

            # Increment usage counter
            workflow.usage_count += 1
            await self.db.commit()

            return workflow.checklist

        logger.warning(
            "emergency_workflow_not_found",
            workflow_type=workflow_type,
            tenant_id=tenant_id
        )
        return None

    async def enrich_workflow_with_context(
        self,
        workflow: Dict[str, Any],
        user_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Enrich workflow steps with real data extracted from user input

        Process:
        1. Extract key details from user input (LLM)
        2. For each step, fill in template variables
        3. Generate message previews (email/SMS)

        V1: Basic extraction + preview generation
        V2+: SQL joins for recipients, RAG for professionals
        """
        # Step 1: Extract incident details from user input
        extracted_data = await self._extract_incident_data(user_input, context)

        logger.info(
            "extracted_incident_data",
            data=extracted_data
        )

        # Step 2: Enrich each workflow step
        enriched_steps = []
        for step in workflow.get("steps", []):
            enriched_step = step.copy()

            # Generate preview if it's a communication action
            if step["workflow_action"] in ["send_email", "send_sms", "send_multi_channel_alert"]:
                preview = self._generate_message_preview(
                    template=step["payload_template"],
                    data=extracted_data
                )
                enriched_step["preview"] = preview

            # Attach extracted data to step
            enriched_step["extracted_data"] = extracted_data
            enriched_steps.append(enriched_step)

        # Step 3: Return enriched workflow
        enriched_workflow = workflow.copy()
        enriched_workflow["steps"] = enriched_steps
        enriched_workflow["context_data"] = extracted_data

        return enriched_workflow

    async def _extract_incident_data(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Extract structured data from user's emergency description

        Uses LLM to extract:
        - Building/apartment details
        - Severity
        - Description
        - Actions already taken
        """
        prompt = f"""Tu es un expert en analyse d'urgences pour copropriétés.

DEMANDE UTILISATEUR:
{user_input}

CONTEXTE DISPONIBLE:
{context or {}}

EXTRAIT les informations suivantes au format JSON (si l'info n'est pas mentionnée, utilise des valeurs par défaut raisonnables):

{{
  "building_name": "Nom de la copropriété (ou 'Résidence' si non mentionné)",
  "building_address": "Adresse complète si disponible (ou 'Non spécifié')",
  "floor": <numéro étage en chiffre ou null>,
  "apartment_number": "Numéro d'appartement (ou 'Non spécifié')",
  "owner_name": "Nom du propriétaire si mentionné (ou 'Copropriétaire')",
  "incident_type": "Type court (ex: 'fuite d'eau', 'dégât des eaux')",
  "incident_description": "Description détaillée de la situation",
  "severity": "low|medium|high|critical",
  "actions_taken": ["Liste des actions déjà prises"],
  "affected_floors": ["Liste des étages impactés"],
  "reporter": "Qui a signalé (gardien, propriétaire, etc.)"
}}

Réponds UNIQUEMENT avec le JSON, sans markdown ni explication."""

        response = await self.llm_service.generate_response(
            prompt=prompt,
            temperature=0.2,
            max_tokens=500
        )

        # Parse JSON
        try:
            import json
            # Remove markdown code blocks if present
            clean_response = re.sub(r'```json\n?|```\n?', '', response.strip())
            extracted = json.loads(clean_response)
            return extracted
        except Exception as e:
            logger.error("failed_to_parse_extracted_data", error=str(e), response=response)
            # Return safe defaults
            return {
                "building_name": "Résidence",
                "building_address": "Non spécifié",
                "floor": None,
                "apartment_number": "Non spécifié",
                "owner_name": "Copropriétaire",
                "incident_type": "urgence",
                "incident_description": user_input,
                "severity": "high",
                "actions_taken": [],
                "affected_floors": [],
                "reporter": "Non spécifié"
            }

    def _generate_message_preview(
        self,
        template: Dict[str, Any],
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate email/SMS preview by filling template with extracted data

        Simple string substitution using {{variable}} syntax
        """
        email_subject = template.get("email_subject", "")
        email_body_template = template.get("email_body_template", "")

        # Replace template variables
        subject_filled = self._fill_template(email_subject, data)
        body_filled = self._fill_template(email_body_template, data)

        return {
            "type": template.get("workflow_action", "email"),
            "subject": subject_filled,
            "body": body_filled,
            "recipients": self._get_recipients_placeholder(template.get("recipient_source")),
            "has_sms_fallback": template.get("sms_fallback", False)
        }

    def _fill_template(self, template_str: str, data: Dict[str, Any]) -> str:
        """Replace {{variable}} with actual values from data"""
        result = template_str

        # Replace all {{key}} with values from data
        for key, value in data.items():
            placeholder = f"{{{{{key}}}}}"
            if placeholder in result:
                # Handle lists specially
                if isinstance(value, list):
                    result = result.replace(placeholder, ", ".join(str(v) for v in value) if value else "Aucun")
                else:
                    result = result.replace(placeholder, str(value) if value else "Non spécifié")

        return result

    def _get_recipients_placeholder(self, recipient_source: Optional[str]) -> List[str]:
        """
        Get recipient list placeholder

        V1: Returns generic placeholders
        V2+: Will query SQL for actual contacts
        """
        if recipient_source == "owner_from_SQL":
            return ["propriétaire@email.com (sera résolu depuis SQL)"]
        elif recipient_source == "neighbors_from_SQL":
            return ["voisin1@email.com", "voisin2@email.com (seront résolus depuis SQL)"]
        elif recipient_source == "plumbers_sql_list":
            return ["plombier-urgence@example.com (sera résolu depuis SQL)"]
        elif recipient_source == "water_provider_sql":
            return ["fournisseur-eau@example.com (sera résolu depuis SQL)"]
        else:
            return ["destinataire@example.com"]

    async def increment_usage(self, workflow_id: int) -> None:
        """Track workflow usage"""
        query = select(EmergencyWorkflow).where(EmergencyWorkflow.id == workflow_id)
        result = await self.db.execute(query)
        workflow = result.scalar_one_or_none()

        if workflow:
            workflow.usage_count += 1
            await self.db.commit()
            logger.info("workflow_usage_incremented", workflow_id=workflow_id, count=workflow.usage_count)
