"""
Pytest Configuration and Shared Fixtures
Provides common test fixtures for database, async client, authentication, etc.
"""

import asyncio
import os
from typing import AsyncGenerator, Generator
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.core.config import settings
from app.models.email import Email, EmailUrgency
from app.models.vendor import Vendor


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
    """Sample vendor data for testing"""
    return {
        "name": "Test Vendor Corp",
        "email": "contact@testvendor.com",
        "phone": "+1-555-0123",
        "address": "123 Test Street, Test City, TC 12345",
        "category": "Technology",
        "description": "A test vendor for unit testing",
        "website": "https://testvendor.com",
        "is_active": True,
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
    Factory fixture to create test vendors in database
    """
    async def _create_vendor(**kwargs) -> Vendor:
        defaults = {
            "name": f"Test Vendor {datetime.now().timestamp()}",
            "email": f"vendor_{datetime.now().timestamp()}@test.com",
            "category": "Technology",
            "is_active": True,
        }
        defaults.update(kwargs)

        vendor = Vendor(**defaults)
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


# ==================== Cleanup Fixtures ====================


@pytest.fixture(autouse=True)
def cleanup_test_files():
    """
    Cleanup any test files created during tests.
    """
    yield
    # Add cleanup logic here if needed
    pass
