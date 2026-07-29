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
from typing import Any, Final

import numpy as np

from auralis.utils.logging import debug

#: Returned by :meth:`SmartCache._generate_key` when an argument cannot be
#: identified faithfully, meaning the call MUST NOT be cached (#4524). It is a
#: distinct sentinel rather than ``None`` because ``None`` already means "cache
#: miss" to ``PerformanceOptimizer.cached_function``, and a miss still writes
#: the result back — which is exactly what must not happen here.
UNCACHEABLE: Final[str] = "\x00uncacheable\x00"

# Types whose repr() is a faithful, complete identity.
_FAITHFUL_SCALARS: Final[tuple[type, ...]] = (str, bytes, bool, int, float, type(None))


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

    @staticmethod
    def _identify(value: Any) -> str:
        """Render one argument as a *faithful* identity, or raise (#4524).

        ``repr()`` is never trustworthy for this job. NumPy truncates the repr
        of any array over 1000 elements to the first and last three samples per
        axis, so two tracks that merely share a shape and their lead-in/tail
        digital silence — the norm for mastered audio — render identically and
        collide. Arbitrary objects are just as bad: the default ``repr``
        embeds ``id(self)``, which CPython reuses after garbage collection.

        Arrays are therefore keyed on their actual bytes, and anything whose
        identity cannot be established is refused outright.
        """
        if isinstance(value, np.ndarray):
            digest = hashlib.blake2b(
                np.ascontiguousarray(value).tobytes(), digest_size=16
            ).hexdigest()
            return f"ndarray({value.shape},{value.dtype.str},{digest})"

        # bool is a subclass of int; both are in _FAITHFUL_SCALARS, and repr
        # distinguishes them (`True` vs `1`), so no special-casing is needed.
        if isinstance(value, _FAITHFUL_SCALARS):
            return f"{type(value).__name__}({value!r})"

        if isinstance(value, (tuple, list)):
            inner = ",".join(SmartCache._identify(v) for v in value)
            return f"{type(value).__name__}([{inner}])"

        if isinstance(value, dict):
            inner = ",".join(
                f"{SmartCache._identify(k)}:{SmartCache._identify(v)}"
                for k, v in sorted(value.items(), key=lambda kv: repr(kv[0]))
            )
            return f"dict({{{inner}}})"

        raise TypeError(f"cannot faithfully identify {type(value).__name__}")

    def _generate_key(self, func_name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        """Generate a content-faithful cache key, or :data:`UNCACHEABLE`.

        Returning :data:`UNCACHEABLE` means "this call must bypass the cache
        entirely" — never "miss, then store". A cache that can return the wrong
        audio is strictly worse than no cache, so the failure mode is a bypass,
        never a false hit (#4524).
        """
        try:
            parts = [f"func({func_name!r})"]
            parts.extend(self._identify(a) for a in args)
            parts.extend(
                f"{k}={self._identify(v)}" for k, v in sorted(kwargs.items())
            )
        except TypeError as exc:
            debug(f"SmartCache: bypassing cache for {func_name}: {exc}")
            return UNCACHEABLE

        return hashlib.md5("|".join(parts).encode('utf-8')).hexdigest()

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
