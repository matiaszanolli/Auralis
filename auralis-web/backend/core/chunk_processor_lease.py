"""
A stream's lease on its HybridProcessor (split from chunked_processor.py, #6091).

Each ``ChunkedAudioProcessor`` is one stream's renderer. It takes its
HybridProcessor from the ProcessorFactory as an exclusive lease at construction,
renders every chunk on that same instance (so EQ envelope and limiter state carry
across the stream's own chunks), and hands it back on ``close()``. A second live
stream of the same track therefore gets a different instance instead of feeding
chunks into this one in interleaved order.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from typing import Any

from .chunk_stream_state import ChunkCancelledError

# Orders hybrid_processor()'s lease against close() across all streams; held only
# for the flag/pointer swap, never across the factory call.
_LEASE_LOCK = threading.Lock()


class StreamProcessorLeaseMixin:
    """Lease bookkeeping for ``ChunkedAudioProcessor``, which provides the attributes."""

    track_id: int
    preset: str | None
    intensity: float
    processor: Any | None
    processor_config: Any | None
    mastering_targets: dict[str, Any] | None
    _processor_factory: Any
    _processor_lock: threading.RLock  # held across a whole chunk render
    _closed: bool = False

    def hybrid_processor(self) -> Any | None:
        """The HybridProcessor leased to this stream; None when serving original audio.

        Leases a fresh one if the last was discarded after a failure or DSP
        timeout (#5274, #5335), so a retry never runs on an advanced instance.
        Raises ChunkCancelledError once ``close()`` ran: a render thread that
        outlived its stream must not lease a processor nothing will return (#6430).
        """
        if self.preset is None:
            return None
        if self._closed:
            raise ChunkCancelledError("processor closed; its stream is gone")
        if self.processor is None:
            leased = self._processor_factory.acquire(
                track_id=self.track_id,
                preset=self.preset,
                intensity=self.intensity,
                config=self.processor_config,
                mastering_targets=self.mastering_targets,
            )
            if not self._adopt_lease(leased):  # close() landed while acquiring: hand it straight back
                self._return_lease(leased)
                raise ChunkCancelledError("processor closed; its stream is gone")
        return self.processor

    def _adopt_lease(self, leased: Any) -> bool:
        """Keep ``leased`` as this stream's processor unless ``close()`` already ran."""
        with _LEASE_LOCK:
            if self._closed:
                return False
            self.processor = leased
            return True

    def _close_lease(self) -> None:
        """Refuse further leases, then hand back the current one (``close()``)."""
        with _LEASE_LOCK:
            self._closed = True
        self._release_processor()

    def _release_processor(self) -> None:
        """Hand the leased HybridProcessor back to the factory. Idempotent.

        Not while a render is still inside it (#6539): a pump exit cannot cancel a look-ahead render
        already in the stream executor, and a lease returned under it let a successor stream of the
        same key acquire an instance that render was still advancing (its limiter and EQ state). The
        render holds _processor_lock for the whole chunk, so a lock this close cannot take means one
        is in flight: that lease is discarded, as after a DSP timeout (#5335). A render starting
        later cannot reach it: ``_closed`` is set first and hybrid_processor() then refuses.
        """
        leased, self.processor = self.processor, None
        if leased is None or self.preset is None:
            return
        lock = getattr(self, "_processor_lock", None)  # absent: __init__ failed before any render could run
        if lock is None:
            self._return_lease(leased)
            return
        if not lock.acquire(blocking=False):
            self._processor_factory.discard_lease(leased, track_id=self.track_id)
            return
        try:
            self._return_lease(leased)
        finally:
            lock.release()

    def _return_lease(self, leased: Any | None) -> None:
        if leased is not None and self.preset is not None:
            self._processor_factory.release_lease(
                leased,
                track_id=self.track_id,
                preset=self.preset,
                config=self.processor_config,
                mastering_targets=self.mastering_targets,
            )
