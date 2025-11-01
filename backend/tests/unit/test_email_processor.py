"""
Unit Tests for Email Processor Service
Tests email fetching, classification, and filtering logic
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.services.email_processor import EmailProcessor


@pytest.mark.unit
@pytest.mark.asyncio
class TestEmailProcessorFiltering:
    """Test email filtering logic"""

    def test_is_promotional_email_noreply(self):
        """Test promotional email detection - noreply senders"""
        processor = EmailProcessor()

        # Promotional senders
        assert processor._is_promotional_email("noreply@example.com", "Test") is True
        assert processor._is_promotional_email("no-reply@marketing.com", "Test") is True
        assert processor._is_promotional_email("do-not-reply@company.com", "Test") is True
        assert processor._is_promotional_email("info@newsletter.com", "Test") is True
        assert processor._is_promotional_email("marketing@company.com", "Test") is True

    def test_is_promotional_email_valid_sender(self):
        """Test that real senders are not filtered"""
        processor = EmailProcessor()

        # Real senders
        assert processor._is_promotional_email("john@company.com", "Meeting") is False
        assert processor._is_promotional_email("sarah.smith@client.com", "Project") is False
        assert processor._is_promotional_email("contact.person@vendor.com", "Invoice") is False

    def test_is_promotional_email_subject_keywords(self):
        """Test promotional detection based on subject keywords"""
        processor = EmailProcessor()

        # Multiple spam keywords in subject
        assert processor._is_promotional_email(
            "normal@example.com",
            "Unsubscribe from our newsletter - Limited time offer"
        ) is True

        # Single spam keyword (should not filter)
        assert processor._is_promotional_email(
            "normal@example.com",
            "Please unsubscribe me"
        ) is False

    def test_is_promotional_email_edge_cases(self):
        """Test edge cases for promotional detection"""
        processor = EmailProcessor()

        # Empty strings
        assert processor._is_promotional_email("", "") is False

        # Case insensitivity
        assert processor._is_promotional_email("NOREPLY@EXAMPLE.COM", "TEST") is True

        # Partial matches
        assert processor._is_promotional_email("mynoreply@example.com", "Test") is True


@pytest.mark.unit
@pytest.mark.asyncio
class TestEmailProcessorDateParsing:
    """Test email date parsing"""

    def test_parse_email_date_valid_formats(self):
        """Test parsing various valid date formats"""
        processor = EmailProcessor()

        # RFC 2822 format (standard email format)
        date1 = processor._parse_email_date("Mon, 1 Nov 2025 12:00:00 +0000")
        assert isinstance(date1, datetime)
        assert date1.year == 2025
        assert date1.month == 11
        assert date1.day == 1

        # Another valid format
        date2 = processor._parse_email_date("Thu, 31 Oct 2025 16:58:25 +0100")
        assert isinstance(date2, datetime)

    def test_parse_email_date_invalid_format(self):
        """Test parsing invalid date format returns current time"""
        processor = EmailProcessor()

        # Invalid format should return current datetime
        result = processor._parse_email_date("invalid date string")
        assert isinstance(result, datetime)
        # Should be close to now
        assert (datetime.now() - result).total_seconds() < 1


@pytest.mark.unit
@pytest.mark.asyncio
class TestEmailProcessorBodyExtraction:
    """Test email body extraction from payload"""

    def test_extract_body_from_plain_text(self):
        """Test extracting plain text body"""
        processor = EmailProcessor()

        payload = {
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {
                        "data": "VGVzdCBib2R5"  # Base64: "Test body"
                    }
                }
            ]
        }

        body = processor._extract_body(payload)
        assert body == "Test body"

    def test_extract_body_from_html_fallback(self):
        """Test extracting HTML body as fallback"""
        processor = EmailProcessor()

        payload = {
            "parts": [
                {
                    "mimeType": "text/html",
                    "body": {
                        "data": "PHA+VGVzdCBIVE1MPC9wPg=="  # Base64: "<p>Test HTML</p>"
                    }
                }
            ]
        }

        body = processor._extract_body(payload)
        assert "Test HTML" in body

    def test_extract_body_from_simple_message(self):
        """Test extracting body from simple message without parts"""
        processor = EmailProcessor()

        payload = {
            "body": {
                "data": "U2ltcGxlIGJvZHk="  # Base64: "Simple body"
            }
        }

        body = processor._extract_body(payload)
        assert body == "Simple body"

    def test_extract_body_empty(self):
        """Test extracting body when no body exists"""
        processor = EmailProcessor()

        payload = {
            "parts": []
        }

        body = processor._extract_body(payload)
        assert body == ""


@pytest.mark.unit
@pytest.mark.asyncio
class TestEmailProcessorAttachments:
    """Test attachment information extraction"""

    def test_extract_attachments_info_multiple(self):
        """Test extracting multiple attachments"""
        processor = EmailProcessor()

        payload = {
            "parts": [
                {
                    "filename": "document.pdf",
                    "mimeType": "application/pdf",
                    "body": {
                        "size": 1024,
                        "attachmentId": "att_001"
                    }
                },
                {
                    "filename": "image.png",
                    "mimeType": "image/png",
                    "body": {
                        "size": 2048,
                        "attachmentId": "att_002"
                    }
                }
            ]
        }

        attachments = processor._extract_attachments_info(payload)

        assert len(attachments) == 2
        assert attachments[0]["filename"] == "document.pdf"
        assert attachments[0]["mime_type"] == "application/pdf"
        assert attachments[0]["size"] == 1024
        assert attachments[1]["filename"] == "image.png"

    def test_extract_attachments_info_no_attachments(self):
        """Test extracting when no attachments"""
        processor = EmailProcessor()

        payload = {
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": "VGVzdA=="}
                }
            ]
        }

        attachments = processor._extract_attachments_info(payload)
        assert attachments == []

    def test_extract_attachments_info_no_parts(self):
        """Test extracting when no parts"""
        processor = EmailProcessor()

        payload = {}

        attachments = processor._extract_attachments_info(payload)
        assert attachments == []


@pytest.mark.unit
@pytest.mark.asyncio
class TestEmailProcessorClassification:
    """Test email classification logic"""

    async def test_classify_emails_filters_promotional(self):
        """Test that promotional emails are filtered out"""
        processor = EmailProcessor()

        emails = [
            {
                "message_id": "msg_001",
                "sender": "noreply@marketing.com",
                "subject": "Special Offer",
                "body": "Buy now!",
                "snippet": "Special..."
            },
            {
                "message_id": "msg_002",
                "sender": "john@company.com",
                "subject": "Meeting Tomorrow",
                "body": "Can we meet tomorrow?",
                "snippet": "Meeting..."
            }
        ]

        # Mock LLM service
        with patch.object(processor.llm_service, 'classify_email_urgency',
                         return_value='routine'):
            classified = await processor.classify_emails(emails)

        # Promotional email should be filtered
        total_classified = (
            len(classified['urgent']) +
            len(classified['important']) +
            len(classified['routine'])
        )
        assert total_classified == 1  # Only non-promotional email

    async def test_classify_emails_handles_errors_gracefully(self):
        """Test that classification errors default to routine"""
        processor = EmailProcessor()

        emails = [
            {
                "message_id": "msg_001",
                "sender": "test@example.com",
                "subject": "Test",
                "body": "Test body",
                "snippet": "Test..."
            }
        ]

        # Mock LLM to raise error
        with patch.object(processor.llm_service, 'classify_email_urgency',
                         side_effect=Exception("LLM Error")):
            classified = await processor.classify_emails(emails)

        # Should default to routine on error
        assert len(classified['routine']) == 1
        assert classified['routine'][0]['urgency'] == 'routine'

    async def test_classify_emails_all_urgency_levels(self):
        """Test classification across all urgency levels"""
        processor = EmailProcessor()

        emails = [
            {
                "message_id": "msg_urgent",
                "sender": "urgent@example.com",
                "subject": "URGENT Issue",
                "body": "Urgent problem",
                "snippet": "Urgent..."
            },
            {
                "message_id": "msg_important",
                "sender": "important@example.com",
                "subject": "Important Update",
                "body": "Important info",
                "snippet": "Important..."
            },
            {
                "message_id": "msg_routine",
                "sender": "routine@example.com",
                "subject": "Regular Message",
                "body": "Regular content",
                "snippet": "Regular..."
            }
        ]

        # Mock LLM to return different urgencies
        urgency_map = {
            "URGENT Issue": "urgent",
            "Important Update": "important",
            "Regular Message": "routine"
        }

        async def mock_classify(subject, **kwargs):
            return urgency_map.get(subject, "routine")

        with patch.object(processor.llm_service, 'classify_email_urgency',
                         side_effect=mock_classify):
            classified = await processor.classify_emails(emails)

        assert len(classified['urgent']) == 1
        assert len(classified['important']) == 1
        assert len(classified['routine']) == 1


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.slow
class TestEmailProcessorIntegration:
    """Integration tests for email processor (with mocks)"""

    @patch('app.services.email_processor.build')
    async def test_initialize_gmail_success(self, mock_build):
        """Test successful Gmail initialization"""
        mock_service = Mock()
        mock_build.return_value = mock_service

        processor = EmailProcessor()

        # Gmail service should be initialized
        # (This test depends on token file existing in test env)

    async def test_run_sync_wrapper(self):
        """Test async wrapper for sync functions"""
        processor = EmailProcessor()

        def sync_function(x, y):
            return x + y

        result = await processor._run_sync(sync_function, 5, 3)
        assert result == 8

    @patch('app.services.email_processor.build')
    async def test_fetch_unread_emails_no_service(self, mock_build):
        """Test fetching emails when Gmail service not initialized"""
        processor = EmailProcessor()
        processor.gmail_service = None

        emails = await processor.fetch_unread_emails()

        assert emails == []
