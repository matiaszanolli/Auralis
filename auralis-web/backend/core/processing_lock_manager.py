#!/usr/bin/env python3

"""
Processing Lock Manager
~~~~~~~~~~~~~~~~~~~~~~~

Handle async/sync processing coordination with locking.

Provides unified interface for:
- Async processing with asyncio.Lock
- Sync processing (direct call, no lock)

This consolidates the processing wrapper patterns in ChunkedAudioProcessor
into a single, consistent approach.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import asyncio
import logging
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ProcessingLockManager:
    """
    Handle async/sync processing coordination with locking.

    The lock prevents concurrent calls to processor.process() from corrupting
    shared processor state (envelope followers, gain reduction tracking, etc.).

    Usage:
        # In ChunkedAudioProcessor.__init__:
        self._lock_manager = ProcessingLockManager()

        # Async processing (e.g., WebSocket streaming):
        async def process_chunk_async(self, chunk_index: int):
            result = await self._lock_manager.process_async(
                lambda: self._process_chunk_impl(chunk_index)
            )
            return result
    """

    def __init__(self) -> None:
        """Initialize processing lock manager."""
        self._lock = asyncio.Lock()
        logger.debug("ProcessingLockManager initialized")

    async def process_async(self, process_fn: Callable[[], T]) -> T:
        """
        Process in async context with lock acquisition.

        This ensures only one chunk is processed at a time, preventing
        concurrent access to shared processor state.

        Args:
            process_fn: Function to execute with lock held (should be sync)

        Returns:
            Result from process_fn

        Examples:
            >>> manager = ProcessingLockManager()
            >>> async def process():
            ...     result = await manager.process_async(lambda: expensive_computation())
            ...     return result
        """
        async with self._lock:
            logger.debug("Acquired processing lock (async)")
            try:
                # Run sync function in thread pool to avoid blocking event loop
                result = await asyncio.to_thread(process_fn)
                logger.debug("Released processing lock (async)")
                return result
            except Exception as e:
                logger.error(f"Processing failed in async context: {e}")
                raise

    def process_sync(self, process_fn: Callable[[], T]) -> T:
        """
        Process synchronously without lock (direct call).

        Use this when:
        - Processing is inherently sequential (e.g., single-threaded export)
        - Caller already holds a lock
        - No concurrency issues possible

        Args:
            process_fn: Function to execute

        Returns:
            Result from process_fn

        Examples:
            >>> manager = ProcessingLockManager()
            >>> result = manager.process_sync(lambda: simple_computation())
        """
        logger.debug("Processing sync (direct call, no lock)")
        try:
            result = process_fn()
            logger.debug("Completed sync processing")
            return result
        except Exception as e:
            logger.error(f"Processing failed in sync context: {e}")
            raise

    def cleanup(self) -> None:
        """
        Clean up resources.

        Call this when the processor is no longer needed.

        Examples:
            >>> manager = ProcessingLockManager()
            >>> # ... use manager ...
            >>> manager.cleanup()
        """
        logger.debug("ProcessingLockManager cleanup complete")
