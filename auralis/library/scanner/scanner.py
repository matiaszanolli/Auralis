"""
Library Scanner
~~~~~~~~~~~~~~

Main scanner orchestrator

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
import time
from typing import Any
from collections.abc import Callable

from ...utils.logging import info, warning
from ..scan_models import ScanResult
from ..scan_paths import scan_roots
from .audio_analyzer import AudioAnalyzer
from .batch_processor import BatchProcessor
from .config import DEFAULT_BATCH_SIZE
from .file_discovery import FileDiscovery
from .metadata_extractor import MetadataExtractor
from .scan_stages import (
    BatchFeeder,
    claim_scan,
    count_audio_files,
    feed_from_walk,
    preview_folder,
)


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
    - Progress tracking
    - Intelligent file filtering
    """

    def __init__(self, library_database: Any) -> None:
        """
        Initialize scanner with the library database

        This scanner does NOT enqueue fingerprints. #2382 moved that to the
        caller, after `asyncio.to_thread(scan_directories)` returns, because
        `scan_directories` is fully synchronous and `asyncio.create_task` from
        its thread raised `RuntimeError: no running event loop`. The
        `fingerprint_queue` parameter this used to accept went with the dead
        `_enqueue_fingerprints` it fed (#4648) — it was being passed in and
        silently ignored. See `routers/library_scan.py` (which imports the
        enqueue from `library_scan_events.py`) and
        `LibraryAutoScanner._do_scan` ->
        `auto_scan_events.enqueue_added_for_fingerprinting` for the enqueue
        that actually runs.

        Args:
            library_database: LibraryDatabase instance
        """
        self.library_database: Any = library_database
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

        # Per-directory deduplication (#3455) lives on library_database, not
        # here — see LibraryDatabase.try_reserve_scan_paths()/#4509. Every
        # caller (LibraryAutoScanner._do_scan, routers/library_scan.py)
        # constructs a fresh LibraryScanner per invocation, so an instance
        # attribute here would never be shared between two overlapping scans.

        # Initialize components
        self.file_discovery: Any = FileDiscovery()
        self.audio_analyzer: Any = AudioAnalyzer()
        self.metadata_extractor: Any = MetadataExtractor()
        self.batch_processor: Any = BatchProcessor(
            library_database,
            self.audio_analyzer,
            self.metadata_extractor
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

        directories = scan_roots(directories, recursive)  # #6097
        normalized = claim_scan(self.library_database, directories, result)
        if normalized is None:
            return result

        info(f"Starting library scan of {len(directories)} directories")

        # Announce the start from HERE — after both rejection guards have passed
        # (#4602). Callers used to broadcast `library_scan_started` on entry,
        # before `rejected` was known, so a 409'd second request had already
        # told the UI a scan began; its handler resets every counter, wiping the
        # live progress of the scan that was actually running. Emitting through
        # the progress callback fixes both emitters (manual route + auto-scanner)
        # at once, since both bridge it to the WebSocket.
        self._report_progress({
            'stage': 'started',
            'directories': normalized,
        })

        try:
            census = count_audio_files(
                self.file_discovery,
                directories,
                recursive,
                self.should_stop,
                self._report_progress,
                cache_limit=_PATH_CACHE_LIMIT,
                progress_every=_COUNT_PROGRESS_EVERY,
            )
            cached_paths = census.cached_paths

            if self.should_stop.is_set():
                return result

            feeder = BatchFeeder(
                self.batch_processor,
                result,
                self._report_progress,
                total_expected=census.total_expected,
                batch_size=batch_size,
                skip_existing=skip_existing,
                check_modifications=check_modifications,
            )

            # The counting pass emits no frames, so the UI stays on the
            # indeterminate state seeded by `stage: 'started'` for its
            # duration. Every frame from here on carries a real fraction —
            # including the leading 0.0, which is a truthful "nothing
            # processed yet", not an unknown.
            self._report_progress({
                'stage': 'discovering',
                'total_expected': census.total_expected,
                'total_found': result.files_found,
                'processed': result.files_processed,
                'progress': feeder.progress_fraction(),
            })

            # Discover and process audio files in streaming batches to
            # bound memory usage regardless of library size (#2160).
            # Instead of collecting all paths first, we fill batches as files
            # are discovered and process each batch immediately.
            if cached_paths is not None:
                # #4840: the counting pass already walked the tree, so reuse its
                # result instead of walking it again. This is the whole point of
                # the fix — one traversal, not two.
                result.directories_scanned = census.directories_counted
                for filepath in cached_paths:
                    if self.should_stop.is_set():
                        break
                    feeder.feed(filepath)
                # Release the cache before the (potentially long) tail of
                # processing rather than holding it to the end of the scan.
                cached_paths = None
                self._report_progress({
                    'stage': 'discovering',
                    'total_found': result.files_found,
                    'total_expected': census.total_expected,
                    'processed': result.files_processed,
                    'progress': feeder.progress_fraction(),
                })
            else:
                feed_from_walk(
                    self.file_discovery, feeder, result, directories, recursive,
                    self.should_stop, self._report_progress,
                )

            info(f"Discovered {result.files_found} audio files")

            if self.should_stop.is_set():
                return result

            # Process remaining files that didn't fill a full batch
            feeder.flush()

            result.scan_time = time.time() - start_time

            info(f"Library scan completed: {result}")
            return result

        except Exception as e:
            warning(f"Library scan failed: {e}")
            result.scan_time = time.time() - start_time
            return result

        finally:
            # Release per-directory dedup guard (#3455 / #4509)
            self.library_database.release_scan_paths(normalized)
            self.library_database.release_scan_slot()

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
        """Convenience wrapper: scan_directories() for exactly one directory."""
        return self.scan_directories([directory], **kwargs)

    def scan_folder(self, folder_path: str, recursive: bool = True, **kwargs: Any) -> list[dict[str, Any]]:
        """
        Discover audio files under a folder and return their metadata directly.

        Unlike scan_directories()/scan_single_directory(), this performs no
        database writes — it's a read-only preview of what a scan would find,
        used today by the scanner's own test suite. Has no production caller
        as of #4973; kept as a documented convenience method rather than
        deleted, since it does genuinely distinct work (discovery + metadata,
        no persistence) rather than merely forwarding to scan_directories().

        Args:
            folder_path: Path to folder to scan
            recursive: Whether to scan subdirectories
            **kwargs: Additional arguments for scan

        Returns:
            List of discovered files with metadata
        """
        return preview_folder(self.file_discovery, self.audio_analyzer, folder_path, recursive)

    def _report_progress(self, progress_data: dict[str, Any]) -> None:
        """Report progress to callback if set"""
        if self.progress_callback:
            try:
                self.progress_callback(progress_data)
            except Exception as e:
                warning(f"Progress callback failed: {e}")
