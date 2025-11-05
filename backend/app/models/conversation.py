"""
Conversation Model - Store chat conversations
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Conversation(Base):
    """
    Conversation model for storing chat history sessions

    Attributes:
        id: Unique identifier
        title: Conversation title (auto-generated from first message)
        created_at: Timestamp when conversation was created
        updated_at: Timestamp when conversation was last updated
        is_active: Whether this conversation is currently active
        session_id: Session ID for state tracking
        message_count: Number of messages in this conversation
    """
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=True)  # Auto-generated title
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    session_id = Column(String(100), unique=True, index=True, nullable=False)  # For state tracking
    message_count = Column(Integer, default=0, nullable=False)

    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")

    def __repr__(self):
        return f"<Conversation(id={self.id}, title='{self.title}', messages={self.message_count})>"
