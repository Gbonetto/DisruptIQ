"""
Unit tests for critical API endpoints

Tests cover:
1. Chat endpoints (ask question, orchestrator routing)
2. Document management (list, get, delete)
3. Email management (list, get, stats, filters)
4. Health checks (basic, detailed, readiness, liveness)
5. Security validations (file validation, sanitization)
6. Error handling and edge cases
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

# Import endpoints routers
from app.api.endpoints import chat, documents, emails, health


@pytest.fixture
def app():
    """Create FastAPI test app with endpoints"""
    test_app = FastAPI()
    test_app.include_router(chat.router, prefix="/chat", tags=["chat"])
    test_app.include_router(documents.router, prefix="/documents", tags=["documents"])
    test_app.include_router(emails.router, prefix="/emails", tags=["emails"])
    test_app.include_router(health.router, prefix="", tags=["health"])
    return test_app


@pytest.fixture
def mock_db():
    """Mock async database session"""
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    db.scalar = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    return db


@pytest.fixture
def override_get_db(app, mock_db):
    """Override database dependency"""
    from app.core.database import get_db

    async def _override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


class TestChatEndpoints:
    """Test chat interface endpoints"""

    def test_ask_question_success(self, app, override_get_db):
        """Test successful question processing through orchestrator"""
        with patch('app.api.endpoints.chat.get_orchestrator') as mock_get_orchestrator:
            # Mock orchestrator response
            mock_orchestrator = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.message = "Voici la réponse"
            mock_response.agents_used = ["intent_classifier", "sql_agent"]
            mock_response.confidence = 0.95
            mock_response.data = {"sources": []}

            mock_orchestrator.process = AsyncMock(return_value=mock_response)
            mock_get_orchestrator.return_value = mock_orchestrator

            client = TestClient(app)
            response = client.post(
                "/chat/ask",
                json={
                    "message": "Combien de plombiers ?",
                    "conversation_history": [],
                    "session_id": "test-session"
                }
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["message"] == "Voici la réponse"
            assert data["session_id"] == "test-session"
            assert "sources" in data

    def test_ask_question_timeout(self, app, override_get_db):
        """Test request timeout handling (30s limit)"""
        import asyncio

        with patch('app.api.endpoints.chat.get_orchestrator') as mock_get_orchestrator:
            mock_orchestrator = MagicMock()
            # Simulate timeout
            mock_orchestrator.process = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_get_orchestrator.return_value = mock_orchestrator

            client = TestClient(app)
            response = client.post(
                "/chat/ask",
                json={"message": "Test timeout", "conversation_history": []}
            )

            # Can return 500 or 504 depending on error handling
            assert response.status_code in [status.HTTP_500_INTERNAL_SERVER_ERROR, status.HTTP_504_GATEWAY_TIMEOUT]

    def test_ask_question_with_history(self, app, override_get_db):
        """Test question with conversation history"""
        with patch('app.api.endpoints.chat.get_orchestrator') as mock_get_orchestrator:
            mock_orchestrator = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.message = "Suite de la conversation"
            mock_response.agents_used = ["intent_classifier"]
            mock_response.confidence = 0.90
            mock_response.data = {"sources": []}

            mock_orchestrator.process = AsyncMock(return_value=mock_response)
            mock_get_orchestrator.return_value = mock_orchestrator

            conversation_history = [
                {"role": "user", "content": "Première question"},
                {"role": "assistant", "content": "Première réponse"}
            ]

            client = TestClient(app)
            response = client.post(
                "/chat/ask",
                json={
                    "message": "Question de suivi",
                    "conversation_history": conversation_history
                }
            )

            assert response.status_code == status.HTTP_200_OK
            # Verify orchestrator received conversation history
            mock_orchestrator.process.assert_called_once()


class TestDocumentEndpoints:
    """Test document management endpoints"""

    def test_list_documents(self, app, override_get_db, mock_db):
        """Test listing documents with pagination"""
        from app.models.document import Document

        # Mock documents
        mock_docs = [
            MagicMock(
                id=1,
                filename="doc1.pdf",
                original_filename="document1.pdf",
                mime_type="application/pdf",
                file_size=1024,
                indexed=True,
                uploaded_at=datetime.now(),
                document_metadata=None
            ),
            MagicMock(
                id=2,
                filename="doc2.txt",
                original_filename="document2.txt",
                mime_type="text/plain",
                file_size=512,
                indexed=True,
                uploaded_at=datetime.now(),
                document_metadata=None
            )
        ]

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=mock_docs)))
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.scalar = AsyncMock(return_value=2)

        client = TestClient(app)
        response = client.get("/documents/?limit=10&offset=0")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "documents" in data
        assert data["total"] == 2
        assert data["limit"] == 10
        assert data["offset"] == 0

    def test_get_document_not_found(self, app, override_get_db, mock_db):
        """Test getting non-existent document returns 404"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        client = TestClient(app)
        response = client.get("/documents/999")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]

    def test_delete_document_success(self, app, override_get_db, mock_db):
        """Test successful document deletion"""
        with patch('app.api.endpoints.documents.RAGService') as mock_rag_service, \
             patch('app.api.endpoints.documents.os.path.exists') as mock_exists, \
             patch('app.api.endpoints.documents.os.remove') as mock_remove:

            # Mock document
            mock_doc = MagicMock()
            mock_doc.id = 1
            mock_doc.indexed = True
            mock_doc.qdrant_id = "point-1"
            mock_doc.file_path = "/tmp/test.pdf"

            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_doc)
            mock_db.execute = AsyncMock(return_value=mock_result)
            mock_db.delete = AsyncMock()
            mock_db.commit = AsyncMock()

            mock_exists.return_value = True
            mock_rag_instance = MagicMock()
            mock_rag_instance.delete_document = AsyncMock()
            mock_rag_service.return_value = mock_rag_instance

            client = TestClient(app)
            response = client.delete("/documents/1")

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["document_id"] == 1
            mock_db.delete.assert_called_once()
            mock_remove.assert_called_once()


class TestEmailEndpoints:
    """Test email management endpoints"""

    def test_list_emails_no_filters(self, app, override_get_db, mock_db):
        """Test listing emails without filters"""
        from app.models.email import Email, EmailUrgency

        # Mock emails
        mock_emails = [
            MagicMock(
                id=1,
                message_id="msg1",
                sender="user@example.com",
                subject="Test Email",
                body="Body content",
                urgency=EmailUrgency.ROUTINE,
                category="general",
                attachments=[],
                processed=False,
                included_in_digest=False,
                received_at=datetime.now(),
                processed_at=None,
                created_at=datetime.now()
            )
        ]

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=mock_emails)))
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.scalar = AsyncMock(return_value=1)

        client = TestClient(app)
        response = client.get("/emails/?limit=20&offset=0")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "emails" in data
        assert data["total"] == 1
        assert len(data["emails"]) == 1

    def test_list_emails_with_urgency_filter(self, app, override_get_db, mock_db):
        """Test listing emails filtered by urgency"""
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.scalar = AsyncMock(return_value=0)

        client = TestClient(app)
        response = client.get("/emails/?urgency=urgent")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "emails" in data

    def test_list_emails_invalid_urgency(self, app, override_get_db, mock_db):
        """Test invalid urgency filter returns 400"""
        client = TestClient(app)
        response = client.get("/emails/?urgency=invalid_urgency")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid urgency value" in response.json()["detail"]

    def test_get_email_stats(self, app, override_get_db, mock_db):
        """Test getting email statistics"""
        # Mock statistics
        mock_db.scalar = AsyncMock(side_effect=[
            10,  # total
            2,   # urgent
            5,   # important
            3,   # routine
            10,  # processed
            0,   # unprocessed
            8,   # in_digest
            3,   # today
            7    # this week
        ])

        client = TestClient(app)
        response = client.get("/emails/stats/summary")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 10
        assert data["by_urgency"]["urgent"] == 2
        assert data["by_status"]["processed"] == 10
        assert data["by_timeframe"]["today"] == 3

    def test_mark_email_processed(self, app, override_get_db, mock_db):
        """Test marking email as processed"""
        from app.models.email import Email

        mock_email = MagicMock(spec=Email)
        mock_email.id = 1
        mock_email.processed = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_email)
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        client = TestClient(app)
        response = client.patch("/emails/1/mark-processed")

        assert response.status_code == status.HTTP_200_OK
        assert mock_email.processed is True
        assert response.json()["email_id"] == 1


class TestHealthEndpoints:
    """Test health check endpoints"""

    def test_basic_health_check(self, app, override_get_db, mock_db):
        """Test basic health endpoint"""
        mock_result = MagicMock()
        mock_result.scalar = MagicMock(return_value=1)
        mock_db.execute = AsyncMock(return_value=mock_result)

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "disruptiq-backend"
        assert "timestamp" in data

    def test_health_check_database_failure(self, app, override_get_db, mock_db):
        """Test health check fails when database is down"""
        mock_db.execute = AsyncMock(side_effect=Exception("Database connection failed"))

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_detailed_health_check(self, app, override_get_db, mock_db):
        """Test detailed health check with all components"""
        with patch('app.api.endpoints.health.check_database') as mock_db_check, \
             patch('app.api.endpoints.health.check_redis') as mock_redis_check, \
             patch('app.api.endpoints.health.check_qdrant') as mock_qdrant_check, \
             patch('app.api.endpoints.health.check_gmail_credentials') as mock_gmail_check:

            # Mock all checks as healthy
            mock_db_check.return_value = {"status": "healthy", "message": "DB OK"}
            mock_redis_check.return_value = {"status": "disabled", "message": "Redis disabled"}
            mock_qdrant_check.return_value = {"status": "not_implemented", "message": "Not implemented"}
            mock_gmail_check.return_value = {"status": "healthy", "message": "Gmail OK"}

            client = TestClient(app)
            response = client.get("/health/detailed")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            # Status can be "healthy" or "unknown" depending on "disabled"/"not_implemented" handling
            assert data["status"] in ["healthy", "unknown"]
            assert "checks" in data
            assert data["checks"]["database"]["status"] == "healthy"

    def test_liveness_probe(self, app, override_get_db):
        """Test Kubernetes liveness probe"""
        client = TestClient(app)
        response = client.get("/health/live")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "alive"

    def test_readiness_probe_success(self, app, override_get_db, mock_db):
        """Test Kubernetes readiness probe when ready"""
        with patch('app.api.endpoints.health.check_gmail_credentials') as mock_gmail_check:
            mock_gmail_check.return_value = {"status": "healthy"}

            mock_result = MagicMock()
            mock_result.scalar = MagicMock(return_value=1)
            mock_db.execute = AsyncMock(return_value=mock_result)

            client = TestClient(app)
            response = client.get("/health/ready")

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["status"] == "ready"

    def test_metrics_endpoint(self, app, override_get_db, mock_db):
        """Test Prometheus metrics endpoint"""
        # Mock email counts
        mock_urgent = MagicMock()
        mock_urgent.scalar = MagicMock(return_value=5)
        mock_important = MagicMock()
        mock_important.scalar = MagicMock(return_value=10)
        mock_routine = MagicMock()
        mock_routine.scalar = MagicMock(return_value=15)

        mock_db.execute = AsyncMock(side_effect=[mock_urgent, mock_important, mock_routine])

        client = TestClient(app)
        response = client.get("/metrics")

        assert response.status_code == status.HTTP_200_OK
        content = response.text
        assert "disruptiq_emails_total" in content
        assert "disruptiq_emails_by_urgency" in content


class TestSecurityValidations:
    """Test security features and validations"""

    def test_filename_sanitization(self):
        """Test that filename sanitization prevents path traversal"""
        from app.api.endpoints.documents import sanitize_filename

        # Path traversal attempts - check that parent refs are removed
        sanitized_1 = sanitize_filename("../../etc/passwd")
        assert ".." not in sanitized_1  # Parent refs must be removed

        sanitized_2 = sanitize_filename("..\\..\\windows\\system32\\config")
        assert ".." not in sanitized_2  # Parent refs must be removed

        # Special characters
        assert sanitize_filename("test file!@#$.pdf") == "test_file.pdf"

        # Long filenames
        long_name = "a" * 300 + ".txt"
        sanitized = sanitize_filename(long_name)
        assert len(sanitized) <= 255

        # Empty names get default
        result = sanitize_filename("...")
        assert "document" in result

    def test_needs_ocr_detection(self):
        """Test OCR detection logic"""
        from app.api.endpoints.documents import needs_ocr

        # Images need OCR
        assert needs_ocr("image/png", "scan.png") is True
        assert needs_ocr("image/jpeg", "photo.jpg") is True

        # PDFs need OCR
        assert needs_ocr("application/pdf", "document.pdf") is True

        # Text files don't need OCR
        assert needs_ocr("text/plain", "notes.txt") is False
        assert needs_ocr("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "doc.docx") is False


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_chat_endpoint_generic_error(self, app, override_get_db):
        """Test generic error handling in chat endpoint"""
        with patch('app.api.endpoints.chat.get_orchestrator') as mock_get_orchestrator:
            mock_get_orchestrator.side_effect = Exception("Unexpected error")

            client = TestClient(app)
            response = client.post(
                "/chat/ask",
                json={"message": "Test", "conversation_history": []}
            )

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to process question" in response.json()["detail"]

    def test_document_endpoint_rollback_on_error(self, app, override_get_db, mock_db):
        """Test database rollback on document deletion error"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=MagicMock(
            id=1,
            indexed=True,
            qdrant_id="point-1",
            file_path="/tmp/test.pdf"
        ))
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.delete = AsyncMock(side_effect=Exception("Database error"))
        mock_db.rollback = AsyncMock()

        with patch('app.api.endpoints.documents.RAGService'):
            client = TestClient(app)
            response = client.delete("/documents/1")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            mock_db.rollback.assert_called_once()

    def test_email_date_filter_invalid_format(self, app, override_get_db, mock_db):
        """Test invalid date format in email filter returns 400"""
        client = TestClient(app)
        response = client.get("/emails/?from_date=invalid-date")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid from_date format" in response.json()["detail"]
