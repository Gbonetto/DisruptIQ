"""
Workflow Instance Models
Tracks the execution state of workflows (active to-do lists).
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class WorkflowStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"

class StepStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"

class WorkflowInstance(Base):
    """
    Represents an active instance of a workflow.
    """
    __tablename__ = "workflow_instances"

    id = Column(String, primary_key=True)  # UUID
    tenant_id = Column(String, nullable=True, index=True) # Optional for now
    
    workflow_type = Column(String, nullable=False) # e.g. "emergency"
    subtype = Column(String, nullable=False) # e.g. "water_leak"
    title = Column(String, nullable=False) # e.g. "Dégât des eaux - Apt 12"
    
    status = Column(String, default=WorkflowStatus.PENDING, index=True)
    current_step_index = Column(Integer, default=0)
    
    # Stores extracted context (building, owner, etc.)
    context_data = Column(JSON, default={})
    
    # Metadata (created_by, etc.)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    steps = relationship("WorkflowStep", back_populates="workflow_instance", cascade="all, delete-orphan", order_by="WorkflowStep.step_index")

    def __repr__(self):
        return f"<WorkflowInstance {self.id} - {self.title} ({self.status})>"

class WorkflowStep(Base):
    """
    Represents a single step in a workflow instance.
    """
    __tablename__ = "workflow_steps"

    id = Column(Integer, primary_key=True, index=True)
    workflow_instance_id = Column(String, ForeignKey("workflow_instances.id"), nullable=False, index=True)
    
    step_index = Column(Integer, nullable=False) # 0-based index
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    
    # Step configuration (from template/LLM)
    step_type = Column(String, default="manual") # manual, email, etc.
    is_critical = Column(Boolean, default=False)
    
    # Execution state
    status = Column(String, default=StepStatus.PENDING)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Specific data for this step (contacts, docs needed, etc.)
    step_data = Column(JSON, default={})
    
    # Output of the step (e.g. email sent ID)
    output_data = Column(JSON, default={})

    # Relationships
    workflow_instance = relationship("WorkflowInstance", back_populates="steps")

    def __repr__(self):
        return f"<WorkflowStep {self.step_index}: {self.title} ({self.status})>"
