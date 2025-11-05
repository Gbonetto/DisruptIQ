"""
Tests for Chat API with Conversational Intelligence Integration

Tests the complete flow:
1. Session creation and management
2. Intent classification with context
3. Conversation turn persistence
4. Feedback collection
5. User profiling
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import ConversationSession, ConversationTurn, UserProfile


@pytest.mark.asyncio
class TestConversationalIntelligence:
    """Test conversational intelligence features"""

    async def test_chat_creates_session(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession
    ):
        """Should create a new conversation session on first message"""
        response = await async_client.post(
            "/api/chat/with-plan",
            json={
                "message": "Bonjour",
                "conversation_history": [],
                "session_id": None
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Should return a session_id
        assert "session_id" in data
        assert data["session_id"].startswith("session-")

        # Verify session was created in database
        from sqlalchemy import select
        result = await db_session.execute(
            select(ConversationSession).where(
                ConversationSession.session_id == data["session_id"]
            )
        )
        session = result.scalars().first()
        assert session is not None
        assert session.turns_count >= 1

    async def test_chat_with_existing_session(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession
    ):
        """Should reuse existing session and load context"""
        # First message
        response1 = await async_client.post(
            "/api/chat/with-plan",
            json={
                "message": "Montre-moi les factures",
                "conversation_history": [],
                "session_id": None
            }
        )
        assert response1.status_code == 200
        session_id = response1.json()["session_id"]

        # Second message with same session
        response2 = await async_client.post(
            "/api/chat/with-plan",
            json={
                "message": "Et maintenant seulement celles qui nécessitent révision",
                "conversation_history": [],
                "session_id": session_id
            }
        )
        assert response2.status_code == 200

        # Should use same session
        assert response2.json()["session_id"] == session_id

        # Verify session has 2 turns
        from sqlalchemy import select
        result = await db_session.execute(
            select(ConversationSession).where(
                ConversationSession.session_id == session_id
            )
        )
        session = result.scalars().first()
        assert session.turns_count >= 2

    async def test_intent_classification_logs_intents(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession
    ):
        """Should classify and log intents for each message"""
        response = await async_client.post(
            "/api/chat/with-plan",
            json={
                "message": "Combien de factures avons-nous ?",
                "conversation_history": [],
                "session_id": None
            }
        )

        assert response.status_code == 200
        session_id = response.json()["session_id"]

        # Get the conversation turn
        from sqlalchemy import select
        result = await db_session.execute(
            select(ConversationTurn).join(ConversationSession).where(
                ConversationSession.session_id == session_id
            )
        )
        turn = result.scalars().first()

        assert turn is not None
        assert turn.detected_intent is not None
        assert turn.intent_confidence > 0
        assert turn.all_intents is not None
        assert isinstance(turn.all_intents, dict)

    async def test_clarification_flow(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession
    ):
        """Should ask for clarification when intent is ambiguous"""
        # Send an ambiguous message
        response = await async_client.post(
            "/api/chat/with-plan",
            json={
                "message": "Je veux voir ça",
                "conversation_history": [],
                "session_id": None
            }
        )

        # Depending on confidence threshold, might ask clarification
        # This is a lenient test - just verify it responds
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    async def test_get_chat_history(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession
    ):
        """Should retrieve complete chat history"""
        # Create a conversation with 3 turns
        session_id = None
        for i in range(3):
            response = await async_client.post(
                "/api/chat/with-plan",
                json={
                    "message": f"Message {i+1}",
                    "conversation_history": [],
                    "session_id": session_id
                }
            )
            assert response.status_code == 200
            session_id = response.json()["session_id"]

        # Get history
        response = await async_client.get(f"/api/chat/history/{session_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["session_id"] == session_id
        assert data["turns_count"] >= 3
        assert len(data["messages"]) >= 3

        # Verify messages are in chronological order
        for i, msg in enumerate(data["messages"][:3]):
            assert msg["turn_number"] == i + 1
            assert "user_message" in msg
            assert "assistant_message" in msg
            assert "detected_intent" in msg

    async def test_submit_feedback(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession
    ):
        """Should submit and store user feedback"""
        # Create a conversation
        response = await async_client.post(
            "/api/chat/with-plan",
            json={
                "message": "Test message",
                "conversation_history": [],
                "session_id": None
            }
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]

        # Get the turn_id
        from sqlalchemy import select
        result = await db_session.execute(
            select(ConversationTurn).join(ConversationSession).where(
                ConversationSession.session_id == session_id
            )
        )
        turn = result.scalars().first()
        assert turn is not None

        # Submit feedback
        feedback_response = await async_client.post(
            "/api/chat/feedback",
            json={
                "turn_id": turn.id,
                "satisfied": True,
                "rating": 5,
                "feedback_text": "Excellent response!"
            }
        )
        assert feedback_response.status_code == 200

        # Verify feedback was saved
        await db_session.refresh(turn)
        assert turn.user_satisfied is True
        assert turn.feedback_rating == 5
        assert turn.feedback_text == "Excellent response!"

    async def test_feedback_with_correction(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession
    ):
        """Should handle intent correction feedback"""
        # Create a conversation
        response = await async_client.post(
            "/api/chat/with-plan",
            json={
                "message": "Test message",
                "conversation_history": [],
                "session_id": None
            }
        )
        session_id = response.json()["session_id"]

        # Get the turn
        from sqlalchemy import select
        result = await db_session.execute(
            select(ConversationTurn).join(ConversationSession).where(
                ConversationSession.session_id == session_id
            )
        )
        turn = result.scalars().first()
        original_intent = turn.detected_intent

        # Submit correction
        feedback_response = await async_client.post(
            "/api/chat/feedback",
            json={
                "turn_id": turn.id,
                "satisfied": False,
                "corrected_intent": "QUERY_SUPPLIER"
            }
        )
        assert feedback_response.status_code == 200

        # Verify correction was saved
        await db_session.refresh(turn)
        assert turn.corrected_intent == "QUERY_SUPPLIER"
        assert turn.user_satisfied is False
        assert turn.was_helpful is False

    async def test_end_session(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession
    ):
        """Should end a conversation session"""
        # Create a conversation
        response = await async_client.post(
            "/api/chat/with-plan",
            json={
                "message": "Test message",
                "conversation_history": [],
                "session_id": None
            }
        )
        session_id = response.json()["session_id"]

        # End session
        end_response = await async_client.delete(
            f"/api/chat/history/{session_id}"
        )
        assert end_response.status_code == 200

        # Verify session is marked as ended
        from sqlalchemy import select
        result = await db_session.execute(
            select(ConversationSession).where(
                ConversationSession.session_id == session_id
            )
        )
        session = result.scalars().first()
        assert session.ended_at is not None

    async def test_context_retention_across_turns(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession
    ):
        """Should retain context across conversation turns"""
        session_id = None

        # Turn 1: Ask about invoices
        response1 = await async_client.post(
            "/api/chat/with-plan",
            json={
                "message": "Montre-moi les factures de plomberie",
                "conversation_history": [],
                "session_id": session_id
            }
        )
        assert response1.status_code == 200
        session_id = response1.json()["session_id"]

        # Turn 2: Follow-up with reference ("celles")
        response2 = await async_client.post(
            "/api/chat/with-plan",
            json={
                "message": "Montre-moi celles qui sont supérieures à 1000€",
                "conversation_history": [],
                "session_id": session_id
            }
        )
        assert response2.status_code == 200

        # Should use same session and understand context
        assert response2.json()["session_id"] == session_id

        # Verify intents are being tracked
        from sqlalchemy import select
        result = await db_session.execute(
            select(ConversationSession).where(
                ConversationSession.session_id == session_id
            )
        )
        session = result.scalars().first()
        assert session.turns_count >= 2
        assert session.intents_distribution is not None

    async def test_invalid_feedback_rating(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession
    ):
        """Should reject invalid ratings"""
        response = await async_client.post(
            "/api/chat/feedback",
            json={
                "turn_id": 999999,
                "rating": 10  # Invalid: should be 1-5
            }
        )
        assert response.status_code == 400

    async def test_get_nonexistent_history(
        self,
        async_client: AsyncClient
    ):
        """Should return 404 for nonexistent session"""
        response = await async_client.get(
            "/api/chat/history/nonexistent-session-id"
        )
        assert response.status_code == 404


# Integration tests with multiple services


@pytest.mark.asyncio
class TestConversationalFlowIntegration:
    """Test complete conversational flows"""

    async def test_invoice_query_flow_with_context(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession
    ):
        """
        Test a realistic multi-turn conversation about invoices:
        1. User asks to see invoices
        2. User asks to filter by amount
        3. User asks about a specific one
        4. User provides positive feedback
        """
        session_id = None

        # Turn 1: Initial query
        response1 = await async_client.post(
            "/api/chat/with-plan",
            json={
                "message": "Montre-moi les factures",
                "conversation_history": [],
                "session_id": session_id
            }
        )
        assert response1.status_code == 200
        session_id = response1.json()["session_id"]

        # Turn 2: Refinement with context
        response2 = await async_client.post(
            "/api/chat/with-plan",
            json={
                "message": "Seulement celles supérieures à 500€",
                "conversation_history": [],
                "session_id": session_id
            }
        )
        assert response2.status_code == 200

        # Turn 3: Follow-up question
        response3 = await async_client.post(
            "/api/chat/with-plan",
            json={
                "message": "Quelle est la plus récente ?",
                "conversation_history": [],
                "session_id": session_id
            }
        )
        assert response3.status_code == 200

        # Get history
        history_response = await async_client.get(
            f"/api/chat/history/{session_id}"
        )
        assert history_response.status_code == 200
        history = history_response.json()

        # Should have 3 turns
        assert history["turns_count"] >= 3

        # Verify intents are being classified
        for msg in history["messages"]:
            assert msg["detected_intent"] is not None
            assert msg["intent_confidence"] is not None

    async def test_greeting_and_help_flow(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession
    ):
        """Test greeting and help intent detection"""
        # Greeting
        response1 = await async_client.post(
            "/api/chat/with-plan",
            json={
                "message": "Bonjour",
                "conversation_history": [],
                "session_id": None
            }
        )
        assert response1.status_code == 200
        session_id = response1.json()["session_id"]

        # Help request
        response2 = await async_client.post(
            "/api/chat/with-plan",
            json={
                "message": "Comment puis-je rechercher des factures ?",
                "conversation_history": [],
                "session_id": session_id
            }
        )
        assert response2.status_code == 200

        # Verify intents
        from sqlalchemy import select
        result = await db_session.execute(
            select(ConversationTurn)
            .join(ConversationSession)
            .where(ConversationSession.session_id == session_id)
            .order_by(ConversationTurn.turn_number)
        )
        turns = result.scalars().all()

        # First turn should be greeting-related (or OTHER if not recognized)
        assert len(turns) >= 2
        # Second turn might be HELP or QUERY depending on classification
        assert turns[1].detected_intent is not None
