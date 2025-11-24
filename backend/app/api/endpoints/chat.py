"""
Chat Interface Endpoints
Intelligent orchestration between RAG and SQL modes
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict
import structlog
import asyncio

from app.services.rag_service import RAGService
from app.services.llm_service import LLMService
from app.services.orchestrator_service import OrchestratorService
from app.services.agents.orchestrator_factory import get_orchestrator
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
    selected_sources: Optional[List[str]] = None  # ['sql', 'rag', 'web'] - None = auto-detect


class ChatResponse(BaseModel):
    """Chat response"""
    message: str
    sources: List[Dict]
    session_id: str
    agents_used: Optional[List[str]] = []  # Agents utilisés pour générer la réponse


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
        # Get singleton orchestrator (eliminates 400ms re-instantiation overhead)
        orchestrator = get_orchestrator()

        logger.info("orchestrator_agent_processing", question=request.message[:50])

        # Convert conversation history to proper format
        conv_history = [{"role": msg.role, "content": msg.content} for msg in request.conversation_history]

        # Process with multi-agent orchestrator (30s timeout protection)
        try:
            agent_response = await asyncio.wait_for(
                orchestrator.process(
                    user_input=request.message,
                    db=db,
                    conversation_history=conv_history,
                    context=None,
                    thought_stream=None,
                    state_manager=None,
                    selected_sources=request.selected_sources,  # User-controlled source selection
                    session_id=request.session_id  # For context_store
                ),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            logger.error("request_timeout", message=request.message[:100])
            raise HTTPException(
                status_code=504,
                detail="La requête a pris trop de temps. Veuillez réessayer avec une question plus simple."
            )

        # Convert agent response to ChatResponse format
        result = {
            "success": agent_response.success,
            "response": agent_response.message,
            "mode": "multi_agent",
            "agents_used": agent_response.agents_used,
            "confidence": agent_response.confidence
        }

        logger.info(
            "orchestrator_agent_completed",
            question=request.message[:50],
            agents_used=result.get("agents_used", []),
            success=result.get("success")
        )

        # Format response based on agent response
        sources = []

        # Extract sources from agent_response.data if available
        if agent_response.data and "sources" in agent_response.data:
            sources = agent_response.data["sources"]
        else:
            # Fallback: Create source info from agents used
            sources = [{
                "text": f"Agents utilisés: {', '.join(result.get('agents_used', []))}",
                "metadata": {
                    "title": "Multi-Agent System",
                    "confidence": result.get("confidence", 1.0),
                    "agents": result.get("agents_used", [])
                }
            }]

        # Return unified response format
        return {
            "message": result["response"],
            "sources": sources,
            "session_id": request.session_id or "default",
            "agents_used": result.get("agents_used", [])  # Include agents_used for UI-API parity
        }

    except Exception as e:
        logger.error("chat_error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process question: {str(e)}"
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
