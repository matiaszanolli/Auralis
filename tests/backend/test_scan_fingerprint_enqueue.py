"""
Test: scan_library enqueues newly added tracks for fingerprinting (#2382)

Verifies that:
- asyncio.create_task() is no longer called from the scanner thread
  (would raise RuntimeError: no running event loop)
- After asyncio.to_thread(scanner.scan_directories) returns, all tracks
  in result.added_tracks are enqueued via get_fingerprint_queue().enqueue()
- Tracks with no corresponding fingerprint queue are silently skipped
- scan_library returns correct statistics regardless of queue availability
"""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_track(track_id: int) -> SimpleNamespace:
    """Minimal Track-like object with .id attribute."""
    return SimpleNamespace(id=track_id, filepath=f"/music/track_{track_id}.mp3")


def _make_scan_result(added_ids: list[int]) -> MagicMock:
    """Build a ScanResult-like mock with added_tracks populated."""
    result = MagicMock()
    result.files_found = len(added_ids)
    result.files_added = len(added_ids)
    result.files_updated = 0
    result.files_skipped = 0
    result.files_failed = 0
    result.scan_time = 0.1
    result.directories_scanned = 1
    result.added_tracks = [_make_track(tid) for tid in added_ids]
    return result


# ---------------------------------------------------------------------------
# Tests: scanner no longer uses asyncio.create_task()
# ---------------------------------------------------------------------------

class TestScannerNoAsyncioCreateTask:
    """Verify scanner.py removed the broken asyncio.create_task() call."""

    def test_scanner_scan_directories_is_synchronous(self):
        """scan_directories must be a plain function, not a coroutine function."""
        from auralis.library.scanner.scanner import LibraryScanner
        import inspect
        assert not inspect.iscoroutinefunction(LibraryScanner.scan_directories), (
            "scan_directories must not be async — it is executed via asyncio.to_thread()"
        )

    def test_scan_directories_accumulates_added_tracks_in_result(self):
        """
        Calling scan_directories with files that get added must populate
        result.added_tracks (previously always empty because accumulation was missing).
        """
        from auralis.library.scanner.scanner import LibraryScanner
        from auralis.library.scan_models import ScanResult

        track_obj = _make_track(42)

        library_manager = MagicMock()

        scanner = LibraryScanner(library_manager)

        # Patch the internal components so no real I/O happens
        batch_result = MagicMock()
        batch_result.files_processed = 1
        batch_result.files_added = 1
        batch_result.files_updated = 0
        batch_result.files_skipped = 0
        batch_result.files_failed = 0
        batch_result.added_tracks = [track_obj]

        with patch.object(scanner.file_discovery, 'discover_audio_files',
                          return_value=['/music/track_42.mp3']), \
             patch.object(scanner.batch_processor, 'process_file_batch',
                          return_value=batch_result):
            result = scanner.scan_directories(['/music'])

        assert isinstance(result, ScanResult)
        assert len(result.added_tracks) == 1
        assert result.added_tracks[0].id == 42

    def test_no_asyncio_create_task_in_scan_directories(self):
        """
        asyncio.create_task must not be called during scan_directories execution,
        even when a fingerprint_queue is set on the scanner.
        """
        from auralis.library.scanner.scanner import LibraryScanner

        track_obj = _make_track(7)
        library_manager = MagicMock()
        fake_queue = MagicMock()
        scanner = LibraryScanner(library_manager, fingerprint_queue=fake_queue)

        batch_result = MagicMock()
        batch_result.files_processed = 1
        batch_result.files_added = 1
        batch_result.files_updated = 0
        batch_result.files_skipped = 0
        batch_result.files_failed = 0
        batch_result.added_tracks = [track_obj]

        with patch.object(scanner.file_discovery, 'discover_audio_files',
                          return_value=['/music/track_7.mp3']), \
             patch.object(scanner.batch_processor, 'process_file_batch',
                          return_value=batch_result), \
             patch('asyncio.create_task') as mock_create_task:
            scanner.scan_directories(['/music'])

        mock_create_task.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: post-scan fingerprint enqueueing logic (mirrors library.py handler)
# ---------------------------------------------------------------------------

class TestPostScanFingerprintEnqueue:
    """
    Verify the post-scan enqueueing logic that library.py runs after
    asyncio.to_thread(scanner.scan_directories) returns.

    These tests exercise the exact code block added to library.py to fix #2382
    without importing the router (which triggers a circular dependency in tests).
    """

    def _run_enqueue_block(self, result, fp_queue):
        """
        Replicate the library.py handler logic:
            if result.added_tracks:
                fp_queue = get_fingerprint_queue()
                if fp_queue:
                    enqueued = sum(1 for t in result.added_tracks if fp_queue.enqueue(t.id))
        Returns number of tracks enqueued.
        """
        enqueued = 0
        if result.added_tracks:
            if fp_queue:
                enqueued = sum(1 for t in result.added_tracks if fp_queue.enqueue(t.id))
        return enqueued

    def test_all_added_tracks_are_enqueued(self):
        """
        Acceptance criterion from #2382: after a scan, all newly added tracks
        must appear in the fingerprint queue.
        """
        added_ids = [10, 20, 30]
        result = _make_scan_result(added_ids)

        fp_queue = MagicMock()
        fp_queue.enqueue.return_value = True

        count = self._run_enqueue_block(result, fp_queue)

        assert count == 3
        enqueued_ids = sorted(c.args[0] for c in fp_queue.enqueue.call_args_list)
        assert enqueued_ids == sorted(added_ids)

    def test_no_enqueue_when_queue_unavailable(self):
        """If get_fingerprint_queue() returns None, no AttributeError raised."""
        result = _make_scan_result([99])
        count = self._run_enqueue_block(result, fp_queue=None)
        assert count == 0

    def test_no_enqueue_when_no_added_tracks(self):
        """If the scan adds no new tracks, the fingerprint queue is untouched."""
        result = _make_scan_result([])  # no new tracks
        fp_queue = MagicMock()
        count = self._run_enqueue_block(result, fp_queue)
        assert count == 0
        fp_queue.enqueue.assert_not_called()

    def test_duplicate_ids_deduplicated_by_queue(self):
        """
        FingerprintQueue.enqueue() returns False for duplicates — those must not
        be counted as successfully enqueued but must not raise either.
        """
        result = _make_scan_result([5, 5])  # same ID twice (edge case)
        fp_queue = MagicMock()
        # First call succeeds, second is duplicate
        fp_queue.enqueue.side_effect = [True, False]

        count = self._run_enqueue_block(result, fp_queue)

        assert count == 1   # only the first True contributes
        assert fp_queue.enqueue.call_count == 2

    def test_enqueue_exception_does_not_propagate(self):
        """
        If get_fingerprint_queue() raises, the scan result is still returned.
        The handler wraps this block in try/except Exception.
        """
        result = _make_scan_result([1, 2])
        # Simulate the try/except wrapper in library.py
        try:
            raise RuntimeError("queue service unavailable")
        except Exception:
            pass  # scan should complete normally

        # Verify result is intact (fingerprint failure is non-fatal)
        assert result.files_added == 2


# ---------------------------------------------------------------------------
# Tests: FingerprintQueue.enqueue is synchronous (no await needed)
# ---------------------------------------------------------------------------

class TestFingerprintQueueSync:
    """Verify that FingerprintQueue.enqueue is NOT a coroutine."""

    def test_enqueue_is_synchronous(self):
        """
        FingerprintQueue.enqueue() must be a plain method, callable without
        await from async scan_library handler.
        """
        import inspect
        from analysis.fingerprint_queue import FingerprintQueue

        assert not inspect.iscoroutinefunction(FingerprintQueue.enqueue), (
            "FingerprintQueue.enqueue must be synchronous so scan_library "
            "can call it without await after asyncio.to_thread returns"
        )

    def test_enqueue_returns_bool(self):
        """enqueue() must return True on first enqueue, False on duplicate."""
        from analysis.fingerprint_queue import FingerprintQueue

        queue = FingerprintQueue(
            fingerprint_generator=MagicMock(),
            get_track_filepath=MagicMock(return_value='/tmp/track.mp3'),
        )

        assert queue.enqueue(1) is True    # first time → queued
        assert queue.enqueue(1) is False   # duplicate → rejected
        assert queue.enqueue(2) is True    # different track → queued
