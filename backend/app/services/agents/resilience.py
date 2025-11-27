"""
Agent Resilience Layer
Phase 3.3 - World-Class SMA Architecture

Provides resilience patterns for agents:
- Retry with exponential backoff
- Fallback chains
- Timeout handling
- Graceful degradation

These wrappers ensure agents are robust against
transient failures and service outages.

Author: Claude Code - Phase 3 World-Class SMA
Date: November 27, 2025
"""

import asyncio
import structlog
from typing import List, Optional, Callable, Any, TypeVar
from functools import wraps
from dataclasses import dataclass
import time
import random

from app.services.agents.base_agent import (
    BaseAgent,
    AgentInput,
    AgentOutput,
    AgentCapability,
    AgentMetrics
)

logger = structlog.get_logger()

T = TypeVar('T')


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True  # Add randomness to prevent thundering herd


@dataclass
class TimeoutConfig:
    """Configuration for timeout behavior"""
    timeout_seconds: float = 30.0
    soft_timeout_seconds: Optional[float] = None  # Warning before hard timeout


class RetryError(Exception):
    """Raised when all retry attempts fail"""
    def __init__(self, attempts: int, last_error: Exception):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"Failed after {attempts} attempts: {last_error}")


class TimeoutError(Exception):
    """Raised when operation times out"""
    def __init__(self, timeout_seconds: float):
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Operation timed out after {timeout_seconds}s")


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for retry attempt with exponential backoff"""
    delay = config.base_delay_seconds * (config.exponential_base ** attempt)
    delay = min(delay, config.max_delay_seconds)

    if config.jitter:
        # Add up to 25% random jitter
        jitter = delay * 0.25 * random.random()
        delay += jitter

    return delay


async def retry_async(
    func: Callable,
    config: RetryConfig = None,
    retryable_exceptions: tuple = (Exception,)
) -> Any:
    """
    Execute async function with retry logic

    Args:
        func: Async function to execute
        config: Retry configuration
        retryable_exceptions: Tuple of exception types to retry

    Returns:
        Function result

    Raises:
        RetryError: If all attempts fail
    """
    config = config or RetryConfig()
    last_error = None

    for attempt in range(config.max_attempts):
        try:
            return await func()

        except retryable_exceptions as e:
            last_error = e

            if attempt < config.max_attempts - 1:
                delay = calculate_delay(attempt, config)
                logger.warning(
                    "retry_attempt",
                    attempt=attempt + 1,
                    max_attempts=config.max_attempts,
                    delay_seconds=round(delay, 2),
                    error=str(e)
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "retry_exhausted",
                    attempts=config.max_attempts,
                    error=str(e)
                )

    raise RetryError(config.max_attempts, last_error)


async def with_timeout(
    func: Callable,
    config: TimeoutConfig = None
) -> Any:
    """
    Execute async function with timeout

    Args:
        func: Async function to execute
        config: Timeout configuration

    Returns:
        Function result

    Raises:
        TimeoutError: If operation times out
    """
    config = config or TimeoutConfig()

    try:
        return await asyncio.wait_for(
            func(),
            timeout=config.timeout_seconds
        )
    except asyncio.TimeoutError:
        logger.error(
            "operation_timeout",
            timeout_seconds=config.timeout_seconds
        )
        raise TimeoutError(config.timeout_seconds)


class ResilientAgent(BaseAgent):
    """
    Wrapper that adds resilience to any BaseAgent

    Features:
    - Automatic retry with exponential backoff
    - Configurable timeouts
    - Fallback responses on failure

    Usage:
        base_agent = MyAgent()
        resilient = ResilientAgent(
            agent=base_agent,
            retry_config=RetryConfig(max_attempts=3),
            timeout_config=TimeoutConfig(timeout_seconds=30)
        )
    """

    def __init__(
        self,
        agent: BaseAgent,
        retry_config: RetryConfig = None,
        timeout_config: TimeoutConfig = None,
        fallback_response: str = None
    ):
        super().__init__()
        self._wrapped_agent = agent
        self._retry_config = retry_config or RetryConfig()
        self._timeout_config = timeout_config or TimeoutConfig()
        self._fallback_response = fallback_response or "Je n'ai pas pu traiter votre demande. Veuillez réessayer."

    @property
    def name(self) -> str:
        return f"resilient_{self._wrapped_agent.name}"

    @property
    def description(self) -> str:
        return f"Resilient wrapper for: {self._wrapped_agent.description}"

    @property
    def capabilities(self) -> List[AgentCapability]:
        return self._wrapped_agent.capabilities

    @property
    def version(self) -> str:
        return f"{self._wrapped_agent.version}-resilient"

    async def can_handle(self, query: str, context: dict) -> float:
        """Delegate to wrapped agent"""
        try:
            return await self._wrapped_agent.can_handle(query, context)
        except Exception:
            return 0.0

    async def process(self, input: AgentInput) -> AgentOutput:
        """Process with retry and timeout"""

        async def _process():
            return await self._wrapped_agent.process(input)

        try:
            # Apply timeout
            result = await with_timeout(
                lambda: retry_async(
                    _process,
                    self._retry_config,
                    retryable_exceptions=(Exception,)
                ),
                self._timeout_config
            )
            return result

        except (RetryError, TimeoutError) as e:
            logger.error(
                "resilient_agent_failed",
                agent=self._wrapped_agent.name,
                error=str(e)
            )

            return AgentOutput(
                success=False,
                response=self._fallback_response,
                confidence=0.0,
                warnings=[str(e)],
                metadata={"resilience_error": str(e)}
            )

    async def health_check(self) -> bool:
        """Delegate health check"""
        return await self._wrapped_agent.health_check()


class FallbackChain:
    """
    Chain of agents with automatic fallback

    Tries each agent in sequence until one succeeds.
    Useful for graceful degradation.

    Usage:
        chain = FallbackChain([
            primary_agent,
            secondary_agent,
            fallback_agent
        ])

        result = await chain.execute(input)
    """

    def __init__(
        self,
        agents: List[BaseAgent],
        min_confidence: float = 0.3
    ):
        self.agents = agents
        self.min_confidence = min_confidence
        self._logger = structlog.get_logger().bind(component="FallbackChain")

    async def execute(self, input: AgentInput) -> AgentOutput:
        """
        Execute through the chain until success

        Args:
            input: Agent input

        Returns:
            First successful AgentOutput, or fallback failure response
        """
        errors = []

        for i, agent in enumerate(self.agents):
            try:
                # Check if agent can handle
                confidence = await agent.can_handle(input.query, input.context)

                if confidence < self.min_confidence:
                    self._logger.debug(
                        "agent_skipped_low_confidence",
                        agent=agent.name,
                        confidence=confidence,
                        position=i
                    )
                    continue

                # Try to process
                result = await agent.process_with_metrics(input)

                if result.success and result.confidence >= self.min_confidence:
                    self._logger.info(
                        "fallback_chain_success",
                        agent=agent.name,
                        position=i,
                        confidence=result.confidence
                    )
                    return result

                # Log unsuccessful but continue to next
                self._logger.debug(
                    "agent_result_insufficient",
                    agent=agent.name,
                    success=result.success,
                    confidence=result.confidence
                )

            except Exception as e:
                errors.append((agent.name, str(e)))
                self._logger.warning(
                    "fallback_chain_agent_error",
                    agent=agent.name,
                    position=i,
                    error=str(e)
                )

        # All agents failed
        self._logger.error(
            "fallback_chain_exhausted",
            agents_tried=len(self.agents),
            errors=errors
        )

        return AgentOutput(
            success=False,
            response="Je n'ai pas pu traiter votre demande avec les ressources disponibles.",
            confidence=0.0,
            warnings=[f"Chaîne de {len(self.agents)} agents épuisée"],
            metadata={"errors": errors}
        )

    def add_agent(self, agent: BaseAgent, position: int = None):
        """Add agent to chain at position (default: end)"""
        if position is None:
            self.agents.append(agent)
        else:
            self.agents.insert(position, agent)

    def remove_agent(self, agent_name: str) -> bool:
        """Remove agent from chain by name"""
        for i, agent in enumerate(self.agents):
            if agent.name == agent_name:
                self.agents.pop(i)
                return True
        return False


class ParallelExecutor:
    """
    Execute multiple agents in parallel and combine results

    Useful for:
    - Gathering information from multiple sources
    - Ensemble approaches
    - Speed optimization

    Usage:
        executor = ParallelExecutor([agent1, agent2, agent3])
        results = await executor.execute(input)
    """

    def __init__(
        self,
        agents: List[BaseAgent],
        timeout_seconds: float = 30.0,
        require_all: bool = False
    ):
        self.agents = agents
        self.timeout_seconds = timeout_seconds
        self.require_all = require_all
        self._logger = structlog.get_logger().bind(component="ParallelExecutor")

    async def execute(self, input: AgentInput) -> List[AgentOutput]:
        """
        Execute all agents in parallel

        Args:
            input: Agent input

        Returns:
            List of AgentOutput from all agents (may include failures)
        """

        async def _execute_agent(agent: BaseAgent) -> AgentOutput:
            try:
                return await asyncio.wait_for(
                    agent.process_with_metrics(input),
                    timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                return AgentOutput(
                    success=False,
                    response="Timeout",
                    confidence=0.0,
                    agent_name=agent.name,
                    warnings=["Agent timed out"]
                )
            except Exception as e:
                return AgentOutput(
                    success=False,
                    response=str(e),
                    confidence=0.0,
                    agent_name=agent.name,
                    warnings=[str(e)]
                )

        # Execute all in parallel
        results = await asyncio.gather(
            *[_execute_agent(agent) for agent in self.agents]
        )

        successful = sum(1 for r in results if r.success)
        self._logger.info(
            "parallel_execution_complete",
            total=len(self.agents),
            successful=successful
        )

        if self.require_all and successful < len(self.agents):
            self._logger.warning(
                "parallel_execution_partial_failure",
                required=len(self.agents),
                successful=successful
            )

        return list(results)

    async def execute_best(self, input: AgentInput) -> AgentOutput:
        """
        Execute all and return best result

        Args:
            input: Agent input

        Returns:
            AgentOutput with highest confidence
        """
        results = await self.execute(input)

        # Filter successful and sort by confidence
        successful = [r for r in results if r.success]

        if not successful:
            return AgentOutput(
                success=False,
                response="Aucun agent n'a réussi à traiter la demande.",
                confidence=0.0,
                warnings=["Tous les agents ont échoué"]
            )

        best = max(successful, key=lambda r: r.confidence)
        return best


# ================================================================
# DECORATORS FOR RESILIENCE
# ================================================================

def with_retry(config: RetryConfig = None):
    """
    Decorator to add retry logic to agent methods

    Usage:
        @with_retry(RetryConfig(max_attempts=3))
        async def process(self, input: AgentInput) -> AgentOutput:
            ...
    """
    config = config or RetryConfig()

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(
                lambda: func(*args, **kwargs),
                config
            )
        return wrapper
    return decorator


def with_fallback(fallback_response: str):
    """
    Decorator to add fallback response on failure

    Usage:
        @with_fallback("Désolé, je n'ai pas pu traiter votre demande.")
        async def process(self, input: AgentInput) -> AgentOutput:
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error("fallback_triggered", error=str(e))
                return AgentOutput(
                    success=False,
                    response=fallback_response,
                    confidence=0.0,
                    warnings=[str(e)]
                )
        return wrapper
    return decorator
