"""
Conversation Management Endpoints
CRUD operations for conversation sessions
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import structlog

from app.core.database import get_db
from app.models.conversation import ConversationSession, ConversationTurn

logger = structlog.get_logger()

router = APIRouter()


# Pydantic models
class ConversationCreate(BaseModel):
    """Create a new conversation"""
    title: Optional[str] = Field(default="Nouvelle conversation", max_length=100)

    @field_validator('title')
    @classmethod
    def title_must_not_be_empty(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError('Title cannot be empty')
            if len(v) > 100:
                raise ValueError('Title too long (max 100 characters)')
        return v


class ConversationUpdate(BaseModel):
    """Update conversation details"""
    title: Optional[str] = Field(None, max_length=100)

    @field_validator('title')
    @classmethod
    def title_must_not_be_empty(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError('Title cannot be empty')
            if len(v) > 100:
                raise ValueError('Title too long (max 100 characters)')
        return v


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
    background_tasks: BackgroundTasks = BackgroundTasks(),
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

            # Generate title if not set (with background task support)
            title = await _get_or_generate_title(session, db, background_tasks)

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

    Returns count of deleted turns for transparency

    Args:
        conversation_id: Conversation ID

    Returns:
        Success message with turns_deleted count
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

        # Count turns before delete (for transparency)
        turns_count = session.turns_count

        # Explicitly delete turns first (safety over CASCADE)
        from sqlalchemy import delete
        await db.execute(
            delete(ConversationTurn)
            .where(ConversationTurn.session_id == session.id)
        )

        # Delete session
        await db.delete(session)
        await db.commit()

        logger.info("conversation_deleted",
                   conversation_id=conversation_id,
                   turns_deleted=turns_count)

        return {
            "message": "Conversation deleted successfully",
            "conversation_id": conversation_id,
            "turns_deleted": turns_count  # Transparency
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("delete_conversation_failed",
                    conversation_id=conversation_id,
                    error=str(e),
                    exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete conversation: {str(e)}"
        )


async def _get_or_generate_title(
    session: ConversationSession,
    db: AsyncSession,
    background_tasks: Optional[BackgroundTasks] = None
) -> str:
    """
    Get conversation title or generate one (with background task support)

    If title doesn't exist and 2+ turns: returns temporary title and
    generates real title in background to avoid blocking GET requests

    Args:
        session: Conversation session
        db: Database session
        background_tasks: Optional background tasks manager

    Returns:
        Conversation title (temporary or final)
    """
    # If title already stored, use it
    if session.current_topic:
        return session.current_topic

    # For conversations with 2+ turns, generate in background
    if session.turns_count >= 2 and background_tasks:
        # Schedule background title generation
        background_tasks.add_task(
            _generate_and_save_title_background,
            session.id,
            session.session_id
        )

        # Return temporary title immediately (from first message)
        first_turn = await db.execute(
            select(ConversationTurn)
            .where(ConversationTurn.session_id == session.id)
            .order_by(ConversationTurn.turn_number)
            .limit(1)
        )
        first_message = first_turn.scalar_one_or_none()

        if first_message:
            temp_title = first_message.user_message[:50]
            if len(first_message.user_message) > 50:
                temp_title += "..."
            return temp_title

        return "Nouvelle conversation"

    # Fallback: Generate from first message (simple truncation)
    if session.turns_count > 0:
        first_turn = await db.execute(
            select(ConversationTurn)
            .where(ConversationTurn.session_id == session.id)
            .order_by(ConversationTurn.turn_number)
            .limit(1)
        )
        first_message = first_turn.scalar_one_or_none()

        if first_message:
            title = first_message.user_message[:50]
            if len(first_message.user_message) > 50:
                title += "..."
            return title

    # Default for empty conversations
    return "Nouvelle conversation"


async def _generate_and_save_title_background(session_id: int, session_session_id: str):
    """
    Background task to generate and save title without blocking the request

    Args:
        session_id: ConversationSession ID
        session_session_id: ConversationSession session_id (UUID)
    """
    try:
        from app.core.database import AsyncSessionLocal
        from app.services.conversation_title_service import get_title_service

        async with AsyncSessionLocal() as db:
            # Get session
            result = await db.execute(
                select(ConversationSession).where(ConversationSession.id == session_id)
            )
            session = result.scalar_one_or_none()

            if not session or session.current_topic:
                return  # Already has title or not found

            # Get turns
            turns_result = await db.execute(
                select(ConversationTurn)
                .where(ConversationTurn.session_id == session.id)
                .order_by(ConversationTurn.turn_number)
                .limit(3)
            )
            turns = turns_result.scalars().all()

            if len(turns) < 2:
                return  # Not enough turns

            # Format messages
            messages = []
            for turn in turns:
                messages.append({"role": "user", "content": turn.user_message})
                messages.append({"role": "assistant", "content": turn.assistant_message})

            # Generate title
            title_service = get_title_service()
            title = await title_service.generate_title(messages, max_length=50)

            # Save title
            session.current_topic = title
            await db.commit()

            logger.info("background_title_generated",
                       session_id=session_id,
                       title=title)

    except Exception as e:
        logger.error("background_title_generation_failed",
                    session_id=session_id,
                    error=str(e))
