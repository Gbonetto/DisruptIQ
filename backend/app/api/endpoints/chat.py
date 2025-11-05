"""
Chat Interface Endpoints
Intelligent orchestration between RAG and SQL modes
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict
import structlog

from app.services.rag_service import RAGService
from app.services.llm_service import LLMService
from app.services.orchestrator_service import OrchestratorService
from app.core.dependencies import get_llm_service, get_rag_service
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
logger = structlog.get_logger()


class ChatMessage(BaseModel):
    """Chat message schema"""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Chat request"""
    message: str
    conversation_history: Optional[List[ChatMessage]] = []
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response"""
    message: str
    sources: List[Dict]
    session_id: str


class ObservabilityData(BaseModel):
    """Observability metadata"""
    run_id: Optional[int]
    plan_steps: int
    total_latency_ms: int
    estimated_tokens: int


class EvaluationData(BaseModel):
    """Evaluation results"""
    passed: bool
    rules_checked: int
    rules_passed: int
    critical_failures: int
    warnings: int
    failed_rules: List[str]


class ChatResponseWithPlan(BaseModel):
    """Enhanced chat response with observability and evaluation"""
    message: str
    sources: List[Dict]
    session_id: str
    observability: ObservabilityData
    evaluation: EvaluationData
    agents_used: List[str]
    confidence: float


@router.post("/ask", response_model=ChatResponse)
async def ask_question(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Ask a question with intelligent routing (RAG or SQL)

    The orchestrator automatically determines if your question needs:
    - RAG: Document search and knowledge retrieval
    - SQL: Database queries and statistics

    Example:
    {
        "message": "Combien d'emails urgents avons-nous?",  # -> SQL
        "conversation_history": []
    }
    {
        "message": "Comment procéder pour un dégât des eaux?",  # -> RAG
        "conversation_history": []
    }

    Performance optimizations:
    - Intelligent routing reduces unnecessary service calls
    - Reuses singleton services (no re-initialization)
    """
    try:
        # Use orchestrator for intelligent routing
        orchestrator = OrchestratorService()

        logger.info("orchestrator_processing", question=request.message[:50])

        result = await orchestrator.process_query(
            query=request.message,
            db=db,
            conversation_history=[msg.dict() for msg in request.conversation_history]
        )

        logger.info(
            "orchestrator_completed",
            question=request.message[:50],
            mode=result.get("mode"),
            success=result.get("success")
        )

        # Format response based on mode
        if result["mode"] == "sql":
            # SQL mode: include query and results
            return {
                "message": result["response"],
                "sources": [{
                    "text": f"Mode: SQL Database Query",
                    "metadata": {
                        "title": "SQL Query Result",
                        "sql": result.get("sql_query", ""),
                        "row_count": result.get("row_count", 0)
                    }
                }],
                "session_id": request.session_id or "default"
            }
        else:
            # RAG mode: include document sources
            return {
                "message": result["response"],
                "sources": result.get("sources", []),
                "session_id": request.session_id or "default"
            }

    except Exception as e:
        logger.error("chat_error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process question: {str(e)}"
        )


@router.post("/with-plan", response_model=ChatResponseWithPlan)
async def ask_question_with_plan(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Ask a question with FULL OBSERVABILITY and EVALUATION (Phase 1 integration)

    This endpoint uses the enhanced orchestrator with:
    - ✅ Execution plan generation (Planner DAG)
    - ✅ Rule-based validation (Evaluator)
    - ✅ Complete observability tracking (AgentRun, AgentSteps)
    - ✅ SQL canonical views for security
    - ✅ Citation validation for RAG responses
    - ✅ Conflict detection for HYBRID queries

    Returns enhanced response with:
    - message: The response text
    - sources: Citations and sources used
    - observability: Run ID, latency, tokens, plan steps
    - evaluation: Rules checked, passed/failed, warnings
    - agents_used: List of agents involved
    - confidence: Overall confidence score

    Example request:
    {
        "message": "Liste des plombiers actifs",
        "conversation_history": [],
        "session_id": "user-123"
    }

    Example response:
    {
        "message": "Trouvé 5 plombiers actifs...",
        "sources": [...],
        "session_id": "user-123",
        "observability": {
            "run_id": 456,
            "plan_steps": 3,
            "total_latency_ms": 1234,
            "estimated_tokens": 500
        },
        "evaluation": {
            "passed": true,
            "rules_checked": 3,
            "rules_passed": 3,
            "critical_failures": 0,
            "warnings": 0,
            "failed_rules": []
        },
        "agents_used": ["sql_agent"],
        "confidence": 0.95
    }

    ⚠️ IMPORTANT: If evaluation.passed is false, the response may not meet
    quality standards (e.g., missing citations, SQL errors, conflicts).
    """
    try:
        # Import orchestrator agent with Phase 1 integration
        from app.services.agents.orchestrator_agent import OrchestratorAgent
        import uuid

        orchestrator = OrchestratorAgent()

        # Generate conversation ID (use session_id or generate new)
        conversation_id = request.session_id or f"session-{uuid.uuid4().hex[:12]}"

        logger.info(
            "orchestrator_with_plan_processing",
            question=request.message[:50],
            conversation_id=conversation_id
        )

        # Process with enhanced orchestrator
        response = await orchestrator.process_with_plan(
            user_input=request.message,
            db=db,
            conversation_id=conversation_id,
            conversation_history=[msg.dict() for msg in request.conversation_history],
            thought_stream=None,  # Could be added for real-time streaming
            state_manager=None
        )

        logger.info(
            "orchestrator_with_plan_completed",
            question=request.message[:50],
            success=response.success,
            run_id=response.data.get("observability", {}).get("run_id"),
            evaluation_passed=response.data.get("evaluation", {}).get("passed")
        )

        # Extract sources from response data
        sources = []
        if response.data and "sources" in response.data:
            sources = response.data["sources"]
        elif response.data and "sql" in response.data:
            # SQL query result
            sources = [{
                "text": "SQL Database Query",
                "metadata": {
                    "title": "SQL Query Result",
                    "sql": response.data.get("sql", ""),
                    "table": "Canonical Views (vw_*)"
                }
            }]

        # Build enhanced response
        return ChatResponseWithPlan(
            message=response.message,
            sources=sources,
            session_id=conversation_id,
            observability=ObservabilityData(**response.data["observability"]),
            evaluation=EvaluationData(**response.data["evaluation"]),
            agents_used=response.agents_used,
            confidence=response.confidence
        )

    except Exception as e:
        logger.error("chat_with_plan_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process question with plan: {str(e)}"
        )


@router.get("/history/{session_id}")
async def get_chat_history(session_id: str):
    """Get chat history for a session"""
    # TODO: Fetch from database
    return {
        "session_id": session_id,
        "messages": []
    }


@router.delete("/history/{session_id}")
async def clear_chat_history(session_id: str):
    """Clear chat history for a session"""
    # TODO: Delete from database
    return {
        "message": "Chat history cleared",
        "session_id": session_id
    }
