# -*- coding: utf-8 -*-

"""
Metadata Editor
~~~~~~~~~~~~~~~

Audio file metadata editing orchestrator

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import os
from typing import Dict, List, Any
from pathlib import Path

try:
    from mutagen import File as MutagenFile
    from mutagen.flac import FLAC
    from mutagen.mp4 import MP4
    from mutagen.oggvorbis import OggVorbis
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    MutagenFile = None

from .models import MetadataUpdate
from .tag_mappings import TAG_MAPPINGS, STANDARD_FIELDS, get_format_key
from .readers import MetadataReaders
from .writers import MetadataWriters
from .backup import BackupManager
from ...utils.logging import info, warning, error, debug


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

    def get_supported_formats(self) -> List[str]:
        """Get list of supported audio formats"""
        return ['mp3', 'flac', 'm4a', 'aac', 'ogg', 'wav']

    def get_editable_fields(self, filepath: str) -> List[str]:
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

    def read_metadata(self, filepath: str) -> Dict[str, Any]:
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

    def write_metadata(self, filepath: str, metadata: Dict[str, Any], backup: bool = True) -> bool:
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

    def batch_update(self, updates: List[MetadataUpdate]) -> Dict[str, Any]:
        """
        Update metadata for multiple tracks

        Args:
            updates: List of MetadataUpdate objects

        Returns:
            Dictionary with success/failure counts and errors
        """
        results: Dict[str, Any] = {
            'success': 0,
            'failed': 0,
            'errors': []
        }

        for update in updates:
            try:
                self.write_metadata(update.filepath, update.updates, backup=update.backup)
                results['success'] += 1
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'track_id': update.track_id,
                    'filepath': update.filepath,
                    'error': str(e)
                })

        info(f"Batch update complete: {results['success']} succeeded, {results['failed']} failed")
        return results

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
