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
from app.services.query_processor import QueryProcessor

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

            # Delete existing points for this document to prevent duplicates
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

            # Cache invalidation hook (Phase 1.3)
            try:
                from app.services.cache_invalidation_hooks import on_document_indexed
                await on_document_indexed(document_id, point_id)
            except Exception as cache_err:
                logger.warning("cache_invalidation_failed", error=str(cache_err))

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

            # Delete existing points for this document to prevent duplicates
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

            # Cache invalidation hook (Phase 1.3)
            try:
                from app.services.cache_invalidation_hooks import on_document_chunks_indexed
                await on_document_chunks_indexed(document_id, len(chunks))
            except Exception as cache_err:
                logger.warning("cache_invalidation_failed", error=str(cache_err))

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
        """Lazy-load hybrid search service (singleton)"""
        if self._hybrid_search is None:
            from app.services.hybrid_search_service import get_hybrid_search_service
            self._hybrid_search = get_hybrid_search_service()  # Use singleton
        return self._hybrid_search

    async def _get_query_expansion(self):
        """Lazy-load query expansion service"""
        if self._query_expansion is None:
            from app.services.query_expansion_service import QueryExpansionService
            self._query_expansion = QueryExpansionService()
        return self._query_expansion

    def _deduplicate_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate chunks by text content with SMART AGGREGATION
        Used in agentic RAG to merge results from multiple sub-queries

        Key insight: Chunks appearing in multiple sub-queries are likely more relevant!
        We boost their score based on frequency.

        Args:
            chunks: List of chunks (potentially duplicated)

        Returns:
            Deduplicated list with boosted scores for frequent chunks
        """
        from collections import Counter

        # Count chunk frequency (how many sub-queries returned this chunk)
        text_to_chunks = {}
        text_counter = Counter()

        for chunk in chunks:
            text = chunk.get('text', '') or chunk.get('chunk', '') or chunk.get('content', '')

            if not text:
                continue

            # Use first 200 chars as key
            text_key = text[:200]

            # Track all versions of this chunk
            if text_key not in text_to_chunks:
                text_to_chunks[text_key] = []

            text_to_chunks[text_key].append(chunk)
            text_counter[text_key] += 1

        # Deduplicate with SMART BOOSTING
        result = []

        for text_key, chunk_versions in text_to_chunks.items():
            frequency = text_counter[text_key]

            # Find best chunk version (highest score)
            best_chunk = max(
                chunk_versions,
                key=lambda c: c.get('score', 0) or c.get('reranked_score', 0)
            )

            # BOOST score if chunk appears in multiple sub-queries
            original_score = best_chunk.get('score', 0) or best_chunk.get('reranked_score', 0)

            if frequency > 1:
                # Frequency boost: +20% per additional occurrence (capped at +60%)
                boost_multiplier = 1 + min(0.6, (frequency - 1) * 0.2)
                boosted_score = original_score * boost_multiplier

                # Update score
                best_chunk['score'] = boosted_score
                if 'reranked_score' in best_chunk:
                    best_chunk['reranked_score'] = boosted_score

                # Add metadata
                best_chunk['metadata'] = best_chunk.get('metadata', {})
                best_chunk['metadata']['frequency_boost'] = boost_multiplier
                best_chunk['metadata']['appeared_in_n_subqueries'] = frequency

                logger.debug("chunk_frequency_boost",
                            frequency=frequency,
                            boost=f"{(boost_multiplier-1)*100:.0f}%",
                            original_score=f"{original_score:.1%}",
                            boosted_score=f"{boosted_score:.1%}")

            result.append(best_chunk)

        return result

    async def search(
        self,
        query: str,
        limit: int = 5,
        filter_conditions: Optional[Dict[str, Any]] = None,
        document_ids: Optional[List[int]] = None,
        use_reranker: bool = True,
        use_hybrid: bool = True,
        use_query_expansion: bool = False,
        use_query_planning: bool = False,
        use_verification: bool = False,
        use_reflection: bool = False
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
            use_query_planning: Use agentic query decomposition for multi-hop queries (default: False)
            use_verification: Use verification agent to validate and refine results (default: False)

        Returns:
            List of search results with scores

        Raises:
            ValueError: If query is empty or limit is invalid

        Note:
            Search pipeline:
            1. Query planning (if use_query_planning=True, decomposes complex queries)
            2. Vector search (retrieves 3x limit if reranker enabled)
            3. Hybrid fusion with BM25 (if use_hybrid=True)
            4. Cross-encoder re-ranking (if use_reranker=True)
            5. Verification (if use_verification=True, validates and refines results)
            Total latency: ~50-150ms depending on options
            + 100-200ms if query planning
            + 200-500ms if verification (with potential re-searches)
        """
        # Validate inputs
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        if limit < 1 or limit > 100:
            raise ValueError("Limit must be between 1 and 100")

        # AGENTIC RAG: Query Planning (if enabled)
        # Decomposes complex queries into sub-queries for better retrieval
        if use_query_planning:
            try:
                from app.services.agents.query_planning_agent import QueryPlanningAgent

                planner = QueryPlanningAgent()
                plan = await planner.plan_query(query)

                # If query is complex, execute sub-queries and merge
                if plan.is_complex:
                    logger.info("agentic_rag_activated",
                               query_type=plan.query_type.value,
                               sub_queries_count=len(plan.sub_queries),
                               strategy=plan.aggregation_strategy.value)

                    # Execute sub-queries
                    all_chunks = []
                    for sub_query in plan.sub_queries:
                        logger.info("executing_sub_query",
                                   order=sub_query.order,
                                   query=sub_query.query[:60])

                        # Recursive call WITHOUT query_planning to avoid infinite loop
                        sub_chunks = await self.search(
                            query=sub_query.query,
                            limit=sub_query.expected_doc_count,
                            filter_conditions=filter_conditions,
                            document_ids=document_ids,
                            use_reranker=use_reranker,
                            use_hybrid=use_hybrid,
                            use_query_expansion=False,  # Disable expansion for sub-queries
                            use_query_planning=False  # CRITICAL: Disable to avoid recursion
                        )

                        all_chunks.extend(sub_chunks)

                    # Aggregate results based on strategy
                    if plan.aggregation_strategy.value == "concat":
                        # Deduplicate and rerank all chunks together
                        merged_chunks = self._deduplicate_chunks(all_chunks)

                        # Rerank merged chunks if reranker enabled
                        if use_reranker and merged_chunks:
                            reranker = await self._get_reranker()
                            merged_chunks = await reranker.rerank(
                                query=query,  # Use ORIGINAL query for final reranking
                                results=merged_chunks,
                                top_k=limit
                            )
                        else:
                            # Just sort by score and limit
                            merged_chunks = sorted(
                                merged_chunks,
                                key=lambda x: x.get('score', 0),
                                reverse=True
                            )[:limit]

                        logger.info("agentic_rag_completed",
                                   sub_queries_executed=len(plan.sub_queries),
                                   total_chunks_retrieved=len(all_chunks),
                                   final_chunks=len(merged_chunks))

                        return merged_chunks

                    elif plan.aggregation_strategy.value == "compare":
                        # Return results grouped by sub-query (for comparison)
                        # Format same as normal search but with metadata indicating source
                        for chunk in all_chunks:
                            chunk['metadata'] = chunk.get('metadata', {})
                            chunk['metadata']['agentic_rag'] = True
                            chunk['metadata']['query_plan'] = plan.reasoning

                        return all_chunks[:limit]

                    else:
                        # Other strategies: merge, filter, sequence
                        # For now, fallback to concat
                        merged_chunks = self._deduplicate_chunks(all_chunks)
                        return merged_chunks[:limit]

                else:
                    # Simple query - continue with normal pipeline
                    logger.info("query_classified_as_simple",
                               reasoning=plan.reasoning)

            except Exception as e:
                logger.error("query_planning_failed_fallback",
                            error=str(e),
                            query=query[:60])
                # Continue with normal search on error

        # Preprocess query: remove stopwords, normalize
        query_processor = QueryProcessor()
        normalized_query = query_processor.normalize(query)

        # OPTIMIZATION: For long queries (>8 words), extract keywords for BM25
        # This helps BM25 focus on key terms instead of being diluted
        query_length = len(query.split())
        if query_length > 8:
            keywords_query = query_processor.extract_keywords(query, max_keywords=5)
            logger.info("long_query_simplified",
                       original_length=query_length,
                       keywords=keywords_query)
            # Use keywords for BM25, full normalized for embeddings
            query_for_bm25 = keywords_query
        else:
            query_for_bm25 = normalized_query

        logger.info("query_preprocessing",
                   original=query[:50],
                   normalized=normalized_query[:50],
                   length_before=len(query.split()),
                   length_after=len(normalized_query.split()))

        # Use normalized query for embedding (better semantic matching)
        query_for_embedding = normalized_query

        try:
            # Apply query expansion if enabled
            # Phase 2.2: Enhanced with HyDE for complex queries
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

                    # Determine best expansion strategy based on query type
                    # - Short queries (<5 words): Use multi_query for variants
                    # - Question queries: Use HyDE (hypothetical document better for Q&A)
                    # - Complex queries: Use "all" strategies combined
                    word_count = len(query.split())
                    is_question = any(q in query.lower() for q in ['comment', 'pourquoi', 'quel', 'combien', 'quand', 'où', '?'])

                    if is_question and word_count > 5:
                        # Complex question - use HyDE for better semantic matching
                        strategy = "hyde"
                        num_variants = 1  # HyDE generates one hypothetical doc
                        logger.info("query_expansion_strategy_hyde", reason="complex_question")
                    elif word_count <= 4:
                        # Short query - use multi_query for coverage
                        strategy = "multi_query"
                        num_variants = 3
                        logger.info("query_expansion_strategy_multi_query", reason="short_query")
                    else:
                        # Medium query - use both for best results
                        strategy = "all"
                        num_variants = 2
                        logger.info("query_expansion_strategy_all", reason="medium_complexity")

                    # Use query expansion with adaptive strategy
                    expanded_results = await query_expansion.expand_and_search(
                        query=query,
                        search_func=base_search,
                        num_variants=num_variants,
                        strategy=strategy,
                        top_k=limit
                    )

                    logger.info("query_expansion_used",
                              query=query[:50],
                              strategy=strategy,
                              results_count=len(expanded_results))
                    return expanded_results

                except Exception as e:
                    logger.warning("query_expansion_failed_fallback", error=str(e))
                    # Continue with normal search if query expansion fails

            # Generate query embedding with cache (use normalized query)
            query_embedding = await self._get_embedding_cached(query_for_embedding)

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
            # INTERGALACTIC MODE: Fetch 6x for maximum precision (increased from 3x)
            # OPTIMIZATION: Increase to 8x if searching long documents
            # This helps find specific info buried in 50k+ char documents
            multiplier = 8 if use_reranker else 6  # Increased for long docs
            search_limit = limit * multiplier

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
                    # INTERGALACTIC MODE: Hybrid returns 3x for reranking (increased from 2x)
                    # OPTIMIZATION: Use keywords query for BM25 if query is long
                    bm25_query = query_for_bm25 if query_length > 8 else query_for_embedding
                    formatted_results = await hybrid_search.hybrid_search(
                        query=bm25_query,  # Use optimized query for BM25
                        vector_results=formatted_results,
                        top_k=limit * 3 if use_reranker else limit  # Get more for reranking
                    )
                    logger.info("hybrid_search_applied", result_count=len(formatted_results))
                except Exception as e:
                    logger.warning("hybrid_search_failed_fallback", error=str(e))
                    # Continue with vector-only results

            # Apply re-ranking if enabled (with multi-level fallback)
            if use_reranker and formatted_results:
                try:
                    reranker = await self._get_reranker()
                    reranked_results = await reranker.rerank(
                        query=query,
                        results=formatted_results,
                        top_k=limit
                    )

                    # Validate reranked results are not empty
                    if reranked_results:
                        formatted_results = reranked_results
                        logger.info("reranking_applied",
                                   original_count=len(results),
                                   final_count=len(formatted_results))
                    else:
                        logger.warning("reranking_returned_empty_fallback_to_original")
                        formatted_results = formatted_results[:limit]

                except Exception as e:
                    logger.error("reranking_failed_using_fallback", error=str(e), exc_info=True)

                    # FALLBACK LEVEL 1: Try hybrid-only (vector + BM25 without reranking)
                    if use_hybrid:
                        logger.warning("fallback_level_1_hybrid_only")
                        formatted_results = formatted_results[:limit]
                    else:
                        # FALLBACK LEVEL 2: Vector-only with score threshold
                        logger.warning("fallback_level_2_vector_only_with_threshold")
                        min_score = 0.5  # Minimum vector similarity score
                        filtered_results = [r for r in formatted_results if r.get("score", 0) >= min_score]

                        if filtered_results:
                            formatted_results = filtered_results[:limit]
                            logger.info("fallback_vector_threshold_applied",
                                       original=len(formatted_results),
                                       filtered=len(filtered_results))
                        else:
                            # FALLBACK LEVEL 3: Return top results without threshold
                            logger.warning("fallback_level_3_vector_only_no_threshold")
                            formatted_results = formatted_results[:limit]

            # FINAL VALIDATION: Ensure results have valid text
            if formatted_results:
                valid_results = []
                for r in formatted_results:
                    # Check if result has valid text content
                    text_content = r.get("text") or r.get("chunk") or r.get("content", "")
                    if text_content and len(text_content.strip()) >= 10:
                        valid_results.append(r)
                    else:
                        logger.warning(
                            "invalid_result_filtered",
                            result_id=r.get("id"),
                            text_length=len(text_content),
                            score=r.get("score", 0)
                        )

                if len(valid_results) < len(formatted_results):
                    logger.warning(
                        "final_validation_filtered_results",
                        original=len(formatted_results),
                        valid=len(valid_results),
                        removed=len(formatted_results) - len(valid_results)
                    )

                formatted_results = valid_results

            # AGENTIC RAG: Verification (if enabled)
            # Validates results and refines search if needed
            if use_verification and formatted_results:
                try:
                    from app.services.agents.verification_agent import VerificationAgent

                    verifier = VerificationAgent()

                    # Quick check: should we verify?
                    should_verify = verifier.should_verify(formatted_results)

                    if should_verify:
                        logger.info("verification_agent_activated",
                                   top_score=formatted_results[0].get('score', 0),
                                   reason="low_confidence")

                        # Create search function for verifier (recursive with verification disabled)
                        async def verification_search(query: str, limit: int = 5):
                            return await self.search(
                                query=query,
                                limit=limit,
                                filter_conditions=filter_conditions,
                                document_ids=document_ids,
                                use_reranker=use_reranker,
                                use_hybrid=use_hybrid,
                                use_query_expansion=False,
                                use_query_planning=False,  # Disable planning in verification
                                use_verification=False  # CRITICAL: Disable to avoid infinite recursion
                            )

                        # Verify and refine
                        verified_results = await verifier.verify_and_refine(
                            query=query,
                            chunks=formatted_results,
                            rag_search_func=verification_search,
                            max_iterations=2
                        )

                        if verified_results:
                            formatted_results = verified_results[:limit]
                            logger.info("verification_completed",
                                       original_count=len(formatted_results),
                                       verified_count=len(verified_results))
                    else:
                        logger.info("verification_skipped",
                                   reason="high_confidence",
                                   top_score=formatted_results[0].get('score', 0))

                except Exception as e:
                    logger.error("verification_failed_using_original_results",
                                error=str(e))
                    # Continue with original results on error

            # === AGENTIC RAG PHASE 3: Reflection (Last Resort) ===
            # Activates if results are STILL low quality after verification
            if use_reflection and formatted_results:
                try:
                    top_score_after_verification = formatted_results[0].get('reranked_score', formatted_results[0].get('score', 0))

                    # Only reflect if still below threshold (0.25 = 25%)
                    if top_score_after_verification < 0.25:
                        from app.services.agents.reflection_agent import ReflectionAgent

                        reflector = ReflectionAgent()

                        logger.info("reflection_agent_activated",
                                   reason="low_quality_after_verification",
                                   top_score=top_score_after_verification)

                        # Create search function for reflector
                        async def reflection_search(query: str, limit: int = 5):
                            return await self.search(
                                query=query,
                                limit=limit,
                                filter_conditions=filter_conditions,
                                document_ids=document_ids,
                                use_reranker=use_reranker,
                                use_hybrid=use_hybrid,
                                use_query_expansion=False,
                                use_query_planning=False,  # Disable all agents in recursive calls
                                use_verification=False,
                                use_reflection=False  # CRITICAL: Prevent infinite recursion
                            )

                        # Reflect and attempt to improve
                        reflection_result = await reflector.reflect_and_improve(
                            query=query,
                            low_quality_chunks=formatted_results,
                            search_func=reflection_search,
                            verification_attempts=1  # Verification already tried
                        )

                        if reflection_result.should_return and reflection_result.improved_results:
                            formatted_results = reflection_result.improved_results[:limit]

                            logger.info("reflection_completed",
                                       strategy=reflection_result.strategy_used.value,
                                       confidence=f"{reflection_result.confidence:.1%}",
                                       improved_count=len(formatted_results))

                            # Add reflection metadata to results
                            for result in formatted_results:
                                if 'metadata' not in result:
                                    result['metadata'] = {}
                                result['metadata']['reflection_applied'] = True
                                result['metadata']['failure_type'] = reflection_result.failure_type.value
                                result['metadata']['strategy_used'] = reflection_result.strategy_used.value

                                # If fallback message exists, add to first result
                                if reflection_result.fallback_message and formatted_results.index(result) == 0:
                                    result['metadata']['fallback_message'] = reflection_result.fallback_message

                    else:
                        logger.info("reflection_skipped",
                                   reason="acceptable_quality_after_verification",
                                   top_score=top_score_after_verification)

                except Exception as e:
                    logger.error("reflection_failed_using_original_results",
                                error=str(e))
                    # Continue with original results on error

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

            # Cache invalidation hook (Phase 1.3)
            try:
                from app.services.cache_invalidation_hooks import on_document_deleted
                await on_document_deleted(document_id)
            except Exception as cache_err:
                logger.warning("cache_invalidation_failed", error=str(cache_err))

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
