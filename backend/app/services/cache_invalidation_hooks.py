"""
Cache Invalidation Hooks Service
Phase 1.3 - World-Class SMA Optimization

Provides intelligent cache invalidation when RAG data changes.

Events that trigger invalidation:
- Document indexed/updated/deleted
- Collection recreated
- Reindex operation
- Entity update (vendors, coproprietes, etc.)

Strategy:
- Tag-based invalidation for fine-grained control
- Pattern-based bulk invalidation for related queries
- Event hooks for automatic cleanup

Author: Claude Code - Phase 1 World-Class SMA
Date: November 27, 2025
"""

import asyncio
import structlog
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps

from app.services.cache_service import get_cache_service, CacheService

logger = structlog.get_logger()


class InvalidationEvent(str, Enum):
    """Cache invalidation event types"""
    DOCUMENT_INDEXED = "document_indexed"
    DOCUMENT_UPDATED = "document_updated"
    DOCUMENT_DELETED = "document_deleted"
    DOCUMENT_CHUNKS_INDEXED = "document_chunks_indexed"
    COLLECTION_RECREATED = "collection_recreated"
    REINDEX_STARTED = "reindex_started"
    REINDEX_COMPLETED = "reindex_completed"
    ENTITY_UPDATED = "entity_updated"
    VENDOR_UPDATED = "vendor_updated"
    COPROPRIETE_UPDATED = "copropriete_updated"
    SEARCH_CONFIG_CHANGED = "search_config_changed"


@dataclass
class InvalidationRule:
    """Defines cache patterns to invalidate for an event"""
    event: InvalidationEvent
    patterns: List[str]
    description: str


# Pre-defined invalidation rules
INVALIDATION_RULES: List[InvalidationRule] = [
    InvalidationRule(
        event=InvalidationEvent.DOCUMENT_INDEXED,
        patterns=[
            "rag:search:*",
            "rag:similar:*",
            "search:document:*",
            "stats:documents:*",
        ],
        description="Invalidate search caches when new document indexed"
    ),
    InvalidationRule(
        event=InvalidationEvent.DOCUMENT_UPDATED,
        patterns=[
            "rag:search:*",
            "rag:similar:*",
            "document:{document_id}:*",
            "search:document:*",
        ],
        description="Invalidate document-specific and search caches"
    ),
    InvalidationRule(
        event=InvalidationEvent.DOCUMENT_DELETED,
        patterns=[
            "rag:search:*",
            "rag:similar:*",
            "document:{document_id}:*",
            "search:document:*",
            "stats:documents:*",
        ],
        description="Full cache cleanup for deleted document"
    ),
    InvalidationRule(
        event=InvalidationEvent.DOCUMENT_CHUNKS_INDEXED,
        patterns=[
            "rag:search:*",
            "rag:similar:*",
            "rag:hybrid:*",
            "search:document:*",
        ],
        description="Invalidate all RAG search caches for chunked indexing"
    ),
    InvalidationRule(
        event=InvalidationEvent.COLLECTION_RECREATED,
        patterns=[
            "rag:*",
            "search:*",
            "stats:*",
        ],
        description="Full RAG cache invalidation for collection recreation"
    ),
    InvalidationRule(
        event=InvalidationEvent.REINDEX_STARTED,
        patterns=[
            "rag:search:*",
            "rag:similar:*",
        ],
        description="Invalidate search during reindex"
    ),
    InvalidationRule(
        event=InvalidationEvent.REINDEX_COMPLETED,
        patterns=[
            "rag:*",
            "search:*",
            "stats:rag:*",
        ],
        description="Full refresh after reindex"
    ),
    InvalidationRule(
        event=InvalidationEvent.VENDOR_UPDATED,
        patterns=[
            "vendor:{entity_id}:*",
            "vendor:list:*",
            "rag:search:*vendor*",
            "stats:vendor*",
            "search:vendor:*",
        ],
        description="Vendor-specific cache invalidation"
    ),
    InvalidationRule(
        event=InvalidationEvent.COPROPRIETE_UPDATED,
        patterns=[
            "copropriete:{entity_id}:*",
            "copropriete:list:*",
            "rag:search:*copro*",
            "stats:copro*",
        ],
        description="Copropriete-specific cache invalidation"
    ),
    InvalidationRule(
        event=InvalidationEvent.SEARCH_CONFIG_CHANGED,
        patterns=[
            "rag:search:*",
            "rag:hybrid:*",
            "rag:similar:*",
        ],
        description="Invalidate all search caches when config changes"
    ),
]


class CacheInvalidationService:
    """
    Service for managing cache invalidation hooks

    Usage:
        invalidation_service = CacheInvalidationService()

        # Emit event after indexing
        await invalidation_service.emit(
            InvalidationEvent.DOCUMENT_INDEXED,
            document_id=123
        )

        # Register custom handler
        @invalidation_service.on(InvalidationEvent.DOCUMENT_DELETED)
        async def custom_handler(event, context):
            # Custom cleanup logic
            pass
    """

    def __init__(self):
        self._cache_service: Optional[CacheService] = None
        self._rules = {rule.event: rule for rule in INVALIDATION_RULES}
        self._handlers: Dict[InvalidationEvent, List[Callable]] = {}
        self._stats = {
            "events_processed": 0,
            "patterns_invalidated": 0,
            "last_event": None,
            "last_event_time": None,
        }

        logger.info("cache_invalidation_service_initialized",
                   rules_count=len(self._rules))

    @property
    def cache_service(self) -> CacheService:
        """Lazy-load cache service"""
        if self._cache_service is None:
            self._cache_service = get_cache_service()
        return self._cache_service

    def on(self, event: InvalidationEvent):
        """
        Decorator to register custom event handler

        Usage:
            @invalidation_service.on(InvalidationEvent.DOCUMENT_INDEXED)
            async def my_handler(event, context):
                print(f"Document {context['document_id']} indexed!")
        """
        def decorator(func: Callable):
            if event not in self._handlers:
                self._handlers[event] = []
            self._handlers[event].append(func)
            logger.debug("invalidation_handler_registered",
                        event=event.value,
                        handler=func.__name__)
            return func
        return decorator

    async def emit(
        self,
        event: InvalidationEvent,
        **context
    ) -> Dict[str, Any]:
        """
        Emit an invalidation event

        Args:
            event: Event type
            **context: Event context (document_id, entity_id, etc.)

        Returns:
            Invalidation result summary
        """
        logger.info("invalidation_event_emitted",
                   event=event.value,
                   context=context)

        result = {
            "event": event.value,
            "patterns_cleared": [],
            "handlers_executed": [],
            "errors": [],
        }

        # Get rule for this event
        rule = self._rules.get(event)

        if rule:
            # Process pattern invalidations
            for pattern in rule.patterns:
                # Interpolate context variables in pattern
                resolved_pattern = pattern.format(**context) if context else pattern

                try:
                    if self.cache_service.enabled:
                        await self.cache_service.clear_pattern(resolved_pattern)
                        result["patterns_cleared"].append(resolved_pattern)
                        logger.debug("cache_pattern_cleared",
                                   pattern=resolved_pattern,
                                   event=event.value)
                except Exception as e:
                    error_msg = f"Failed to clear {resolved_pattern}: {str(e)}"
                    result["errors"].append(error_msg)
                    logger.warning("cache_clear_failed",
                                 pattern=resolved_pattern,
                                 error=str(e))

        # Execute custom handlers
        handlers = self._handlers.get(event, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event, context)
                else:
                    handler(event, context)
                result["handlers_executed"].append(handler.__name__)
            except Exception as e:
                error_msg = f"Handler {handler.__name__} failed: {str(e)}"
                result["errors"].append(error_msg)
                logger.error("invalidation_handler_failed",
                           handler=handler.__name__,
                           error=str(e))

        # Update stats
        self._stats["events_processed"] += 1
        self._stats["patterns_invalidated"] += len(result["patterns_cleared"])
        self._stats["last_event"] = event.value
        self._stats["last_event_time"] = datetime.now().isoformat()

        logger.info("invalidation_event_processed",
                   event=event.value,
                   patterns_cleared=len(result["patterns_cleared"]),
                   handlers_executed=len(result["handlers_executed"]),
                   errors=len(result["errors"]))

        return result

    async def invalidate_document(self, document_id: int, deleted: bool = False):
        """
        Convenience method to invalidate document caches

        Args:
            document_id: Document ID
            deleted: Whether document was deleted
        """
        event = InvalidationEvent.DOCUMENT_DELETED if deleted else InvalidationEvent.DOCUMENT_UPDATED
        await self.emit(event, document_id=document_id)

    async def invalidate_entity(self, entity_type: str, entity_id: int):
        """
        Convenience method to invalidate entity caches

        Args:
            entity_type: Entity type (vendor, copropriete, etc.)
            entity_id: Entity ID
        """
        event_map = {
            "vendor": InvalidationEvent.VENDOR_UPDATED,
            "copropriete": InvalidationEvent.COPROPRIETE_UPDATED,
        }

        event = event_map.get(entity_type, InvalidationEvent.ENTITY_UPDATED)
        await self.emit(event, entity_id=entity_id, entity_type=entity_type)

    async def invalidate_search(self):
        """Invalidate all search-related caches"""
        await self.emit(InvalidationEvent.SEARCH_CONFIG_CHANGED)

    def get_stats(self) -> Dict[str, Any]:
        """Get invalidation statistics"""
        return {
            **self._stats,
            "rules_count": len(self._rules),
            "handlers_count": sum(len(h) for h in self._handlers.values()),
        }


# ================================================================
# DECORATOR FOR AUTOMATIC INVALIDATION
# ================================================================

def invalidates_on_success(event: InvalidationEvent, **static_context):
    """
    Decorator that emits invalidation event after successful function execution

    Usage:
        @invalidates_on_success(InvalidationEvent.DOCUMENT_INDEXED)
        async def index_document(document_id: int, text: str):
            # ... indexing logic ...
            return point_id
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            # Build context from function arguments
            context = {**static_context}

            # Try to extract common parameters
            if 'document_id' in kwargs:
                context['document_id'] = kwargs['document_id']
            elif len(args) > 0 and isinstance(args[0], int):
                context['document_id'] = args[0]

            if 'entity_id' in kwargs:
                context['entity_id'] = kwargs['entity_id']

            # Emit invalidation event
            try:
                service = get_invalidation_service()
                await service.emit(event, **context)
            except Exception as e:
                logger.warning("auto_invalidation_failed",
                             event=event.value,
                             error=str(e))

            return result

        return wrapper
    return decorator


# ================================================================
# SINGLETON INSTANCE
# ================================================================

_invalidation_service: Optional[CacheInvalidationService] = None


def get_invalidation_service() -> CacheInvalidationService:
    """Get or create singleton invalidation service"""
    global _invalidation_service

    if _invalidation_service is None:
        _invalidation_service = CacheInvalidationService()

    return _invalidation_service


# ================================================================
# RAG SERVICE INTEGRATION HOOKS
# ================================================================

async def on_document_indexed(document_id: int, point_id: str):
    """Hook called after document indexed in Qdrant"""
    service = get_invalidation_service()
    await service.emit(
        InvalidationEvent.DOCUMENT_INDEXED,
        document_id=document_id,
        point_id=point_id
    )


async def on_document_chunks_indexed(document_id: int, chunk_count: int):
    """Hook called after document chunks indexed"""
    service = get_invalidation_service()
    await service.emit(
        InvalidationEvent.DOCUMENT_CHUNKS_INDEXED,
        document_id=document_id,
        chunk_count=chunk_count
    )


async def on_document_deleted(document_id: int):
    """Hook called after document deleted from Qdrant"""
    service = get_invalidation_service()
    await service.emit(
        InvalidationEvent.DOCUMENT_DELETED,
        document_id=document_id
    )


async def on_collection_recreated():
    """Hook called after Qdrant collection recreated"""
    service = get_invalidation_service()
    await service.emit(InvalidationEvent.COLLECTION_RECREATED)


async def on_reindex_started():
    """Hook called when reindex operation starts"""
    service = get_invalidation_service()
    await service.emit(InvalidationEvent.REINDEX_STARTED)


async def on_reindex_completed():
    """Hook called when reindex operation completes"""
    service = get_invalidation_service()
    await service.emit(InvalidationEvent.REINDEX_COMPLETED)
