"""
Redis caching service for DMARC data

Caching strategy:
- Aggregation queries: 5 minute TTL
- Domain lists: 10 minute TTL
- Timeline data: 5 minute TTL
- Report details: 30 minute TTL
"""
import redis
import json
import logging
import os
from typing import Optional, Any
from functools import wraps

logger = logging.getLogger(__name__)


class CacheService:
    """Redis caching service with graceful degradation"""

    def __init__(self):
        redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')

        try:
            self.client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            self.client.ping()
            self.enabled = True
            logger.info(f"Redis cache connected: {redis_url}")
        except Exception as e:
            logger.warning(f"Redis unavailable, caching disabled: {e}")
            self.client = None
            self.enabled = False

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.enabled:
            return None
        try:
            value = self.client.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL in seconds"""
        if not self.enabled:
            return False
        try:
            return self.client.setex(key, ttl, json.dumps(value, default=str))
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.enabled:
            return False
        try:
            return self.client.delete(key) > 0
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False

    def invalidate_pattern(self, pattern: str):
        """Invalidate all keys matching pattern"""
        if not self.enabled:
            return
        try:
            for key in self.client.scan_iter(match=pattern):
                self.client.delete(key)
            logger.info(f"Invalidated cache pattern: {pattern}")
        except Exception as e:
            logger.error(f"Cache invalidate pattern error for {pattern}: {e}")


# Global cache instance
_cache_instance = None


def get_cache() -> CacheService:
    """Get or create global cache instance"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheService()
    return _cache_instance


def cache_key(*args, **kwargs) -> str:
    """Generate cache key from arguments"""
    parts = [str(arg) for arg in args]
    parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items()) if v is not None])
    return ":".join(parts)


def cached(prefix: str, ttl: int = 300):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache()
            if not cache.enabled:
                return await func(*args, **kwargs)

            # Generate cache key from function name and args
            key = cache_key(prefix, func.__name__, *args, **kwargs)

            # Try to get from cache
            cached_value = cache.get(key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {key}")
                return cached_value

            # Execute function and cache result
            result = await func(*args, **kwargs)
            cache.set(key, result, ttl)
            logger.debug(f"Cache miss, stored: {key}")
            return result
        return wrapper
    return decorator
