"""
Reranker Service - Cross-Encoder Reranking for RAG

Uses cross-encoder models to refine search results by computing relevance scores
between query and document pairs.

Architecture:
- Bi-encoder (vector search): Fast but less accurate → retrieve top 20
- Cross-encoder (reranking): Slow but very accurate → rerank to top 5

Models recommended:
- cross-encoder/ms-marco-MiniLM-L-6-v2 (English, fast, 80MB)
- cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 (Multilingual, 470MB)

Performance:
- Improves P@3 by 15-20%
- Latency: ~50-100ms for 20 documents
"""

import asyncio
import structlog
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

logger = structlog.get_logger()


class RankedChunk(BaseModel):
    """Chunk with reranking scores"""
    chunk_id: str
    text: str
    metadata: Dict[str, Any]
    original_score: float  # Cosine similarity from vector search
    reranked_score: float  # Cross-encoder score (0-1)
    boost_factor: float  # reranked / original


class RerankerService:
    """
    Cross-encoder reranking service

    Improves search precision by reranking results with a cross-encoder model
    that jointly encodes query + document.
    """

    def __init__(self):
        self._model = None
        self._model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
        logger.info("reranker_service_initialized", model=self._model_name)

    async def initialize(self):
        """
        Lazy-load cross-encoder model

        Uses sentence-transformers CrossEncoder which is optimized for
        ranking tasks.
        """
        if self._model is not None:
            return

        try:
            from sentence_transformers import CrossEncoder

            # Load model in thread pool to avoid blocking
            self._model = await asyncio.to_thread(
                CrossEncoder,
                self._model_name,
                max_length=512  # Max tokens for query+doc
            )

            logger.info("cross_encoder_loaded",
                       model=self._model_name,
                       max_length=512)

        except ImportError:
            logger.error("sentence_transformers_not_installed",
                        message="Install with: pip install sentence-transformers")
            raise ImportError(
                "sentence-transformers required for reranking. "
                "Install with: pip install sentence-transformers"
            )
        except Exception as e:
            logger.error("cross_encoder_load_failed", error=str(e))
            raise

    async def rerank(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[RankedChunk]:
        """
        Rerank search results using cross-encoder

        Args:
            query: User's search query
            chunks: List of chunks from vector search with 'text', 'metadata', 'score'
            top_k: Number of top results to return after reranking

        Returns:
            List of RankedChunk sorted by reranked_score (descending)

        Example:
            >>> chunks = [
            ...     {"text": "Le plombier...", "score": 0.82, "metadata": {...}},
            ...     {"text": "Délai livraison", "score": 0.79, "metadata": {...}},
            ... ]
            >>> reranked = await reranker.rerank("délai plombier", chunks, top_k=5)
            >>> reranked[0].reranked_score  # 0.95 (better than 0.82)
        """
        if not chunks:
            return []

        # Ensure model is loaded
        await self.initialize()

        try:
            # Prepare query-document pairs
            pairs = [[query, chunk.get("text", "")] for chunk in chunks]

            # Run cross-encoder prediction in thread pool (CPU-bound)
            scores = await asyncio.to_thread(
                self._model.predict,
                pairs,
                batch_size=32,
                show_progress_bar=False
            )

            # Convert to RankedChunk objects
            ranked_chunks = []
            for i, (chunk, score) in enumerate(zip(chunks, scores)):
                original_score = chunk.get("score", 0.0)

                ranked_chunk = RankedChunk(
                    chunk_id=chunk.get("id", f"chunk_{i}"),
                    text=chunk.get("text", ""),
                    metadata=chunk.get("metadata", {}),
                    original_score=original_score,
                    reranked_score=float(score),
                    boost_factor=float(score) / original_score if original_score > 0 else 1.0
                )
                ranked_chunks.append(ranked_chunk)

            # Sort by reranked score (descending)
            ranked_chunks.sort(key=lambda x: x.reranked_score, reverse=True)

            # Return top_k
            result = ranked_chunks[:top_k]

            logger.info("reranking_completed",
                       input_chunks=len(chunks),
                       output_chunks=len(result),
                       top_score=result[0].reranked_score if result else 0,
                       avg_boost=sum(c.boost_factor for c in result) / len(result) if result else 0)

            return result

        except Exception as e:
            logger.error("reranking_failed", error=str(e), exc_info=True)
            # Fallback: return original chunks sorted by original score
            logger.warning("falling_back_to_original_ranking")
            return [
                RankedChunk(
                    chunk_id=chunk.get("id", f"chunk_{i}"),
                    text=chunk.get("text", ""),
                    metadata=chunk.get("metadata", {}),
                    original_score=chunk.get("score", 0.0),
                    reranked_score=chunk.get("score", 0.0),
                    boost_factor=1.0
                )
                for i, chunk in enumerate(sorted(chunks, key=lambda x: x.get("score", 0), reverse=True)[:top_k])
            ]

    async def get_relevance_score(
        self,
        query: str,
        document: str
    ) -> float:
        """
        Get relevance score for a single query-document pair

        Args:
            query: User's query
            document: Document text

        Returns:
            Relevance score (0-1, higher is better)
        """
        await self.initialize()

        try:
            score = await asyncio.to_thread(
                self._model.predict,
                [[query, document]],
                show_progress_bar=False
            )
            return float(score[0])

        except Exception as e:
            logger.error("relevance_scoring_failed", error=str(e))
            return 0.0
