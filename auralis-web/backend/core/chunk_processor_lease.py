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

from typing import Any


class StreamProcessorLeaseMixin:
    """Lease bookkeeping for ``ChunkedAudioProcessor``, which provides the attributes."""

    track_id: int
    preset: str | None
    intensity: float
    processor: Any | None
    processor_config: Any | None
    mastering_targets: dict[str, Any] | None
    _processor_factory: Any

    def hybrid_processor(self) -> Any | None:
        """The HybridProcessor leased to this stream; None when serving original audio.

        Leases a fresh one if the last was discarded after a failure or DSP
        timeout (#5274, #5335), so a retry never runs on an advanced instance.
        """
        if self.preset is None:
            return None
        if self.processor is None:
            self.processor = self._processor_factory.acquire(
                track_id=self.track_id,
                preset=self.preset,
                intensity=self.intensity,
                config=self.processor_config,
                mastering_targets=self.mastering_targets,
            )
        return self.processor

    def _release_processor(self) -> None:
        """Hand the leased HybridProcessor back to the factory. Idempotent."""
        leased, self.processor = self.processor, None
        if leased is not None and self.preset is not None:
            self._processor_factory.release_lease(
                leased,
                track_id=self.track_id,
                preset=self.preset,
                config=self.processor_config,
                mastering_targets=self.mastering_targets,
            )
