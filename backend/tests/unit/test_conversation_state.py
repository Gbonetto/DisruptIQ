"""
Unit tests for Conversation State Manager

Tests cover:
1. State initialization
2. Topic and context management
3. Recipients tracking
4. Pending actions
5. Business context
6. Document tracking
7. State extraction from messages
8. State persistence across turns
"""

import pytest
from app.services.agents.conversation_state import (
    ConversationState,
    StateManager,
    ActionType
)


@pytest.fixture
def conversation_state():
    """Create fresh ConversationState for each test"""
    return ConversationState()


@pytest.fixture
def state_manager():
    """Create fresh StateManager for each test"""
    return StateManager()


class TestConversationStateBasics:
    """Test basic state initialization and properties"""

    def test_state_initialization(self, conversation_state):
        """Test that state initializes with correct defaults"""
        assert conversation_state.topic is None
        assert conversation_state.sub_topic is None
        assert conversation_state.recipients_identified == []
        assert conversation_state.recipients_context is None
        assert conversation_state.pending_action == ActionType.NONE
        assert conversation_state.pending_data == {}
        assert conversation_state.business_context == {}
        assert conversation_state.last_uploaded_documents == []

    def test_update_topic(self, conversation_state):
        """Test updating conversation topic"""
        conversation_state.update_topic("dégât des eaux", "alerte")

        assert conversation_state.topic == "dégât des eaux"
        assert conversation_state.sub_topic == "alerte"

    def test_update_topic_without_subtopic(self, conversation_state):
        """Test updating topic without subtopic"""
        conversation_state.update_topic("demande devis")

        assert conversation_state.topic == "demande devis"
        assert conversation_state.sub_topic is None


class TestRecipientsTracking:
    """Test recipient management"""

    def test_add_recipients(self, conversation_state):
        """Test adding recipients"""
        emails = ["john@example.com", "jane@example.com"]
        conversation_state.add_recipients(emails)

        assert len(conversation_state.recipients_identified) == 2
        assert "john@example.com" in conversation_state.recipients_identified
        assert "jane@example.com" in conversation_state.recipients_identified

    def test_add_recipients_no_duplicates(self, conversation_state):
        """Test that duplicate recipients are not added"""
        conversation_state.add_recipients(["john@example.com"])
        conversation_state.add_recipients(["john@example.com", "jane@example.com"])

        assert len(conversation_state.recipients_identified) == 2
        assert conversation_state.recipients_identified.count("john@example.com") == 1

    def test_set_recipients_context(self, conversation_state):
        """Test setting recipient context"""
        conversation_state.set_recipients_context("copropriétaires des mimosas")

        assert conversation_state.recipients_context == "copropriétaires des mimosas"


class TestPendingActions:
    """Test pending action management"""

    def test_set_pending_action(self, conversation_state):
        """Test setting pending action"""
        data = {"draft": {"subject": "Test", "body": "Content"}}
        conversation_state.set_pending_action(ActionType.AWAITING_EMAIL_CONFIRMATION, data)

        assert conversation_state.pending_action == ActionType.AWAITING_EMAIL_CONFIRMATION
        assert conversation_state.pending_data == data

    def test_set_pending_action_without_data(self, conversation_state):
        """Test setting pending action without data"""
        conversation_state.set_pending_action(ActionType.AWAITING_SQL_QUERY)

        assert conversation_state.pending_action == ActionType.AWAITING_SQL_QUERY
        assert conversation_state.pending_data == {}

    def test_clear_pending_action(self, conversation_state):
        """Test clearing pending action"""
        conversation_state.set_pending_action(ActionType.AWAITING_EMAIL_CONFIRMATION, {"test": "data"})
        conversation_state.clear_pending_action()

        assert conversation_state.pending_action == ActionType.NONE
        assert conversation_state.pending_data == {}

    def test_set_email_draft(self, conversation_state):
        """Test storing email draft"""
        draft = {
            "subject": "Alerte gaz",
            "body": "Attention odeurs de gaz",
            "recipients": ["test@example.com"]
        }
        conversation_state.set_email_draft(draft)

        assert conversation_state.email_draft == draft
        assert conversation_state.pending_action == ActionType.AWAITING_EMAIL_CONFIRMATION
        assert conversation_state.pending_data["draft"] == draft


class TestBusinessContext:
    """Test business context management"""

    def test_update_business_context(self, conversation_state):
        """Test updating business context"""
        context = {"incident_type": "gas", "urgency": "high"}
        conversation_state.update_business_context(context)

        assert conversation_state.business_context["incident_type"] == "gas"
        assert conversation_state.business_context["urgency"] == "high"

    def test_update_business_context_incremental(self, conversation_state):
        """Test that business context updates incrementally"""
        conversation_state.update_business_context({"incident_type": "gas"})
        conversation_state.update_business_context({"urgency": "high"})

        assert conversation_state.business_context["incident_type"] == "gas"
        assert conversation_state.business_context["urgency"] == "high"

    def test_get_relevant_professions_gas(self, conversation_state):
        """Test getting relevant professions for gas incident"""
        conversation_state.update_business_context({"incident_type": "gas"})
        professions = conversation_state.get_relevant_professions()

        assert "chauffagiste" in professions
        assert "plombier" in professions

    def test_get_relevant_professions_electrical(self, conversation_state):
        """Test getting relevant professions for electrical incident"""
        conversation_state.update_business_context({"incident_type": "electrical"})
        professions = conversation_state.get_relevant_professions()

        assert "électricien" in professions

    def test_get_relevant_professions_no_incident(self, conversation_state):
        """Test getting professions with no incident type"""
        professions = conversation_state.get_relevant_professions()

        assert professions == []


class TestDocumentTracking:
    """Test document tracking"""

    def test_add_uploaded_document(self, conversation_state):
        """Test adding uploaded document"""
        conversation_state.add_uploaded_document("contrat.pdf", 123, "application/pdf")

        assert len(conversation_state.last_uploaded_documents) == 1
        doc = conversation_state.last_uploaded_documents[0]
        assert doc["filename"] == "contrat.pdf"
        assert doc["document_id"] == 123
        assert doc["mime_type"] == "application/pdf"

    def test_add_multiple_documents_fifo(self, conversation_state):
        """Test that documents are kept in FIFO order (max 5)"""
        for i in range(7):
            conversation_state.add_uploaded_document(f"doc{i}.pdf", i, "application/pdf")

        # Should keep only last 5
        assert len(conversation_state.last_uploaded_documents) == 5
        # Most recent should be first
        assert conversation_state.last_uploaded_documents[0]["document_id"] == 6
        assert conversation_state.last_uploaded_documents[4]["document_id"] == 2

    def test_set_active_document_ids(self, conversation_state):
        """Test setting active document IDs"""
        doc_ids = [1, 2, 3]
        conversation_state.set_active_document_ids(doc_ids)

        assert conversation_state.active_document_ids == doc_ids


class TestQueryEntityTracking:
    """Test query entity tracking for reference resolution"""

    def test_set_last_query_entities(self, conversation_state):
        """Test storing entities from last query"""
        entities = [
            {"nom": "Dupont", "prenom": "Jean", "email": "jean@example.com"},
            {"nom": "Martin", "prenom": "Marie", "email": "marie@example.com"}
        ]
        conversation_state.set_last_query_entities(entities, "people")

        assert len(conversation_state.last_query_entities) == 2
        assert conversation_state.last_query_type == "people"
        assert conversation_state.last_query_entities[0]["nom"] == "Dupont"


class TestStateManager:
    """Test StateManager functionality"""

    def test_state_manager_initialization(self, state_manager):
        """Test that StateManager initializes with fresh state"""
        state = state_manager.get_state()

        assert isinstance(state, ConversationState)
        assert state.topic is None

    def test_state_manager_reset(self, state_manager):
        """Test resetting state"""
        state_manager.state.update_topic("test topic")
        state_manager.reset()

        assert state_manager.state.topic is None
        assert len(state_manager.state.recipients_identified) == 0

    def test_extract_from_message_gas_incident(self, state_manager):
        """Test extracting context from gas incident message"""
        message = "Odeurs de gaz détectées aux Mimosas, prévenez les copropriétaires"
        state_manager.extract_and_update_from_message(message)

        assert state_manager.state.topic == "odeurs de gaz"
        assert state_manager.state.sub_topic == "alerte sécurité"
        assert state_manager.state.business_context["incident_type"] == "gas"
        assert state_manager.state.recipients_context == "copropriétaires des mimosas"

    def test_extract_from_message_water_damage(self, state_manager):
        """Test extracting context from water damage message"""
        message = "Dégât des eaux au 3ème étage"
        state_manager.extract_and_update_from_message(message)

        assert state_manager.state.topic == "dégât des eaux"
        assert state_manager.state.business_context["incident_type"] == "water_damage"

    def test_extract_from_message_profession(self, state_manager):
        """Test extracting profession from message"""
        message = "Contacte tous les plombiers pour devis"
        state_manager.extract_and_update_from_message(message)

        assert state_manager.state.recipients_context == "plombiers"
        assert state_manager.state.business_context["profession_requested"] == "plombier"


class TestStateSummary:
    """Test state summary generation"""

    def test_get_context_summary_empty(self, conversation_state):
        """Test context summary with empty state"""
        summary = conversation_state.get_context_summary()

        assert summary == "Aucun contexte"

    def test_get_context_summary_with_data(self, conversation_state):
        """Test context summary with data"""
        conversation_state.update_topic("dégât des eaux")
        conversation_state.set_recipients_context("copropriétaires")
        conversation_state.add_recipients(["test@example.com"])
        conversation_state.update_business_context({"urgency": "high"})

        summary = conversation_state.get_context_summary()

        assert "Sujet: dégât des eaux" in summary
        assert "Destinataires: copropriétaires" in summary
        assert "Emails trouvés: 1" in summary
        assert "urgency=high" in summary
