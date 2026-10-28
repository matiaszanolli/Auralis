"""
Batch Processor
~~~~~~~~~~~~~~

Batch processing of audio files for library scanning

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from pathlib import Path
from typing import Any

from ...utils.logging import error, warning
from ..repositories.track_repository_mutation import MTIME_TOLERANCE_SEC
from ..scan_models import ScannedTrackRef, ScanResult


class BatchProcessor:
    """
    Processes batches of audio files

    Handles:
    - Batch processing for performance
    - Modification tracking
    - Add/update/skip logic
    - Error handling per file
    """

    def __init__(self, library_database: Any, audio_analyzer: Any, metadata_extractor: Any,
                 should_stop: threading.Event | None = None) -> None:
        """
        Initialize batch processor

        Args:
            library_database: LibraryDatabase instance
            audio_analyzer: AudioAnalyzer instance
            metadata_extractor: MetadataExtractor instance
            should_stop: Cancellation Event shared with the owning scanner; a
                private one when omitted (#6100)
        """
        self.library_database = library_database
        self.audio_analyzer = audio_analyzer
        self.metadata_extractor = metadata_extractor
        self.should_stop = should_stop if should_stop is not None else threading.Event()

    def stop(self) -> None:
        """Signal processor to stop"""
        self.should_stop.set()

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
            if self.should_stop.is_set():
                break

            try:
                file_result, track_record, reason = self.process_single_file(
                    file_path, skip_existing, check_modifications
                )

                result.files_processed += 1
                if file_result == 'added':
                    result.files_added += 1
                    if track_record:
                        result.added_tracks.append(ScannedTrackRef(track_record.id))
                elif file_result == 'updated':
                    result.files_updated += 1
                    if track_record:
                        result.updated_tracks.append(ScannedTrackRef(track_record.id))
                elif file_result == 'skipped':
                    result.files_skipped += 1
                else:  # failed
                    # #4841: keep the path and reason, not just a tally.
                    result.record_failure(file_path, reason or 'Unknown error')

            except Exception as e:
                error(f"Failed to process {file_path}: {e}")
                result.record_failure(file_path, str(e) or e.__class__.__name__)

        return result

    @staticmethod
    def _skip_existing_track(
        existing_track: Any, file_path: str, check_modifications: bool
    ) -> bool:
        """True when a file already in the library needs no re-scan."""
        if not check_modifications:
            return True  # Skip existing files

        # #5574: compare against the SCANNER's watermark
        # (tracks.file_mtime, written on every add/update), not
        # tracks.updated_at — the latter carries an `onupdate` bump from every
        # repository write (record_play, set_favorite, fingerprint-status
        # updates), so a file edited after its last scan but played afterwards
        # was skipped forever. A NULL watermark (pre-v22 rows) means
        # "unknown": proceed, so the row is refreshed exactly once and the
        # watermark takes over. Epoch seconds on both sides — no naive-datetime
        # tz hazards (#4881).
        scanner_watermark = existing_track.file_mtime
        if scanner_watermark is None:
            return False
        stat = Path(file_path).stat()
        # Equality, not <=: a replaced file restored with an OLDER mtime (backup
        # restore, `cp -p`, `rsync -t`, an earlier master swapped back in) is
        # just as changed as a newer one (#5748). The size catches a rewrite
        # that kept the mtime; a NULL stored size means "unknown" and defers to
        # the mtime alone.
        if abs(stat.st_mtime - scanner_watermark) > MTIME_TOLERANCE_SEC:
            return False
        stored_size = getattr(existing_track, 'filesize', None)
        return stored_size is None or stored_size == stat.st_size

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
            if newly added or updated (#5719), None otherwise; and reason explains a 'failed'
            status and is None for every other status (#4841 — the caller used
            to receive a bare 'failed' with nothing to tell the user).
        """
        try:
            # Names that are not valid UTF-8 (old latin-1 rips, media from other
            # locales) reach us as surrogate escapes and fail at the first DB
            # bind with an opaque codec error; say what is wrong instead (#5749).
            try:
                file_path.encode('utf-8')
            except UnicodeEncodeError:
                return 'failed', None, 'File name is not valid UTF-8; rename the file to import it'

            # Check if file already exists in library (query once, reuse below)
            # Repository access: the scanner is handed a LibraryDatabase,
            # which has `.tracks` but no convenience wrappers.
            tracks_repo = self.library_database.tracks
            existing_track = tracks_repo.get_by_path(file_path) if skip_existing else None
            if existing_track and self._skip_existing_track(
                existing_track, file_path, check_modifications
            ):
                return 'skipped', None, None

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

            # #5574: stamp the scanner's change-detection watermark (and the
            # file size as a cheap secondary signal) onto the row so the next
            # rescan compares against THIS sync, not against updated_at.
            # Tolerates a vanished file: the extraction failure above already
            # reports the real reason.
            try:
                track_info['file_mtime'] = Path(file_path).stat().st_mtime
                track_info.setdefault('filesize', Path(file_path).stat().st_size)
            except OSError:
                pass

            # Add or update track in library
            if existing_track:
                # Update existing track (reuses query from above)
                track = tracks_repo.update_by_filepath(file_path, track_info)
                if track:
                    return 'updated', track, None
                return 'failed', None, 'Database update failed'
            if skip_existing:
                # A path new to the library may be a moved/renamed file: keep
                # that row (id, playlists, favorite, play count, fingerprint)
                # instead of adding a twin the post-scan prune then orphans (#5880).
                moved = tracks_repo.relocate_missing_track(
                    file_path, track_info.get('filesize'), track_info.get('duration')
                )
                if moved:
                    return 'updated', tracks_repo.update_by_filepath(file_path, track_info) or moved, None
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
