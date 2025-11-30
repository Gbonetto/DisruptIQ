"""
Conversation Management API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import structlog
import uuid

from app.core.database import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.llm_service import LLMService

router = APIRouter()
logger = structlog.get_logger()


# Pydantic Models
class MessageCreate(BaseModel):
    """Message creation schema"""
    role: str
    content: str
    thoughts: Optional[List[Dict[str, Any]]] = None
    sources: Optional[List[Dict[str, Any]]] = None
    suggestions: Optional[List[str]] = None
    data: Optional[Dict[str, Any]] = None


class ConversationCreate(BaseModel):
    """Conversation creation schema"""
    title: Optional[str] = None
    session_id: Optional[str] = None


class ConversationResponse(BaseModel):
    """Conversation response schema"""
    id: int
    title: Optional[str]
    created_at: str
    updated_at: str
    is_active: bool
    session_id: str
    message_count: int
    preview: Optional[str] = None  # First message preview


class MessageResponse(BaseModel):
    """Message response schema"""
    id: int
    conversation_id: int
    role: str
    content: str
    thoughts: Optional[List[Dict[str, Any]]]
    sources: Optional[List[Dict[str, Any]]]
    suggestions: Optional[List[str]]
    data: Optional[Dict[str, Any]]
    timestamp: str


# API Endpoints

@router.post("/", response_model=ConversationResponse)
async def create_conversation(
    conversation: ConversationCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new conversation
    """
    try:
        # Generate session_id if not provided
        session_id = conversation.session_id or str(uuid.uuid4())

        # Create conversation
        new_conversation = Conversation(
            title=conversation.title,
            session_id=session_id,
            is_active=True,
            message_count=0
        )

        db.add(new_conversation)
        await db.commit()
        await db.refresh(new_conversation)

        logger.info("conversation_created", conversation_id=new_conversation.id, session_id=session_id)

        return ConversationResponse(
            id=new_conversation.id,
            title=new_conversation.title,
            created_at=new_conversation.created_at.isoformat(),
            updated_at=new_conversation.updated_at.isoformat(),
            is_active=new_conversation.is_active,
            session_id=new_conversation.session_id,
            message_count=new_conversation.message_count
        )

    except Exception as e:
        logger.error("conversation_creation_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create conversation: {str(e)}")


@router.get("/", response_model=List[ConversationResponse])
async def list_conversations(
    response: Response,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """
    List all conversations ordered by most recent
    """
    # Disable HTTP caching to prevent stale data after deletion
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    try:
        # Get conversations with message count
        query = select(Conversation).order_by(desc(Conversation.updated_at)).limit(limit).offset(offset)
        result = await db.execute(query)
        conversations = result.scalars().all()

        # Build response with preview
        response = []
        for conv in conversations:
            # Get first message for preview
            preview = None
            first_msg_query = select(Message).where(
                Message.conversation_id == conv.id
            ).order_by(Message.created_at).limit(1)
            first_msg_result = await db.execute(first_msg_query)
            first_msg = first_msg_result.scalar_one_or_none()

            if first_msg:
                preview = first_msg.content[:100] + "..." if len(first_msg.content) > 100 else first_msg.content

            response.append(ConversationResponse(
                id=conv.id,
                title=conv.title or "Sans titre",
                created_at=conv.created_at.isoformat(),
                updated_at=conv.updated_at.isoformat(),
                is_active=conv.is_active,
                session_id=conv.session_id,
                message_count=conv.message_count,
                preview=preview
            ))

        return response

    except Exception as e:
        logger.error("conversation_list_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list conversations: {str(e)}")


@router.get("/{conversation_id}", response_model=Dict[str, Any])
async def get_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a conversation with all its messages
    """
    try:
        # Get conversation
        query = select(Conversation).where(Conversation.id == conversation_id)
        result = await db.execute(query)
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Get all messages
        messages_query = select(Message).where(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at)
        messages_result = await db.execute(messages_query)
        messages = messages_result.scalars().all()

        return {
            "conversation": ConversationResponse(
                id=conversation.id,
                title=conversation.title,
                created_at=conversation.created_at.isoformat(),
                updated_at=conversation.updated_at.isoformat(),
                is_active=conversation.is_active,
                session_id=conversation.session_id,
                message_count=conversation.message_count
            ),
            "messages": [msg.to_dict() for msg in messages]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("conversation_get_failed", error=str(e), conversation_id=conversation_id)
        raise HTTPException(status_code=500, detail=f"Failed to get conversation: {str(e)}")


@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def add_message(
    conversation_id: int,
    message: MessageCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Add a message to a conversation and auto-generate title if needed
    """
    try:
        # Check conversation exists
        query = select(Conversation).where(Conversation.id == conversation_id)
        result = await db.execute(query)
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Create message
        new_message = Message(
            conversation_id=conversation_id,
            role=message.role,
            content=message.content,
            thoughts=message.thoughts,
            sources=message.sources,
            suggestions=message.suggestions,
            data=message.data
        )

        db.add(new_message)

        # Update conversation message count
        conversation.message_count += 1

        # Auto-generate title if this is the first user message and no title exists
        if not conversation.title and message.role == "user" and conversation.message_count == 1:
            llm_service = LLMService()
            try:
                title_prompt = f"""Génère un titre court (max 50 caractères) pour cette conversation basé sur le premier message de l'utilisateur.

Message: {message.content[:200]}

Règles:
- Maximum 50 caractères
- Pas de guillemets
- Descriptif et clair
- En français
- Un seul titre, rien d'autre

Titre:"""
                title = await llm_service.generate_response(title_prompt, max_tokens=20, temperature=0.7)
                conversation.title = title.strip()[:50]
                logger.info("conversation_title_generated", conversation_id=conversation_id, title=conversation.title)
            except Exception as e:
                logger.warning("title_generation_failed", error=str(e))
                # Fallback title
                conversation.title = message.content[:50] + ("..." if len(message.content) > 50 else "")

        await db.commit()
        await db.refresh(new_message)

        logger.info("message_added", conversation_id=conversation_id, message_id=new_message.id)

        return MessageResponse(
            id=new_message.id,
            conversation_id=new_message.conversation_id,
            role=new_message.role,
            content=new_message.content,
            thoughts=new_message.thoughts,
            sources=new_message.sources,
            suggestions=new_message.suggestions,
            data=new_message.data,
            timestamp=new_message.created_at.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("message_add_failed", error=str(e), conversation_id=conversation_id)
        raise HTTPException(status_code=500, detail=f"Failed to add message: {str(e)}")


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a conversation and all its messages
    """
    try:
        query = select(Conversation).where(Conversation.id == conversation_id)
        result = await db.execute(query)
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        await db.delete(conversation)
        await db.commit()

        logger.info("conversation_deleted", conversation_id=conversation_id)

        return {"success": True, "message": "Conversation deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("conversation_delete_failed", error=str(e), conversation_id=conversation_id)
        raise HTTPException(status_code=500, detail=f"Failed to delete conversation: {str(e)}")


@router.put("/{conversation_id}/title")
async def update_title(
    conversation_id: int,
    title: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Update conversation title
    """
    try:
        query = select(Conversation).where(Conversation.id == conversation_id)
        result = await db.execute(query)
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        conversation.title = title[:255]  # Limit to 255 chars
        await db.commit()

        logger.info("conversation_title_updated", conversation_id=conversation_id, title=title)

        return {"success": True, "title": conversation.title}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("conversation_title_update_failed", error=str(e), conversation_id=conversation_id)
        raise HTTPException(status_code=500, detail=f"Failed to update title: {str(e)}")
