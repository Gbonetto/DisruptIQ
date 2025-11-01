"""
Unit Tests for Database Models
Tests email and vendor models, validation, and constraints
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError

from app.models.email import Email, EmailUrgency
from app.models.professionnel import Professionnel


@pytest.mark.unit
@pytest.mark.asyncio
class TestEmailModel:
    """Test suite for Email model"""

    async def test_create_email_with_all_fields(self, async_session, sample_email_data):
        """Test creating an email with all fields"""
        email = Email(**sample_email_data, urgency=EmailUrgency.ROUTINE)
        async_session.add(email)
        await async_session.commit()
        await async_session.refresh(email)

        assert email.id is not None
        assert email.message_id == sample_email_data["message_id"]
        assert email.subject == sample_email_data["subject"]
        assert email.urgency == EmailUrgency.ROUTINE
        assert email.processed is True
        assert email.created_at is not None

    async def test_email_urgency_enum(self, async_session):
        """Test email urgency enum values"""
        for urgency in [EmailUrgency.URGENT, EmailUrgency.IMPORTANT, EmailUrgency.ROUTINE]:
            email = Email(
                message_id=f"test_{urgency.value}",
                thread_id="thread_001",
                sender="test@example.com",
                subject=f"Test {urgency.value}",
                body="Test body",
                urgency=urgency,
                received_at=datetime.now()
            )
            async_session.add(email)
            await async_session.commit()
            await async_session.refresh(email)

            assert email.urgency == urgency

    async def test_email_unique_message_id(self, async_session, create_test_email):
        """Test that message_id must be unique"""
        # Create first email
        await create_test_email(message_id="unique_msg_001")

        # Try to create duplicate
        with pytest.raises(IntegrityError):
            await create_test_email(message_id="unique_msg_001")
            await async_session.commit()

    async def test_email_default_values(self, async_session):
        """Test default values are set correctly"""
        email = Email(
            message_id="test_defaults",
            thread_id="thread_001",
            sender="test@example.com",
            subject="Test",
            body="Test body",
            urgency=EmailUrgency.ROUTINE,
            received_at=datetime.now()
        )
        async_session.add(email)
        await async_session.commit()
        await async_session.refresh(email)

        assert email.processed is True
        assert email.included_in_digest is True
        assert email.attachments == []
        assert isinstance(email.created_at, datetime)
        assert isinstance(email.updated_at, datetime)

    async def test_email_timestamp_auto_update(self, async_session, create_test_email):
        """Test that updated_at is automatically updated"""
        email = await create_test_email(subject="Original Subject")
        original_updated_at = email.updated_at

        # Wait a tiny bit to ensure timestamp difference
        import asyncio
        await asyncio.sleep(0.01)

        # Update email
        email.subject = "Updated Subject"
        await async_session.commit()
        await async_session.refresh(email)

        assert email.updated_at > original_updated_at

    async def test_email_with_attachments(self, async_session):
        """Test email with attachments"""
        attachments = [
            {
                "filename": "document.pdf",
                "mime_type": "application/pdf",
                "size": 1024,
                "attachment_id": "att_001"
            },
            {
                "filename": "image.png",
                "mime_type": "image/png",
                "size": 2048,
                "attachment_id": "att_002"
            }
        ]

        email = Email(
            message_id="test_with_attachments",
            thread_id="thread_001",
            sender="test@example.com",
            subject="Email with attachments",
            body="Test body",
            urgency=EmailUrgency.ROUTINE,
            received_at=datetime.now(),
            attachments=attachments
        )
        async_session.add(email)
        await async_session.commit()
        await async_session.refresh(email)

        assert len(email.attachments) == 2
        assert email.attachments[0]["filename"] == "document.pdf"
        assert email.attachments[1]["filename"] == "image.png"

    async def test_email_required_fields(self, async_session):
        """Test that required fields must be provided"""
        # Missing message_id
        with pytest.raises(TypeError):
            email = Email(
                thread_id="thread_001",
                sender="test@example.com",
                subject="Test",
                body="Test body",
                urgency=EmailUrgency.ROUTINE
            )


@pytest.mark.unit
@pytest.mark.asyncio
class TestVendorModel:
    """Test suite for Professionnel model"""

    async def test_create_vendor_with_all_fields(self, async_session, sample_vendor_data):
        """Test creating a professionnel with all fields"""
        vendor = Professionnel(**sample_vendor_data)
        async_session.add(vendor)
        await async_session.commit()
        await async_session.refresh(vendor)

        assert vendor.id is not None
        assert vendor.name == sample_vendor_data["name"]
        assert vendor.email == sample_vendor_data["email"]
        assert vendor.is_active is True
        assert vendor.created_at is not None

    async def test_vendor_unique_email(self, async_session, create_test_vendor):
        """Test that professionnel email must be unique"""
        # Create first professionnel
        await create_test_vendor(email="unique@vendor.com")

        # Try to create duplicate
        with pytest.raises(IntegrityError):
            await create_test_vendor(email="unique@vendor.com")
            await async_session.commit()

    async def test_vendor_default_values(self, async_session):
        """Test professionnel default values"""
        vendor = Professionnel(
            name="Test Vendor",
            email="test@vendor.com",
            category="Technology"
        )
        async_session.add(vendor)
        await async_session.commit()
        await async_session.refresh(vendor)

        assert vendor.is_active is True
        assert vendor.is_indexed is False
        assert vendor.tags == []
        assert isinstance(vendor.created_at, datetime)

    async def test_vendor_with_tags(self, async_session):
        """Test professionnel with tags"""
        tags = ["technology", "cloud", "saas"]
        vendor = Professionnel(
            name="Tech Vendor",
            email="tech@vendor.com",
            category="Technology",
            tags=tags
        )
        async_session.add(vendor)
        await async_session.commit()
        await async_session.refresh(vendor)

        assert len(vendor.tags) == 3
        assert "cloud" in vendor.tags

    async def test_vendor_optional_fields(self, async_session):
        """Test professionnel with optional fields null"""
        vendor = Professionnel(
            name="Minimal Vendor",
            email="minimal@vendor.com",
            category="Other"
        )
        async_session.add(vendor)
        await async_session.commit()
        await async_session.refresh(vendor)

        assert vendor.phone is None
        assert vendor.address is None
        assert vendor.website is None
        assert vendor.description is None
        assert vendor.logo_url is None
