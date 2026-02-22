"""
Smart Cache
~~~~~~~~~~~

Intelligent caching system with LRU eviction and TTL expiration.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import hashlib
import sys
import threading
import time
from collections import OrderedDict
from typing import Any

from auralis.utils.logging import debug


class SmartCache:
    """Intelligent caching system with LRU and TTL"""

    def __init__(self, max_size_mb: int = 128, ttl_seconds: int = 300) -> None:
        self.max_size_bytes: int = max_size_mb * 1024 * 1024
        self.ttl_seconds: int = ttl_seconds
        self.cache: OrderedDict[str, Any] = OrderedDict()
        self.access_times: dict[str, float] = {}
        self.sizes: dict[str, int] = {}
        self.current_size: int = 0
        self.lock: threading.RLock = threading.RLock()

        # Statistics
        self.hits: int = 0
        self.misses: int = 0

        debug(f"Smart cache initialized: {max_size_mb}MB, TTL: {ttl_seconds}s")

    def _generate_key(self, func_name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        """Generate cache key from function arguments"""
        # Create a stable hash from arguments
        key_data = (func_name, args, sorted(kwargs.items()))
        key_str = str(key_data).encode('utf-8')
        return hashlib.md5(key_str).hexdigest()

    def get(self, key: str) -> Any | None:
        """Get item from cache"""
        with self.lock:
            current_time = time.time()

            if key in self.cache:
                # Check TTL
                if current_time - self.access_times[key] <= self.ttl_seconds:
                    # Move to end (most recently used)
                    self.cache.move_to_end(key)
                    self.access_times[key] = current_time
                    self.hits += 1
                    return self.cache[key]
                else:
                    # Expired
                    self._remove_item(key)

            self.misses += 1
            return None

    def put(self, key: str, value: Any) -> None:
        """Put item in cache"""
        with self.lock:
            # Estimate size — prefer .nbytes for NumPy arrays (most common
            # cache content), fall back to sys.getsizeof for other types.
            try:
                size = int(value.nbytes) if hasattr(value, 'nbytes') else sys.getsizeof(value)
            except Exception:
                size = 1024  # Default estimate

            current_time = time.time()

            # Remove if already exists
            if key in self.cache:
                self._remove_item(key)

            # Make space if needed
            while self.current_size + size > self.max_size_bytes and self.cache:
                self._remove_oldest()

            # Add new item
            if size <= self.max_size_bytes:  # Only cache if it fits
                self.cache[key] = value
                self.access_times[key] = current_time
                self.sizes[key] = size
                self.current_size += size

    def _remove_item(self, key: str) -> None:
        """Remove item from cache"""
        if key in self.cache:
            del self.cache[key]
            del self.access_times[key]
            self.current_size -= self.sizes[key]
            del self.sizes[key]

    def _remove_oldest(self) -> None:
        """Remove least recently used item"""
        if self.cache:
            oldest_key = next(iter(self.cache))
            self._remove_item(oldest_key)

    def clear_expired(self) -> None:
        """Remove expired items"""
        with self.lock:
            current_time = time.time()
            expired_keys = [
                key for key, access_time in self.access_times.items()
                if current_time - access_time > self.ttl_seconds
            ]

            for key in expired_keys:
                self._remove_item(key)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            total_requests = self.hits + self.misses
            hit_rate = self.hits / total_requests if total_requests > 0 else 0

            return {
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': hit_rate,
                'size_mb': self.current_size / (1024 * 1024),
                'max_size_mb': self.max_size_bytes / (1024 * 1024),
                'utilization': self.current_size / self.max_size_bytes,
                'items': len(self.cache)
            }
