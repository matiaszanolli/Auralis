"""
Discovery walks the tree once, and reports progress while counting (#4840)

`scan_directories()` ran a full recursive `count_audio_files()` pass over every
configured directory and then threw the result away, so the identical walk —
including a `stat()` per entry for the symlink-cycle check — ran again for the
real pass. For a discovery-bound library on slow storage (network share, USB
drive: the realistic desktop cases) that roughly doubled wall-clock. Worse, the
counting pass emitted no frames at all, so the UI showed a pure indeterminate
spinner for its entire duration — potentially minutes of apparent silence
before anything moved.

The counting pass now keeps the paths it finds and the processing pass consumes
them, so the tree is traversed once. The cache is hard-capped: #2160 requires
memory to stay bounded regardless of library size, so past the cap the cache is
dropped and the old two-walk behaviour resumes rather than trading that
invariant away.

The #4616 denominator behaviour must survive all of this — `progress` has to
stay a real, monotonically increasing fraction and must not regress to #4411's
pinned-at-100%.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import threading
from unittest.mock import MagicMock

import pytest

import auralis.library.scanner.scanner as scanner_module
from auralis.library.scan_models import ScanResult
from auralis.library.scanner.scanner import LibraryScanner


def _batch_result(processed: int) -> ScanResult:
    result = ScanResult()
    result.files_processed = processed
    result.files_added = processed
    return result


def _make_scanner(files_by_dir: dict[str, list[str]]) -> tuple[LibraryScanner, dict]:
    """A scanner whose discovery is instrumented to count traversals."""
    library_database = MagicMock()
    library_database.try_acquire_scan_slot.return_value = (True, 1)
    # #4509: a bare MagicMock's auto-attribute return value is truthy, which
    # would otherwise make the per-directory dedup guard reject every scan.
    library_database.try_reserve_scan_paths.return_value = []

    scanner = LibraryScanner(library_database)
    stats = {'walks': 0, 'entries_yielded': 0, 'walks_per_dir': {}}

    def _discover(directory: str, recursive: bool = True):
        stats['walks'] += 1
        stats['walks_per_dir'][directory] = stats['walks_per_dir'].get(directory, 0) + 1
        for path in files_by_dir.get(directory, []):
            stats['entries_yielded'] += 1
            yield path

    scanner.file_discovery = MagicMock()
    scanner.file_discovery.discover_audio_files.side_effect = _discover

    scanner.batch_processor = MagicMock()
    scanner.batch_processor.process_file_batch.side_effect = (
        lambda batch, *_a, **_kw: _batch_result(len(batch))
    )
    return scanner, stats


class TestSingleWalk:
    """The performance claim, measured rather than asserted in prose."""

    def test_tree_is_walked_once_per_directory(self):
        scanner, stats = _make_scanner({'/music': [f'/music/{i}.mp3' for i in range(10)]})

        scanner.scan_directories(['/music'], batch_size=4)

        assert stats['walks_per_dir']['/music'] == 1, (
            f"directory walked {stats['walks_per_dir']['/music']} times — the "
            "counting pass and the processing pass are both traversing it (#4840)"
        )

    def test_multiple_directories_each_walked_once(self):
        scanner, stats = _make_scanner({
            '/a': ['/a/1.mp3', '/a/2.mp3'],
            '/b': ['/b/1.mp3'],
        })

        scanner.scan_directories(['/a', '/b'], batch_size=10)

        assert stats['walks'] == 2, f"expected 2 walks for 2 directories, got {stats['walks']}"

    def test_every_discovered_file_is_still_processed(self):
        """One walk must not mean fewer files."""
        files = [f'/music/{i}.mp3' for i in range(25)]
        scanner, _ = _make_scanner({'/music': files})

        result = scanner.scan_directories(['/music'], batch_size=4)

        assert result.files_found == 25
        assert result.files_processed == 25

    def test_directories_scanned_is_still_reported(self):
        """The cached path skips the per-directory loop, so this counter has to
        be carried over from the counting pass or it silently reads zero."""
        scanner, _ = _make_scanner({'/a': ['/a/1.mp3'], '/b': ['/b/1.mp3']})

        result = scanner.scan_directories(['/a', '/b'], batch_size=10)

        assert result.directories_scanned == 2


class TestCacheStaysBounded:
    """#2160: memory must not grow with library size."""

    def test_falls_back_to_a_second_walk_past_the_cap(self, monkeypatch):
        monkeypatch.setattr(scanner_module, '_PATH_CACHE_LIMIT', 5)
        files = [f'/music/{i}.mp3' for i in range(12)]
        scanner, stats = _make_scanner({'/music': files})

        result = scanner.scan_directories(['/music'], batch_size=4)

        assert stats['walks_per_dir']['/music'] == 2, (
            "past the cache cap the scan must re-walk rather than hold an "
            "unbounded path list (#2160)"
        )
        assert result.files_processed == 12, "the fallback path must still process everything"

    def test_exactly_at_the_cap_still_uses_one_walk(self, monkeypatch):
        """Boundary: a library of exactly _PATH_CACHE_LIMIT files still caches.

        The cap is checked before each append, so the Nth file is admitted when
        the list holds N-1. Overflow begins at limit+1. Pinned so a future
        off-by-one is visible rather than silently costing everyone a walk.
        """
        monkeypatch.setattr(scanner_module, '_PATH_CACHE_LIMIT', 10)
        scanner, stats = _make_scanner({'/music': [f'/music/{i}.mp3' for i in range(10)]})

        scanner.scan_directories(['/music'], batch_size=4)

        assert stats['walks_per_dir']['/music'] == 1

    def test_one_past_the_cap_falls_back(self, monkeypatch):
        monkeypatch.setattr(scanner_module, '_PATH_CACHE_LIMIT', 10)
        scanner, stats = _make_scanner({'/music': [f'/music/{i}.mp3' for i in range(11)]})

        scanner.scan_directories(['/music'], batch_size=4)

        assert stats['walks_per_dir']['/music'] == 2


class TestCountingPassReportsProgress:
    """The UX half: no more silent indeterminate spinner."""

    def _frames(self, scanner) -> list[dict]:
        frames: list[dict] = []
        scanner.set_progress_callback(frames.append)
        return frames

    def test_counting_frames_are_emitted_during_the_count(self, monkeypatch):
        monkeypatch.setattr(scanner_module, '_COUNT_PROGRESS_EVERY', 5)
        scanner, _ = _make_scanner({'/music': [f'/music/{i}.mp3' for i in range(20)]})
        frames = self._frames(scanner)

        scanner.scan_directories(['/music'], batch_size=100)

        counting = [f for f in frames if f.get('stage') == 'counting']
        assert counting, (
            "the counting pass emitted no frames — the UI sits on a pure "
            "indeterminate spinner for its whole duration (#4840)"
        )
        assert [f['total_found'] for f in counting] == [5, 10, 15, 20], (
            "the running tally must actually climb"
        )

    def test_counting_frames_report_indeterminate_progress(self, monkeypatch):
        """Honesty check: there is no denominator yet, so `progress` must be
        None rather than a fabricated fraction."""
        monkeypatch.setattr(scanner_module, '_COUNT_PROGRESS_EVERY', 5)
        scanner, _ = _make_scanner({'/music': [f'/music/{i}.mp3' for i in range(10)]})
        frames = self._frames(scanner)

        scanner.scan_directories(['/music'], batch_size=100)

        for frame in (f for f in frames if f.get('stage') == 'counting'):
            assert frame['progress'] is None


class TestDenominatorBehaviourUnchanged:
    """#4616 / #4411 must not regress."""

    def test_progress_is_a_real_increasing_fraction(self):
        scanner, _ = _make_scanner({'/music': [f'/music/{i}.mp3' for i in range(20)]})
        frames: list[dict] = []
        scanner.set_progress_callback(frames.append)

        scanner.scan_directories(['/music'], batch_size=5)

        fractions = [
            f['progress'] for f in frames
            if f.get('stage') == 'processing' and f.get('progress') is not None
        ]
        assert fractions, "no processing frame carried a fraction"
        assert fractions == sorted(fractions), f"progress went backwards: {fractions}"
        assert fractions[0] < 1.0, (
            "the first processing frame is already at 100% — #4411's "
            "pinned-denominator bug is back"
        )
        assert fractions[-1] == pytest.approx(1.0)

    def test_total_expected_matches_the_real_file_count(self):
        scanner, _ = _make_scanner({'/music': [f'/music/{i}.mp3' for i in range(7)]})
        frames: list[dict] = []
        scanner.set_progress_callback(frames.append)

        scanner.scan_directories(['/music'], batch_size=3)

        totals = {f['total_expected'] for f in frames if 'total_expected' in f}
        assert totals == {7}


class TestCancellation:
    """stop() during the counting pass must abandon the scan, as before."""

    def test_stop_during_counting_returns_early(self, monkeypatch):
        # Counting frames are the only hook into the count pass, so the cadence
        # has to be small enough to fire within this fixture's file count.
        monkeypatch.setattr(scanner_module, '_COUNT_PROGRESS_EVERY', 5)
        scanner, stats = _make_scanner({'/music': [f'/music/{i}.mp3' for i in range(50)]})

        def _stop_after_a_few(frame):
            if frame.get('stage') == 'counting':
                scanner.should_stop.set()

        scanner.set_progress_callback(_stop_after_a_few)
        result = scanner.scan_directories(['/music'], batch_size=5)

        assert result.files_processed == 0, "a cancelled count must not process anything"

    def test_stop_is_still_a_threading_event(self):
        scanner, _ = _make_scanner({})
        assert isinstance(scanner.should_stop, threading.Event)
