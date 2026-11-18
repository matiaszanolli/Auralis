"""
Regression tests: every ChunkedAudioProcessor lease is returned (#6430).

Since #6091 a processor with a preset takes an exclusive HybridProcessor lease in
``__init__`` and only ``close()`` returns it. Three paths built one and never
closed it: the recommendation analysis, a stream init that timed out or was
cancelled (the worker thread outlives the await), and a render thread that
leased after its stream's ``close()``.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import sys
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

import core.audio_stream_controller as asc
import core.chunked_processor as cp
from core.audio_stream_controller import AudioStreamController
from core.chunk_stream_state import ChunkCancelledError
from core.processor_factory import ProcessorFactory
from core.processor_init_handoff import ProcessorInitHandoff
from services.recommendation_analysis import cached_or_analyzed_recommendation

SR = 44100


@pytest.fixture
def wav(tmp_path):
    path = tmp_path / "tiny.wav"
    sf.write(str(path), np.zeros((SR // 10, 2), dtype=np.float32), SR, subtype="FLOAT")
    return str(path)


@pytest.fixture
def factory():
    """A real factory whose HybridProcessor construction is stubbed (200-500 ms each)."""
    built: list[MagicMock] = []

    def _build(*_a, **_k):
        processor = MagicMock(name=f"hybrid-{len(built)}")
        built.append(processor)
        return processor

    with patch("auralis.core.hybrid_processor.HybridProcessor", side_effect=_build):
        factory = ProcessorFactory()
        factory.built = built  # type: ignore[attr-defined]
        with patch.object(cp, "get_processor_factory", return_value=factory):
            yield factory


def _stream(wav: str, factory: ProcessorFactory, **kwargs) -> "cp.ChunkedAudioProcessor":
    return cp.ChunkedAudioProcessor(
        track_id=1, filepath=wav, preset="adaptive", processor_factory=factory, **kwargs
    )


# --- recommendation analysis ---------------------------------------------------


def _cache_manager() -> MagicMock:
    cache = MagicMock()
    cache.get_mastering_recommendation.return_value = None
    return cache


@pytest.mark.asyncio
@pytest.mark.parametrize("track_id", [101, 102, 103])
async def test_recommendation_analysis_returns_its_lease(wav, factory, track_id):
    rec = MagicMock()
    rec.to_response.return_value = {"track_id": track_id}
    with patch.object(cp.ChunkedAudioProcessor, "get_mastering_recommendation", return_value=rec):
        result = await cached_or_analyzed_recommendation(_cache_manager(), track_id, wav, 0.4)

    assert result == {"track_id": track_id}
    assert factory._active_processors == {}


@pytest.mark.asyncio
async def test_recommendation_analysis_returns_its_lease_when_analysis_raises(wav, factory):
    with patch.object(
        cp.ChunkedAudioProcessor, "get_mastering_recommendation", side_effect=RuntimeError("boom")
    ):
        with pytest.raises(RuntimeError):
            await cached_or_analyzed_recommendation(_cache_manager(), 7, wav, 0.4)

    assert factory._active_processors == {}


# --- closed processors refuse to lease -----------------------------------------


def test_hybrid_processor_refuses_to_lease_after_close(wav, factory):
    stream = _stream(wav, factory)
    stream.close()
    built_before = len(factory.built)

    with pytest.raises(ChunkCancelledError):
        stream.hybrid_processor()

    assert len(factory.built) == built_before
    assert factory._active_processors == {}


def test_a_close_landing_during_the_lease_hands_it_straight_back(wav, factory):
    stream = _stream(wav, factory)
    stream._release_processor()  # as after a discarded instance: next call re-leases
    real_acquire = factory.acquire

    def _acquire_then_close(**kwargs):
        leased = real_acquire(**kwargs)
        stream.close()  # the stream is torn down while this thread is mid-lease
        return leased

    with patch.object(factory, "acquire", side_effect=_acquire_then_close):
        with pytest.raises(ChunkCancelledError):
            stream.hybrid_processor()

    assert stream.processor is None
    assert factory._active_processors == {}


def test_preset_none_never_leases_and_closes_cleanly(wav, factory):
    stream = cp.ChunkedAudioProcessor(track_id=1, filepath=wav, preset=None, processor_factory=factory)
    assert stream.hybrid_processor() is None
    stream.close()
    assert stream.hybrid_processor() is None


# --- abandoned init ------------------------------------------------------------


def test_handoff_closes_a_processor_built_after_the_stream_gave_up(wav, factory):
    cancel = threading.Event()
    handoff = ProcessorInitHandoff(cancel)
    cancel.set()  # the stream gave up before the thread finished constructing

    processor = handoff.build(
        cp.ChunkedAudioProcessor, track_id=1, filepath=wav, preset="adaptive", processor_factory=factory
    )

    assert factory._active_processors == {}
    assert processor._closed


def test_handoff_abandon_closes_a_processor_built_before_the_stream_gave_up(wav, factory):
    cancel = threading.Event()
    handoff = ProcessorInitHandoff(cancel)
    processor = handoff.build(
        cp.ChunkedAudioProcessor, track_id=1, filepath=wav, preset="adaptive", processor_factory=factory
    )
    assert factory._active_processors == {1: processor.processor}  # live while the stream holds it

    handoff.abandon()

    assert cancel.is_set() and processor._closed
    assert factory._active_processors == {}


class _SlowProcessor:
    """Stand-in whose construction outlives the awaiting stream."""

    instances: list["_SlowProcessor"] = []

    def __init__(self, **_kwargs):
        time.sleep(0.4)
        self.closed = 0
        type(self).instances.append(self)

    def close(self) -> None:
        self.closed += 1


def _controller() -> AudioStreamController:
    controller = AudioStreamController()
    track = MagicMock()
    track.filepath = "/fake/track.wav"
    repo_factory = MagicMock()
    repo_factory.tracks.get_by_id.return_value = track
    controller._get_repository_factory = lambda: repo_factory
    controller.chunked_processor_class = _SlowProcessor
    return controller


def _websocket() -> AsyncMock:
    ws = AsyncMock()
    ws.client_state.name = "CONNECTED"
    return ws


@pytest.mark.asyncio
async def test_timed_out_init_still_returns_its_processor():
    _SlowProcessor.instances = []
    with patch.object(asc, "PROCESSOR_INIT_TIMEOUT", 0.05), patch.object(Path, "exists", return_value=True):
        await _controller().stream_enhanced_audio(
            websocket=_websocket(), track_id=1, preset="adaptive", intensity=0.5
        )

    await asyncio.sleep(0.6)  # let the abandoned init thread finish
    assert [p.closed for p in _SlowProcessor.instances] == [1]


@pytest.mark.asyncio
async def test_cancelled_init_still_returns_its_processor():
    _SlowProcessor.instances = []
    with patch.object(Path, "exists", return_value=True):
        task = asyncio.create_task(
            _controller().stream_enhanced_audio(
                websocket=_websocket(), track_id=1, preset="adaptive", intensity=0.5
            )
        )
        await asyncio.sleep(0.1)  # inside the worker thread's construction
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    await asyncio.sleep(0.6)
    assert [p.closed for p in _SlowProcessor.instances] == [1]
