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
"""

import asyncio
import structlog
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

logger = structlog.get_logger()


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

        # Emit thought: Starting search - DeepSeek format (narrative in title, details in content)
        if thought_stream:
            await thought_stream.add_thought(
                ThoughtType.EXECUTING,
                title=f"Ok, je cherche dans {filter_info}. J'utilise une recherche hybride (sémantique + mots-clés) pour maximiser mes chances de trouver quelque chose de pertinent.",
                content="",  # Empty for DeepSeek style
                agent="rag"
            )

        # Retrieve chunks (increased from 5 to 15 for better precision)
        chunks = await rag_service.search(
            query=query,
            limit=15,
            document_ids=document_ids,
            use_hybrid=True,  # Enable hybrid search (vector + keyword)
            use_reranker=True,  # Enable cross-encoder re-ranking
            use_query_expansion=True  # Generate query variants for better recall
        )

        search_duration = time.time() - start_time
        logger.info("rag_search_returned", chunks_count=len(chunks), query=query[:50], filtered_by_docs=document_ids is not None, duration=search_duration)

        # Emit thought: Results found - DeepSeek format (everything in title as narrative)
        if thought_stream:
            if chunks:
                # Calculate score info
                top_scores = [chunk.get('cross_encoder_score', chunk.get('score', 0)) for chunk in chunks[:3]]
                scores_display = [f'{int(s*100)}%' for s in top_scores if s]

                # Evaluate quality - DeepSeek style narrative
                avg_score = sum(top_scores[:3]) / len(top_scores) if top_scores else 0
                if avg_score >= 0.8:
                    quality_assessment = "Excellent ! Les passages semblent très pertinents, je devrais pouvoir donner une réponse précise."
                elif avg_score >= 0.6:
                    quality_assessment = "Scores corrects. Les informations sont utiles mais peut-être un peu incomplètes."
                else:
                    quality_assessment = "Hmm... scores moyens ({', '.join(scores_display[:3])}). Les documents ne mentionnent peut-être le sujet que partiellement."

                # DeepSeek format: full narrative in title
                await thought_stream.add_thought(
                    ThoughtType.COMPLETED,
                    title=f"Trouvé {len(chunks)} passages en {search_duration:.1f}s. Meilleurs scores : {', '.join(scores_display[:3])}. {quality_assessment}",
                    content="",  # Empty for DeepSeek style
                    agent="rag"
                )
            else:
                await thought_stream.add_thought(
                    ThoughtType.COMPLETED,
                    title=f"Recherche terminée en {search_duration:.1f}s mais aucun passage pertinent trouvé. Soit l'information n'existe pas dans les documents, soit il faudrait reformuler la question différemment.",
                    content="",  # Empty for DeepSeek style
                    agent="rag"
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
            # Emit thought: Synthesizing response - DeepSeek format
            synthesis_start = time.time()
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.EXECUTING,
                    title=f"Maintenant je vais analyser et combiner ces {len(chunks)} passages. Je vérifie aussi s'il y a des contradictions entre les sources.",
                    content="",  # Empty for DeepSeek style
                    agent="synthesis"
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

            # Emit thought: Synthesis complete - DeepSeek format (full narrative)
            if thought_stream:
                confidence = int(synthesized.overall_confidence * 100)
                factual_count = len([s for s in synthesized.sentences if s.is_factual])

                # Build natural narrative - DeepSeek style
                if confidence >= 80:
                    confidence_narrative = f"Parfait ! J'ai une réponse solide avec {confidence}% de confiance. Les {len(synthesized.sources)} sources sont détaillées et cohérentes, j'ai extrait {factual_count} fait{'s' if factual_count > 1 else ''}."
                elif confidence >= 60:
                    confidence_narrative = f"Synthèse terminée en {synthesis_duration:.1f}s avec {confidence}% de confiance. Les {len(synthesized.sources)} sources contiennent l'info mais de façon partielle. J'ai quand même pu extraire {factual_count} fait{'s' if factual_count > 1 else ''}."
                else:
                    confidence_narrative = f"Hmm, synthèse terminée mais ma confiance est faible ({confidence}%). Les informations sont fragmentaires sur les {len(synthesized.sources)} sources. Les documents ne couvrent peut-être pas bien le sujet."

                # Add contradiction warning if needed
                if synthesized.has_contradictions:
                    confidence_narrative += " ⚠️ Attention : j'ai détecté des contradictions entre les sources."

                await thought_stream.add_thought(
                    ThoughtType.COMPLETED,
                    title=confidence_narrative,
                    content="",  # Empty for DeepSeek style
                    agent="synthesis"
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
