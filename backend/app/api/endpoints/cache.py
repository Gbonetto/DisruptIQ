"""
Cache Management Endpoints
Provides cache statistics and management operations
"""

from fastapi import APIRouter, HTTPException
import structlog

from app.services.cache_service import get_cache_service

router = APIRouter()
logger = structlog.get_logger()


@router.get("/stats")
async def get_cache_stats():
    """
    Get Redis cache statistics

    Returns:
        Cache performance metrics including hits, misses, and hit rate
    """
    try:
        cache_service = get_cache_service()
        stats = await cache_service.get_stats()

        return {
            "success": True,
            **stats
        }

    except Exception as e:
        logger.error("cache_stats_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get cache stats: {str(e)}"
        )


@router.post("/clear")
async def clear_cache(pattern: str = "*"):
    """
    Clear cache keys matching a pattern

    Args:
        pattern: Pattern to match (e.g., 'vendor:*', 'stats:*', '*' for all)

    Returns:
        Number of keys deleted
    """
    try:
        cache_service = get_cache_service()

        if not cache_service.enabled:
            return {
                "success": False,
                "message": "Cache is disabled"
            }

        deleted = await cache_service.clear_pattern(pattern)

        logger.info("cache_cleared", pattern=pattern, deleted=deleted)

        return {
            "success": True,
            "pattern": pattern,
            "keys_deleted": deleted,
            "message": f"Cleared {deleted} cache keys matching '{pattern}'"
        }

    except Exception as e:
        logger.error("cache_clear_failed", pattern=pattern, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear cache: {str(e)}"
        )


@router.post("/invalidate/{entity_type}")
async def invalidate_entity_cache(entity_type: str, entity_id: int = None):
    """
    Invalidate cache for a specific entity type

    Args:
        entity_type: Type of entity ('vendor', 'copropriete', 'document', etc.)
        entity_id: Optional specific entity ID

    Returns:
        Confirmation of invalidation
    """
    try:
        cache_service = get_cache_service()

        if not cache_service.enabled:
            return {
                "success": False,
                "message": "Cache is disabled"
            }

        await cache_service.invalidate_related(entity_type, entity_id)

        return {
            "success": True,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "message": f"Invalidated cache for {entity_type}" + (f" ID {entity_id}" if entity_id else "")
        }

    except Exception as e:
        logger.error("cache_invalidation_failed", entity_type=entity_type, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to invalidate cache: {str(e)}"
        )
