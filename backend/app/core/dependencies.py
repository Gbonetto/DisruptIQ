"""
FastAPI Dependencies
Service factories with module-level caching to improve performance
"""

import structlog

from app.services.llm_service import LLMService
from app.services.rag_service import get_rag_service  # Use singleton from rag_service.py
from app.services.email_processor import EmailProcessor

logger = structlog.get_logger()

# Module-level cached instances (safer than lru_cache with async/complex objects)
_llm_service = None
_email_processor = None


def get_llm_service() -> LLMService:
    """
    Get cached LLM service instance.

    Thread-safe singleton pattern for LLM service.
    """
    global _llm_service
    if _llm_service is None:
        logger.info("llm_service_created")
        _llm_service = LLMService()
    return _llm_service


# get_rag_service is now imported from app.services.rag_service


def get_email_processor() -> EmailProcessor:
    """
    Get cached EmailProcessor instance.

    Thread-safe singleton pattern for email processor.
    """
    global _email_processor
    if _email_processor is None:
        logger.info("email_processor_created")
        _email_processor = EmailProcessor()
    return _email_processor
