"""
Regression tests: LibraryScanner cancellation via threading.Event (#3728, test debt #3736)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`LibraryScanner.should_stop` was a plain bool. Under default CPython the GIL
kept bare-attribute reads atomic, but free-threaded Python (PEP 703 /
`python -X gil=0`) races on it. #3728 promoted it to a `threading.Event`, the
idiomatic cross-thread cancellation primitive, matching #3710 /
library_auto_scanner.

The tests below exercise the real cancellation path — `stop_scan()` called from
another thread while `scan_directories()` is mid-batch — and assert the scan
thread exits promptly rather than only that the flag flipped.
"""

import threading
import time
from unittest.mock import MagicMock

import pytest

from auralis.library.scan_models import ScanResult
from auralis.library.scanner.scanner import LibraryScanner

# Generous ceiling: the scan loop checks should_stop between files, so a real
# stop lands in milliseconds. 5 s only fails a genuinely stuck thread.
JOIN_TIMEOUT = 5.0


def _make_scanner(files: list[str], per_file_delay: float = 0.0) -> LibraryScanner:
    """Build a scanner whose discovery yields *files* with an optional delay.

    library_database is a lightweight mock: LibraryScanner tolerates one that
    lacks try_acquire_scan_slot / release_scan_slot (it catches AttributeError),
    so the scan-slot guard stays out of the way.
    """
    library_database = MagicMock()
    library_database.try_acquire_scan_slot.return_value = (True, 1)
    # #4509: the per-directory dedup guard moved from LibraryScanner onto
    # library_database — a bare MagicMock's auto-attribute return value is
    # truthy, which would otherwise make every scan look "already scanning".
    library_database.try_reserve_scan_paths.return_value = []

    scanner = LibraryScanner(library_database)

    def _discover(directory: str, recursive: bool = True):
        for path in files:
            if per_file_delay:
                time.sleep(per_file_delay)
            yield path

    scanner.file_discovery = MagicMock()
    scanner.file_discovery.discover_audio_files.side_effect = _discover
    # #4840: the scanner no longer calls count_audio_files() — the counting
    # pass keeps its discovered paths and reuses them, so the tree is walked
    # once. Left configured anyway so this harness still works if a future
    # change reinstates a separate counting call.
    scanner.file_discovery.count_audio_files.return_value = len(files)

    scanner.batch_processor = MagicMock()
    scanner.batch_processor.process_file_batch.side_effect = (
        lambda batch, *_a, **_kw: _batch_result(len(batch))
    )

    return scanner


def _batch_result(processed: int) -> ScanResult:
    result = ScanResult()
    result.files_processed = processed
    result.files_added = processed
    return result


class TestStopScanSignal:
    """stop_scan() must set the Event and fan out to the sub-components."""

    def test_should_stop_is_a_threading_event(self):
        """#3728: a bare bool would silently pass every is_set() call site."""
        scanner = _make_scanner([])
        assert isinstance(scanner.should_stop, threading.Event)

    def test_stop_scan_sets_the_event(self):
        scanner = _make_scanner([])
        assert scanner.should_stop.is_set() is False

        scanner.stop_scan()

        assert scanner.should_stop.is_set() is True

    def test_stop_scan_propagates_to_discovery_and_batch_processor(self):
        """Cancellation must reach the two components that own the inner loops."""
        scanner = _make_scanner([])

        scanner.stop_scan()

        scanner.file_discovery.stop.assert_called_once()
        scanner.batch_processor.stop.assert_called_once()

    def test_stop_scan_is_idempotent(self):
        scanner = _make_scanner([])
        scanner.stop_scan()
        scanner.stop_scan()
        assert scanner.should_stop.is_set() is True


class TestStopScanMidBatch:
    """The scan thread must observe the Event and unwind promptly."""

    def test_scan_thread_exits_after_stop_scan(self):
        """A running scan stops and the thread joins well inside the timeout."""
        # 400 files at 5 ms each ≈ 2 s if the scan is never cancelled.
        scanner = _make_scanner([f"/music/{i}.flac" for i in range(400)], per_file_delay=0.005)

        results: list = []
        started = threading.Event()

        def _run():
            started.set()
            results.append(scanner.scan_directories(["/music"], batch_size=10))

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        assert started.wait(JOIN_TIMEOUT), "scan thread never started"

        # Let a couple of batches through, then cancel mid-scan.
        time.sleep(0.05)
        scanner.stop_scan()

        thread.join(timeout=JOIN_TIMEOUT)
        assert not thread.is_alive(), "scan thread did not exit after stop_scan()"
        assert scanner.should_stop.is_set() is True

        # The scan returned a partial result rather than raising.
        assert len(results) == 1
        assert results[0].files_found < 400

    def test_stop_before_scan_starts_returns_immediately(self):
        """Cancelling before the scan begins short-circuits the counting pass."""
        scanner = _make_scanner([f"/music/{i}.flac" for i in range(50)])
        scanner.should_stop.set()

        result = scanner.scan_directories(["/music"], batch_size=10)

        assert result.files_found == 0
        assert result.files_processed == 0
        scanner.file_discovery.discover_audio_files.assert_not_called()

    def test_scan_slot_is_released_when_cancelled(self):
        """A cancelled scan must not leak the concurrency slot (#2438 / #4330)."""
        scanner = _make_scanner([f"/music/{i}.flac" for i in range(50)])
        scanner.should_stop.set()

        scanner.scan_directories(["/music"], batch_size=10)

        scanner.library_database.release_scan_slot.assert_called_once()

    def test_directory_path_is_released_when_cancelled(self):
        """The per-directory dedup guard must not stay latched after a cancel.

        #4509: the guard moved onto library_database (a fresh LibraryScanner
        is constructed per real scan, so the dedup set has to live on the
        one object every call shares) — assert the release call reached it,
        mirroring the scan-slot release check above.
        """
        scanner = _make_scanner([f"/music/{i}.flac" for i in range(50)])
        scanner.should_stop.set()

        scanner.scan_directories(["/music"], batch_size=10)

        scanner.library_database.release_scan_paths.assert_called_once()

    def test_uncancelled_scan_still_completes_fully(self):
        """Control: without a stop, every file is discovered and processed."""
        scanner = _make_scanner([f"/music/{i}.flac" for i in range(25)])

        result = scanner.scan_directories(["/music"], batch_size=10)

        assert result.files_found == 25
        assert result.files_processed == 25
        assert scanner.should_stop.is_set() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
