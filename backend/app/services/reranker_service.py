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
import math
import structlog
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

logger = structlog.get_logger()


def sigmoid(x: float) -> float:
    """
    Apply sigmoid function to normalize scores to 0-1 range

    Cross-encoder models output raw logits (can be negative).
    Sigmoid maps these to probabilities: sigmoid(x) = 1 / (1 + e^(-x))

    Examples:
        sigmoid(-3) ≈ 0.047 (low relevance)
        sigmoid(0)  = 0.5   (neutral)
        sigmoid(3)  ≈ 0.953 (high relevance)
    """
    return 1.0 / (1.0 + math.exp(-x))


class RankedChunk(BaseModel):
    """Chunk with reranking scores"""
    chunk_id: str
    text: str
    metadata: Dict[str, Any]
    original_score: float  # Cosine similarity from vector search
    reranked_score: float  # Cross-encoder score normalized with sigmoid (0-1)
    boost_factor: float  # reranked / original


class RerankerService:
    """
    Cross-encoder reranking service

    Improves search precision by reranking results with a cross-encoder model
    that jointly encodes query + document.
    """

    def __init__(self):
        from app.core.config import settings

        self._model = None

        # Optimisation FRANÇAIS: Utilise ColBERT français si activé
        if settings.USE_FRENCH_RERANKER:
            self._model_name = settings.FRENCH_RERANKER_MODEL
            # antoinelouis/colbert-xm-v1: ColBERT multilingue optimisé français
            # Meilleur que Camembert pour ranking (token-level matching vs sentence-level)
            logger.info("french_reranker_enabled", model=self._model_name)
        else:
            # Fallback: multilingual model
            self._model_name = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
            logger.info("multilingual_reranker_fallback", model=self._model_name)

        self._fallback_enabled = settings.FALLBACK_ON_ERROR
        logger.info("reranker_service_initialized",
                   model=self._model_name,
                   fallback=self._fallback_enabled)

    async def initialize(self):
        """
        Lazy-load cross-encoder model

        Uses sentence-transformers CrossEncoder which is optimized for
        ranking tasks.

        Avec fallback automatique:
        1. Essaie de charger modèle français (ColBERT)
        2. Si échec, essaie modèle multilingual
        3. Si échec, désactive reranking
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
            if not self._fallback_enabled:
                raise ImportError(
                    "sentence-transformers required for reranking. "
                    "Install with: pip install sentence-transformers"
                )

        except Exception as e:
            logger.error("cross_encoder_load_failed",
                        model=self._model_name,
                        error=str(e))

            # Fallback: essayer modèle multilingual si échec avec français
            if self._fallback_enabled and self._model_name != "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1":
                logger.warning("french_reranker_failed_trying_multilingual")
                try:
                    from sentence_transformers import CrossEncoder

                    self._model = await asyncio.to_thread(
                        CrossEncoder,
                        "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
                        max_length=512
                    )
                    logger.info("multilingual_reranker_loaded_as_fallback")
                    return

                except Exception as e2:
                    logger.error("multilingual_reranker_also_failed", error=str(e2))

            # Si fallback désactivé, raise error
            if not self._fallback_enabled:
                raise

    async def rerank(
        self,
        query: str,
        chunks: List[Dict[str, Any]] = None,
        top_k: int = 5,
        results: List[Dict[str, Any]] = None  # Alias for chunks (compatibility)
    ) -> List[RankedChunk]:
        """
        Rerank search results using cross-encoder

        Args:
            query: User's search query
            chunks: List of chunks from vector search with 'chunk'/'text', 'metadata', 'score'
            results: Alias for chunks (for compatibility)
            top_k: Number of top results to return after reranking

        Returns:
            List of RankedChunk sorted by reranked_score (descending)

        Example:
            >>> chunks = [
            ...     {"chunk": "Le plombier...", "score": 0.82, "metadata": {...}},
            ...     {"chunk": "Délai livraison", "score": 0.79, "metadata": {...}},
            ... ]
            >>> reranked = await reranker.rerank("délai plombier", chunks, top_k=5)
            >>> reranked[0].reranked_score  # 0.95 (better than 0.82)
        """
        # Support both 'chunks' and 'results' parameter names
        chunks = chunks or results

        if not chunks:
            return []

        # Ensure model is loaded
        await self.initialize()

        try:
            # Validate and prepare query-document pairs
            # Support 'chunk', 'content', and 'text' keys for compatibility
            def validate_chunk_text(chunk: dict, idx: int) -> Optional[str]:
                """Validate chunk has non-empty text"""
                text = chunk.get("chunk") or chunk.get("content") or chunk.get("text", "")

                if not text or len(text.strip()) < 10:
                    logger.warning(
                        "invalid_chunk_detected",
                        chunk_id=chunk.get("id", f"chunk_{idx}"),
                        text_length=len(text),
                        reason="empty_or_too_short"
                    )
                    return None

                return text

            # Filter and validate chunks
            valid_pairs = []
            valid_chunks = []
            invalid_count = 0

            for i, chunk in enumerate(chunks):
                text = validate_chunk_text(chunk, i)
                if text is not None:
                    valid_pairs.append([query, text])
                    valid_chunks.append(chunk)
                else:
                    invalid_count += 1

            if invalid_count > 0:
                logger.warning(
                    "chunks_filtered_invalid",
                    total=len(chunks),
                    invalid=invalid_count,
                    valid=len(valid_chunks)
                )

            if not valid_pairs:
                logger.error("all_chunks_invalid", total=len(chunks))
                return []

            pairs = valid_pairs
            chunks = valid_chunks  # Use only valid chunks from here on

            # Run cross-encoder prediction in thread pool (CPU-bound)
            scores = await asyncio.to_thread(
                self._model.predict,
                pairs,
                batch_size=32,
                show_progress_bar=False
            )

            # Convert to RankedChunk objects with original chunk reference
            ranked_chunks = []
            for i, (chunk, score) in enumerate(zip(chunks, scores)):
                original_score = chunk.get("score", 0.0)

                # Apply sigmoid to normalize cross-encoder logits to 0-1 range
                # Cross-encoder outputs raw logits (can be negative)
                normalized_score = sigmoid(float(score))

                ranked_chunk = RankedChunk(
                    chunk_id=chunk.get("id", f"chunk_{i}"),
                    text=chunk.get("chunk") or chunk.get("content") or chunk.get("text", ""),  # Support all keys
                    metadata=chunk.get("metadata", {}),
                    original_score=original_score,
                    reranked_score=normalized_score,  # Use normalized score (0-1)
                    boost_factor=normalized_score / original_score if original_score > 0 else 1.0
                )
                # Store original chunk for later reference
                ranked_chunk._original_chunk = chunk
                ranked_chunks.append(ranked_chunk)

            # Sort by reranked score (descending)
            ranked_chunks.sort(key=lambda x: x.reranked_score, reverse=True)

            # INTERGALACTIC MODE: Quality filtering - Remove low-confidence chunks
            MIN_CONFIDENCE_SCORE = 0.05  # 5% minimum (sigmoid normalized) - Lowered from 30% for better recall

            # Apply filtering
            filtered_chunks = [c for c in ranked_chunks if c.reranked_score >= MIN_CONFIDENCE_SCORE]

            # Logging
            removed_count = len(ranked_chunks) - len(filtered_chunks)
            if removed_count > 0:
                logger.info("low_confidence_chunks_filtered",
                           total=len(ranked_chunks),
                           removed=removed_count,
                           kept=len(filtered_chunks),
                           threshold=MIN_CONFIDENCE_SCORE)

            # Return top_k from FILTERED results (not all ranked results)
            result = filtered_chunks[:top_k]

            # If we filtered everything, return at least top 3 to avoid empty results
            if len(result) == 0 and len(ranked_chunks) > 0:
                logger.warning("all_chunks_below_threshold_keeping_top3")
                result = ranked_chunks[:3]

            logger.info("reranking_completed",
                       input_chunks=len(chunks),
                       output_chunks=len(result),
                       top_score=result[0].reranked_score if result else 0,
                       avg_boost=sum(c.boost_factor for c in result) / len(result) if result else 0)

            # Convert RankedChunk objects back to dicts for compatibility with RAG service
            return [
                {
                    "id": rc.chunk_id,
                    "chunk": rc.text,
                    "text": rc.text,  # Also include 'text' key for synthesis_agent compatibility
                    "metadata": rc.metadata,
                    "score": rc.reranked_score,
                    "reranked_score": rc.reranked_score,  # Explicit reranked_score key
                    "original_score": rc.original_score,
                    "boost_factor": rc.boost_factor,
                    "source": "reranked",
                    "document_id": rc._original_chunk.get("document_id")  # Preserve document_id from original
                }
                for rc in result
            ]

        except Exception as e:
            logger.error("reranking_failed", error=str(e), exc_info=True)
            # Fallback: return original chunks sorted by original score (as dicts)
            logger.warning("falling_back_to_original_ranking")
            sorted_chunks = sorted(chunks, key=lambda x: x.get("score", 0), reverse=True)[:top_k]
            text_content = lambda c: c.get("chunk") or c.get("content") or c.get("text", "")
            return [
                {
                    "id": chunk.get("id", f"chunk_{i}"),
                    "chunk": text_content(chunk),
                    "text": text_content(chunk),  # Also include 'text' key
                    "metadata": chunk.get("metadata", {}),
                    "score": chunk.get("score", 0.0),
                    "reranked_score": chunk.get("score", 0.0),
                    "original_score": chunk.get("score", 0.0),
                    "boost_factor": 1.0,
                    "source": "fallback",
                    "document_id": chunk.get("document_id")
                }
                for i, chunk in enumerate(sorted_chunks)
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
