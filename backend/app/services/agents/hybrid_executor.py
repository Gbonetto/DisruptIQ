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
        intent: str = "HYBRID"
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
                return await self._execute_sql_only(query, db, state_manager)

            elif intent == "RAG_ONLY":
                return await self._execute_rag_only(query, db, state_manager)

            elif intent == "HYBRID":
                return await self._execute_both_parallel(query, db, state_manager)

            else:
                logger.warning("unknown_intent", intent=intent)
                # Fallback to RAG
                return await self._execute_rag_only(query, db, state_manager)

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
        state_manager
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
            rows_returned=len(sql_result_dict.get("data", {}).get("results", []))
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
        state_manager
    ) -> HybridResult:
        """Execute RAG agent only"""
        from app.services.rag_service import RAGService
        from .synthesis_agent import SynthesisAgent

        logger.info("executing_rag_only", query=query[:50])

        rag_service = RAGService()
        synthesis_agent = SynthesisAgent()

        # Get active document IDs from state
        document_ids = None
        if state_manager and state_manager.state.active_document_ids:
            document_ids = state_manager.state.active_document_ids

        # Retrieve chunks
        chunks = await rag_service.search(query, limit=5, document_ids=document_ids)

        if not chunks:
            rag_result = RAGResult(
                success=True,
                message="Aucun document pertinent trouvé.",
                chunks_retrieved=0,
                confidence=0.0
            )
        else:
            # Synthesize with citations
            is_procedural = self._is_procedural(query)
            synthesized = await synthesis_agent.synthesize_with_citations(
                query=query,
                chunks=chunks,
                is_procedural=is_procedural
            )

            # Prepare sources
            sources = [
                {
                    "id": s.id,
                    "title": s.title,
                    "page": s.page,
                    "confidence": s.confidence,
                    "document_id": s.document_id
                }
                for s in synthesized.sources
            ]

            rag_result = RAGResult(
                success=True,
                message=synthesized.text,
                data={
                    "sources": sources,
                    "sentences": [s.dict() for s in synthesized.sentences],
                    "has_contradictions": synthesized.has_contradictions,
                    "warnings": synthesized.warnings
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
        state_manager
    ) -> HybridResult:
        """
        Execute SQL and RAG in parallel for HYBRID intent

        This is the most powerful mode: combines structured data
        with unstructured document knowledge.
        """
        logger.info("executing_both_parallel", query=query[:50])

        # Execute both in parallel using asyncio.gather
        sql_task = self._execute_sql_only(query, db, state_manager)
        rag_task = self._execute_rag_only(query, db, state_manager)

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
