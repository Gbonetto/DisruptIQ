"""
Base Agent Interface
Phase 3.1 - World-Class SMA Architecture

Provides a common interface for all agents in the system.
This is the foundation for:
- Uniform agent behavior
- Registry pattern
- Metrics collection
- Testability
- Extensibility

All agents should inherit from BaseAgent and implement
the required abstract methods.

Author: Claude Code - Phase 3 World-Class SMA
Date: November 27, 2025
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import structlog
import time
import asyncio

logger = structlog.get_logger()


class AgentCapability(str, Enum):
    """Standard capabilities agents can declare"""
    TEXT_GENERATION = "text_generation"
    DATA_QUERY = "data_query"
    DOCUMENT_ANALYSIS = "document_analysis"
    EMAIL_GENERATION = "email_generation"
    LEGAL_ANALYSIS = "legal_analysis"
    WEB_SEARCH = "web_search"
    WORKFLOW_TRIGGER = "workflow_trigger"
    OCR_EXTRACTION = "ocr_extraction"
    SYNTHESIS = "synthesis"
    REFLECTION = "reflection"
    ENTITY_EXTRACTION = "entity_extraction"
    TABLE_GENERATION = "table_generation"


@dataclass
class AgentInput:
    """
    Standardized input for all agents

    This ensures all agents receive the same context structure,
    making them interchangeable and testable.
    """
    query: str
    context: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    thought_stream: Optional[Any] = None  # ThoughtStream instance
    db_session: Optional[Any] = None  # AsyncSession
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "context": self.context,
            "conversation_history_length": len(self.conversation_history),
            "has_thought_stream": self.thought_stream is not None,
            "has_db_session": self.db_session is not None,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "session_id": self.session_id,
            "metadata": self.metadata,
        }


@dataclass
class AgentOutput:
    """
    Standardized output from all agents

    Provides consistent response structure for:
    - Success/failure indication
    - Response content
    - Confidence scoring
    - Source attribution
    - Suggestions for follow-up
    """
    success: bool
    response: str
    data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    sources: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0
    agent_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "response": self.response,
            "data": self.data,
            "confidence": self.confidence,
            "sources": self.sources,
            "suggestions": self.suggestions,
            "warnings": self.warnings,
            "metadata": self.metadata,
            "processing_time_ms": self.processing_time_ms,
            "agent_name": self.agent_name,
        }


@dataclass
class AgentMetrics:
    """
    Metrics collected for each agent

    Enables:
    - Performance monitoring
    - Error tracking
    - Optimization targeting
    """
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0.0
    total_confidence: float = 0.0
    last_call_time: Optional[datetime] = None
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    errors_by_type: Dict[str, int] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Calculate success rate (0-1)"""
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency in milliseconds"""
        if self.total_calls == 0:
            return 0.0
        return self.total_latency_ms / self.total_calls

    @property
    def avg_confidence(self) -> float:
        """Calculate average confidence score"""
        if self.successful_calls == 0:
            return 0.0
        return self.total_confidence / self.successful_calls

    def record_success(self, latency_ms: float, confidence: float):
        """Record a successful call"""
        self.total_calls += 1
        self.successful_calls += 1
        self.total_latency_ms += latency_ms
        self.total_confidence += confidence
        self.last_call_time = datetime.now()

    def record_failure(self, latency_ms: float, error: str):
        """Record a failed call"""
        self.total_calls += 1
        self.failed_calls += 1
        self.total_latency_ms += latency_ms
        self.last_error = error
        self.last_error_time = datetime.now()
        self.last_call_time = datetime.now()

        # Track error types
        error_type = type(error).__name__ if isinstance(error, Exception) else "Unknown"
        self.errors_by_type[error_type] = self.errors_by_type.get(error_type, 0) + 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": round(self.success_rate, 3),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "avg_confidence": round(self.avg_confidence, 3),
            "last_call_time": self.last_call_time.isoformat() if self.last_call_time else None,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
            "errors_by_type": self.errors_by_type,
        }


class BaseAgent(ABC):
    """
    Abstract base class for all agents

    All agents in DisruptIQ must inherit from this class and implement:
    - name: Unique identifier
    - description: Human-readable description
    - capabilities: List of AgentCapability
    - process(): Main processing method
    - can_handle(): Confidence scoring for routing

    Optional overrides:
    - health_check(): Service health verification
    - initialize(): Async initialization
    - cleanup(): Resource cleanup

    Usage:
        class MyAgent(BaseAgent):
            @property
            def name(self) -> str:
                return "my_agent"

            @property
            def description(self) -> str:
                return "Does something useful"

            @property
            def capabilities(self) -> List[AgentCapability]:
                return [AgentCapability.TEXT_GENERATION]

            async def process(self, input: AgentInput) -> AgentOutput:
                # Implementation
                pass

            async def can_handle(self, query: str, context: Dict) -> float:
                # Return confidence 0-1
                return 0.8
    """

    def __init__(self):
        self._metrics = AgentMetrics()
        self._initialized = False
        self._logger = structlog.get_logger().bind(agent=self.name)

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique agent identifier"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what the agent does"""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> List[AgentCapability]:
        """List of capabilities this agent provides"""
        pass

    @property
    def version(self) -> str:
        """Agent version (override for versioned agents)"""
        return "1.0.0"

    @property
    def metrics(self) -> AgentMetrics:
        """Get agent metrics"""
        return self._metrics

    @abstractmethod
    async def process(self, input: AgentInput) -> AgentOutput:
        """
        Main processing method - MUST be implemented by all agents

        Args:
            input: Standardized AgentInput

        Returns:
            AgentOutput with results
        """
        pass

    @abstractmethod
    async def can_handle(self, query: str, context: Dict[str, Any]) -> float:
        """
        Determine confidence (0-1) that this agent can handle the query

        Used by the registry for smart routing.

        Args:
            query: User query
            context: Request context

        Returns:
            Confidence score (0.0 = cannot handle, 1.0 = perfect match)
        """
        pass

    async def process_with_metrics(self, input: AgentInput) -> AgentOutput:
        """
        Process with automatic metrics collection

        Wraps process() to collect:
        - Latency
        - Success/failure
        - Confidence scores
        """
        start_time = time.time()

        try:
            output = await self.process(input)

            latency_ms = (time.time() - start_time) * 1000
            output.processing_time_ms = latency_ms
            output.agent_name = self.name

            if output.success:
                self._metrics.record_success(latency_ms, output.confidence)
            else:
                self._metrics.record_failure(latency_ms, "Process returned success=False")

            self._logger.info(
                "agent_process_complete",
                success=output.success,
                confidence=output.confidence,
                latency_ms=round(latency_ms, 2)
            )

            return output

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._metrics.record_failure(latency_ms, str(e))

            self._logger.error(
                "agent_process_failed",
                error=str(e),
                latency_ms=round(latency_ms, 2),
                exc_info=True
            )

            return AgentOutput(
                success=False,
                response=f"Erreur lors du traitement: {str(e)}",
                confidence=0.0,
                processing_time_ms=latency_ms,
                agent_name=self.name,
                warnings=[str(e)]
            )

    async def health_check(self) -> bool:
        """
        Check if agent is healthy and ready to process

        Override to add service-specific health checks
        (e.g., API connectivity, model loading)
        """
        return True

    async def initialize(self) -> bool:
        """
        Async initialization (called once at startup)

        Override for agents that need async setup
        (e.g., loading models, warming caches)
        """
        self._initialized = True
        return True

    async def cleanup(self):
        """
        Cleanup resources before shutdown

        Override for agents with resources to release
        """
        pass

    def get_status(self) -> Dict[str, Any]:
        """Get agent status for monitoring"""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "capabilities": [c.value for c in self.capabilities],
            "initialized": self._initialized,
            "metrics": self._metrics.to_dict(),
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name}, version={self.version})>"


class CompositeAgent(BaseAgent):
    """
    Agent that combines multiple sub-agents

    Useful for complex workflows that require
    multiple specialized agents working together.
    """

    def __init__(self, agents: List[BaseAgent]):
        super().__init__()
        self.agents = agents

    @property
    def name(self) -> str:
        return "composite_agent"

    @property
    def description(self) -> str:
        agent_names = [a.name for a in self.agents]
        return f"Composite agent combining: {', '.join(agent_names)}"

    @property
    def capabilities(self) -> List[AgentCapability]:
        """Combine capabilities from all sub-agents"""
        all_caps = set()
        for agent in self.agents:
            all_caps.update(agent.capabilities)
        return list(all_caps)

    async def can_handle(self, query: str, context: Dict[str, Any]) -> float:
        """Return max confidence from sub-agents"""
        confidences = await asyncio.gather(
            *[agent.can_handle(query, context) for agent in self.agents]
        )
        return max(confidences) if confidences else 0.0

    async def process(self, input: AgentInput) -> AgentOutput:
        """
        Process through all sub-agents and combine results

        Override for custom combination logic
        """
        results = []

        for agent in self.agents:
            confidence = await agent.can_handle(input.query, input.context)
            if confidence > 0.3:
                result = await agent.process_with_metrics(input)
                results.append((agent.name, result, confidence))

        if not results:
            return AgentOutput(
                success=False,
                response="Aucun agent n'a pu traiter cette demande.",
                confidence=0.0
            )

        # Return best result by confidence
        results.sort(key=lambda x: x[2], reverse=True)
        best_name, best_result, best_conf = results[0]

        return best_result
