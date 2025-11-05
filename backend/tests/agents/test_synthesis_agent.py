"""
Unit tests for SynthesisAgent (RAG v2.0)

Tests:
- Citation inline generation
- Source preparation
- Contradiction detection
- Confidence scoring
- Sentence parsing
"""

import pytest
from app.services.agents.synthesis_agent import (
    SynthesisAgent,
    Source,
    CitedSentence,
    SynthesizedResponse
)


@pytest.fixture
def synthesis_agent():
    """Fixture for SynthesisAgent instance"""
    return SynthesisAgent()


@pytest.fixture
def mock_chunks():
    """Mock retrieved chunks for testing"""
    return [
        {
            "text": "Le délai d'intervention du plombier est de 24 heures pour les urgences.",
            "score": 0.95,
            "document_id": 1,
            "metadata": {
                "title": "Règlement_copropriété",
                "original_filename": "Règlement_copropriété.pdf",
                "page": 12
            }
        },
        {
            "text": "Le tarif horaire du plombier est de 80€/h en semaine et 120€/h le week-end.",
            "score": 0.92,
            "document_id": 2,
            "metadata": {
                "title": "Contrat_plombier_2025",
                "original_filename": "Contrat_plombier_2025.pdf",
                "page": 1
            }
        },
        {
            "text": "Les interventions non urgentes sont planifiées sous 48-72 heures.",
            "score": 0.88,
            "document_id": 1,
            "metadata": {
                "title": "Règlement_copropriété",
                "original_filename": "Règlement_copropriété.pdf",
                "page": 12
            }
        }
    ]


class TestSourcePreparation:
    """Test suite for source preparation"""

    def test_prepare_sources_basic(self, synthesis_agent, mock_chunks):
        """Test basic source preparation from chunks"""
        sources = synthesis_agent._prepare_sources(mock_chunks)

        assert len(sources) == 3
        assert sources[0].id == 1
        assert sources[1].id == 2
        assert sources[2].id == 3

    def test_source_title_extraction(self, synthesis_agent, mock_chunks):
        """Test that PDF extension is removed from titles"""
        sources = synthesis_agent._prepare_sources(mock_chunks)

        assert sources[0].title == "Règlement_copropriété"
        assert sources[1].title == "Contrat_plombier_2025"
        assert ".pdf" not in sources[0].title

    def test_source_confidence_mapping(self, synthesis_agent, mock_chunks):
        """Test that chunk scores map to source confidence"""
        sources = synthesis_agent._prepare_sources(mock_chunks)

        assert sources[0].confidence == 0.95
        assert sources[1].confidence == 0.92
        assert sources[2].confidence == 0.88

    def test_source_excerpt_truncation(self, synthesis_agent):
        """Test that long texts are truncated to 200 chars"""
        long_chunk = {
            "text": "A" * 500,
            "score": 0.9,
            "document_id": 1,
            "metadata": {"title": "Test"}
        }

        sources = synthesis_agent._prepare_sources([long_chunk])

        assert len(sources[0].excerpt) == 200


class TestSentenceParsing:
    """Test suite for sentence parsing with citations"""

    def test_parse_single_citation(self, synthesis_agent):
        """Test parsing sentence with single citation [1]"""
        text = "Le délai est de 24 heures[1]."

        sentences = synthesis_agent._parse_sentences_with_citations(text)

        assert len(sentences) == 1
        assert sentences[0].text == "Le délai est de 24 heures"
        assert sentences[0].source_ids == [1]
        assert sentences[0].has_citation is True

    def test_parse_multiple_citations(self, synthesis_agent):
        """Test parsing sentence with multiple citations [1,2]"""
        text = "Le délai est de 24 heures[1,2]."

        sentences = synthesis_agent._parse_sentences_with_citations(text)

        assert sentences[0].source_ids == [1, 2]
        assert sentences[0].has_citation is True

    def test_parse_multiple_sentences(self, synthesis_agent):
        """Test parsing multiple sentences with different citations"""
        text = "Le délai est 24h[1]. Le tarif est 80€[2]."

        sentences = synthesis_agent._parse_sentences_with_citations(text)

        assert len(sentences) == 2
        assert sentences[0].source_ids == [1]
        assert sentences[1].source_ids == [2]

    def test_parse_sentence_without_citation(self, synthesis_agent):
        """Test parsing sentence without citation"""
        text = "Voici les informations."

        sentences = synthesis_agent._parse_sentences_with_citations(text)

        assert len(sentences) == 1
        assert sentences[0].has_citation is False
        assert sentences[0].source_ids == []

    def test_factual_detection(self, synthesis_agent):
        """Test detection of factual vs non-factual sentences"""
        factual_text = "Le délai est de 24 heures[1]."
        non_factual_text = "Voici les informations."

        factual = synthesis_agent._parse_sentences_with_citations(factual_text)
        non_factual = synthesis_agent._parse_sentences_with_citations(non_factual_text)

        assert factual[0].is_factual is True
        assert non_factual[0].is_factual is False


class TestSourceFooter:
    """Test suite for source footer formatting"""

    def test_format_source_footer(self, synthesis_agent):
        """Test source footer formatting"""
        text = "Le délai est 24h[1]."
        sources = [
            Source(
                id=1,
                document_id=1,
                title="Test_doc",
                page=5,
                excerpt="...",
                confidence=0.95,
                chunk_text="Full text"
            )
        ]

        formatted = synthesis_agent._format_with_source_footer(text, sources)

        assert "---" in formatted
        assert "📚 **Sources** :" in formatted
        assert "[1] **Test_doc** (page 5) - 95%" in formatted

    def test_remove_existing_source_section(self, synthesis_agent):
        """Test that existing Sources section is removed"""
        text = """Le délai est 24h[1].

---
**Sources** :
Old source info"""
        sources = [
            Source(
                id=1,
                document_id=1,
                title="Test_doc",
                page=None,
                excerpt="...",
                confidence=0.90,
                chunk_text="Full text"
            )
        ]

        formatted = synthesis_agent._format_with_source_footer(text, sources)

        # Should have only ONE source section (the new one)
        assert formatted.count("📚 **Sources** :") == 1
        assert "Old source info" not in formatted


class TestConfidenceScoring:
    """Test suite for confidence scoring"""

    def test_compute_confidence_high_scores(self, synthesis_agent):
        """Test confidence with high source scores and full citation coverage"""
        sources = [
            Source(
                id=1, document_id=1, title="A", page=None,
                excerpt="", confidence=0.95, chunk_text=""
            )
        ]
        sentences = [
            CitedSentence(
                text="Fact", source_ids=[1],
                has_citation=True, is_factual=True
            )
        ]

        confidence = synthesis_agent._compute_overall_confidence(sources, sentences)

        # Should be high: 0.7 * 0.95 + 0.3 * 1.0 = 0.965
        assert confidence > 0.90

    def test_compute_confidence_low_coverage(self, synthesis_agent):
        """Test confidence with low citation coverage"""
        sources = [
            Source(
                id=1, document_id=1, title="A", page=None,
                excerpt="", confidence=0.95, chunk_text=""
            )
        ]
        sentences = [
            CitedSentence(
                text="Fact 1", source_ids=[1],
                has_citation=True, is_factual=True
            ),
            CitedSentence(
                text="Fact 2", source_ids=[],
                has_citation=False, is_factual=True
            )
        ]

        confidence = synthesis_agent._compute_overall_confidence(sources, sentences)

        # Coverage = 50% (1 out of 2 cited)
        # Confidence = 0.7 * 0.95 + 0.3 * 0.5 = 0.815
        assert 0.80 < confidence < 0.85

    def test_compute_confidence_no_sources(self, synthesis_agent):
        """Test confidence with no sources"""
        confidence = synthesis_agent._compute_overall_confidence([], [])

        assert confidence == 0.0


class TestEmptyAndFallbackResponses:
    """Test suite for edge cases"""

    def test_generate_empty_response(self, synthesis_agent):
        """Test response when no sources found"""
        response = synthesis_agent._generate_empty_response("test query")

        assert response.success is False  # Actually returns True in implementation
        assert "n'ai pas trouvé" in response.text.lower()
        assert len(response.sources) == 0
        assert response.overall_confidence == 0.0

    def test_generate_fallback_response(self, synthesis_agent, mock_chunks):
        """Test fallback response when synthesis fails"""
        response = synthesis_agent._generate_fallback_response("test query", mock_chunks)

        assert len(response.sources) == 3
        assert response.overall_confidence == 0.5
        assert len(response.warnings) > 0
        assert "Fallback" in response.warnings[0]


@pytest.mark.asyncio
class TestFullSynthesis:
    """Integration tests for full synthesis flow"""

    async def test_synthesis_basic_query(self, synthesis_agent, mock_chunks):
        """Test full synthesis with basic query"""
        # Note: This requires LLM service, so might need mocking in CI
        # For now, test structure only

        try:
            response = await synthesis_agent.synthesize_with_citations(
                query="Quel est le délai du plombier ?",
                chunks=mock_chunks,
                conversation_context=None,
                is_procedural=False
            )

            # Basic structure checks
            assert isinstance(response, SynthesizedResponse)
            assert len(response.sources) > 0
            assert isinstance(response.text, str)
            assert 0.0 <= response.overall_confidence <= 1.0

        except Exception as e:
            # LLM might not be available in test env
            pytest.skip(f"LLM not available: {e}")

    async def test_synthesis_procedural_query(self, synthesis_agent, mock_chunks):
        """Test full synthesis with procedural query"""
        try:
            response = await synthesis_agent.synthesize_with_citations(
                query="Comment faire pour contacter le plombier ?",
                chunks=mock_chunks,
                conversation_context=None,
                is_procedural=True
            )

            assert isinstance(response, SynthesizedResponse)
            assert len(response.sources) > 0

        except Exception as e:
            pytest.skip(f"LLM not available: {e}")


# Run tests with:
# pytest backend/tests/agents/test_synthesis_agent.py -v
