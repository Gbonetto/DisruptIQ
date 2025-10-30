"""
Chat Interface Endpoints
RAG-based question answering
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
import structlog

from app.services.rag_service import RAGService
from app.services.llm_service import LLMService

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


@router.post("/ask", response_model=ChatResponse)
async def ask_question(request: ChatRequest):
    """
    Ask a question with RAG context

    Example:
    {
        "message": "Qui est le plombier habituel ?",
        "conversation_history": [
            {"role": "user", "content": "Bonjour"},
            {"role": "assistant", "content": "Bonjour, comment puis-je vous aider?"}
        ]
    }
    """
    try:
        rag_service = RAGService()
        llm_service = LLMService()

        # Get relevant context from vector DB
        logger.info("searching_context", question=request.message[:50])
        context = await rag_service.get_context_for_question(
            question=request.message,
            top_k=3
        )

        # Get answer from LLM
        logger.info("generating_answer")
        answer = await llm_service.answer_question(
            question=request.message,
            context=context,
            conversation_history=[msg.dict() for msg in request.conversation_history]
        )

        # Get sources
        sources = await rag_service.search(request.message, limit=3)

        logger.info("question_answered", question=request.message[:50])

        return {
            "message": answer,
            "sources": sources,
            "session_id": request.session_id or "default"
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
