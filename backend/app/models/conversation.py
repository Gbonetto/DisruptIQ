"""
Conversation Models - Intelligence Conversationnelle

Modèles pour gérer les conversations, profils utilisateur, et apprentissage
"""

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class ConversationSession(Base):
    """
    Session conversationnelle utilisateur

    Représente une session de chat avec historique complet
    """
    __tablename__ = "conversation_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Null for anonymous

    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    last_activity_at = Column(DateTime(timezone=True), onupdate=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)

    # Summary
    turns_count = Column(Integer, default=0)
    topics = Column(JSONB, default=list)  # ["invoices", "suppliers", ...]
    intents_distribution = Column(JSONB, default=dict)  # {"QUERY_INVOICE": 5, ...}

    # Context
    current_topic = Column(String(100), nullable=True)
    current_entities = Column(JSONB, default=dict)  # Last mentioned entities

    # Relations
    turns = relationship("ConversationTurn", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ConversationSession {self.session_id} - {self.turns_count} turns>"


class ConversationTurn(Base):
    """
    Un tour de conversation (message utilisateur + réponse assistant)
    """
    __tablename__ = "conversation_turns"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("conversation_sessions.id", ondelete="CASCADE"), index=True)
    turn_number = Column(Integer, index=True)  # 1, 2, 3, ...

    # Timestamps
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # User message
    user_message = Column(Text, nullable=False)
    user_message_cleaned = Column(Text)  # Preprocessed version

    # Intent detection
    detected_intent = Column(String(100), index=True)  # Primary intent
    intent_confidence = Column(Float)
    all_intents = Column(JSONB, default=dict)  # {"QUERY_INVOICE": 0.95, ...}
    sub_intents = Column(JSONB, default=list)  # ["BY_AMOUNT", "BY_DATE"]

    # Entity extraction
    extracted_entities = Column(JSONB, default=dict)  # {"amount": 500, "date_range": ...}
    resolved_entities = Column(JSONB, default=dict)  # After resolution

    # Assistant response
    assistant_message = Column(Text, nullable=False)
    response_type = Column(String(50))  # "answer", "clarification", "error", "suggestion"
    sources_used = Column(JSONB, default=list)

    # Execution details
    agents_used = Column(JSONB, default=list)  # ["sql_agent", "rag_agent"]
    execution_plan = Column(JSONB, default=dict)
    execution_time_ms = Column(Integer)
    orchestrator_mode = Column(String(20))  # "sql", "rag", "hybrid"

    # User feedback (updated after response)
    user_satisfied = Column(Boolean, nullable=True)
    feedback_rating = Column(Integer, nullable=True)  # 1-5 stars
    feedback_text = Column(Text, nullable=True)
    corrected_intent = Column(String(100), nullable=True)  # If user corrected

    # Learning signals
    was_helpful = Column(Boolean, default=True)
    led_to_action = Column(Boolean, default=False)  # Did user take action?
    user_clicked_result = Column(Boolean, default=False)
    user_refined_query = Column(Boolean, default=False)

    # Relations
    session = relationship("ConversationSession", back_populates="turns")

    def __repr__(self):
        return f"<ConversationTurn {self.id} - {self.detected_intent}>"


class UserProfile(Base):
    """
    Profil utilisateur avec préférences apprises automatiquement
    """
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True)

    # Learned preferences (automatic)
    default_copropriete_id = Column(Integer, ForeignKey("coproprietes.id"), nullable=True)
    preferred_date_range = Column(String(50), default="last_30_days")
    preferred_response_style = Column(String(20), default="detailed")  # detailed, concise, technical
    preferred_language = Column(String(10), default="fr")

    # Usage patterns
    most_common_intents = Column(JSONB, default=dict)  # {"QUERY_INVOICE": 0.45, ...}
    favorite_queries = Column(JSONB, default=list)  # Recent successful queries
    interaction_frequency = Column(String(20))  # daily, weekly, monthly
    peak_usage_hours = Column(JSONB, default=list)  # [9, 10, 14, 15]

    # Personalization
    interests = Column(JSONB, default=list)  # ["invoices", "suppliers", "duplicates"]
    expertise_level = Column(String(20), default="beginner")  # beginner, intermediate, expert
    custom_preferences = Column(JSONB, default=dict)  # Any custom prefs

    # Statistics
    total_sessions = Column(Integer, default=0)
    total_turns = Column(Integer, default=0)
    avg_satisfaction = Column(Float, default=0.0)
    avg_session_length = Column(Float, default=0.0)  # avg turns per session

    # Context memory
    recent_entities = Column(JSONB, default=dict)  # Recently mentioned entities
    last_successful_queries = Column(JSONB, default=list)  # Last 5 successful queries

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_interaction_at = Column(DateTime(timezone=True))

    def __repr__(self):
        return f"<UserProfile user_id={self.user_id} - {self.expertise_level}>"


class FeedbackEvent(Base):
    """
    Événement de feedback utilisateur (explicite et implicite)
    """
    __tablename__ = "feedback_events"

    id = Column(Integer, primary_key=True, index=True)
    turn_id = Column(Integer, ForeignKey("conversation_turns.id", ondelete="CASCADE"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(Integer, ForeignKey("conversation_sessions.id"), nullable=True)

    # Feedback type
    feedback_type = Column(String(50), index=True)  # thumbs_up, thumbs_down, correction, rating, implicit
    rating = Column(Integer, nullable=True)  # 1-5 stars
    feedback_text = Column(Text, nullable=True)

    # Implicit signals
    implicit_signal = Column(String(50), nullable=True)  # clicked_result, refined_query, abandoned
    signal_metadata = Column(JSONB, default=dict)

    # Correction data (if user corrected)
    original_intent = Column(String(100), nullable=True)
    corrected_intent = Column(String(100), nullable=True)
    original_entities = Column(JSONB, default=dict)
    corrected_entities = Column(JSONB, default=dict)

    # Learning
    was_processed = Column(Boolean, default=False)  # Has this feedback been used for learning?
    learning_impact = Column(String(20), nullable=True)  # low, medium, high

    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<FeedbackEvent {self.id} - {self.feedback_type}>"
