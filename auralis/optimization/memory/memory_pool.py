"""
Memory Pool
~~~~~~~~~~~

High-performance memory pool for audio buffer reuse.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import threading
from collections import deque
from typing import Any

import numpy as np

from auralis.utils.logging import debug


class MemoryPool:
    """High-performance memory pool for audio buffers"""

    def __init__(self, pool_size_mb: int = 64) -> None:
        self.pool_size_bytes = pool_size_mb * 1024 * 1024
        # Keyed by (shape, dtype), not shape alone (#4992). Keying on shape
        # only let get_buffer() hand back a buffer of the wrong dtype, which
        # it papered over with `np.asarray(buffer, dtype=dtype)` — a *cast
        # copy*. The caller then held a different object than the id() the
        # pool had recorded in allocated_buffers, so that entry could never be
        # returned: permanent accounting growth, plus an id()-reuse hazard
        # once the orphaned original was garbage collected, since
        # return_buffer keys solely on id().
        self.available_buffers: dict[tuple[tuple[int, ...], np.dtype], deque[np.ndarray]] = {}
        self.allocated_buffers: set[int] = set()
        self.total_allocated = 0
        self.lock = threading.RLock()

        debug(f"Memory pool initialized: {pool_size_mb}MB")

    @staticmethod
    def _key(shape: tuple[int, ...], dtype: Any) -> tuple[tuple[int, ...], np.dtype]:
        """Pool key: shape AND dtype, so a hit never needs a cast (#4992)."""
        return tuple(shape), np.dtype(dtype)

    def get_buffer(self, shape: tuple[int, ...], dtype: Any = np.float32) -> np.ndarray:
        """Get a buffer from the pool or allocate new one"""
        buffer_size = np.prod(shape) * np.dtype(dtype).itemsize
        key = self._key(shape, dtype)

        with self.lock:
            # A pool hit now matches shape *and* dtype exactly, so the buffer
            # is returned as-is — the object the caller gets is the object
            # whose id() is tracked in allocated_buffers.
            pooled = self.available_buffers.get(key)
            if pooled:
                buffer = pooled.popleft()
                self.allocated_buffers.add(id(buffer))
                return buffer

            # Allocate new buffer if we have space
            if self.total_allocated + buffer_size <= self.pool_size_bytes:
                buffer = np.zeros(shape, dtype=dtype)
                self.allocated_buffers.add(id(buffer))
                self.total_allocated += buffer_size
                return buffer

            # Pool is full, return temporary buffer (will be GC'd). Not
            # tracked in allocated_buffers, so return_buffer ignores it.
            return np.zeros(shape, dtype=dtype)

    def return_buffer(self, buffer: np.ndarray) -> None:
        """Return buffer to the pool"""
        buffer_id = id(buffer)

        with self.lock:
            if buffer_id in self.allocated_buffers:
                self.allocated_buffers.remove(buffer_id)

                # Clear buffer and add to available pool under its own
                # (shape, dtype) so it can only be handed out for a matching
                # request (#4992).
                buffer.fill(0)
                key = self._key(buffer.shape, buffer.dtype)

                if key not in self.available_buffers:
                    self.available_buffers[key] = deque(maxlen=10)

                if len(self.available_buffers[key]) < 10:
                    self.available_buffers[key].append(buffer)

    def get_stats(self) -> dict[str, Any]:
        """Get memory pool statistics"""
        with self.lock:
            return {
                'total_allocated_mb': self.total_allocated / (1024 * 1024),
                'pool_size_mb': self.pool_size_bytes / (1024 * 1024),
                'utilization': self.total_allocated / self.pool_size_bytes,
                'active_buffers': len(self.allocated_buffers),
                'available_buffer_types': len(self.available_buffers)
            }
