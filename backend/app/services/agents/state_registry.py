"""
Global State Registry - Shared across all endpoints

This module provides a single source of truth for StateManagers
to ensure state is shared between documents.py and assistant endpoints.
"""

import structlog
from typing import Dict
from app.services.agents.conversation_state import StateManager

logger = structlog.get_logger()

# Global registry (singleton pattern)
_state_managers: Dict[str, StateManager] = {}


def get_state_manager(session_id: str) -> StateManager:
    """
    Get or create state manager for session

    Args:
        session_id: Session identifier

    Returns:
        StateManager instance for this session
    """
    if session_id not in _state_managers:
        _state_managers[session_id] = StateManager()
        logger.info("state_manager_created", session_id=session_id)
    return _state_managers[session_id]


def cleanup_state_manager(session_id: str):
    """
    Cleanup state manager for session

    Args:
        session_id: Session identifier
    """
    if session_id in _state_managers:
        del _state_managers[session_id]
        logger.info("state_manager_cleaned_up", session_id=session_id)
