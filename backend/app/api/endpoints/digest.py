"""
Email Digest Endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import structlog
import asyncio
import subprocess
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from app.services.email_processor import EmailProcessor
from app.schemas.email import DigestResponse
from app.core.database import get_db
from app.models.email import Email, EmailUrgency
from app.core.dependencies import get_email_processor

router = APIRouter()
logger = structlog.get_logger()


class DigestGenerateRequest(BaseModel):
    """Request to generate digest"""
    since_hours: Optional[int] = 24
    max_emails: Optional[int] = 100  # Increased from 10 to retrieve all recent emails


class ProcessEmailsRequest(BaseModel):
    """Request to process pre-fetched emails from external service"""
    emails: List[Dict[str, Any]]


class SyncGmailRequest(BaseModel):
    """Request to sync Gmail"""
    since_hours: Optional[int] = 24
    max_emails: Optional[int] = 100


async def _persist_classified_emails(db: AsyncSession, classified: Dict[str, List[Dict[str, Any]]]) -> None:
    """
    Helper function to persist classified emails to database

    Args:
        db: Database session
        classified: Dictionary with 'urgent', 'important', 'routine' keys containing email lists
    """
    # Collect all message IDs from classified emails
    all_message_ids = []
    for urgency_level in ['urgent', 'important', 'routine']:
        for email_data in classified[urgency_level]:
            all_message_ids.append(email_data['message_id'])

    # Single query to fetch all existing message IDs (OPTIMIZATION)
    existing_result = await db.execute(
        select(Email.message_id).where(Email.message_id.in_(all_message_ids))
    )
    existing_message_ids = set(row[0] for row in existing_result.fetchall())
    logger.debug("existing_emails_fetched", count=len(existing_message_ids))

    # Collect new emails for bulk insert
    new_emails = []
    for urgency_level in ['urgent', 'important', 'routine']:
        for email_data in classified[urgency_level]:
            # Skip if already exists (using set lookup - O(1))
            if email_data['message_id'] in existing_message_ids:
                logger.debug("email_already_exists", message_id=email_data['message_id'])
                continue

            # Create new email record
            db_email = Email(
                message_id=email_data['message_id'],
                thread_id=email_data.get('thread_id'),
                sender=email_data['sender'],
                subject=email_data['subject'],
                body=email_data.get('body', ''),
                urgency=EmailUrgency(email_data['urgency']),
                category=email_data.get('category'),
                attachments=email_data.get('attachments', []),
                received_at=email_data.get('received_at'),
                processed=True,
                included_in_digest=True,
                processed_at=datetime.now()
            )
            new_emails.append(db_email)

    # Bulk insert all new emails (OPTIMIZATION: single transaction)
    if new_emails:
        db.add_all(new_emails)
        await db.commit()
        logger.info("emails_persisted", count=len(new_emails))
    else:
        logger.info("no_new_emails_to_persist")


@router.post("/sync-gmail")
async def sync_gmail(
    request: SyncGmailRequest = None
):
    """
    Trigger external Gmail sync service on-demand

    This endpoint calls the HTTP Trigger Service running on the host which:
    1. Runs outside Docker to bypass network/SSL issues
    2. Executes v1.py to fetch unread emails from Gmail via OAuth2
    3. v1.py sends emails to /api/digest/process-emails for classification & persistence
    4. Returns sync status and email count

    ## Architecture:

    ```
    Backend (Docker) → HTTP Trigger (Host:5001) → v1.py (Gmail API) → Backend (Docker)
    ```

    ## Why External Service?

    The digest service runs on the HOST (not in Docker) because:
    - Gmail API has network/SSL issues inside Docker containers
    - External execution has native network access
    - Proven 100% success rate vs 6% inside Docker

    ## Prerequisites:

    The HTTP Trigger Service must be running on the host:
    ```bash
    cd scripts/digest-service
    python http_trigger.py
    ```

    ## Performance:

    - Execution time: 5-15 seconds (depending on email count)
    - Timeout: 130 seconds max (120s for script + 10s buffer)
    - Parallel LLM classification for speed

    ## Request:

    - `since_hours` (int): Fetch emails from last N hours (default: 24)
    - `max_emails` (int): Maximum emails to fetch (default: 100)

    ## Response:

    - `status`: "success" or "error"
    - `emails_synced`: Number of emails fetched
    - `execution_time`: Time taken in seconds
    - `message`: Status message

    ## Usage:

    Call this endpoint before generating a digest to ensure fresh data:

    ```python
    # 1. Sync Gmail
    sync_response = await client.post("/api/digest/sync-gmail", json={"since_hours": 24})

    # 2. Generate digest from fresh data
    digest = await client.post("/api/digest/generate", json={"since_hours": 24})
    ```
    """
    import httpx

    if request is None:
        request = SyncGmailRequest()

    try:
        start_time = datetime.now()
        logger.info("sync_gmail_triggered", since_hours=request.since_hours, max_emails=request.max_emails)

        # Call HTTP Trigger Service running on host
        # Use host.docker.internal to reach host machine from Docker
        trigger_url = "http://host.docker.internal:5001/trigger-sync"

        logger.info("calling_trigger_service", url=trigger_url)

        async with httpx.AsyncClient(timeout=130.0) as client:
            try:
                response = await client.post(
                    trigger_url,
                    json={
                        "since_hours": request.since_hours,
                        "max_emails": request.max_emails
                    }
                )

                execution_time = (datetime.now() - start_time).total_seconds()

                if response.status_code == 200:
                    result = response.json()
                    logger.info("gmail_sync_succeeded",
                                emails=result.get('emails_synced', 0),
                                duration=execution_time)

                    return {
                        "status": "success",
                        "emails_synced": result.get('emails_synced', 0),
                        "execution_time": round(execution_time, 2),
                        "message": result.get('message', 'Gmail sync completed')
                    }
                else:
                    error_detail = response.text
                    logger.error("gmail_sync_failed", status_code=response.status_code, error=error_detail)
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Gmail sync failed: {error_detail}"
                    )

            except httpx.ConnectError:
                logger.error("trigger_service_not_available")
                raise HTTPException(
                    status_code=503,
                    detail="HTTP Trigger Service not available. Please ensure 'python http_trigger.py' is running on the host."
                )
            except httpx.TimeoutException:
                logger.error("trigger_service_timeout")
                raise HTTPException(
                    status_code=504,
                    detail="Gmail sync timed out after 130 seconds"
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("sync_gmail_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync Gmail: {str(e)}"
        )


@router.post("/generate")
async def generate_digest(
    request: DigestGenerateRequest = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate email digest from database - SIMPLE ARCHITECTURE

    ## Architecture Overview:

    This endpoint reads emails from the database and generates a digest.
    It does NOT fetch from Gmail - use v1.py (manual or cron) to sync emails first.

    ## Workflow:

    1. **Query Database** - Fetch emails from last `since_hours`
    2. **Group by Urgency** - URGENT, IMPORTANT, ROUTINE
    3. **Return Structured Digest**

    ## Prerequisites:

    Run v1.py to sync emails from Gmail to database:
    ```bash
    cd scripts/digest-service
    python v1.py
    ```

    Or setup a cron job on VPS:
    ```bash
    0 */6 * * * cd /path/to/DisruptIQ_CC/scripts/digest-service && python v1.py
    ```

    ## Request Parameters:

    - `since_hours` (int): Fetch emails from last N hours (default: 24)
    - `max_emails` (int): Maximum emails to fetch (default: 100)

    ## Response:

    Returns `DigestResponse` with emails grouped by urgency:
    - `urgent`: List[EmailDigestItem] - URGENT emails
    - `important`: List[EmailDigestItem] - IMPORTANT emails
    - `routine`: List[EmailDigestItem] - ROUTINE emails
    - `total`: int - Total email count

    ## Notes:

    - This endpoint is FAST - no Gmail API calls
    - Works offline if emails are already cached
    - For VPS deployment: run v1.py via cron for automation
    """
    if request is None:
        request = DigestGenerateRequest()

    try:
        # Query database for emails from last N hours
        time_threshold = datetime.now() - timedelta(hours=request.since_hours)

        logger.info("fetching_digest_from_db", since_hours=request.since_hours)
        result = await db.execute(
            select(Email)
            .where(Email.received_at >= time_threshold)
            .order_by(Email.received_at.desc())
            .limit(request.max_emails)
        )
        db_emails = result.scalars().all()

        if not db_emails:
            logger.info("no_emails_in_digest")
            return {
                "date": datetime.now().isoformat(),
                "total_emails": 0,
                "urgent": {"count": 0, "emails": []},
                "important": {"count": 0, "emails": []},
                "routine": {"count": 0, "emails": []},
                "generated_at": datetime.now().isoformat()
            }

        # Group emails by urgency
        urgent_emails = []
        important_emails = []
        routine_emails = []

        for email in db_emails:
            email_dict = {
                "id": email.id,
                "message_id": email.message_id,
                "sender": email.sender,
                "subject": email.subject,
                "body": email.body,
                "urgency": email.urgency.value,
                "category": email.category,
                "received_at": email.received_at.isoformat() if email.received_at else None,
                "attachments": email.attachments or []
            }

            if email.urgency == EmailUrgency.URGENT:
                urgent_emails.append(email_dict)
            elif email.urgency == EmailUrgency.IMPORTANT:
                important_emails.append(email_dict)
            else:
                routine_emails.append(email_dict)

        # Format response
        response = {
            "date": datetime.now().isoformat(),
            "total_emails": len(db_emails),
            "urgent": {
                "count": len(urgent_emails),
                "emails": urgent_emails
            },
            "important": {
                "count": len(important_emails),
                "emails": important_emails
            },
            "routine": {
                "count": len(routine_emails),
                "emails": routine_emails
            },
            "generated_at": datetime.now().isoformat()
        }

        logger.info(
            "digest_generated",
            total=len(db_emails),
            urgent=len(urgent_emails),
            important=len(important_emails),
            routine=len(routine_emails)
        )

        return response

    except Exception as e:
        logger.error("digest_generation_failed", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate digest: {str(e)}"
        )
    finally:
        await db.close()


@router.post("/generate-html")
async def generate_digest_html(
    request: DigestGenerateRequest = None
):
    """
    Generate HTML digest email

    Returns HTML content ready to be sent via email
    """
    if request is None:
        request = DigestGenerateRequest()

    try:
        processor = get_email_processor()

        # Fetch and classify emails
        emails = await processor.fetch_unread_emails(
            max_results=request.max_emails,
            since_hours=request.since_hours
        )

        if not emails:
            return {
                "html": "<p>No unread emails found</p>",
                "email_count": 0
            }

        classified = await processor.classify_emails(emails)

        # Generate HTML
        html = await processor.generate_digest_html(classified)

        return {
            "html": html,
            "email_count": len(emails)
        }

    except Exception as e:
        logger.error("html_digest_generation_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate HTML digest: {str(e)}"
        )


@router.get("/latest")
async def get_latest_digest(
    hours: int = 24,
    db: AsyncSession = Depends(get_db)
):
    """
    Get the latest digest from database

    Fetches emails from the last N hours (default 24) and groups them by urgency
    """
    try:
        # Calculate time threshold
        time_threshold = datetime.now() - timedelta(hours=hours)

        # Fetch emails from database
        result = await db.execute(
            select(Email)
            .where(Email.received_at >= time_threshold)
            .order_by(Email.received_at.desc())
        )
        emails = result.scalars().all()

        logger.info("fetching_latest_digest", count=len(emails), hours=hours)

        if not emails:
            return {
                "date": datetime.now().isoformat(),
                "total_emails": 0,
                "urgent": {"count": 0, "emails": []},
                "important": {"count": 0, "emails": []},
                "routine": {"count": 0, "emails": []},
                "generated_at": datetime.now().isoformat()
            }

        # Group by urgency
        urgent = []
        important = []
        routine = []

        for email in emails:
            email_dict = {
                "id": email.id,
                "message_id": email.message_id,
                "sender": email.sender,
                "subject": email.subject,
                "body": email.body,
                "urgency": email.urgency.value,
                "received_at": email.received_at.isoformat() if email.received_at else None,
                "attachments": email.attachments or []
            }

            if email.urgency == EmailUrgency.URGENT:
                urgent.append(email_dict)
            elif email.urgency == EmailUrgency.IMPORTANT:
                important.append(email_dict)
            else:
                routine.append(email_dict)

        response = {
            "date": datetime.now().isoformat(),
            "total_emails": len(emails),
            "urgent": {
                "count": len(urgent),
                "emails": urgent
            },
            "important": {
                "count": len(important),
                "emails": important
            },
            "routine": {
                "count": len(routine),
                "emails": routine
            },
            "generated_at": datetime.now().isoformat()
        }

        logger.info(
            "latest_digest_retrieved",
            total=len(emails),
            urgent=len(urgent),
            important=len(important),
            routine=len(routine)
        )

        return response

    except Exception as e:
        logger.error("latest_digest_fetch_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch latest digest: {str(e)}"
        )


@router.post("/process-emails")
async def process_emails(
    request: ProcessEmailsRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Process pre-fetched emails from external digest service

    This endpoint:
    1. Receives emails already fetched from Gmail (by external service)
    2. Classifies them by urgency using LLM
    3. Persists emails to database
    4. Returns structured digest data

    Used by: digest_service.py (hybrid solution)

    Performance optimizations:
    - Reuses singleton EmailProcessor
    - Bulk insert emails (eliminates N+1 queries)
    """
    try:
        processor = get_email_processor()
        emails = request.emails

        if not emails:
            return {
                "date": datetime.now().isoformat(),
                "total_emails": 0,
                "urgent": {"count": 0, "emails": []},
                "important": {"count": 0, "emails": []},
                "routine": {"count": 0, "emails": []},
                "generated_at": datetime.now().isoformat()
            }

        # Classify emails
        logger.info("classifying_emails_from_external_service", count=len(emails))
        classified = await processor.classify_emails(emails)

        # Persist emails to database (OPTIMIZATION: bulk insert to eliminate N+1 queries)
        logger.info("persisting_emails_to_db", count=len(emails))

        # Collect all message IDs from classified emails
        all_message_ids = []
        for urgency_level in ['urgent', 'important', 'routine']:
            for email_data in classified[urgency_level]:
                all_message_ids.append(email_data['message_id'])

        # Single query to fetch all existing message IDs (OPTIMIZATION)
        existing_result = await db.execute(
            select(Email.message_id).where(Email.message_id.in_(all_message_ids))
        )
        existing_message_ids = set(row[0] for row in existing_result.fetchall())
        logger.debug("existing_emails_fetched", count=len(existing_message_ids))

        # Collect new emails for bulk insert
        new_emails = []
        for urgency_level in ['urgent', 'important', 'routine']:
            for email_data in classified[urgency_level]:
                # Skip if already exists (using set lookup - O(1))
                if email_data['message_id'] in existing_message_ids:
                    logger.debug("email_already_exists", message_id=email_data['message_id'])
                    continue

                # Parse received_at if it's a string (ISO format from external service)
                received_at = email_data.get('received_at')
                if isinstance(received_at, str):
                    from dateutil import parser as date_parser
                    received_at = date_parser.isoparse(received_at)

                # Create new email record
                db_email = Email(
                    message_id=email_data['message_id'],
                    thread_id=email_data.get('thread_id'),
                    sender=email_data['sender'],
                    subject=email_data['subject'],
                    body=email_data.get('body', ''),
                    urgency=EmailUrgency(email_data['urgency']),
                    attachments=email_data.get('attachments', []),
                    received_at=received_at,
                    processed=True,
                    included_in_digest=True,
                    processed_at=datetime.now()
                )
                new_emails.append(db_email)

        # Bulk insert all new emails (OPTIMIZATION: single transaction)
        if new_emails:
            db.add_all(new_emails)
            await db.commit()
            logger.info("emails_persisted", count=len(new_emails))
        else:
            logger.info("no_new_emails_to_persist")

        # Format response
        response = {
            "date": datetime.now().isoformat(),
            "total_emails": len(emails),
            "urgent": {
                "count": len(classified['urgent']),
                "emails": classified['urgent']
            },
            "important": {
                "count": len(classified['important']),
                "emails": classified['important']
            },
            "routine": {
                "count": len(classified['routine']),
                "emails": classified['routine']
            },
            "generated_at": datetime.now().isoformat()
        }

        logger.info(
            "digest_processed_from_external",
            total=len(emails),
            urgent=len(classified['urgent']),
            important=len(classified['important']),
            routine=len(classified['routine'])
        )

        return response

    except Exception as e:
        logger.error("email_processing_failed", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process emails: {str(e)}"
        )


# ============================================================================
# ROUTES PREMIUM - Composants Avancés
# ============================================================================

class DigestIntelligentRequest(BaseModel):
    """Requête génération digest intelligent avec composants premium"""
    emails_bruts: Optional[List[Dict[str, Any]]] = None  # Emails directs à classifier (optionnel)
    periode_heures: Optional[int] = 24
    max_emails: Optional[int] = 100
    generer_actions: Optional[bool] = True


class ActionsRequest(BaseModel):
    """Requête exécution actions automatiques"""
    email_ids: Optional[List[str]] = None  # Si None, traite tous les emails critiques/urgents récents


@router.post("/generate-intelligent")
async def generer_digest_intelligent(
    request: DigestIntelligentRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Génère un digest intelligent avec classification avancée

    Utilise les composants premium:
    - ClassificateurEmailAvance: 6 niveaux urgence + extraction entités
    - AgentResumeurDigest: Résumé Markdown structuré + tendances
    - ExecuteurActions: Actions automatiques selon urgence

    Returns:
        - resume_markdown: Digest formaté en Markdown
        - statistiques: Stats détaillées (total, par urgence, etc.)
        - actions_urgentes: Top actions prioritaires
        - tendances: Patterns identifiés
        - emails_classifies: Liste complète emails avec classification
    """
    try:
        from app.services.classificateur_email_avance import ClassificateurEmailAvance
        from app.services.agents.agent_resumeur_digest import AgentResumeurDigest

        logger.info("generation_digest_intelligent_demarree",
                   periode_heures=request.periode_heures,
                   max_emails=request.max_emails,
                   emails_bruts_fournis=request.emails_bruts is not None)

        # 1. Récupérer emails (soit depuis request, soit depuis DB)
        if request.emails_bruts:
            # Mode 1: Emails fournis directement dans la requête
            emails_bruts = request.emails_bruts
            logger.info("utilisation_emails_bruts_request", count=len(emails_bruts))
        else:
            # Mode 2: Récupération depuis DB
            since_time = datetime.now() - timedelta(hours=request.periode_heures)
            result = await db.execute(
                select(Email)
                .where(Email.received_at >= since_time)
                .order_by(Email.received_at.desc())
                .limit(request.max_emails)
            )
            emails_db = result.scalars().all()

            if not emails_db:
                return {
                    "resume_markdown": f"# 📧 Digest Emails - Aucun email trouvé\n\nAucun email reçu dans les dernières {request.periode_heures}h.",
                    "statistiques": {"total_emails": 0},
                    "actions_urgentes": [],
                    "tendances": [],
                    "emails_classifies": []
                }

            emails_bruts = [
                {
                    "id_message": email.message_id,
                    "sujet": email.subject,
                    "corps": email.body,
                    "expediteur": email.sender,
                    "recu_le": email.received_at
                }
                for email in emails_db
            ]
            logger.info("utilisation_emails_db", count=len(emails_bruts))

        # 2. Classification avancée batch
        classificateur = ClassificateurEmailAvance()

        emails_classifies = await classificateur.classifier_batch(emails_bruts, taille_batch=20)
        logger.info("classification_batch_terminee", total=len(emails_classifies))

        # 3. Génération digest avec résumés intelligents
        agent_resumeur = AgentResumeurDigest()
        digest = await agent_resumeur.generer_digest(
            emails_classifies,
            periode_heures=request.periode_heures
        )

        # 4. Ajouter liste emails pour UI
        digest["emails_classifies"] = [
            {
                "id_message": e.id_message,
                "sujet": e.sujet,
                "expediteur": e.expediteur,
                "urgence": e.urgence.value,
                "categorie": e.categorie.value,
                "confiance": e.confiance,
                "resume": e.resume,
                "action_requise": e.action_requise,
                "action_suggeree": e.action_suggeree,
                "recu_le": e.recu_le.isoformat() if e.recu_le else None
            }
            for e in emails_classifies
        ]

        logger.info("digest_intelligent_genere",
                   total_emails=digest["statistiques"]["total_emails"],
                   nb_actions=len(digest["actions_urgentes"]))

        return digest

    except Exception as e:
        logger.error("generation_digest_intelligent_echouee", erreur=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Échec génération digest intelligent: {str(e)}"
        )


@router.get("/actions-pending")
async def get_actions_pending(
    periode_heures: int = 24,
    db: AsyncSession = Depends(get_db)
):
    """
    Récupère les actions urgentes en attente

    Retourne uniquement les emails critiques/urgents des dernières N heures
    qui nécessitent une action immédiate

    Returns:
        Liste actions avec priorité, sujet, action suggérée
    """
    try:
        from app.services.classificateur_email_avance import ClassificateurEmailAvance, NiveauUrgenceEmail

        # Récupérer emails récents non traités
        since_time = datetime.now() - timedelta(hours=periode_heures)
        result = await db.execute(
            select(Email)
            .where(Email.received_at >= since_time)
            .where(Email.processed == True)  # Processed mais pas encore actionné
            .order_by(Email.received_at.desc())
        )
        emails_db = result.scalars().all()

        if not emails_db:
            return {"actions_pending": [], "total": 0}

        # Classifier pour identifier urgences
        classificateur = ClassificateurEmailAvance()
        emails_bruts = [
            {
                "id_message": email.message_id,
                "sujet": email.subject,
                "corps": email.body,
                "expediteur": email.sender
            }
            for email in emails_db
        ]

        emails_classifies = await classificateur.classifier_batch(emails_bruts, taille_batch=20)

        # Filtrer uniquement critiques/urgents
        actions_pending = []
        for email in emails_classifies:
            if email.urgence in [NiveauUrgenceEmail.CRITIQUE, NiveauUrgenceEmail.URGENT]:
                actions_pending.append({
                    "priorite": "🚨 CRITIQUE" if email.urgence == NiveauUrgenceEmail.CRITIQUE else "⚠️ URGENT",
                    "id_message": email.id_message,
                    "sujet": email.sujet,
                    "expediteur": email.expediteur,
                    "categorie": email.categorie.value,
                    "action_suggeree": email.action_suggeree,
                    "confiance": email.confiance
                })

        logger.info("actions_pending_recuperees", total=len(actions_pending))

        return {
            "actions_pending": actions_pending,
            "total": len(actions_pending),
            "periode_heures": periode_heures
        }

    except Exception as e:
        logger.error("recuperation_actions_pending_echouee", erreur=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Échec récupération actions: {str(e)}"
        )


@router.post("/execute-actions")
async def execute_actions(
    request: ActionsRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Exécute actions automatiques pour emails urgents

    Workflow:
    - 🚨 CRITIQUE → Workflow N8N immédiat (fuite, incendie, etc.)
    - ⚠️ URGENT → Recherche SQL/RAG + suggestion contexte
    - 📌 IMPORTANT → Génération email draft réponse
    - 📋 ROUTINIER → Création tâche

    Returns:
        Résultats avec workflows déclenchés, requêtes SQL, drafts, tâches
    """
    try:
        from app.services.classificateur_email_avance import ClassificateurEmailAvance
        from app.services.executeur_actions import ExecuteurActions

        logger.info("execution_actions_demarree", email_ids=request.email_ids)

        # Si IDs spécifiés, récupérer ces emails, sinon prendre récents critiques/urgents
        if request.email_ids:
            result = await db.execute(
                select(Email).where(Email.message_id.in_(request.email_ids))
            )
        else:
            # Prendre emails des dernières 48h
            since_time = datetime.now() - timedelta(hours=48)
            result = await db.execute(
                select(Email)
                .where(Email.received_at >= since_time)
                .order_by(Email.received_at.desc())
                .limit(50)
            )

        emails_db = result.scalars().all()

        if not emails_db:
            return {
                "workflows_declenches": [],
                "requetes_sql_executees": [],
                "drafts_generes": [],
                "taches_creees": [],
                "total_actions": 0
            }

        # Classifier emails
        classificateur = ClassificateurEmailAvance()
        emails_bruts = [
            {
                "id_message": email.message_id,
                "sujet": email.subject,
                "corps": email.body,
                "expediteur": email.sender
            }
            for email in emails_db
        ]

        emails_classifies = await classificateur.classifier_batch(emails_bruts, taille_batch=20)

        # Exécuter actions
        executeur = ExecuteurActions()
        resultats = await executeur.executer_actions_depuis_digest(emails_classifies, db)

        total_actions = (
            len(resultats["workflows_declenches"]) +
            len(resultats["requetes_sql_executees"]) +
            len(resultats["drafts_generes"]) +
            len(resultats["taches_creees"])
        )

        resultats["total_actions"] = total_actions

        logger.info("execution_actions_terminee",
                   total_actions=total_actions,
                   workflows=len(resultats["workflows_declenches"]),
                   sql=len(resultats["requetes_sql_executees"]),
                   drafts=len(resultats["drafts_generes"]),
                   taches=len(resultats["taches_creees"]))

        return resultats

    except Exception as e:
        logger.error("execution_actions_echouee", erreur=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Échec exécution actions: {str(e)}"
        )
