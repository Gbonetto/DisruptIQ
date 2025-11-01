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
