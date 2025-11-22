"""
Intent Models - Centralized Intent Classification System
Clean, stable intent types for world-class multi-agent orchestration
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class IntentType(str, Enum):
    """
    8 Stable Intent Types - Core user intentions

    Design Principles:
    - Stable: These should rarely change
    - Mutually Exclusive: Each query maps to ONE intent
    - Action-Oriented: Describes WHAT, not HOW
    - Domain-Agnostic: Intent != Agent (e.g., LEGAL intent but Legal Agent decides action)

    NOTE: Includes HYBRID_QUERY for backward compatibility (will be removed in Phase 2)
    """

    # Data Access Intents
    QUERY_DATA = "query_data"              # SQL database queries (copropriétaires, documents)
    SEARCH_DOCUMENTS = "search_documents"  # RAG semantic search (contracts, PDFs)
    WEB_SEARCH = "web_search"              # Internet search (current info, jurisprudence)

    # Action Intents
    SEND_EMAIL = "send_email"              # Generate and send emails
    REQUEST_QUOTES = "request_quotes"      # Request devis from vendors
    TRIGGER_WORKFLOW = "trigger_workflow"  # Explicit N8N workflow trigger

    # Analysis Intents
    LEGAL = "legal"                        # Legal analysis/advice (agent decides specific action)
    GENERAL_QUESTION = "general_question"  # General assistant questions (not domain-specific)

    # Legacy (DEPRECATED - for backward compatibility)
    HYBRID_QUERY = "hybrid_query"          # DEPRECATED: Use QUERY_DATA or SEARCH_DOCUMENTS


class Domain(str, Enum):
    """
    Domain classification - Semantic context for intent
    Helps route to correct specialist agent
    """
    LEGAL = "legal"                # Legal, jurisprudence, contracts
    PLUMBING = "plumbing"          # Plumbing, water, heating issues
    PROPERTY_MGMT = "property_mgmt"  # Copropriété management
    VENDOR_MGMT = "vendor_mgmt"    # Vendor, quotes, contracts
    GENERAL = "general"            # General queries
    UNKNOWN = "unknown"            # Unable to determine


class DataSource(str, Enum):
    """
    Available data sources for context retrieval

    NOTE: Includes legacy values for backward compatibility with intent_classifier_v4
    These will be removed in Phase 2 refactoring
    """
    # New values (Phase 1)
    SQL = "sql"                    # PostgreSQL database
    RAG = "rag"                    # Qdrant vector search
    LEGIFRANCE = "legifrance"      # Official French legal database
    WEB = "web"                    # DuckDuckGo web search
    UPLOADED_DOCS = "uploaded_docs"  # User-uploaded documents
    CONVERSATION = "conversation"  # Conversation history

    # Legacy values (for backward compatibility - DEPRECATED)
    SQL_ONLY = "sql_only"          # DEPRECATED: Use SQL instead
    RAG_ONLY = "rag_only"          # DEPRECATED: Use RAG instead
    HYBRID = "hybrid"              # DEPRECATED: Use list of sources instead
    AMBIGUOUS = "ambiguous"        # DEPRECATED: Use needs_clarification field


class IntentClassification(BaseModel):
    """
    Result of intent classification

    Key Design Decision:
    - suggested_sources: NOT obligations, just hints
    - Agents have full autonomy to decide data strategy
    - Orchestrator builds context, agent decides what to use
    """
    intent: IntentType = Field(..., description="Primary user intention")
    domain: Domain = Field(default=Domain.UNKNOWN, description="Semantic domain")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classification confidence (0-1)")

    # Data suggestions (NOT requirements)
    suggested_sources: List[DataSource] = Field(
        default_factory=list,
        description="Suggested data sources (agents decide final strategy)"
    )

    # Metadata
    reasoning: Optional[str] = Field(None, description="Why this classification? (for debugging)")
    keywords_matched: List[str] = Field(default_factory=list, description="Keywords that triggered this intent")

    # Clarification (if confidence < threshold)
    needs_clarification: bool = Field(default=False, description="Should we ask user for clarification?")
    clarification_question: Optional[str] = Field(None, description="Question to ask user")
    possible_intents: List[IntentType] = Field(
        default_factory=list,
        description="Alternative intents if ambiguous"
    )

    class Config:
        # Keep enum types intact (don't convert to values)
        # Orchestrator and agents expect IntentType/Domain/DataSource objects, not strings
        use_enum_values = False


class AgentResponse(BaseModel):
    """
    Standardized agent response format
    All agents return this structure for consistency
    """
    success: bool = Field(..., description="Did the operation succeed?")
    message: str = Field(..., description="Human-readable response")
    data: Optional[Dict[str, Any]] = Field(None, description="Structured data (JSON)")

    # Metadata
    agents_used: List[str] = Field(default_factory=list, description="Which agents were involved?")
    sources_used: List[DataSource] = Field(default_factory=list, description="Which data sources were accessed?")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Response confidence")

    # User guidance
    suggestions: List[str] = Field(default_factory=list, description="Follow-up action suggestions")
    warnings: List[str] = Field(default_factory=list, description="Important warnings/caveats")

    class Config:
        # Keep enum types intact for consistency with IntentClassification
        use_enum_values = False


class AgentPlan(BaseModel):
    """
    Agent execution plan (OPTIONAL - for complex multi-step operations)

    Philosophy:
    - Most queries are simple (1 agent, 1 action)
    - Only use for complex workflows (multi-agent coordination)
    - Agents can execute immediately without formal plan
    """
    primary_agent: str = Field(..., description="Agent responsible for this query")
    action: str = Field(..., description="What action will be performed?")

    # Optional support
    support_agents: List[str] = Field(default_factory=list, description="Agents that might be called")
    data_sources: List[DataSource] = Field(default_factory=list, description="Data sources to access")

    # Execution metadata
    estimated_complexity: str = Field(default="simple", description="simple|medium|complex")
    requires_user_confirmation: bool = Field(default=False, description="Ask before executing?")

    class Config:
        # Keep enum types intact for consistency with IntentClassification
        use_enum_values = False


# Intent → Agent Mapping (Reference, not enforced)
# This is DOCUMENTATION, not rigid routing
INTENT_AGENT_MAP = {
    IntentType.QUERY_DATA: "SQLAgent",
    IntentType.SEARCH_DOCUMENTS: "RAGAgent",
    IntentType.WEB_SEARCH: "WebSearchAgent",
    IntentType.SEND_EMAIL: "EmailAgent",
    IntentType.REQUEST_QUOTES: "QuoteAgent",
    IntentType.TRIGGER_WORKFLOW: "WorkflowAgent",
    IntentType.LEGAL: "LegalAgent",  # Legal Agent decides: analysis, advice, jurisprudence
    IntentType.GENERAL_QUESTION: "OrchestratorAgent",  # Orchestrator handles directly
}


# Intent → Common Data Sources (Reference)
INTENT_DEFAULT_SOURCES = {
    IntentType.QUERY_DATA: [DataSource.SQL],
    IntentType.SEARCH_DOCUMENTS: [DataSource.RAG, DataSource.UPLOADED_DOCS],
    IntentType.WEB_SEARCH: [DataSource.WEB],
    IntentType.LEGAL: [DataSource.RAG, DataSource.LEGIFRANCE, DataSource.UPLOADED_DOCS],
    IntentType.SEND_EMAIL: [DataSource.SQL, DataSource.CONVERSATION],
    IntentType.REQUEST_QUOTES: [DataSource.SQL],
    IntentType.TRIGGER_WORKFLOW: [],
    IntentType.GENERAL_QUESTION: [DataSource.CONVERSATION],
}
