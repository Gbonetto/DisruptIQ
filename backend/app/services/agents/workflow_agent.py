"""
Workflow Agent - Triggers N8N workflows with contextual data

Enhanced with:
- LLM-based workflow family classification
- Standardized payload generation
- ThoughtStream integration for real-time updates
"""

import structlog
from typing import Dict, Any, List, Optional
from enum import Enum
import httpx
from datetime import datetime

from app.core.config import settings
from app.services.llm_service import LLMService
from app.services.agents.thought_stream import ThoughtStream, ThoughtType

logger = structlog.get_logger()


class WorkflowFamily(str, Enum):
    """
    Workflow families as defined in SPECIFICATION_N8N_INTEGRATION.md
    """
    COMMUNICATION = "COMMUNICATION"  # Emails, SMS, notifications
    URGENCE = "URGENCE"             # Emergency workflows
    GESTION = "GESTION"             # Management tasks
    DIGEST = "DIGEST"               # Scheduled reports


class UrgencyLevel(str, Enum):
    """Workflow urgency levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorkflowAgent:
    """
    Workflow Agent - Manages N8N workflow triggers with intelligent classification

    Architecture:
    1. Receives user request from Orchestrator
    2. Classifies workflow family using LLM
    3. Builds standardized payload with trace context
    4. Triggers N8N webhook
    5. Returns confirmation to user

    N8N workflows send real-time updates via callback endpoints.
    """

    # Workflow mapping: action → N8N webhook path
    WORKFLOWS = {
        # COMMUNICATION family
        "send_email": "email-individual",
        "send_email_building": "email-building-residents",
        "send_email_professional": "email-professional",

        # URGENCE family
        "emergency_water_leak": "emergency-water-leak",
        "emergency_fire": "emergency-fire-alert",
        "emergency_lockdown": "building-lockdown",

        # GESTION family
        "payment_reminder": "cotisation-reminder",
        "document_collection": "document-collection-request",
        "meeting_preparation": "ag-meeting-preparation",

        # DIGEST family
        "daily_digest": "daily-syndic-digest",
        "weekly_report": "weekly-building-report",
        "monthly_summary": "monthly-financial-summary"
    }

    # Workflow family classification
    FAMILY_MAPPING = {
        "send_email": WorkflowFamily.COMMUNICATION,
        "send_email_building": WorkflowFamily.COMMUNICATION,
        "send_email_professional": WorkflowFamily.COMMUNICATION,
        "emergency_water_leak": WorkflowFamily.URGENCE,
        "emergency_fire": WorkflowFamily.URGENCE,
        "emergency_lockdown": WorkflowFamily.URGENCE,
        "payment_reminder": WorkflowFamily.GESTION,
        "document_collection": WorkflowFamily.GESTION,
        "meeting_preparation": WorkflowFamily.GESTION,
        "daily_digest": WorkflowFamily.DIGEST,
        "weekly_report": WorkflowFamily.DIGEST,
        "monthly_summary": WorkflowFamily.DIGEST
    }

    def __init__(self):
        self.n8n_base_url = settings.N8N_WEBHOOK_BASE_URL
        self.auth_token = settings.N8N_WEBHOOK_AUTH_TOKEN
        self.timeout = settings.N8N_TIMEOUT
        self.llm_service = LLMService()
        logger.info("workflow_agent_initialized", base_url=self.n8n_base_url)

    async def process_request(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        thought_stream: Optional[ThoughtStream] = None,
        conversation_id: Optional[str] = None,
        tenant_id: str = "default",
        user_id: str = "anonymous"
    ) -> Dict[str, Any]:
        """
        Main entry point for workflow processing

        Args:
            user_input: User's natural language request
            context: Conversation context (active docs, history, etc.)
            thought_stream: Stream for real-time UI updates
            conversation_id: Conversation identifier
            tenant_id: Tenant/syndic identifier
            user_id: User identifier

        Returns:
            Dict with success, message, workflow_result
        """
        try:
            if thought_stream:
                await thought_stream.add_thought(
                    thought_type=ThoughtType.PROCESSING,
                    title="Analyse de la demande de workflow",
                    content=f"Classification: {user_input[:80]}...",
                    agent="WorkflowAgent",
                    progress=0.1
                )

            # Step 1: Classify workflow family and action using LLM
            classification = await self._classify_workflow(user_input, context)

            if not classification["success"]:
                return classification

            workflow_action = classification["action"]
            workflow_family = self.FAMILY_MAPPING.get(workflow_action, WorkflowFamily.GESTION)
            urgency = classification.get("urgency", UrgencyLevel.MEDIUM)

            if thought_stream:
                await thought_stream.add_thought(
                    thought_type=ThoughtType.PROCESSING,
                    title=f"Workflow identifié: {workflow_action}",
                    content=f"Famille: {workflow_family.value}, Urgence: {urgency}",
                    agent="WorkflowAgent",
                    progress=0.3
                )

            # Step 2: Extract structured data from user input
            extracted_data = await self._extract_workflow_data(
                user_input=user_input,
                workflow_action=workflow_action,
                context=context
            )

            if thought_stream:
                await thought_stream.add_thought(
                    thought_type=ThoughtType.PROCESSING,
                    title="Préparation du payload standardisé",
                    content=f"Données extraites: {len(extracted_data)} champs",
                    agent="WorkflowAgent",
                    progress=0.5
                )

            # Step 3: Build standardized payload
            payload = self._build_standardized_payload(
                action=workflow_action,
                tenant_id=tenant_id,
                user_id=user_id,
                urgency=urgency,
                context_data=context or {},
                workflow_data=extracted_data,
                trace={
                    "conversation_id": conversation_id or "unknown",
                    "request_id": f"req_{datetime.now().timestamp()}",
                    "thought_stream_id": thought_stream.stream_id if thought_stream else None
                }
            )

            if thought_stream:
                await thought_stream.add_thought(
                    thought_type=ThoughtType.EXECUTING,
                    title=f"Déclenchement N8N: {workflow_action}",
                    content="Envoi de la requête au workflow N8N...",
                    agent="WorkflowAgent",
                    progress=0.7
                )

            # Step 4: Trigger N8N workflow
            result = await self._trigger_workflow(
                workflow_action=workflow_action,
                payload=payload
            )

            if thought_stream:
                if result["success"]:
                    await thought_stream.add_thought(
                        thought_type=ThoughtType.COMPLETED,
                        title=f"✅ Workflow {workflow_action} déclenché",
                        content="N8N va envoyer les mises à jour en temps réel",
                        agent="WorkflowAgent",
                        progress=1.0
                    )
                else:
                    await thought_stream.add_thought(
                        thought_type=ThoughtType.ERROR,
                        title=f"❌ Échec du workflow {workflow_action}",
                        content=result.get("message", "Erreur inconnue"),
                        agent="WorkflowAgent",
                        progress=1.0
                    )

            return result

        except Exception as e:
            logger.error("workflow_agent_process_failed", error=str(e), exc_info=True)
            if thought_stream:
                await thought_stream.add_thought(
                    thought_type=ThoughtType.ERROR,
                    title="Erreur WorkflowAgent",
                    content=str(e),
                    agent="WorkflowAgent",
                    progress=1.0
                )
            return {
                "success": False,
                "message": f"Erreur lors du traitement du workflow: {str(e)}"
            }

    async def _classify_workflow(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Use LLM to classify user request into workflow action

        Returns:
            Dict with success, action, urgency, confidence
        """
        try:
            classification_prompt = f"""Tu es un expert en classification de demandes utilisateur pour des workflows d'automatisation.

WORKFLOWS DISPONIBLES:
- COMMUNICATION: send_email, send_email_building, send_email_professional
- URGENCE: emergency_water_leak, emergency_fire, emergency_lockdown
- GESTION: payment_reminder, document_collection, meeting_preparation
- DIGEST: daily_digest, weekly_report, monthly_summary

REQUÊTE UTILISATEUR:
{user_input}

CONTEXTE:
{context if context else "Aucun contexte"}

Analyse la requête et réponds UNIQUEMENT avec un JSON valide (pas de markdown):
{{
  "action": "nom_du_workflow",
  "urgency": "low|medium|high|critical",
  "confidence": 0.95,
  "reasoning": "Explication courte"
}}

Si aucun workflow ne correspond, retourne:
{{
  "action": null,
  "urgency": "low",
  "confidence": 0.0,
  "reasoning": "Aucun workflow ne correspond à cette demande"
}}
"""

            response = await self.llm_service.generate_response(
                prompt=classification_prompt,
                temperature=0.1,
                max_tokens=300
            )

            # Parse JSON response
            import json
            import re

            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in LLM response")

            classification = json.loads(json_match.group(0))

            if not classification.get("action"):
                return {
                    "success": False,
                    "message": "❌ Aucun workflow ne correspond à votre demande. Veuillez reformuler ou utiliser une autre fonctionnalité."
                }

            # Validate action exists
            if classification["action"] not in self.WORKFLOWS:
                return {
                    "success": False,
                    "message": f"❌ Workflow '{classification['action']}' non configuré."
                }

            return {
                "success": True,
                **classification
            }

        except Exception as e:
            logger.error("workflow_classification_failed", error=str(e))
            return {
                "success": False,
                "message": f"Erreur lors de la classification: {str(e)}"
            }

    async def _extract_workflow_data(
        self,
        user_input: str,
        workflow_action: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Use LLM to extract structured data from user input for the specific workflow

        Returns:
            Dict with workflow-specific data fields
        """
        try:
            # Define expected fields per workflow
            workflow_schemas = {
                "emergency_water_leak": ["building_id", "floor", "apartment_number", "description", "severity"],
                "payment_reminder": ["tenant_name", "amount_due", "due_date", "payment_method"],
                "daily_digest": ["date", "include_financials", "include_incidents", "recipients"],
                "send_email": ["recipient_email", "recipient_name", "subject", "message"],
                # Add more as needed
            }

            expected_fields = workflow_schemas.get(workflow_action, ["description"])

            extraction_prompt = f"""Extrait les informations structurées de cette demande utilisateur.

WORKFLOW: {workflow_action}
CHAMPS ATTENDUS: {', '.join(expected_fields)}

REQUÊTE:
{user_input}

CONTEXTE:
{context if context else "Aucun"}

Réponds UNIQUEMENT avec un JSON valide contenant les champs disponibles:
{{
  "field1": "value1",
  "field2": "value2"
}}

Si un champ n'est pas disponible, ne l'inclus pas. Si rien n'est extrait, retourne {{}}.
"""

            response = await self.llm_service.generate_response(
                prompt=extraction_prompt,
                temperature=0.1,
                max_tokens=500
            )

            # Parse JSON
            import json
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                return {"description": user_input}

        except Exception as e:
            logger.warning("workflow_data_extraction_failed", error=str(e))
            return {"description": user_input}

    def _build_standardized_payload(
        self,
        action: str,
        tenant_id: str,
        user_id: str,
        urgency: str,
        context_data: Dict[str, Any],
        workflow_data: Dict[str, Any],
        trace: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build standardized N8N payload as per SPECIFICATION_N8N_INTEGRATION.md

        Returns:
            Standardized payload dict
        """
        return {
            "action": action,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "urgency": urgency,
            "context": {
                "active_documents": context_data.get("active_document_ids", []),
                "conversation_history": context_data.get("messages", [])[-3:],  # Last 3 messages
                "building_id": context_data.get("building_id"),
                "timestamp": datetime.utcnow().isoformat()
            },
            "data": workflow_data,
            "trace": trace
        }

    async def _trigger_workflow(
        self,
        workflow_action: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Trigger N8N workflow via webhook

        Args:
            workflow_action: Workflow action identifier
            payload: Standardized payload

        Returns:
            Dict with success, message, data
        """
        try:
            # Get webhook path
            webhook_path = self.WORKFLOWS.get(workflow_action)
            if not webhook_path:
                raise ValueError(f"Unknown workflow action: {workflow_action}")

            webhook_url = f"{self.n8n_base_url}/webhook/{webhook_path}"

            logger.info("triggering_n8n_workflow", workflow=workflow_action, url=webhook_url)

            # Trigger webhook
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.auth_token}",
                        "Content-Type": "application/json"
                    }
                )

                response.raise_for_status()

                result_data = response.json() if response.text else {}

                logger.info(
                    "n8n_workflow_triggered_successfully",
                    workflow=workflow_action,
                    status=response.status_code
                )

                return {
                    "success": True,
                    "message": f"✅ Workflow '{workflow_action}' déclenché avec succès. Vous recevrez des mises à jour en temps réel.",
                    "data": {
                        "workflow_action": workflow_action,
                        "status": "triggered",
                        "result": result_data,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }

        except httpx.HTTPStatusError as e:
            logger.error(
                "n8n_workflow_http_error",
                workflow=workflow_action,
                status=e.response.status_code,
                error=str(e)
            )
            return {
                "success": False,
                "message": f"❌ Erreur HTTP {e.response.status_code}: {e.response.text[:100]}"
            }

        except httpx.RequestError as e:
            logger.error("n8n_workflow_request_error", workflow=workflow_action, error=str(e))
            return {
                "success": False,
                "message": f"❌ Impossible de joindre N8N: {str(e)}"
            }

        except Exception as e:
            logger.error("n8n_workflow_trigger_failed", workflow=workflow_action, error=str(e), exc_info=True)
            return {
                "success": False,
                "message": f"❌ Erreur inattendue: {str(e)}"
            }

    def list_workflows(self) -> List[Dict[str, Any]]:
        """List all available workflows with metadata"""
        return [
            {
                "action": action,
                "webhook_path": webhook_path,
                "family": self.FAMILY_MAPPING.get(action, WorkflowFamily.GESTION).value,
                "description": self._get_workflow_description(action)
            }
            for action, webhook_path in self.WORKFLOWS.items()
        ]

    def _get_workflow_description(self, action: str) -> str:
        """Get human-readable description for workflow"""
        descriptions = {
            "emergency_water_leak": "Fuite d'eau urgente - Alerte professionnels et résidents",
            "payment_reminder": "Rappel de paiement cotisation",
            "daily_digest": "Digest quotidien syndic",
            "send_email": "Envoi email individuel",
            # Add more descriptions
        }
        return descriptions.get(action, "Workflow automation")
