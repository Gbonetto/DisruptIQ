"""
Email Model
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean, Enum as SQLEnum
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class EmailUrgency(str, enum.Enum):
    """Email urgency classification"""
    URGENT = "urgent"
    IMPORTANT = "important"
    ROUTINE = "routine"


class Email(Base):
    """Email record model"""

    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String, unique=True, index=True)  # Gmail message ID
    thread_id = Column(String, index=True)

    # Email data
    sender = Column(String, nullable=False)
    recipient = Column(String)
    subject = Column(String, nullable=False)
    body = Column(Text)

    # Classification
    urgency = Column(SQLEnum(EmailUrgency), default=EmailUrgency.ROUTINE)
    category = Column(String)  # e.g., "vendor_quote", "neighbor_complaint", etc.

    # Metadata
    attachments = Column(JSON, default=list)  # List of attachment info
    llm_analysis = Column(JSON)  # LLM analysis result

    # Status
    processed = Column(Boolean, default=False)
    included_in_digest = Column(Boolean, default=False)

    # Timestamps
    received_at = Column(DateTime(timezone=True))
    processed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Email {self.subject} ({self.urgency})>"
