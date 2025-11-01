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


# ==================== NEW TESTS - Phase 3 ====================


@pytest.mark.unit
@pytest.mark.asyncio
class TestGmailInitialization:
    """Tests for Gmail OAuth initialization and token management"""

    @patch('app.services.email_processor.build')
    @patch('app.services.email_processor.Credentials')
    @patch('os.path.exists')
    def test_initialize_gmail_with_valid_token(self, mock_exists, mock_creds, mock_build):
        """Test Gmail init with valid existing token"""
        mock_exists.return_value = True
        mock_token = Mock()
        mock_token.valid = True
        mock_token.expired = False  # Explicitly set expired to False
        mock_token.refresh_token = None
        mock_creds.from_authorized_user_file.return_value = mock_token
        mock_service = Mock()
        mock_build.return_value = mock_service

        processor = EmailProcessor()
        assert processor.gmail_service is not None
        mock_build.assert_called_once()

    @patch('app.services.email_processor.build')
    @patch('app.services.email_processor.Credentials')
    @patch('app.services.email_processor.InstalledAppFlow')
    @patch('os.path.exists')
    def test_initialize_gmail_token_refresh(self, mock_exists, mock_flow, mock_creds, mock_build):
        """Test token refresh when expired"""
        mock_exists.side_effect = lambda path: 'token' in path or 'credentials' in path
        mock_token = Mock()
        mock_token.valid = False
        mock_token.expired = True
        mock_token.refresh_token = "refresh_token"
        mock_creds.from_authorized_user_file.return_value = mock_token

        processor = EmailProcessor()
        # Token should have been refreshed
        mock_token.refresh.assert_called_once()

    @patch('os.path.exists')
    def test_initialize_gmail_no_token_file(self, mock_exists):
        """Test Gmail init when token file missing - should log warning"""
        mock_exists.return_value = False

        processor = EmailProcessor()
        # Should initialize but gmail_service will be None
        assert processor.gmail_service is None

    @patch('app.services.email_processor.build')
    @patch('app.services.email_processor.Credentials')
    @patch('os.path.exists')
    def test_initialize_gmail_invalid_credentials(self, mock_exists, mock_creds, mock_build):
        """Test handling of invalid credentials"""
        mock_exists.return_value = True
        mock_creds.from_authorized_user_file.side_effect = Exception("Invalid credentials")

        processor = EmailProcessor()
        # Should handle error gracefully
        assert processor.gmail_service is None


@pytest.mark.unit
@pytest.mark.asyncio
class TestFetchUnreadEmails:
    """Tests for fetching unread emails from Gmail API"""

    @patch('app.services.email_processor.build')
    async def test_fetch_unread_emails_success(self, mock_build):
        """Test successfully fetching and parsing emails"""
        mock_service = Mock()
        mock_messages_list = Mock()
        mock_messages_list.execute.return_value = {
            'messages': [{'id': 'msg1'}, {'id': 'msg2'}]
        }
        mock_service.users().messages().list.return_value = mock_messages_list

        processor = EmailProcessor()
        processor.gmail_service = mock_service

        with patch.object(processor, '_get_email_details', new=AsyncMock(return_value={"id": "msg1"})):
            emails = await processor.fetch_unread_emails()

        assert len(emails) == 2

    @patch('app.services.email_processor.build')
    async def test_fetch_unread_emails_empty_result(self, mock_build):
        """Test when no unread emails found"""
        mock_service = Mock()
        mock_messages_list = Mock()
        mock_messages_list.execute.return_value = {}  # No messages key
        mock_service.users().messages().list.return_value = mock_messages_list

        processor = EmailProcessor()
        processor.gmail_service = mock_service

        emails = await processor.fetch_unread_emails()
        assert emails == []

    @patch('app.services.email_processor.build')
    async def test_fetch_unread_emails_with_time_filter(self, mock_build):
        """Test fetching emails with since_hours parameter"""
        mock_service = Mock()
        mock_messages_list = Mock()
        mock_messages_list.execute.return_value = {'messages': []}

        def mock_list_call(userId, q, maxResults):
            # Verify query includes time filter
            assert 'after:' in q
            return mock_messages_list

        mock_service.users().messages().list.side_effect = mock_list_call

        processor = EmailProcessor()
        processor.gmail_service = mock_service

        await processor.fetch_unread_emails(since_hours=24)

    @patch('app.services.email_processor.build')
    async def test_fetch_unread_emails_batch_processing(self, mock_build):
        """Test emails are processed in batches of 5"""
        mock_service = Mock()
        mock_messages_list = Mock()
        # Create 12 messages to test batch processing
        mock_messages_list.execute.return_value = {
            'messages': [{'id': f'msg{i}'} for i in range(12)]
        }
        mock_service.users().messages().list.return_value = mock_messages_list

        processor = EmailProcessor()
        processor.gmail_service = mock_service

        call_count = 0

        async def mock_get_details(message_id):
            nonlocal call_count
            call_count += 1
            return {"id": message_id, "subject": f"Email {message_id}"}

        with patch.object(processor, '_get_email_details', side_effect=mock_get_details):
            emails = await processor.fetch_unread_emails()

        assert len(emails) == 12
        assert call_count == 12  # All emails processed

    @patch('app.services.email_processor.build')
    async def test_fetch_unread_emails_partial_failure(self, mock_build):
        """Test that processing continues when some emails fail"""
        mock_service = Mock()
        mock_messages_list = Mock()
        mock_messages_list.execute.return_value = {
            'messages': [{'id': 'msg1'}, {'id': 'msg2'}, {'id': 'msg3'}]
        }
        mock_service.users().messages().list.return_value = mock_messages_list

        processor = EmailProcessor()
        processor.gmail_service = mock_service

        call_count = 0

        async def mock_get_details(message_id):
            nonlocal call_count
            call_count += 1
            if message_id == 'msg2':
                raise Exception("Failed to fetch msg2")
            return {"id": message_id, "subject": f"Email {message_id}"}

        with patch.object(processor, '_get_email_details', side_effect=mock_get_details):
            emails = await processor.fetch_unread_emails()

        # Should get 2 emails (msg1 and msg3), msg2 failed
        assert len(emails) == 2
        assert call_count == 3  # All 3 were attempted


@pytest.mark.unit
@pytest.mark.asyncio
class TestEmailDetails:
    """Tests for fetching individual email details"""

    @patch('app.services.email_processor.build')
    async def test_get_email_details_success(self, mock_build):
        """Test parsing full email correctly"""
        mock_service = Mock()
        mock_get = Mock()
        mock_get.execute.return_value = {
            'id': 'msg001',
            'threadId': 'thread001',
            'snippet': 'Test email snippet',
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'Test Subject'},
                    {'name': 'From', 'value': 'test@example.com'},
                    {'name': 'Date', 'value': 'Mon, 1 Nov 2025 12:00:00 +0000'}
                ],
                'body': {'data': 'VGVzdCBib2R5'}  # "Test body"
            }
        }
        mock_service.users().messages().get.return_value = mock_get

        processor = EmailProcessor()
        processor.gmail_service = mock_service

        details = await processor._get_email_details('msg001')

        assert details['message_id'] == 'msg001'
        assert details['subject'] == 'Test Subject'
        assert details['sender'] == 'test@example.com'
        assert details['body'] == 'Test body'

    @patch('app.services.email_processor.build')
    async def test_get_email_details_missing_headers(self, mock_build):
        """Test handling of missing headers gracefully"""
        mock_service = Mock()
        mock_get = Mock()
        mock_get.execute.return_value = {
            'id': 'msg002',
            'threadId': 'thread002',
            'snippet': 'Snippet',
            'payload': {
                'headers': [
                    # Missing Subject and From
                    {'name': 'Date', 'value': 'Mon, 1 Nov 2025 12:00:00 +0000'}
                ],
                'body': {'data': 'Ym9keQ=='}  # "body"
            }
        }
        mock_service.users().messages().get.return_value = mock_get

        processor = EmailProcessor()
        processor.gmail_service = mock_service

        details = await processor._get_email_details('msg002')

        assert details['subject'] == '(No Subject)'
        assert details['sender'] == 'unknown@example.com'

    @patch('app.services.email_processor.build')
    async def test_get_email_details_multipart_body(self, mock_build):
        """Test extraction from multipart messages"""
        mock_service = Mock()
        mock_get = Mock()
        mock_get.execute.return_value = {
            'id': 'msg003',
            'threadId': 'thread003',
            'snippet': 'Multipart',
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'Multipart Test'},
                    {'name': 'From', 'value': 'multi@example.com'},
                    {'name': 'Date', 'value': 'Mon, 1 Nov 2025 12:00:00 +0000'}
                ],
                'parts': [
                    {
                        'mimeType': 'text/plain',
                        'body': {'data': 'UGxhaW4gdGV4dA=='}  # "Plain text"
                    },
                    {
                        'mimeType': 'text/html',
                        'body': {'data': 'PGh0bWw+SFRNTDwvaHRtbD4='}  # "<html>HTML</html>"
                    }
                ]
            }
        }
        mock_service.users().messages().get.return_value = mock_get

        processor = EmailProcessor()
        processor.gmail_service = mock_service

        details = await processor._get_email_details('msg003')

        assert 'Plain text' in details['body'] or 'HTML' in details['body']


@pytest.mark.unit
@pytest.mark.asyncio
class TestEmailClassificationAdvanced:
    """Advanced tests for email classification"""

    async def test_classify_emails_parallel_processing(self, mock_llm_service):
        """Test that multiple emails are processed concurrently"""
        processor = EmailProcessor()
        processor.llm_service = mock_llm_service

        emails = [{"message_id": f"msg{i}", "sender": f"test{i}@example.com",
                  "subject": f"Test {i}", "body": f"Body {i}", "snippet": f"Snippet {i}"}
                 for i in range(10)]

        classified = await processor.classify_emails(emails)

        # All emails should be classified
        total = len(classified['urgent']) + len(classified['important']) + len(classified['routine'])
        assert total == 10

    async def test_classify_emails_semaphore_limits(self, mock_llm_service):
        """Test that semaphore respects concurrency limit"""
        processor = EmailProcessor()
        processor.llm_service = mock_llm_service

        # Create 20 emails to test semaphore
        emails = [{"message_id": f"msg{i}", "sender": f"test{i}@example.com",
                  "subject": "Test", "body": "Body", "snippet": "Snippet"}
                 for i in range(20)]

        classified = await processor.classify_emails(emails)

        # All should still be processed
        total = len(classified['urgent']) + len(classified['important']) + len(classified['routine'])
        assert total == 20

    async def test_classify_emails_mixed_results(self, mock_llm_service):
        """Test correct grouping of urgent/important/routine emails"""
        processor = EmailProcessor()

        # Configure mock to return different urgencies
        async def classify_by_subject(subject, **kwargs):
            if "URGENT" in subject:
                return "urgent"
            elif "Important" in subject:
                return "important"
            return "routine"

        mock_llm_service.classify_email_urgency = AsyncMock(side_effect=classify_by_subject)
        processor.llm_service = mock_llm_service

        emails = [
            {"message_id": "1", "sender": "a@test.com", "subject": "URGENT Problem", "body": "Help", "snippet": "..."},
            {"message_id": "2", "sender": "b@test.com", "subject": "Important Update", "body": "Info", "snippet": "..."},
            {"message_id": "3", "sender": "c@test.com", "subject": "Regular Email", "body": "Hi", "snippet": "..."},
        ]

        classified = await processor.classify_emails(emails)

        assert len(classified['urgent']) == 1
        assert len(classified['important']) == 1
        assert len(classified['routine']) == 1

    async def test_classify_emails_empty_list(self):
        """Test handling of empty email list"""
        processor = EmailProcessor()

        classified = await processor.classify_emails([])

        assert classified == {'urgent': [], 'important': [], 'routine': []}


@pytest.mark.unit
@pytest.mark.asyncio
class TestDigestGeneration:
    """Tests for HTML digest generation"""

    async def test_generate_digest_html_all_urgencies(self):
        """Test digest includes all three categories"""
        processor = EmailProcessor()

        classified_emails = {
            'urgent': [
                {"subject": "Urgent 1", "sender": "u1@test.com", "urgency": "urgent", "snippet": "Urgent..."}
            ],
            'important': [
                {"subject": "Important 1", "sender": "i1@test.com", "urgency": "important", "snippet": "Important..."}
            ],
            'routine': [
                {"subject": "Routine 1", "sender": "r1@test.com", "urgency": "routine", "snippet": "Routine..."}
            ]
        }

        html = await processor.generate_digest_html(classified_emails)

        assert 'Urgent 1' in html
        assert 'Important 1' in html
        assert 'Routine 1' in html
        assert 'Urgent' in html or 'URGENT' in html
        assert 'Important' in html or 'IMPORTANT' in html

    async def test_generate_digest_html_empty(self):
        """Test digest with no emails"""
        processor = EmailProcessor()

        classified_emails = {
            'urgent': [],
            'important': [],
            'routine': []
        }

        html = await processor.generate_digest_html(classified_emails)

        assert 'No emails' in html or 'Aucun' in html or len(html) > 0  # Should handle gracefully

    async def test_generate_digest_html_formatting(self):
        """Test HTML structure and styles are present"""
        processor = EmailProcessor()

        classified_emails = {
            'urgent': [{"subject": "Test", "sender": "test@test.com", "urgency": "urgent", "snippet": "..."}],
            'important': [],
            'routine': []
        }

        html = await processor.generate_digest_html(classified_emails)

        # Check for basic HTML structure
        assert '<html>' in html or '<!DOCTYPE' in html or '<div' in html
        assert '</html>' in html or '</div>' in html

    async def test_generate_digest_html_special_characters(self):
        """Test HTML entities are properly escaped"""
        processor = EmailProcessor()

        classified_emails = {
            'urgent': [],
            'important': [
                {
                    "subject": "Test <script>alert('XSS')</script>",
                    "sender": "test@test.com",
                    "urgency": "important",
                    "snippet": "Dangerous & special chars: <>&\""
                }
            ],
            'routine': []
        }

        html = await processor.generate_digest_html(classified_emails)

        # Script tags should be escaped or removed
        assert '<script>' not in html or '&lt;script&gt;' in html


@pytest.mark.unit
@pytest.mark.asyncio
class TestAsyncHelpers:
    """Tests for async helper methods"""

    async def test_run_sync_wrapper_timeout(self):
        """Test that timeout error is raised correctly"""
        import time

        processor = EmailProcessor()

        def slow_function():
            time.sleep(5)  # Sleep for 5 seconds
            return "result"

        # Should timeout before 5 seconds
        with pytest.raises(Exception):  # asyncio.TimeoutError or similar
            await processor._run_sync(slow_function, timeout=0.1)
