"""A render cancelled mid-DSP is never persisted to the chunk cache (#5328).

#4815 checked the per-stream cancel event only before DSP. A seek landing while
a look-ahead chunk was already rendering could not stop the executor thread,
which then wrote the chunk to the durable, stream-identity-less on-disk cache
with gain smoothed against the abandoned stream's LevelManager — and a later
disk hit is never re-smoothed (#4669). Both rendering entry points now re-check
the event right before the durable write.
"""

import threading
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

# tests/backend/conftest.py puts auralis-web/backend on sys.path.
from core import chunk_streaming
from core.chunk_streaming import ChunkCancelledError
from tests.backend.test_chunk_dsp_cancellation_4815 import _make_processor


@pytest.fixture(autouse=True)
def _identity_segment_extraction(monkeypatch):
    monkeypatch.setattr(
        "core.chunk_operations.ChunkOperations.extract_chunk_segment",
        lambda **kw: kw["processed_chunk"],
    )


def _rendering_processor(event: threading.Event, *, cancel_during_dsp: bool) -> Mock:
    processor = _make_processor(cancel_event=event)
    processor.sample_rate = 44100
    processor.total_duration = 15.0
    processor.file_signature = "sig"
    processor._sync_cache_lock = threading.RLock()
    processor._get_wav_chunk_path = Mock(return_value=Path("/tmp/v4_track_1_chunk_1.wav"))
    processor._wav_encoder.encode_and_save_from_path = Mock(return_value="/tmp/chunk_1.wav")
    processor._wav_encoder.encode_and_save = Mock()
    processor._path_cache.store = Mock()
    processor._processor_factory.invalidate = Mock()

    def _dsp(chunk_index, fast_start=False):
        processor._dsp_state_advanced = True
        if cancel_during_dsp:
            event.set()  # the seek lands while this render is in flight
        return np.zeros((44100, 2), dtype=np.float32)

    processor._process_chunk_core = Mock(side_effect=_dsp)
    return processor


def _assert_nothing_persisted(processor: Mock) -> None:
    processor._wav_encoder.encode_and_save_from_path.assert_not_called()
    processor._wav_encoder.encode_and_save.assert_not_called()
    processor._path_cache.store.assert_not_called()


class TestProcessChunk:
    def test_render_cancelled_mid_dsp_is_not_persisted(self):
        processor = _rendering_processor(threading.Event(), cancel_during_dsp=True)

        with pytest.raises(ChunkCancelledError):
            chunk_streaming.process_chunk(processor, chunk_index=1, locked=False)

        processor._process_chunk_core.assert_called_once()
        _assert_nothing_persisted(processor)

    def test_cancellation_does_not_invalidate_the_pooled_processor(self):
        """A cancel is not a failed retry (#5274); discarding the shared
        processor would make every scrub rebuild it."""
        processor = _rendering_processor(threading.Event(), cancel_during_dsp=True)

        with pytest.raises(ChunkCancelledError):
            chunk_streaming.process_chunk(processor, chunk_index=1, locked=False)

        processor._processor_factory.invalidate.assert_not_called()
        assert processor._dsp_state_advanced is False

    def test_uncancelled_render_is_still_persisted(self):
        processor = _rendering_processor(threading.Event(), cancel_during_dsp=False)

        path, _audio = chunk_streaming.process_chunk(processor, chunk_index=1, locked=False)

        assert path == "/tmp/chunk_1.wav"
        processor._path_cache.store.assert_called_once_with(1, "/tmp/chunk_1.wav")


class TestGetWavChunkPath:
    def test_render_cancelled_mid_dsp_is_not_persisted(self):
        processor = _rendering_processor(threading.Event(), cancel_during_dsp=True)

        with pytest.raises(ChunkCancelledError):
            chunk_streaming.get_wav_chunk_path(processor, chunk_index=1)

        _assert_nothing_persisted(processor)
        processor._processor_factory.invalidate.assert_not_called()

    def test_already_cancelled_stream_skips_dsp(self):
        event = threading.Event()
        event.set()
        processor = _rendering_processor(event, cancel_during_dsp=False)

        with pytest.raises(ChunkCancelledError):
            chunk_streaming.get_wav_chunk_path(processor, chunk_index=1)

        processor._process_chunk_core.assert_not_called()
        _assert_nothing_persisted(processor)

    def test_uncancelled_render_is_still_persisted(self):
        processor = _rendering_processor(threading.Event(), cancel_during_dsp=False)

        path = chunk_streaming.get_wav_chunk_path(processor, chunk_index=1)

        assert path == "/tmp/v4_track_1_chunk_1.wav"
        processor._wav_encoder.encode_and_save.assert_called_once()
        processor._path_cache.store.assert_called_once()
