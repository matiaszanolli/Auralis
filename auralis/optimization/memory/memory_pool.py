# -*- coding: utf-8 -*-

"""
Memory Pool
~~~~~~~~~~~

High-performance memory pool for audio buffer reuse.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import threading
from collections import deque
from typing import Dict, Any, Tuple, Set
from auralis.utils.logging import debug


class MemoryPool:
    """High-performance memory pool for audio buffers"""

    def __init__(self, pool_size_mb: int = 64) -> None:
        self.pool_size_bytes = pool_size_mb * 1024 * 1024
        self.available_buffers: Dict[Tuple[int, ...], deque[Any]] = {}  # size -> deque of buffers
        self.allocated_buffers: Set[int] = set()
        self.total_allocated = 0
        self.lock = threading.RLock()

        debug(f"Memory pool initialized: {pool_size_mb}MB")

    def get_buffer(self, shape: Tuple[int, ...], dtype: Any = np.float32) -> np.ndarray:
        """Get a buffer from the pool or allocate new one"""
        buffer_size = np.prod(shape) * np.dtype(dtype).itemsize

        with self.lock:
            # Check if we have a suitable buffer
            if shape in self.available_buffers and self.available_buffers[shape]:
                buffer = self.available_buffers[shape].popleft()
                self.allocated_buffers.add(id(buffer))
                return buffer

            # Allocate new buffer if we have space
            if self.total_allocated + buffer_size <= self.pool_size_bytes:
                buffer = np.zeros(shape, dtype=dtype)
                self.allocated_buffers.add(id(buffer))
                self.total_allocated += buffer_size
                return buffer

            # Pool is full, return temporary buffer (will be GC'd)
            return np.zeros(shape, dtype=dtype)

    def return_buffer(self, buffer: np.ndarray) -> None:
        """Return buffer to the pool"""
        buffer_id = id(buffer)

        with self.lock:
            if buffer_id in self.allocated_buffers:
                self.allocated_buffers.remove(buffer_id)

                # Clear buffer and add to available pool
                buffer.fill(0)
                shape = buffer.shape

                if shape not in self.available_buffers:
                    self.available_buffers[shape] = deque(maxlen=10)

                if len(self.available_buffers[shape]) < 10:
                    self.available_buffers[shape].append(buffer)

    def get_stats(self) -> Dict[str, Any]:
        """Get memory pool statistics"""
        with self.lock:
            return {
                'total_allocated_mb': self.total_allocated / (1024 * 1024),
                'pool_size_mb': self.pool_size_bytes / (1024 * 1024),
                'utilization': self.total_allocated / self.pool_size_bytes,
                'active_buffers': len(self.allocated_buffers),
                'available_buffer_types': len(self.available_buffers)
            }
