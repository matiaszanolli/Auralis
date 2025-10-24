"""
Auralis Library Caching Layer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In-memory caching for frequently accessed library queries

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
from functools import lru_cache, wraps
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import hashlib
import json

logger = logging.getLogger(__name__)


class QueryCache:
    """
    Simple in-memory cache for library queries.

    Features:
    - LRU eviction policy
    - TTL (time-to-live) support
    - Automatic cache invalidation
    - Query result caching
    """

    def __init__(self, max_size: int = 128, default_ttl: int = 300):
        """
        Initialize query cache.

        Args:
            max_size: Maximum number of cached items (LRU eviction)
            default_ttl: Default time-to-live in seconds (0 = no expiration)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, Tuple[Any, Optional[datetime]]] = {}
        self._hits = 0
        self._misses = 0

    def _make_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """
        Create cache key from function name and arguments.

        Args:
            func_name: Function name
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Cache key string
        """
        # Create a deterministic key from function name and arguments
        key_data = {
            'func': func_name,
            'args': args,
            'kwargs': sorted(kwargs.items())
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if key not in self._cache:
            self._misses += 1
            return None

        value, expiry = self._cache[key]

        # Check if expired
        if expiry and datetime.now() > expiry:
            del self._cache[key]
            self._misses += 1
            return None

        self._hits += 1
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Store value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (None = use default, 0 = no expiration)
        """
        if ttl is None:
            ttl = self.default_ttl

        expiry = None
        if ttl > 0:
            expiry = datetime.now() + timedelta(seconds=ttl)

        # LRU eviction if cache is full
        if len(self._cache) >= self.max_size and key not in self._cache:
            # Remove oldest item (first inserted)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        self._cache[key] = (value, expiry)

    def invalidate(self, pattern: Optional[str] = None):
        """
        Invalidate cache entries.

        Args:
            pattern: Optional pattern to match keys (None = clear all)
        """
        if pattern is None:
            self._cache.clear()
            logger.info("🗑️  Cache cleared")
        else:
            # Remove matching keys
            keys_to_remove = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self._cache[key]
            logger.info(f"🗑️  Invalidated {len(keys_to_remove)} cache entries matching '{pattern}'")

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': f'{hit_rate:.1f}%',
            'total_requests': total_requests
        }


# Global cache instance
_global_cache = QueryCache(max_size=256, default_ttl=300)  # 5-minute TTL


def cached_query(ttl: Optional[int] = None):
    """
    Decorator to cache query results.

    Args:
        ttl: Time-to-live in seconds (None = use default, 0 = no expiration)

    Usage:
        @cached_query(ttl=300)
        def get_recent_tracks(limit=50, offset=0):
            return repository.get_recent(limit, offset)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key
            cache_key = _global_cache._make_key(func.__name__, args, kwargs)

            # Try to get from cache
            cached_result = _global_cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit: {func.__name__}")
                return cached_result

            # Cache miss - execute function
            logger.debug(f"Cache miss: {func.__name__}")
            result = func(*args, **kwargs)

            # Store in cache
            _global_cache.set(cache_key, result, ttl=ttl)

            return result

        return wrapper
    return decorator


def invalidate_cache(pattern: Optional[str] = None):
    """
    Invalidate cached queries.

    Args:
        pattern: Optional pattern to match function names (None = clear all)

    Usage:
        # Clear all cache
        invalidate_cache()

        # Clear specific queries
        invalidate_cache('get_recent')
    """
    _global_cache.invalidate(pattern)


def get_cache_stats() -> dict:
    """
    Get cache statistics.

    Returns:
        Dictionary with cache statistics
    """
    return _global_cache.get_stats()


def clear_cache():
    """Clear all cached queries."""
    _global_cache.invalidate()
