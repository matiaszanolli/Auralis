#!/usr/bin/env python3

"""
Processing Lock Manager
~~~~~~~~~~~~~~~~~~~~~~~

Handle async/sync processing coordination with thread-safe locking.

Provides unified interface for:
- Async processing with asyncio.Lock
- Sync processing in async context (ThreadPoolExecutor)
- Sync processing in sync context (direct call)

This consolidates the 3 different processing wrapper patterns in ChunkedAudioProcessor
into a single, consistent approach.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import asyncio
import concurrent.futures
import logging
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ProcessingLockManager:
    """
    Handle async/sync processing coordination with thread-safe locking.

    This service consolidates three processing wrapper patterns:
    - process_chunk() → Direct sync call
    - process_chunk_safe() → Async with lock
    - process_chunk_synchronized() → Sync in async context

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

        # Sync processing in async context (e.g., full audio export):
        def process_chunk_sync(self, chunk_index: int):
            result = self._lock_manager.process_sync_in_async_context(
                lambda: self._process_chunk_impl(chunk_index)
            )
            return result
    """

    def __init__(self) -> None:
        """Initialize processing lock manager."""
        self._lock = asyncio.Lock()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
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

    def process_sync_in_async_context(self, process_fn: Callable[[], T]) -> T:
        """
        Process synchronously within an async context.

        This is for synchronous callers that need to wait for processing to complete
        (e.g., get_full_processed_audio_path) but may be called from an async context.

        The method handles two cases:
        1. Called from async context: Creates new event loop in thread
        2. Called from sync context: Creates new event loop

        Args:
            process_fn: Function to execute with lock held

        Returns:
            Result from process_fn

        Examples:
            >>> manager = ProcessingLockManager()
            >>> def export_full_audio():
            ...     result = manager.process_sync_in_async_context(
            ...         lambda: process_all_chunks()
            ...     )
            ...     return result
        """
        try:
            # Check if we're in an async context
            loop = asyncio.get_running_loop()

            # We're in an async context - run in thread to avoid blocking
            logger.debug("Processing sync in async context (via thread pool)")
            future = self._executor.submit(
                lambda: asyncio.run(self.process_async(process_fn))
            )
            result = future.result()
            logger.debug("Completed sync processing in async context")
            return result

        except RuntimeError:
            # No event loop running - create one
            logger.debug("Processing sync in sync context (new event loop)")
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(self.process_async(process_fn))
                logger.debug("Completed sync processing in sync context")
                return result
            finally:
                loop.close()

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
        Clean up resources (shutdown executor).

        Call this when the processor is no longer needed.

        Examples:
            >>> manager = ProcessingLockManager()
            >>> # ... use manager ...
            >>> manager.cleanup()
        """
        logger.debug("Shutting down ProcessingLockManager executor")
        self._executor.shutdown(wait=True)
        logger.debug("ProcessingLockManager cleanup complete")

    def __del__(self) -> None:
        """Ensure executor is cleaned up on deletion."""
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass  # Silently ignore cleanup errors during deletion
