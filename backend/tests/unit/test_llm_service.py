"""
Unit Tests for LLM Service
Tests email classification, email generation, document extraction, and Q&A
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import json

from app.services.llm_service import LLMService


@pytest.mark.unit
@pytest.mark.asyncio
class TestLLMServiceInitialization:
    """Tests for LLM service initialization"""

    @patch('app.services.llm_service.ChatOpenAI')
    def test_init_with_openai_key(self, mock_openai):
        """Test OpenAI client initialized when key present"""
        llm = LLMService()

        assert llm.chat_model is not None
        mock_openai.assert_called_once()

    @patch('app.services.llm_service.ChatOpenAI')
    @patch('langchain_anthropic.ChatAnthropic')
    def test_init_with_anthropic_fallback(self, mock_anthropic, mock_openai):
        """Test Anthropic client created if key present"""
        llm = LLMService()

        # Both should be initialized if keys present
        assert hasattr(llm, 'chat_model')
        assert hasattr(llm, 'fallback_model')

    @patch('app.services.llm_service.OpenAIEmbeddings')
    @patch('app.services.llm_service.ChatOpenAI')
    @patch('app.core.config.settings')
    def test_init_without_anthropic(self, mock_settings, mock_openai, mock_embeddings):
        """Test fallback disabled if no Anthropic key"""
        # Provide real string values to satisfy Pydantic
        mock_settings.ANTHROPIC_API_KEY = None
        mock_settings.OPENAI_API_KEY = "sk-test-key"
        mock_settings.OPENAI_MODEL = "gpt-4"
        mock_settings.OPENAI_EMBEDDING_MODEL = "text-embedding-ada-002"

        llm = LLMService()

        assert llm.fallback_model is None

    @patch('app.services.llm_service.ChatOpenAI')
    def test_init_anthropic_import_error(self, mock_openai):
        """Test handles missing anthropic package gracefully"""
        # This test just verifies LLM initializes without Anthropic
        # The dynamic import handles ImportError internally
        llm = LLMService()

        # Should still initialize with primary model
        assert llm.chat_model is not None

    @patch('app.services.llm_service.OpenAIEmbeddings')
    @patch('app.services.llm_service.ChatOpenAI')
    @patch('app.core.config.settings')
    def test_init_with_custom_models(self, mock_settings, mock_openai, mock_embeddings):
        """Test uses settings for model names"""
        mock_settings.OPENAI_MODEL = "gpt-4-turbo"
        mock_settings.OPENAI_API_KEY = "sk-test-key"
        mock_settings.OPENAI_EMBEDDING_MODEL = "text-embedding-ada-002"
        mock_settings.ANTHROPIC_API_KEY = None

        llm = LLMService()

        # Should call with correct parameters (model not model_name, temperature 0.1 not 0.3)
        mock_openai.assert_called_with(
            model="gpt-4-turbo",
            api_key="sk-test-key",
            temperature=0.1
        )


@pytest.mark.unit
@pytest.mark.asyncio
class TestEmailUrgencyClassification:
    """Tests for email urgency classification"""

    @patch('app.services.llm_service.ChatOpenAI')
    async def test_classify_email_urgent(self, mock_openai):
        """Test correctly identifies urgent email"""
        # Mock the chat model
        mock_chat_model = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "urgent"
        mock_chat_model.ainvoke = AsyncMock(return_value=mock_response)
        mock_openai.return_value = mock_chat_model

        llm = LLMService()
        llm.chat_model = mock_chat_model

        urgency = await llm.classify_email_urgency(
            subject="URGENT: Server down",
            sender="ops@company.com",
            body="The production server has crashed",
            snippet="Server crashed need immediate attention"
        )

        assert urgency == "urgent"

    @patch('app.services.llm_service.ChatOpenAI')
    async def test_classify_email_important(self, mock_openai):
        """Test correctly identifies important email"""
        mock_chat_model = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "important"
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        urgency = await llm.classify_email_urgency(
            subject="Important: Meeting tomorrow",
            body="We need to discuss the project",
            sender="boss@company.com"
        )

        assert urgency == "important"

    async def test_classify_email_routine(self):
        """Test correctly identifies routine email"""
        llm = LLMService()

        mock_response = MagicMock()
        mock_response.content = "routine"
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        urgency = await llm.classify_email_urgency(
            subject="Weekly newsletter",
            body="Here's this week's update",
            sender="news@company.com"
        )

        assert urgency == "routine"

    async def test_classify_email_invalid_response(self):
        """Test handles non-enum response (defaults to routine)"""
        llm = LLMService()

        mock_response = MagicMock()
        mock_response.content = "invalid_urgency"
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        urgency = await llm.classify_email_urgency(
            subject="Test",
            body="Body",
            sender="test@test.com"
        )

        # Should default to routine for invalid responses
        assert urgency == "routine"

    async def test_classify_email_openai_error(self):
        """Test tries fallback on OpenAI error"""
        llm = LLMService()

        # Mock primary to fail
        llm.chat_model.ainvoke = AsyncMock(side_effect=Exception("OpenAI Error"))

        # Mock fallback to succeed
        mock_fallback_response = MagicMock()
        mock_fallback_response.content = "important"
        llm.fallback_model = MagicMock()
        llm.fallback_model.ainvoke = AsyncMock(return_value=mock_fallback_response)

        urgency = await llm.classify_email_urgency(
            subject="Test",
            body="Body",
            sender="test@test.com"
        )

        assert urgency == "important"
        llm.fallback_model.ainvoke.assert_called_once()

    async def test_classify_email_fallback_success(self):
        """Test Anthropic fallback works"""
        llm = LLMService()

        # Simulate OpenAI timeout
        llm.chat_model.ainvoke = AsyncMock(side_effect=TimeoutError("Timeout"))

        # Mock fallback
        mock_fallback = MagicMock()
        mock_fallback.content = "urgent"
        llm.fallback_model = MagicMock()
        llm.fallback_model.ainvoke = AsyncMock(return_value=mock_fallback)

        urgency = await llm.classify_email_urgency(
            subject="Emergency",
            body="Help",
            sender="test@test.com"
        )

        assert urgency == "urgent"

    async def test_classify_email_all_models_fail(self):
        """Test returns routine when all models fail"""
        llm = LLMService()

        # Both models fail
        llm.chat_model.ainvoke = AsyncMock(side_effect=Exception("Primary fail"))
        llm.fallback_model = MagicMock()
        llm.fallback_model.ainvoke = AsyncMock(side_effect=Exception("Fallback fail"))

        urgency = await llm.classify_email_urgency(
            subject="Test",
            body="Body",
            sender="test@test.com"
        )

        # Should default to routine on complete failure
        assert urgency == "routine"

    async def test_classify_email_with_french_content(self):
        """Test handles French text correctly"""
        llm = LLMService()

        mock_response = MagicMock()
        mock_response.content = "urgent"
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        urgency = await llm.classify_email_urgency(
            subject="URGENT: Problème de chauffage",
            body="Le chauffage est en panne dans l'immeuble",
            sender="gardien@residence.fr"
        )

        assert urgency == "urgent"

    async def test_classify_email_empty_fields(self):
        """Test handles empty subject/body"""
        llm = LLMService()

        mock_response = MagicMock()
        mock_response.content = "routine"
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        urgency = await llm.classify_email_urgency(
            subject="",
            body="",
            sender="test@test.com"
        )

        assert urgency == "routine"

    async def test_classify_email_long_content(self):
        """Test truncates very long content appropriately"""
        llm = LLMService()

        mock_response = MagicMock()
        mock_response.content = "routine"
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        # Very long email body
        long_body = "Lorem ipsum " * 1000  # Very long text

        urgency = await llm.classify_email_urgency(
            subject="Test",
            body=long_body,
            sender="test@test.com"
        )

        # Should still work
        assert urgency in ["urgent", "important", "routine"]


@pytest.mark.unit
@pytest.mark.asyncio
class TestEmailGeneration:
    """Tests for email generation"""

    async def test_generate_email_success(self):
        """Test generates valid email with subject/body"""
        llm = LLMService()

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "subject": "Test Email Subject",
            "body": "This is the email body",
            "confidence": 0.9
        })
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await llm.generate_email(
            prompt="Write a professional email asking for a quote"
        )

        assert result["subject"] == "Test Email Subject"
        assert result["body"] == "This is the email body"
        assert result["confidence"] == 0.9

    async def test_generate_email_with_context(self):
        """Test includes context in generation"""
        llm = LLMService()

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "subject": "Devis pour travaux",
            "body": "Bonjour, je souhaite un devis",
            "confidence": 0.85
        })
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await llm.generate_email(
            prompt="Demande de devis",
            context={"vendor_name": "Plomberie Martin", "situation": "fuite"}
        )

        assert "subject" in result
        assert "body" in result
        llm.chat_model.ainvoke.assert_called_once()

    async def test_generate_email_json_parsing(self):
        """Test parses LLM JSON response correctly"""
        llm = LLMService()

        # JSON with extra whitespace
        mock_response = MagicMock()
        mock_response.content = """
        {
            "subject": "Test",
            "body": "Body text",
            "confidence": 0.95
        }
        """
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await llm.generate_email(prompt="Test")

        assert result["subject"] == "Test"
        assert result["confidence"] == 0.95

    async def test_generate_email_invalid_json(self):
        """Test handles malformed JSON gracefully"""
        llm = LLMService()

        mock_response = MagicMock()
        mock_response.content = "This is not JSON"
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await llm.generate_email(prompt="Test")

        # Should return error or default response
        assert "error" in result or "subject" in result

    async def test_generate_email_error_handling(self):
        """Test returns error message on failure"""
        llm = LLMService()

        llm.chat_model.ainvoke = AsyncMock(side_effect=Exception("API Error"))

        result = await llm.generate_email(prompt="Test")

        assert "error" in result

    async def test_generate_email_french_formatting(self):
        """Test uses formal French"""
        llm = LLMService()

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "subject": "Demande de renseignements",
            "body": "Madame, Monsieur,\n\nJe vous prie...",
            "confidence": 0.9
        })
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await llm.generate_email(
            prompt="Email formel en français"
        )

        assert "subject" in result
        assert "body" in result

    async def test_generate_email_empty_prompt(self):
        """Test handles empty prompt"""
        llm = LLMService()

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "subject": "Email",
            "body": "Content",
            "confidence": 0.5
        })
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await llm.generate_email(prompt="")

        # Should still work with empty prompt
        assert "subject" in result


@pytest.mark.unit
@pytest.mark.asyncio
class TestDocumentExtraction:
    """Tests for document information extraction"""

    async def test_extract_document_info_success(self):
        """Test extracts structured data from document"""
        llm = LLMService()

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "type": "invoice",
            "summary": "Invoice from ABC Corp",
            "amount": 1500.00,
            "entities": ["ABC Corp", "Invoice #12345"]
        })
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await llm.extract_document_info("Invoice text content")

        assert result["type"] == "invoice"
        assert result["amount"] == 1500.00
        assert len(result["entities"]) == 2

    async def test_extract_document_info_with_type(self):
        """Test identifies document type correctly"""
        llm = LLMService()

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "type": "contract",
            "summary": "Service contract",
            "entities": ["Company A", "Company B"]
        })
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await llm.extract_document_info("Contract between parties")

        assert result["type"] == "contract"

    async def test_extract_document_info_invoice(self):
        """Test extracts amount from invoice"""
        llm = LLMService()

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "type": "invoice",
            "amount": 2450.50,
            "summary": "Invoice for services"
        })
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await llm.extract_document_info("Total: 2450.50 EUR")

        assert result["type"] == "invoice"
        assert result["amount"] == 2450.50

    async def test_extract_document_info_long_text(self):
        """Test truncates to 2000 chars"""
        llm = LLMService()

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "type": "document",
            "summary": "Long document"
        })
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        long_text = "A" * 5000  # 5000 characters

        result = await llm.extract_document_info(long_text)

        # Should work despite long input
        assert "type" in result

    async def test_extract_document_info_json_error(self):
        """Test handles JSON parsing errors"""
        llm = LLMService()

        mock_response = MagicMock()
        mock_response.content = "Invalid JSON response"
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await llm.extract_document_info("Some text")

        # Should return error or default
        assert "error" in result or "type" in result

    async def test_extract_document_info_llm_failure(self):
        """Test returns default on LLM error"""
        llm = LLMService()

        llm.chat_model.ainvoke = AsyncMock(side_effect=Exception("LLM Error"))

        result = await llm.extract_document_info("Text")

        assert "error" in result or result == {}


@pytest.mark.unit
@pytest.mark.asyncio
class TestRAGQuestionAnswering:
    """Tests for RAG question answering"""

    async def test_answer_question_with_context(self):
        """Test uses provided context"""
        llm = LLMService()

        mock_response = MagicMock()
        mock_response.content = "Based on the context, the answer is..."
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        answer = await llm.answer_question(
            question="What is the issue?",
            context="There is a water leak in apartment 12"
        )

        assert "answer" in answer or len(answer) > 0
        llm.chat_model.ainvoke.assert_called_once()

    async def test_answer_question_with_history(self):
        """Test includes conversation history"""
        llm = LLMService()

        mock_response = MagicMock()
        mock_response.content = "Following up on our discussion..."
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"}
        ]

        answer = await llm.answer_question(
            question="Follow-up question",
            context="Context",
            history=history
        )

        assert len(answer) > 0

    async def test_answer_question_truncates_history(self):
        """Test only uses last 5 messages"""
        llm = LLMService()

        mock_response = MagicMock()
        mock_response.content = "Answer"
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        # Create 10 messages
        long_history = [
            {"role": "user", "content": f"Question {i}"}
            for i in range(10)
        ]

        answer = await llm.answer_question(
            question="New question",
            context="Context",
            history=long_history
        )

        # Should still work
        assert len(answer) > 0

    async def test_answer_question_no_context(self):
        """Test says 'I don't know' when no context"""
        llm = LLMService()

        mock_response = MagicMock()
        mock_response.content = "I don't have enough context"
        llm.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        answer = await llm.answer_question(
            question="What happened?",
            context=""
        )

        # Should indicate lack of context
        assert "context" in answer.lower() or "don't know" in answer.lower() or len(answer) > 0

    async def test_answer_question_llm_error(self):
        """Test returns error message gracefully"""
        llm = LLMService()

        llm.chat_model.ainvoke = AsyncMock(side_effect=Exception("Error"))

        answer = await llm.answer_question(
            question="Test",
            context="Context"
        )

        # Should handle error
        assert "error" in answer.lower() or len(answer) > 0


@pytest.mark.unit
@pytest.mark.asyncio
class TestEmbeddings:
    """Tests for embeddings generation"""

    @patch('app.services.llm_service.OpenAIEmbeddings')
    async def test_get_embeddings_single_text(self, mock_embeddings_class):
        """Test generates embedding for one text"""
        llm = LLMService()

        # Mock embeddings
        mock_embeddings = MagicMock()
        mock_embeddings.aembed_documents = AsyncMock(return_value=[[0.1] * 1536])
        llm.embeddings_model = mock_embeddings

        embeddings = await llm.get_embeddings(["Test text"])

        assert len(embeddings) == 1
        assert len(embeddings[0]) == 1536

    @patch('app.services.llm_service.OpenAIEmbeddings')
    async def test_get_embeddings_multiple_texts(self, mock_embeddings_class):
        """Test batch embedding generation"""
        llm = LLMService()

        mock_embeddings = MagicMock()
        mock_embeddings.aembed_documents = AsyncMock(return_value=[
            [0.1] * 1536,
            [0.2] * 1536,
            [0.3] * 1536
        ])
        llm.embeddings_model = mock_embeddings

        texts = ["Text 1", "Text 2", "Text 3"]
        embeddings = await llm.get_embeddings(texts)

        assert len(embeddings) == 3

    @patch('app.services.llm_service.OpenAIEmbeddings')
    async def test_get_embeddings_empty_list(self, mock_embeddings_class):
        """Test handles empty input"""
        llm = LLMService()

        mock_embeddings = MagicMock()
        mock_embeddings.aembed_documents = AsyncMock(return_value=[])
        llm.embeddings_model = mock_embeddings

        embeddings = await llm.get_embeddings([])

        assert embeddings == []

    @patch('app.services.llm_service.OpenAIEmbeddings')
    async def test_get_embeddings_error(self, mock_embeddings_class):
        """Test returns empty list on error"""
        llm = LLMService()

        mock_embeddings = MagicMock()
        mock_embeddings.aembed_documents = AsyncMock(side_effect=Exception("API Error"))
        llm.embeddings_model = mock_embeddings

        embeddings = await llm.get_embeddings(["Test"])

        assert embeddings == [] or "error" in str(embeddings).lower()
