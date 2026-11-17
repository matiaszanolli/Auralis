"""
One DSP render per chunk cache key across processors (#5258)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Every stream leases its own processor (#6091), so two streams missing the cache for
the same chunk rendered it twice. chunk_single_flight makes the first caller the
leader and the rest wait for the WAV it leaves; a cancelled or failed leader never
fails its followers, and unrelated keys never wait on each other.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from unittest.mock import Mock, patch

import numpy as np
import pytest

from core import chunk_streaming
from core.chunk_single_flight import chunk_flights
from core.chunk_stream_state import ChunkCancelledError


class _Disk:
    """The shared durable tier: key -> path, written by whichever processor renders."""

    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self.renders: list[str] = []
        self.render_started = threading.Event()
        self.release_render = threading.Event()


def _processor(disk: _Disk, key: str, cancel: threading.Event | None = None) -> Mock:
    p = Mock()
    p.total_chunks = 9
    p._cancel_event = cancel
    p._validate_chunk_index = Mock()
    p._path_cache.cache_key = Mock(return_value=key)
    p._lookup_cached_chunk = lambda idx: disk.files.get(key)
    p._smooth_level_transition = lambda audio, idx: audio
    p._processor_lock = threading.RLock()
    return p


def _fake_render(disk: _Disk, fail_first: bool = False):
    state = {"calls": 0}

    def render(processor, chunk_index):
        key = processor._path_cache.cache_key(chunk_index)
        state["calls"] += 1
        disk.renders.append(key)
        disk.render_started.set()
        assert disk.release_render.wait(5), "test never released the leader"
        if fail_first and state["calls"] == 1:
            raise ChunkCancelledError("leader abandoned")
        disk.files[key] = f"/cache/{key}.wav"
        return (disk.files[key], np.zeros((4, 2), dtype=np.float32))

    return render


def _run(processor: Mock, results: list, errors: list) -> threading.Thread:
    def target():
        try:
            results.append(chunk_streaming.process_chunk(processor, 3))
        except BaseException as exc:  # noqa: BLE001 - surfaced to the asserting thread
            errors.append(exc)

    t = threading.Thread(target=target)
    t.start()
    return t


@pytest.fixture(autouse=True)
def _patched_cache_read():
    with patch.object(chunk_streaming, "read_chunk_wav", lambda path: np.zeros((4, 2), dtype=np.float32)):
        yield
    assert chunk_flights.in_flight() == 0, "a flight leaked past its render"


def test_concurrent_processors_for_one_key_render_once():
    disk = _Disk()
    results: list = []
    errors: list = []
    with patch.object(chunk_streaming, "render_chunk", _fake_render(disk)):
        leader = _run(_processor(disk, "k"), results, errors)
        assert disk.render_started.wait(5)
        followers = [_run(_processor(disk, "k"), results, errors) for _ in range(3)]
        disk.release_render.set()
        for t in [leader, *followers]:
            t.join(10)

    assert errors == []
    assert disk.renders == ["k"]
    assert [path for path, _ in results] == ["/cache/k.wav"] * 4


def test_different_keys_do_not_wait_on_each_other():
    disk = _Disk()
    results: list = []
    errors: list = []
    with patch.object(chunk_streaming, "render_chunk", _fake_render(disk)):
        a = _run(_processor(disk, "a"), results, errors)
        assert disk.render_started.wait(5)
        b = _run(_processor(disk, "b"), results, errors)
        # b became a leader of its own while a is still rendering: it was not queued behind a.
        pause = threading.Event()
        for _ in range(500):
            if len(disk.renders) >= 2:
                break
            pause.wait(0.01)
        assert sorted(disk.renders) == ["a", "b"]
        disk.release_render.set()
        a.join(10)
        b.join(10)

    assert errors == []
    assert sorted(path for path, _ in results) == ["/cache/a.wav", "/cache/b.wav"]


def test_a_cancelled_leader_does_not_fail_its_follower():
    disk = _Disk()
    results: list = []
    errors: list = []
    with patch.object(chunk_streaming, "render_chunk", _fake_render(disk, fail_first=True)):
        leader = _run(_processor(disk, "k"), results, errors)
        assert disk.render_started.wait(5)
        follower = _run(_processor(disk, "k"), results, errors)
        disk.release_render.set()
        leader.join(10)
        follower.join(10)

    assert [type(e) for e in errors] == [ChunkCancelledError]  # only the leader's own stream
    assert [path for path, _ in results] == ["/cache/k.wav"]  # the follower took over and rendered
    assert disk.renders == ["k", "k"]


def test_a_follower_whose_own_stream_is_cancelled_stops_waiting():
    disk = _Disk()
    results: list = []
    errors: list = []
    cancel = threading.Event()
    with patch.object(chunk_streaming, "render_chunk", _fake_render(disk)):
        leader = _run(_processor(disk, "k"), results, errors)
        assert disk.render_started.wait(5)
        follower_errors: list = []
        follower = _run(_processor(disk, "k", cancel=cancel), [], follower_errors)
        cancel.set()
        follower.join(5)
        assert not follower.is_alive()
        disk.release_render.set()
        leader.join(10)

    assert [type(e) for e in follower_errors] == [ChunkCancelledError]
    assert errors == []
    assert disk.renders == ["k"]
