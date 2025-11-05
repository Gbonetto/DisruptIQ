"""
Agent Run Model - Trace de l'exécution complète d'un agent
"""

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean,
    DECIMAL, CheckConstraint, ForeignKey
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class AgentRunStatus(str, enum.Enum):
    """Status d'exécution d'un agent run"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ABORTED = "aborted"


class AgentIntent(str, enum.Enum):
    """Type d'intent détecté"""
    SQL_ONLY = "SQL_ONLY"
    RAG_ONLY = "RAG_ONLY"
    HYBRID = "HYBRID"
    EMAIL = "EMAIL"
    N8N = "N8N"
    WEB = "WEB"
    OCR = "OCR"


class AgentRun(Base):
    """
    Trace complète d'une exécution d'agent.

    Enregistre:
    - L'intent détecté et la source utilisée
    - Le plan d'exécution (DAG JSON)
    - Les résultats et métriques (tokens, coût, latence)
    - Les sources/citations utilisées
    - Les conflits détectés (SQL vs RAG)
    - Le résultat de l'évaluation

    Relations:
    - 1:N avec AgentStep (les étapes du plan)
    - N:1 avec User (optionnel)
    """

    __tablename__ = "agent_runs"

    # Identification
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(100), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Classification
    intent = Column(String(50), index=True)  # SQL_ONLY, RAG_ONLY, HYBRID, etc.
    source = Column(String(50))  # Source effective utilisée
    confidence = Column(DECIMAL(4, 3))  # 0.000-1.000

    # Plan d'exécution (JSON DAG)
    plan_json = Column(JSONB, nullable=True)
    # Format: {"goal": str, "steps": [{"tool": str, "input": dict}], "success": str}

    # Résultats
    status = Column(
        String(20),
        nullable=False,
        default=AgentRunStatus.PENDING.value,
        index=True
    )
    error_message = Column(Text, nullable=True)
    output_summary = Column(Text, nullable=True)  # Résumé de la réponse

    # Métriques
    cost_tokens = Column(Integer, nullable=True)  # Tokens total
    cost_usd = Column(DECIMAL(10, 6), nullable=True)  # Coût USD
    latency_ms = Column(Integer, nullable=True)  # Latence totale

    # Sources utilisées
    sources_count = Column(Integer, default=0)
    citations_json = Column(JSONB, nullable=True)
    # Format: [{"id": str, "type": "rag"|"sql", "content": str, "confidence": float}]

    # Conflits détectés
    has_conflicts = Column(Boolean, default=False, index=True)
    conflicts_json = Column(JSONB, nullable=True)
    # Format: [{"field": str, "sql_value": any, "rag_value": any, "severity": str}]

    # Évaluation
    evaluator_passed = Column(Boolean, nullable=True)
    evaluator_rules_failed = Column(JSONB, nullable=True)
    # Format: ["no_citation", "missing_evidence", etc.]

    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    # Relations
    steps = relationship("AgentStep", back_populates="run", cascade="all, delete-orphan")

    # Contraintes
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="check_confidence_range"
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'success', 'failed', 'aborted')",
            name="check_status_values"
        ),
    )

    def __repr__(self):
        return (
            f"<AgentRun {self.id} "
            f"conversation={self.conversation_id} "
            f"intent={self.intent} "
            f"status={self.status}>"
        )

    @property
    def duration_ms(self) -> int | None:
        """Calcule la durée d'exécution en ms"""
        if self.ended_at and self.started_at:
            delta = self.ended_at - self.started_at
            return int(delta.total_seconds() * 1000)
        return None

    @property
    def is_success(self) -> bool:
        """Vérifie si l'exécution a réussi"""
        return self.status == AgentRunStatus.SUCCESS.value

    @property
    def has_errors(self) -> bool:
        """Vérifie si l'exécution a des erreurs"""
        return self.status in [AgentRunStatus.FAILED.value, AgentRunStatus.ABORTED.value]

    def to_dict(self) -> dict:
        """Convertit en dictionnaire pour API"""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "intent": self.intent,
            "source": self.source,
            "confidence": float(self.confidence) if self.confidence else None,
            "plan": self.plan_json,
            "status": self.status,
            "error_message": self.error_message,
            "output_summary": self.output_summary,
            "cost_tokens": self.cost_tokens,
            "cost_usd": float(self.cost_usd) if self.cost_usd else None,
            "latency_ms": self.latency_ms,
            "duration_ms": self.duration_ms,
            "sources_count": self.sources_count,
            "citations": self.citations_json,
            "has_conflicts": self.has_conflicts,
            "conflicts": self.conflicts_json,
            "evaluator_passed": self.evaluator_passed,
            "evaluator_rules_failed": self.evaluator_rules_failed,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }
