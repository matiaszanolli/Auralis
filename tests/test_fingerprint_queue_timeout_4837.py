"""Fingerprint extraction is bounded per track (#4837).

`_process_track` called `extract_and_store()` synchronously with no bound, so a
pathological file that hung DSP analysis wedged the worker thread — and the
`ResizableSemaphore` slot it holds — for the lifetime of the process. With
`num_workers` defaulting to `max(4, cpu_count * 0.5)`, as few as four such files
starved fingerprinting permanently until an app restart.

These tests drive `_process_track` directly with a tiny `track_timeout`, which
is the same code path a worker thread takes.
"""

import threading
import time
from types import SimpleNamespace

import pytest

from auralis.services.fingerprint_queue import (
    DEFAULT_TRACK_TIMEOUT_SECONDS,
    FingerprintExtractionQueue,
    _default_track_timeout,
)


class _StubExtractor:
    """Extractor whose `extract_and_store` behaves as the test dictates."""

    def __init__(self, behaviour):
        self._behaviour = behaviour
        self.calls: list[int] = []

    def extract_and_store(self, track_id: int, filepath: str) -> bool:
        self.calls.append(track_id)
        return self._behaviour(track_id, filepath)


def _make_queue(extractor, track_timeout: float) -> FingerprintExtractionQueue:
    return FingerprintExtractionQueue(
        fingerprint_extractor=extractor,
        get_repository_factory=lambda: None,
        num_workers=1,
        enable_adaptive_scaling=False,
        max_workers=1,
        track_timeout=track_timeout,
    )


def _track(track_id: int) -> SimpleNamespace:
    return SimpleNamespace(id=track_id, filepath=f"/music/{track_id}.flac")


class TestPerTrackTimeout:
    def test_hung_extraction_does_not_wedge_the_worker(self):
        release = threading.Event()

        def _hang(track_id, filepath):
            release.wait(30)  # far beyond the timeout; released in teardown
            return True

        queue = _make_queue(_StubExtractor(_hang), track_timeout=0.2)
        try:
            started = time.time()
            queue._process_track(_track(1), worker_id=0)
            elapsed = time.time() - started

            assert elapsed < 5, "worker stayed blocked on the hung extraction"
            assert queue.stats['failed'] == 1
            assert queue.stats['completed'] == 0
            assert queue.stats['processing'] == 0
        finally:
            release.set()

    def test_semaphore_slot_is_released_after_a_timeout(self):
        release = threading.Event()
        queue = _make_queue(
            _StubExtractor(lambda track_id, filepath: release.wait(30) or True),
            track_timeout=0.2,
        )
        try:
            in_use_before, capacity = queue.processing_semaphore.usage
            queue._process_track(_track(1), worker_id=0)

            in_use_after, _ = queue.processing_semaphore.usage
            assert in_use_after == in_use_before, (
                "the timed-out track leaked its semaphore slot — with every slot "
                "leaked, fingerprinting is starved for the life of the process"
            )
            assert capacity > 0
        finally:
            release.set()

    def test_later_tracks_still_process_after_a_timeout(self):
        release = threading.Event()

        def _hang_only_first(track_id, filepath):
            if track_id == 1:
                release.wait(30)
            return True

        extractor = _StubExtractor(_hang_only_first)
        queue = _make_queue(extractor, track_timeout=0.2)
        try:
            queue._process_track(_track(1), worker_id=0)
            queue._process_track(_track(2), worker_id=0)

            assert extractor.calls == [1, 2]
            assert queue.stats['failed'] == 1
            assert queue.stats['completed'] == 1
        finally:
            release.set()

    def test_progress_reports_the_timeout_as_an_error(self):
        release = threading.Event()
        queue = _make_queue(
            _StubExtractor(lambda track_id, filepath: release.wait(30) or True),
            track_timeout=0.2,
        )
        reports: list[dict] = []
        queue.set_progress_callback(reports.append)
        try:
            queue._process_track(_track(7), worker_id=0)
        finally:
            release.set()

        assert len(reports) == 1
        assert reports[0]['status'] == 'error'
        assert reports[0]['track_id'] == 7
        assert 'timed out' in reports[0]['error']

    def test_normal_extraction_is_unaffected(self):
        queue = _make_queue(_StubExtractor(lambda track_id, filepath: True), track_timeout=5)
        queue._process_track(_track(1), worker_id=0)

        assert queue.stats['completed'] == 1
        assert queue.stats['failed'] == 0

    def test_extractor_exceptions_still_surface_as_failures(self):
        def _boom(track_id, filepath):
            raise ValueError("corrupt file")

        queue = _make_queue(_StubExtractor(_boom), track_timeout=5)
        reports: list[dict] = []
        queue.set_progress_callback(reports.append)

        queue._process_track(_track(1), worker_id=0)

        assert queue.stats['failed'] == 1
        assert 'corrupt file' in reports[0]['error']


class TestTimeoutConfiguration:
    def test_default_is_used_when_unset(self, monkeypatch):
        monkeypatch.delenv('AURALIS_FINGERPRINT_TRACK_TIMEOUT', raising=False)
        assert _default_track_timeout() == DEFAULT_TRACK_TIMEOUT_SECONDS

    def test_env_override_is_honoured(self, monkeypatch):
        monkeypatch.setenv('AURALIS_FINGERPRINT_TRACK_TIMEOUT', '42.5')
        assert _default_track_timeout() == 42.5

    @pytest.mark.parametrize('raw', ['not-a-number', '0', '-1'])
    def test_invalid_override_falls_back_rather_than_disabling_the_bound(self, monkeypatch, raw):
        monkeypatch.setenv('AURALIS_FINGERPRINT_TRACK_TIMEOUT', raw)
        assert _default_track_timeout() == DEFAULT_TRACK_TIMEOUT_SECONDS
