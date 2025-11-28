"""
Email Management Endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.email import Email, EmailUrgency

router = APIRouter()
logger = structlog.get_logger()


@router.get("/")
async def list_emails(
    limit: int = Query(20, ge=1, le=100, description="Number of emails to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    urgency: Optional[str] = Query(None, description="Filter by urgency: urgent, important, routine"),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search in subject and sender"),
    processed: Optional[bool] = Query(None, description="Filter by processed status"),
    included_in_digest: Optional[bool] = Query(None, description="Filter by digest inclusion"),
    from_date: Optional[str] = Query(None, description="Filter emails from this date (ISO format)"),
    to_date: Optional[str] = Query(None, description="Filter emails to this date (ISO format)"),
    db: AsyncSession = Depends(get_db)
):
    """
    List emails with filtering and pagination

    Supports filters:
    - urgency: urgent, important, routine
    - category: email category
    - search: search in subject and sender
    - processed: true/false
    - included_in_digest: true/false
    - from_date/to_date: date range filter
    """
    try:
        # Build WHERE conditions
        conditions = []

        if urgency:
            try:
                urgency_enum = EmailUrgency(urgency)
                conditions.append(Email.urgency == urgency_enum)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid urgency value. Must be one of: urgent, important, routine"
                )

        if category:
            conditions.append(Email.category == category)

        if search:
            # Search in subject and sender
            search_pattern = f"%{search}%"
            conditions.append(
                (Email.subject.ilike(search_pattern)) | (Email.sender.ilike(search_pattern))
            )

        if processed is not None:
            conditions.append(Email.processed == processed)

        if included_in_digest is not None:
            conditions.append(Email.included_in_digest == included_in_digest)

        if from_date:
            try:
                from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
                conditions.append(Email.received_at >= from_dt)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid from_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
                )

        if to_date:
            try:
                to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
                conditions.append(Email.received_at <= to_dt)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid to_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
                )

        # Build query
        where_clause = and_(*conditions) if conditions else True

        # Get total count
        total = await db.scalar(
            select(func.count()).select_from(Email).where(where_clause)
        )

        # Get emails
        result = await db.execute(
            select(Email)
            .where(where_clause)
            .order_by(Email.received_at.desc())
            .limit(limit)
            .offset(offset)
        )
        emails = result.scalars().all()

        # Format response
        email_list = []
        for email in emails:
            email_dict = {
                "id": email.id,
                "message_id": email.message_id,
                "thread_id": email.thread_id,
                "sender": email.sender,
                "recipient": email.recipient,
                "subject": email.subject,
                "snippet": email.body[:200] if email.body else None,  # First 200 chars
                "urgency": email.urgency.value if email.urgency else "routine",
                "category": email.category,
                "attachments": email.attachments or [],
                "processed": email.processed,
                "included_in_digest": email.included_in_digest,
                "received_at": email.received_at.isoformat() if email.received_at else None,
                "processed_at": email.processed_at.isoformat() if email.processed_at else None,
                "created_at": email.created_at.isoformat() if email.created_at else None
            }
            email_list.append(email_dict)

        logger.info(
            "emails_listed",
            total=total,
            returned=len(email_list),
            filters={
                "urgency": urgency,
                "category": category,
                "search": search,
                "processed": processed,
                "included_in_digest": included_in_digest
            }
        )

        return {
            "emails": email_list,
            "total": total or 0,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(email_list)) < (total or 0)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_emails_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list emails: {str(e)}"
        )


@router.get("/{email_id}")
async def get_email(
    email_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get full email details by ID"""
    try:
        result = await db.execute(
            select(Email).where(Email.id == email_id)
        )
        email = result.scalar_one_or_none()

        if not email:
            raise HTTPException(
                status_code=404,
                detail=f"Email {email_id} not found"
            )

        return {
            "id": email.id,
            "message_id": email.message_id,
            "thread_id": email.thread_id,
            "sender": email.sender,
            "recipient": email.recipient,
            "subject": email.subject,
            "body": email.body,  # Full body
            "urgency": email.urgency.value if email.urgency else "routine",
            "category": email.category,
            "attachments": email.attachments or [],
            "llm_analysis": email.llm_analysis,
            "professionnel_id": email.professionnel_id,
            "copropriete_id": email.copropriete_id,
            "coproprietaire_id": email.coproprietaire_id,
            "processed": email.processed,
            "included_in_digest": email.included_in_digest,
            "received_at": email.received_at.isoformat() if email.received_at else None,
            "processed_at": email.processed_at.isoformat() if email.processed_at else None,
            "created_at": email.created_at.isoformat() if email.created_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_email_failed", email_id=email_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get email: {str(e)}"
        )


@router.get("/stats/summary")
async def get_email_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get email statistics summary"""
    try:
        # Get total count
        total = await db.scalar(select(func.count()).select_from(Email))

        # Count by urgency
        urgent_count = await db.scalar(
            select(func.count()).select_from(Email).where(Email.urgency == EmailUrgency.URGENT)
        )
        important_count = await db.scalar(
            select(func.count()).select_from(Email).where(Email.urgency == EmailUrgency.IMPORTANT)
        )
        routine_count = await db.scalar(
            select(func.count()).select_from(Email).where(Email.urgency == EmailUrgency.ROUTINE)
        )

        # Count by status
        processed_count = await db.scalar(
            select(func.count()).select_from(Email).where(Email.processed == True)
        )
        unprocessed_count = await db.scalar(
            select(func.count()).select_from(Email).where(Email.processed == False)
        )

        # Count in digest
        in_digest_count = await db.scalar(
            select(func.count()).select_from(Email).where(Email.included_in_digest == True)
        )

        # Today's emails
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = await db.scalar(
            select(func.count()).select_from(Email).where(Email.received_at >= today_start)
        )

        # This week's emails
        week_start = datetime.now() - timedelta(days=7)
        week_count = await db.scalar(
            select(func.count()).select_from(Email).where(Email.received_at >= week_start)
        )

        return {
            "total": total or 0,
            "by_urgency": {
                "urgent": urgent_count or 0,
                "important": important_count or 0,
                "routine": routine_count or 0
            },
            "by_status": {
                "processed": processed_count or 0,
                "unprocessed": unprocessed_count or 0,
                "in_digest": in_digest_count or 0
            },
            "by_timeframe": {
                "today": today_count or 0,
                "this_week": week_count or 0
            }
        }

    except Exception as e:
        logger.error("get_email_stats_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get email stats: {str(e)}"
        )


@router.patch("/{email_id}/mark-processed")
async def mark_email_processed(
    email_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Mark an email as processed"""
    try:
        result = await db.execute(
            select(Email).where(Email.id == email_id)
        )
        email = result.scalar_one_or_none()

        if not email:
            raise HTTPException(
                status_code=404,
                detail=f"Email {email_id} not found"
            )

        email.processed = True
        email.processed_at = datetime.now()

        await db.commit()
        await db.refresh(email)

        logger.info("email_marked_processed", email_id=email_id)

        return {
            "message": "Email marked as processed",
            "email_id": email_id,
            "processed_at": email.processed_at.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("mark_email_processed_failed", email_id=email_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to mark email as processed: {str(e)}"
        )


@router.delete("/{email_id}")
async def delete_email(
    email_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete an email"""
    try:
        result = await db.execute(
            select(Email).where(Email.id == email_id)
        )
        email = result.scalar_one_or_none()

        if not email:
            raise HTTPException(
                status_code=404,
                detail=f"Email {email_id} not found"
            )

        await db.delete(email)
        await db.commit()

        logger.info("email_deleted", email_id=email_id)

        return {
            "message": "Email deleted successfully",
            "email_id": email_id
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("delete_email_failed", email_id=email_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete email: {str(e)}"
        )


# ============================================================================
# ROUTES PREMIUM - Classification Avancée
# ============================================================================

class ClassifyEmailRequest(BaseModel):
    """Requête classification email individuel"""
    sujet: str
    corps: str
    expediteur: str
    id_message: Optional[str] = ""


class ClassifyBatchRequest(BaseModel):
    """Requête classification batch emails"""
    emails: List[Dict[str, str]]  # Liste de {sujet, corps, expediteur, id_message}
    taille_batch: Optional[int] = 20


@router.post("/classify-advanced")
async def classify_email_advanced(request: ClassifyEmailRequest):
    """
    Classification avancée d'un email individuel

    Utilise ClassificateurEmailAvance pour:
    - 6 niveaux d'urgence (critique → spam)
    - 20+ catégories métier
    - Extraction entités (téléphone, montant, appartement, etc.)
    - Suggestion action automatique
    - Confiance de classification

    Returns:
        EmailClassifie avec toutes métadonnées enrichies
    """
    try:
        from app.services.classificateur_email_avance import ClassificateurEmailAvance

        logger.info("classification_avancee_demarree",
                   sujet=request.sujet[:50],
                   expediteur=request.expediteur)

        classificateur = ClassificateurEmailAvance()
        email_classifie = await classificateur.classifier(
            sujet=request.sujet,
            corps=request.corps,
            expediteur=request.expediteur,
            id_message=request.id_message
        )

        # Sérialiser pour JSON
        result = {
            "id_message": email_classifie.id_message,
            "sujet": email_classifie.sujet,
            "expediteur": email_classifie.expediteur,
            "urgence": email_classifie.urgence.value,
            "categorie": email_classifie.categorie.value,
            "confiance": email_classifie.confiance,
            "entites_detectees": email_classifie.entites_detectees,
            "intention": email_classifie.intention,
            "action_requise": email_classifie.action_requise,
            "action_suggeree": email_classifie.action_suggeree,
            "resume": email_classifie.resume,
            "mots_cles": email_classifie.mots_cles,
            "sentiment": email_classifie.sentiment,
            "classifie_le": email_classifie.classifie_le.isoformat()
        }

        logger.info("classification_avancee_terminee",
                   urgence=result["urgence"],
                   categorie=result["categorie"],
                   confiance=result["confiance"])

        return result

    except Exception as e:
        logger.error("classification_avancee_echouee",
                    erreur=str(e),
                    exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Échec classification avancée: {str(e)}"
        )


@router.post("/batch-classify")
async def classify_emails_batch(request: ClassifyBatchRequest):
    """
    Classification batch de plusieurs emails (optimisé)

    Batch processing économise ~94% de coûts LLM:
    - 50 emails individuels = 50 appels LLM = 0.15€
    - 50 emails batch (20/appel) = 3 appels LLM = 0.009€

    Args:
        emails: Liste emails avec {sujet, corps, expediteur, id_message}
        taille_batch: Nb emails par appel LLM (défaut 20, max recommandé 20)

    Returns:
        Liste emails classifiés avec métadonnées complètes
    """
    try:
        from app.services.classificateur_email_avance import ClassificateurEmailAvance

        logger.info("classification_batch_demarree",
                   total_emails=len(request.emails),
                   taille_batch=request.taille_batch)

        classificateur = ClassificateurEmailAvance()
        emails_classifies = await classificateur.classifier_batch(
            request.emails,
            taille_batch=request.taille_batch
        )

        # Sérialiser pour JSON
        results = [
            {
                "id_message": e.id_message,
                "sujet": e.sujet,
                "expediteur": e.expediteur,
                "urgence": e.urgence.value,
                "categorie": e.categorie.value,
                "confiance": e.confiance,
                "entites_detectees": e.entites_detectees,
                "intention": e.intention,
                "action_requise": e.action_requise,
                "action_suggeree": e.action_suggeree,
                "resume": e.resume,
                "mots_cles": e.mots_cles,
                "sentiment": e.sentiment,
                "classifie_le": e.classifie_le.isoformat()
            }
            for e in emails_classifies
        ]

        # Stats par urgence
        from collections import Counter
        urgences_count = Counter([e["urgence"] for e in results])

        logger.info("classification_batch_terminee",
                   total_classifies=len(results),
                   critiques=urgences_count.get("critique", 0),
                   urgents=urgences_count.get("urgent", 0),
                   importants=urgences_count.get("important", 0))

        return {
            "emails_classifies": results,
            "total": len(results),
            "statistiques": {
                "par_urgence": dict(urgences_count),
                "taille_batch": request.taille_batch,
                "nb_appels_llm_estimes": (len(request.emails) // request.taille_batch) + 1
            }
        }

    except Exception as e:
        logger.error("classification_batch_echouee",
                    erreur=str(e),
                    exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Échec classification batch: {str(e)}"
        )
