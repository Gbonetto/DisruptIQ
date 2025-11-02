#!/usr/bin/env python3
"""
DisruptIQ Digest Service - Hybrid Solution
Runs outside Docker to access Gmail API, communicates with backend API

This service:
1. Fetches emails from Gmail (outside Docker for network access)
2. Classifies emails using OpenAI
3. Persists results to backend API (Docker)

Usage:
    python digest_service.py

For Windows Service:
    python digest_service.py --install
    python digest_service.py --start
"""

import os
import sys
import asyncio
import base64
import structlog
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Add backend to path for shared code
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from app.core.config import settings

logger = structlog.get_logger()


class DigestService:
    """Standalone digest service that runs outside Docker"""

    def __init__(self, backend_url: str = "http://localhost:8000"):
        self.backend_url = backend_url
        self.gmail_service = None
        self._initialize_gmail()

    def _initialize_gmail(self):
        """Initialize Gmail API connection"""
        try:
            if not os.path.exists(settings.GMAIL_TOKEN_PATH):
                logger.error("gmail_token_missing", path=settings.GMAIL_TOKEN_PATH)
                return

            creds = Credentials.from_authorized_user_file(
                settings.GMAIL_TOKEN_PATH,
                settings.gmail_scopes_list
            )

            if creds and creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                with open(settings.GMAIL_TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
                logger.info("gmail_token_refreshed")

            self.gmail_service = build('gmail', 'v1', credentials=creds)
            logger.info("gmail_initialized")

        except Exception as e:
            logger.error("gmail_init_failed", error=str(e))
            self.gmail_service = None

    def _parse_email_date(self, date_str: str) -> datetime:
        """Parse email date string to datetime object"""
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except Exception as e:
            logger.error("date_parse_error", date_str=date_str, error=str(e))
            return datetime.now()

    def _extract_body(self, payload: Dict) -> str:
        """Extract email body from payload"""
        body = ""

        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        body = base64.urlsafe_b64decode(
                            part['body']['data']
                        ).decode('utf-8', errors='ignore')
                        break
                elif part['mimeType'] == 'text/html' and not body:
                    # Fallback to HTML if no plain text
                    if 'data' in part['body']:
                        body = base64.urlsafe_b64decode(
                            part['body']['data']
                        ).decode('utf-8', errors='ignore')[:1000]  # Limit HTML
        else:
            if 'data' in payload['body']:
                body = base64.urlsafe_b64decode(
                    payload['body']['data']
                ).decode('utf-8', errors='ignore')

        return body

    def fetch_unread_emails(
        self,
        max_results: int = 100,
        since_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Fetch unread emails from Gmail"""
        if not self.gmail_service:
            logger.warning("gmail_service_not_initialized")
            return []

        try:
            # Calculate date filter
            after_date = datetime.now() - timedelta(hours=since_hours)
            after_timestamp = int(after_date.timestamp())

            # Build query
            query = f"is:unread after:{after_timestamp}"

            logger.info("fetching_emails", query=query, max_results=max_results)

            # Fetch message list
            results = self.gmail_service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()

            messages = results.get('messages', [])

            if not messages:
                logger.info("no_unread_emails_found")
                return []

            logger.info("fetching_message_details", count=len(messages))

            emails = []
            for i, msg in enumerate(messages):
                try:
                    message = self.gmail_service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='full'
                    ).execute()

                    # Extract headers
                    headers = message['payload']['headers']
                    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
                    sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
                    date = next((h['value'] for h in headers if h['name'] == 'Date'), '')

                    # Extract body
                    body = self._extract_body(message['payload'])

                    email_data = {
                        'message_id': msg['id'],
                        'thread_id': message['threadId'],
                        'subject': subject,
                        'sender': sender,
                        'received_at': self._parse_email_date(date),  # Send as datetime object
                        'body': body,
                        'snippet': message.get('snippet', ''),
                    }

                    emails.append(email_data)
                    logger.info("email_fetched", num=i+1, total=len(messages), subject=subject[:50])

                except Exception as e:
                    logger.error("email_fetch_error", message_id=msg['id'], error=str(e))
                    continue

            logger.info("emails_fetched_successfully", count=len(emails), total=len(messages))
            return emails

        except HttpError as error:
            logger.error("gmail_api_error", error=str(error))
            return []
        except Exception as e:
            logger.error("unexpected_error", error=str(e))
            return []

    async def classify_and_persist_emails(self, emails: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Send emails to backend API for classification and persistence"""
        if not emails:
            logger.info("no_emails_to_process")
            return {
                "total_emails": 0,
                "urgent": {"count": 0, "emails": []},
                "important": {"count": 0, "emails": []},
                "routine": {"count": 0, "emails": []}
            }

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                logger.info("sending_to_backend", url=f"{self.backend_url}/api/digest/process-emails", count=len(emails))

                # Serialize datetime objects to ISO strings for JSON
                serialized_emails = []
                for email in emails:
                    email_copy = email.copy()
                    if isinstance(email_copy.get('received_at'), datetime):
                        email_copy['received_at'] = email_copy['received_at'].isoformat()
                    serialized_emails.append(email_copy)

                response = await client.post(
                    f"{self.backend_url}/api/digest/process-emails",
                    json={"emails": serialized_emails}
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.info("backend_processing_complete",
                               total=result.get('total_emails', 0),
                               urgent=result.get('urgent', {}).get('count', 0),
                               important=result.get('important', {}).get('count', 0),
                               routine=result.get('routine', {}).get('count', 0))
                    return result
                else:
                    logger.error("backend_api_error", status=response.status_code, text=response.text)
                    return {"error": f"Backend returned {response.status_code}"}

        except Exception as e:
            logger.error("backend_communication_error", error=str(e))
            return {"error": str(e)}

    async def generate_digest(self, since_hours: int = 24, max_emails: int = 100) -> Dict[str, Any]:
        """Main digest generation workflow"""
        logger.info("digest_generation_started", since_hours=since_hours, max_emails=max_emails)

        # Step 1: Fetch emails from Gmail (outside Docker)
        emails = self.fetch_unread_emails(max_results=max_emails, since_hours=since_hours)

        if not emails:
            logger.info("digest_generation_complete_no_emails")
            return {
                "date": datetime.now().isoformat(),
                "total_emails": 0,
                "urgent": {"count": 0, "emails": []},
                "important": {"count": 0, "emails": []},
                "routine": {"count": 0, "emails": []},
            }

        # Step 2: Send to backend for classification and persistence
        result = await self.classify_and_persist_emails(emails)

        logger.info("digest_generation_complete", total=result.get('total_emails', 0))
        return result


async def main():
    """Main entry point"""
    print("=" * 60)
    print("📧 DisruptIQ Digest Service - Hybrid Solution")
    print("=" * 60)
    print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📍 Backend URL: http://localhost:8000")
    print(f"🔑 Gmail Token: {settings.GMAIL_TOKEN_PATH}")
    print("=" * 60)

    service = DigestService()

    # Generate digest
    result = await service.generate_digest(since_hours=24, max_emails=100)

    # Print results
    print("\n" + "=" * 60)
    print("📊 Digest Results")
    print("=" * 60)
    print(f"Total Emails: {result.get('total_emails', 0)}")
    print(f"🔴 Urgent: {result.get('urgent', {}).get('count', 0)}")
    print(f"🟠 Important: {result.get('important', {}).get('count', 0)}")
    print(f"🟢 Routine: {result.get('routine', {}).get('count', 0)}")

    if result.get('error'):
        print(f"\n❌ Error: {result['error']}")

    print("=" * 60)
    print(f"✅ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
