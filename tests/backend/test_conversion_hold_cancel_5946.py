"""A temp-WAV hold is not leaked when its stream is cancelled mid-conversion (#5946).

`ConvertedWavRegistry.acquire()` takes its hold before it decodes the file. A
stream cancelled (stop/seek/skip/disconnect) while that decode was still running
used to leave the worker thread to finish the acquire and return the key to
nobody - refs stayed >= 1 and the full-track float32 WAV was never evicted. Two
holders were affected: `stream_normal_audio` (assigned `conversion_key` only
after the await returned) and `SeekableSource` (set `_key` after the blocking
acquire, while `close()` saw `_key is None` and returned).
"""

import asyncio
import json
import sys
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import seekable_source, stream_normal
from core.audio_stream_controller import AudioStreamController
from core.seekable_source import (
    SeekableSource,
    SeekableSourceClosed,
    acquire_conversion,
)


class _SlowRegistry:
    """Stands in for ConvertedWavRegistry: acquire blocks until `unblock` is set."""

    def __init__(self, expected_acquires: int = 1) -> None:
        self.unblock = threading.Event()
        self.all_started = threading.Event()
        self._expected = expected_acquires
        self._lock = threading.Lock()
        self.acquired: list[str] = []
        self.released: list[str] = []

    def acquire(self, filepath, *, prefix=None):
        with self._lock:
            key = f"key-{len(self.acquired)}"
            self.acquired.append(key)
            if len(self.acquired) >= self._expected:
                self.all_started.set()
        assert self.unblock.wait(timeout=10), "test never unblocked the decode"
        return key, f"/tmp/{key}.wav"

    def release(self, key):
        with self._lock:
            self.released.append(key)

    @property
    def refs(self) -> int:
        return len(self.acquired) - len(self.released)


async def _wait_until(predicate, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "condition never became true"
        await asyncio.sleep(0.01)


class TestAcquireConversion:
    @pytest.mark.asyncio
    async def test_cancel_during_acquire_releases_the_late_hold(self):
        registry = _SlowRegistry()
        task = asyncio.create_task(acquire_conversion(registry, "/music/a.m4a"))
        await _wait_until(registry.all_started.is_set)

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        registry.unblock.set()

        await _wait_until(lambda: registry.released == ["key-0"])
        assert registry.refs == 0

    @pytest.mark.asyncio
    async def test_normal_completion_hands_the_key_to_the_caller_without_releasing(self):
        registry = _SlowRegistry()
        registry.unblock.set()

        key, path = await acquire_conversion(registry, "/music/a.m4a")

        assert (key, path) == ("key-0", "/tmp/key-0.wav")
        await asyncio.sleep(0.05)
        assert registry.released == []

    @pytest.mark.asyncio
    async def test_failed_acquire_releases_nothing_extra(self):
        class _Failing(_SlowRegistry):
            def acquire(self, filepath, *, prefix=None):
                raise OSError("decode failed")

        registry = _Failing()
        task = asyncio.create_task(acquire_conversion(registry, "/music/a.m4a"))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises((asyncio.CancelledError, OSError)):
            await task
        await asyncio.sleep(0.05)
        assert registry.released == []  # registry.acquire cleans up its own failures


class TestSeekableSourceCloseDuringResolve:
    def _source(self, registry) -> SeekableSource:
        return SeekableSource("/music/a.m4a", registry)

    def test_close_while_resolving_releases_the_late_acquire(self):
        registry = _SlowRegistry()
        source = self._source(registry)
        outcome: list = []

        def resolve():
            try:
                outcome.append(source.resolve())
            except BaseException as exc:  # noqa: BLE001 - the test inspects it
                outcome.append(exc)

        with patch.object(seekable_source, "can_seek_natively", return_value=False):
            worker = threading.Thread(target=resolve)
            worker.start()
            assert registry.all_started.wait(timeout=5)

            source.close()  # the cancelled stream's finally: _key is still None here
            registry.unblock.set()
            worker.join(timeout=5)

        assert isinstance(outcome[0], SeekableSourceClosed)
        assert registry.released == ["key-0"]
        assert registry.refs == 0
        assert source.converted is False

    def test_concurrent_resolves_keep_exactly_one_hold(self):
        registry = _SlowRegistry(expected_acquires=2)
        source = self._source(registry)
        paths: list = []

        with patch.object(seekable_source, "can_seek_natively", return_value=False):
            workers = [threading.Thread(target=lambda: paths.append(source.resolve())) for _ in range(2)]
            for w in workers:
                w.start()
            assert registry.all_started.wait(timeout=5)
            registry.unblock.set()
            for w in workers:
                w.join(timeout=5)

        assert len(set(paths)) == 1
        assert registry.refs == 1
        source.close()
        assert registry.refs == 0

    def test_source_is_reusable_after_close(self):
        registry = _SlowRegistry()
        registry.unblock.set()
        source = self._source(registry)

        with patch.object(seekable_source, "can_seek_natively", return_value=False):
            first = source.resolve()
            source.close()
            second = source.resolve()

        assert first != second
        assert registry.refs == 1


class TestStreamNormalCancelledDuringConversion:
    @pytest.mark.asyncio
    async def test_cancelled_stream_leaves_the_registry_at_zero_refs(self):
        registry = _SlowRegistry()
        controller = AudioStreamController()
        controller._send_stream_start = AsyncMock(return_value=True)
        track = MagicMock()
        track.filepath = "/tmp/fake_5946.m4a"
        factory = MagicMock()
        factory.tracks.get_by_id.return_value = track
        controller._get_repository_factory = MagicMock(return_value=factory)
        ws = MagicMock()
        ws.client_state = MagicMock()
        ws.client_state.name = "CONNECTED"
        ws.send_text = AsyncMock(side_effect=lambda text: json.loads(text))
        ws.send_bytes = AsyncMock()

        with patch.object(stream_normal, "converted_wavs", registry), \
             patch.object(stream_normal, "validate_file_path", side_effect=lambda p, **_kw: p):
            task = asyncio.create_task(
                stream_normal.stream_normal_audio(controller=controller, track_id=5946, websocket=ws)
            )
            await _wait_until(registry.all_started.is_set)

            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            registry.unblock.set()

            await _wait_until(lambda: registry.refs == 0)
        assert registry.acquired == ["key-0"]
        assert registry.released == ["key-0"]
