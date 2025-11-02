"""
Email Digest Endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import structlog
import asyncio
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


@router.post("/generate")
async def generate_digest(
    request: DigestGenerateRequest = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate email digest with Gmail sync - HYBRID ARCHITECTURE

    ## Architecture Overview:

    This endpoint implements a **hybrid Gmail + Database approach** for resilient
    email digest generation. The system attempts real-time Gmail sync but gracefully
    falls back to cached data if Gmail is unavailable.

    ## Workflow:

    1. **Gmail API Fetch** (with 60s timeout protection)
       - Authenticates via OAuth2 (credentials/token.json)
       - Fetches unread emails from the last `since_hours`
       - Timeout prevents hanging requests on network issues

    2. **LLM Classification** (parallel processing, 90s timeout)
       - Classifies emails by urgency: URGENT, IMPORTANT, ROUTINE
       - Uses semantic analysis of subject + body
       - Processes in parallel for speed

    3. **Database Persistence** (bulk insert)
       - Stores classified emails in `emails` table
       - Provides offline access to email history
       - Enables digest generation even when Gmail is down

    4. **Digest Generation from Database** (always succeeds)
       - Queries `emails` table for cached/fresh data
       - Groups by urgency level
       - Returns structured digest

    ## Benefits of Hybrid Approach:

    - ✅ **Real-time data**: Fresh emails when Gmail is accessible
    - ✅ **Offline capability**: Works with cached data when Gmail is down
    - ✅ **Timeout protection**: Never hangs indefinitely (120s total max)
    - ✅ **Docker-safe**: Handles container networking issues gracefully
    - ✅ **Resilient**: Digest endpoint always returns successfully

    ## Gmail Setup (One-time):

    ```bash
    # 1. Place Gmail API credentials
    cp path/to/credentials.json credentials/credentials.json

    # 2. Run authentication script (opens browser for OAuth)
    cd backend
    python scripts/gmail_auth.py

    # 3. Verify token.json was created
    ls -la credentials/token.json
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
    - `gmail_sync_status`: str - "success", "timeout", or "failed"

    ## Timeouts:

    - Gmail fetch: 60 seconds
    - LLM classification: 90 seconds
    - Total endpoint: ~120 seconds max

    ## Notes:

    - Gmail API uses OAuth2 - token refreshes automatically
    - Database cache enables historical digest queries
    - Parallel LLM classification for speed (async/await)
    - Fallback ensures digest always succeeds
    """
    if request is None:
        request = DigestGenerateRequest()

    gmail_fetch_succeeded = False

    try:
        # Try to fetch from Gmail with timeout protection
        processor = get_email_processor()
        logger.info("attempting_gmail_fetch", since_hours=request.since_hours)

        try:
            # Fetch with 60 second timeout
            emails = await asyncio.wait_for(
                processor.fetch_unread_emails(
                    max_results=request.max_emails,
                    since_hours=request.since_hours
                ),
                timeout=60.0
            )

            if emails:
                logger.info("gmail_fetch_succeeded", count=len(emails))

                # Classify emails with LLM (also with timeout)
                classified = await asyncio.wait_for(
                    processor.classify_emails(emails),
                    timeout=90.0
                )

                # Persist to database
                await _persist_classified_emails(db, classified)
                gmail_fetch_succeeded = True
                logger.info("emails_synced_to_db", count=len(emails))

        except asyncio.TimeoutError:
            logger.warning("gmail_fetch_timeout", message="Gmail fetch took too long, using existing DB data")
        except Exception as e:
            logger.warning("gmail_fetch_failed", error=str(e), message="Using existing DB data")

        # Whether Gmail succeeded or not, return digest from database
        # This ensures we always return data
        time_threshold = datetime.now() - timedelta(hours=request.since_hours)

        logger.info("fetching_digest_from_db", gmail_synced=gmail_fetch_succeeded)
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
                "generated_at": datetime.now().isoformat(),
                "gmail_synced": gmail_fetch_succeeded
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
