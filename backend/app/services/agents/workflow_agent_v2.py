"""
WorkflowAgent V2 - Intelligent Workflow Orchestrator

⚠️ ARCHITECTURE NOTE (Phase 3 - World-Class SMA):
   This agent is wrapped by WrappedWorkflowAgent in wrapped_agents.py for integration
   with the new BaseAgent interface and AgentRegistry system.

   For new integrations, prefer using:
   - WrappedWorkflowAgent from app.services.agents.wrapped_agents
   - AgentRegistry for discovery and routing
   - ResilientAgent wrapper for production resilience

   See: base_agent.py, agent_registry.py, resilience.py

Specialized agent for understanding problems and generating actionable to-do lists
that guide users step-by-step through complex processes.

Capabilities:
- Automatic workflow classification (emergency, communication, maintenance, etc.)
- Context extraction (who, what, where, when, severity, professionals needed)
- Intelligent to-do list generation (from templates or LLM)
- Step-by-step execution guidance with human-in-the-loop
- Multi-professional coordination
- State persistence for workflow continuity

Use Cases:
- Emergency: "URGENT: Dégât des eaux apt 12" → Generate emergency response workflow
- Communication: "Convoquer AG le 15 décembre" → Generate AG invitation workflow
- Maintenance: "Organiser travaux hall" → Generate multi-professional coordination workflow

Architecture (inspired by LegalAgent):
1. User describes problem
2. WorkflowAgent classifies workflow type
3. Extracts context entities
4. Loads/generates intelligent to-do list
5. Enriches each step with SQL/RAG data
6. Returns interactive to-do for user validation
7. User validates step-by-step
8. N8N executes actions (emails, SMS, tickets)
9. ThoughtStream shows real-time progress
10. Auto-advances to next step

Brain (DisruptIQ) → Arms (N8N)
WorkflowAgent = The Conductor
"""

import structlog
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, date
import json
import re

from app.services.llm_service import LLMService


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")
from app.services.agents.thought_stream import ThoughtStream, ThoughtType
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import WorkflowInstance, WorkflowStep, WorkflowStatus, StepStatus
import uuid

logger = structlog.get_logger()


class WorkflowType:
    """Workflow type constants"""
    EMERGENCY = "emergency"
    COMMUNICATION = "communication"
    MAINTENANCE = "maintenance"
    ADMINISTRATIVE = "administrative"


class WorkflowAgentV2:
    """
    Intelligent Workflow Orchestrator

    Architecture:
    1. Classification: Determine workflow type and subtype
    2. Extraction: Extract key entities and context
    3. Generation: Generate intelligent to-do list
    4. Enrichment: Enrich steps with SQL/RAG data
    5. Execution: Guide user through step-by-step execution
    """

    def __init__(self):
        self.llm_service = LLMService()

        # Workflow type definitions
        self.workflow_types = {
            WorkflowType.EMERGENCY: {
                "subtypes": ["water_leak", "fire", "electrical", "gas_leak", "structural", "flooding"],
                "urgency": "critical",
                "requires_immediate_action": True,
                "professional_types": ["plumber", "electrician", "engineer", "firefighter", "roofer"],
                "template_available": True
            },
            WorkflowType.COMMUNICATION: {
                "subtypes": ["ag_invitation", "info_broadcast", "vote_request", "work_notice", "regulation_update"],
                "urgency": "normal",
                "requires_immediate_action": False,
                "professional_types": [],
                "template_available": True
            },
            WorkflowType.MAINTENANCE: {
                "subtypes": ["scheduled_maintenance", "inspection", "cleaning", "renovation", "repair"],
                "urgency": "low",
                "requires_immediate_action": False,
                "professional_types": ["maintenance_company", "inspector", "cleaner", "painter", "gardener"],
                "template_available": False
            },
            WorkflowType.ADMINISTRATIVE: {
                "subtypes": ["document_request", "complaint_handling", "insurance_claim", "contract_renewal"],
                "urgency": "normal",
                "requires_immediate_action": False,
                "professional_types": ["lawyer", "insurance_agent", "accountant"],
                "template_available": False
            }
        }

        # Keywords for classification
        self.workflow_keywords = {
            WorkflowType.EMERGENCY: [
                "urgent", "urgence", "fuite", "eau", "incendie", "feu", "électrique",
                "court-circuit", "gaz", "fissure", "effondrement", "inondation", "dégât"
            ],
            WorkflowType.COMMUNICATION: [
                "assemblée", "ag", "convoquer", "inviter", "informer", "prévenir",
                "annonce", "vote", "décision", "travaux", "règlement"
            ],
            WorkflowType.MAINTENANCE: [
                "travaux", "rénovation", "entretien", "maintenance", "réparation",
                "nettoyage", "peinture", "hall", "ascenseur", "jardin"
            ],
            WorkflowType.ADMINISTRATIVE: [
                "contrat", "assurance", "document", "réclamation", "plainte",
                "comptabilité", "facture", "juridique"
            ]
        }

        logger.info("workflow_agent_v2_initialized",
                   workflow_types=len(self.workflow_types))

    async def process_request(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        db: Optional[AsyncSession] = None,
        thought_stream: Optional[ThoughtStream] = None
    ) -> Dict[str, Any]:
        """
        Central entry point for all workflow requests.

        The WorkflowAgent analyzes the user's request and decides which workflow
        to execute, then generates an intelligent to-do list.

        Architecture principle (like LegalAgent):
        - Orchestrator routes to WorkflowAgent (WHAT agent)
        - WorkflowAgent decides the workflow (HOW to process)

        Args:
            user_input: Raw user query describing the problem
            context: Optional context (building, user, history, etc.)
            db: Database session for SQL operations
            thought_stream: Optional ThoughtStream for real-time CoT

        Returns:
            Dict with:
                - workflow_type: Type of workflow ("emergency", "communication", etc.)
                - subtype: Specific subtype ("water_leak", "ag_invitation", etc.)
                - todo_list: Intelligent to-do list with enriched steps
                - context_data: Extracted entities and context
                - success: Boolean success status
                - message: Human-readable message
        """
        try:
            logger.info("workflow_request_received", query=user_input[:100])

            if thought_stream:
                await thought_stream.add_thought(
                    thought_type=ThoughtType.PROCESSING,
                    title="🧠 Analyse de votre demande",
                    content="Classification du type de workflow...",
                    agent="WorkflowAgent",
                    progress=0.1
                )

            # Step 1: Classify workflow type
            classification = await self.classify_workflow_type(user_input)

            logger.info("workflow_classified",
                       workflow_type=classification["workflow_type"],
                       subtype=classification["subtype"],
                       confidence=classification["confidence"])

            if thought_stream:
                await thought_stream.add_thought(
                    thought_type=ThoughtType.PROCESSING,
                    title=f"📋 Workflow détecté: {classification['subtype']}",
                    content=f"Type: {classification['workflow_type']} | Confiance: {classification['confidence']:.0%}",
                    agent="WorkflowAgent",
                    progress=0.3
                )

            # Step 2: Extract context entities
            extracted_context = await self.extract_context(
                user_input=user_input,
                workflow_type=classification["workflow_type"],
                subtype=classification["subtype"],
                context=context
            )

            logger.info("context_extracted",
                       entities=list(extracted_context.keys()))

            if thought_stream:
                await thought_stream.add_thought(
                    thought_type=ThoughtType.PROCESSING,
                    title="🔍 Contexte extrait",
                    content=f"Bâtiment: {extracted_context.get('building_name', 'N/A')}, "
                           f"Gravité: {extracted_context.get('severity', 'N/A').upper()}",
                    agent="WorkflowAgent",
                    progress=0.5
                )

            # Step 3: Generate/Load intelligent to-do list
            todo_list = await self.generate_todo_list(
                workflow_type=classification["workflow_type"],
                subtype=classification["subtype"],
                context=extracted_context,
                db=db
            )

            logger.info("todo_list_generated",
                       steps=len(todo_list["steps"]))

            if thought_stream:
                await thought_stream.add_thought(
                    thought_type=ThoughtType.COMPLETED,
                    title="✅ To-Do List prête",
                    content=f"{len(todo_list['steps'])} étapes générées et enrichies",
                    agent="WorkflowAgent",
                    progress=1.0
                )

            # Step 4: Persist workflow if DB session available
            workflow_id = None
            if db:
                try:
                    workflow_instance = await self._create_workflow_instance(
                        db=db,
                        workflow_type=classification["workflow_type"],
                        subtype=classification["subtype"],
                        context=extracted_context,
                        todo_list=todo_list
                    )
                    workflow_id = workflow_instance.id
                    logger.info("workflow_persisted", workflow_id=workflow_id)
                    
                    if thought_stream:
                        await thought_stream.add_thought(
                            thought_type=ThoughtType.COMPLETED,
                            title="💾 Workflow sauvegardé",
                            content=f"ID: {workflow_id}",
                            agent="WorkflowAgent",
                            progress=1.0
                        )
                except Exception as e:
                    logger.error("workflow_persistence_failed", error=str(e))
                    # Don't fail the request if persistence fails, just log it

            # Step 5: Return workflow for user validation
            return {
                "success": True,
                "workflow_id": workflow_id,
                "workflow_type": classification["workflow_type"],
                "subtype": classification["subtype"],
                "confidence": classification["confidence"],
                "context_data": extracted_context,
                "todo_list": todo_list,
                "message": self._generate_summary_message(
                    workflow_type=classification["workflow_type"],
                    subtype=classification["subtype"],
                    todo_list=todo_list,
                    context=extracted_context
                )
            }

        except Exception as e:
            logger.error("workflow_processing_failed", error=str(e), exc_info=True)
            if thought_stream:
                await thought_stream.add_thought(
                    thought_type=ThoughtType.ERROR,
                    title="❌ Erreur lors de l'analyse",
                    content=str(e),
                    agent="WorkflowAgent",
                    progress=1.0
                )
            return {
                "success": False,
                "message": f"Erreur lors du traitement du workflow: {str(e)}"
            }

    async def classify_workflow_type(
        self,
        user_input: str
    ) -> Dict[str, Any]:
        """
        Classify user request into workflow type and subtype using LLM.

        First tries keyword matching for speed, then uses LLM for complex cases.

        Returns:
            {
                "workflow_type": "emergency",
                "subtype": "water_leak",
                "confidence": 0.95,
                "reasoning": "Keywords detected: urgent, fuite, eau, plafond"
            }
        """
        # Quick keyword-based classification
        keyword_match = self._keyword_classification(user_input)
        if keyword_match["confidence"] > 0.8:
            return keyword_match

        # LLM-based classification for complex cases
        prompt = f"""Tu es un expert en gestion de copropriété.

DEMANDE UTILISATEUR:
{user_input}

TYPES DE WORKFLOW DISPONIBLES:
1. emergency: Urgences (fuites, incendies, pannes électriques, etc.)
   Sous-types: water_leak, fire, electrical, gas_leak, structural, flooding

2. communication: Communications (AG, informations, votes, annonces)
   Sous-types: ag_invitation, info_broadcast, vote_request, work_notice, regulation_update

3. maintenance: Maintenance et travaux (entretien, rénovations, réparations)
   Sous-types: scheduled_maintenance, inspection, cleaning, renovation, repair

4. administrative: Administratif (contrats, assurances, réclamations)
   Sous-types: document_request, complaint_handling, insurance_claim, contract_renewal

CLASSIFIE cette demande au format JSON:
{{
  "workflow_type": "emergency|communication|maintenance|administrative",
  "subtype": "subtype_spécifique",
  "confidence": 0.0-1.0,
  "reasoning": "Brève explication"
}}

Réponds UNIQUEMENT avec le JSON, sans markdown."""

        response = await self.llm_service.generate_response(
            prompt=prompt,
            temperature=0.2,
            max_tokens=300
        )

        try:
            clean_response = re.sub(r'```json\n?|```\n?', '', response.strip())
            classification = json.loads(clean_response)
            return classification
        except Exception as e:
            logger.error("classification_parsing_failed", error=str(e), response=response)
            # Fallback to keyword match
            return keyword_match

    def _keyword_classification(self, user_input: str) -> Dict[str, Any]:
        """Quick keyword-based classification"""
        user_input_lower = user_input.lower()

        scores = {}
        for workflow_type, keywords in self.workflow_keywords.items():
            score = sum(1 for kw in keywords if kw in user_input_lower)
            scores[workflow_type] = score

        if max(scores.values()) == 0:
            return {
                "workflow_type": WorkflowType.ADMINISTRATIVE,
                "subtype": "document_request",
                "confidence": 0.3,
                "reasoning": "Aucun mot-clé détecté, fallback sur administrative"
            }

        best_type = max(scores, key=scores.get)

        # Determine subtype based on keywords
        subtype_map = {
            WorkflowType.EMERGENCY: {
                "water_leak": ["fuite", "eau", "dégât des eaux", "plafond", "inondation"],
                "fire": ["incendie", "feu", "fumée", "brûlé"],
                "electrical": ["électrique", "court-circuit", "panne", "électricité"],
                "gas_leak": ["gaz", "odeur", "fuite de gaz"]
            },
            WorkflowType.COMMUNICATION: {
                "ag_invitation": ["assemblée", "ag", "convoquer", "convocation"],
                "info_broadcast": ["informer", "prévenir", "annonce"],
                "vote_request": ["vote", "voter", "décision"]
            }
        }

        subtype = self.workflow_types[best_type]["subtypes"][0]  # Default
        if best_type in subtype_map:
            for sub, kws in subtype_map[best_type].items():
                if any(kw in user_input_lower for kw in kws):
                    subtype = sub
                    break

        confidence = min(scores[best_type] / 3, 1.0)  # 3+ keywords = high confidence

        return {
            "workflow_type": best_type,
            "subtype": subtype,
            "confidence": confidence,
            "reasoning": f"Mots-clés détectés: {scores[best_type]}"
        }

    async def extract_context(
        self,
        user_input: str,
        workflow_type: str,
        subtype: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Extract key entities and context from user input using LLM.

        Similar to emergency_workflow_service._extract_incident_data()
        but more generic for all workflow types.

        Returns:
            {
                "building_name": "Résidence Les Tilleuls",
                "apartment_number": "12",
                "floor": 3,
                "owner_name": "M. Dupont",
                "severity": "high",
                "professionals_needed": ["plumber"],
                "description": "...",
                "missing_info": ["contact plombier", "photos"]
            }
        """
        prompt = f"""Tu es un expert en gestion de copropriété.

DEMANDE UTILISATEUR:
{user_input}

TYPE DE WORKFLOW: {workflow_type} - {subtype}

CONTEXTE DISPONIBLE:
{json.dumps(context or {}, indent=2, ensure_ascii=False, default=json_serial)}

EXTRAIT les informations clés au format JSON:
{{
  "building_name": "Nom de la copropriété (ou 'Non spécifié')",
  "building_address": "Adresse si disponible",
  "floor": <numéro ou null>,
  "apartment_number": "Numéro d'appartement (ou 'Non spécifié')",
  "owner_name": "Nom du propriétaire/occupant",
  "owner_email": "Email si mentionné",
  "owner_phone": "Téléphone si mentionné",
  "description": "Description détaillée de la situation",
  "severity": "low|medium|high|critical",
  "professionals_needed": ["Liste des professionnels nécessaires: plumber, electrician, etc."],
  "affected_areas": ["Zones impactées"],
  "urgency_level": "immediate|urgent|normal|low",
  "missing_info": ["Informations manquantes pour traiter efficacement"],
  "legal_deadlines": ["Délais légaux si applicables (ex: 21 jours pour AG)"]
}}

Réponds UNIQUEMENT avec le JSON, sans markdown."""

        response = await self.llm_service.generate_response(
            prompt=prompt,
            temperature=0.2,
            max_tokens=600
        )

        try:
            clean_response = re.sub(r'```json\n?|```\n?', '', response.strip())
            extracted = json.loads(clean_response)
            return extracted
        except Exception as e:
            logger.error("context_extraction_failed", error=str(e), response=response)
            # Return safe defaults
            return {
                "building_name": "Non spécifié",
                "building_address": "Non spécifié",
                "floor": None,
                "apartment_number": "Non spécifié",
                "owner_name": "Non spécifié",
                "description": user_input,
                "severity": "medium",
                "professionals_needed": [],
                "affected_areas": [],
                "urgency_level": "normal",
                "missing_info": []
            }

    async def generate_todo_list(
        self,
        workflow_type: str,
        subtype: str,
        context: Dict[str, Any],
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Generate intelligent to-do list for the workflow.

        Strategy:
        1. Try to load template from DB (emergency_workflows table)
        2. If no template, generate using LLM
        3. Enrich each step with context data

        Returns:
            {
                "workflow_name": "Dégât des eaux - Procédure standard",
                "estimated_duration": "15-20 minutes",
                "total_steps": 7,
                "steps": [
                    {
                        "step_id": 1,
                        "title": "Sécuriser la zone",
                        "description": "...",
                        "type": "manual|email|sms|multi_channel|query|export",
                        "is_critical": True,
                        "can_skip": False,
                        "actions": [
                            {
                                "action_id": "verify_water_off",
                                "label": "Vérifier que l'eau est coupée",
                                "type": "manual_check"
                            }
                        ],
                        "status": "pending"
                    },
                    ...
                ]
            }
        """
        # V2: ALWAYS generate with LLM for maximum operational value
        # Templates will be used later for faster generation once LLM output is validated
        logger.info("generating_operational_todo_with_llm", workflow_type=workflow_type, subtype=subtype)
        return await self._generate_todo_with_llm(
            workflow_type=workflow_type,
            subtype=subtype,
            context=context
        )

    def _enrich_template_with_context(
        self,
        template: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enrich template steps with extracted context data"""
        enriched = template.copy()

        for step in enriched.get("steps", []):
            # Add context data to each step
            step["context_data"] = context

            # Fill template variables in title/description
            if "{{" in step.get("title", ""):
                step["title"] = self._fill_template_vars(step["title"], context)
            if "{{" in step.get("description", ""):
                step["description"] = self._fill_template_vars(step["description"], context)

        return enriched

    def _fill_template_vars(self, template_str: str, data: Dict[str, Any]) -> str:
        """Replace {{variable}} with actual values"""
        result = template_str
        for key, value in data.items():
            placeholder = f"{{{{{key}}}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value) if value else "Non spécifié")
        return result

    async def _generate_todo_with_llm(
        self,
        workflow_type: str,
        subtype: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate HIGHLY OPERATIONAL to-do list using LLM"""
        prompt = f"""Tu es un expert en gestion de copropriété et tu dois créer une TO-DO LIST ULTRA-OPÉRATIONNELLE pour un syndic.

SITUATION:
Type: {workflow_type} - {subtype}
Contexte: {json.dumps(context, indent=2, ensure_ascii=False, default=json_serial)}

IMPORTANT: Cette to-do list doit être IMMÉDIATEMENT ACTIONNABLE par le syndic.
Chaque étape doit contenir:
1. QUI contacter (personne/service précis)
2. POURQUOI (justification claire)
3. QUELLES INFORMATIONS transmettre (checklist complète)
4. QUELS DOCUMENTS préparer (photos, rapports, etc.)
5. ACTIONS SMART disponibles (boutons pour aider)

EXEMPLE DE STEP OPÉRATIONNELLE (pour urgence):
{{
  "step_id": 1,
  "title": "Sécuriser l'installation électrique",
  "description": "Contacter EDF/Enedis ou l'électricien partenaire car risque d'électrocution et court-circuit. Eau proche du compteur électrique.",
  "contact_who": "EDF/Enedis ou électricien d'urgence partenaire",
  "contact_why": "Risque électrocution + court-circuit si eau atteint compteur",
  "info_needed": [
    "Adresse complète de la copropriété",
    "Cage d'escalier / étage",
    "Numéro d'appartement concerné",
    "Mentionner explicitement: 'Eau proche du compteur électrique'",
    "État actuel: électricité coupée ou non"
  ],
  "documents_needed": [
    "Photo du compteur électrique menacé (si disponible)",
    "Photo de la source de la fuite"
  ],
  "type": "multi_channel",
  "is_critical": true,
  "urgency_level": "immediate",
  "estimated_duration": "5 minutes",
  "actions": [
    {{
      "action_id": "find_electrician",
      "label": "Trouver électricien d'urgence",
      "type": "find_professionals",
      "payload": {{"profession": "electrician", "urgency": "immediate"}}
    }},
    {{
      "action_id": "prepare_emergency_call",
      "label": "Préparer script d'appel",
      "type": "generate_script",
      "payload": {{"script_type": "emergency_electrical"}}
    }}
  ]
}}

GÉNÈRE maintenant une to-do list COMPLÈTE et OPÉRATIONNELLE au format JSON:

{{
  "workflow_name": "Nom descriptif du workflow",
  "estimated_duration": "Durée totale estimée (ex: 30-45 minutes)",
  "total_steps": <nombre d'étapes>,
  "steps": [
    {{
      "step_id": <numéro>,
      "title": "Action claire et précise",
      "description": "Description complète avec contexte",
      "contact_who": "Qui contacter précisément",
      "contact_why": "Pourquoi cette action est nécessaire",
      "info_needed": ["Liste des infos à fournir"],
      "documents_needed": ["Liste des docs à préparer"],
      "type": "manual|email|phone_call|multi_channel",
      "is_critical": true|false,
      "urgency_level": "immediate|urgent|normal",
      "estimated_duration": "Durée estimée pour ce step",
      "actions": [
        {{
          "action_id": "identifiant_unique",
          "label": "Action concrète proposée",
          "type": "find_professionals|prepare_email|generate_script|create_report|find_contacts",
          "payload": {{}}
        }}
      ]
    }}
  ]
}}

RÈGLES STRICTES:
- JAMAIS de steps génériques comme "Notifier le propriétaire" sans détails
- TOUJOURS expliquer QUI, POURQUOI, QUELLES INFOS, QUELS DOCS
- TOUJOURS proposer des actions concrètes (boutons)
- Ordre CHRONOLOGIQUE et LOGIQUE
- Steps CRITIQUES en premier
- Durées RÉALISTES
- Pour les tâches du syndic: NE PAS écrire "Contacter: Syndic (vous-même)" mais directement l'action
  EXEMPLE: "contact_who": "Action interne" ou omettre ce champ si c'est une tâche interne
- Être DIRECT et ACTIONNABLE, pas de formulations inutiles

Réponds UNIQUEMENT avec le JSON, sans markdown."""

        response = await self.llm_service.generate_response(
            prompt=prompt,
            temperature=0.3,
            max_tokens=4000  # Increased for exhaustive to-do lists
        )

        try:
            clean_response = re.sub(r'```json\n?|```\n?', '', response.strip())
            todo_list = json.loads(clean_response)
            return todo_list
        except Exception as e:
            logger.error("todo_generation_failed", error=str(e), response=response)
            # Fallback to minimal to-do
            return {
                "workflow_name": f"{workflow_type} - {subtype}",
                "estimated_duration": "Non estimé",
                "total_steps": 1,
                "steps": [
                    {
                        "step_id": 1,
                        "title": "Analyser la situation",
                        "description": context.get("description", "Veuillez analyser la situation et définir les actions nécessaires"),
                        "type": "manual",
                        "is_critical": True,
                        "can_skip": False,
                        "actions": []
                    }
                ]
            }

    def _generate_summary_message(
        self,
        workflow_type: str,
        subtype: str,
        todo_list: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """Generate OPERATIONAL summary message with actionable details"""
        severity_emoji = {
            "critical": "🚨",
            "high": "⚠️",
            "medium": "📋",
            "low": "📝"
        }

        emoji = severity_emoji.get(context.get("severity", "medium"), "📋")

        message = f"{emoji} **{todo_list.get('workflow_name', 'Workflow')}**\n\n"

        # Context summary
        if context.get("building_name") != "Non spécifié":
            message += f"**📍 Contexte:**\n"
            message += f"- Bâtiment: {context.get('building_name')}\n"
            if context.get("apartment_number") != "Non spécifié":
                message += f"- Appartement: {context.get('apartment_number')}\n"
            if context.get("floor"):
                message += f"- Étage: {context.get('floor')}\n"
            if context.get("description"):
                message += f"- Situation: {context.get('description')}\n"
            message += f"- Gravité: **{context.get('severity', 'N/A').upper()}**\n\n"

        # Operational to-do summary
        total_steps = len(todo_list.get("steps", []))

        message += f"**📋 Plan d'action ({total_steps} étape{'s' if total_steps > 1 else ''}):**\n\n"

        for i, step in enumerate(todo_list.get("steps", []), 1):  # Show ALL steps with ALL details
            # Critical marker
            if step.get("is_critical"):
                urgency_mark = "🔴 CRITIQUE"
            elif step.get("urgency_level") == "immediate":
                urgency_mark = "🟠 URGENT"
            else:
                urgency_mark = "🟢"

            message += f"**{i}. {step.get('title')}** {urgency_mark}\n"

            # Contact who
            if step.get("contact_who"):
                message += f"   → Contacter: {step.get('contact_who')}\n"

            # Why
            if step.get("contact_why"):
                message += f"   → Pourquoi: {step.get('contact_why')}\n"

            # Info needed (ALL of them)
            if step.get("info_needed") and len(step.get("info_needed", [])) > 0:
                info_list = step.get("info_needed", [])
                message += f"   → Infos nécessaires:\n"
                for info in info_list:
                    message += f"     • {info}\n"

            # Estimated duration
            if step.get("estimated_duration"):
                message += f"   ⏱️ {step.get('estimated_duration')}\n"

            message += "\n"

        # Summary footer (ALL steps shown, no truncation)
        message += f"⏱️ **Durée totale estimée:** {todo_list.get('estimated_duration', 'Non estimée')}\n\n"
        message += f"💡 **Utilisez les actions suggérées pour gagner du temps.**"

        return message

    async def _create_workflow_instance(
        self,
        db: AsyncSession,
        workflow_type: str,
        subtype: str,
        context: Dict[str, Any],
        todo_list: Dict[str, Any]
    ) -> WorkflowInstance:
        """Create and persist a new workflow instance with steps"""
        
        # Create instance
        instance_id = str(uuid.uuid4())
        workflow_instance = WorkflowInstance(
            id=instance_id,
            workflow_type=workflow_type,
            subtype=subtype,
            title=todo_list.get("workflow_name", f"Workflow {subtype}"),
            status=WorkflowStatus.PENDING,
            context_data=context,
            current_step_index=0
        )
        
        db.add(workflow_instance)
        
        # Create steps
        for i, step_data in enumerate(todo_list.get("steps", [])):
            step = WorkflowStep(
                workflow_instance_id=instance_id,
                step_index=i,
                title=step_data.get("title", f"Step {i+1}"),
                description=step_data.get("description"),
                step_type=step_data.get("type", "manual"),
                is_critical=step_data.get("is_critical", False),
                status=StepStatus.PENDING,
                step_data=step_data # Store full step data including actions
            )
            db.add(step)
            
        await db.commit()
        await db.refresh(workflow_instance)
        
        return workflow_instance

    def list_workflow_types(self) -> List[Dict[str, Any]]:
        """List all available workflow types with metadata"""
        return [
            {
                "workflow_type": wf_type,
                "subtypes": config["subtypes"],
                "urgency": config["urgency"],
                "professional_types": config["professional_types"],
                "template_available": config["template_available"]
            }
            for wf_type, config in self.workflow_types.items()
        ]
