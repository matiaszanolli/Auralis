# -*- coding: utf-8 -*-

"""
Batch Processor
~~~~~~~~~~~~~~

Batch processing of audio files for library scanning

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, List, Tuple

from ...utils.logging import debug, error
from ..scan_models import ScanResult


class BatchProcessor:
    """
    Processes batches of audio files

    Handles:
    - Batch processing for performance
    - Modification tracking
    - Add/update/skip logic
    - Error handling per file
    """

    def __init__(self, library_manager: Any, audio_analyzer: Any, metadata_extractor: Any) -> None:
        """
        Initialize batch processor

        Args:
            library_manager: Library manager instance
            audio_analyzer: AudioAnalyzer instance
            metadata_extractor: MetadataExtractor instance
        """
        self.library_manager = library_manager
        self.audio_analyzer = audio_analyzer
        self.metadata_extractor = metadata_extractor
        self.should_stop = False

    def stop(self) -> None:
        """Signal processor to stop"""
        self.should_stop = True

    def process_file_batch(self, file_paths: List[str],
                          skip_existing: bool,
                          check_modifications: bool) -> ScanResult:
        """
        Process a batch of audio files

        Args:
            file_paths: List of file paths to process
            skip_existing: Skip files already in library
            check_modifications: Check for file modifications

        Returns:
            ScanResult with processing statistics and added track records
        """
        result = ScanResult()

        for file_path in file_paths:
            if self.should_stop:
                break

            try:
                file_result, track_record = self.process_single_file(
                    file_path, skip_existing, check_modifications
                )

                result.files_processed += 1
                if file_result == 'added':
                    result.files_added += 1
                    if track_record:
                        result.added_tracks.append(track_record)
                elif file_result == 'updated':
                    result.files_updated += 1
                elif file_result == 'skipped':
                    result.files_skipped += 1
                else:  # failed
                    result.files_failed += 1

            except Exception as e:
                error(f"Failed to process {file_path}: {e}")
                result.files_failed += 1

        return result

    def process_single_file(self, file_path: str,
                           skip_existing: bool,
                           check_modifications: bool) -> Tuple[str, Any]:
        """
        Process a single audio file

        Args:
            file_path: Path to audio file
            skip_existing: Skip if already in library
            check_modifications: Check if file was modified

        Returns:
            Tuple of (status, track_record) where status is 'added', 'updated', 'skipped', or 'failed'
            and track_record is the Track object if newly added, None otherwise
        """
        try:
            # Check if file already exists in library
            if skip_existing:
                existing_track = self.library_manager.get_track_by_filepath(file_path)
                if existing_track:
                    if check_modifications:
                        # Check if file was modified since last scan
                        file_stat = Path(file_path).stat()
                        file_mtime = datetime.fromtimestamp(file_stat.st_mtime)

                        if existing_track.updated_at and existing_track.updated_at >= file_mtime:
                            return 'skipped', None  # File hasn't been modified
                    else:
                        return 'skipped', None  # Skip existing files

            # Extract file information
            audio_info = self.audio_analyzer.extract_audio_info(file_path)
            if not audio_info:
                return 'failed', None

            # Extract metadata and add to audio_info
            metadata = self.metadata_extractor.extract_metadata_from_file(file_path)
            if metadata:
                audio_info.metadata = metadata

            # Convert to track info format
            track_info = self.metadata_extractor.audio_info_to_track_info(audio_info)

            # Add or update track in library
            if skip_existing and self.library_manager.get_track_by_filepath(file_path):
                # Update existing track
                track = self.library_manager.update_track_by_filepath(file_path, track_info)
                return ('updated', None) if track else ('failed', None)
            else:
                # Add new track
                track = self.library_manager.add_track(track_info)
                return ('added', track) if track else ('failed', None)

        except Exception as e:
            debug(f"Error processing {file_path}: {e}")
            return 'failed', None
