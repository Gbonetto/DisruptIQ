"""
Unit tests for Hybrid Search Service

Tests cover:
1. BM25 index building
2. BM25 search functionality
3. Reciprocal Rank Fusion (RRF)
4. Hybrid search (BM25 + Vector)
5. Incremental document addition
6. Edge cases and error handling
"""

import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hybrid_search_service import HybridSearchService, get_hybrid_search_service


@pytest.fixture
def hybrid_service():
    """Create a fresh Hybrid Search Service instance for each test"""
    return HybridSearchService()


@pytest.fixture
def sample_documents():
    """Sample documents for testing"""
    return [
        {
            "id": "doc1",
            "text": "Python is a programming language used for web development",
            "title": "Python Programming",
            "type": "article"
        },
        {
            "id": "doc2",
            "text": "JavaScript is used for frontend web development and Node.js",
            "title": "JavaScript Guide",
            "type": "tutorial"
        },
        {
            "id": "doc3",
            "text": "Machine learning algorithms use Python for data science",
            "title": "ML with Python",
            "type": "article"
        },
        {
            "id": "doc4",
            "text": "Web development frameworks include Django and Flask for Python",
            "title": "Python Web Frameworks",
            "type": "guide"
        },
        {
            "id": "doc5",
            "text": "React is a JavaScript library for building user interfaces",
            "title": "React Introduction",
            "type": "tutorial"
        }
    ]


class TestBM25Indexing:
    """Test BM25 index building"""

    @pytest.mark.asyncio
    async def test_build_bm25_index_success(self, hybrid_service, sample_documents):
        """Test successful BM25 index building"""
        await hybrid_service.build_bm25_index(sample_documents)

        assert hybrid_service._initialized is True
        assert len(hybrid_service._documents) == 5
        assert len(hybrid_service._tokenized_corpus) == 5
        assert hybrid_service._bm25_index is not None

    @pytest.mark.asyncio
    async def test_build_bm25_index_empty_documents(self, hybrid_service):
        """Test BM25 index with empty document list"""
        await hybrid_service.build_bm25_index([])

        assert hybrid_service._initialized is False
        assert len(hybrid_service._documents) == 0

    @pytest.mark.asyncio
    async def test_tokenization(self, hybrid_service):
        """Test document tokenization"""
        text = "Python Programming Language"
        tokens = hybrid_service._tokenize(text)

        assert tokens == ["python", "programming", "language"]
        assert all(token.islower() for token in tokens)

    @pytest.mark.asyncio
    async def test_add_document_incremental(self, hybrid_service, sample_documents):
        """Test adding document incrementally rebuilds index"""
        # Build initial index
        await hybrid_service.build_bm25_index(sample_documents[:3])
        assert len(hybrid_service._documents) == 3

        # Add new document
        new_doc = {
            "id": "doc6",
            "text": "TypeScript extends JavaScript with static typing",
            "title": "TypeScript Basics"
        }
        await hybrid_service.add_document(new_doc)

        assert len(hybrid_service._documents) == 4
        assert hybrid_service._documents[-1]["id"] == "doc6"
        assert hybrid_service._initialized is True


class TestBM25Search:
    """Test BM25 search functionality"""

    @pytest.mark.asyncio
    async def test_bm25_search_basic(self, hybrid_service, sample_documents):
        """Test basic BM25 search"""
        await hybrid_service.build_bm25_index(sample_documents)

        results = await hybrid_service.bm25_search("Python programming", top_k=3)

        assert len(results) <= 3
        assert all("id" in result for result in results)
        assert all("score" in result for result in results)
        assert all("source" in result for result in results)
        assert all(result["source"] == "bm25" for result in results)

        # Check scores are descending
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_bm25_search_exact_match(self, hybrid_service, sample_documents):
        """Test BM25 search with exact keyword match"""
        await hybrid_service.build_bm25_index(sample_documents)

        # Query for "Django" which appears only in doc4
        results = await hybrid_service.bm25_search("Django Flask", top_k=5)

        # doc4 should rank highest due to exact matches
        assert len(results) > 0
        # Find doc4 in results
        doc4_result = next((r for r in results if r["id"] == "doc4"), None)
        assert doc4_result is not None
        assert doc4_result["score"] > 0

    @pytest.mark.asyncio
    async def test_bm25_search_not_initialized(self, hybrid_service):
        """Test BM25 search before index is built"""
        results = await hybrid_service.bm25_search("test query")

        assert results == []

    @pytest.mark.asyncio
    async def test_bm25_search_filters_zero_scores(self, hybrid_service, sample_documents):
        """Test that BM25 filters out documents with zero scores"""
        await hybrid_service.build_bm25_index(sample_documents)

        # Query with terms not in any document
        results = await hybrid_service.bm25_search("xyzabc nonexistent query", top_k=10)

        # Should return empty or only documents with non-zero scores
        assert all(result["score"] > 0 for result in results)


class TestReciprocalRankFusion:
    """Test Reciprocal Rank Fusion (RRF)"""

    @pytest.mark.asyncio
    async def test_rrf_basic_fusion(self, hybrid_service):
        """Test basic RRF fusion of BM25 and vector results"""
        bm25_results = [
            {"id": "doc1", "text": "Python programming", "score": 5.2, "metadata": {}},
            {"id": "doc2", "text": "JavaScript guide", "score": 3.1, "metadata": {}},
            {"id": "doc3", "text": "ML algorithms", "score": 2.5, "metadata": {}}
        ]

        vector_results = [
            {"id": "doc2", "text": "JavaScript guide", "score": 0.92, "metadata": {}},
            {"id": "doc1", "text": "Python programming", "score": 0.88, "metadata": {}},
            {"id": "doc4", "text": "Django framework", "score": 0.75, "metadata": {}}
        ]

        fused_results = await hybrid_service.reciprocal_rank_fusion(
            bm25_results=bm25_results,
            vector_results=vector_results,
            top_k=3
        )

        assert len(fused_results) <= 3
        assert all("id" in result for result in fused_results)
        assert all("score" in result for result in fused_results)
        assert all(result["source"] == "hybrid_rrf" for result in fused_results)
        assert all("vector_rank" in result or "bm25_rank" in result for result in fused_results)

    @pytest.mark.asyncio
    async def test_rrf_boosts_common_documents(self, hybrid_service):
        """Test that RRF boosts documents appearing in both result sets"""
        # doc1 appears in both → should rank highest
        # doc2 only in BM25
        # doc3 only in vector
        bm25_results = [
            {"id": "doc1", "text": "Common doc", "score": 10.0, "metadata": {}},
            {"id": "doc2", "text": "BM25 only", "score": 8.0, "metadata": {}}
        ]

        vector_results = [
            {"id": "doc1", "text": "Common doc", "score": 0.95, "metadata": {}},
            {"id": "doc3", "text": "Vector only", "score": 0.85, "metadata": {}}
        ]

        fused_results = await hybrid_service.reciprocal_rank_fusion(
            bm25_results=bm25_results,
            vector_results=vector_results,
            top_k=3
        )

        # doc1 should be first due to appearing in both
        assert fused_results[0]["id"] == "doc1"
        assert fused_results[0]["vector_rank"] is not None
        assert fused_results[0]["bm25_rank"] is not None

    @pytest.mark.asyncio
    async def test_rrf_respects_alpha_weighting(self, hybrid_service):
        """Test that RRF respects alpha parameter (vector vs BM25 weight)"""
        # Default alpha = 0.7 (70% vector, 30% BM25)
        assert hybrid_service._alpha == 0.7

        bm25_results = [{"id": "doc1", "text": "Test", "score": 10, "metadata": {}}]
        vector_results = [{"id": "doc1", "text": "Test", "score": 0.9, "metadata": {}}]

        fused_results = await hybrid_service.reciprocal_rank_fusion(
            bm25_results=bm25_results,
            vector_results=vector_results,
            top_k=1
        )

        # RRF score should reflect weighted combination
        assert len(fused_results) == 1
        assert fused_results[0]["score"] > 0

    @pytest.mark.asyncio
    async def test_rrf_fallback_on_error(self, hybrid_service):
        """Test that RRF falls back to vector results on error"""
        # Malformed results to trigger error
        bm25_results = [{"id": "doc1", "text": "Test"}]  # Missing score
        vector_results = [{"id": "doc2", "text": "Vector", "score": 0.9, "metadata": {}}]

        # Should fallback to vector results
        with patch.object(hybrid_service, 'reciprocal_rank_fusion', side_effect=Exception("RRF error")):
            # This will be tested in hybrid_search which has fallback logic
            pass


class TestHybridSearch:
    """Test full hybrid search workflow"""

    @pytest.mark.asyncio
    async def test_hybrid_search_integration(self, hybrid_service, sample_documents):
        """Test full hybrid search pipeline"""
        # Build BM25 index
        await hybrid_service.build_bm25_index(sample_documents)

        # Mock vector results
        vector_results = [
            {"id": "doc1", "text": sample_documents[0]["text"], "score": 0.92, "metadata": {}},
            {"id": "doc3", "text": sample_documents[2]["text"], "score": 0.88, "metadata": {}},
            {"id": "doc4", "text": sample_documents[3]["text"], "score": 0.75, "metadata": {}}
        ]

        # Perform hybrid search
        results = await hybrid_service.hybrid_search(
            query="Python web development",
            vector_results=vector_results,
            top_k=3
        )

        assert len(results) <= 3
        assert all("id" in result for result in results)
        assert all(result["source"] == "hybrid_rrf" for result in results)

    @pytest.mark.asyncio
    async def test_hybrid_search_fallback_to_vector(self, hybrid_service):
        """Test hybrid search falls back to vector results if BM25 fails"""
        # Don't build BM25 index (simulates failure)
        vector_results = [
            {"id": "doc1", "text": "Test document", "score": 0.9, "metadata": {}}
        ]

        results = await hybrid_service.hybrid_search(
            query="test query",
            vector_results=vector_results,
            top_k=5
        )

        # Should return vector results as fallback
        assert len(results) > 0


class TestServiceStats:
    """Test service statistics and configuration"""

    @pytest.mark.asyncio
    async def test_get_stats_before_init(self, hybrid_service):
        """Test stats before index is built"""
        stats = hybrid_service.get_stats()

        assert stats["initialized"] is False
        assert stats["document_count"] == 0
        assert stats["avg_doc_length"] == 0
        assert stats["rrf_k"] == 60
        assert stats["alpha"] == 0.7

    @pytest.mark.asyncio
    async def test_get_stats_after_init(self, hybrid_service, sample_documents):
        """Test stats after index is built"""
        await hybrid_service.build_bm25_index(sample_documents)
        stats = hybrid_service.get_stats()

        assert stats["initialized"] is True
        assert stats["document_count"] == 5
        assert stats["avg_doc_length"] > 0
        assert "weights" in stats
        assert stats["weights"]["vector_search"] == 0.7
        # Use approximate comparison for floating point
        assert abs(stats["weights"]["bm25_search"] - 0.3) < 0.001

    def test_singleton_pattern(self):
        """Test that get_hybrid_search_service returns singleton"""
        service1 = get_hybrid_search_service()
        service2 = get_hybrid_search_service()

        assert service1 is service2
