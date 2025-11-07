"""
Orchestrator Factory - Singleton Pattern

Provides a single shared instance of OrchestratorAgent to avoid
re-instantiation overhead (400ms per request).

Usage:
    from app.services.agents.orchestrator_factory import get_orchestrator

    orchestrator = get_orchestrator()
    result = await orchestrator.process(...)

Author: Claude Code
Date: November 2025
"""

import structlog
from typing import Optional
from .orchestrator_agent import OrchestratorAgent

logger = structlog.get_logger()

# Global singleton instance
_orchestrator_instance: Optional[OrchestratorAgent] = None


def get_orchestrator() -> OrchestratorAgent:
    """
    Get or create the singleton orchestrator instance

    Returns:
        OrchestratorAgent: Shared orchestrator instance
    """
    global _orchestrator_instance

    if _orchestrator_instance is None:
        logger.info("orchestrator_singleton_creating")
        _orchestrator_instance = OrchestratorAgent()
        logger.info("orchestrator_singleton_created")

    return _orchestrator_instance


def reset_orchestrator():
    """
    Reset the singleton (useful for testing or config changes)

    WARNING: Only call this during testing or after config changes.
    Do NOT call during normal operation.
    """
    global _orchestrator_instance

    logger.warning("orchestrator_singleton_reset")
    _orchestrator_instance = None
