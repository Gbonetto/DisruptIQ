"""
Emergency Workflow Model - V1 Simplified

Stores pre-configured emergency workflows (to-do lists) for urgent situations.
V1: Only supports 'water_leak' workflow type.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class EmergencyWorkflow(Base):
    """
    Emergency workflow templates (to-do lists)

    V1 Scope:
    - Single workflow_type: 'water_leak'
    - No dynamic generation (V2)
    - No versioning yet (V2)
    - Basic multi-tenant support
    """

    __tablename__ = "emergency_workflows"

    id = Column(Integer, primary_key=True, index=True)

    # Workflow identification
    tenant_id = Column(String(255), nullable=False, index=True)
    workflow_type = Column(String(100), nullable=False, index=True)  # 'water_leak' for V1
    workflow_name = Column(String(255), nullable=False)  # "Dégât des eaux - Procédure standard"

    # Checklist structure (JSONB in Postgres)
    # Contains: workflow_type, workflow_name, metadata, steps[]
    checklist = Column(JSON, nullable=False)

    # Status
    is_active = Column(Boolean, default=True, index=True)

    # Audit
    created_by = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # V1: Simple counter for analytics
    usage_count = Column(Integer, default=0)

    def __repr__(self):
        return f"<EmergencyWorkflow {self.workflow_type} - {self.workflow_name}>"
