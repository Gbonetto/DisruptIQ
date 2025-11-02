"""
Workflow Agent - Triggers N8N workflows with contextual data
"""

import structlog
from typing import Dict, Any, List
import httpx
from app.core.config import settings

logger = structlog.get_logger()


class WorkflowAgent:
    """
    Workflow Agent - Manages N8N workflow triggers

    Capabilities:
    - Trigger N8N workflows via webhooks
    - Pass contextual data to workflows
    - Handle async workflow responses
    - Retry logic for failed triggers
    """

    # N8N Workflow IDs/Names (configured in .env)
    WORKFLOWS = {
        "email_draft": "create-gmail-draft",
        "bulk_devis": "bulk-devis-request",
        "emergency_alert": "emergency-sms-email",
        "document_process": "ocr-classify-store"
    }

    def __init__(self):
        self.n8n_base_url = settings.N8N_WEBHOOK_BASE_URL
        self.auth_token = settings.N8N_WEBHOOK_AUTH_TOKEN
        self.timeout = settings.N8N_TIMEOUT
        logger.info("workflow_agent_initialized", base_url=self.n8n_base_url)

    async def trigger_email_draft(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trigger N8N workflow to create Gmail draft

        Args:
            email_data: Dict with subject, body, recipients

        Returns:
            Dict with success, message, workflow_result
        """
        return await self._trigger_workflow(
            workflow_name="email_draft",
            payload={
                "action": "create_draft",
                "email": {
                    "subject": email_data.get("subject"),
                    "body": email_data.get("body"),
                    "recipients": email_data.get("recipients", [])
                }
            }
        )

    async def trigger_bulk_quotes(
        self,
        vendors: List[Dict[str, Any]],
        message: str
    ) -> Dict[str, Any]:
        """
        Trigger N8N workflow for bulk devis requests

        Args:
            vendors: List of vendor dicts with name, email
            message: Quote request message

        Returns:
            Dict with success, message, workflow_result
        """
        return await self._trigger_workflow(
            workflow_name="bulk_devis",
            payload={
                "action": "request_quotes",
                "vendors": vendors,
                "message": message,
                "attachments": []  # Can be filled later
            }
        )

    async def trigger_generic(self, workflow_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trigger any N8N workflow generically

        Args:
            workflow_id: Workflow identifier
            payload: Data to send to workflow

        Returns:
            Dict with success, message
        """
        return await self._trigger_workflow(workflow_name=workflow_id, payload=payload)

    async def _trigger_workflow(
        self,
        workflow_name: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Internal method to trigger N8N workflow

        Args:
            workflow_name: Name/ID of workflow
            payload: Data payload

        Returns:
            Dict with success, message, data
        """
        try:
            # Build webhook URL
            workflow_id = self.WORKFLOWS.get(workflow_name, workflow_name)
            webhook_url = f"{self.n8n_base_url}/webhook/{workflow_id}"

            logger.info("triggering_n8n_workflow", workflow=workflow_name, url=webhook_url)

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
                    workflow=workflow_name,
                    status=response.status_code
                )

                return {
                    "success": True,
                    "message": f"✅ Workflow '{workflow_name}' déclenché avec succès. Les brouillons seront disponibles dans Gmail.",
                    "data": {
                        "workflow_id": workflow_id,
                        "status": "triggered",
                        "result": result_data
                    }
                }

        except httpx.HTTPStatusError as e:
            logger.error(
                "n8n_workflow_http_error",
                workflow=workflow_name,
                status=e.response.status_code,
                error=str(e)
            )
            return {
                "success": False,
                "message": f"❌ Erreur lors du déclenchement du workflow: HTTP {e.response.status_code}"
            }

        except httpx.RequestError as e:
            logger.error("n8n_workflow_request_error", workflow=workflow_name, error=str(e))
            return {
                "success": False,
                "message": f"❌ Impossible de joindre N8N: {str(e)}"
            }

        except Exception as e:
            logger.error("n8n_workflow_trigger_failed", workflow=workflow_name, error=str(e), exc_info=True)
            return {
                "success": False,
                "message": f"❌ Erreur inattendue: {str(e)}"
            }

    def list_workflows(self) -> List[Dict[str, str]]:
        """List all available workflows"""
        return [
            {"id": workflow_id, "name": workflow_name}
            for workflow_id, workflow_name in self.WORKFLOWS.items()
        ]
