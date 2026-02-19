"""
Metadata Editor
~~~~~~~~~~~~~~~

Audio file metadata editing orchestrator

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import os
from typing import Any

try:
    from mutagen import File as MutagenFile  # type: ignore[attr-defined]
    from mutagen.flac import FLAC
    from mutagen.mp4 import MP4
    from mutagen.oggvorbis import OggVorbis
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    MutagenFile = None

from ...utils.logging import debug, error, info
from .backup import BackupManager
from .models import MetadataUpdate
from .readers import MetadataReaders
from .tag_mappings import STANDARD_FIELDS, TAG_MAPPINGS, get_format_key
from .writers import MetadataWriters


class MetadataEditor:
    """
    Audio file metadata editor using mutagen

    Supports:
    - MP3 (ID3v2 tags)
    - FLAC (Vorbis comments)
    - M4A/AAC (iTunes tags)
    - OGG (Vorbis comments)
    - WAV (ID3v2 or RIFF INFO)

    Features:
    - Individual track editing
    - Batch editing
    - Backup before modification
    - Format-specific tag handling
    - Validation and error handling
    """

    # Class attributes for tag mappings
    STANDARD_FIELDS = STANDARD_FIELDS
    TAG_MAPPINGS = TAG_MAPPINGS

    def __init__(self) -> None:
        """Initialize metadata editor"""
        if not MUTAGEN_AVAILABLE:
            raise ImportError("mutagen library is required for metadata editing")

        self.readers = MetadataReaders()
        self.writers = MetadataWriters()
        self.backup_manager = BackupManager()

    def get_supported_formats(self) -> list[str]:
        """Get list of supported audio formats"""
        return ['mp3', 'flac', 'm4a', 'aac', 'ogg', 'wav']

    def get_editable_fields(self, filepath: str) -> list[str]:
        """
        Get list of editable metadata fields for a file

        Args:
            filepath: Path to audio file

        Returns:
            List of field names that can be edited
        """
        ext = os.path.splitext(filepath)[1].lower().lstrip('.')
        format_key = get_format_key(ext)
        return list(TAG_MAPPINGS.get(format_key, {}).keys())

    def read_metadata(self, filepath: str) -> dict[str, Any]:
        """
        Read all metadata from an audio file

        Args:
            filepath: Path to audio file

        Returns:
            Dictionary of metadata fields

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format not supported
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        try:
            audio_file = MutagenFile(filepath)
            if audio_file is None:
                raise ValueError(f"Unsupported or invalid audio file: {filepath}")

            metadata = {}
            ext = os.path.splitext(filepath)[1].lower().lstrip('.')

            # Determine format and read metadata
            if isinstance(audio_file, FLAC) or ext == 'flac':
                metadata = self.readers.read_flac_metadata(audio_file)
            elif isinstance(audio_file, MP4) or ext in ('m4a', 'aac', 'mp4'):
                metadata = self.readers.read_mp4_metadata(audio_file)
            elif isinstance(audio_file, OggVorbis) or ext in ('ogg', 'oga'):
                metadata = self.readers.read_ogg_metadata(audio_file)
            elif ext == 'mp3':
                metadata = self.readers.read_mp3_metadata(audio_file)
            else:
                # Generic fallback
                metadata = self.readers.read_generic_metadata(audio_file)

            debug(f"Read metadata from {filepath}: {list(metadata.keys())}")
            return metadata

        except Exception as e:
            error(f"Failed to read metadata from {filepath}: {e}")
            raise

    def write_metadata(self, filepath: str, metadata: dict[str, Any], backup: bool = True) -> bool:
        """
        Write metadata to an audio file

        Args:
            filepath: Path to audio file
            metadata: Dictionary of metadata fields to update
            backup: Create backup before modification

        Returns:
            True if successful, False otherwise

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format not supported
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        # Create backup if requested
        if backup:
            self.backup_manager.create_backup(filepath)

        try:
            audio_file = MutagenFile(filepath)
            if audio_file is None:
                raise ValueError(f"Unsupported or invalid audio file: {filepath}")

            ext = os.path.splitext(filepath)[1].lower().lstrip('.')

            # Write format-specific metadata
            if isinstance(audio_file, FLAC) or ext == 'flac':
                self.writers.write_flac_metadata(audio_file, metadata)
            elif isinstance(audio_file, MP4) or ext in ('m4a', 'aac', 'mp4'):
                self.writers.write_mp4_metadata(audio_file, metadata)
            elif isinstance(audio_file, OggVorbis) or ext in ('ogg', 'oga'):
                self.writers.write_ogg_metadata(audio_file, metadata)
            elif ext == 'mp3':
                self.writers.write_mp3_metadata(audio_file, metadata)
            else:
                # Generic fallback
                self.writers.write_generic_metadata(audio_file, metadata)

            # Save changes
            audio_file.save()
            info(f"Updated metadata for {filepath}")
            return True

        except Exception as e:
            error(f"Failed to write metadata to {filepath}: {e}")
            # Restore backup if available
            if backup:
                self.backup_manager.restore_backup(filepath)
            raise

    def batch_update(self, updates: list[MetadataUpdate]) -> dict[str, Any]:
        """
        Update metadata for multiple tracks atomically.

        When backup=True (the default), all files are backed up before any
        write is attempted.  If any write fails, every file that was already
        modified is restored from its backup so the collection is left in a
        consistent state.  Backups are deleted only on a fully-successful run.

        When backup=False the batch is best-effort (no rollback possible).

        Args:
            updates: List of MetadataUpdate objects

        Returns:
            Dictionary with:
            - total (int): updates attempted
            - successful (int): updates that committed
            - failed (int): updates that did not commit
            - results (list): per-file {track_id, filepath, success, [error], [updates]}
            - rolled_back (bool): True when a failure triggered a full rollback
        """
        if not updates:
            return {
                'total': 0, 'successful': 0, 'failed': 0,
                'results': [], 'rolled_back': False,
            }

        # Guard: mixing backup=True and backup=False entries in a single batch
        # leads to an inconsistent state where backup=False files are marked as
        # rolled_back=True in the result (and skipped by the router's DB update)
        # even though their on-disk write is NOT reverted (#2460).
        backup_flags = {u.backup for u in updates}
        if len(backup_flags) > 1:
            raise ValueError(
                "All updates in a batch must share the same backup setting. "
                "Got mixed backup=True and backup=False entries."
            )

        total = len(updates)

        # Phase 1 — Validate all files exist before touching any.
        for update in updates:
            if not os.path.exists(update.filepath):
                return {
                    'total': total,
                    'successful': 0,
                    'failed': total,
                    'results': [
                        {
                            'track_id': u.track_id,
                            'filepath': u.filepath,
                            'success': False,
                            'error': (
                                f"File not found: {update.filepath}"
                                if u.filepath == update.filepath
                                else f"Aborted: {update.filepath} not found"
                            ),
                        }
                        for u in updates
                    ],
                    'rolled_back': False,
                }

        # Phase 2 — Back up every file (fail-fast: any backup failure aborts all).
        backed_up_paths: set[str] = set()
        if any(u.backup for u in updates):
            for update in updates:
                if update.backup:
                    if not self.backup_manager.create_backup(update.filepath):
                        for path in backed_up_paths:
                            self.backup_manager.cleanup_backup(path)
                        return {
                            'total': total,
                            'successful': 0,
                            'failed': total,
                            'results': [
                                {
                                    'track_id': u.track_id,
                                    'filepath': u.filepath,
                                    'success': False,
                                    'error': (
                                        f"Failed to create backup: {update.filepath}"
                                        if u.filepath == update.filepath
                                        else f"Aborted: backup failed for {update.filepath}"
                                    ),
                                }
                                for u in updates
                            ],
                            'rolled_back': False,
                        }
                    backed_up_paths.add(update.filepath)

        # Phase 3 — Apply all updates (skip per-file backup; batch backup done above).
        per_file_results: list[dict[str, Any]] = []
        applied_paths: list[str] = []
        any_failed = False

        for update in updates:
            try:
                self.write_metadata(update.filepath, update.updates, backup=False)
                applied_paths.append(update.filepath)
                per_file_results.append({
                    'track_id': update.track_id,
                    'filepath': update.filepath,
                    'success': True,
                    'updates': update.updates,
                })
            except Exception as e:
                any_failed = True
                per_file_results.append({
                    'track_id': update.track_id,
                    'filepath': update.filepath,
                    'success': False,
                    'error': str(e),
                })

        # Phase 4 — Roll back all applied files when the batch was backed up and any failed.
        rolled_back = False
        if any_failed and backed_up_paths:
            for filepath in applied_paths:
                if filepath in backed_up_paths:
                    self.backup_manager.restore_backup(filepath)
            rolled_back = True
            # Mark previously-succeeded items as rolled back.
            per_file_results = [
                {**r, 'success': False, 'rolled_back': True} if r.get('success') else r
                for r in per_file_results
            ]

        # Phase 5 — Clean up backups on a fully successful run.
        if not any_failed:
            for path in backed_up_paths:
                self.backup_manager.cleanup_backup(path)

        successful = sum(1 for r in per_file_results if r.get('success'))
        failed = total - successful

        info(f"Batch update: {successful}/{total} successful, rolled_back={rolled_back}")
        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'results': per_file_results,
            'rolled_back': rolled_back,
        }

    def _create_backup(self, filepath: str) -> bool:
        """
        Create a backup of an audio file before modification

        Args:
            filepath: Path to audio file

        Returns:
            True if backup successful, False otherwise
        """
        return BackupManager.create_backup(filepath)

    def _restore_backup(self, filepath: str) -> bool:
        """
        Restore an audio file from backup

        Args:
            filepath: Path to audio file to restore

        Returns:
            True if restore successful, False otherwise
        """
        return BackupManager.restore_backup(filepath)
