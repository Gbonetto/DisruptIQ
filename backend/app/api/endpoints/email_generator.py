"""
Email Generator Endpoints
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import structlog

from app.services.llm_service import LLMService
from app.schemas.email import EmailGenerateRequest, EmailGenerateResponse

router = APIRouter()
logger = structlog.get_logger()


class VendorEmailRequest(BaseModel):
    """Request to send emails to vendors"""
    prompt: str
    vendor_category: str
    property_address: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


@router.post("/generate", response_model=EmailGenerateResponse)
async def generate_email(request: EmailGenerateRequest):
    """
    Generate a professional email based on prompt

    Example:
    {
        "prompt": "Demander un devis pour ravalement de façade",
        "context": {
            "property_address": "15 rue Victor Hugo, 75001 Paris",
            "budget": "50000",
            "timeline": "3 mois"
        }
    }
    """
    try:
        llm_service = LLMService()

        # Generate email
        result = await llm_service.generate_email(
            prompt=request.prompt,
            context=request.context
        )

        logger.info("email_generated", prompt=request.prompt[:50])

        return {
            "subject": result.get("subject", "Email"),
            "body": result.get("body", ""),
            "recipients": [],  # TODO: Add vendor search
            "draft_id": None,
            "n8n_webhook_available": True
        }

    except Exception as e:
        logger.error("email_generation_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate email: {str(e)}"
        )


@router.post("/generate-vendor-emails")
async def generate_vendor_emails(request: VendorEmailRequest):
    """
    Generate and prepare emails for multiple vendors

    This endpoint:
    1. Generates the email content
    2. Searches for relevant vendors
    3. Prepares data for N8N webhook
    """
    try:
        llm_service = LLMService()

        # Generate email content
        email_result = await llm_service.generate_email(
            prompt=request.prompt,
            context=request.context or {}
        )

        # TODO: Search vendors by category from database
        # For now, return mock vendors
        vendors = [
            {
                "name": "Jean Dupont",
                "email": "jean@example.com",
                "company": "Peinture Pro"
            }
        ]

        return {
            "email_content": email_result.get("body", ""),
            "subject": email_result.get("subject", ""),
            "recipients": vendors,
            "n8n_webhook": {
                "available": True,
                "endpoint": "/api/webhooks/send-vendor-emails"
            },
            "metadata": {
                "property_address": request.property_address,
                "vendor_category": request.vendor_category
            }
        }

    except Exception as e:
        logger.error("vendor_email_generation_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate vendor emails: {str(e)}"
        )


@router.get("/suggestions")
async def get_email_suggestions():
    """Get suggested email prompts"""
    return {
        "suggestions": [
            {
                "id": "devis_ravalement",
                "label": "Demander devis ravalement",
                "prompt": "Demander un devis pour ravalement de façade"
            },
            {
                "id": "convocation_ag",
                "label": "Convoquer à l'AG",
                "prompt": "Convoquer les copropriétaires à l'assemblée générale"
            },
            {
                "id": "urgence_plombier",
                "label": "Urgence plomberie",
                "prompt": "Contacter un plombier pour une urgence"
            }
        ]
    }
