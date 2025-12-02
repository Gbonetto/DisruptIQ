"""
Orchestrator Factory - Singleton Pattern with Core-First Support

Provides singleton instances for:
- OrchestratorAgent (legacy): Full multi-agent orchestration
- CoreFirstOrchestrator (new): Simplified SQL+RAG core with suggestions

Feature Flags:
- USE_CORE_FIRST_ORCHESTRATOR: Enable new Core-First pipeline (default: False)
  Set to True to use the simplified pipeline with suggestions

Usage:
    from app.services.agents.orchestrator_factory import get_orchestrator

    orchestrator = get_orchestrator()
    result = await orchestrator.process(...)

Author: Claude Code
Date: December 2024
"""

import os
import structlog
from typing import Optional, Union
from .orchestrator_agent import OrchestratorAgent

logger = structlog.get_logger()

# Feature flag for Core-First pipeline
# Set CORE_FIRST_ENABLED=true in environment to activate
USE_CORE_FIRST_ORCHESTRATOR = os.getenv("CORE_FIRST_ENABLED", "false").lower() == "true"

# Global singleton instances
_orchestrator_instance: Optional[OrchestratorAgent] = None
_core_first_instance = None  # CoreFirstOrchestrator


def get_orchestrator() -> OrchestratorAgent:
    """
    Get or create the singleton orchestrator instance.

    By default, returns the legacy OrchestratorAgent.
    If CORE_FIRST_ENABLED=true, still returns legacy orchestrator
    (use get_core_first_orchestrator() for the new pipeline).

    Returns:
        OrchestratorAgent: Shared orchestrator instance
    """
    global _orchestrator_instance

    if _orchestrator_instance is None:
        logger.info("orchestrator_singleton_creating",
                   core_first_available=USE_CORE_FIRST_ORCHESTRATOR)
        _orchestrator_instance = OrchestratorAgent()
        logger.info("orchestrator_singleton_created")

    return _orchestrator_instance


def get_core_first_orchestrator():
    """
    Get or create the Core-First orchestrator singleton.

    This is the new simplified pipeline:
    - Core (SQL+RAG) executed in parallel
    - Suggestions for Legal/Web (one-shot, non-persistent)
    - Short-circuit for pure legal/web queries (rare)

    Returns:
        CoreFirstOrchestrator or None if not initialized
    """
    global _core_first_instance

    if _core_first_instance is None and USE_CORE_FIRST_ORCHESTRATOR:
        try:
            from .core_first_orchestrator import CoreFirstOrchestrator
            from app.services.rag_service import RAGService

            # Get agents from legacy orchestrator
            legacy = get_orchestrator()

            # Initialize with required agents
            # Note: sql_agent and synthesis_agent need to be extracted from legacy
            _core_first_instance = CoreFirstOrchestrator(
                sql_agent=getattr(legacy, 'hybrid_executor', None),  # Uses SQL via hybrid
                rag_service=RAGService(),
                synthesis_agent=getattr(legacy, 'fusion_agent', None),
                legal_agent=None,  # Will be lazy loaded if needed
                web_agent=None,    # Will be lazy loaded if needed
            )

            logger.info("core_first_orchestrator_initialized",
                       has_sql=_core_first_instance._sql_agent is not None,
                       has_rag=_core_first_instance._rag_service is not None)

        except Exception as e:
            logger.error("core_first_orchestrator_init_failed", error=str(e))
            return None

    return _core_first_instance


def reset_orchestrator():
    """
    Reset all singletons (useful for testing or config changes)

    WARNING: Only call this during testing or after config changes.
    Do NOT call during normal operation.
    """
    global _orchestrator_instance, _core_first_instance

    logger.warning("orchestrator_singleton_reset",
                  had_legacy=_orchestrator_instance is not None,
                  had_core_first=_core_first_instance is not None)

    _orchestrator_instance = None
    _core_first_instance = None


def is_core_first_enabled() -> bool:
    """Check if Core-First pipeline is enabled."""
    return USE_CORE_FIRST_ORCHESTRATOR


# Diagnostic function for debugging
def get_orchestrator_status() -> dict:
    """
    Get status of orchestrator singletons.

    Returns:
        dict with status info for debugging
    """
    return {
        "core_first_enabled": USE_CORE_FIRST_ORCHESTRATOR,
        "legacy_initialized": _orchestrator_instance is not None,
        "core_first_initialized": _core_first_instance is not None,
        "active_orchestrator": "core_first" if USE_CORE_FIRST_ORCHESTRATOR and _core_first_instance else "legacy"
    }
