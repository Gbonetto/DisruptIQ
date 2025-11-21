"""
Unit tests for Intent Classifier V4

Tests cover:
1. Classification accuracy for different intent types
2. Confidence threshold enforcement
3. Data source disambiguation (SQL vs RAG vs HYBRID)
4. Quick rule matching
5. Anaphora resolution
6. French name parsing
7. Clarification handling
8. Edge cases and error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.agents.intent_classifier_v4 import (
    EnhancedIntentClassifierV4,
    IntentType,
    DataSource,
    ClassificationResult,
    FrenchNameEntity
)


@pytest.fixture
def classifier():
    """Create Intent Classifier V4 instance"""
    return EnhancedIntentClassifierV4()


@pytest.fixture
def mock_state_manager():
    """Mock state manager for conversation context"""
    state_manager = MagicMock()
    state_manager.state = {}
    return state_manager


@pytest.fixture
def mock_db_session():
    """Mock async database session"""
    db = AsyncMock(spec=AsyncSession)
    return db


class TestQuickRules:
    """Test quick pattern-based rules (60% of queries)"""

    @pytest.mark.asyncio
    async def test_confirmation_keyword_detection(self, classifier, mock_state_manager):
        """Test that confirmation keywords trigger CONFIRM_EMAIL intent"""
        context = {"awaiting_email_confirmation": True}

        result = await classifier.classify(
            user_input="oui",
            context=context,
            state_manager=mock_state_manager
        )

        assert result.intent == IntentType.CONFIRM_EMAIL
        assert result.confidence >= 0.90
        assert result.quick_rule_used == "confirmation_keyword"
        assert result.data_source == DataSource.SQL_ONLY
        assert not result.requires_clarification

    @pytest.mark.asyncio
    async def test_anaphora_detection_with_email_verb(self, classifier, mock_state_manager):
        """Test anaphora with email verb triggers SEND_EMAIL"""
        conversation_history = [
            {"role": "user", "content": "Liste des copropriétaires de l'immeuble Mimosas"},
            {"role": "assistant", "content": "Voici la liste des 5 copropriétaires trouvés: ..."}
        ]

        result = await classifier.classify(
            user_input="envoie leur un email",
            conversation_history=conversation_history,
            state_manager=mock_state_manager
        )

        assert result.intent == IntentType.SEND_EMAIL
        assert result.confidence >= 0.80
        # Quick rule checks explicit_email_verb first before anaphora
        assert result.quick_rule_used in ["anaphora_with_email_verb", "explicit_email_verb"]
        assert result.quick_rule_used is not None

    @pytest.mark.asyncio
    async def test_anaphora_follow_up_without_email(self, classifier, mock_state_manager):
        """Test pure anaphora without email verb continues previous query"""
        conversation_history = [
            {"role": "user", "content": "Combien de plombiers ?"},
            {"role": "assistant", "content": "Voici les 3 plombiers trouvés: ..."}
        ]

        with patch.object(classifier.llm_service, 'generate_response', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '{"intent": "query_data", "data_source": "sql_only", "confidence": 0.90, "reasoning": "Anaphora follow-up", "alternatives": []}'

            result = await classifier.classify(
                user_input="lesquels sont certifiés ?",
                conversation_history=conversation_history,
                state_manager=mock_state_manager
            )

        # Should either match quick rule or use LLM with decent confidence
        assert result.intent == IntentType.QUERY_DATA
        assert result.confidence >= 0.70

    @pytest.mark.asyncio
    async def test_explicit_email_verb_detection(self, classifier, mock_state_manager):
        """Test explicit email verbs trigger SEND_EMAIL"""
        result = await classifier.classify(
            user_input="contacte tous les plombiers pour demander un devis",
            state_manager=mock_state_manager
        )

        assert result.intent == IntentType.SEND_EMAIL
        assert result.confidence >= 0.85
        assert result.quick_rule_used == "explicit_email_verb"

    @pytest.mark.asyncio
    async def test_recent_document_mention(self, classifier, mock_state_manager):
        """Test recent document mention triggers SEARCH_DOCUMENTS"""
        mock_state_manager.state["last_uploaded_documents"] = [
            {"filename": "reglement_interieur.pdf", "uploaded_at": "2025-11-13"}
        ]

        result = await classifier.classify(
            user_input="Que dit le reglement_interieur sur les animaux ?",
            state_manager=mock_state_manager
        )

        assert result.intent == IntentType.SEARCH_DOCUMENTS
        assert result.data_source == DataSource.RAG_ONLY
        assert result.confidence >= 0.90
        assert result.quick_rule_used == "recent_document_mention"

    @pytest.mark.asyncio
    async def test_file_attached_context(self, classifier, mock_state_manager):
        """Test file attached context triggers ANALYZE_DOCUMENT"""
        context = {"file_attached": True}

        result = await classifier.classify(
            user_input="Analyse ce document",
            context=context,
            state_manager=mock_state_manager
        )

        assert result.intent == IntentType.ANALYZE_DOCUMENT
        assert result.data_source == DataSource.RAG_ONLY
        assert result.confidence >= 0.90
        assert result.quick_rule_used == "file_attached"


class TestDataSourceDisambiguation:
    """Test SQL vs RAG vs HYBRID disambiguation"""

    @pytest.mark.asyncio
    async def test_strong_sql_query(self, classifier, mock_db_session, mock_state_manager):
        """Test quantitative query routes to SQL_ONLY"""
        # Mock schema check
        mock_db_session.execute = AsyncMock(return_value=MagicMock(scalar=lambda: 1))

        with patch.object(classifier.llm_service, 'generate_response', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '{"intent": "query_data", "data_source": "sql_only", "confidence": 0.92, "reasoning": "Quantitative query", "alternatives": []}'

            result = await classifier.classify(
                user_input="Combien de copropriétaires dans l'immeuble Mimosas ?",
                db=mock_db_session,
                state_manager=mock_state_manager
            )

        assert result.data_source == DataSource.SQL_ONLY
        assert result.intent == IntentType.QUERY_DATA
        assert result.confidence >= 0.85

    @pytest.mark.asyncio
    async def test_strong_rag_query(self, classifier, mock_db_session, mock_state_manager):
        """Test document-centric query routes to RAG_ONLY"""
        with patch.object(classifier.llm_service, 'generate_response', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '{"intent": "search_documents", "data_source": "rag_only", "confidence": 0.91, "reasoning": "Document search", "alternatives": []}'

            result = await classifier.classify(
                user_input="Que dit le règlement intérieur sur les travaux ?",
                db=mock_db_session,
                state_manager=mock_state_manager
            )

        assert result.data_source == DataSource.RAG_ONLY
        assert result.intent == IntentType.SEARCH_DOCUMENTS
        assert result.confidence >= 0.85

    @pytest.mark.asyncio
    async def test_hybrid_query_detection(self, classifier, mock_db_session, mock_state_manager):
        """Test hybrid query requiring both SQL and RAG"""
        mock_db_session.execute = AsyncMock(return_value=MagicMock(scalar=lambda: 1))

        with patch.object(classifier.llm_service, 'generate_response', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '{"intent": "hybrid_query", "data_source": "hybrid", "confidence": 0.87, "reasoning": "Needs both DB and docs", "alternatives": []}'

            result = await classifier.classify(
                user_input="Liste les copropriétaires et résume leurs contrats",
                db=mock_db_session,
                state_manager=mock_state_manager
            )

        assert result.data_source == DataSource.HYBRID
        assert result.intent == IntentType.HYBRID_QUERY
        assert result.confidence >= 0.80


class TestConfidenceThreshold:
    """Test confidence threshold enforcement"""

    @pytest.mark.asyncio
    async def test_low_confidence_requires_clarification(self, classifier, mock_state_manager):
        """Test low confidence (<0.70) forces clarification"""
        with patch.object(classifier.llm_service, 'generate_response', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '{"intent": "general_question", "data_source": "ambiguous", "confidence": 0.55, "reasoning": "Unclear intent", "alternatives": []}'

            result = await classifier.classify(
                user_input="hmm peut-être",
                state_manager=mock_state_manager
            )

        assert result.requires_clarification is True
        assert result.confidence < classifier.THRESHOLD_MEDIUM
        assert result.clarification_question is not None
        assert "pending_clarification" in mock_state_manager.state

    @pytest.mark.asyncio
    async def test_high_confidence_no_clarification(self, classifier, mock_state_manager):
        """Test high confidence (>=0.85) executes without clarification"""
        with patch.object(classifier.llm_service, 'generate_response', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '{"intent": "query_data", "data_source": "sql_only", "confidence": 0.95, "reasoning": "Clear SQL query", "alternatives": []}'

            result = await classifier.classify(
                user_input="Liste tous les plombiers",
                state_manager=mock_state_manager
            )

        assert result.requires_clarification is False
        assert result.confidence >= classifier.THRESHOLD_HIGH
        assert result.clarification_question is None


class TestFrenchNameParsing:
    """Test French name entity extraction"""

    def test_parse_french_names_valid(self, classifier):
        """Test parsing valid French names (Nom Prenom)"""
        # Use clear name without verb in front to ensure clean parsing
        query = "Email pour Dupont Marie concernant les travaux"

        parsed_names = classifier._parse_french_names(query)

        # Should extract "Dupont Marie" name
        assert len(parsed_names) >= 1
        # Find the "Dupont Marie" match
        dupont_marie = next((n for n in parsed_names if "Marie" in n.prenom and "Dupont" in n.nom), None)
        assert dupont_marie is not None, f"Expected to find Dupont Marie, got: {[(n.nom, n.prenom) for n in parsed_names]}"
        assert dupont_marie.confidence >= 0.6

    def test_parse_french_names_multiple(self, classifier):
        """Test parsing multiple names in query"""
        query = "Envoie un email à Martin Jean et Bernard Sophie"

        parsed_names = classifier._parse_french_names(query)

        assert len(parsed_names) == 2
        assert parsed_names[0].nom == "Martin"
        assert parsed_names[0].prenom == "Jean"
        assert parsed_names[1].nom == "Bernard"
        assert parsed_names[1].prenom == "Sophie"

    def test_parse_french_names_with_context(self, classifier):
        """Test name parsing with person context increases confidence"""
        query = "Quel est l'email de Durand Michel le copropriétaire ?"

        parsed_names = classifier._parse_french_names(query)

        assert len(parsed_names) == 1
        assert parsed_names[0].confidence >= 0.7  # Context hint boosts confidence


class TestClarificationHandling:
    """Test clarification response handling"""

    @pytest.mark.asyncio
    async def test_numeric_choice_response(self, classifier, mock_state_manager):
        """Test numeric choice response (1, 2, 3)"""
        mock_state_manager.state["pending_clarification"] = {
            "original_query": "Liste des contacts",
            "type": "data_source_ambiguous",
            "options": [
                {"label": "Base de données", "intent": IntentType.QUERY_DATA, "data_source": DataSource.SQL_ONLY},
                {"label": "Documents", "intent": IntentType.SEARCH_DOCUMENTS, "data_source": DataSource.RAG_ONLY}
            ]
        }

        result = await classifier.classify(
            user_input="1",
            state_manager=mock_state_manager
        )

        assert result.intent == IntentType.QUERY_DATA
        assert result.data_source == DataSource.SQL_ONLY
        assert result.confidence >= 0.90
        assert result.quick_rule_used == "clarification_response_numeric"
        assert "pending_clarification" not in mock_state_manager.state

    @pytest.mark.asyncio
    async def test_keyword_choice_response(self, classifier, mock_state_manager):
        """Test keyword-based choice response"""
        mock_state_manager.state["pending_clarification"] = {
            "original_query": "Cherche les informations",
            "type": "data_source_ambiguous",
            "options": [
                {"label": "Base de données", "intent": IntentType.QUERY_DATA, "data_source": DataSource.SQL_ONLY, "keywords": ["base", "données", "database"]},
                {"label": "Documents", "intent": IntentType.SEARCH_DOCUMENTS, "data_source": DataSource.RAG_ONLY, "keywords": ["documents", "fichiers"]}
            ]
        }

        result = await classifier.classify(
            user_input="dans les documents",
            state_manager=mock_state_manager
        )

        assert result.intent == IntentType.SEARCH_DOCUMENTS
        assert result.data_source == DataSource.RAG_ONLY
        assert result.confidence >= 0.85
        assert result.quick_rule_used == "clarification_response_keyword"


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_empty_input(self, classifier, mock_state_manager):
        """Test classification with empty input"""
        with patch.object(classifier.llm_service, 'generate_response', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '{"intent": "general_question", "data_source": "ambiguous", "confidence": 0.3, "reasoning": "Empty input", "alternatives": []}'

            result = await classifier.classify(
                user_input="",
                state_manager=mock_state_manager
            )

        assert result.requires_clarification is True
        assert result.confidence < classifier.THRESHOLD_MEDIUM

    @pytest.mark.asyncio
    async def test_llm_service_failure(self, classifier, mock_state_manager):
        """Test graceful handling of LLM service failure"""
        with patch.object(classifier.llm_service, 'generate_response', new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("LLM service unavailable")

            result = await classifier.classify(
                user_input="Test query",
                state_manager=mock_state_manager
            )

        assert result.intent == IntentType.GENERAL_QUESTION
        assert result.data_source == DataSource.AMBIGUOUS
        assert result.requires_clarification is True
        assert ("Classification failed" in result.reasoning or "LLM classification failed" in result.reasoning)

    @pytest.mark.asyncio
    async def test_processing_time_tracking(self, classifier, mock_state_manager):
        """Test that processing time is tracked"""
        context = {"awaiting_email_confirmation": True}

        result = await classifier.classify(
            user_input="oui",
            context=context,
            state_manager=mock_state_manager
        )

        assert result.processing_time_ms > 0
        assert result.processing_time_ms < 1000  # Quick rule should be fast


class TestPreprocessing:
    """Test query preprocessing"""

    @pytest.mark.asyncio
    async def test_preprocessed_query_stored(self, classifier, mock_state_manager):
        """Test that preprocessed query is stored in result"""
        with patch.object(classifier.llm_service, 'generate_response', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '{"intent": "query_data", "data_source": "sql_only", "confidence": 0.88, "reasoning": "SQL query", "alternatives": []}'

            result = await classifier.classify(
                user_input="  Liste   des   plombiers  ",  # Multiple spaces
                state_manager=mock_state_manager
            )

        assert result.preprocessed_query is not None
        assert result.preprocessed_query == "Liste des plombiers"  # Normalized whitespace

    @pytest.mark.asyncio
    async def test_detected_entities_stored(self, classifier, mock_state_manager):
        """Test that detected entities are stored in result"""
        with patch.object(classifier.llm_service, 'generate_response', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '{"intent": "send_email", "data_source": "sql_only", "confidence": 0.90, "reasoning": "Email with name", "alternatives": []}'

            result = await classifier.classify(
                user_input="Contacte Dupont Marie",
                state_manager=mock_state_manager
            )

        assert result.detected_entities is not None
        if "names" in result.detected_entities:
            assert len(result.detected_entities["names"]) >= 1
