"""
RAG Service
Retrieval-Augmented Generation using Qdrant + LangChain

Improvements:
- Async wrappers for Qdrant synchronous calls
- Embedding cache to reduce OpenAI costs
- Better error handling
"""

import asyncio
import hashlib
import structlog
from typing import List, Dict, Any, Optional
from functools import partial
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny
)
import uuid

from app.core.config import settings
from app.services.llm_service import LLMService

logger = structlog.get_logger()


class RAGService:
    """Service for RAG operations with Qdrant"""

    def __init__(self):
        self.client = QdrantClient(url=settings.QDRANT_URL)
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.llm_service = LLMService()
        self._initialized = False

        # Embedding cache (in-memory, max 1000 entries)
        self._embedding_cache: Dict[str, List[float]] = {}
        self._cache_max_size = 1000

        # Reranker (lazy-loaded)
        self._reranker = None

        # Hybrid search (lazy-loaded)
        self._hybrid_search = None

        # Query expansion (lazy-loaded)
        self._query_expansion = None

    async def _run_sync(self, func, *args, **kwargs):
        """
        Run synchronous Qdrant calls in thread pool to avoid blocking event loop.

        Args:
            func: Synchronous function to execute
            *args, **kwargs: Function arguments

        Returns:
            Function result
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            partial(func, *args, **kwargs)
        )

    async def initialize(self):
        """
        Initialize service asynchronously (call once at startup).

        Creates Qdrant collection if it doesn't exist.
        """
        if self._initialized:
            return

        try:
            await self._ensure_collection_exists()
            self._initialized = True
            logger.info("rag_service_initialized")
        except Exception as e:
            logger.error("rag_service_init_failed", error=str(e))
            raise

    async def _ensure_collection_exists(self):
        """Create collection if it doesn't exist (async wrapper)"""
        try:
            # Get collections (sync call wrapped in async)
            collections_result = await self._run_sync(self.client.get_collections)
            collection_names = [c.name for c in collections_result.collections]

            if self.collection_name not in collection_names:
                # Create collection (sync call wrapped in async)
                # Mistral embeddings use 1024 dimensions
                await self._run_sync(
                    self.client.create_collection,
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=1024,  # Mistral AI embedding dimension (mistral-embed)
                        distance=Distance.COSINE
                    )
                )
                logger.info("qdrant_collection_created", name=self.collection_name)
            else:
                logger.info("qdrant_collection_exists", name=self.collection_name)

        except Exception as e:
            logger.error("qdrant_collection_error", error=str(e))
            raise

    async def _get_embedding_cached(self, text: str) -> List[float]:
        """
        Get embedding with caching to reduce OpenAI API costs.

        Args:
            text: Text to embed

        Returns:
            Embedding vector

        Note:
            Cache is FIFO with max 1000 entries
        """
        # Create cache key from text hash
        cache_key = hashlib.md5(text.encode()).hexdigest()

        # Check cache
        if cache_key in self._embedding_cache:
            logger.debug("embedding_cache_hit", key=cache_key[:8])
            return self._embedding_cache[cache_key]

        # Generate embedding
        embeddings = await self.llm_service.get_embeddings([text])

        if not embeddings:
            raise ValueError("Failed to generate embedding")

        embedding = embeddings[0]

        # Store in cache with FIFO eviction
        self._embedding_cache[cache_key] = embedding

        if len(self._embedding_cache) > self._cache_max_size:
            # Remove oldest entry (first key)
            first_key = next(iter(self._embedding_cache))
            del self._embedding_cache[first_key]
            logger.debug("embedding_cache_evicted", key=first_key[:8])

        logger.debug("embedding_cache_miss", key=cache_key[:8])
        return embedding

    async def index_document(
        self,
        document_id: int,
        text: str,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Index a document in Qdrant

        Args:
            document_id: Database document ID
            text: Document text content
            metadata: Document metadata

        Returns:
            Qdrant point ID
        """
        try:
            # Generate embedding with cache
            embedding = await self._get_embedding_cached(text)

            # Create unique point ID
            point_id = str(uuid.uuid4())

            # Prepare payload
            payload = {
                "document_id": document_id,
                "text": text,
                **metadata
            }

            # Upload to Qdrant (async wrapper)
            await self._run_sync(
                self.client.upsert,
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload=payload
                    )
                ]
            )

            logger.info(
                "document_indexed",
                document_id=document_id,
                point_id=point_id
            )

            return point_id

        except Exception as e:
            logger.error(
                "indexing_error",
                document_id=document_id,
                error=str(e)
            )
            raise

    async def index_document_chunks(
        self,
        document_id: int,
        chunks: List[str],
        metadata: Dict[str, Any],
        enrich_metadata: bool = True
    ) -> List[str]:
        """
        Index multiple chunks from a single document with enriched metadata

        Args:
            document_id: Database document ID
            chunks: List of text chunks
            metadata: Document metadata
            enrich_metadata: Enable metadata enrichment (default: True)

        Returns:
            List of Qdrant point IDs

        Note:
            With enrich_metadata=True:
            - Extracts entities (emails, phones, amounts, dates, IBANs, SIRETs)
            - Detects language
            - Identifies content type (list, table, invoice, legal, narrative)
            - Adds temporal features for time-weighted ranking
            - Extracts keywords for structural ranking
            Impact: +5-10% filtrage precision, better ranking
        """
        point_ids = []

        try:
            # Lazy-load metadata enrichment service
            metadata_enricher = None
            if enrich_metadata:
                try:
                    from app.services.metadata_enrichment_service import get_metadata_enrichment_service
                    metadata_enricher = get_metadata_enrichment_service()
                except ImportError:
                    logger.warning("metadata_enrichment_unavailable", message="Proceeding with basic metadata")
                    enrich_metadata = False

            # Generate embeddings for all chunks (batch call)
            embeddings = await self.llm_service.get_embeddings(chunks)

            if len(embeddings) != len(chunks):
                raise ValueError("Embedding count mismatch")

            # Create points with enriched metadata
            points = []
            total_chunks = len(chunks)

            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                point_id = str(uuid.uuid4())
                point_ids.append(point_id)

                # Enrich metadata for this chunk
                if enrich_metadata and metadata_enricher:
                    chunk_metadata = metadata_enricher.enrich(
                        text=chunk,
                        basic_metadata=metadata,
                        chunk_index=i,
                        total_chunks=total_chunks
                    )
                else:
                    # Basic metadata
                    chunk_metadata = {
                        "document_id": document_id,
                        "text": chunk,
                        "chunk_index": i,
                        "total_chunks": total_chunks,
                        **metadata
                    }

                # Add document_id and text if not already present
                chunk_metadata["document_id"] = document_id
                chunk_metadata["text"] = chunk

                points.append(
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload=chunk_metadata
                    )
                )

            # Batch upload (async wrapper)
            await self._run_sync(
                self.client.upsert,
                collection_name=self.collection_name,
                points=points
            )

            logger.info(
                "chunks_indexed",
                document_id=document_id,
                chunk_count=len(chunks)
            )

            # Update BM25 index if hybrid search is enabled
            try:
                hybrid_search = await self._get_hybrid_search()
                for chunk in chunks:
                    await hybrid_search.add_document({
                        "id": document_id,
                        "text": chunk,
                        **metadata
                    })
            except Exception as e:
                logger.warning("bm25_index_update_failed", error=str(e))

            return point_ids

        except Exception as e:
            logger.error(
                "chunk_indexing_error",
                document_id=document_id,
                error=str(e)
            )
            raise

    async def _get_reranker(self):
        """Lazy-load reranker service"""
        if self._reranker is None:
            from app.services.reranker_service import RerankerService
            self._reranker = RerankerService()
            await self._reranker.initialize()
        return self._reranker

    async def _get_hybrid_search(self):
        """Lazy-load hybrid search service"""
        if self._hybrid_search is None:
            from app.services.hybrid_search_service import HybridSearchService
            self._hybrid_search = HybridSearchService()
        return self._hybrid_search

    async def _get_query_expansion(self):
        """Lazy-load query expansion service"""
        if self._query_expansion is None:
            from app.services.query_expansion_service import QueryExpansionService
            self._query_expansion = QueryExpansionService()
        return self._query_expansion

    async def search(
        self,
        query: str,
        limit: int = 5,
        filter_conditions: Optional[Dict[str, Any]] = None,
        document_ids: Optional[List[int]] = None,
        use_reranker: bool = True,
        use_hybrid: bool = True,
        use_query_expansion: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant documents

        Args:
            query: Search query
            limit: Maximum results to return
            filter_conditions: Optional metadata filters
            document_ids: Optional list of document IDs to filter by (from checkbox selection)
            use_reranker: Use cross-encoder re-ranking (default: True)
            use_hybrid: Use hybrid search (BM25 + Vector) (default: True)
            use_query_expansion: Use query expansion for better recall (default: False)

        Returns:
            List of search results with scores

        Raises:
            ValueError: If query is empty or limit is invalid

        Note:
            Search pipeline:
            1. Vector search (retrieves 3x limit if reranker enabled)
            2. Hybrid fusion with BM25 (if use_hybrid=True)
            3. Cross-encoder re-ranking (if use_reranker=True)
            Total latency: ~50-150ms depending on options
        """
        # Validate inputs
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        if limit < 1 or limit > 100:
            raise ValueError("Limit must be between 1 and 100")

        try:
            # Apply query expansion if enabled
            if use_query_expansion:
                try:
                    query_expansion = await self._get_query_expansion()

                    # Create a wrapper search function that doesn't use query expansion (to avoid recursion)
                    async def base_search(q, limit):
                        return await self.search(
                            query=q,
                            limit=limit,
                            filter_conditions=filter_conditions,
                            document_ids=document_ids,
                            use_reranker=use_reranker,
                            use_hybrid=use_hybrid,
                            use_query_expansion=False  # Disable to avoid recursion
                        )

                    # Use query expansion
                    expanded_results = await query_expansion.expand_and_search(
                        query=query,
                        search_func=base_search,
                        num_variants=3,
                        top_k=limit
                    )

                    logger.info("query_expansion_used", query=query[:50], results_count=len(expanded_results))
                    return expanded_results

                except Exception as e:
                    logger.warning("query_expansion_failed_fallback", error=str(e))
                    # Continue with normal search if query expansion fails

            # Generate query embedding with cache
            query_embedding = await self._get_embedding_cached(query)

            # Build filter if provided
            search_filter = None
            conditions = []

            # Add custom filter conditions
            if filter_conditions:
                conditions.extend([
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                    for key, value in filter_conditions.items()
                ])

            # Add document_ids filter (checkbox selection from frontend)
            if document_ids is not None and len(document_ids) > 0:
                conditions.append(
                    FieldCondition(
                        key="document_id",
                        match=MatchAny(any=document_ids)
                    )
                )
                logger.info("rag_filtering_by_document_ids", document_ids=document_ids)

            # Create filter if we have conditions
            if conditions:
                search_filter = Filter(must=conditions)

            # Determine search limit (fetch more if using reranker)
            search_limit = limit * 3 if use_reranker else limit

            # Search (async wrapper)
            results = await self._run_sync(
                self.client.search,
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=search_limit,
                query_filter=search_filter
            )

            # Format results
            formatted_results = [
                {
                    "id": result.id,
                    "score": result.score,
                    "content": result.payload.get("text"),  # Changed from "text" to "content" for orchestrator compatibility
                    "document_id": result.payload.get("document_id"),
                    "metadata": {
                        k: v for k, v in result.payload.items()
                        if k not in ["text", "document_id"]
                    }
                }
                for result in results
            ]

            # Apply hybrid search fusion if enabled
            if use_hybrid and formatted_results:
                try:
                    hybrid_search = await self._get_hybrid_search()
                    formatted_results = await hybrid_search.hybrid_search(
                        query=query,
                        vector_results=formatted_results,
                        top_k=limit * 2 if use_reranker else limit  # Get more for reranking
                    )
                    logger.info("hybrid_search_applied", result_count=len(formatted_results))
                except Exception as e:
                    logger.warning("hybrid_search_failed_fallback", error=str(e))
                    # Continue with vector-only results

            # Apply re-ranking if enabled
            if use_reranker and formatted_results:
                try:
                    reranker = await self._get_reranker()
                    formatted_results = await reranker.rerank(
                        query=query,
                        results=formatted_results,
                        top_k=limit
                    )
                    logger.info("reranking_applied", original_count=len(results), final_count=len(formatted_results))
                except Exception as e:
                    logger.warning("reranking_failed_fallback", error=str(e))
                    # Fallback to original results on reranking failure
                    formatted_results = formatted_results[:limit]

            # Log detailed search results
            if formatted_results:
                logger.info(
                    "search_completed",
                    query=query[:50],
                    results_count=len(formatted_results),
                    top_score=formatted_results[0]["score"] if formatted_results else 0,
                    document_ids_found=[r["document_id"] for r in formatted_results[:3]]
                )
            else:
                logger.warning(
                    "search_returned_no_results",
                    query=query[:50],
                    filter_used=search_filter is not None,
                    document_ids_filter=document_ids
                )

            return formatted_results

        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error("search_error", query=query, error=str(e))
            raise

    async def delete_document(self, document_id: int):
        """
        Delete all chunks of a document from Qdrant

        Args:
            document_id: Database document ID
        """
        try:
            # Delete (async wrapper)
            await self._run_sync(
                self.client.delete,
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id)
                        )
                    ]
                )
            )

            logger.info("document_deleted", document_id=document_id)

        except Exception as e:
            logger.error(
                "delete_error",
                document_id=document_id,
                error=str(e)
            )
            raise

    async def get_context_for_question(
        self,
        question: str,
        top_k: int = 3
    ) -> str:
        """
        Get relevant context for answering a question

        Args:
            question: User's question
            top_k: Number of top results to include

        Returns:
            Combined context string
        """
        results = await self.search(question, limit=top_k)

        if not results:
            return "Aucun document pertinent trouvé."

        # Combine results into context
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(
                f"[Document {i} - Score: {result['score']:.2f}]\n{result['text']}\n"
            )

        return "\n---\n".join(context_parts)
