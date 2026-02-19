"""
Library Scanner
~~~~~~~~~~~~~~

Main scanner orchestrator

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import time
from typing import Any
from collections.abc import Callable

from ...utils.logging import info, warning
from ..scan_models import ScanResult
from .audio_analyzer import AudioAnalyzer
from .batch_processor import BatchProcessor
from .config import DEFAULT_BATCH_SIZE
from .duplicate_detector import DuplicateDetector
from .file_discovery import FileDiscovery
from .metadata_extractor import MetadataExtractor


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

    def __init__(self, library_manager: Any, fingerprint_queue: Any | None = None) -> None:
        """
        Initialize scanner with library manager

        Args:
            library_manager: Library manager instance
            fingerprint_queue: Optional FingerprintExtractionQueue for background fingerprinting
        """
        self.library_manager: Any = library_manager
        self.fingerprint_queue: Any | None = fingerprint_queue
        self.progress_callback: Callable[[dict[str, Any]], None] | None = None
        self.should_stop: bool = False

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
            self.audio_analyzer
        )

    def set_progress_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Set callback for progress updates"""
        self.progress_callback = callback

    def stop_scan(self) -> None:
        """Signal scanner to stop"""
        self.should_stop = True
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

        info(f"Starting library scan of {len(directories)} directories")

        try:
            # Discover all audio files
            all_files: list[str] = []
            for directory in directories:
                if self.should_stop:
                    break

                files: list[str] = list(self.file_discovery.discover_audio_files(directory, recursive))
                all_files.extend(files)
                result.directories_scanned += 1

                self._report_progress({
                    'stage': 'discovering',
                    'directory': directory,
                    'files_found': len(files),
                    'total_found': len(all_files)
                })

            result.files_found = len(all_files)
            info(f"Discovered {result.files_found} audio files")

            if self.should_stop:
                return result

            # Process files in batches for better performance
            for i in range(0, len(all_files), batch_size):
                if self.should_stop:
                    break  # type: ignore[unreachable]

                batch: list[str] = all_files[i:i + batch_size]
                batch_result: Any = self.batch_processor.process_file_batch(
                    batch, skip_existing, check_modifications
                )

                result.files_processed += batch_result.files_processed
                result.files_added += batch_result.files_added
                result.files_updated += batch_result.files_updated
                result.files_skipped += batch_result.files_skipped
                result.files_failed += batch_result.files_failed

                # Accumulate added tracks so the async caller can enqueue
                # fingerprints in the event loop after to_thread() returns.
                # asyncio.create_task() cannot be called from this worker
                # thread — it raises RuntimeError: no running event loop (#2382).
                if batch_result.added_tracks:
                    result.added_tracks.extend(batch_result.added_tracks)

                # Report progress
                progress: float = (i + len(batch)) / len(all_files)
                self._report_progress({
                    'stage': 'processing',
                    'progress': progress,
                    'processed': result.files_processed,
                    'added': result.files_added,
                    'failed': result.files_failed
                })

            result.scan_time = time.time() - start_time

            # Update library statistics
            self._update_library_stats(result)

            info(f"Library scan completed: {result}")
            return result

        except Exception as e:
            warning(f"Library scan failed: {e}")
            result.scan_time = time.time() - start_time
            return result

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

    def _update_library_stats(self, scan_result: ScanResult) -> None:
        """Update library statistics after scan"""
        try:
            # This would update the LibraryStats table
            # For now, just log the results
            info(f"Scan completed: {scan_result}")
        except Exception as e:
            warning(f"Failed to update library stats: {e}")

    def _report_progress(self, progress_data: dict[str, Any]) -> None:
        """Report progress to callback if set"""
        if self.progress_callback:
            try:
                self.progress_callback(progress_data)
            except Exception as e:
                warning(f"Progress callback failed: {e}")

    async def _enqueue_fingerprints(self, track_records: list[Any]) -> None:
        """
        Enqueue fingerprints for newly added tracks

        Args:
            track_records: List of Track objects that need fingerprinting
        """
        if not self.fingerprint_queue or not track_records:
            return

        enqueued_count: int = 0
        for track in track_records:
            try:
                success: bool = await self.fingerprint_queue.enqueue(
                    track_id=track.id,
                    filepath=track.filepath,
                    priority=0  # Normal priority for scan operations
                )
                if success:
                    enqueued_count += 1
            except Exception as e:
                warning(f"Failed to enqueue fingerprint for track {track.id}: {e}")

        if enqueued_count > 0:
            info(f"Enqueued {enqueued_count} fingerprints for extraction")
            self._report_progress({
                'stage': 'fingerprinting',
                'fingerprints_enqueued': enqueued_count
            })
