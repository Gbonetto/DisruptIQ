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
from app.services.digest_summarizer import DigestSummarizer
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
                llm_analysis=email_data.get('llm_analysis'),
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
                "llm_analysis": email.llm_analysis if hasattr(email, 'llm_analysis') else None,
                "received_at": email.received_at.isoformat() if email.received_at else None,
                "attachments": email.attachments or []
            }

            if email.urgency == EmailUrgency.URGENT:
                urgent_emails.append(email_dict)
            elif email.urgency == EmailUrgency.IMPORTANT:
                important_emails.append(email_dict)
            else:
                routine_emails.append(email_dict)

        # Generate executive summary
        classified_emails = {
            "urgent": urgent_emails,
            "important": important_emails,
            "routine": routine_emails
        }

        summarizer = DigestSummarizer()
        executive_summary = await summarizer.generate_executive_summary(classified_emails)

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
            "executive_summary": executive_summary,
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
                "category": email.category,
                "llm_analysis": email.llm_analysis if hasattr(email, 'llm_analysis') else None,
                "received_at": email.received_at.isoformat() if email.received_at else None,
                "attachments": email.attachments or []
            }

            if email.urgency == EmailUrgency.URGENT:
                urgent.append(email_dict)
            elif email.urgency == EmailUrgency.IMPORTANT:
                important.append(email_dict)
            else:
                routine.append(email_dict)

        # Generate executive summary
        classified_emails = {
            "urgent": urgent,
            "important": important,
            "routine": routine
        }

        summarizer = DigestSummarizer()
        executive_summary = await summarizer.generate_executive_summary(classified_emails)

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
            "executive_summary": executive_summary,
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
                    category=email_data.get('category'),
                    llm_analysis=email_data.get('llm_analysis'),
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

        # Generate executive summary
        summarizer = DigestSummarizer()
        executive_summary = await summarizer.generate_executive_summary(classified)

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
            "executive_summary": executive_summary,
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
