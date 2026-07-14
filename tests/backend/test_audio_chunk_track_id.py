"""
Regression tests for track_id on audio_chunk_meta (#4434).

Chunk metadata previously carried no track_id, so on a rapid skip the frontend
could not tell a late chunk-progress update belonged to a superseded track. The
backend now seeds a per-stream `_track_id_var` at every _send_stream_start and
stamps it onto each audio_chunk_meta. These tests assert the stamped track_id
matches the active stream and stays isolated across concurrent streams.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))

from core.audio_stream_controller import (  # noqa: E402
    AudioStreamController,
    _frame_seq_var,
    _stream_type_var,
    _track_id_var,
)

SAMPLES_PER_CHUNK = 100_000


def _make_controller_capturing(records):
    controller = AudioStreamController()

    async def fake_safe_send(_ws, message):
        if message.get("type") == "audio_chunk_meta":
            data = message["data"]
            records.append((data.get("stream_type"), data.get("track_id")))
        return True

    controller._safe_send = fake_safe_send  # type: ignore[assignment]
    controller._safe_send_bytes = AsyncMock(return_value=True)  # type: ignore[assignment]
    return controller


async def _start_stream(controller, track_id):
    await controller._send_stream_start(
        AsyncMock(),
        track_id=track_id,
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
async def test_chunk_meta_carries_active_track_id():
    _frame_seq_var.set(None)
    _track_id_var.set(None)
    records: list = []
    controller = _make_controller_capturing(records)

    await _start_stream(controller, track_id=42)
    await _send_chunk(controller, chunk_index=0)

    assert records, "no audio_chunk_meta captured"
    assert all(track_id == 42 for (_st, track_id) in records), records


@pytest.mark.asyncio
async def test_new_stream_start_reseeds_track_id():
    _frame_seq_var.set(None)
    _track_id_var.set(None)
    records: list = []
    controller = _make_controller_capturing(records)

    await _start_stream(controller, track_id=1)
    await _send_chunk(controller, chunk_index=0)
    first_count = len(records)
    assert first_count > 0
    assert all(track_id == 1 for (_st, track_id) in records)

    # A skip to a new track re-seeds the per-stream track id.
    await _start_stream(controller, track_id=99)
    await _send_chunk(controller, chunk_index=0)
    second = records[first_count:]
    assert second, "no chunks for the second stream"
    assert all(track_id == 99 for (_st, track_id) in second), second


@pytest.mark.asyncio
async def test_concurrent_streams_keep_independent_track_ids():
    records: list = []
    controller = _make_controller_capturing(records)

    async def run_stream(stream_type, track_id):
        _stream_type_var.set(stream_type)
        _frame_seq_var.set(None)
        _track_id_var.set(None)
        await _start_stream(controller, track_id=track_id)
        await _send_chunk(controller, chunk_index=0)
        await asyncio.sleep(0)
        await _send_chunk(controller, chunk_index=1)

    await asyncio.gather(
        asyncio.create_task(run_stream("enhanced", 7), name="A"),
        asyncio.create_task(run_stream("normal", 13), name="B"),
    )

    enhanced_ids = [tid for (st, tid) in records if st == "enhanced"]
    normal_ids = [tid for (st, tid) in records if st == "normal"]
    assert enhanced_ids and all(tid == 7 for tid in enhanced_ids), enhanced_ids
    assert normal_ids and all(tid == 13 for tid in normal_ids), normal_ids
