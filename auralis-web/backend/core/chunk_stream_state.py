"""
Per-chunk cancellation and invalidation helpers (split from
chunk_streaming.py, #5833). Each takes the owning ``ChunkedAudioProcessor``
as its first argument, like the entry points that call them.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.chunked_processor import ChunkedAudioProcessor

logger = logging.getLogger("core.chunked_processor")


class ChunkCancelledError(Exception):
    """Raised when a chunk's owning stream was cancelled before/during DSP
    (#4815). Distinguishes a deliberately-abandoned chunk from a genuine
    processing failure — callers must not log/retry it as one. In practice
    the coroutine that would have awaited this chunk has almost always
    already unwound via CancelledError by the time this is raised (asyncio
    cancellation doesn't wait for the underlying executor thread), so this
    exists mainly to cut the wasted DSP work short rather than to be
    observed by a live caller."""


def fast_start_for(chunk_index: int) -> bool:
    """Whether ``chunk_index`` is rendered with ``fast_start`` (skips the fingerprint
    analysis, which would block the first chunk). The durable chunk cache key carries
    no renderer identity, so every writer -- live stream, proactive buffer, batch
    render -- must apply this one rule or the stored bytes depend on who won (#6090)."""
    return chunk_index == 0


def _raise_if_cancelled(processor: "ChunkedAudioProcessor", chunk_index: int) -> None:
    """Abandon a chunk whose owning stream was cancelled (#4815, #5328).

    ``task.cancel()`` on the streaming coroutine cannot stop DSP already
    running in an executor thread, so the chunk-rendering functions poll the
    per-stream cancel event themselves: once before DSP, to skip the work, and
    again right before the durable write, so a render the stream abandoned
    mid-DSP is never persisted.
    """
    cancel_event = getattr(processor, "_cancel_event", None)
    if cancel_event is not None and cancel_event.is_set():
        raise ChunkCancelledError(
            f"Chunk {chunk_index} abandoned: owning stream was cancelled"
        )


def _invalidate_after_post_dsp_failure(
    processor: "ChunkedAudioProcessor", chunk_index: int
) -> None:
    """Ensure a retry cannot reuse a stateful processor advanced by this chunk."""
    if not getattr(processor, "_dsp_state_advanced", False):
        return
    processor._dsp_state_advanced = False
    invalidate_pooled_processor(processor, chunk_index, "failed after DSP state advanced")


def invalidate_pooled_processor(
    processor: "ChunkedAudioProcessor", chunk_index: int, reason: str
) -> None:
    """Discard the pooled HybridProcessor this chunk rendered on.

    The stream leases its HybridProcessor (#6091), so an instance left in an
    unknown state is discarded rather than returned to the cache, and the next
    chunk leases a fresh one. Used after a post-DSP failure (#5274) and after a
    chunk DSP timeout (#5335), where the abandoned executor thread may still
    be advancing the instance.
    """
    leased = processor.processor
    processor.processor = None
    if leased is None:
        return
    processor._processor_factory.discard_lease(leased, track_id=processor.track_id)
    logger.error(
        "Chunk %s %s; invalidated the cached processor so a retry starts fresh",
        chunk_index,
        reason,
    )
