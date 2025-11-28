"""
Hybrid Executor - Execute SQL and RAG in parallel

This agent orchestrates parallel execution of:
- SQL Agent (database queries)
- RAG Agent (document search)

Then aggregates results for fusion.

Use cases:
- HYBRID intent: Both SQL and RAG needed
- Enrichment: SQL provides facts, RAG provides context
- Validation: Cross-check SQL data against documents

World-Class Features (Harvey AI / LexisNexis inspired):
- Verification Agent: Validates if chunks answer the query
- Reflection Agent: Diagnoses and fixes retrieval failures
- Confidence Calibration: Quality-aware response generation
"""

import asyncio
import structlog
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from functools import partial

logger = structlog.get_logger()

# ============================================================================
# WORLD-CLASS RAG CONFIGURATION
# ============================================================================
# Enable/disable advanced agents (feature flags for gradual rollout)
ENABLE_QUERY_PLANNING = True      # Decompose complex queries (multi-hop, comparison)
ENABLE_VERIFICATION_AGENT = True  # Verify if chunks answer the query
ENABLE_REFLECTION_AGENT = True    # Fix retrieval failures
VERIFICATION_CONFIDENCE_THRESHOLD = 0.40  # Below this, trigger verification
REFLECTION_CONFIDENCE_THRESHOLD = 0.30    # Below this, trigger reflection


class SQLResult(BaseModel):
    """SQL execution result"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: str
    query_executed: Optional[str] = None
    rows_returned: int = 0
    tables: List[str] = []  # Table names used in the query


class RAGResult(BaseModel):
    """RAG execution result"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: str
    sources: List[Dict[str, Any]] = []
    chunks_retrieved: int = 0
    confidence: float = 0.0


class HybridResult(BaseModel):
    """Combined result from SQL and RAG"""
    success: bool
    sql_result: Optional[SQLResult] = None
    rag_result: Optional[RAGResult] = None
    execution_mode: str  # "sql_only", "rag_only", "both"
    has_sql: bool
    has_rag: bool
    needs_fusion: bool  # True if both have results


class HybridExecutor:
    """
    Executes SQL and RAG agents in parallel and aggregates results

    Execution strategies:
    1. SQL_ONLY: Execute SQL agent only
    2. RAG_ONLY: Execute RAG agent only
    3. HYBRID: Execute both in parallel
    """

    def __init__(self):
        logger.info("hybrid_executor_initialized")

    async def execute_hybrid(
        self,
        query: str,
        db,
        state_manager=None,
        intent: str = "HYBRID",
        thought_stream=None
    ) -> HybridResult:
        """
        Execute SQL and RAG in parallel based on intent

        Args:
            query: User's question
            db: Database session
            state_manager: State manager for context
            intent: Execution intent (SQL_ONLY, RAG_ONLY, HYBRID)

        Returns:
            HybridResult with aggregated results
        """
        try:
            logger.info("hybrid_execution_started",
                       query=query[:50],
                       intent=intent)

            # Execute based on intent
            if intent == "SQL_ONLY":
                return await self._execute_sql_only(query, db, state_manager, thought_stream)

            elif intent == "RAG_ONLY":
                return await self._execute_rag_only(query, db, state_manager, thought_stream)

            elif intent == "HYBRID":
                return await self._execute_both_parallel(query, db, state_manager, thought_stream)

            else:
                logger.warning("unknown_intent", intent=intent)
                # Fallback to RAG
                return await self._execute_rag_only(query, db, state_manager, thought_stream)

        except Exception as e:
            logger.error("hybrid_execution_failed", error=str(e), exc_info=True)
            return HybridResult(
                success=False,
                execution_mode="error",
                has_sql=False,
                has_rag=False,
                needs_fusion=False
            )

    async def _execute_sql_only(
        self,
        query: str,
        db,
        state_manager,
        thought_stream=None
    ) -> HybridResult:
        """Execute SQL agent only"""
        from .sql_agent import SQLAgent

        logger.info("executing_sql_only", query=query[:50])

        sql_agent = SQLAgent()
        sql_result_dict = await sql_agent.process(query, db)

        sql_result = SQLResult(
            success=sql_result_dict.get("success", False),
            data=sql_result_dict.get("data"),
            message=sql_result_dict.get("message", ""),
            rows_returned=len(sql_result_dict.get("data", {}).get("results", [])),
            tables=sql_result_dict.get("tables", [])  # Extract table names from sql_agent response
        )

        logger.info("sql_execution_completed",
                   success=sql_result.success,
                   rows=sql_result.rows_returned)

        return HybridResult(
            success=sql_result.success,
            sql_result=sql_result,
            rag_result=None,
            execution_mode="sql_only",
            has_sql=sql_result.success,
            has_rag=False,
            needs_fusion=False
        )

    async def _execute_rag_only(
        self,
        query: str,
        db,
        state_manager,
        thought_stream=None
    ) -> HybridResult:
        """Execute RAG agent only"""
        from app.services.rag_service import RAGService
        from .synthesis_agent import SynthesisAgent
        from .thought_stream import ThoughtType

        import time
        start_time = time.time()

        logger.info("executing_rag_only", query=query[:50])

        rag_service = RAGService()
        synthesis_agent = SynthesisAgent()

        # Get active document IDs from state
        document_ids = None
        filter_info = "tous les documents"
        if state_manager and state_manager.state.active_document_ids is not None:
            # Only use filter if there are actual IDs (non-empty list)
            if len(state_manager.state.active_document_ids) > 0:
                document_ids = state_manager.state.active_document_ids
                filter_info = f"{len(document_ids)} document(s) sélectionné(s)"
                logger.info("rag_filtering_by_active_docs", count=len(document_ids))
            else:
                logger.info("rag_no_active_docs_set_searching_all")

        # ================================================================
        # PHASE 0: QUERY PLANNING (Multi-hop / Comparison detection)
        # Decomposes complex queries into simpler sub-queries
        # ================================================================
        query_plan = None
        is_complex_query = False

        if ENABLE_QUERY_PLANNING:
            try:
                from .query_planning_agent import QueryPlanningAgent, AggregationStrategy

                planner = QueryPlanningAgent()
                query_plan = await planner.plan_query(query)

                if query_plan.is_complex:
                    is_complex_query = True
                    if thought_stream:
                        sub_query_list = [sq.query[:40] + "..." for sq in query_plan.sub_queries[:3]]
                        await thought_stream.add_thought(
                            ThoughtType.ANALYZING,
                            title=f"🧩 Requête complexe détectée ({query_plan.query_type.value})",
                            content=f"Décomposition en {len(query_plan.sub_queries)} sous-requête(s):\n" +
                                    "\n".join([f"• {sq}" for sq in sub_query_list]),
                            agent="query_planner",
                            data={
                                "query_type": query_plan.query_type.value,
                                "sub_queries": len(query_plan.sub_queries),
                                "strategy": query_plan.aggregation_strategy.value
                            },
                            progress=0.25
                        )
                    logger.info("complex_query_planned",
                               query_type=query_plan.query_type.value,
                               sub_queries=len(query_plan.sub_queries),
                               strategy=query_plan.aggregation_strategy.value)

            except Exception as e:
                logger.warning("query_planning_error", error=str(e))
                # Continue with normal search

        # Emit thought: Starting search
        if thought_stream:
            await thought_stream.add_thought(
                ThoughtType.RAG_SEARCHING,
                title=f"Recherche dans {filter_info}",
                content="Recherche hybride (sémantique + mots-clés) en cours...",
                agent="rag_agent",
                progress=0.3
            )

        # INTERGALACTIC MODE: Fetch more for maximum precision
        # User accepts 3-5s latency for better results
        # Pipeline: Fetch 60 → Hybrid 30 → Rerank 20 → Filter 10
        INTERGALACTIC_MODE = True

        if INTERGALACTIC_MODE:
            limit = 10  # Final chunks (reduced from 15 to focus on best quality)
            use_expansion = False  # DISABLED: Query expansion conflicts with score filtering
        else:
            limit = 15  # Standard mode
            use_expansion = False

        # ================================================================
        # EXECUTE SEARCH (Simple or Multi-hop)
        # ================================================================
        chunks = []

        if is_complex_query and query_plan and len(query_plan.sub_queries) > 1:
            # COMPLEX QUERY: Execute sub-queries and aggregate
            all_sub_chunks = []

            for i, sub_query in enumerate(query_plan.sub_queries):
                if thought_stream:
                    await thought_stream.add_thought(
                        ThoughtType.RAG_SEARCHING,
                        title=f"Sous-requête {i+1}/{len(query_plan.sub_queries)}",
                        content=f"Recherche: {sub_query.query[:60]}...",
                        agent="rag_agent",
                        progress=0.3 + (i * 0.1)
                    )

                sub_chunks = await rag_service.search(
                    query=sub_query.query,
                    limit=sub_query.expected_doc_count or limit,
                    document_ids=document_ids,
                    use_hybrid=True,
                    use_reranker=True
                )

                # Tag chunks with sub-query info for aggregation
                for chunk in sub_chunks:
                    chunk['_sub_query_index'] = i
                    chunk['_sub_query'] = sub_query.query

                all_sub_chunks.extend(sub_chunks)
                logger.info("sub_query_executed",
                           sub_query_index=i,
                           chunks_found=len(sub_chunks))

            # Aggregate results based on strategy
            if query_plan.aggregation_strategy == AggregationStrategy.COMPARE:
                # Keep chunks grouped by sub-query for comparison
                chunks = all_sub_chunks
            elif query_plan.aggregation_strategy == AggregationStrategy.MERGE:
                # Deduplicate by chunk ID
                seen_ids = set()
                for chunk in all_sub_chunks:
                    chunk_id = chunk.get('id', str(chunk.get('text', '')[:50]))
                    if chunk_id not in seen_ids:
                        seen_ids.add(chunk_id)
                        chunks.append(chunk)
            else:
                # CONCAT (default) - just combine all
                chunks = all_sub_chunks

            # Sort by score and limit
            chunks = sorted(chunks, key=lambda x: x.get('cross_encoder_score', x.get('score', 0)), reverse=True)[:limit * 2]

            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.RAG_RESULTS,
                    title=f"✅ {len(chunks)} passage(s) agrégés",
                    content=f"Stratégie: {query_plan.aggregation_strategy.value}",
                    agent="query_planner",
                    progress=0.5
                )

        else:
            # SIMPLE QUERY: Direct search
            chunks = await rag_service.search(
                query=query,
                limit=limit,
                document_ids=document_ids,
                use_hybrid=True,  # Enable hybrid search (vector + keyword)
                use_reranker=True,  # Enable cross-encoder re-ranking
                use_query_expansion=use_expansion  # INTERGALACTIC: Enable controlled expansion
            )

        search_duration = time.time() - start_time
        logger.info("rag_search_returned", chunks_count=len(chunks), query=query[:50], filtered_by_docs=document_ids is not None, duration=search_duration)

        # Emit thought: Results found with document details
        if thought_stream:
            if chunks:
                # Calculate score info
                top_scores = [chunk.get('cross_encoder_score', chunk.get('score', 0)) for chunk in chunks[:3]]
                avg_score = sum(top_scores[:3]) / len(top_scores) if top_scores else 0

                # Extract document names from chunks
                doc_names = list(set([
                    chunk.get('metadata', {}).get('filename', chunk.get('filename', 'Document'))
                    for chunk in chunks[:5]
                ]))

                await thought_stream.add_thought(
                    ThoughtType.RAG_RESULTS,
                    title=f"{len(chunks)} passage(s) trouvé(s)",
                    content=f"Recherche terminée en {search_duration:.1f}s",
                    agent="rag_agent",
                    data={
                        "documents": doc_names[:5],
                        "chunks": len(chunks),
                        "confidence": avg_score
                    },
                    progress=0.6
                )
            else:
                await thought_stream.add_thought(
                    ThoughtType.RAG_RESULTS,
                    title="Aucun passage pertinent trouvé",
                    content=f"Recherche terminée en {search_duration:.1f}s",
                    agent="rag_agent",
                    data={
                        "documents": [],
                        "chunks": 0,
                        "confidence": 0
                    },
                    progress=0.6
                )

        # 🔴 CRITICAL FIX: NEVER ignore user's explicit document selection!
        # If user selected documents and we get no results, it means:
        # 1. Documents don't contain relevant info → tell user honestly
        # 2. OR embedding mismatch → needs investigation
        # DO NOT retry without filter - it breaks user trust!
        if not chunks and document_ids is not None:
            logger.warning("rag_no_results_in_selected_documents",
                          document_ids=document_ids,
                          query=query[:50],
                          message="User selected specific documents but they don't contain relevant info")
            # DO NOT RETRY - respect user's selection!

        if not chunks:
            # Provide context-aware error message
            if document_ids is not None:
                # User selected specific documents
                message = f"❌ Je n'ai trouvé aucune information pertinente dans les {len(document_ids)} document(s) sélectionné(s).\n\n**Raisons possibles** :\n1. Ces documents ne contiennent pas l'information recherchée\n2. L'information existe mais est formulée différemment\n3. Les documents n'ont peut-être pas été correctement indexés\n\n**Suggestions** :\n- Reformulez votre question avec d'autres mots\n- Vérifiez que vous avez sélectionné les bons documents\n- Décochez les filtres pour rechercher dans tous les documents"
            else:
                # General search across all documents
                message = "Je n'ai trouvé aucune information pertinente pour répondre à votre question.\n\n**Suggestions** :\n1. Vérifiez que des documents sont bien uploadés dans le panneau de droite\n2. Reformulez votre question avec d'autres mots\n3. Précisez le contexte (noms, dates, catégories)\n\nSi vous cherchez dans les documents, assurez-vous qu'ils contiennent l'information recherchée."

            rag_result = RAGResult(
                success=True,
                message=message,
                chunks_retrieved=0,
                confidence=0.0
            )
        else:
            # ================================================================
            # WORLD-CLASS RAG: VERIFICATION & REFLECTION PIPELINE
            # Inspired by Harvey AI / LexisNexis best practices
            # ================================================================

            # Calculate initial confidence from chunk scores
            top_scores = [chunk.get('cross_encoder_score', chunk.get('score', 0)) for chunk in chunks[:5]]
            initial_confidence = sum(top_scores) / len(top_scores) if top_scores else 0

            # PHASE 1: VERIFICATION AGENT
            # Check if chunks actually answer the query (not just keyword match)
            if ENABLE_VERIFICATION_AGENT and initial_confidence < VERIFICATION_CONFIDENCE_THRESHOLD:
                try:
                    from .verification_agent import VerificationAgent

                    if thought_stream:
                        await thought_stream.add_thought(
                            ThoughtType.ANALYZING,
                            title="🔍 Vérification de la pertinence",
                            content=f"Confiance initiale: {initial_confidence:.0%} - Vérification en cours...",
                            agent="verification_agent",
                            progress=0.55
                        )

                    verifier = VerificationAgent()

                    # Create a search function for potential re-search
                    async def rag_search_func(refined_query: str):
                        return await rag_service.search(
                            query=refined_query,
                            limit=limit,
                            document_ids=document_ids,
                            use_hybrid=True,
                            use_reranker=True
                        )

                    verified_chunks = await verifier.verify_and_refine(
                        query=query,
                        chunks=chunks,
                        rag_search_func=rag_search_func,
                        max_iterations=1  # Keep latency reasonable
                    )

                    if verified_chunks and len(verified_chunks) > 0:
                        chunks = verified_chunks
                        logger.info("verification_improved_results",
                                   original_count=len(top_scores),
                                   verified_count=len(chunks))

                except Exception as e:
                    logger.warning("verification_agent_error", error=str(e))
                    # Continue with original chunks

            # PHASE 2: REFLECTION AGENT
            # If still low confidence, diagnose and fix the retrieval failure
            refined_scores = [chunk.get('cross_encoder_score', chunk.get('score', 0)) for chunk in chunks[:5]]
            refined_confidence = sum(refined_scores) / len(refined_scores) if refined_scores else 0

            if ENABLE_REFLECTION_AGENT and refined_confidence < REFLECTION_CONFIDENCE_THRESHOLD:
                try:
                    from .reflection_agent import ReflectionAgent

                    if thought_stream:
                        await thought_stream.add_thought(
                            ThoughtType.ANALYZING,
                            title="🔄 Amélioration des résultats",
                            content=f"Confiance: {refined_confidence:.0%} - Réflexion en cours...",
                            agent="reflection_agent",
                            progress=0.6
                        )

                    reflector = ReflectionAgent()

                    # Create search function for reflection agent
                    async def reflection_search_func(refined_query: str):
                        return await rag_service.search(
                            query=refined_query,
                            limit=limit,
                            document_ids=document_ids,
                            use_hybrid=True,
                            use_reranker=True
                        )

                    reflection_result = await reflector.reflect_and_improve(
                        query=query,
                        low_quality_chunks=chunks,
                        search_func=reflection_search_func,
                        verification_attempts=0
                    )

                    # Use improved results if available
                    if reflection_result.improved_results and len(reflection_result.improved_results) > 0:
                        chunks = reflection_result.improved_results
                        logger.info("reflection_improved_results",
                                   strategy=reflection_result.strategy_used.value if reflection_result.strategy_used else "none",
                                   new_count=len(chunks))

                        if thought_stream:
                            await thought_stream.add_thought(
                                ThoughtType.ANALYZING,
                                title=f"✅ Amélioration: {reflection_result.strategy_used.value if reflection_result.strategy_used else 'none'}",
                                content=reflection_result.fallback_message or "Résultats améliorés",
                                agent="reflection_agent",
                                progress=0.65
                            )

                except Exception as e:
                    logger.warning("reflection_agent_error", error=str(e))
                    # Continue with current chunks

            # ================================================================
            # END WORLD-CLASS RAG PIPELINE
            # ================================================================

            # Emit thought: Synthesizing response
            synthesis_start = time.time()
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.SYNTHESIZING,
                    title=f"Analyse de {len(chunks)} passage(s)",
                    content="Synthèse des informations en cours...",
                    agent="rag_agent",
                    progress=0.7
                )

            # Synthesize with citations
            is_procedural = self._is_procedural(query)
            synthesized = await synthesis_agent.synthesize_with_citations(
                query=query,
                chunks=chunks,
                is_procedural=is_procedural
            )

            synthesis_duration = time.time() - synthesis_start
            total_duration = time.time() - start_time

            # Emit thought: Synthesis complete
            if thought_stream:
                confidence = synthesized.overall_confidence
                sources_count = len(synthesized.sources)

                # Extract source titles for display
                source_titles = [s.title for s in synthesized.sources[:5]]

                await thought_stream.add_thought(
                    ThoughtType.COMPLETED,
                    title=f"Synthèse terminée ({int(confidence * 100)}% confiance)",
                    content=f"{sources_count} source(s) utilisée(s)",
                    agent="rag_agent",
                    data={
                        "documents": source_titles,
                        "confidence": confidence
                    },
                    progress=0.9
                )

            # Clean HTML tags from synthesized text (remove <!--COT_START--> etc.)
            import re
            cleaned_text = re.sub(r'<!--COT_START-->.*?<!--COT_END-->', '', synthesized.text, flags=re.DOTALL)
            cleaned_text = re.sub(r'<!--ANSWER_START-->|<!--ANSWER_END-->', '', cleaned_text)
            cleaned_text = re.sub(r'<!--SOURCES_START-->.*?<!--SOURCES_END-->', '', cleaned_text, flags=re.DOTALL)
            cleaned_text = cleaned_text.strip()

            # Prepare sources with proper frontend format (preserve all scoring metadata)
            sources = [
                {
                    "type": "rag",  # Add type field for frontend display
                    "id": s.id,
                    "title": s.title,
                    "page": s.page,
                    "confidence": s.confidence,
                    "document_id": s.document_id,
                    "text": s.excerpt,  # Add text for display
                    "score": s.vector_score if s.vector_score else s.confidence,  # Fallback to confidence
                    "rrf_score": s.rrf_score,
                    "cross_encoder_score": s.cross_encoder_score
                }
                for s in synthesized.sources
            ]

            rag_result = RAGResult(
                success=True,
                message=cleaned_text,  # Use cleaned text without HTML tags
                data={
                    "sources": sources,
                    "sentences": [s.dict() for s in synthesized.sentences],
                    "has_contradictions": synthesized.has_contradictions,
                    "warnings": synthesized.warnings,
                    "chunks": chunks  # 🔴 CRITICAL: Include raw chunks for fusion (preserves all details)
                },
                sources=sources,
                chunks_retrieved=len(chunks),
                confidence=synthesized.overall_confidence
            )

        logger.info("rag_execution_completed",
                   success=rag_result.success,
                   chunks=rag_result.chunks_retrieved,
                   confidence=rag_result.confidence)

        return HybridResult(
            success=rag_result.success,
            sql_result=None,
            rag_result=rag_result,
            execution_mode="rag_only",
            has_sql=False,
            has_rag=rag_result.success and rag_result.chunks_retrieved > 0,
            needs_fusion=False
        )

    async def _execute_both_parallel(
        self,
        query: str,
        db,
        state_manager,
        thought_stream=None
    ) -> HybridResult:
        """
        Execute SQL and RAG in parallel for HYBRID intent

        This is the most powerful mode: combines structured data
        with unstructured document knowledge.
        """
        logger.info("executing_both_parallel", query=query[:50])

        # Execute both in parallel using asyncio.gather
        sql_task = self._execute_sql_only(query, db, state_manager, thought_stream)
        rag_task = self._execute_rag_only(query, db, state_manager, thought_stream)

        sql_hybrid, rag_hybrid = await asyncio.gather(
            sql_task,
            rag_task,
            return_exceptions=True
        )

        # Handle exceptions
        if isinstance(sql_hybrid, Exception):
            logger.error("sql_execution_failed_in_parallel", error=str(sql_hybrid))
            sql_hybrid = HybridResult(
                success=False,
                execution_mode="sql_only",
                has_sql=False,
                has_rag=False,
                needs_fusion=False
            )

        if isinstance(rag_hybrid, Exception):
            logger.error("rag_execution_failed_in_parallel", error=str(rag_hybrid))
            rag_hybrid = HybridResult(
                success=False,
                execution_mode="rag_only",
                has_sql=False,
                has_rag=False,
                needs_fusion=False
            )

        # Extract results
        sql_result = sql_hybrid.sql_result
        rag_result = rag_hybrid.rag_result

        has_sql = sql_result is not None and sql_result.success and sql_result.rows_returned > 0
        has_rag = rag_result is not None and rag_result.success and rag_result.chunks_retrieved > 0

        needs_fusion = has_sql and has_rag

        logger.info("parallel_execution_completed",
                   has_sql=has_sql,
                   has_rag=has_rag,
                   needs_fusion=needs_fusion,
                   sql_rows=sql_result.rows_returned if sql_result else 0,
                   rag_chunks=rag_result.chunks_retrieved if rag_result else 0)

        return HybridResult(
            success=has_sql or has_rag,  # Success if at least one succeeded
            sql_result=sql_result,
            rag_result=rag_result,
            execution_mode="both",
            has_sql=has_sql,
            has_rag=has_rag,
            needs_fusion=needs_fusion
        )

    def _is_procedural(self, query: str) -> bool:
        """Detect if query is procedural (asking for steps)"""
        procedural_keywords = [
            "comment", "procédure", "étapes", "steps",
            "que faire", "marche à suivre", "actions",
            "comment faire", "procedure", "démarche"
        ]
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in procedural_keywords)
