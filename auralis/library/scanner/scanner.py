# -*- coding: utf-8 -*-

"""
Library Scanner
~~~~~~~~~~~~~~

Main scanner orchestrator

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import time
from typing import List, Dict, Optional, Callable

from ...utils.logging import info, warning
from ..scan_models import ScanResult
from .config import DEFAULT_BATCH_SIZE
from .file_discovery import FileDiscovery
from .audio_analyzer import AudioAnalyzer
from .metadata_extractor import MetadataExtractor
from .batch_processor import BatchProcessor
from .duplicate_detector import DuplicateDetector


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

    def __init__(self, library_manager):
        """Initialize scanner with library manager"""
        self.library_manager = library_manager
        self.progress_callback: Optional[Callable] = None
        self.should_stop = False

        # Initialize components
        self.file_discovery = FileDiscovery()
        self.audio_analyzer = AudioAnalyzer()
        self.metadata_extractor = MetadataExtractor()
        self.batch_processor = BatchProcessor(
            library_manager,
            self.audio_analyzer,
            self.metadata_extractor
        )
        self.duplicate_detector = DuplicateDetector(
            self.file_discovery,
            self.audio_analyzer
        )

    def set_progress_callback(self, callback: Callable[[Dict], None]):
        """Set callback for progress updates"""
        self.progress_callback = callback

    def stop_scan(self):
        """Signal scanner to stop"""
        self.should_stop = True
        self.file_discovery.stop()
        self.batch_processor.stop()

    def scan_directories(self, directories: List[str],
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
        start_time = time.time()
        result = ScanResult()

        info(f"Starting library scan of {len(directories)} directories")

        try:
            # Discover all audio files
            all_files = []
            for directory in directories:
                if self.should_stop:
                    break

                files = list(self.file_discovery.discover_audio_files(directory, recursive))
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
                    break

                batch = all_files[i:i + batch_size]
                batch_result = self.batch_processor.process_file_batch(
                    batch, skip_existing, check_modifications
                )

                result.files_processed += batch_result.files_processed
                result.files_added += batch_result.files_added
                result.files_updated += batch_result.files_updated
                result.files_skipped += batch_result.files_skipped
                result.files_failed += batch_result.files_failed

                # Report progress
                progress = (i + len(batch)) / len(all_files)
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

    def scan_single_directory(self, directory: str, **kwargs) -> ScanResult:
        """Scan a single directory"""
        return self.scan_directories([directory], **kwargs)

    def find_duplicates(self, directories: List[str] = None) -> List[List[str]]:
        """
        Find duplicate audio files based on content hash

        Args:
            directories: Specific directories to check, or None for entire library

        Returns:
            List of lists, where each inner list contains paths of duplicate files
        """
        return self.duplicate_detector.find_duplicates(directories)

    def _update_library_stats(self, scan_result: ScanResult):
        """Update library statistics after scan"""
        try:
            # This would update the LibraryStats table
            # For now, just log the results
            info(f"Scan completed: {scan_result}")
        except Exception as e:
            warning(f"Failed to update library stats: {e}")

    def _report_progress(self, progress_data: Dict):
        """Report progress to callback if set"""
        if self.progress_callback:
            try:
                self.progress_callback(progress_data)
            except Exception as e:
                warning(f"Progress callback failed: {e}")
