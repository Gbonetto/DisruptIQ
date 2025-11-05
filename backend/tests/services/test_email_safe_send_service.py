"""
Tests for Email Safe-Send Service
"""

import pytest
from app.services.email_safe_send_service import (
    EmailSafeSendService,
    Recipient,
    Evidence,
    EvidenceType,
    EmailPriority,
    EmailSendRequest,
    EmailChecklist
)


class TestEmailSafeSendService:
    """Test suite for Email Safe-Send Service"""

    @pytest.fixture
    def service(self):
        """Create service instance"""
        return EmailSafeSendService()

    @pytest.fixture
    def sample_recipients(self):
        """Sample recipients"""
        return [
            Recipient(email="test1@example.com", name="Test User 1", type="to"),
            Recipient(email="test2@example.com", name="Test User 2", type="to")
        ]

    @pytest.fixture
    def sample_evidence(self):
        """Sample evidence"""
        return [
            Evidence(
                type=EvidenceType.SQL,
                title="Liste copropriétaires",
                content="25 copropriétaires trouvés",
                reference="query_123"
            ),
            Evidence(
                type=EvidenceType.RAG,
                title="Procédure convocation AG",
                content="Document règlement intérieur",
                reference="doc_456"
            )
        ]

    @pytest.mark.asyncio
    async def test_generate_draft(self, service, sample_recipients, sample_evidence):
        """Test draft creation"""
        draft = await service.generate_draft(
            subject="Test Email",
            body="This is a test email body",
            recipients=sample_recipients,
            evidence=sample_evidence,
            priority=EmailPriority.NORMAL
        )

        assert draft is not None
        assert draft.id is not None
        assert draft.subject == "Test Email"
        assert len(draft.recipients) == 2
        assert len(draft.evidence) == 2
        assert draft.preview_shown is False
        assert draft.checklist_validated is False
        assert draft.content_hash is not None

    @pytest.mark.asyncio
    async def test_get_draft(self, service, sample_recipients, sample_evidence):
        """Test get draft by ID"""
        # Create draft
        draft = await service.generate_draft(
            subject="Test",
            body="Body",
            recipients=sample_recipients,
            evidence=sample_evidence
        )

        # Retrieve it
        retrieved = await service.get_draft(draft.id)

        assert retrieved is not None
        assert retrieved.id == draft.id
        assert retrieved.subject == draft.subject

    @pytest.mark.asyncio
    async def test_get_draft_not_found(self, service):
        """Test get draft with invalid ID"""
        retrieved = await service.get_draft("non_existent_id")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_generate_preview_success(self, service, sample_recipients, sample_evidence):
        """Test preview generation with valid draft"""
        # Create draft
        draft = await service.generate_draft(
            subject="Test Email",
            body="Test body content",
            recipients=sample_recipients,
            evidence=sample_evidence
        )

        # Generate preview
        preview = await service.generate_preview(draft.id)

        assert preview is not None
        assert preview.draft_id == draft.id
        assert preview.subject == "Test Email"
        assert preview.recipients_count == 2
        assert preview.evidence_count == 2
        assert len(preview.recipients_preview) > 0
        assert len(preview.evidence_summary) > 0
        assert preview.checklist is not None
        assert preview.can_send is True  # Should be OK with 2 evidence
        assert preview.preview_text != ""

        # Draft should be marked as preview shown
        updated_draft = await service.get_draft(draft.id)
        assert updated_draft.preview_shown is True

    @pytest.mark.asyncio
    async def test_generate_preview_no_evidence(self, service, sample_recipients):
        """Test preview generation with no evidence"""
        # Create draft WITHOUT evidence
        draft = await service.generate_draft(
            subject="Test",
            body="Body",
            recipients=sample_recipients,
            evidence=[]  # No evidence
        )

        preview = await service.generate_preview(draft.id)

        assert preview is not None
        assert preview.can_send is False  # Should be blocked
        assert len(preview.blocking_issues) > 0
        assert any("evidence" in issue.lower() for issue in preview.blocking_issues)

    @pytest.mark.asyncio
    async def test_generate_preview_insufficient_evidence(self, service, sample_recipients):
        """Test preview generation with only 1 evidence"""
        # Create draft with only 1 evidence
        evidence = [
            Evidence(
                type=EvidenceType.MANUAL,
                title="Single source",
                content="Only one source"
            )
        ]

        draft = await service.generate_draft(
            subject="Test",
            body="Body",
            recipients=sample_recipients,
            evidence=evidence
        )

        preview = await service.generate_preview(draft.id)

        assert preview is not None
        assert preview.can_send is True  # Not blocking, just warning
        assert len(preview.warnings) > 0
        assert any("2 sources" in warning for warning in preview.warnings)

    @pytest.mark.asyncio
    async def test_generate_preview_sensitive_info(self, service, sample_recipients, sample_evidence):
        """Test preview generation detects sensitive info"""
        # Create draft with sensitive content
        draft = await service.generate_draft(
            subject="Test",
            body="Voici mon mot de passe: secret123 et mon IBAN",
            recipients=sample_recipients,
            evidence=sample_evidence
        )

        preview = await service.generate_preview(draft.id)

        assert preview is not None
        assert len(preview.warnings) > 0
        # Should detect "mot de passe" and "iban"
        assert any("sensible" in warning.lower() for warning in preview.warnings)

    @pytest.mark.asyncio
    async def test_generate_preview_mass_send(self, service, sample_evidence):
        """Test preview generation with mass send (50+ recipients)"""
        # Create 60 recipients
        mass_recipients = [
            Recipient(email=f"test{i}@example.com")
            for i in range(60)
        ]

        draft = await service.generate_draft(
            subject="Test",
            body="Mass email",
            recipients=mass_recipients,
            evidence=sample_evidence
        )

        preview = await service.generate_preview(draft.id)

        assert preview is not None
        assert preview.recipients_count == 60
        assert len(preview.warnings) > 0
        assert any("massif" in warning.lower() for warning in preview.warnings)

    @pytest.mark.asyncio
    async def test_content_hash_generation(self, service, sample_recipients, sample_evidence):
        """Test content hash is generated"""
        draft = await service.generate_draft(
            subject="Test",
            body="Body",
            recipients=sample_recipients,
            evidence=sample_evidence
        )

        assert draft.content_hash is not None
        assert len(draft.content_hash) == 64  # SHA256 hex = 64 chars

    @pytest.mark.asyncio
    async def test_has_been_modified_false(self, service, sample_recipients, sample_evidence):
        """Test has_been_modified returns False when no changes"""
        draft = await service.generate_draft(
            subject="Test",
            body="Body",
            recipients=sample_recipients,
            evidence=sample_evidence
        )

        # No modifications
        assert draft.has_been_modified() is False

    @pytest.mark.asyncio
    async def test_has_been_modified_true(self, service, sample_recipients, sample_evidence):
        """Test has_been_modified returns True after changes"""
        draft = await service.generate_draft(
            subject="Test",
            body="Body",
            recipients=sample_recipients,
            evidence=sample_evidence
        )

        # Modify subject
        draft.subject = "Modified Subject"

        # Should detect modification
        assert draft.has_been_modified() is True

    @pytest.mark.asyncio
    async def test_validate_checklist_all_required_checked(self, service, sample_recipients, sample_evidence):
        """Test checklist validation with all required items checked"""
        draft = await service.generate_draft(
            subject="Test",
            body="Body",
            recipients=sample_recipients,
            evidence=sample_evidence
        )

        # Create checklist with all required items checked
        checklist = EmailChecklist.default_checklist()
        for item in checklist.items:
            if item.get("required"):
                item["checked"] = True

        validated = await service.validate_checklist(draft.id, checklist)

        assert validated is True

        # Draft should be marked as validated
        updated_draft = await service.get_draft(draft.id)
        assert updated_draft.checklist_validated is True

    @pytest.mark.asyncio
    async def test_validate_checklist_missing_required(self, service, sample_recipients, sample_evidence):
        """Test checklist validation with missing required items"""
        draft = await service.generate_draft(
            subject="Test",
            body="Body",
            recipients=sample_recipients,
            evidence=sample_evidence
        )

        # Create checklist with some required items unchecked
        checklist = EmailChecklist.default_checklist()
        checklist.items[0]["checked"] = False  # First required item unchecked

        validated = await service.validate_checklist(draft.id, checklist)

        assert validated is False

    @pytest.mark.asyncio
    async def test_send_email_success(self, service, sample_recipients, sample_evidence):
        """Test successful email send"""
        # Create draft
        draft = await service.generate_draft(
            subject="Test",
            body="Body",
            recipients=sample_recipients,
            evidence=sample_evidence
        )

        # Generate preview
        await service.generate_preview(draft.id)

        # Validate checklist
        checklist = EmailChecklist.default_checklist()
        for item in checklist.items:
            if item.get("required"):
                item["checked"] = True
        await service.validate_checklist(draft.id, checklist)

        # Send
        result = await service.send_email(
            EmailSendRequest(
                draft_id=draft.id,
                checklist_confirmed=True
            ),
            email_sender_service=None  # No real SMTP in test
        )

        assert result.success is True
        assert result.sent_count == 2  # Simulation mode
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_send_email_blocked_no_preview(self, service, sample_recipients, sample_evidence):
        """Test email send blocked without preview"""
        draft = await service.generate_draft(
            subject="Test",
            body="Body",
            recipients=sample_recipients,
            evidence=sample_evidence
        )

        # Try to send WITHOUT preview
        result = await service.send_email(
            EmailSendRequest(
                draft_id=draft.id,
                checklist_confirmed=True
            )
        )

        assert result.success is False
        assert any("preview" in err.lower() for err in result.errors)

    @pytest.mark.asyncio
    async def test_send_email_blocked_no_checklist(self, service, sample_recipients):
        """Test email send blocked without checklist validation"""
        # Create draft with insufficient evidence
        evidence = [Evidence(type=EvidenceType.MANUAL, title="One", content="Only one")]

        draft = await service.generate_draft(
            subject="Test",
            body="Body",
            recipients=sample_recipients,
            evidence=evidence
        )

        # Generate preview
        await service.generate_preview(draft.id)

        # Try to send WITHOUT checklist validation
        result = await service.send_email(
            EmailSendRequest(
                draft_id=draft.id,
                checklist_confirmed=True
            )
        )

        assert result.success is False
        assert any("checklist" in err.lower() for err in result.errors)

    @pytest.mark.asyncio
    async def test_send_email_blocked_modified_after_preview(self, service, sample_recipients, sample_evidence):
        """Test email send blocked if modified after preview"""
        draft = await service.generate_draft(
            subject="Original",
            body="Body",
            recipients=sample_recipients,
            evidence=sample_evidence
        )

        # Generate preview
        await service.generate_preview(draft.id)

        # Modify draft AFTER preview
        draft.subject = "Modified Subject"

        # Try to send
        result = await service.send_email(
            EmailSendRequest(
                draft_id=draft.id,
                checklist_confirmed=True
            )
        )

        assert result.success is False
        assert any("modifié" in err for err in result.errors)

    @pytest.mark.asyncio
    async def test_send_email_force_send(self, service, sample_recipients, sample_evidence):
        """Test force_send bypasses some checks (admin only)"""
        draft = await service.generate_draft(
            subject="Test",
            body="Body",
            recipients=sample_recipients,
            evidence=sample_evidence
        )

        # Try to send with force_send (no preview, no checklist)
        result = await service.send_email(
            EmailSendRequest(
                draft_id=draft.id,
                checklist_confirmed=False,
                force_send=True
            )
        )

        # Should succeed in simulation mode
        assert result.success is True

    def test_default_checklist_structure(self):
        """Test default checklist has proper structure"""
        checklist = EmailChecklist.default_checklist()

        assert len(checklist.items) == 6

        # Count required items
        required_count = sum(1 for item in checklist.items if item.get("required"))
        assert required_count == 4

        # Check all items have required fields
        for item in checklist.items:
            assert "id" in item
            assert "label" in item
            assert "checked" in item
            assert "required" in item

    @pytest.mark.asyncio
    async def test_preview_text_formatting(self, service, sample_recipients, sample_evidence):
        """Test preview text is properly formatted"""
        draft = await service.generate_draft(
            subject="Test Email",
            body="Body",
            recipients=sample_recipients,
            evidence=sample_evidence
        )

        preview = await service.generate_preview(draft.id)

        assert preview.preview_text != ""
        assert "📧 PREVIEW EMAIL" in preview.preview_text
        assert "Test Email" in preview.preview_text
        assert "2 source(s)" in preview.preview_text
