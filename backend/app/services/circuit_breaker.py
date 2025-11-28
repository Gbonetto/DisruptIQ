"""
Circuit Breaker Pattern for External Service Resilience
Phase 1.4 - World-Class SMA Optimization

Prevents cascading failures when external services (LLM, Qdrant, etc.) are down.

States:
- CLOSED: Normal operation, requests go through
- OPEN: Service is down, requests fail fast
- HALF_OPEN: Testing if service recovered

Benefits:
- Fail-fast when service is down (no waiting for timeouts)
- Automatic recovery detection
- Prevents resource exhaustion
- Detailed metrics for monitoring

Author: Claude Code - Phase 1 World-Class SMA
Date: November 27, 2025
"""

import asyncio
import time
import structlog
from typing import Callable, Any, Optional, Dict, TypeVar, Generic
from enum import Enum
from dataclasses import dataclass, field
from functools import wraps
from datetime import datetime, timedelta

logger = structlog.get_logger()

T = TypeVar('T')


class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitStats:
    """Statistics for circuit breaker monitoring"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0  # Calls rejected when circuit is OPEN
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    state_changes: int = 0
    last_state_change: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "success_rate": self.successful_calls / max(self.total_calls, 1),
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_success": self.last_success_time.isoformat() if self.last_success_time else None,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "state_changes": self.state_changes,
        }


class CircuitBreakerError(Exception):
    """Raised when circuit is OPEN and call is rejected"""

    def __init__(self, service_name: str, retry_after: float):
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker OPEN for {service_name}. "
            f"Retry after {retry_after:.1f}s"
        )


class CircuitBreaker:
    """
    Circuit Breaker implementation for async functions

    Usage:
        breaker = CircuitBreaker(
            name="mistral_llm",
            failure_threshold=5,
            recovery_timeout=30.0,
            half_open_max_calls=3
        )

        @breaker.protect
        async def call_llm(prompt: str):
            return await mistral.chat(prompt)

        # Or manually:
        result = await breaker.call(some_async_function, arg1, arg2)
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
        success_threshold: int = 2,
        excluded_exceptions: tuple = ()
    ):
        """
        Initialize circuit breaker

        Args:
            name: Service name (for logging)
            failure_threshold: Failures before opening circuit
            recovery_timeout: Seconds before trying half-open
            half_open_max_calls: Max calls in half-open state
            success_threshold: Successes in half-open to close circuit
            excluded_exceptions: Exceptions that don't count as failures
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.success_threshold = success_threshold
        self.excluded_exceptions = excluded_exceptions

        self._state = CircuitState.CLOSED
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._stats = CircuitStats()
        self._lock = asyncio.Lock()

        logger.info("circuit_breaker_initialized",
                   name=name,
                   failure_threshold=failure_threshold,
                   recovery_timeout=recovery_timeout)

    @property
    def state(self) -> CircuitState:
        """Get current circuit state (may auto-transition to HALF_OPEN)"""
        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    # Transition to HALF_OPEN
                    self._transition_to(CircuitState.HALF_OPEN)
        return self._state

    @property
    def stats(self) -> CircuitStats:
        """Get circuit breaker statistics"""
        return self._stats

    def _transition_to(self, new_state: CircuitState):
        """Transition to a new state with logging"""
        old_state = self._state
        self._state = new_state
        self._stats.state_changes += 1
        self._stats.last_state_change = datetime.now()

        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0

        logger.info("circuit_breaker_state_change",
                   name=self.name,
                   from_state=old_state.value,
                   to_state=new_state.value)

    def _record_success(self):
        """Record a successful call"""
        self._stats.total_calls += 1
        self._stats.successful_calls += 1
        self._stats.last_success_time = datetime.now()
        self._stats.consecutive_successes += 1
        self._stats.consecutive_failures = 0

        if self._state == CircuitState.HALF_OPEN:
            if self._stats.consecutive_successes >= self.success_threshold:
                # Service recovered, close circuit
                self._transition_to(CircuitState.CLOSED)

    def _record_failure(self, error: Exception):
        """Record a failed call"""
        self._stats.total_calls += 1
        self._stats.failed_calls += 1
        self._stats.last_failure_time = datetime.now()
        self._stats.consecutive_failures += 1
        self._stats.consecutive_successes = 0
        self._last_failure_time = time.time()

        logger.warning("circuit_breaker_failure",
                      name=self.name,
                      error=str(error),
                      consecutive_failures=self._stats.consecutive_failures)

        if self._state == CircuitState.CLOSED:
            if self._stats.consecutive_failures >= self.failure_threshold:
                # Too many failures, open circuit
                self._transition_to(CircuitState.OPEN)

        elif self._state == CircuitState.HALF_OPEN:
            # Failure in half-open, reopen circuit
            self._transition_to(CircuitState.OPEN)

    def _can_execute(self) -> bool:
        """Check if a call can be executed"""
        state = self.state  # This may auto-transition

        if state == CircuitState.CLOSED:
            return True

        elif state == CircuitState.OPEN:
            return False

        elif state == CircuitState.HALF_OPEN:
            # Allow limited calls in half-open
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

        return False

    async def call(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """
        Execute a function through the circuit breaker

        Args:
            func: Async function to call
            *args, **kwargs: Function arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is OPEN
            Original exception: If function fails
        """
        async with self._lock:
            if not self._can_execute():
                self._stats.rejected_calls += 1
                retry_after = self.recovery_timeout - (time.time() - (self._last_failure_time or 0))
                raise CircuitBreakerError(self.name, max(0, retry_after))

        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                # Run sync function in thread pool
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: func(*args, **kwargs))

            # Record success
            async with self._lock:
                self._record_success()

            return result

        except Exception as e:
            # Check if this exception should be excluded
            if isinstance(e, self.excluded_exceptions):
                async with self._lock:
                    self._record_success()  # Don't count as failure
                raise

            # Record failure
            async with self._lock:
                self._record_failure(e)

            raise

    def protect(self, func: Callable) -> Callable:
        """
        Decorator to protect an async function with circuit breaker

        Usage:
            @breaker.protect
            async def call_external_api():
                ...
        """
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.call(func, *args, **kwargs)
        return wrapper

    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status for monitoring"""
        return {
            "name": self.name,
            "state": self.state.value,
            "config": {
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
                "half_open_max_calls": self.half_open_max_calls,
                "success_threshold": self.success_threshold,
            },
            "stats": self._stats.to_dict(),
        }

    def reset(self):
        """Manually reset circuit breaker to CLOSED state"""
        self._state = CircuitState.CLOSED
        self._stats.consecutive_failures = 0
        self._stats.consecutive_successes = 0
        self._last_failure_time = None
        self._half_open_calls = 0

        logger.info("circuit_breaker_manual_reset", name=self.name)


# ================================================================
# PRE-CONFIGURED CIRCUIT BREAKERS FOR DISRUPTIQ SERVICES
# ================================================================

# Circuit breaker for Mistral LLM API
mistral_breaker = CircuitBreaker(
    name="mistral_llm",
    failure_threshold=3,      # Open after 3 consecutive failures
    recovery_timeout=30.0,    # Try again after 30 seconds
    half_open_max_calls=2,    # Allow 2 test calls
    success_threshold=2,      # Need 2 successes to close
)

# Circuit breaker for Qdrant vector database
qdrant_breaker = CircuitBreaker(
    name="qdrant_db",
    failure_threshold=5,      # More tolerant (DB should be stable)
    recovery_timeout=15.0,    # Quick retry for local service
    half_open_max_calls=3,
    success_threshold=2,
)

# Circuit breaker for external web services (N8N, Gmail, etc.)
external_api_breaker = CircuitBreaker(
    name="external_api",
    failure_threshold=3,
    recovery_timeout=60.0,    # Longer timeout for external services
    half_open_max_calls=1,
    success_threshold=1,
)

# Circuit breaker for reranking model
reranker_breaker = CircuitBreaker(
    name="reranker_model",
    failure_threshold=3,
    recovery_timeout=20.0,
    half_open_max_calls=2,
    success_threshold=2,
)


def get_all_breaker_status() -> Dict[str, Dict[str, Any]]:
    """Get status of all circuit breakers for monitoring"""
    return {
        "mistral_llm": mistral_breaker.get_status(),
        "qdrant_db": qdrant_breaker.get_status(),
        "external_api": external_api_breaker.get_status(),
        "reranker_model": reranker_breaker.get_status(),
    }
