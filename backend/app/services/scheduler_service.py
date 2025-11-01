"""
Scheduler Service - Manages scheduled tasks
"""

import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import structlog
from typing import List

from app.services.email_sender import EmailSenderService
from app.api.endpoints.digest import generate_digest
from app.core.database import get_db

logger = structlog.get_logger()


class SchedulerService:
    """Service for managing scheduled tasks like daily digest"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.email_service = EmailSenderService()
        self.enabled = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
        self.digest_time = os.getenv("DIGEST_SEND_TIME", "08:00")  # Default 8:00 AM
        self.digest_recipients = self._parse_recipients()
        # Hourly digest generation interval (in minutes, default: 60)
        self.digest_interval_minutes = int(os.getenv("DIGEST_GENERATION_INTERVAL", "60"))

    def _parse_recipients(self) -> List[str]:
        """Parse digest recipients from environment variable"""
        recipients_str = os.getenv("DIGEST_RECIPIENTS", "")
        if not recipients_str:
            logger.warning("no_digest_recipients_configured")
            return []

        # Split by comma and clean up
        recipients = [email.strip() for email in recipients_str.split(",") if email.strip()]
        return recipients

    async def send_daily_digest_job(self):
        """
        Job to generate and send daily digest
        This is called by the scheduler
        """
        try:
            logger.info("daily_digest_job_started")

            # Check if recipients are configured
            if not self.digest_recipients:
                logger.error("digest_job_failed", reason="No recipients configured")
                return

            # Generate digest
            async for db in get_db():
                try:
                    # Call the digest generation endpoint
                    from app.services.email_processor import EmailProcessor
                    from app.services.llm_service import LLMService

                    email_processor = EmailProcessor()
                    llm_service = LLMService()

                    # Get unprocessed emails
                    logger.info("fetching_unread_emails")
                    emails = await email_processor.fetch_unread_emails()

                    if not emails:
                        logger.info("no_new_emails_for_digest")
                        return

                    logger.info("classifying_emails", count=len(emails))

                    # Classify emails by urgency
                    classified_emails = {
                        "urgent": [],
                        "important": [],
                        "routine": []
                    }

                    for email in emails:
                        # Classify using LLM
                        urgency = await llm_service.classify_urgency(
                            subject=email.get("subject", ""),
                            body=email.get("body", "")
                        )

                        urgency_key = urgency.lower()
                        if urgency_key in classified_emails:
                            classified_emails[urgency_key].append({
                                "id": email.get("id"),
                                "subject": email.get("subject", "Sans objet"),
                                "sender": email.get("from", "Inconnu"),
                                "snippet": email.get("snippet", email.get("body", "")[:150]),
                                "body": email.get("body", ""),
                                "urgency": urgency_key
                            })

                    # Build digest data
                    digest_data = {
                        "date": datetime.now().strftime("%d %B %Y"),
                        "total_emails": len(emails),
                        "urgent": {
                            "count": len(classified_emails["urgent"]),
                            "emails": classified_emails["urgent"]
                        },
                        "important": {
                            "count": len(classified_emails["important"]),
                            "emails": classified_emails["important"]
                        },
                        "routine": {
                            "count": len(classified_emails["routine"]),
                            "emails": classified_emails["routine"]
                        }
                    }

                    logger.info(
                        "digest_generated",
                        urgent=digest_data["urgent"]["count"],
                        important=digest_data["important"]["count"],
                        routine=digest_data["routine"]["count"]
                    )

                    # Format email content
                    html_content = self.email_service.format_digest_html(digest_data)
                    text_content = self.email_service.format_digest_text(digest_data)

                    # Send email
                    subject = f"📧 Digest Quotidien - {digest_data['date']}"
                    success = self.email_service.send_digest_email(
                        to_emails=self.digest_recipients,
                        subject=subject,
                        html_content=html_content,
                        text_content=text_content
                    )

                    if success:
                        logger.info(
                            "daily_digest_sent_successfully",
                            recipients=len(self.digest_recipients)
                        )
                    else:
                        logger.error("daily_digest_send_failed")

                except Exception as e:
                    logger.error("digest_generation_error", error=str(e))
                finally:
                    break  # Exit the async for loop after first iteration

        except Exception as e:
            logger.error("daily_digest_job_failed", error=str(e))

    async def generate_digest_background_job(self):
        """
        Background job to generate digest and persist to database
        Runs hourly to ensure no emails are missed
        Frontend displays results from database instantly
        """
        try:
            logger.info("background_digest_generation_started")

            # Generate digest using existing endpoint logic
            async for db in get_db():
                try:
                    from app.services.email_processor import EmailProcessor
                    from app.models.email import Email, EmailUrgency
                    from sqlalchemy import select

                    processor = EmailProcessor()

                    # Fetch unread emails (limit to 20 per batch to avoid timeouts)
                    logger.info("fetching_unread_emails_background")
                    emails = await processor.fetch_unread_emails(
                        max_results=20,
                        since_hours=24
                    )

                    if not emails:
                        logger.info("no_new_emails_for_background_digest")
                        return

                    # Classify emails
                    logger.info("classifying_emails_background", count=len(emails))
                    classified = await processor.classify_emails(emails)

                    # Persist to database
                    persisted_count = 0
                    for urgency_level in ['urgent', 'important', 'routine']:
                        for email_data in classified[urgency_level]:
                            # Check if email already exists
                            existing = await db.execute(
                                select(Email).where(Email.message_id == email_data['message_id'])
                            )
                            if existing.scalar_one_or_none():
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
                                attachments=email_data.get('attachments', []),
                                received_at=email_data.get('received_at'),
                                processed=True,
                                included_in_digest=True,
                                processed_at=datetime.now()
                            )
                            db.add(db_email)
                            persisted_count += 1

                    # Commit all emails
                    await db.commit()

                    logger.info(
                        "background_digest_generation_completed",
                        total_fetched=len(emails),
                        persisted=persisted_count,
                        urgent=len(classified['urgent']),
                        important=len(classified['important']),
                        routine=len(classified['routine'])
                    )

                except Exception as e:
                    logger.error("background_digest_generation_error", error=str(e))
                    await db.rollback()
                finally:
                    break  # Exit after first iteration

        except Exception as e:
            logger.error("background_digest_job_failed", error=str(e))

    def start(self):
        """Start the scheduler"""
        if not self.enabled:
            logger.info("scheduler_disabled")
            return

        if not self.digest_recipients:
            logger.warning("scheduler_started_without_recipients")

        try:
            # Schedule hourly background digest generation (persists to DB)
            self.scheduler.add_job(
                self.generate_digest_background_job,
                'interval',
                minutes=self.digest_interval_minutes,
                id="background_digest_generation",
                name="Generate Digest Background (DB Persistence)",
                replace_existing=True
            )

            logger.info(
                "background_digest_scheduled",
                interval_minutes=self.digest_interval_minutes
            )

            # Parse digest time (format: HH:MM) for daily email sending
            hour, minute = map(int, self.digest_time.split(":"))

            # Schedule daily digest email sending (optional)
            if self.digest_recipients:
                self.scheduler.add_job(
                    self.send_daily_digest_job,
                    trigger=CronTrigger(hour=hour, minute=minute),
                    id="daily_digest_email",
                    name="Send Daily Digest Email",
                    replace_existing=True
                )

                logger.info(
                    "daily_digest_email_scheduled",
                    digest_time=self.digest_time,
                    recipients=len(self.digest_recipients)
                )

            logger.info("scheduler_started_successfully")
            self.scheduler.start()

        except ValueError as e:
            logger.error("invalid_digest_time_format", time=self.digest_time, error=str(e))
        except Exception as e:
            logger.error("scheduler_start_failed", error=str(e))

    def shutdown(self):
        """Shutdown the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("scheduler_shutdown")

    def trigger_digest_now(self):
        """
        Manually trigger digest generation and send immediately
        Useful for testing
        """
        logger.info("manual_digest_trigger")
        self.scheduler.add_job(
            self.send_daily_digest_job,
            id="manual_digest",
            replace_existing=True
        )


# Global scheduler instance
_scheduler_instance = None


def get_scheduler() -> SchedulerService:
    """Get or create scheduler instance"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SchedulerService()
    return _scheduler_instance
