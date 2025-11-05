"""
Message Model - Store individual chat messages
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Message(Base):
    """
    Message model for storing individual chat messages

    Attributes:
        id: Unique identifier
        conversation_id: Foreign key to parent conversation
        role: Message role ('user' or 'assistant')
        content: Message text content
        thoughts: Chain of thoughts data (JSON)
        sources: Source citations (JSON)
        suggestions: Suggested actions (JSON)
        data: Additional metadata (JSON)
        created_at: Timestamp when message was created
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    thoughts = Column(JSON, nullable=True)  # Chain of thoughts data
    sources = Column(JSON, nullable=True)  # Source citations
    suggestions = Column(JSON, nullable=True)  # Suggested actions
    data = Column(JSON, nullable=True)  # Additional metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<Message(id={self.id}, role='{self.role}', conversation_id={self.conversation_id})>"

    def to_dict(self):
        """Convert message to dictionary for API responses"""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "thoughts": self.thoughts,
            "sources": self.sources,
            "suggestions": self.suggestions,
            "data": self.data,
            "timestamp": self.created_at.isoformat() if self.created_at else None
        }
