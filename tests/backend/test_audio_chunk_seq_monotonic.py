"""
Regression tests for stream-wide monotonic `audio_chunk_meta.seq` (#3841).

`seq` used to be a local in `_send_pcm_chunk`, so it reset to 0 at every chunk
boundary (~every 10s) instead of being monotonic across the whole stream as the
backend docstring and the frontend `AudioChunkMetaMessage` JSDoc both promise.

The fix moves the counter into a per-stream ContextVar cell (`_frame_seq_var`),
reset at every `_send_stream_start`. These tests assert:
  - seq is contiguous 0..N-1 across multiple chunks of one stream,
  - seq restarts at 0 when a new stream starts,
  - seq increments by exactly 1 per frame,
  - concurrent streams in separate tasks keep independent counters.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))

from core.audio_stream_controller import AudioStreamController, _frame_seq_var, _stream_type_var

# 76800 float32 samples == one ~300 KB frame; 100k mono samples -> 2 frames/chunk.
SAMPLES_PER_CHUNK = 100_000


def _make_controller_capturing(captures):
    """Build a controller whose _safe_send records audio_chunk_meta seq values.

    `captures` is a dict keyed by stream_type so concurrent streams can be
    routed apart; for single-stream tests pass a list-backed shim instead.
    """
    controller = AudioStreamController()

    async def fake_safe_send(_ws, message):
        if message.get("type") == "audio_chunk_meta":
            data = message["data"]
            captures.record(data["stream_type"], data["seq"], data["frame_index"])
        return True

    controller._safe_send = fake_safe_send  # type: ignore[assignment]
    controller._safe_send_bytes = AsyncMock(return_value=True)  # type: ignore[assignment]
    return controller


class _Captures:
    """Collects (seq, frame_index) per stream_type key."""

    def __init__(self):
        self.seq = {}
        self.frame_index = {}

    def record(self, key, seq, frame_index):
        self.seq.setdefault(key, []).append(seq)
        self.frame_index.setdefault(key, []).append(frame_index)


async def _start_stream(controller):
    """Drive _send_stream_start with throwaway metadata to seed the seq cell."""
    await controller._send_stream_start(
        AsyncMock(),
        track_id=1,
        preset="adaptive",
        intensity=1.0,
        sample_rate=44100,
        channels=1,
        total_chunks=2,
        chunk_duration=10.0,
        total_duration=20.0,
    )


async def _send_chunk(controller, chunk_index, total_chunks=2):
    samples = np.zeros(SAMPLES_PER_CHUNK, dtype=np.float32)
    await controller._send_pcm_chunk(
        AsyncMock(),
        pcm_samples=samples,
        chunk_index=chunk_index,
        total_chunks=total_chunks,
        crossfade_samples=0,
    )


@pytest.mark.asyncio
async def test_seq_is_monotonic_across_chunk_boundaries():
    """seq must keep counting up across chunks, not reset at each boundary."""
    _frame_seq_var.set(None)  # simulate a fresh task context
    caps = _Captures()
    controller = _make_controller_capturing(caps)

    await _start_stream(controller)
    await _send_chunk(controller, chunk_index=0)
    await _send_chunk(controller, chunk_index=1)

    seqs = caps.seq[None]  # stream_type defaults to None when _stream_type_var unset
    assert len(seqs) >= 4, f"expected >=2 frames/chunk over 2 chunks, got {seqs}"
    # The defining property: contiguous, strictly +1, never resets to 0 mid-stream.
    assert seqs == list(range(len(seqs))), f"seq not stream-monotonic: {seqs}"


@pytest.mark.asyncio
async def test_seq_increments_by_exactly_one_per_frame():
    _frame_seq_var.set(None)
    caps = _Captures()
    controller = _make_controller_capturing(caps)

    await _start_stream(controller)
    await _send_chunk(controller, chunk_index=0)

    seqs = caps.seq[None]
    diffs = [b - a for a, b in zip(seqs, seqs[1:])]
    assert all(d == 1 for d in diffs), f"seq must step by 1 per frame: {seqs}"


@pytest.mark.asyncio
async def test_seq_resets_at_new_stream_start():
    """A new audio_stream_start (new track / seek / resume) restarts seq at 0."""
    _frame_seq_var.set(None)
    caps = _Captures()
    controller = _make_controller_capturing(caps)

    await _start_stream(controller)
    await _send_chunk(controller, chunk_index=0)
    first = list(caps.seq[None])
    assert first[0] == 0 and first[-1] > 0

    # Second stream: counter must reset.
    await _start_stream(controller)
    await _send_chunk(controller, chunk_index=0)
    second = caps.seq[None][len(first):]
    assert second[0] == 0, f"seq did not reset at new stream start: {second}"
    assert second == list(range(len(second)))


@pytest.mark.asyncio
async def test_concurrent_streams_keep_independent_counters():
    """A shared controller serving two concurrent streams (in separate tasks)
    must not interleave their seq counters — the reason the counter lives in a
    per-task ContextVar rather than a shared instance attribute (the #2493 bug).
    """
    caps = _Captures()
    controller = _make_controller_capturing(caps)

    async def run_stream(stream_type):
        # Per-task: _stream_type_var also tags each frame so captures route apart.
        _stream_type_var.set(stream_type)
        _frame_seq_var.set(None)
        await _start_stream(controller)
        await _send_chunk(controller, chunk_index=0)
        # Yield so the two streams genuinely interleave at the event loop.
        await asyncio.sleep(0)
        await _send_chunk(controller, chunk_index=1)

    await asyncio.gather(
        asyncio.create_task(run_stream("enhanced"), name="A"),
        asyncio.create_task(run_stream("normal"), name="B"),
    )

    enhanced = caps.seq["enhanced"]
    normal = caps.seq["normal"]
    assert enhanced == list(range(len(enhanced))), f"enhanced not isolated: {enhanced}"
    assert normal == list(range(len(normal))), f"normal not isolated: {normal}"
    assert len(enhanced) > 0 and len(normal) > 0
