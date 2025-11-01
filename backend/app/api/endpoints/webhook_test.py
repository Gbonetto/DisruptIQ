"""
Webhook Test Endpoints
For testing N8N integration
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import structlog

from app.services.webhook_service import WebhookService

router = APIRouter()
logger = structlog.get_logger()


class WebhookTestRequest(BaseModel):
    """Request for testing webhook"""
    workflow_name: str
    test_data: Dict[str, Any]


class SimpleWebhookTestRequest(BaseModel):
    """Simple test request"""
    message: str
    test_type: Optional[str] = "basic"


@router.post("/test")
async def test_webhook(request: WebhookTestRequest):
    """
    Test N8N webhook connection

    Example:
    {
        "workflow_name": "test_workflow",
        "test_data": {
            "message": "Hello from DisruptIQ!",
            "timestamp": "2025-11-01T12:00:00"
        }
    }
    """
    try:
        webhook_service = WebhookService()

        result = await webhook_service.trigger_custom_workflow(
            workflow_name=request.workflow_name,
            data=request.test_data
        )

        await webhook_service.close()

        logger.info(
            "webhook_test_success",
            workflow=request.workflow_name,
            result=result
        )

        return {
            "status": "success",
            "message": "Webhook sent successfully",
            "result": result
        }

    except Exception as e:
        logger.error(
            "webhook_test_failed",
            workflow=request.workflow_name,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Webhook test failed: {str(e)}"
        )


@router.post("/test/simple")
async def test_webhook_simple(request: SimpleWebhookTestRequest):
    """
    Simple webhook test endpoint

    Sends a basic payload to N8N webhook to verify connectivity
    """
    try:
        webhook_service = WebhookService()

        test_payload = {
            "message": request.message,
            "test_type": request.test_type,
            "source": "DisruptIQ Backend",
            "version": "1.0"
        }

        # Using trigger_custom_workflow with the webhook path
        result = await webhook_service.trigger_custom_workflow(
            workflow_name="test",
            data=test_payload
        )

        await webhook_service.close()

        return {
            "status": "success",
            "message": "Simple webhook test completed",
            "sent_payload": test_payload,
            "n8n_response": result
        }

    except Exception as e:
        logger.error("simple_webhook_test_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Simple webhook test failed: {str(e)}"
        )


@router.post("/test/notify-neighbors")
async def test_notify_neighbors():
    """Test the notify_neighbors workflow"""
    try:
        webhook_service = WebhookService()

        result = await webhook_service.notify_neighbors(
            address="123 Rue de la Paix, 75001 Paris",
            apartment="Apt 3B",
            issue="water_damage",
            neighbors=[
                {"apt": "3A", "email": "neighbor1@example.com"},
                {"apt": "3C", "email": "neighbor2@example.com"}
            ]
        )

        await webhook_service.close()

        return {
            "status": "success",
            "workflow": "notify_neighbors",
            "result": result
        }

    except Exception as e:
        logger.error("notify_neighbors_test_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Notify neighbors test failed: {str(e)}"
        )


@router.post("/test/send-vendor-emails")
async def test_send_vendor_emails():
    """Test the send_vendor_emails workflow"""
    try:
        webhook_service = WebhookService()

        result = await webhook_service.send_vendor_emails(
            email_content="Bonjour {{name}},\n\nNous recherchons un devis pour {{service}}.\n\nCordialement",
            recipients=[
                {
                    "email": "vendor1@example.com",
                    "name": "Jean Dupont",
                    "company": "Plomberie Dupont"
                }
            ],
            metadata={
                "subject": "Demande de devis",
                "property_address": "123 Rue de la Paix",
                "service": "réparation plomberie"
            }
        )

        await webhook_service.close()

        return {
            "status": "success",
            "workflow": "send_vendor_emails",
            "result": result
        }

    except Exception as e:
        logger.error("send_vendor_emails_test_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Send vendor emails test failed: {str(e)}"
        )
