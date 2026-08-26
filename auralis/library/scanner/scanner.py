"""
Library Scanner
~~~~~~~~~~~~~~

Main scanner orchestrator

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import os
import threading
import time
from typing import Any
from collections.abc import Callable

from ...utils.logging import debug, info, warning
from ..scan_models import MAX_RECORDED_FAILURES, ScanResult
from .audio_analyzer import AudioAnalyzer
from .batch_processor import BatchProcessor
from .config import DEFAULT_BATCH_SIZE
from .duplicate_detector import DuplicateDetector
from .file_discovery import FileDiscovery
from .metadata_extractor import MetadataExtractor


# #4840: hard ceiling on the discovery cache. Path strings average roughly
# 100 bytes, so 100k paths is ~10 MB — negligible next to the audio buffers the
# app already holds, and it covers essentially every real music library. Past
# this the cache is dropped and discovery falls back to a second walk, which
# preserves #2160's "memory bounded regardless of library size" invariant
# instead of trading it away.
_PATH_CACHE_LIMIT = 100_000

# How often the counting pass emits a running tally. Frequent enough that the
# UI moves on a slow network share, rare enough not to flood the WebSocket.
_COUNT_PROGRESS_EVERY = 250


class LibraryScanner:
    """
    Comprehensive library scanning system

    Features:
    - Recursive directory scanning
    - Audio format detection and analysis
    - Metadata extraction
    - Duplicate detection
    - Progress tracking
    - Intelligent file filtering
    """

    def __init__(self, library_manager: Any) -> None:
        """
        Initialize scanner with library manager

        This scanner does NOT enqueue fingerprints. #2382 moved that to the
        caller, after `asyncio.to_thread(scan_directories)` returns, because
        `scan_directories` is fully synchronous and `asyncio.create_task` from
        its thread raised `RuntimeError: no running event loop`. The
        `fingerprint_queue` parameter this used to accept went with the dead
        `_enqueue_fingerprints` it fed (#4648) — it was being passed in and
        silently ignored. See `routers/library_scan.py` and
        `LibraryAutoScanner._run_scan_cycle` for the enqueue that actually runs.

        Args:
            library_manager: Library manager instance
        """
        self.library_manager: Any = library_manager
        self.progress_callback: Callable[[dict[str, Any]], None] | None = None
        # #3479: invoked after every successful scan completes (even an empty
        # one), outside the scan-slot lock so the consumer can do its own DB
        # I/O. Used by the backend to fire `reference_seeder.refresh_cloud()`.
        self.on_scan_complete: Callable[[ScanResult], None] | None = None
        # #3728: threading.Event instead of plain bool. Cross-thread
        # cancellation now goes through a proper synchronisation
        # primitive — under default CPython the GIL kept plain-bool
        # reads atomic, but free-threaded Python (PEP 703 / `python -X
        # gil=0`) would race on the bare attribute. Event is the
        # idiomatic choice and matches the scanner cancellation
        # pattern (#3710 / library_auto_scanner).
        self.should_stop: threading.Event = threading.Event()

        # Per-directory deduplication (#3455) lives on library_manager, not
        # here — see LibraryDatabase.try_reserve_scan_paths()/#4509. Every
        # caller (LibraryAutoScanner._do_scan, routers/library_scan.py)
        # constructs a fresh LibraryScanner per invocation, so an instance
        # attribute here would never be shared between two overlapping scans.

        # Initialize components
        self.file_discovery: Any = FileDiscovery()
        self.audio_analyzer: Any = AudioAnalyzer()
        self.metadata_extractor: Any = MetadataExtractor()
        self.batch_processor: Any = BatchProcessor(
            library_manager,
            self.audio_analyzer,
            self.metadata_extractor
        )
        self.duplicate_detector: Any = DuplicateDetector(
            self.file_discovery,
            self.audio_analyzer,
            library_manager
        )

    def set_progress_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Set callback for progress updates"""
        self.progress_callback = callback

    def set_scan_complete_callback(self, callback: Callable[[ScanResult], None]) -> None:
        """#3479: callback fired after a scan finishes (success path only),
        outside the scan-slot lock. Used to trigger reference-cloud refresh."""
        self.on_scan_complete = callback

    def stop_scan(self) -> None:
        """Signal scanner to stop (#3728: Event.set, not bare attribute)."""
        self.should_stop.set()
        self.file_discovery.stop()
        self.batch_processor.stop()

    def _release_scan_slot_safe(self) -> None:
        """Release a scan slot, tolerating a lightweight mock library_manager
        that lacks release_scan_slot (mirrors the try_acquire guard)."""
        try:
            self.library_manager.release_scan_slot()
        except AttributeError:
            pass

    def _release_scan_paths_safe(self, paths: list[str]) -> None:
        """Release reserved per-directory dedup paths (#3455 / #4509),
        tolerating a lightweight mock library_manager that lacks
        release_scan_paths (mirrors _release_scan_slot_safe)."""
        try:
            self.library_manager.release_scan_paths(paths)
        except AttributeError:
            pass

    def scan_directories(self, directories: list[str],
                        recursive: bool = True,
                        skip_existing: bool = True,
                        check_modifications: bool = True,
                        batch_size: int = DEFAULT_BATCH_SIZE) -> ScanResult:
        """
        Scan multiple directories for audio files

        Args:
            directories: List of directory paths to scan
            recursive: Whether to scan subdirectories
            skip_existing: Skip files already in library
            check_modifications: Check for file modifications
            batch_size: Number of files to process per batch

        Returns:
            ScanResult with scan statistics
        """
        start_time: float = time.time()
        result: ScanResult = ScanResult()

        # --- Concurrency guard (#2438) ---
        _acquired: bool = True
        _max_scans: int = 1
        try:
            _acquired, _max_scans = self.library_manager.try_acquire_scan_slot()
        except AttributeError:
            pass  # library_manager is a lightweight mock; skip guard

        if not _acquired:
            warning(
                f"Scan rejected: max_concurrent_scans limit ({_max_scans}) already reached. "
                "Retry when the active scan completes."
            )
            result.rejected = True
            return result
        # --- End concurrency guard ---

        # --- Per-directory dedup guard (#3455 / #4509) ---
        # Reserved on library_manager, not on self — see the #4509 note in
        # __init__: a fresh LibraryScanner per invocation means an instance
        # attribute here would never be shared between two overlapping scans.
        normalized = [os.path.normpath(os.path.abspath(d)) for d in directories]
        already_scanning: list[str] = []
        try:
            already_scanning = self.library_manager.try_reserve_scan_paths(normalized)
        except AttributeError:
            pass  # library_manager is a lightweight mock; skip guard

        if already_scanning:
            warning(
                f"Scan rejected: directories already being scanned: {already_scanning}"
            )
            result.rejected = True
            # #4330: this early return happens BEFORE the try/finally that
            # releases the slot, so release it here or the slot leaks
            # permanently. We must NOT release `normalized` from the shared
            # dedup set here: try_reserve_scan_paths() did not reserve them
            # for us on this rejection path (they belong to the OTHER,
            # already-running scan), so there is nothing of ours to release.
            if _acquired:
                self._release_scan_slot_safe()
            return result
        # --- End per-directory dedup guard ---

        info(f"Starting library scan of {len(directories)} directories")

        # Announce the start from HERE — after both rejection guards have passed
        # (#4602). Callers used to broadcast `library_scan_started` on entry,
        # before `rejected` could possibly be known, so a second scan request
        # that ended up 409'd had already told the UI a scan had begun; its
        # handler resets every counter, wiping the live progress of the scan that
        # was actually running. Routing it through the progress callback means
        # the frame can only be emitted once the slot is genuinely owned, and
        # fixes both emitters (manual route + auto-scanner) at once, since both
        # bridge this callback to the WebSocket.
        self._report_progress({
            'stage': 'started',
            'directories': normalized,
        })

        try:
            # #4616: establish the progress denominator BEFORE the streaming
            # pass. `files_found` climbs in lockstep with `files_processed`
            # (a file is counted as found at most `batch_size` frames before
            # it is processed), so `processed / files_found` is pinned at
            # ~100% — that was #4411, and it must not come back. A dedicated
            # counting pass gives a fixed total, making
            # `processed / total_expected` a real, monotonically increasing
            # fraction.
            #
            # #4840: that pass used to throw its results away, so the identical
            # recursive walk (including a `stat()` per entry for the
            # symlink-cycle check) ran twice — roughly doubling wall-clock for
            # discovery-bound libraries on slow storage, which is exactly the
            # network-share / USB-drive case a desktop app hits. The paths are
            # now kept and reused, so the tree is walked once.
            #
            # The cache is hard-capped rather than unbounded: #2160's streaming
            # memory bound is the reason the count pass discarded paths in the
            # first place. Past the cap the cache is dropped and the scan falls
            # back to re-walking, so memory is bounded by construction and only
            # libraries beyond the cap pay the second walk.
            total_expected: int = 0
            cached_paths: list[str] | None = []
            directories_counted: int = 0

            for directory in directories:
                if self.should_stop.is_set():
                    break
                for filepath in self.file_discovery.discover_audio_files(directory, recursive):
                    if self.should_stop.is_set():
                        break
                    total_expected += 1
                    if cached_paths is not None:
                        if len(cached_paths) >= _PATH_CACHE_LIMIT:
                            # Give up caching for this scan; stay bounded.
                            debug(
                                f"Path cache limit ({_PATH_CACHE_LIMIT}) reached — "
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
                    if total_expected % _COUNT_PROGRESS_EVERY == 0:
                        self._report_progress({
                            'stage': 'counting',
                            'directory': directory,
                            'total_found': total_expected,
                            'processed': 0,
                            # Still genuinely unknown: there is no denominator
                            # until this pass finishes.
                            'progress': None,
                        })
                directories_counted += 1

            if self.should_stop.is_set():
                return result

            def _progress_fraction() -> float | None:
                """Completed fraction, or ``None`` while indeterminate.

                Clamped to 1.0: the count pass and the scan pass are separate
                traversals, so files added between them can push `processed`
                past `total_expected`. A zero total stays indeterminate rather
                than dividing by zero.
                """
                if total_expected <= 0:
                    return None
                return min(result.files_processed / total_expected, 1.0)

            # The counting pass emits no frames, so the UI stays on the
            # indeterminate state seeded by `stage: 'started'` for its
            # duration. Every frame from here on carries a real fraction —
            # including the leading 0.0, which is a truthful "nothing
            # processed yet", not an unknown.
            self._report_progress({
                'stage': 'discovering',
                'total_expected': total_expected,
                'total_found': result.files_found,
                'processed': result.files_processed,
                'progress': _progress_fraction(),
            })

            # Discover and process audio files in streaming batches to
            # bound memory usage regardless of library size (#2160).
            # Instead of collecting all paths first, we fill batches as files
            # are discovered and process each batch immediately.
            pending_batch: list[str] = []

            def _process_batch(batch: list[str]) -> None:
                """Process a single batch and accumulate results."""
                batch_result: Any = self.batch_processor.process_file_batch(
                    batch, skip_existing, check_modifications
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
                if batch_result.added_tracks:
                    result.added_tracks.extend(batch_result.added_tracks)
                self._report_progress({
                    'stage': 'processing',
                    'processed': result.files_processed,
                    'added': result.files_added,
                    'failed': result.files_failed,
                    'total_found': result.files_found,
                    'total_expected': total_expected,
                    'progress': _progress_fraction(),
                    'current_file': batch[0] if batch else None,
                })

            def _feed(filepath: str) -> None:
                """Accumulate one discovered path, flushing on a full batch."""
                nonlocal pending_batch
                pending_batch.append(filepath)
                result.files_found += 1
                if len(pending_batch) >= batch_size:
                    _process_batch(pending_batch)
                    pending_batch = []

            if cached_paths is not None:
                # #4840: the counting pass already walked the tree, so reuse its
                # result instead of walking it again. This is the whole point of
                # the fix — one traversal, not two.
                result.directories_scanned = directories_counted
                for filepath in cached_paths:
                    if self.should_stop.is_set():
                        break
                    _feed(filepath)
                # Release the cache before the (potentially long) tail of
                # processing rather than holding it to the end of the scan.
                cached_paths = None
                self._report_progress({
                    'stage': 'discovering',
                    'total_found': result.files_found,
                    'total_expected': total_expected,
                    'processed': result.files_processed,
                    'progress': _progress_fraction(),
                })
            else:
                # Cache overflowed (library larger than _PATH_CACHE_LIMIT), so
                # fall back to the second walk. Bounded memory wins over the
                # extra I/O; see the note at the counting pass.
                for directory in directories:
                    if self.should_stop.is_set():
                        break

                    for filepath in self.file_discovery.discover_audio_files(directory, recursive):
                        if self.should_stop.is_set():
                            break
                        _feed(filepath)

                    result.directories_scanned += 1
                    self._report_progress({
                        'stage': 'discovering',
                        'directory': directory,
                        'total_found': result.files_found,
                        'total_expected': total_expected,
                        'processed': result.files_processed,
                        'progress': _progress_fraction(),
                    })

            info(f"Discovered {result.files_found} audio files")

            if self.should_stop.is_set():
                return result

            # Process remaining files that didn't fill a full batch
            if pending_batch:
                _process_batch(pending_batch)

            result.scan_time = time.time() - start_time

            info(f"Library scan completed: {result}")
            return result

        except Exception as e:
            warning(f"Library scan failed: {e}")
            result.scan_time = time.time() - start_time
            return result

        finally:
            # Release per-directory dedup guard (#3455 / #4509)
            self._release_scan_paths_safe(normalized)
            self._release_scan_slot_safe()

            # #3479: fire scan-complete callback outside the scan-slot lock
            # so the consumer (reference cloud refresh) can do its own DB I/O
            # without contending with future scans. Failures here must not
            # affect the scan result the caller sees.
            if self.on_scan_complete is not None and not result.rejected:
                try:
                    self.on_scan_complete(result)
                except Exception as cb_exc:  # noqa: BLE001
                    warning(f"on_scan_complete callback raised: {cb_exc}")

    def scan_single_directory(self, directory: str, **kwargs: Any) -> ScanResult:
        """Scan a single directory"""
        return self.scan_directories([directory], **kwargs)

    def scan_folder(self, folder_path: str, recursive: bool = True, **kwargs: Any) -> list[dict[str, Any]]:
        """
        Backward compatibility method for scanning a folder.

        Args:
            folder_path: Path to folder to scan
            recursive: Whether to scan subdirectories
            **kwargs: Additional arguments for scan

        Returns:
            List of discovered files with metadata
        """
        # Use FileDiscovery to find all audio files in the folder
        # This is compatible with the old test expectations
        files: list[dict[str, Any]] = []

        try:
            for filepath in self.file_discovery.discover_audio_files(folder_path, recursive):
                # Extract metadata for each file
                file_info: Any = self.audio_analyzer.extract_audio_info(filepath)

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

    def find_duplicates(self, directories: list[str] | None = None) -> list[list[str]]:
        """
        Find duplicate audio files based on content hash

        Args:
            directories: Specific directories to check, or None for entire library

        Returns:
            List of lists, where each inner list contains paths of duplicate files
        """
        return self.duplicate_detector.find_duplicates(directories)  # type: ignore[no-any-return]

    def _report_progress(self, progress_data: dict[str, Any]) -> None:
        """Report progress to callback if set"""
        if self.progress_callback:
            try:
                self.progress_callback(progress_data)
            except Exception as e:
                warning(f"Progress callback failed: {e}")
