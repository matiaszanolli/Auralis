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
    from mutagen.asf import ASF
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
from .errors import open_audio_file
from .batch import BatchUpdateMixin
from .readers import MetadataReaders
from .tag_mappings import STANDARD_FIELDS, TAG_MAPPINGS, get_format_key
from .writers import MetadataWriters


class MetadataEditor(BatchUpdateMixin):
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
        return ['mp3', 'flac', 'm4a', 'aac', 'ogg', 'wav', 'wma']

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
            UnreadableAudioFileError: If mutagen cannot identify or parse the file
        """
        if not Path(filepath).exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        try:
            audio_file = open_audio_file(MutagenFile, filepath)

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
            elif isinstance(audio_file, ASF) or ext == 'wma':
                # Real ASF attribute names (#5536); the generic fallthrough
                # lowercase-matched raw keys and missed Author/WM/* fields.
                metadata = self.readers.read_asf_metadata(audio_file)
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
            UnreadableAudioFileError: If mutagen cannot identify or parse the file
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
                audio_file = open_audio_file(MutagenFile, filepath)

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
                elif isinstance(audio_file, ASF) or ext == 'wma':
                    # Real ASF attribute names (#5536); the generic fallthrough
                    # wrote bogus lowercase keys no other player reads.
                    self.writers.write_asf_metadata(audio_file, metadata)
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
