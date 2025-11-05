"""
Conversation Management Endpoints
CRUD operations for conversation sessions
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import List, Optional
from pydantic import BaseModel
import structlog

from app.core.database import get_db
from app.models.conversation import ConversationSession, ConversationTurn

logger = structlog.get_logger()

router = APIRouter()


# Pydantic models
class ConversationCreate(BaseModel):
    """Create a new conversation"""
    title: Optional[str] = "Nouvelle conversation"


class ConversationUpdate(BaseModel):
    """Update conversation details"""
    title: Optional[str] = None


class ConversationResponse(BaseModel):
    """Conversation response"""
    id: int
    session_id: str
    title: str
    preview: str
    timestamp: str
    message_count: int

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """Message response"""
    role: str
    content: str
    timestamp: str
    thoughts: Optional[List[dict]] = None
    sources: Optional[List[dict]] = None
    table_data: Optional[List[dict]] = None


@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    skip: int = 0,
    limit: int = 20,
    user_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List all conversation sessions

    Args:
        skip: Number of conversations to skip (pagination)
        limit: Maximum conversations to return
        user_id: Optional user filter

    Returns:
        List of conversations with metadata
    """
    try:
        # Build query
        query = select(ConversationSession)

        if user_id:
            query = query.where(ConversationSession.user_id == user_id)

        query = query.order_by(desc(ConversationSession.last_activity_at))
        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        sessions = result.scalars().all()

        # Format response
        conversations = []
        for session in sessions:
            # Get first message for preview
            first_turn = await db.execute(
                select(ConversationTurn)
                .where(ConversationTurn.session_id == session.id)
                .order_by(ConversationTurn.turn_number)
                .limit(1)
            )
            first_message = first_turn.scalar_one_or_none()

            preview = first_message.user_message[:100] if first_message else ""

            # Generate title if not set
            title = await _get_or_generate_title(session, db)

            conversations.append(ConversationResponse(
                id=session.id,
                session_id=session.session_id,
                title=title,
                preview=preview,
                timestamp=session.last_activity_at.isoformat() if session.last_activity_at else session.started_at.isoformat(),
                message_count=session.turns_count
            ))

        logger.info("conversations_listed", count=len(conversations))

        return conversations

    except Exception as e:
        logger.error("list_conversations_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list conversations: {str(e)}"
        )


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    conversation: ConversationCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new conversation session

    Args:
        conversation: Conversation creation data

    Returns:
        Created conversation
    """
    try:
        # Create new session
        new_session = ConversationSession(
            turns_count=0,
            topics=[],
            intents_distribution={}
        )

        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)

        logger.info("conversation_created", session_id=new_session.session_id)

        return ConversationResponse(
            id=new_session.id,
            session_id=new_session.session_id,
            title=conversation.title,
            preview="",
            timestamp=new_session.started_at.isoformat(),
            message_count=0
        )

    except Exception as e:
        await db.rollback()
        logger.error("create_conversation_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create conversation: {str(e)}"
        )


@router.get("/conversations/{conversation_id}", response_model=dict)
async def get_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get conversation details with all messages

    Args:
        conversation_id: Conversation ID

    Returns:
        Conversation with all messages
    """
    try:
        # Get session
        result = await db.execute(
            select(ConversationSession)
            .where(ConversationSession.id == conversation_id)
        )
        session = result.scalar_one_or_none()

        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found"
            )

        # Get all turns
        turns_result = await db.execute(
            select(ConversationTurn)
            .where(ConversationTurn.session_id == session.id)
            .order_by(ConversationTurn.turn_number)
        )
        turns = turns_result.scalars().all()

        # Format messages
        messages = []
        for turn in turns:
            # User message
            messages.append({
                "role": "user",
                "content": turn.user_message,
                "timestamp": turn.timestamp.isoformat()
            })

            # Assistant message
            messages.append({
                "role": "assistant",
                "content": turn.assistant_message,
                "timestamp": turn.timestamp.isoformat(),
                "thoughts": None,  # TODO: Store thoughts in turn
                "sources": turn.sources_used or [],
                "table_data": None  # TODO: Store table_data in turn
            })

        # Get title
        title = await _get_or_generate_title(session, db)

        return {
            "id": session.id,
            "session_id": session.session_id,
            "title": title,
            "messages": messages,
            "message_count": len(messages),
            "started_at": session.started_at.isoformat(),
            "last_activity_at": session.last_activity_at.isoformat() if session.last_activity_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_conversation_failed", conversation_id=conversation_id, error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get conversation: {str(e)}"
        )


@router.patch("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: int,
    update: ConversationUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update conversation (rename)

    Args:
        conversation_id: Conversation ID
        update: Update data (title)

    Returns:
        Updated conversation
    """
    try:
        # Get session
        result = await db.execute(
            select(ConversationSession)
            .where(ConversationSession.id == conversation_id)
        )
        session = result.scalar_one_or_none()

        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found"
            )

        # Update title (store in current_topic for now, could add a title field)
        if update.title:
            session.current_topic = update.title

        await db.commit()
        await db.refresh(session)

        logger.info("conversation_updated", conversation_id=conversation_id, title=update.title)

        return {
            "id": session.id,
            "session_id": session.session_id,
            "title": update.title or await _get_or_generate_title(session, db),
            "message": "Conversation updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("update_conversation_failed", conversation_id=conversation_id, error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update conversation: {str(e)}"
        )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a conversation and all its turns

    Args:
        conversation_id: Conversation ID

    Returns:
        Success message
    """
    try:
        # Get session
        result = await db.execute(
            select(ConversationSession)
            .where(ConversationSession.id == conversation_id)
        )
        session = result.scalar_one_or_none()

        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found"
            )

        # Delete (cascade will delete turns)
        await db.delete(session)
        await db.commit()

        logger.info("conversation_deleted", conversation_id=conversation_id)

        return {
            "message": "Conversation deleted successfully",
            "conversation_id": conversation_id
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("delete_conversation_failed", conversation_id=conversation_id, error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete conversation: {str(e)}"
        )


async def _get_or_generate_title(session: ConversationSession, db: AsyncSession) -> str:
    """
    Get conversation title or generate one

    Args:
        session: Conversation session
        db: Database session

    Returns:
        Conversation title
    """
    # If title stored in current_topic, use it
    if session.current_topic:
        return session.current_topic

    # Generate from first message
    if session.turns_count > 0:
        first_turn = await db.execute(
            select(ConversationTurn)
            .where(ConversationTurn.session_id == session.id)
            .order_by(ConversationTurn.turn_number)
            .limit(1)
        )
        first_message = first_turn.scalar_one_or_none()

        if first_message:
            # Simple title from first 50 chars
            title = first_message.user_message[:50]
            if len(first_message.user_message) > 50:
                title += "..."
            return title

    # Default
    return "Nouvelle conversation"
