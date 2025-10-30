"""
N8N Webhook Integration Endpoints
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import structlog

from app.services.webhook_service import WebhookService

router = APIRouter()
logger = structlog.get_logger()


class NeighborNotifyRequest(BaseModel):
    """Request to notify neighbors"""
    address: str
    apartment: str
    issue: str
    neighbors: List[Dict[str, str]]  # [{"apt": "22", "email": "..."}]


class VendorEmailRequest(BaseModel):
    """Request to send vendor emails"""
    email_content: str
    recipients: List[Dict[str, str]]
    metadata: Dict[str, Any]


@router.post("/notify-neighbors")
async def notify_neighbors(request: NeighborNotifyRequest):
    """
    Trigger N8N workflow to notify neighbors

    Example:
    {
        "address": "15 rue Victor Hugo",
        "apartment": "23",
        "issue": "water_damage",
        "neighbors": [
            {"apt": "22", "email": "neighbor1@example.com"},
            {"apt": "24", "email": "neighbor2@example.com"}
        ]
    }
    """
    try:
        webhook_service = WebhookService()

        result = await webhook_service.notify_neighbors(
            address=request.address,
            apartment=request.apartment,
            issue=request.issue,
            neighbors=request.neighbors
        )

        logger.info(
            "neighbor_notification_triggered",
            apartment=request.apartment,
            neighbor_count=len(request.neighbors)
        )

        return {
            "status": "success",
            "message": f"Notification sent to {len(request.neighbors)} neighbors",
            "workflow_result": result
        }

    except Exception as e:
        logger.error("neighbor_notification_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger notification: {str(e)}"
        )


@router.post("/send-vendor-emails")
async def send_vendor_emails(request: VendorEmailRequest):
    """
    Trigger N8N workflow to send emails to vendors

    Example:
    {
        "email_content": "Bonjour {{vendor_name}}, nous sollicitons...",
        "recipients": [
            {
                "email": "vendor@example.com",
                "name": "Jean Dupont",
                "company": "Peinture Pro"
            }
        ],
        "metadata": {
            "subject": "Demande de devis",
            "property_address": "15 rue Victor Hugo",
            "property_id": "PROP_001"
        }
    }
    """
    try:
        webhook_service = WebhookService()

        result = await webhook_service.send_vendor_emails(
            email_content=request.email_content,
            recipients=request.recipients,
            metadata=request.metadata
        )

        logger.info(
            "vendor_emails_triggered",
            recipient_count=len(request.recipients)
        )

        return {
            "status": "success",
            "message": f"Emails queued for {len(request.recipients)} vendors",
            "workflow_result": result
        }

    except Exception as e:
        logger.error("vendor_email_workflow_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger email workflow: {str(e)}"
        )


@router.post("/archive-document")
async def archive_document(
    document_url: str,
    filename: str,
    property_id: str
):
    """Trigger N8N workflow to archive a document"""
    try:
        webhook_service = WebhookService()

        result = await webhook_service.archive_document(
            document_url=document_url,
            original_filename=filename,
            property_id=property_id
        )

        logger.info("document_archive_triggered", filename=filename)

        return {
            "status": "success",
            "message": "Document archiving initiated",
            "workflow_result": result
        }

    except Exception as e:
        logger.error("archive_workflow_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger archive workflow: {str(e)}"
        )


@router.get("/status")
async def get_webhook_status():
    """Get N8N webhook status"""
    # TODO: Ping N8N to check connectivity
    return {
        "status": "connected",
        "base_url": "configured"
    }
