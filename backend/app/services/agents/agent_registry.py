"""
Agent Registry
Phase 3.1 - World-Class SMA Architecture

Central registry for all agents in the system.
Provides:
- Agent registration and discovery
- Smart routing based on capabilities
- Health monitoring
- Metrics aggregation

Usage:
    from app.services.agents.agent_registry import AgentRegistry, registry

    # Register an agent
    registry.register(MyAgent())

    # Get agent by name
    agent = registry.get("my_agent")

    # Find capable agents for a query
    agents = await registry.find_capable("What is the budget?", context)

    # Get all metrics
    metrics = registry.get_all_metrics()

Author: Claude Code - Phase 3 World-Class SMA
Date: November 27, 2025
"""

import structlog
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import asyncio

from app.services.agents.base_agent import (
    BaseAgent,
    AgentCapability,
    AgentInput,
    AgentOutput,
    AgentMetrics
)

logger = structlog.get_logger()


class AgentRegistry:
    """
    Central registry for all SMA agents

    Singleton pattern - use `registry` instance or `get_registry()`

    Features:
    - Agent registration with duplicate detection
    - Discovery by name or capability
    - Smart routing with confidence scoring
    - Health monitoring
    - Aggregated metrics
    """

    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self._agents_by_capability: Dict[AgentCapability, List[str]] = {}
        self._initialization_time = datetime.now()
        self._initialized = False

        logger.info("agent_registry_created")

    def register(self, agent: BaseAgent) -> bool:
        """
        Register an agent in the registry

        Args:
            agent: Agent instance to register

        Returns:
            True if registered, False if already exists
        """
        if agent.name in self._agents:
            logger.warning("agent_already_registered", agent=agent.name)
            return False

        self._agents[agent.name] = agent

        # Index by capabilities
        for capability in agent.capabilities:
            if capability not in self._agents_by_capability:
                self._agents_by_capability[capability] = []
            self._agents_by_capability[capability].append(agent.name)

        logger.info(
            "agent_registered",
            agent=agent.name,
            version=agent.version,
            capabilities=[c.value for c in agent.capabilities]
        )

        return True

    def unregister(self, agent_name: str) -> bool:
        """
        Remove an agent from the registry

        Args:
            agent_name: Name of agent to remove

        Returns:
            True if removed, False if not found
        """
        if agent_name not in self._agents:
            return False

        agent = self._agents[agent_name]

        # Remove from capability index
        for capability in agent.capabilities:
            if capability in self._agents_by_capability:
                self._agents_by_capability[capability].remove(agent_name)

        del self._agents[agent_name]

        logger.info("agent_unregistered", agent=agent_name)
        return True

    def get(self, name: str) -> Optional[BaseAgent]:
        """
        Get agent by name

        Args:
            name: Agent name

        Returns:
            Agent instance or None
        """
        return self._agents.get(name)

    def get_all(self) -> List[BaseAgent]:
        """Get all registered agents"""
        return list(self._agents.values())

    def get_by_capability(self, capability: AgentCapability) -> List[BaseAgent]:
        """
        Get all agents with a specific capability

        Args:
            capability: Required capability

        Returns:
            List of agents with that capability
        """
        agent_names = self._agents_by_capability.get(capability, [])
        return [self._agents[name] for name in agent_names if name in self._agents]

    async def find_capable(
        self,
        query: str,
        context: Dict[str, Any],
        min_confidence: float = 0.3,
        max_agents: int = 5
    ) -> List[Tuple[BaseAgent, float]]:
        """
        Find all agents capable of handling a query

        Args:
            query: User query
            context: Request context
            min_confidence: Minimum confidence threshold
            max_agents: Maximum number of agents to return

        Returns:
            List of (agent, confidence) tuples, sorted by confidence desc
        """
        results = []

        # Gather confidence scores in parallel
        async def get_confidence(agent: BaseAgent) -> Tuple[BaseAgent, float]:
            try:
                confidence = await agent.can_handle(query, context)
                return (agent, confidence)
            except Exception as e:
                logger.warning(
                    "agent_can_handle_failed",
                    agent=agent.name,
                    error=str(e)
                )
                return (agent, 0.0)

        confidence_results = await asyncio.gather(
            *[get_confidence(agent) for agent in self._agents.values()]
        )

        # Filter by minimum confidence
        results = [
            (agent, conf) for agent, conf in confidence_results
            if conf >= min_confidence
        ]

        # Sort by confidence (highest first)
        results.sort(key=lambda x: x[1], reverse=True)

        # Limit results
        results = results[:max_agents]

        logger.debug(
            "find_capable_complete",
            query=query[:50],
            found=len(results),
            agents=[a.name for a, _ in results]
        )

        return results

    async def route_to_best(
        self,
        input: AgentInput,
        min_confidence: float = 0.3
    ) -> Optional[AgentOutput]:
        """
        Route query to the best capable agent

        Args:
            input: Agent input
            min_confidence: Minimum confidence to process

        Returns:
            AgentOutput from best agent, or None if no agent capable
        """
        capable = await self.find_capable(
            input.query,
            input.context,
            min_confidence=min_confidence,
            max_agents=1
        )

        if not capable:
            logger.warning(
                "no_capable_agent_found",
                query=input.query[:50]
            )
            return None

        best_agent, confidence = capable[0]

        logger.info(
            "routing_to_agent",
            agent=best_agent.name,
            confidence=confidence,
            query=input.query[:50]
        )

        return await best_agent.process_with_metrics(input)

    async def health_check_all(self) -> Dict[str, bool]:
        """
        Run health check on all agents

        Returns:
            Dict of agent_name -> healthy (bool)
        """
        results = {}

        async def check_agent(agent: BaseAgent) -> Tuple[str, bool]:
            try:
                healthy = await agent.health_check()
                return (agent.name, healthy)
            except Exception as e:
                logger.error(
                    "agent_health_check_failed",
                    agent=agent.name,
                    error=str(e)
                )
                return (agent.name, False)

        checks = await asyncio.gather(
            *[check_agent(agent) for agent in self._agents.values()]
        )

        for name, healthy in checks:
            results[name] = healthy

        healthy_count = sum(1 for h in results.values() if h)
        logger.info(
            "health_check_complete",
            total=len(results),
            healthy=healthy_count
        )

        return results

    async def initialize_all(self) -> Dict[str, bool]:
        """
        Initialize all agents

        Returns:
            Dict of agent_name -> initialized (bool)
        """
        results = {}

        for agent in self._agents.values():
            try:
                success = await agent.initialize()
                results[agent.name] = success
                logger.info(
                    "agent_initialized",
                    agent=agent.name,
                    success=success
                )
            except Exception as e:
                results[agent.name] = False
                logger.error(
                    "agent_initialization_failed",
                    agent=agent.name,
                    error=str(e)
                )

        self._initialized = True
        return results

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get metrics from all agents

        Returns:
            Dict of agent_name -> metrics dict
        """
        return {
            name: agent.metrics.to_dict()
            for name, agent in self._agents.items()
        }

    def get_aggregated_metrics(self) -> Dict[str, Any]:
        """
        Get aggregated metrics across all agents

        Returns:
            Summary statistics
        """
        total_calls = 0
        total_successes = 0
        total_failures = 0
        total_latency = 0.0

        for agent in self._agents.values():
            metrics = agent.metrics
            total_calls += metrics.total_calls
            total_successes += metrics.successful_calls
            total_failures += metrics.failed_calls
            total_latency += metrics.total_latency_ms

        return {
            "total_agents": len(self._agents),
            "total_calls": total_calls,
            "total_successes": total_successes,
            "total_failures": total_failures,
            "overall_success_rate": total_successes / max(total_calls, 1),
            "total_latency_ms": total_latency,
            "avg_latency_ms": total_latency / max(total_calls, 1),
            "uptime_seconds": (datetime.now() - self._initialization_time).total_seconds(),
            "agents_by_capability": {
                cap.value: len(agents)
                for cap, agents in self._agents_by_capability.items()
            }
        }

    def get_status(self) -> Dict[str, Any]:
        """
        Get complete registry status

        Returns:
            Full status including all agents
        """
        return {
            "initialized": self._initialized,
            "initialization_time": self._initialization_time.isoformat(),
            "agent_count": len(self._agents),
            "agents": {
                name: agent.get_status()
                for name, agent in self._agents.items()
            },
            "aggregated_metrics": self.get_aggregated_metrics(),
        }

    def list_agents(self) -> List[Dict[str, Any]]:
        """
        List all agents with basic info

        Returns:
            List of agent summaries
        """
        return [
            {
                "name": agent.name,
                "description": agent.description,
                "version": agent.version,
                "capabilities": [c.value for c in agent.capabilities],
                "metrics_summary": {
                    "calls": agent.metrics.total_calls,
                    "success_rate": agent.metrics.success_rate,
                    "avg_latency_ms": agent.metrics.avg_latency_ms,
                }
            }
            for agent in self._agents.values()
        ]

    def __len__(self) -> int:
        return len(self._agents)

    def __contains__(self, name: str) -> bool:
        return name in self._agents

    def __repr__(self) -> str:
        return f"<AgentRegistry(agents={len(self._agents)})>"


# ================================================================
# SINGLETON INSTANCE
# ================================================================

_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """Get or create singleton registry instance"""
    global _registry

    if _registry is None:
        _registry = AgentRegistry()

    return _registry


# Convenience alias
registry = get_registry()


# ================================================================
# AUTO-REGISTRATION DECORATOR
# ================================================================

def register_agent(cls):
    """
    Decorator to auto-register an agent class

    Usage:
        @register_agent
        class MyAgent(BaseAgent):
            ...
    """
    # Create instance and register
    instance = cls()
    get_registry().register(instance)
    return cls


# ================================================================
# AGENT DISCOVERY HELPERS
# ================================================================

async def discover_and_register_agents():
    """
    Discover and register all available agents

    Called at application startup to populate the registry
    with all production agents.
    """
    from app.services.agents.base_agent import AgentCapability

    reg = get_registry()

    # Import and register production agents
    # These are wrapped versions that implement BaseAgent

    try:
        from app.services.agents.wrapped_agents import (
            WrappedSQLAgent,
            WrappedEmailAgent,
            WrappedLegalAgent,
            WrappedOCRAgent,
            WrappedSynthesisAgent,
            WrappedReflectionAgent,
            WrappedWorkflowAgent,
            WrappedWebSearchAgent,
            WrappedDigestAgent,
        )

        agents_to_register = [
            WrappedSQLAgent(),
            WrappedEmailAgent(),
            WrappedLegalAgent(),
            WrappedOCRAgent(),
            WrappedSynthesisAgent(),
            WrappedReflectionAgent(),
            WrappedWorkflowAgent(),
            WrappedWebSearchAgent(),
            WrappedDigestAgent(),
        ]

        for agent in agents_to_register:
            reg.register(agent)

        logger.info(
            "agents_discovered_and_registered",
            count=len(agents_to_register)
        )

    except ImportError as e:
        logger.warning(
            "agent_discovery_partial",
            error=str(e),
            message="Some agents could not be imported"
        )

    return reg
