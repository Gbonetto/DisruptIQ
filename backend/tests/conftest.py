"""
Pytest Configuration and Shared Fixtures
Provides common test fixtures for database, async client, authentication, etc.
"""

import asyncio
import os
from typing import AsyncGenerator, Generator
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
import pytest_asyncio
from faker import Faker
from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.core.config import settings
from app.models.email import Email, EmailUrgency
from app.models.professionnel import Professionnel


# Test database URL (in-memory SQLite for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TEST_SYNC_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """
    Create an event loop for the entire test session.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """
    Create async engine for tests with in-memory SQLite.
    Each test gets a fresh database.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,  # Set to True for SQL debugging
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create async database session for tests.
    Automatically rolls back after each test.
    """
    async_session_maker = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(async_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Create async HTTP client for testing API endpoints.
    Overrides the database dependency with test database.
    """
    async def override_get_db():
        yield async_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ==================== Test Data Fixtures ====================


@pytest.fixture
def sample_email_data() -> dict:
    """Sample email data for testing"""
    return {
        "message_id": "test_msg_001",
        "thread_id": "test_thread_001",
        "sender": "test@example.com",
        "subject": "Test Email Subject",
        "body": "This is a test email body.",
        "snippet": "This is a test...",
        "received_at": datetime.now(),
        "attachments": []
    }


@pytest.fixture
def sample_urgent_email_data() -> dict:
    """Sample urgent email data"""
    return {
        "message_id": "urgent_msg_001",
        "thread_id": "urgent_thread_001",
        "sender": "emergency@example.com",
        "subject": "URGENT: Server Down",
        "body": "The production server is down. Immediate action required.",
        "snippet": "URGENT: Server Down...",
        "received_at": datetime.now(),
        "attachments": []
    }


@pytest.fixture
def sample_promotional_email_data() -> dict:
    """Sample promotional email data (should be filtered)"""
    return {
        "message_id": "promo_msg_001",
        "thread_id": "promo_thread_001",
        "sender": "noreply@marketing.com",
        "subject": "Special Offer: 50% Off!",
        "body": "Get 50% off on all products. Limited time offer!",
        "snippet": "Special Offer...",
        "received_at": datetime.now(),
        "attachments": []
    }


@pytest.fixture
def sample_vendor_data() -> dict:
    """Sample professional/vendor data for testing"""
    return {
        "name": "Test Professional",
        "company_name": "Test Company",
        "email": "contact@testvendor.com",
        "phone": "+1-555-0123",
        "address": "123 Test Street",
        "city": "Paris",
        "postal_code": "75001",
        "category": "plombier",
        "description": "A test professional for unit testing",
        "statut": "active",
    }


@pytest_asyncio.fixture
async def create_test_email(async_session: AsyncSession):
    """
    Factory fixture to create test emails in database
    """
    async def _create_email(**kwargs) -> Email:
        defaults = {
            "message_id": f"test_msg_{datetime.now().timestamp()}",
            "thread_id": f"test_thread_{datetime.now().timestamp()}",
            "sender": "test@example.com",
            "subject": "Test Email",
            "body": "Test body",
            "urgency": EmailUrgency.ROUTINE,
            "received_at": datetime.now(),
            "processed": True,
        }
        defaults.update(kwargs)

        email = Email(**defaults)
        async_session.add(email)
        await async_session.commit()
        await async_session.refresh(email)
        return email

    return _create_email


@pytest_asyncio.fixture
async def create_test_vendor(async_session: AsyncSession):
    """
    Factory fixture to create test professionals/vendors in database
    """
    async def _create_vendor(**kwargs) -> Professionnel:
        defaults = {
            "name": f"Test Professional {datetime.now().timestamp()}",
            "email": f"vendor_{datetime.now().timestamp()}@test.com",
            "category": "plombier",
            "statut": "active",
        }
        defaults.update(kwargs)

        vendor = Professionnel(**defaults)
        async_session.add(vendor)
        await async_session.commit()
        await async_session.refresh(vendor)
        return vendor

    return _create_vendor


# ==================== Mock Fixtures ====================


@pytest.fixture
def mock_gmail_service(monkeypatch):
    """
    Mock Gmail API service for testing without real API calls
    """
    class MockGmailService:
        def __init__(self):
            self.messages_list_called = False
            self.messages_get_called = False

        def users(self):
            return self

        def messages(self):
            return self

        def list(self, userId, q, maxResults):
            self.messages_list_called = True
            return self

        def execute(self):
            if self.messages_list_called:
                return {
                    "messages": [
                        {"id": "msg_001"},
                        {"id": "msg_002"},
                    ]
                }
            elif self.messages_get_called:
                return {
                    "id": "msg_001",
                    "threadId": "thread_001",
                    "snippet": "Test email snippet",
                    "payload": {
                        "headers": [
                            {"name": "Subject", "value": "Test Subject"},
                            {"name": "From", "value": "test@example.com"},
                            {"name": "Date", "value": "Mon, 1 Nov 2025 12:00:00 +0000"},
                        ],
                        "body": {"data": "VGVzdCBib2R5"}  # Base64: "Test body"
                    }
                }
            return {}

        def get(self, userId, id, format):
            self.messages_get_called = True
            return self

    return MockGmailService()


@pytest.fixture
def mock_openai_client(monkeypatch):
    """
    Mock OpenAI client for testing LLM classification without API calls
    """
    class MockOpenAIResponse:
        def __init__(self, urgency="routine"):
            self.urgency = urgency

        @property
        def choices(self):
            class Choice:
                class Message:
                    content = self.urgency
                message = Message()
            return [Choice()]

    class MockOpenAIClient:
        def __init__(self):
            self.chat = self
            self.completions = self

        def create(self, **kwargs):
            # Extract urgency from message content if available
            messages = kwargs.get("messages", [])
            content = messages[-1].get("content", "") if messages else ""

            # Simple heuristic for testing
            if "urgent" in content.lower() or "emergency" in content.lower():
                return MockOpenAIResponse("urgent")
            elif "important" in content.lower():
                return MockOpenAIResponse("important")
            else:
                return MockOpenAIResponse("routine")

    return MockOpenAIClient()


# ==================== Environment Fixtures ====================


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """
    Setup test environment variables.
    Automatically applied to all tests.
    """
    test_env = {
        "ENVIRONMENT": "test",
        "DATABASE_URL": TEST_DATABASE_URL,
        "OPENAI_API_KEY": "test_openai_key",
        "ANTHROPIC_API_KEY": "test_anthropic_key",
        "SECRET_KEY": "test_secret_key_minimum_32_characters_long",
        "GMAIL_CREDENTIALS_PATH": "./tests/fixtures/gmail_credentials.json",
        "GMAIL_TOKEN_PATH": "./tests/fixtures/gmail_token.json",
    }

    for key, value in test_env.items():
        monkeypatch.setenv(key, value)


# ==================== Enhanced Test Fixtures (Phase 4) ====================


@pytest.fixture
def mock_llm_service():
    """
    Mock LLM service with configurable responses for different test scenarios.
    Returns a mock that can be configured to return specific responses.
    """
    mock = AsyncMock()

    # Default email classification response
    async def default_classify_email(subject: str, body: str, sender: str = ""):
        if "urgent" in subject.lower() or "emergency" in body.lower():
            return "urgent"
        elif "important" in subject.lower():
            return "important"
        return "routine"

    # Default email generation response
    async def default_generate_email(prompt: str, context: dict = None):
        return {
            "subject": "Test Generated Email",
            "body": f"This is a test email generated for: {prompt}",
            "confidence": 0.95
        }

    # Default document extraction response
    async def default_extract_document_info(text: str):
        return {
            "type": "document",
            "summary": "Test document summary",
            "entities": []
        }

    # Default Q&A response
    async def default_answer_question(question: str, context: str = "", history: list = None):
        if not context:
            return "I don't have enough context to answer this question."
        return f"Answer based on context: {context[:50]}..."

    # Configure mock methods
    mock.classify_email_urgency = AsyncMock(side_effect=default_classify_email)
    mock.generate_email = AsyncMock(side_effect=default_generate_email)
    mock.extract_document_info = AsyncMock(side_effect=default_extract_document_info)
    mock.answer_question = AsyncMock(side_effect=default_answer_question)
    mock.get_embeddings = AsyncMock(return_value=[[0.1] * 1536])  # Mock 1536-dim embedding

    # Mock chat model for direct LLM calls
    mock.chat_model = AsyncMock()
    mock.chat_model.ainvoke = AsyncMock()

    return mock


@pytest_asyncio.fixture
async def sql_test_db(async_session: AsyncSession):
    """
    Populate test database with DisruptIQ schema tables and sample data.
    Creates the necessary tables for SQL agent testing.
    """
    # Create professionnels table
    await async_session.execute(text("""
        CREATE TABLE IF NOT EXISTS professionnels (
            id INTEGER PRIMARY KEY,
            name VARCHAR(255),
            company_name VARCHAR(255),
            email VARCHAR(255) UNIQUE,
            phone VARCHAR(50),
            siret VARCHAR(14),
            description TEXT,
            statut VARCHAR(20) DEFAULT 'active',
            category VARCHAR(100),
            address TEXT,
            city VARCHAR(100),
            postal_code VARCHAR(10),
            rating REAL,
            total_jobs INTEGER DEFAULT 0,
            is_indexed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))

    # Create coproprietes table
    await async_session.execute(text("""
        CREATE TABLE IF NOT EXISTS coproprietes (
            id INTEGER PRIMARY KEY,
            nom VARCHAR(255),
            adresse TEXT,
            ville VARCHAR(100),
            code_postal VARCHAR(10),
            nombre_lots INTEGER,
            nombre_batiments INTEGER,
            annee_construction INTEGER,
            syndic VARCHAR(255),
            type_copropriete VARCHAR(50),
            surface_totale REAL,
            is_indexed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))

    # Create coproprietaires table
    await async_session.execute(text("""
        CREATE TABLE IF NOT EXISTS coproprietaires (
            id INTEGER PRIMARY KEY,
            nom VARCHAR(255),
            prenom VARCHAR(255),
            email VARCHAR(255),
            telephone VARCHAR(50),
            telephone_mobile VARCHAR(50),
            copropriete_id INTEGER,
            numero_lot VARCHAR(50),
            type_lot VARCHAR(50),
            etage INTEGER,
            surface REAL,
            statut VARCHAR(50),
            statut_special VARCHAR(50),
            est_resident BOOLEAN DEFAULT TRUE,
            tantiemes INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (copropriete_id) REFERENCES coproprietes(id)
        )
    """))

    # Insert sample data for testing
    await async_session.execute(text("""
        INSERT INTO professionnels (name, company_name, email, category, city, postal_code, is_indexed)
        VALUES
            ('Jean Plombier', 'Plomberie Jean', 'jean@plomberie.fr', 'plombier', 'Paris', '75013', TRUE),
            ('Marie Électricienne', 'Électricité Marie', 'marie@elec.fr', 'électricien', 'Paris', '75014', TRUE),
            ('Pierre Peintre', 'Peinture Pierre', 'pierre@peinture.fr', 'peintre', 'Lyon', '69001', FALSE)
    """))

    await async_session.execute(text("""
        INSERT INTO coproprietes (nom, adresse, ville, code_postal, nombre_lots, type_copropriete, is_indexed)
        VALUES
            ('Les Mimosas', '10 Rue des Fleurs', 'Paris', '75013', 50, 'résidentiel', TRUE),
            ('Résidence du Parc', '25 Avenue Verte', 'Lyon', '69001', 30, 'résidentiel', TRUE)
    """))

    await async_session.execute(text("""
        INSERT INTO coproprietaires (nom, prenom, email, copropriete_id, numero_lot, statut, est_resident)
        VALUES
            ('Dupont', 'Jacques', 'j.dupont@email.fr', 1, 'A12', 'propriétaire', TRUE),
            ('Martin', 'Sophie', 's.martin@email.fr', 1, 'B34', 'propriétaire', FALSE),
            ('Bernard', 'Luc', 'l.bernard@email.fr', 2, '101', 'locataire', TRUE)
    """))

    await async_session.commit()
    return async_session


@pytest.fixture
def fake_email_generator():
    """
    Generate realistic fake emails using Faker.
    Returns a function that creates email data with customizable properties.
    """
    faker = Faker('fr_FR')  # French locale for DisruptIQ

    def generate_email(
        urgency: str = "routine",
        is_promotional: bool = False,
        has_attachments: bool = False,
        category: str = "general"
    ) -> dict:
        """Generate a fake email with specified properties"""

        # Subject templates based on urgency
        urgent_subjects = [
            f"URGENT: {faker.catch_phrase()}",
            f"EMERGENCY: {faker.bs()}",
            "Intervention immédiate requise",
            "Problème critique à résoudre"
        ]

        important_subjects = [
            f"Important: {faker.catch_phrase()}",
            f"À traiter: {faker.bs()}",
            "Réunion importante",
            "Document à signer"
        ]

        routine_subjects = [
            faker.catch_phrase(),
            f"Info: {faker.bs()}",
            "Mise à jour",
            "Confirmation"
        ]

        promo_subjects = [
            f"🎉 Offre spéciale: {faker.word()}",
            "Ne manquez pas cette opportunité!",
            f"Promo exclusive: {faker.word()}",
            "Votre code promo inside"
        ]

        # Select subject based on type
        if is_promotional:
            subject = faker.random.choice(promo_subjects)
            sender = f"noreply@{faker.domain_name()}"
        else:
            if urgency == "urgent":
                subject = faker.random.choice(urgent_subjects)
            elif urgency == "important":
                subject = faker.random.choice(important_subjects)
            else:
                subject = faker.random.choice(routine_subjects)
            sender = faker.email()

        # Generate body
        body = "\n\n".join([faker.paragraph(nb_sentences=3) for _ in range(2)])

        # Add promotional keywords if needed
        if is_promotional:
            body += "\n\n" + "Cliquez ici pour en profiter! Désabonnez-vous ici."

        # Generate attachments
        attachments = []
        if has_attachments:
            attachments = [
                {
                    "filename": f"{faker.word()}.pdf",
                    "mime_type": "application/pdf",
                    "size": faker.random_int(min=1000, max=500000)
                }
                for _ in range(faker.random_int(min=1, max=3))
            ]

        return {
            "message_id": faker.uuid4(),
            "thread_id": faker.uuid4(),
            "sender": sender,
            "subject": subject,
            "body": body,
            "snippet": body[:100] + "...",
            "received_at": faker.date_time_between(start_date="-7d", end_date="now"),
            "attachments": attachments,
            "category": category
        }

    return generate_email


@pytest.fixture
def frozen_time():
    """
    Freeze time for consistent timestamp testing.
    Returns a context manager that freezes time to a specific datetime.

    Usage:
        with frozen_time("2025-11-01 12:00:00"):
            # Time is frozen at 2025-11-01 12:00:00
            assert datetime.now() == datetime(2025, 11, 1, 12, 0, 0)
    """
    return freeze_time


# ==================== Cleanup Fixtures ====================


@pytest.fixture(autouse=True)
def cleanup_test_files():
    """
    Cleanup any test files created during tests.
    """
    yield
    # Add cleanup logic here if needed
    pass
