"""
Stages of LibraryScanner.scan_directories (split from scanner.py, #5837): the
counting pass that establishes the progress denominator, and the batch feeder
that turns discovered paths into processed batches.

Pure code motion out of the old ``scan_directories`` body -- the closures became
:class:`BatchFeeder`, the counting loop became :func:`count_audio_files`. The
module-level constants stay in ``scanner.py`` and are passed in, so they remain
patchable there.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from collections.abc import Callable
from typing import Any, NamedTuple

from ...utils.logging import debug, warning
from ..scan_models import MAX_RECORDED_FAILURES, ScanResult
from ..scan_paths import reservation_key

ProgressReporter = Callable[[dict[str, Any]], None]


def claim_scan(library_database: Any, directories: list[str], result: ScanResult) -> list[str] | None:
    """Take a scan slot and reserve the directories; None means rejected.

    On rejection ``result.rejected`` is set and nothing is left held.
    """
    # --- Concurrency guard (#2438) ---
    # No `except AttributeError` around this or the calls below (#5802): a
    # real LibraryDatabase always has them, and swallowing the error made the
    # guard fail OPEN -- a renamed attribute inside the method left the scan
    # running with no slot held. Tests that hand the scanner a stand-in
    # database give it these methods (a `MagicMock(spec=LibraryDatabase)`).
    acquired, max_scans = library_database.try_acquire_scan_slot()

    if not acquired:
        warning(
            f"Scan rejected: max_concurrent_scans limit ({max_scans}) already reached. "
            "Retry when the active scan completes."
        )
        result.rejected = True
        return None

    # --- Per-directory dedup guard (#3455 / #4509) ---
    # Reserved on library_database, not on self — see the #4509 note in
    # __init__: a fresh LibraryScanner per invocation means an instance
    # attribute here would never be shared between two overlapping scans.
    normalized = [reservation_key(d) for d in directories]
    already_scanning: list[str] = library_database.try_reserve_scan_paths(normalized)

    if already_scanning:
        warning(
            f"Scan rejected: directories already being scanned: {already_scanning}"
        )
        result.rejected = True
        # #4330: release the slot here or it leaks permanently. We must NOT
        # release `normalized` from the shared dedup set: try_reserve_scan_paths()
        # did not reserve them for us on this rejection path (they belong to
        # the OTHER, already-running scan), so there is nothing of ours to release.
        library_database.release_scan_slot()
        return None
    return normalized


class PathCensus(NamedTuple):
    """Outcome of the counting pass."""

    total_expected: int
    cached_paths: list[str] | None   # None when the cache overflowed
    directories_counted: int


def count_audio_files(
    file_discovery: Any,
    directories: list[str],
    recursive: bool,
    should_stop: threading.Event,
    report: ProgressReporter,
    cache_limit: int,
    progress_every: int,
) -> PathCensus:
    """Walk ``directories`` once, counting files and caching their paths.

    #4616: establish the progress denominator BEFORE the streaming pass.
    `files_found` climbs in lockstep with `files_processed` (a file is counted
    as found at most `batch_size` frames before it is processed), so
    `processed / files_found` is pinned at ~100% — that was #4411, and it must
    not come back. A dedicated counting pass gives a fixed total, making
    `processed / total_expected` a real, monotonically increasing fraction.

    #4840: that pass used to throw its results away, so the identical recursive
    walk (including a `stat()` per entry for the symlink-cycle check) ran twice
    — roughly doubling wall-clock for discovery-bound libraries on slow
    storage, which is exactly the network-share / USB-drive case a desktop app
    hits. The paths are now kept and reused, so the tree is walked once.

    The cache is hard-capped rather than unbounded: #2160's streaming memory
    bound is the reason the count pass discarded paths in the first place. Past
    the cap the cache is dropped (``cached_paths`` is None) and the scan falls
    back to re-walking, so memory is bounded by construction and only
    libraries beyond the cap pay the second walk.
    """
    total_expected = 0
    cached_paths: list[str] | None = []
    directories_counted = 0

    for directory in directories:
        if should_stop.is_set():
            break
        for filepath in file_discovery.discover_audio_files(directory, recursive):
            if should_stop.is_set():
                break
            total_expected += 1
            if cached_paths is not None:
                if len(cached_paths) >= cache_limit:
                    # Give up caching for this scan; stay bounded.
                    debug(
                        f"Path cache limit ({cache_limit}) reached — "
                        "falling back to a second discovery walk (#4840)"
                    )
                    cached_paths = None
                else:
                    cached_paths.append(filepath)
            # #4840: the count pass emitted nothing, so the UI sat on a
            # pure indeterminate spinner for its whole duration — which
            # on a large or slow library is minutes of apparent silence.
            # A running tally is the one honest thing available before
            # the denominator exists.
            if total_expected % progress_every == 0:
                report({
                    'stage': 'counting',
                    'directory': directory,
                    'total_found': total_expected,
                    'processed': 0,
                    # Still genuinely unknown: there is no denominator
                    # until this pass finishes.
                    'progress': None,
                })
        directories_counted += 1

    return PathCensus(total_expected, cached_paths, directories_counted)


class BatchFeeder:
    """Accumulates discovered paths into batches and folds batch results into a ScanResult."""

    def __init__(
        self,
        batch_processor: Any,
        result: ScanResult,
        report: ProgressReporter,
        total_expected: int,
        batch_size: int,
        skip_existing: bool,
        check_modifications: bool,
    ) -> None:
        self._batch_processor = batch_processor
        self._result = result
        self._report = report
        self.total_expected = total_expected
        self._batch_size = batch_size
        self._skip_existing = skip_existing
        self._check_modifications = check_modifications
        self.pending_batch: list[str] = []

    def progress_fraction(self) -> float | None:
        """Completed fraction, or ``None`` while indeterminate.

        Clamped to 1.0: the count pass and the scan pass are separate
        traversals, so files added between them can push `processed` past
        `total_expected`. A zero total stays indeterminate rather than
        dividing by zero.
        """
        if self.total_expected <= 0:
            return None
        return min(self._result.files_processed / self.total_expected, 1.0)

    def feed(self, filepath: str) -> None:
        """Accumulate one discovered path, flushing on a full batch."""
        self.pending_batch.append(filepath)
        self._result.files_found += 1
        if len(self.pending_batch) >= self._batch_size:
            self._process_batch(self.pending_batch)
            self.pending_batch = []

    def flush(self) -> None:
        """Process the files that didn't fill a full batch."""
        if self.pending_batch:
            self._process_batch(self.pending_batch)
            self.pending_batch = []

    def _process_batch(self, batch: list[str]) -> None:
        """Process a single batch and accumulate results."""
        result = self._result
        batch_result: Any = self._batch_processor.process_file_batch(
            batch, self._skip_existing, self._check_modifications
        )
        result.files_processed += batch_result.files_processed
        result.files_added += batch_result.files_added
        result.files_updated += batch_result.files_updated
        result.files_skipped += batch_result.files_skipped
        result.files_failed += batch_result.files_failed
        # #4841: carry the per-file failures up too, still capped, so
        # the caller can name the files instead of only counting them.
        if batch_result.failures:
            room = MAX_RECORDED_FAILURES - len(result.failures)
            if room > 0:
                result.failures.extend(batch_result.failures[:room])
        # Accumulate added tracks so the async caller can enqueue
        # fingerprints in the event loop after to_thread() returns.
        # asyncio.create_task() cannot be called from this worker
        # thread — it raises RuntimeError: no running event loop (#2382).
        result.added_tracks.extend(batch_result.added_tracks)
        result.updated_tracks.extend(batch_result.updated_tracks)
        self._report({
            'stage': 'processing',
            'processed': result.files_processed,
            'added': result.files_added,
            'failed': result.files_failed,
            'total_found': result.files_found,
            'total_expected': self.total_expected,
            'progress': self.progress_fraction(),
            'current_file': batch[-1] if batch else None,  # last of the finished batch (#5913)
        })


def feed_from_walk(
    file_discovery: Any,
    feeder: "BatchFeeder",
    result: ScanResult,
    directories: list[str],
    recursive: bool,
    should_stop: threading.Event,
    report: ProgressReporter,
) -> None:
    """Second discovery walk, used only when the count pass's cache overflowed.

    Bounded memory wins over the extra I/O; see :func:`count_audio_files`.
    """
    for directory in directories:
        if should_stop.is_set():
            break

        for filepath in file_discovery.discover_audio_files(directory, recursive):
            if should_stop.is_set():
                break
            feeder.feed(filepath)

        result.directories_scanned += 1
        report({
            'stage': 'discovering',
            'directory': directory,
            'total_found': result.files_found,
            'total_expected': feeder.total_expected,
            'processed': result.files_processed,
            'progress': feeder.progress_fraction(),
        })


def preview_folder(
    file_discovery: Any, audio_analyzer: Any, folder_path: str, recursive: bool
) -> list[dict[str, Any]]:
    """Discover audio files under a folder and return their metadata (no database writes)."""
    files: list[dict[str, Any]] = []

    try:
        for filepath in file_discovery.discover_audio_files(folder_path, recursive):
            # Extract metadata for each file
            file_info: Any = audio_analyzer.extract_audio_info(filepath)

            if file_info:
                # Convert AudioFileInfo to dict for backward compatibility
                file_dict: dict[str, Any] = {
                    'filepath': filepath,
                    'duration': file_info.duration,
                    'sample_rate': file_info.sample_rate,
                    'channels': file_info.channels,
                    'format': file_info.format,
                }
            else:
                # Minimal info if analysis failed
                file_dict = {'filepath': filepath}

            files.append(file_dict)
    except Exception as e:
        warning(f"Error discovering audio files in {folder_path}: {e}")

    return files
