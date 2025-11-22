"""
Redis client configuration and initialization
"""

import redis.asyncio as redis
import os
import structlog
from typing import Optional

logger = structlog.get_logger()

_redis_client: Optional[redis.Redis] = None


async def init_redis_client():
    """Initialize Redis client"""
    global _redis_client

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    try:
        _redis_client = redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        # Test connection
        await _redis_client.ping()
        logger.info("redis_connected", url=redis_url)
    except Exception as e:
        logger.warning("redis_connection_failed", error=str(e), url=redis_url)
        _redis_client = None


def get_redis_client() -> Optional[redis.Redis]:
    """Get Redis client instance (lazy init)"""
    global _redis_client

    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            logger.debug("redis_not_configured")
            return None

        try:
            # Synchronous init for get_redis_client (used in service __init__)
            # For async init, use init_redis_client() in app startup
            import redis as sync_redis
            _redis_client = sync_redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info("redis_client_created_sync", url=redis_url)
        except Exception as e:
            logger.warning("redis_client_creation_failed", error=str(e))
            return None

    return _redis_client


async def close_redis_client():
    """Close Redis client"""
    global _redis_client

    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("redis_client_closed")
