"""
Batch Processor
~~~~~~~~~~~~~~

Batch processing of audio files for library scanning

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...utils.logging import error, warning
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

    def __init__(self, library_database: Any, audio_analyzer: Any, metadata_extractor: Any) -> None:
        """
        Initialize batch processor

        Args:
            library_database: Library manager instance
            audio_analyzer: AudioAnalyzer instance
            metadata_extractor: MetadataExtractor instance
        """
        self.library_database = library_database
        self.audio_analyzer = audio_analyzer
        self.metadata_extractor = metadata_extractor
        self.should_stop = False

    def stop(self) -> None:
        """Signal processor to stop"""
        self.should_stop = True

    def process_file_batch(self, file_paths: list[str],
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
                file_result, track_record, reason = self.process_single_file(
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
                    # #4841: keep the path and reason, not just a tally.
                    result.record_failure(file_path, reason or 'Unknown error')

            except Exception as e:
                error(f"Failed to process {file_path}: {e}")
                result.record_failure(file_path, str(e) or e.__class__.__name__)

        return result

    def process_single_file(self, file_path: str,
                           skip_existing: bool,
                           check_modifications: bool) -> tuple[str, Any, str | None]:
        """
        Process a single audio file

        Args:
            file_path: Path to audio file
            skip_existing: Skip if already in library
            check_modifications: Check if file was modified

        Returns:
            Tuple of (status, track_record, reason) where status is 'added',
            'updated', 'skipped', or 'failed'; track_record is the Track object
            if newly added, None otherwise; and reason explains a 'failed'
            status and is None for every other status (#4841 — the caller used
            to receive a bare 'failed' with nothing to tell the user).
        """
        try:
            # Check if file already exists in library (query once, reuse below)
            # #4619: repository access, not the deprecated LibraryManager
            # facade — the scanner is handed a LibraryDatabase now, which has
            # `.tracks` but none of the facade's convenience wrappers.
            tracks_repo = self.library_database.tracks
            existing_track = tracks_repo.get_by_path(file_path) if skip_existing else None
            if existing_track:
                if check_modifications:
                    # Check if file was modified since last scan
                    file_stat = Path(file_path).stat()
                    file_mtime = datetime.fromtimestamp(file_stat.st_mtime, tz=timezone.utc)

                    # `updated_at` round-trips through SQLite as a naive datetime
                    # holding UTC wall-clock numbers (#4881) — reattach tzinfo
                    # so both sides compare on the same clock basis.
                    updated_at = existing_track.updated_at
                    if updated_at and updated_at.tzinfo is None:
                        updated_at = updated_at.replace(tzinfo=timezone.utc)
                    if updated_at and updated_at >= file_mtime:
                        return 'skipped', None, None  # File hasn't been modified
                else:
                    return 'skipped', None, None  # Skip existing files

            # Extract file information
            audio_info = self.audio_analyzer.extract_audio_info(file_path)
            if not audio_info:
                # The most common failure by far: unreadable or corrupt file,
                # or a format the analyzer cannot decode.
                return 'failed', None, 'Could not read audio information (unreadable or unsupported file)'

            # Extract metadata and add to audio_info
            metadata = self.metadata_extractor.extract_metadata_from_file(file_path)
            if metadata:
                audio_info.metadata = metadata

            # Convert to track info format
            track_info = self.metadata_extractor.audio_info_to_track_info(audio_info)

            # Add or update track in library
            if existing_track:
                # Update existing track (reuses query from above)
                track = tracks_repo.update_by_filepath(file_path, track_info)
                if track:
                    return 'updated', None, None
                return 'failed', None, 'Database update failed'
            else:
                # Add new track
                track = tracks_repo.add(track_info)
                if track:
                    return 'added', track, None
                return 'failed', None, 'Database insert failed'

        except Exception as e:
            # #4841: warning, not debug. This is the more common of the two
            # failure sites, and debug is not surfaced by default logging
            # configs — so the one failure a user was most likely to hit was
            # also the one they were least likely to see.
            warning(f"Error processing {file_path}: {e}")
            return 'failed', None, str(e) or e.__class__.__name__
