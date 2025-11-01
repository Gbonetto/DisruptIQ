"""
Redis Cache Service
Provides caching functionality with automatic TTL management and invalidation
"""

import json
import hashlib
from typing import Any, Optional, Callable, List
from functools import wraps
import redis.asyncio as redis
import structlog
from app.core.config import settings

logger = structlog.get_logger()


class CacheService:
    """
    Redis-based caching service with automatic key generation and TTL management
    """

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.enabled = settings.redis_enabled

        # Default TTLs (in seconds)
        self.TTL_SHORT = 300  # 5 minutes
        self.TTL_MEDIUM = 1800  # 30 minutes
        self.TTL_LONG = 3600  # 1 hour
        self.TTL_VERY_LONG = 86400  # 24 hours

    async def initialize(self):
        """Initialize Redis connection"""
        if not self.enabled:
            logger.info("cache_disabled", message="Redis caching is disabled")
            return

        try:
            self.redis_client = await redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30
            )

            # Test connection
            await self.redis_client.ping()
            logger.info("cache_initialized", message="Redis cache connected successfully")

        except Exception as e:
            logger.error("cache_init_failed", error=str(e))
            self.enabled = False
            self.redis_client = None

    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("cache_closed")

    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Generate a cache key from prefix and parameters

        Args:
            prefix: Key prefix (e.g., 'vendor', 'stats')
            *args: Positional arguments to include in key
            **kwargs: Keyword arguments to include in key

        Returns:
            Generated cache key
        """
        # Create a deterministic string from args and kwargs
        key_parts = [str(arg) for arg in args]
        key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])

        # Hash long keys to avoid Redis key size limits
        if len(key_parts) > 0:
            params_str = ":".join(key_parts)
            if len(params_str) > 100:
                params_hash = hashlib.md5(params_str.encode()).hexdigest()[:12]
                return f"{prefix}:{params_hash}"
            return f"{prefix}:{params_str}"

        return prefix

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if not self.enabled or not self.redis_client:
            return None

        try:
            value = await self.redis_client.get(key)
            if value:
                logger.debug("cache_hit", key=key)
                return json.loads(value)

            logger.debug("cache_miss", key=key)
            return None

        except Exception as e:
            logger.error("cache_get_failed", key=key, error=str(e))
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds (None = default TTL_MEDIUM)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.redis_client:
            return False

        try:
            ttl = ttl or self.TTL_MEDIUM
            serialized = json.dumps(value, default=str)

            await self.redis_client.setex(key, ttl, serialized)
            logger.debug("cache_set", key=key, ttl=ttl)
            return True

        except Exception as e:
            logger.error("cache_set_failed", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache

        Args:
            key: Cache key or pattern (supports wildcards with *)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.redis_client:
            return False

        try:
            # If key contains wildcard, delete all matching keys
            if "*" in key:
                cursor = 0
                deleted = 0
                while True:
                    cursor, keys = await self.redis_client.scan(
                        cursor, match=key, count=100
                    )
                    if keys:
                        deleted += await self.redis_client.delete(*keys)
                    if cursor == 0:
                        break

                logger.info("cache_pattern_deleted", pattern=key, count=deleted)
                return deleted > 0
            else:
                # Single key deletion
                result = await self.redis_client.delete(key)
                logger.debug("cache_deleted", key=key, found=result > 0)
                return result > 0

        except Exception as e:
            logger.error("cache_delete_failed", key=key, error=str(e))
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """
        Clear all keys matching a pattern

        Args:
            pattern: Pattern to match (e.g., 'vendor:*', 'stats:*')

        Returns:
            Number of keys deleted
        """
        return await self.delete(pattern)

    async def invalidate_related(self, entity_type: str, entity_id: Optional[int] = None):
        """
        Invalidate cache for an entity and its related queries

        Args:
            entity_type: Type of entity ('vendor', 'copropriete', 'document', etc.)
            entity_id: Optional specific entity ID
        """
        patterns = []

        if entity_id:
            # Invalidate specific entity
            patterns.append(f"{entity_type}:{entity_id}")
            patterns.append(f"{entity_type}:{entity_id}:*")

        # Invalidate list queries for this entity type
        patterns.append(f"{entity_type}:list:*")
        patterns.append(f"stats:{entity_type}*")
        patterns.append(f"search:{entity_type}*")

        for pattern in patterns:
            await self.clear_pattern(pattern)

        logger.info(
            "cache_invalidated",
            entity_type=entity_type,
            entity_id=entity_id
        )

    async def get_stats(self) -> dict:
        """Get cache statistics"""
        if not self.enabled or not self.redis_client:
            return {"enabled": False}

        try:
            info = await self.redis_client.info()
            return {
                "enabled": True,
                "connected": True,
                "keys": info.get("db0", {}).get("keys", 0),
                "memory_used": info.get("used_memory_human", "N/A"),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                )
            }
        except Exception as e:
            logger.error("cache_stats_failed", error=str(e))
            return {"enabled": True, "connected": False, "error": str(e)}

    def _calculate_hit_rate(self, hits: int, misses: int) -> str:
        """Calculate cache hit rate percentage"""
        total = hits + misses
        if total == 0:
            return "0%"
        return f"{(hits / total * 100):.2f}%"


# Singleton instance
_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """Get or create cache service singleton"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


# Decorator for caching function results
def cached(
    prefix: str,
    ttl: Optional[int] = None,
    key_builder: Optional[Callable] = None
):
    """
    Decorator to cache function results

    Args:
        prefix: Cache key prefix
        ttl: Time to live in seconds
        key_builder: Optional custom key builder function

    Example:
        @cached(prefix="vendor", ttl=300)
        async def get_vendor(vendor_id: int):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache_service()

            if not cache.enabled:
                return await func(*args, **kwargs)

            # Generate cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = cache._generate_key(prefix, *args, **kwargs)

            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function and cache result
            result = await func(*args, **kwargs)
            if result is not None:
                await cache.set(cache_key, result, ttl)

            return result

        return wrapper
    return decorator


# Decorator for cache invalidation
def invalidates_cache(*patterns: str):
    """
    Decorator to invalidate cache after function execution

    Args:
        *patterns: Cache patterns to invalidate

    Example:
        @invalidates_cache("vendor:*", "stats:vendors")
        async def update_vendor(vendor_id: int):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            cache = get_cache_service()
            if cache.enabled:
                for pattern in patterns:
                    await cache.clear_pattern(pattern)

            return result

        return wrapper
    return decorator
