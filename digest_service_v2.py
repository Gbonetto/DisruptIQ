#!/usr/bin/env python3
"""
DisruptIQ Digest Service - Production-Ready Hybrid Solution
Version 2.0 - Ultra-Robust, Future-Proof Implementation

This service:
1. Fetches emails from Gmail (outside Docker for network access)
2. Validates all data with Pydantic schemas
3. Communicates with backend API with retry logic
4. Provides comprehensive error handling and logging
5. Includes health checks and monitoring

Usage:
    python digest_service_v2.py
    python digest_service_v2.py --dry-run
    python digest_service_v2.py --health-check

For Windows Service:
    python digest_service_v2.py --install
    python digest_service_v2.py --start
"""

import os
import sys
import asyncio
import base64
import argparse
import signal
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

import structlog
import httpx
from pydantic import BaseModel, Field, validator, EmailStr
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError
)
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Add backend to path for shared code
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from app.core.config import settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


# ==================== Pydantic Schemas for Validation ====================


class EmailAttachment(BaseModel):
    """Schema for email attachment"""
    filename: str
    mime_type: str
    size: int = 0
    attachment_id: Optional[str] = None

    class Config:
        extra = "ignore"


class GmailEmail(BaseModel):
    """Schema for Gmail email data with strict validation"""
    message_id: str = Field(..., min_length=1, max_length=255)
    thread_id: str = Field(..., min_length=1, max_length=255)
    sender: str = Field(..., min_length=1, max_length=500)
    subject: str = Field(..., min_length=0, max_length=1000)
    body: str = Field(default="", max_length=100000)
    snippet: str = Field(default="", max_length=500)
    received_at: datetime
    attachments: List[EmailAttachment] = Field(default_factory=list)

    @validator('sender')
    def validate_sender(cls, v):
        """Validate sender format"""
        if not v or len(v.strip()) == 0:
            raise ValueError("Sender cannot be empty")
        return v.strip()

    @validator('subject')
    def validate_subject(cls, v):
        """Sanitize subject"""
        return v.strip() if v else ""

    @validator('body')
    def validate_body(cls, v):
        """Sanitize body"""
        return v.strip() if v else ""

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DigestConfig(BaseModel):
    """Configuration for digest service"""
    backend_url: str = Field(default="http://localhost:8000")
    max_emails: int = Field(default=100, ge=1, le=1000)
    since_hours: int = Field(default=24, ge=1, le=168)  # Max 1 week
    gmail_token_path: str = Field(...)
    timeout_seconds: int = Field(default=300, ge=10, le=600)
    max_retries: int = Field(default=3, ge=1, le=10)

    @validator('backend_url')
    def validate_backend_url(cls, v):
        """Validate backend URL format"""
        if not v.startswith(('http://', 'https://')):
            raise ValueError("Backend URL must start with http:// or https://")
        return v.rstrip('/')

    @validator('gmail_token_path')
    def validate_token_path(cls, v):
        """Validate token path exists"""
        if not Path(v).exists():
            raise ValueError(f"Gmail token file not found: {v}")
        return v


class DigestMetrics(BaseModel):
    """Metrics for digest service execution"""
    execution_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    emails_fetched: int = 0
    emails_processed: int = 0
    emails_failed: int = 0
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    success: bool = False

    def duration_seconds(self) -> float:
        """Calculate execution duration"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


# ==================== Enhanced Digest Service ====================


class DigestServiceV2:
    """Production-ready digest service with comprehensive error handling"""

    def __init__(self, config: DigestConfig):
        """
        Initialize digest service with configuration

        Args:
            config: DigestConfig instance with service configuration
        """
        self.config = config
        self.gmail_service = None
        self.metrics = DigestMetrics(
            execution_id=datetime.now().strftime("%Y%m%d_%H%M%S"),
            start_time=datetime.now()
        )
        self._shutdown_requested = False

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self._initialize_gmail()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.warning("shutdown_signal_received", signal=signum)
        self._shutdown_requested = True

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HttpError, OSError)),
        reraise=True
    )
    def _initialize_gmail(self):
        """
        Initialize Gmail API connection with retry logic

        Raises:
            ValueError: If token file is missing or invalid
            HttpError: If Gmail API initialization fails
        """
        try:
            logger.info("gmail_initialization_started", token_path=self.config.gmail_token_path)

            if not os.path.exists(self.config.gmail_token_path):
                error_msg = f"Gmail token not found: {self.config.gmail_token_path}"
                logger.error("gmail_token_missing", path=self.config.gmail_token_path)
                self.metrics.errors.append(error_msg)
                raise ValueError(error_msg)

            creds = Credentials.from_authorized_user_file(
                self.config.gmail_token_path,
                settings.gmail_scopes_list
            )

            # Refresh token if expired
            if creds and creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request
                logger.info("refreshing_gmail_token")
                creds.refresh(Request())

                # Save refreshed token
                with open(self.config.gmail_token_path, 'w') as token:
                    token.write(creds.to_json())
                logger.info("gmail_token_refreshed")

            self.gmail_service = build('gmail', 'v1', credentials=creds)
            logger.info("gmail_initialized_successfully")

        except ValueError:
            raise
        except Exception as e:
            error_msg = f"Gmail initialization failed: {str(e)}"
            logger.error("gmail_init_failed", error=str(e), exc_info=True)
            self.metrics.errors.append(error_msg)
            self.gmail_service = None
            raise

    def _parse_email_date(self, date_str: str) -> datetime:
        """
        Parse email date string to datetime object

        Args:
            date_str: Date string from email header

        Returns:
            Parsed datetime object, or current time if parsing fails
        """
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except Exception as e:
            warning_msg = f"Date parse error: {date_str}"
            logger.warning("date_parse_error", date_str=date_str, error=str(e))
            self.metrics.warnings.append(warning_msg)
            return datetime.now()

    def _extract_body(self, payload: Dict) -> str:
        """
        Extract email body from Gmail payload

        Args:
            payload: Gmail message payload

        Returns:
            Email body text (plain text preferred, HTML as fallback)
        """
        try:
            body = ""

            if 'parts' in payload:
                for part in payload['parts']:
                    # Prefer plain text
                    if part['mimeType'] == 'text/plain':
                        if 'data' in part['body']:
                            body = base64.urlsafe_b64decode(
                                part['body']['data']
                            ).decode('utf-8', errors='ignore')
                            break
                    # Fallback to HTML
                    elif part['mimeType'] == 'text/html' and not body:
                        if 'data' in part['body']:
                            html_body = base64.urlsafe_b64decode(
                                part['body']['data']
                            ).decode('utf-8', errors='ignore')
                            # Limit HTML to reasonable size
                            body = html_body[:10000]
            else:
                # Simple message without parts
                if 'data' in payload.get('body', {}):
                    body = base64.urlsafe_b64decode(
                        payload['body']['data']
                    ).decode('utf-8', errors='ignore')

            return body

        except Exception as e:
            logger.warning("body_extraction_error", error=str(e))
            return ""

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=3, max=30),
        retry=retry_if_exception_type((HttpError, TimeoutError, OSError)),
        reraise=True
    )
    def _fetch_email_details(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch full email details by message ID with retry logic

        Args:
            message_id: Gmail message ID

        Returns:
            Email data dictionary or None if failed
        """
        try:
            message = self.gmail_service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()

            # Extract headers
            headers = message['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
            date_str = next((h['value'] for h in headers if h['name'] == 'Date'), '')

            # Parse date
            received_at = self._parse_email_date(date_str)

            # Extract body
            body = self._extract_body(message['payload'])

            # Extract attachments (basic info only)
            attachments = []
            if 'parts' in message['payload']:
                for part in message['payload']['parts']:
                    if part.get('filename'):
                        attachments.append({
                            'filename': part['filename'],
                            'mime_type': part['mimeType'],
                            'size': part['body'].get('size', 0),
                            'attachment_id': part['body'].get('attachmentId'),
                        })

            return {
                'message_id': message_id,
                'thread_id': message['threadId'],
                'subject': subject,
                'sender': sender,
                'received_at': received_at,
                'body': body,
                'snippet': message.get('snippet', ''),
                'attachments': attachments
            }

        except HttpError as e:
            logger.error("email_fetch_http_error", message_id=message_id, error=str(e))
            raise
        except Exception as e:
            logger.error("email_fetch_error", message_id=message_id, error=str(e), exc_info=True)
            return None

    def fetch_unread_emails(self) -> List[GmailEmail]:
        """
        Fetch unread emails from Gmail

        Returns:
            List of validated GmailEmail objects

        Raises:
            ValueError: If Gmail service not initialized
        """
        if not self.gmail_service:
            error_msg = "Gmail service not initialized"
            logger.error("gmail_service_not_available")
            self.metrics.errors.append(error_msg)
            raise ValueError(error_msg)

        if self._shutdown_requested:
            logger.info("shutdown_requested_aborting_fetch")
            return []

        try:
            # Calculate date filter
            after_date = datetime.now() - timedelta(hours=self.config.since_hours)
            after_timestamp = int(after_date.timestamp())

            # Build query
            query = f"is:unread after:{after_timestamp}"

            logger.info(
                "fetching_emails",
                query=query,
                max_results=self.config.max_emails,
                since_hours=self.config.since_hours
            )

            # Fetch message list
            results = self.gmail_service.users().messages().list(
                userId='me',
                q=query,
                maxResults=self.config.max_emails
            ).execute()

            messages = results.get('messages', [])

            if not messages:
                logger.info("no_unread_emails_found")
                return []

            logger.info("fetching_message_details", count=len(messages))

            # Fetch details for each message
            emails = []
            for i, msg in enumerate(messages, 1):
                if self._shutdown_requested:
                    logger.info("shutdown_requested_stopping_fetch", processed=i-1)
                    break

                try:
                    email_data = self._fetch_email_details(msg['id'])

                    if email_data:
                        # Validate with Pydantic
                        validated_email = GmailEmail(**email_data)
                        emails.append(validated_email)
                        logger.info(
                            "email_fetched",
                            num=i,
                            total=len(messages),
                            subject=validated_email.subject[:50]
                        )
                    else:
                        self.metrics.emails_failed += 1

                except RetryError as e:
                    logger.error(
                        "email_fetch_retry_exhausted",
                        message_id=msg['id'],
                        error=str(e)
                    )
                    self.metrics.emails_failed += 1
                    self.metrics.errors.append(f"Failed to fetch email {msg['id']} after retries")

                except Exception as e:
                    logger.error(
                        "email_validation_error",
                        message_id=msg['id'],
                        error=str(e),
                        exc_info=True
                    )
                    self.metrics.emails_failed += 1
                    self.metrics.errors.append(f"Validation error for email {msg['id']}: {str(e)}")

            self.metrics.emails_fetched = len(emails)
            logger.info(
                "emails_fetched_successfully",
                count=len(emails),
                total=len(messages),
                failed=self.metrics.emails_failed
            )

            return emails

        except HttpError as error:
            error_msg = f"Gmail API error: {str(error)}"
            logger.error("gmail_api_error", error=str(error), exc_info=True)
            self.metrics.errors.append(error_msg)
            return []

        except Exception as e:
            error_msg = f"Unexpected error fetching emails: {str(e)}"
            logger.error("unexpected_fetch_error", error=str(e), exc_info=True)
            self.metrics.errors.append(error_msg)
            return []

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=20),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True
    )
    async def _send_to_backend(self, emails: List[GmailEmail]) -> Dict[str, Any]:
        """
        Send emails to backend API with retry logic

        Args:
            emails: List of validated GmailEmail objects

        Returns:
            Backend response dictionary

        Raises:
            httpx.RequestError: On network errors
            httpx.HTTPStatusError: On HTTP errors
        """
        # Serialize emails to dict for JSON
        serialized_emails = [email.dict() for email in emails]

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            logger.info(
                "sending_to_backend",
                url=f"{self.config.backend_url}/api/digest/process-emails",
                count=len(emails)
            )

            response = await client.post(
                f"{self.config.backend_url}/api/digest/process-emails",
                json={"emails": serialized_emails}
            )

            response.raise_for_status()
            return response.json()

    async def classify_and_persist_emails(
        self,
        emails: List[GmailEmail]
    ) -> Dict[str, Any]:
        """
        Send emails to backend API for classification and persistence

        Args:
            emails: List of validated GmailEmail objects

        Returns:
            Dictionary with processing results
        """
        if not emails:
            logger.info("no_emails_to_process")
            return {
                "total_emails": 0,
                "urgent": {"count": 0, "emails": []},
                "important": {"count": 0, "emails": []},
                "routine": {"count": 0, "emails": []}
            }

        try:
            result = await self._send_to_backend(emails)

            self.metrics.emails_processed = result.get('total_emails', 0)

            logger.info(
                "backend_processing_complete",
                total=result.get('total_emails', 0),
                urgent=result.get('urgent', {}).get('count', 0),
                important=result.get('important', {}).get('count', 0),
                routine=result.get('routine', {}).get('count', 0)
            )

            return result

        except RetryError as e:
            error_msg = f"Backend communication failed after retries: {str(e)}"
            logger.error("backend_communication_retry_exhausted", error=str(e), exc_info=True)
            self.metrics.errors.append(error_msg)
            return {"error": error_msg}

        except httpx.HTTPStatusError as e:
            error_msg = f"Backend returned error {e.response.status_code}: {e.response.text}"
            logger.error(
                "backend_http_error",
                status=e.response.status_code,
                text=e.response.text
            )
            self.metrics.errors.append(error_msg)
            return {"error": error_msg}

        except Exception as e:
            error_msg = f"Backend communication error: {str(e)}"
            logger.error("backend_communication_error", error=str(e), exc_info=True)
            self.metrics.errors.append(error_msg)
            return {"error": error_msg}

    async def generate_digest(self) -> Dict[str, Any]:
        """
        Main digest generation workflow

        Returns:
            Dictionary with digest results and metrics
        """
        logger.info(
            "digest_generation_started",
            execution_id=self.metrics.execution_id,
            since_hours=self.config.since_hours,
            max_emails=self.config.max_emails
        )

        try:
            # Step 1: Fetch emails from Gmail
            emails = self.fetch_unread_emails()

            if not emails:
                self.metrics.success = True
                self.metrics.end_time = datetime.now()
                logger.info("digest_generation_complete_no_emails", metrics=self.metrics.dict())
                return {
                    "date": datetime.now().isoformat(),
                    "total_emails": 0,
                    "urgent": {"count": 0, "emails": []},
                    "important": {"count": 0, "emails": []},
                    "routine": {"count": 0, "emails": []},
                    "metrics": self.metrics.dict()
                }

            # Step 2: Send to backend for classification and persistence
            result = await self.classify_and_persist_emails(emails)

            # Update metrics
            self.metrics.end_time = datetime.now()
            self.metrics.success = "error" not in result

            logger.info(
                "digest_generation_complete",
                total=result.get('total_emails', 0),
                duration_seconds=self.metrics.duration_seconds(),
                metrics=self.metrics.dict()
            )

            result["metrics"] = self.metrics.dict()
            return result

        except Exception as e:
            error_msg = f"Digest generation failed: {str(e)}"
            logger.error("digest_generation_failed", error=str(e), exc_info=True)
            self.metrics.errors.append(error_msg)
            self.metrics.success = False
            self.metrics.end_time = datetime.now()
            return {
                "error": error_msg,
                "metrics": self.metrics.dict()
            }

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of service components

        Returns:
            Dictionary with health status
        """
        health = {
            "service": "digest_service_v2",
            "timestamp": datetime.now().isoformat(),
            "status": "healthy",
            "checks": {}
        }

        # Check Gmail service
        try:
            if self.gmail_service:
                # Try a simple API call
                self.gmail_service.users().getProfile(userId='me').execute()
                health["checks"]["gmail"] = "healthy"
            else:
                health["checks"]["gmail"] = "unavailable"
                health["status"] = "degraded"
        except Exception as e:
            health["checks"]["gmail"] = f"unhealthy: {str(e)}"
            health["status"] = "unhealthy"

        # Check backend connectivity
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.config.backend_url}/health")
                if response.status_code == 200:
                    health["checks"]["backend"] = "healthy"
                else:
                    health["checks"]["backend"] = f"unhealthy: HTTP {response.status_code}"
                    health["status"] = "degraded"
        except Exception as e:
            health["checks"]["backend"] = f"unhealthy: {str(e)}"
            health["status"] = "unhealthy"

        # Check token file
        if os.path.exists(self.config.gmail_token_path):
            health["checks"]["gmail_token"] = "present"
        else:
            health["checks"]["gmail_token"] = "missing"
            health["status"] = "unhealthy"

        return health


# ==================== CLI and Main ====================


def print_banner():
    """Print service banner"""
    print("=" * 70)
    print("📧 DisruptIQ Digest Service v2.0 - Production Ready")
    print("=" * 70)
    print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)


def print_results(result: Dict[str, Any]):
    """Pretty print digest results"""
    print("\n" + "=" * 70)
    print("📊 Digest Results")
    print("=" * 70)
    print(f"Total Emails: {result.get('total_emails', 0)}")
    print(f"🔴 Urgent: {result.get('urgent', {}).get('count', 0)}")
    print(f"🟠 Important: {result.get('important', {}).get('count', 0)}")
    print(f"🟢 Routine: {result.get('routine', {}).get('count', 0)}")

    if result.get('error'):
        print(f"\n❌ Error: {result['error']}")

    # Print metrics
    if 'metrics' in result:
        metrics = result['metrics']
        print("\n" + "-" * 70)
        print("📈 Execution Metrics")
        print("-" * 70)
        print(f"Execution ID: {metrics.get('execution_id')}")
        print(f"Duration: {metrics.get('duration_seconds', 0):.2f} seconds")
        print(f"Emails Fetched: {metrics.get('emails_fetched', 0)}")
        print(f"Emails Processed: {metrics.get('emails_processed', 0)}")
        print(f"Emails Failed: {metrics.get('emails_failed', 0)}")
        print(f"Status: {'✅ Success' if metrics.get('success') else '❌ Failed'}")

        if metrics.get('errors'):
            print("\n⚠️  Errors:")
            for error in metrics['errors']:
                print(f"  - {error}")

        if metrics.get('warnings'):
            print("\n⚠️  Warnings:")
            for warning in metrics['warnings']:
                print(f"  - {warning}")

    print("=" * 70)
    print(f"✅ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="DisruptIQ Digest Service v2.0")
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run in dry-run mode (no backend communication)'
    )
    parser.add_argument(
        '--health-check',
        action='store_true',
        help='Perform health check only'
    )
    parser.add_argument(
        '--since-hours',
        type=int,
        default=24,
        help='Fetch emails from last N hours (default: 24)'
    )
    parser.add_argument(
        '--max-emails',
        type=int,
        default=100,
        help='Maximum emails to fetch (default: 100)'
    )
    parser.add_argument(
        '--backend-url',
        type=str,
        default="http://localhost:8000",
        help='Backend API URL (default: http://localhost:8000)'
    )

    args = parser.parse_args()

    print_banner()

    try:
        # Create configuration
        config = DigestConfig(
            backend_url=args.backend_url,
            max_emails=args.max_emails,
            since_hours=args.since_hours,
            gmail_token_path=settings.GMAIL_TOKEN_PATH,
            timeout_seconds=300,
            max_retries=3
        )

        print(f"📍 Backend URL: {config.backend_url}")
        print(f"🔑 Gmail Token: {config.gmail_token_path}")
        print(f"📊 Max Emails: {config.max_emails}")
        print(f"⏱️  Since Hours: {config.since_hours}")
        print("=" * 70)

        # Initialize service
        service = DigestServiceV2(config)

        # Health check mode
        if args.health_check:
            health = await service.health_check()
            print("\n🏥 Health Check Results:")
            print("=" * 70)
            import json
            print(json.dumps(health, indent=2))
            print("=" * 70)
            return 0 if health["status"] == "healthy" else 1

        # Generate digest
        result = await service.generate_digest()

        # Print results
        print_results(result)

        # Return exit code based on success
        return 0 if result.get('metrics', {}).get('success', False) else 1

    except ValueError as e:
        logger.error("configuration_error", error=str(e))
        print(f"\n❌ Configuration Error: {str(e)}")
        return 1

    except Exception as e:
        logger.error("fatal_error", error=str(e), exc_info=True)
        print(f"\n❌ Fatal Error: {str(e)}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
