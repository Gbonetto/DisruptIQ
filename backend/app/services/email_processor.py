"""
Email Processing Service
Handles Gmail API connection, email fetching, and classification

Improvements:
- Async wrappers for Gmail API synchronous calls
- Retry logic for API resilience
- Concurrent batch processing
- Better OAuth handling for Docker
"""

import asyncio
import base64
import os
import structlog
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from functools import partial
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings
from app.services.llm_service import LLMService
from app.models.email import EmailUrgency

logger = structlog.get_logger()


class EmailProcessor:
    """Service for processing emails from Gmail"""

    def __init__(self):
        self.llm_service = LLMService()
        self.gmail_service = None
        self._initialize_gmail()

    async def _run_sync(self, func, *args, **kwargs):
        """
        Run synchronous Gmail API calls in thread pool to avoid blocking event loop.

        Args:
            func: Synchronous function to execute
            *args, **kwargs: Function arguments

        Returns:
            Function result
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            partial(func, *args, **kwargs)
        )

    def _initialize_gmail(self):
        """
        Initialize Gmail API connection.

        Note: Only refreshes tokens, does not attempt interactive auth.
        For first-time setup, run: python backend/scripts/gmail_auth.py
        """
        try:
            creds = None

            # Check if token exists
            if not os.path.exists(settings.GMAIL_TOKEN_PATH):
                logger.warning(
                    "gmail_token_missing",
                    path=settings.GMAIL_TOKEN_PATH,
                    message="Run 'python scripts/gmail_auth.py' to authenticate"
                )
                self.gmail_service = None
                return

            # Load existing token
            creds = Credentials.from_authorized_user_file(
                settings.GMAIL_TOKEN_PATH,
                settings.GMAIL_SCOPES
            )

            # Refresh if expired (but don't try interactive auth)
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # Save refreshed token
                with open(settings.GMAIL_TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
                logger.info("gmail_token_refreshed")

            self.gmail_service = build('gmail', 'v1', credentials=creds)
            logger.info("gmail_initialized")

        except Exception as e:
            logger.error("gmail_init_failed", error=str(e))
            self.gmail_service = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(HttpError),
        reraise=True
    )
    async def _fetch_messages_list_with_retry(
        self,
        query: str,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """
        Fetch message list with retry logic.

        Args:
            query: Gmail query string
            max_results: Maximum results

        Returns:
            List of message IDs

        Note:
            Retries up to 3 times with exponential backoff for HttpError
        """
        # Run Gmail API call in thread pool (async wrapper)
        results = await self._run_sync(
            lambda: self.gmail_service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
        )

        return results.get('messages', [])

    async def fetch_unread_emails(
        self,
        max_results: int = 50,
        since_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Fetch unread emails from the last N hours

        Args:
            max_results: Maximum number of emails to fetch
            since_hours: Fetch emails from last N hours

        Returns:
            List of email dictionaries
        """
        if not self.gmail_service:
            logger.warning("gmail_service_not_initialized")
            return []

        try:
            # Calculate date filter
            after_date = datetime.now() - timedelta(hours=since_hours)
            after_timestamp = int(after_date.timestamp())

            # Build query
            query = f"is:unread after:{after_timestamp}"

            # Fetch message list with retry
            messages = await self._fetch_messages_list_with_retry(query, max_results)

            if not messages:
                logger.info("no_unread_emails_found")
                return []

            # Fetch full message details concurrently (batch)
            tasks = [self._get_email_details(msg['id']) for msg in messages]
            email_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions and None values
            emails = [
                email for email in email_results
                if email and not isinstance(email, Exception)
            ]

            # Log any failures
            failures = [
                email for email in email_results
                if isinstance(email, Exception)
            ]
            if failures:
                logger.warning("email_fetch_partial_failure", failed_count=len(failures))

            logger.info("emails_fetched", count=len(emails), total=len(messages))
            return emails

        except HttpError as error:
            logger.error("gmail_fetch_error", error=str(error))
            return []
        except Exception as e:
            logger.error("unexpected_fetch_error", error=str(e))
            return []

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(HttpError),
        reraise=True
    )
    async def _get_email_details(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full email details by message ID with retry logic.

        Args:
            message_id: Gmail message ID

        Returns:
            Email data dict or None if failed

        Note:
            Retries up to 3 times with exponential backoff
        """
        try:
            # Run Gmail API call in thread pool (async wrapper)
            message = await self._run_sync(
                lambda: self.gmail_service.users().messages().get(
                    userId='me',
                    id=message_id,
                    format='full'
                ).execute()
            )

            # Extract headers
            headers = message['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), '')

            # Extract body
            body = self._extract_body(message['payload'])

            # Extract attachments info
            attachments = self._extract_attachments_info(message['payload'])

            return {
                'message_id': message_id,
                'thread_id': message['threadId'],
                'subject': subject,
                'sender': sender,
                'received_at': self._parse_email_date(date),
                'body': body,
                'attachments': attachments,
                'snippet': message.get('snippet', ''),
            }

        except HttpError as e:
            logger.error("email_details_http_error", message_id=message_id, error=str(e))
            raise  # Will be retried by @retry decorator
        except Exception as e:
            logger.error("email_details_error", message_id=message_id, error=str(e))
            return None

    def _parse_email_date(self, date_str: str) -> str:
        """Parse email date string to ISO format"""
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            return dt.isoformat()
        except Exception as e:
            logger.error("date_parse_error", date_str=date_str, error=str(e))
            return datetime.now().isoformat()

    def _extract_body(self, payload: Dict) -> str:
        """Extract email body from payload"""
        body = ""

        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        body = base64.urlsafe_b64decode(
                            part['body']['data']
                        ).decode('utf-8')
                        break
        else:
            if 'data' in payload['body']:
                body = base64.urlsafe_b64decode(
                    payload['body']['data']
                ).decode('utf-8')

        return body

    def _extract_attachments_info(self, payload: Dict) -> List[Dict[str, Any]]:
        """Extract attachment information"""
        attachments = []

        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('filename'):
                    attachments.append({
                        'filename': part['filename'],
                        'mime_type': part['mimeType'],
                        'size': part['body'].get('size', 0),
                        'attachment_id': part['body'].get('attachmentId'),
                    })

        return attachments

    async def classify_emails(
        self,
        emails: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Classify emails by urgency using LLM

        Args:
            emails: List of email dictionaries

        Returns:
            Dictionary with emails grouped by urgency
        """
        classified = {
            'urgent': [],
            'important': [],
            'routine': []
        }

        for email in emails:
            try:
                urgency = await self.llm_service.classify_email_urgency(
                    subject=email['subject'],
                    sender=email['sender'],
                    body=email['body'],
                    snippet=email['snippet']
                )

                email['urgency'] = urgency
                classified[urgency].append(email)

                logger.info(
                    "email_classified",
                    subject=email['subject'],
                    urgency=urgency
                )

            except Exception as e:
                logger.error(
                    "classification_error",
                    subject=email['subject'],
                    error=str(e)
                )
                # Default to routine if classification fails
                email['urgency'] = 'routine'
                classified['routine'].append(email)

        return classified

    async def generate_digest_html(
        self,
        classified_emails: Dict[str, List[Dict[str, Any]]]
    ) -> str:
        """
        Generate HTML digest from classified emails

        Args:
            classified_emails: Dictionary of emails grouped by urgency

        Returns:
            HTML string
        """
        urgency_colors = {
            'urgent': '#EF4444',
            'important': '#F59E0B',
            'routine': '#10B981'
        }

        urgency_icons = {
            'urgent': '🔴',
            'important': '🟠',
            'routine': '🟢'
        }

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #3B82F6; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                .section {{ margin-bottom: 30px; }}
                .section-title {{ font-size: 18px; font-weight: bold; margin-bottom: 15px; }}
                .email-card {{ border: 1px solid #E5E7EB; border-radius: 8px; padding: 15px; margin-bottom: 10px; }}
                .email-subject {{ font-weight: bold; margin-bottom: 5px; }}
                .email-sender {{ color: #6B7280; font-size: 14px; margin-bottom: 10px; }}
                .email-snippet {{ color: #374151; font-size: 14px; }}
                .badge {{ display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 12px; color: white; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📧 DisruptIQ - Digest Quotidien</h1>
                <p>{datetime.now().strftime('%A %d %B %Y')}</p>
                <p>Total: {sum(len(emails) for emails in classified_emails.values())} emails</p>
            </div>
        """

        for urgency in ['urgent', 'important', 'routine']:
            emails = classified_emails.get(urgency, [])
            if not emails:
                continue

            html += f"""
            <div class="section">
                <div class="section-title">
                    {urgency_icons[urgency]} {urgency.upper()} ({len(emails)})
                </div>
            """

            for email in emails:
                html += f"""
                <div class="email-card">
                    <div class="email-subject">{email['subject']}</div>
                    <div class="email-sender">De: {email['sender']}</div>
                    <div class="email-snippet">{email['snippet'][:200]}...</div>
                    <span class="badge" style="background: {urgency_colors[urgency]};">
                        {urgency}
                    </span>
                </div>
                """

            html += "</div>"

        html += """
        </body>
        </html>
        """

        return html

    async def send_digest_email(self, html_content: str, recipient: str):
        """Send the digest email via Gmail API"""
        # TODO: Implement email sending via Gmail API
        logger.info("digest_email_sent", recipient=recipient)
        pass
