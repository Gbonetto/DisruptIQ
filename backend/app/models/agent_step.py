"""
Agent Step Model - Trace d'une étape individuelle d'un agent run
"""

from sqlalchemy import (
    Column, Integer, String, Text, DateTime,
    CheckConstraint, ForeignKey
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class AgentStepStatus(str, enum.Enum):
    """Status d'exécution d'une étape"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentTool(str, enum.Enum):
    """Tools/skills disponibles pour les agents"""
    # SQL
    SQL_PLAN = "sql.plan"
    SQL_EXECUTE = "sql.execute"
    SQL_VALIDATE = "sql.validate"

    # RAG
    RAG_SEARCH = "rag.search"
    RAG_SUMMARIZE = "rag.summarize"
    RAG_RERANK = "rag.rerank"

    # OCR
    OCR_EXTRACT = "ocr.extract"
    OCR_INDEX = "ocr.index"
    OCR_VALIDATE = "ocr.validate"

    # Email
    EMAIL_GENERATE = "email.generate"
    EMAIL_SEND_SAFE = "email.send_safe"
    EMAIL_PREVIEW = "email.preview"

    # Web
    WEB_SEARCH = "web.search"
    WEB_EXTRACT = "web.extract"

    # N8N
    N8N_PREVIEW = "n8n.preview"
    N8N_TRIGGER = "n8n.trigger"

    # Orchestration
    INTENT_CLASSIFY = "intent.classify"
    FUSION_MERGE = "fusion.merge"
    EVALUATOR_CHECK = "evaluator.check"


class AgentStep(Base):
    """
    Trace d'une étape individuelle dans un agent run.

    Enregistre:
    - Le tool/skill exécuté
    - Les paramètres d'entrée et sortie (JSON)
    - Les métriques (latence, tokens, evidence)
    - Le hash de l'input (pour cache/dedup)

    Relations:
    - N:1 avec AgentRun (le run parent)
    """

    __tablename__ = "agent_steps"

    # Identification
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(
        Integer,
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Identification step
    step_number = Column(Integer, nullable=False)  # Ordre dans le plan (0, 1, 2, ...)
    tool = Column(String(100), nullable=False, index=True)  # "sql.plan", "rag.search", etc.

    # Input/Output
    input_json = Column(JSONB, nullable=True)
    input_hash = Column(String(64), index=True)  # SHA256 pour cache
    output_json = Column(JSONB, nullable=True)
    output_ref = Column(String(200), nullable=True)  # Référence externe (fichier, cache key)

    # Résultat
    status = Column(
        String(20),
        nullable=False,
        default=AgentStepStatus.PENDING.value,
        index=True
    )
    error_message = Column(Text, nullable=True)

    # Métriques
    latency_ms = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    evidence_count = Column(Integer, default=0)  # Nombre d'éléments retournés

    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    # Relations
    run = relationship("AgentRun", back_populates="steps")

    # Contraintes
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'success', 'failed', 'skipped')",
            name="check_step_status"
        ),
    )

    def __repr__(self):
        return (
            f"<AgentStep {self.id} "
            f"run_id={self.run_id} "
            f"step={self.step_number} "
            f"tool={self.tool} "
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
        """Vérifie si l'étape a réussi"""
        return self.status == AgentStepStatus.SUCCESS.value

    @property
    def has_errors(self) -> bool:
        """Vérifie si l'étape a des erreurs"""
        return self.status == AgentStepStatus.FAILED.value

    def to_dict(self) -> dict:
        """Convertit en dictionnaire pour API"""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "step_number": self.step_number,
            "tool": self.tool,
            "input": self.input_json,
            "input_hash": self.input_hash,
            "output": self.output_json,
            "output_ref": self.output_ref,
            "status": self.status,
            "error_message": self.error_message,
            "latency_ms": self.latency_ms,
            "duration_ms": self.duration_ms,
            "tokens_used": self.tokens_used,
            "evidence_count": self.evidence_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }
