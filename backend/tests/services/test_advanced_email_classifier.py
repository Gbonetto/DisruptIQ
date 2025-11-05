"""
Tests for Advanced Email Classifier Service
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.services.advanced_email_classifier import AdvancedEmailClassifier
from app.models.email_category import EmailCategory, EmailSentiment


@pytest.fixture
def classifier():
    """Fixture for AdvancedEmailClassifier instance"""
    return AdvancedEmailClassifier()


@pytest.fixture
def sample_email():
    """Sample email for testing"""
    return {
        "message_id": "test123",
        "subject": "Devis plomberie - Résidence Les Mimosas",
        "sender": "plombier@example.com",
        "body": "Bonjour, veuillez trouver ci-joint le devis pour les travaux de plomberie. Montant total: 2500€. Merci de me confirmer avant le 15/11/2024.",
        "snippet": "Devis travaux plomberie...",
        "received_at": "2024-11-05T10:00:00Z"
    }


@pytest.fixture
def llm_classification_response():
    """Mock LLM classification response"""
    return {
        "urgency": "important",
        "category": "devis_fournisseur",
        "subcategory": "plomberie",
        "sentiment": "neutral",
        "confidence": 0.85,
        "action_required": True,
        "deadline": "2024-11-15T23:59:59Z",
        "suggested_response": "Vérifier le devis et confirmer avant la deadline",
        "tags": ["plomberie", "devis", "travaux"]
    }


@pytest.fixture
def entity_extraction_response():
    """Mock entity extraction response"""
    return {
        "amounts": [{"value": 2500.0, "currency": "EUR", "text": "2500€"}],
        "dates": ["15/11/2024"],
        "persons": [],
        "companies": [],
        "locations": ["Résidence Les Mimosas"]
    }


class TestAdvancedEmailClassifier:
    """Test suite for AdvancedEmailClassifier"""

    @pytest.mark.asyncio
    async def test_classify_advanced_success(
        self,
        classifier,
        sample_email,
        llm_classification_response,
        entity_extraction_response
    ):
        """Test successful advanced classification"""
        # Mock entity extractor (NOT async)
        with patch.object(
            classifier.entity_extractor,
            'extract_entities',
            return_value=entity_extraction_response
        ) as mock_extract:
            # Mock LLM service
            with patch.object(
                classifier.llm_service,
                'generate_response',
                new_callable=AsyncMock
            ) as mock_llm:
                import json
                mock_llm.return_value = json.dumps(llm_classification_response)

                # Call classify_advanced
                result = await classifier.classify_advanced(sample_email)

                # Assertions
                assert result["urgency"] == "important"
                assert result["category"] == "devis_fournisseur"
                assert result["subcategory"] == "plomberie"
                assert result["sentiment"] == "neutral"
                assert result["confidence"] == 0.85
                assert result["action_required"] is True
                assert result["deadline"] == "2024-11-15T23:59:59Z"
                assert result["entities"] == entity_extraction_response
                assert "priority_score" in result
                assert isinstance(result["priority_score"], int)
                assert 0 <= result["priority_score"] <= 100

    @pytest.mark.asyncio
    async def test_classify_advanced_with_thread_context(
        self,
        classifier,
        sample_email,
        llm_classification_response
    ):
        """Test classification with thread context"""
        thread_emails = [
            {"subject": "Re: Devis", "body": "Premier message du thread"},
            {"subject": "Re: Devis", "body": "Deuxième message du thread"}
        ]

        with patch.object(
            classifier.entity_extractor,
            'extract_entities',
            return_value={"amounts": [], "dates": [], "persons": [], "companies": [], "locations": []}
        ) as mock_extract:

            with patch.object(
                classifier.llm_service,
                'generate_response',
                new_callable=AsyncMock
            ) as mock_llm:
                import json
                mock_llm.return_value = json.dumps({
                    **llm_classification_response,
                    "thread_summary": "Conversation sur devis plomberie"
                })

                result = await classifier.classify_advanced(
                    sample_email,
                    thread_emails=thread_emails
                )

                # Verify thread summary is included
                assert "thread_summary" in result
                assert mock_llm.call_count == 1
                # Verify prompt included thread context
                prompt = mock_llm.call_args[1]["prompt"]
                assert "THREAD CONTEXT" in prompt or "thread" in prompt.lower()

    @pytest.mark.asyncio
    async def test_priority_score_calculation_urgent(self, classifier):
        """Test priority score for urgent email"""
        score = classifier._calculate_priority_score(
            urgency="urgent",
            category="intervention_urgente",
            has_deadline=True,
            has_amount=True,
            sender="important@client.com"
        )

        # Urgent (40) + High priority category (20) + Deadline (20) + Amount (10) + Sender (10) = 100
        assert score >= 80  # Should be high priority
        assert score <= 100

    @pytest.mark.asyncio
    async def test_priority_score_calculation_routine(self, classifier):
        """Test priority score for routine email"""
        score = classifier._calculate_priority_score(
            urgency="routine",
            category="information",
            has_deadline=False,
            has_amount=False,
            sender="newsletter@example.com"
        )

        # Routine (10) + Low priority category (10) + No deadline (0) + No amount (0) + Normal sender (5) = 25
        assert score <= 30  # Should be low priority

    @pytest.mark.asyncio
    async def test_priority_score_calculation_important(self, classifier):
        """Test priority score for important email with deadline"""
        score = classifier._calculate_priority_score(
            urgency="important",
            category="devis_fournisseur",
            has_deadline=True,
            has_amount=True,
            sender="fournisseur@example.com"
        )

        # Important (25) + Medium priority category (15) + Deadline (20) + Amount (10) + Sender (5-10) = 75-80
        assert 60 <= score <= 90

    @pytest.mark.asyncio
    async def test_llm_classification_fallback(
        self,
        classifier,
        sample_email
    ):
        """Test fallback when LLM classification fails"""
        with patch.object(
            classifier.entity_extractor,
            'extract_entities',
            return_value={"amounts": [], "dates": [], "persons": [], "companies": [], "locations": []}
        ) as mock_extract:

            with patch.object(
                classifier.llm_service,
                'generate_response',
                new_callable=AsyncMock
            ) as mock_llm:
                # Simulate LLM failure
                mock_llm.side_effect = Exception("LLM service unavailable")

                result = await classifier.classify_advanced(sample_email)

                # Should return fallback classification
                assert result["urgency"] == "routine"
                assert result["category"] == "autre"
                assert result["confidence"] == 0.3
                # Fallback should not crash and return valid structure

    @pytest.mark.asyncio
    async def test_entity_extraction_integration(
        self,
        classifier,
        sample_email,
        llm_classification_response
    ):
        """Test entity extraction is called and results are included"""
        mock_entities = {
            "amounts": [{"value": 2500.0, "currency": "EUR"}],
            "dates": ["2024-11-15"],
            "persons": ["Jean Dupont"],
            "companies": ["Plomberie Express"],
            "locations": ["Paris"]
        }

        with patch.object(
            classifier.entity_extractor,
            'extract_entities',
            return_value=mock_entities
        ) as mock_extract:

            with patch.object(
                classifier.llm_service,
                'generate_response',
                new_callable=AsyncMock
            ) as mock_llm:
                import json
                mock_llm.return_value = json.dumps(llm_classification_response)

                result = await classifier.classify_advanced(sample_email)

                # Verify entity extraction was called
                mock_extract.assert_called_once()
                # Verify entities are in result
                assert result["entities"] == mock_entities

    @pytest.mark.asyncio
    async def test_deadline_extraction(
        self,
        classifier,
        sample_email,
        llm_classification_response
    ):
        """Test deadline extraction from LLM response"""
        with patch.object(
            classifier.entity_extractor,
            'extract_entities',
            return_value={"amounts": [], "dates": [], "persons": [], "companies": [], "locations": []}
        ) as mock_extract:

            with patch.object(
                classifier.llm_service,
                'generate_response',
                new_callable=AsyncMock
            ) as mock_llm:
                import json
                response_with_deadline = {
                    **llm_classification_response,
                    "deadline": "2024-11-15T17:00:00Z"
                }
                mock_llm.return_value = json.dumps(response_with_deadline)

                result = await classifier.classify_advanced(sample_email)

                assert result["deadline"] == "2024-11-15T17:00:00Z"

    @pytest.mark.asyncio
    async def test_action_required_detection(
        self,
        classifier,
        sample_email,
        llm_classification_response
    ):
        """Test action_required flag is properly set"""
        with patch.object(
            classifier.entity_extractor,
            'extract_entities',
            return_value={"amounts": [], "dates": [], "persons": [], "companies": [], "locations": []}
        ) as mock_extract:

            with patch.object(
                classifier.llm_service,
                'generate_response',
                new_callable=AsyncMock
            ) as mock_llm:
                import json
                response_with_action = {
                    **llm_classification_response,
                    "action_required": True,
                    "suggested_response": "Répondre avant la deadline"
                }
                mock_llm.return_value = json.dumps(response_with_action)

                result = await classifier.classify_advanced(sample_email)

                assert result["action_required"] is True
                assert result["suggested_response"] == "Répondre avant la deadline"

    @pytest.mark.asyncio
    async def test_sentiment_analysis(
        self,
        classifier,
        llm_classification_response
    ):
        """Test sentiment analysis for angry/negative emails"""
        angry_email = {
            "message_id": "angry123",
            "subject": "URGENT - Problème grave non résolu!!!",
            "sender": "client.mecontent@example.com",
            "body": "C'est inacceptable! Cela fait 3 semaines que j'attends une réponse! Je vais porter plainte!",
            "snippet": "C'est inacceptable...",
            "received_at": "2024-11-05T10:00:00Z"
        }

        with patch.object(
            classifier.entity_extractor,
            'extract_entities',
            return_value={"amounts": [], "dates": [], "persons": [], "companies": [], "locations": []}
        ) as mock_extract:

            with patch.object(
                classifier.llm_service,
                'generate_response',
                new_callable=AsyncMock
            ) as mock_llm:
                import json
                response_angry = {
                    **llm_classification_response,
                    "sentiment": "angry",
                    "urgency": "urgent"
                }
                mock_llm.return_value = json.dumps(response_angry)

                result = await classifier.classify_advanced(angry_email)

                assert result["sentiment"] == "angry"
                assert result["urgency"] == "urgent"

    @pytest.mark.asyncio
    async def test_tags_generation(
        self,
        classifier,
        sample_email,
        llm_classification_response
    ):
        """Test tags are properly generated"""
        with patch.object(
            classifier.entity_extractor,
            'extract_entities',
            return_value={"amounts": [], "dates": [], "persons": [], "companies": [], "locations": []}
        ) as mock_extract:

            with patch.object(
                classifier.llm_service,
                'generate_response',
                new_callable=AsyncMock
            ) as mock_llm:
                import json
                response_with_tags = {
                    **llm_classification_response,
                    "tags": ["plomberie", "devis", "urgent", "travaux"]
                }
                mock_llm.return_value = json.dumps(response_with_tags)

                result = await classifier.classify_advanced(sample_email)

                assert "tags" in result
                assert isinstance(result["tags"], list)
                assert "plomberie" in result["tags"]
                assert "devis" in result["tags"]
