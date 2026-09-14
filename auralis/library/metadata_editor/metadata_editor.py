"""
Metadata Editor
~~~~~~~~~~~~~~~

Audio file metadata editing orchestrator

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pathlib import Path
from typing import Any

try:
    from mutagen import File as MutagenFile
    from mutagen.flac import FLAC
    from mutagen.mp4 import MP4
    from mutagen.oggopus import OggOpus
    from mutagen.oggvorbis import OggVorbis
    from mutagen.wave import WAVE
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    MutagenFile = None

from ...utils.logging import debug, error, info
from .backup import BackupManager, lock_files
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
        ext = Path(filepath).suffix.lower().lstrip('.')
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
        if not Path(filepath).exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        try:
            audio_file = MutagenFile(filepath)
            if audio_file is None:
                raise ValueError(f"Unsupported or invalid audio file: {filepath}")

            metadata = {}
            ext = Path(filepath).suffix.lower().lstrip('.')

            # Determine format and read metadata
            if isinstance(audio_file, FLAC) or ext == 'flac':
                metadata = self.readers.read_flac_metadata(audio_file)
            elif isinstance(audio_file, MP4) or ext in ('m4a', 'aac', 'mp4'):
                metadata = self.readers.read_mp4_metadata(audio_file)
            elif isinstance(audio_file, OggOpus) or ext == 'opus':
                # OPUS uses Vorbis comments, same as OggVorbis (#4130).
                metadata = self.readers.read_ogg_metadata(audio_file)
            elif isinstance(audio_file, OggVorbis) or ext in ('ogg', 'oga'):
                metadata = self.readers.read_ogg_metadata(audio_file)
            elif isinstance(audio_file, WAVE) or ext == 'wav':
                # WAV stores tags as embedded ID3 frames (#4130).
                metadata = self.readers.read_mp3_metadata(audio_file)
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
        if not Path(filepath).exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        # #5307: serialize every write to this file — single-track and batch
        # alike — so two requests can neither interleave saves nor race on the
        # backup. Re-entrant, so batch_update can call in while holding it.
        with lock_files([filepath]):
            backup_path: str | None = None
            if backup:
                backup_path = self.backup_manager.create_backup(filepath)
                if backup_path is None:
                    # The caller asked for a safety net; writing without one is
                    # how a failed save used to clobber the file (#5307).
                    raise OSError(f"Failed to create backup of {filepath}; metadata not written")

            try:
                audio_file = MutagenFile(filepath)
                if audio_file is None:
                    raise ValueError(f"Unsupported or invalid audio file: {filepath}")

                ext = Path(filepath).suffix.lower().lstrip('.')

                # Write format-specific metadata
                if isinstance(audio_file, FLAC) or ext == 'flac':
                    self.writers.write_flac_metadata(audio_file, metadata)
                elif isinstance(audio_file, MP4) or ext in ('m4a', 'aac', 'mp4'):
                    self.writers.write_mp4_metadata(audio_file, metadata)
                elif isinstance(audio_file, OggOpus) or ext == 'opus':
                    # OPUS uses Vorbis comments, same as OggVorbis (#4130).
                    self.writers.write_ogg_metadata(audio_file, metadata)
                elif isinstance(audio_file, OggVorbis) or ext in ('ogg', 'oga'):
                    self.writers.write_ogg_metadata(audio_file, metadata)
                elif isinstance(audio_file, WAVE) or ext == 'wav':
                    # WAV stores tags as embedded ID3 frames (#4130).
                    self.writers.write_mp3_metadata(audio_file, metadata)
                elif ext == 'mp3':
                    self.writers.write_mp3_metadata(audio_file, metadata)
                else:
                    # Generic fallback
                    self.writers.write_generic_metadata(audio_file, metadata)

                # Save changes
                audio_file.save()

            except Exception as e:
                error(f"Failed to write metadata to {filepath}: {e}")
                if backup_path is not None:
                    self.backup_manager.restore_backup(filepath, backup_path)
                raise

            if backup_path is not None:
                self.backup_manager.cleanup_backup(backup_path)
            info(f"Updated metadata for {filepath}")
            return True

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
            - results (list): per-file {track_id, success, [error], [updates]}
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
            if not Path(update.filepath).exists():
                return {
                    'total': total,
                    'successful': 0,
                    'failed': total,
                    'results': [
                        {
                            'track_id': u.track_id,
                            'success': False,
                            'error': (
                                "File not found"
                                if u.filepath == update.filepath
                                else "Aborted: another batch file was not found"
                            ),
                        }
                        for u in updates
                    ],
                    'rolled_back': False,
                }

        # #5307: hold every file's lock across backup → apply → rollback so a
        # concurrent single-track write cannot interleave with the batch.
        with lock_files(u.filepath for u in updates):
            # Phase 2 — Back up every file (fail-fast: any backup failure aborts
            # all). Maps each filepath to its own unique backup copy.
            backups: dict[str, str] = {}
            for update in updates:
                if not update.backup or update.filepath in backups:
                    continue
                backup_path = self.backup_manager.create_backup(update.filepath)
                if backup_path is None:
                    for path in backups.values():
                        self.backup_manager.cleanup_backup(path)
                    return {
                        'total': total,
                        'successful': 0,
                        'failed': total,
                        'results': [
                            {
                                'track_id': u.track_id,
                                'success': False,
                                'error': (
                                    "Failed to create backup"
                                    if u.filepath == update.filepath
                                    else "Aborted: another batch backup failed"
                                ),
                            }
                            for u in updates
                        ],
                        'rolled_back': False,
                    }
                backups[update.filepath] = backup_path

            # Phase 3 — Apply all updates (skip per-file backup; batch backup done above).
            per_file_results: list[dict[str, Any]] = []
            any_failed = False

            for update in updates:
                try:
                    self.write_metadata(update.filepath, update.updates, backup=False)
                    per_file_results.append({
                        'track_id': update.track_id,
                        'success': True,
                        'updates': update.updates,
                    })
                except Exception as e:
                    any_failed = True
                    per_file_results.append({
                        'track_id': update.track_id,
                        'success': False,
                        'error': str(e).replace(update.filepath, Path(update.filepath).name),
                    })

            # Phase 4 — On any failure, restore EVERY backed-up file — including
            # the one whose save raised, which may have been left half-written
            # (write_metadata restores in that case too, #5307). Otherwise
            # delete the backups; either way none is left behind.
            rolled_back = False
            if any_failed and backups:
                for filepath, backup_path in backups.items():
                    self.backup_manager.restore_backup(filepath, backup_path)
                rolled_back = True
                # Mark previously-succeeded items as rolled back.
                per_file_results = [
                    {**r, 'success': False, 'rolled_back': True} if r.get('success') else r
                    for r in per_file_results
                ]
            else:
                for backup_path in backups.values():
                    self.backup_manager.cleanup_backup(backup_path)

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
