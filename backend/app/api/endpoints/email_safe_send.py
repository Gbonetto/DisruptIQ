"""
Email Safe-Send API Endpoints

Endpoints pour envoi sécurisé d'emails:
- Génération brouillon
- Preview avec checklist
- Validation checklist
- Envoi avec confirmation
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr

from app.services.email_safe_send_service import (
    EmailSafeSendService,
    EmailDraft,
    EmailPreview,
    EmailChecklist,
    EmailSendRequest,
    EmailSendResult,
    Recipient,
    Evidence,
    EvidenceType,
    EmailPriority
)
import structlog

logger = structlog.get_logger()

router = APIRouter()

# Service singleton
email_service = EmailSafeSendService()


# =========================================================================
# Request/Response Models
# =========================================================================

class CreateDraftRequest(BaseModel):
    """Requête création brouillon"""
    subject: str
    body: str
    recipients: List[Dict[str, Any]]  # {email, name?, type?}
    evidence: List[Dict[str, Any]]  # {type, title, content, reference?}
    context: Optional[Dict[str, Any]] = None
    conversation_id: Optional[str] = None
    priority: str = "normal"


class ValidateChecklistRequest(BaseModel):
    """Requête validation checklist"""
    draft_id: str
    checklist: Dict[str, Any]


# =========================================================================
# Endpoints
# =========================================================================

@router.post("/drafts", response_model=dict)
async def create_draft(request: CreateDraftRequest):
    """
    Crée un brouillon d'email avec evidence.

    Body:
    - subject: Sujet email
    - body: Corps email (HTML ou texte)
    - recipients: Liste destinataires [{email, name?, type?}]
    - evidence: Sources [{type, title, content}]
    - context: Contexte additionnel (optionnel)
    - priority: Priorité (low|normal|high|urgent)

    Returns:
    - EmailDraft créé avec ID
    """
    try:
        # Convertir recipients
        recipients = [
            Recipient(**r) for r in request.recipients
        ]

        # Convertir evidence
        evidence = [
            Evidence(**e) for e in request.evidence
        ]

        # Convertir priority
        priority = EmailPriority(request.priority)

        draft = await email_service.generate_draft(
            subject=request.subject,
            body=request.body,
            recipients=recipients,
            evidence=evidence,
            context=request.context,
            conversation_id=request.conversation_id,
            priority=priority
        )

        logger.info(
            "email_draft_created_via_api",
            draft_id=draft.id,
            recipients_count=len(recipients)
        )

        return draft.dict()

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "email_draft_creation_error",
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur création brouillon: {str(e)}"
        )


@router.get("/drafts/{draft_id}", response_model=dict)
async def get_draft(draft_id: str):
    """
    Récupère un brouillon par ID.
    """
    draft = await email_service.get_draft(draft_id)

    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Brouillon {draft_id} non trouvé"
        )

    return draft.dict()


@router.post("/drafts/{draft_id}/preview", response_model=dict)
async def preview_draft(
    draft_id: str,
    regenerate_checklist: bool = False
):
    """
    Génère preview d'un brouillon avec checklist.

    Effectue:
    - Vérification evidence (≥2 recommandé)
    - Détection informations sensibles
    - Génération checklist validation
    - Warnings et blocages

    Query params:
    - regenerate_checklist: Régénérer checklist (après modifications)

    Returns:
    - EmailPreview avec preview_text, warnings, checklist
    """
    try:
        preview = await email_service.generate_preview(
            draft_id=draft_id,
            regenerate_checklist=regenerate_checklist
        )

        logger.info(
            "email_preview_generated_via_api",
            draft_id=draft_id,
            can_send=preview.can_send
        )

        return preview.dict()

    except Exception as e:
        logger.error(
            "email_preview_error",
            draft_id=draft_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur génération preview: {str(e)}"
        )


@router.post("/drafts/{draft_id}/validate-checklist", response_model=dict)
async def validate_checklist(draft_id: str, request: ValidateChecklistRequest):
    """
    Valide la checklist d'un brouillon.

    Body:
    - checklist: Checklist avec items cochés

    Returns:
    - {validated: true/false}
    """
    try:
        # Convertir en EmailChecklist
        checklist = EmailChecklist(**request.checklist)

        validated = await email_service.validate_checklist(
            draft_id=draft_id,
            checklist=checklist
        )

        logger.info(
            "email_checklist_validated_via_api",
            draft_id=draft_id,
            validated=validated
        )

        return {"validated": validated}

    except Exception as e:
        logger.error(
            "email_checklist_validation_error",
            draft_id=draft_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur validation checklist: {str(e)}"
        )


@router.post("/drafts/{draft_id}/send", response_model=dict)
async def send_email(draft_id: str, request: EmailSendRequest):
    """
    Envoie un email après validation.

    Body:
    - checklist_confirmed: true/false (obligatoire)
    - force_send: true/false (admin only, override warnings)
    - correlation_id: ID corrélation (optionnel)

    Vérifications:
    - Preview affiché
    - Checklist validée si evidence < 2
    - Checklist confirmée dans requête
    - Pas de modifications après preview

    Returns:
    - EmailSendResult avec sent_count, errors
    """
    try:
        # Forcer draft_id
        request.draft_id = draft_id

        result = await email_service.send_email(
            request=request,
            email_sender_service=None  # TODO: Injecter vrai service SMTP
        )

        logger.info(
            "email_sent_via_api",
            draft_id=draft_id,
            success=result.success,
            sent_count=result.sent_count
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Envoi bloqué",
                    "errors": result.errors
                }
            )

        return result.dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "email_send_error",
            draft_id=draft_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur envoi email: {str(e)}"
        )


@router.get("/evidence-types", response_model=dict)
async def list_evidence_types():
    """
    Liste les types d'evidence disponibles.
    """
    return {
        "evidence_types": [e.value for e in EvidenceType]
    }


@router.get("/priorities", response_model=dict)
async def list_priorities():
    """
    Liste les priorités email disponibles.
    """
    return {
        "priorities": [p.value for p in EmailPriority]
    }
