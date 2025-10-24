# -*- coding: utf-8 -*-

"""
Auralis Metadata Editor
~~~~~~~~~~~~~~~~~~~~~~~

Audio file metadata editing and management
Supports MP3, FLAC, M4A, OGG, WAV and other formats via mutagen

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import os
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass

try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TDRC, TCON, TRCK, TPOS, COMM
    from mutagen.flac import FLAC
    from mutagen.mp4 import MP4
    from mutagen.oggvorbis import OggVorbis
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    MutagenFile = None

from ..utils.logging import info, warning, error, debug


@dataclass
class MetadataUpdate:
    """Represents a metadata update operation"""
    track_id: int
    filepath: str
    updates: Dict[str, Any]
    backup: bool = True


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

    # Standard metadata fields (common across all formats)
    STANDARD_FIELDS = {
        'title', 'artist', 'album', 'albumartist', 'year',
        'genre', 'track', 'disc', 'comment', 'bpm', 'composer',
        'publisher', 'lyrics', 'copyright'
    }

    # Format-specific tag mappings
    TAG_MAPPINGS = {
        'mp3': {
            'title': 'TIT2',
            'artist': 'TPE1',
            'album': 'TALB',
            'albumartist': 'TPE2',
            'year': 'TDRC',
            'genre': 'TCON',
            'track': 'TRCK',
            'disc': 'TPOS',
            'comment': 'COMM::eng',
            'bpm': 'TBPM',
            'composer': 'TCOM',
            'publisher': 'TPUB',
            'lyrics': 'USLT::eng',
            'copyright': 'TCOP'
        },
        'flac': {
            # FLAC uses Vorbis comments (case-insensitive, but uppercase by convention)
            'title': 'TITLE',
            'artist': 'ARTIST',
            'album': 'ALBUM',
            'albumartist': 'ALBUMARTIST',
            'year': 'DATE',
            'genre': 'GENRE',
            'track': 'TRACKNUMBER',
            'disc': 'DISCNUMBER',
            'comment': 'COMMENT',
            'bpm': 'BPM',
            'composer': 'COMPOSER',
            'publisher': 'PUBLISHER',
            'lyrics': 'LYRICS',
            'copyright': 'COPYRIGHT'
        },
        'm4a': {
            # MP4/M4A uses freeform atoms
            'title': '\xa9nam',
            'artist': '\xa9ART',
            'album': '\xa9alb',
            'albumartist': 'aART',
            'year': '\xa9day',
            'genre': '\xa9gen',
            'track': 'trkn',
            'disc': 'disk',
            'comment': '\xa9cmt',
            'bpm': 'tmpo',
            'composer': '\xa9wrt',
            'publisher': '----:com.apple.iTunes:PUBLISHER',
            'lyrics': '\xa9lyr',
            'copyright': 'cprt'
        },
        'ogg': {
            # OGG Vorbis comments
            'title': 'TITLE',
            'artist': 'ARTIST',
            'album': 'ALBUM',
            'albumartist': 'ALBUMARTIST',
            'year': 'DATE',
            'genre': 'GENRE',
            'track': 'TRACKNUMBER',
            'disc': 'DISCNUMBER',
            'comment': 'COMMENT',
            'bpm': 'BPM',
            'composer': 'COMPOSER',
            'publisher': 'PUBLISHER',
            'lyrics': 'LYRICS',
            'copyright': 'COPYRIGHT'
        }
    }

    def __init__(self):
        """Initialize metadata editor"""
        if not MUTAGEN_AVAILABLE:
            raise ImportError("mutagen library is required for metadata editing")

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

        # Map extensions to format keys
        format_map = {
            'mp3': 'mp3',
            'flac': 'flac',
            'm4a': 'm4a',
            'aac': 'm4a',
            'mp4': 'm4a',
            'ogg': 'ogg',
            'oga': 'ogg'
        }

        format_key = format_map.get(ext, 'flac')  # Default to FLAC tags
        return list(self.TAG_MAPPINGS.get(format_key, {}).keys())

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

            # Determine format
            if isinstance(audio_file, FLAC) or ext == 'flac':
                metadata = self._read_flac_metadata(audio_file)
            elif isinstance(audio_file, MP4) or ext in ('m4a', 'aac', 'mp4'):
                metadata = self._read_mp4_metadata(audio_file)
            elif isinstance(audio_file, OggVorbis) or ext in ('ogg', 'oga'):
                metadata = self._read_ogg_metadata(audio_file)
            elif ext == 'mp3':
                metadata = self._read_mp3_metadata(audio_file)
            else:
                # Generic fallback
                metadata = self._read_generic_metadata(audio_file)

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
            self._create_backup(filepath)

        try:
            audio_file = MutagenFile(filepath)
            if audio_file is None:
                raise ValueError(f"Unsupported or invalid audio file: {filepath}")

            ext = os.path.splitext(filepath)[1].lower().lstrip('.')

            # Write format-specific metadata
            if isinstance(audio_file, FLAC) or ext == 'flac':
                self._write_flac_metadata(audio_file, metadata)
            elif isinstance(audio_file, MP4) or ext in ('m4a', 'aac', 'mp4'):
                self._write_mp4_metadata(audio_file, metadata)
            elif isinstance(audio_file, OggVorbis) or ext in ('ogg', 'oga'):
                self._write_ogg_metadata(audio_file, metadata)
            elif ext == 'mp3':
                self._write_mp3_metadata(audio_file, metadata)
            else:
                # Generic fallback
                self._write_generic_metadata(audio_file, metadata)

            # Save changes
            audio_file.save()
            info(f"Updated metadata for {filepath}")
            return True

        except Exception as e:
            error(f"Failed to write metadata to {filepath}: {e}")
            # Restore backup if available
            if backup:
                self._restore_backup(filepath)
            raise

    def batch_update(self, updates: List[MetadataUpdate]) -> Dict[str, Any]:
        """
        Update metadata for multiple tracks

        Args:
            updates: List of MetadataUpdate objects

        Returns:
            Dictionary with success/failure counts and errors
        """
        results = {
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

    # Format-specific read methods

    def _read_mp3_metadata(self, audio_file) -> Dict[str, Any]:
        """Read metadata from MP3 file"""
        metadata = {}
        tag_map = self.TAG_MAPPINGS['mp3']

        for field, tag_key in tag_map.items():
            if tag_key in audio_file:
                value = audio_file[tag_key]
                if field in ('track', 'disc'):
                    # Handle track/disc as string "number/total"
                    metadata[field] = str(value) if value else None
                else:
                    metadata[field] = str(value) if value else None

        return metadata

    def _read_flac_metadata(self, audio_file) -> Dict[str, Any]:
        """Read metadata from FLAC file"""
        metadata = {}
        tag_map = self.TAG_MAPPINGS['flac']

        for field, tag_key in tag_map.items():
            if tag_key in audio_file:
                value = audio_file[tag_key]
                if isinstance(value, list) and value:
                    value = value[0]
                metadata[field] = str(value) if value else None

        return metadata

    def _read_mp4_metadata(self, audio_file) -> Dict[str, Any]:
        """Read metadata from MP4/M4A file"""
        metadata = {}
        tag_map = self.TAG_MAPPINGS['m4a']

        for field, tag_key in tag_map.items():
            if tag_key in audio_file:
                value = audio_file[tag_key]
                if isinstance(value, list) and value:
                    value = value[0]

                # Handle special MP4 types
                if field in ('track', 'disc') and isinstance(value, tuple):
                    metadata[field] = f"{value[0]}/{value[1]}" if len(value) > 1 else str(value[0])
                else:
                    metadata[field] = str(value) if value else None

        return metadata

    def _read_ogg_metadata(self, audio_file) -> Dict[str, Any]:
        """Read metadata from OGG file"""
        return self._read_flac_metadata(audio_file)  # Same as FLAC (Vorbis comments)

    def _read_generic_metadata(self, audio_file) -> Dict[str, Any]:
        """Read metadata using generic method"""
        metadata = {}
        if hasattr(audio_file, 'tags') and audio_file.tags:
            for key, value in audio_file.tags.items():
                if isinstance(value, list) and value:
                    value = value[0]
                metadata[str(key).lower()] = str(value) if value else None
        return metadata

    # Format-specific write methods

    def _write_mp3_metadata(self, audio_file, metadata: Dict[str, Any]):
        """Write metadata to MP3 file"""
        # Ensure ID3 tags exist
        if audio_file.tags is None:
            audio_file.add_tags()

        tag_map = self.TAG_MAPPINGS['mp3']

        for field, value in metadata.items():
            if field not in tag_map:
                continue

            tag_key = tag_map[field]

            if value is None or value == '':
                # Remove tag
                if tag_key in audio_file:
                    del audio_file[tag_key]
            else:
                # Set tag
                if field == 'title':
                    audio_file['TIT2'] = TIT2(encoding=3, text=str(value))
                elif field == 'artist':
                    audio_file['TPE1'] = TPE1(encoding=3, text=str(value))
                elif field == 'album':
                    audio_file['TALB'] = TALB(encoding=3, text=str(value))
                elif field == 'albumartist':
                    audio_file['TPE2'] = TPE2(encoding=3, text=str(value))
                elif field == 'year':
                    audio_file['TDRC'] = TDRC(encoding=3, text=str(value))
                elif field == 'genre':
                    audio_file['TCON'] = TCON(encoding=3, text=str(value))
                elif field == 'track':
                    audio_file['TRCK'] = TRCK(encoding=3, text=str(value))
                elif field == 'disc':
                    audio_file['TPOS'] = TPOS(encoding=3, text=str(value))
                elif field == 'comment':
                    audio_file['COMM::eng'] = COMM(encoding=3, lang='eng', desc='', text=str(value))

    def _write_flac_metadata(self, audio_file, metadata: Dict[str, Any]):
        """Write metadata to FLAC file"""
        tag_map = self.TAG_MAPPINGS['flac']

        for field, value in metadata.items():
            if field not in tag_map:
                continue

            tag_key = tag_map[field]

            if value is None or value == '':
                # Remove tag
                if tag_key in audio_file:
                    del audio_file[tag_key]
            else:
                # Set tag
                audio_file[tag_key] = str(value)

    def _write_mp4_metadata(self, audio_file, metadata: Dict[str, Any]):
        """Write metadata to MP4/M4A file"""
        tag_map = self.TAG_MAPPINGS['m4a']

        for field, value in metadata.items():
            if field not in tag_map:
                continue

            tag_key = tag_map[field]

            if value is None or value == '':
                # Remove tag
                if tag_key in audio_file:
                    del audio_file[tag_key]
            else:
                # Set tag (handle special MP4 types)
                if field in ('track', 'disc'):
                    # Parse "number/total" format
                    parts = str(value).split('/')
                    if len(parts) == 2:
                        audio_file[tag_key] = [(int(parts[0]), int(parts[1]))]
                    else:
                        audio_file[tag_key] = [(int(parts[0]), 0)]
                else:
                    audio_file[tag_key] = [str(value)]

    def _write_ogg_metadata(self, audio_file, metadata: Dict[str, Any]):
        """Write metadata to OGG file"""
        self._write_flac_metadata(audio_file, metadata)  # Same as FLAC (Vorbis comments)

    def _write_generic_metadata(self, audio_file, metadata: Dict[str, Any]):
        """Write metadata using generic method"""
        if audio_file.tags is None:
            audio_file.add_tags()

        for field, value in metadata.items():
            if value is None or value == '':
                if field in audio_file:
                    del audio_file[field]
            else:
                audio_file[field] = str(value)

    # Backup/restore methods

    def _create_backup(self, filepath: str):
        """Create backup of file before modification"""
        backup_path = filepath + '.bak'
        try:
            import shutil
            shutil.copy2(filepath, backup_path)
            debug(f"Created backup: {backup_path}")
        except Exception as e:
            warning(f"Failed to create backup: {e}")

    def _restore_backup(self, filepath: str):
        """Restore file from backup"""
        backup_path = filepath + '.bak'
        if os.path.exists(backup_path):
            try:
                import shutil
                shutil.move(backup_path, filepath)
                info(f"Restored from backup: {filepath}")
            except Exception as e:
                error(f"Failed to restore backup: {e}")


def create_metadata_editor() -> MetadataEditor:
    """Factory function to create metadata editor"""
    return MetadataEditor()
