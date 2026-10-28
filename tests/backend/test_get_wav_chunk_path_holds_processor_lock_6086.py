"""get_wav_chunk_path mutates DSP state under _processor_lock (#6086).

It reset `_dsp_state_advanced` and ran `_process_chunk_core` (which advances the
LevelManager's rms/gain history) with only `_sync_cache_lock`. A caller mixing it
with process_chunk could interleave that history or have the flag cleared by the
wrong call, defeating the #5274 invalidation. The DSP section now runs inside
`with _processor_lock`, nested inside `_sync_cache_lock` (the order chunk_render
already uses).
"""

import threading
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from core import chunk_streaming
from tests.backend.test_chunk_dsp_cancellation_4815 import _make_processor


class _SpyLock:
    """An RLock that records whether (and by whom) it is currently held."""

    def __init__(self):
        self._lock = threading.RLock()
        self.depth = 0
        self.events: list[str] = []

    def __enter__(self):
        self._lock.acquire()
        self.depth += 1
        self.events.append("acquire")
        return self

    def __exit__(self, *exc):
        self.depth -= 1
        self.events.append("release")
        self._lock.release()
        return False


@pytest.fixture(autouse=True)
def _identity_segment_extraction(monkeypatch):
    monkeypatch.setattr(
        "core.chunk_segment_extraction.extract_chunk_segment", lambda **kw: kw["processed_chunk"]
    )


def _processor(spy: _SpyLock, sync_events: list[str]) -> Mock:
    processor = _make_processor()
    processor.sample_rate = 44100
    processor.total_duration = 15.0
    processor.file_signature = "sig"
    processor._processor_lock = spy
    sync = _SpyLock()
    sync.events = sync_events
    processor._sync_cache_lock = sync
    processor._get_wav_chunk_path = Mock(return_value=Path("/tmp/v4_track_1_chunk_1.wav"))
    processor._wav_encoder.encode_and_save = Mock()
    processor._path_cache.store = Mock()
    processor._processor_factory.discard_lease = Mock()
    return processor


def test_the_dsp_state_is_touched_only_while_the_processor_lock_is_held():
    spy = _SpyLock()
    observed: dict[str, list[bool]] = {"held": []}
    processor = _processor(spy, [])

    def _dsp(chunk_index, fast_start=False):
        observed["held"].append(spy.depth > 0)
        processor._dsp_state_advanced = True
        return np.zeros((44100, 2), dtype=np.float32)

    processor._process_chunk_core = Mock(side_effect=_dsp)

    chunk_streaming.get_wav_chunk_path(processor, 1)

    assert observed["held"] == [True], "_process_chunk_core ran without _processor_lock"
    assert spy.depth == 0, "the lock must be released afterwards"
    assert spy.events == ["acquire", "release"]
    assert processor._dsp_state_advanced is False


def test_the_lock_is_released_when_the_render_fails():
    spy = _SpyLock()
    processor = _processor(spy, [])
    processor._process_chunk_core = Mock(side_effect=RuntimeError("dsp blew up"))

    with pytest.raises(RuntimeError, match="dsp blew up"):
        chunk_streaming.get_wav_chunk_path(processor, 1)

    assert spy.depth == 0


def test_a_cache_hit_does_not_need_the_processor_lock():
    spy = _SpyLock()
    processor = _processor(spy, [])
    processor._lookup_cached_chunk = Mock(return_value=Path("/tmp/cached.wav"))
    processor._process_chunk_core = Mock()

    assert chunk_streaming.get_wav_chunk_path(processor, 1) == "/tmp/cached.wav"

    assert spy.events == []
    processor._process_chunk_core.assert_not_called()
