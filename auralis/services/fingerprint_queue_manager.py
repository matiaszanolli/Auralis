"""
Fingerprint Queue Lifecycle Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``FingerprintQueueManager`` — the thin lifecycle facade over
``FingerprintExtractionQueue`` used by the library-scanner integration, split
out of ``fingerprint_queue.py`` (#5039) as a **pure move**.

``fingerprint_queue`` re-exports this name, so the historical import path keeps
resolving.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any
from collections.abc import Callable

from auralis.services.fingerprint_queue import FingerprintExtractionQueue

from ..utils.logging import info, warning


class FingerprintQueueManager:
    """
    Manager for fingerprint extraction queue lifecycle

    Handles initialization, starting, stopping, and integration
    with the library scanner.
    """

    def __init__(self,
                 fingerprint_extractor: Any,
                 library_database: Any,
                 num_workers: int = 4) -> None:
        """Initialize queue manager.

        Args:
            fingerprint_extractor: Extractor used by the worker pool
            library_database: A ``LibraryDatabase`` whose ``repositories``
                factory the workers query through. (Until #4915 this also
                accepted the deprecated ``LibraryManager`` subclass; that
                class no longer exists.)
            num_workers: Worker pool size
        """
        # #4619: was `library_database.repository_factory` — an attribute that
        # exists on neither class, so a real object here raised AttributeError
        # on the first worker tick. Only mocks ever survived it.
        self.queue: FingerprintExtractionQueue = FingerprintExtractionQueue(
            fingerprint_extractor=fingerprint_extractor,
            get_repository_factory=lambda: library_database.repositories,
            num_workers=num_workers
        )
        self.is_running: bool = False

    async def initialize(self) -> None:
        """Initialize and start the queue"""
        if not self.is_running:
            await self.queue.start()
            self.is_running = True
            info("Fingerprint queue manager initialized and started")

    async def shutdown(self, timeout: float = 30.0) -> bool:
        """Shutdown the queue gracefully"""
        if self.is_running:
            success = await self.queue.stop(timeout=timeout)
            self.is_running = False
            if success:
                info("Fingerprint queue manager shut down successfully")
            else:
                warning("Fingerprint queue manager shutdown timed out")
            return success
        return True


    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics"""
        return self.queue.get_stats()

    def set_progress_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Set progress callback"""
        self.queue.set_progress_callback(callback)
