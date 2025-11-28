"""
Database Models and Intent System
"""

# Database Models
from app.models.user import User
from app.models.email import Email
from app.models.professionnel import Professionnel, Vendor  # Vendor est un alias
from app.models.document import Document
from app.models.copropriete import Copropriete
from app.models.coproprietaire import Coproprietaire
from app.models.professionnel_copropriete import ProfessionnelCopropriete
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.emergency_workflow import EmergencyWorkflow
from app.models.workflow_instance import WorkflowInstance, WorkflowStep, WorkflowStatus, StepStatus

# Intent System (Centralized)
from app.models.intent import (
    IntentType,
    Domain,
    DataSource,
    IntentClassification,
    AgentResponse,
    AgentPlan,
    INTENT_AGENT_MAP,
    INTENT_DEFAULT_SOURCES,
)

__all__ = [
    # Database Models
    "User",
    "Email",
    "Professionnel",
    "Vendor",  # Alias pour compatibilité
    "Document",
    "Copropriete",
    "Coproprietaire",
    "ProfessionnelCopropriete",
    "Conversation",
    "Message",
    "EmergencyWorkflow",
    "WorkflowInstance",
    "WorkflowStep",
    "WorkflowStatus",
    "StepStatus",
    # Intent System
    "IntentType",
    "Domain",
    "DataSource",
    "IntentClassification",
    "AgentResponse",
    "AgentPlan",
    "INTENT_AGENT_MAP",
    "INTENT_DEFAULT_SOURCES",
]
