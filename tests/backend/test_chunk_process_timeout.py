"""
Regression tests for per-chunk DSP timeout (#3852)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A hung DSP call (pathological buffer / Rust DSP deadlock) must not wedge the
per-stream coroutine forever. `_process_chunk_only` now bounds
`process_chunk_safe` with `asyncio.wait_for(..., CHUNK_PROCESS_TIMEOUT)`; on
timeout it raises TimeoutError, which flows into the caller's
skip-failed-chunk recovery branch rather than blocking the stream and holding
the semaphore slot.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

import core.audio_stream_controller as asc
from core.audio_stream_controller import AudioStreamController


def _make_controller() -> AudioStreamController:
    return AudioStreamController()


def _make_processor() -> Mock:
    processor = Mock()
    processor.track_id = 1
    processor.total_chunks = 5
    processor.sample_rate = 44100
    processor.channels = 2
    processor.preset = "adaptive"
    processor.intensity = 1.0
    return processor


def _connected_ws() -> Mock:
    ws = Mock()
    ws.client_state = Mock()
    ws.client_state.name = "CONNECTED"
    return ws


class TestChunkProcessTimeout:
    """_process_chunk_only bounds the per-chunk DSP call."""

    @pytest.mark.asyncio
    async def test_hung_chunk_raises_timeout(self, monkeypatch):
        """A process_chunk_safe that never returns must raise TimeoutError."""
        monkeypatch.setattr(asc, "CHUNK_PROCESS_TIMEOUT", 0.05)

        controller = _make_controller()
        processor = _make_processor()

        async def _hang(*_a, **_k):
            await asyncio.sleep(10)  # longer than the patched timeout

        processor.process_chunk_safe = AsyncMock(side_effect=_hang)

        with pytest.raises(TimeoutError) as exc_info:
            await controller._process_chunk_only(0, processor, _connected_ws())

        assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_fast_chunk_succeeds_within_timeout(self, monkeypatch):
        """A chunk that completes in time returns normally (no false timeout)."""
        monkeypatch.setattr(asc, "CHUNK_PROCESS_TIMEOUT", 5.0)

        controller = _make_controller()
        processor = _make_processor()

        pcm = np.zeros((44100, 2), dtype=np.float32)
        processor.process_chunk_safe = AsyncMock(return_value=(Path("/tmp/c.wav"), pcm))

        samples, sr = await controller._process_chunk_only(0, processor, _connected_ws())

        assert sr == 44100
        assert len(samples) == 44100

    @pytest.mark.asyncio
    async def test_timeout_is_exception_subclass_for_recovery(self, monkeypatch):
        """The raised TimeoutError is catchable as Exception (recovery branch)."""
        monkeypatch.setattr(asc, "CHUNK_PROCESS_TIMEOUT", 0.05)

        controller = _make_controller()
        processor = _make_processor()

        async def _hang(*_a, **_k):
            await asyncio.sleep(10)

        processor.process_chunk_safe = AsyncMock(side_effect=_hang)

        caught_as_exception = False
        try:
            await controller._process_chunk_only(0, processor, _connected_ws())
        except Exception:  # noqa: BLE001 — mirrors the recovery branch
            caught_as_exception = True

        assert caught_as_exception, "TimeoutError must be catchable by except Exception"
