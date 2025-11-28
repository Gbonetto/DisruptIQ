"""
Webhook Service
Integration with N8N workflows
"""

import httpx
import hmac
import hashlib
import json
import structlog
from typing import Dict, Any, Optional
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = structlog.get_logger()


class WebhookService:
    """Service for triggering N8N webhooks"""

    def __init__(self):
        self.base_url = settings.N8N_WEBHOOK_BASE_URL
        self.auth_token = settings.N8N_WEBHOOK_AUTH_TOKEN
        self.timeout = settings.N8N_TIMEOUT
        self.max_retries = settings.N8N_MAX_RETRIES

        self.client = httpx.AsyncClient(timeout=self.timeout)

    def _sign_payload(self, payload: Dict[str, Any]) -> str:
        """
        Sign payload with HMAC-SHA256

        Args:
            payload: Dictionary to sign

        Returns:
            Hex signature string
        """
        message = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            self.auth_token.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        return signature

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def _send_webhook(
        self,
        endpoint: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send webhook with retry logic

        Args:
            endpoint: Webhook endpoint path
            payload: Data to send

        Returns:
            Response dictionary
        """
        url = f"{self.base_url}{endpoint}"

        # Add timestamp
        payload['timestamp'] = datetime.utcnow().isoformat()

        headers = {
            "Content-Type": "application/json",
        }

        # Only sign payload if auth token is configured
        if self.auth_token:
            signature = self._sign_payload(payload)
            headers["X-Signature"] = signature
            headers["X-Timestamp"] = payload['timestamp']

        try:
            response = await self.client.post(
                url,
                json=payload,
                headers=headers
            )

            response.raise_for_status()

            logger.info(
                "webhook_sent",
                endpoint=endpoint,
                url=url,
                status=response.status_code
            )

            # Try to parse JSON response, fallback to text if not JSON
            try:
                # Handle empty response body (N8N sometimes returns empty on success)
                if not response.text or response.text.strip() == '':
                    logger.warning(
                        "webhook_empty_response",
                        endpoint=endpoint,
                        status=response.status_code,
                        note="N8N returned empty response, treating as success"
                    )
                    return {
                        "success": True,
                        "status": "success",
                        "message": "Email sent (N8N empty response)",
                        "emails_sent": []  # Mark as email response
                    }
                return response.json()
            except Exception:
                return {
                    "status": "success",
                    "response_text": response.text
                }

        except httpx.HTTPError as e:
            logger.error(
                "webhook_error",
                endpoint=endpoint,
                url=url,
                error=str(e)
            )
            raise

    async def notify_neighbors(
        self,
        address: str,
        apartment: str,
        issue: str,
        neighbors: list
    ) -> Dict[str, Any]:
        """
        Trigger neighbor notification workflow

        Args:
            address: Property address
            apartment: Apartment number
            issue: Type of issue (e.g., "water_damage")
            neighbors: List of neighbor dicts with 'apt' and 'email'

        Returns:
            Workflow execution result
        """
        payload = {
            "workflow": "notify_neighbors",
            "data": {
                "address": address,
                "apartment": apartment,
                "issue": issue,
                "neighbors": neighbors
            }
        }

        return await self._send_webhook("/webhook/notify-neighbors", payload)

    async def send_vendor_emails(
        self,
        email_content: str,
        recipients: list,
        metadata: dict
    ) -> Dict[str, Any]:
        """
        Trigger vendor email workflow

        Args:
            email_content: Email template with {{placeholders}}
            recipients: List of vendor dicts with 'email', 'name', 'company'
            metadata: Additional metadata (subject, property info, etc.)

        Returns:
            Workflow execution result
        """
        payload = {
            "workflow": "send_vendor_emails",
            "data": {
                "email_content": email_content,
                "recipients": recipients,
                "metadata": metadata,
                "sender_email": "syndic@example.com",  # TODO: Get from config
                "reply_to": "contact@syndic.com"
            }
        }

        return await self._send_webhook("/webhook/send-vendor-emails", payload)

    async def archive_document(
        self,
        document_url: str,
        original_filename: str,
        property_id: str,
        extracted_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Trigger document archiving workflow

        Args:
            document_url: URL to download document
            original_filename: Original file name
            property_id: Property identifier
            extracted_text: Extracted text if available

        Returns:
            Workflow execution result
        """
        payload = {
            "workflow": "archive_document",
            "data": {
                "document_url": document_url,
                "original_filename": original_filename,
                "property_id": property_id,
                "extracted_text": extracted_text
            }
        }

        return await self._send_webhook("/webhook/archive-document", payload)

    async def send_email(
        self,
        subject: str,
        body: str,
        recipients: list,
        tenant_id: str = "default",
        user_id: str = "anonymous",
        urgency: str = "medium",
        tone: str = "professional",
        request_id: Optional[str] = None,
        thought_stream_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send email via N8N workflow

        Args:
            subject: Email subject
            body: Email body (text or HTML)
            recipients: List of recipients (can be strings or dicts with 'email', 'name')
            tenant_id: Tenant identifier
            user_id: User identifier
            urgency: Email urgency level ("low", "medium", "high", "critical")
            tone: Email tone ("professional", "urgent", "friendly")
            request_id: Request tracking ID
            thought_stream_id: ThoughtStream ID for real-time updates
            conversation_id: Conversation ID for context

        Returns:
            N8N workflow response with email sending status

        Example:
            >>> webhook_service = WebhookService()
            >>> result = await webhook_service.send_email(
            ...     subject="Test Email",
            ...     body="Hello World",
            ...     recipients=["test@example.com"]
            ... )
            >>> print(result)
            {'success': True, 'message': 'Email sent successfully to 1 recipient(s)', ...}
        """
        # Normalize recipients to list of dicts
        normalized_recipients = []
        for recipient in recipients:
            if isinstance(recipient, dict):
                normalized_recipients.append({
                    "email": recipient.get("email", str(recipient)),
                    "name": recipient.get("name", recipient.get("email", "")),
                    "id": recipient.get("id")
                })
            else:
                # String format (just email)
                normalized_recipients.append({
                    "email": str(recipient),
                    "name": str(recipient)
                })

        payload = {
            "action": "send_email",
            "tenant_id": tenant_id,
            "user_id": user_id,
            "urgency": urgency,
            "data": {
                "subject": subject,
                "body": body,
                "recipients": normalized_recipients,
                "tone": tone,
                "urgency": urgency
            },
            "trace": {
                "request_id": request_id or f"email_{datetime.utcnow().timestamp()}",
                "thought_stream_id": thought_stream_id,
                "conversation_id": conversation_id
            }
        }

        logger.info(
            "sending_email_via_n8n",
            recipients_count=len(normalized_recipients),
            subject=subject,
            urgency=urgency
        )

        try:
            result = await self._send_webhook("/webhook/send-email", payload)

            logger.info(
                "email_sent_via_n8n",
                success=result.get("success", False),
                recipients_count=len(normalized_recipients)
            )

            return result

        except Exception as e:
            logger.error(
                "email_send_failed",
                error=str(e),
                recipients_count=len(normalized_recipients)
            )
            return {
                "success": False,
                "error": str(e),
                "message": f"Échec de l'envoi d'email: {str(e)}"
            }

    async def trigger_custom_workflow(
        self,
        workflow_name: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Trigger a custom N8N workflow

        Args:
            workflow_name: Name of the workflow
            data: Workflow data

        Returns:
            Workflow execution result
        """
        payload = {
            "workflow": workflow_name,
            "data": data
        }

        endpoint = f"/webhook/{workflow_name}"
        return await self._send_webhook(endpoint, payload)

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
