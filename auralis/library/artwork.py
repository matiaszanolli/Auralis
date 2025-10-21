# -*- coding: utf-8 -*-

"""
Auralis Artwork Extraction
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Album artwork extraction and management for music library

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import os
import hashlib
from pathlib import Path
from typing import Optional, Tuple
from mutagen import File as MutagenFile
from mutagen.id3 import ID3, APIC
from mutagen.mp4 import MP4, MP4Cover
from mutagen.flac import FLAC, Picture

from ..utils.logging import info, warning, error, debug


class ArtworkExtractor:
    """
    Extract and manage album artwork from audio files

    Features:
    - Extract embedded artwork from MP3, FLAC, M4A, OGG
    - Save artwork to organized directory structure
    - Generate unique filenames to avoid collisions
    - Support multiple image formats (JPEG, PNG)
    """

    def __init__(self, artwork_directory: str):
        """
        Initialize artwork extractor

        Args:
            artwork_directory: Base directory for saving artwork
        """
        self.artwork_dir = Path(artwork_directory)
        self.artwork_dir.mkdir(parents=True, exist_ok=True)

    def extract_artwork(self, audio_filepath: str, album_id: int) -> Optional[str]:
        """
        Extract artwork from audio file and save to artwork directory

        Args:
            audio_filepath: Path to audio file
            album_id: Album ID for organizing artwork

        Returns:
            Path to saved artwork file, or None if no artwork found
        """
        try:
            audio_file = MutagenFile(audio_filepath)
            if not audio_file:
                return None

            # Extract artwork data based on file type
            artwork_data = None
            mime_type = None

            if isinstance(audio_file, ID3) or hasattr(audio_file, 'tags') and isinstance(audio_file.tags, ID3):
                # MP3 files with ID3 tags
                artwork_data, mime_type = self._extract_from_id3(audio_file)
            elif isinstance(audio_file, MP4):
                # M4A/MP4 files
                artwork_data, mime_type = self._extract_from_mp4(audio_file)
            elif isinstance(audio_file, FLAC):
                # FLAC files
                artwork_data, mime_type = self._extract_from_flac(audio_file)
            elif hasattr(audio_file, 'tags') and audio_file.tags:
                # OGG and other formats with generic tags
                artwork_data, mime_type = self._extract_from_generic(audio_file)

            if not artwork_data:
                debug(f"No artwork found in {audio_filepath}")
                return None

            # Save artwork to file
            return self._save_artwork(artwork_data, album_id, mime_type)

        except Exception as e:
            debug(f"Failed to extract artwork from {audio_filepath}: {e}")
            return None

    def _extract_from_id3(self, audio_file) -> Tuple[Optional[bytes], Optional[str]]:
        """Extract artwork from ID3 tags (MP3)"""
        try:
            tags = audio_file if isinstance(audio_file, ID3) else audio_file.tags
            if not tags:
                return None, None

            # Look for APIC (Attached Picture) frames
            for key in tags.keys():
                if key.startswith('APIC'):
                    apic = tags[key]
                    return apic.data, apic.mime

        except Exception as e:
            debug(f"Failed to extract from ID3: {e}")

        return None, None

    def _extract_from_mp4(self, audio_file: MP4) -> Tuple[Optional[bytes], Optional[str]]:
        """Extract artwork from MP4/M4A files"""
        try:
            if 'covr' in audio_file.tags:
                cover = audio_file.tags['covr'][0]
                # MP4Cover has imageformat attribute
                if cover.imageformat == MP4Cover.FORMAT_JPEG:
                    mime_type = 'image/jpeg'
                elif cover.imageformat == MP4Cover.FORMAT_PNG:
                    mime_type = 'image/png'
                else:
                    mime_type = 'image/jpeg'  # Default
                return bytes(cover), mime_type

        except Exception as e:
            debug(f"Failed to extract from MP4: {e}")

        return None, None

    def _extract_from_flac(self, audio_file: FLAC) -> Tuple[Optional[bytes], Optional[str]]:
        """Extract artwork from FLAC files"""
        try:
            if audio_file.pictures:
                picture = audio_file.pictures[0]  # Get first picture
                return picture.data, picture.mime

        except Exception as e:
            debug(f"Failed to extract from FLAC: {e}")

        return None, None

    def _extract_from_generic(self, audio_file) -> Tuple[Optional[bytes], Optional[str]]:
        """Extract artwork from generic tag formats (OGG, etc.)"""
        try:
            tags = audio_file.tags

            # Try common artwork tag names
            artwork_keys = ['COVERART', 'COVER', 'METADATA_BLOCK_PICTURE']

            for key in artwork_keys:
                if key in tags:
                    # Handle base64-encoded artwork (Vorbis comments)
                    if key == 'METADATA_BLOCK_PICTURE':
                        import base64
                        picture_data = base64.b64decode(tags[key][0])
                        # Parse FLAC Picture block
                        picture = Picture(picture_data)
                        return picture.data, picture.mime
                    else:
                        return tags[key][0], 'image/jpeg'

        except Exception as e:
            debug(f"Failed to extract from generic tags: {e}")

        return None, None

    def _save_artwork(self, artwork_data: bytes, album_id: int, mime_type: Optional[str]) -> Optional[str]:
        """
        Save artwork data to file

        Args:
            artwork_data: Raw image data
            album_id: Album ID for filename
            mime_type: MIME type of image (e.g., 'image/jpeg')

        Returns:
            Path to saved artwork file
        """
        try:
            # Determine file extension from MIME type
            if mime_type and 'png' in mime_type.lower():
                ext = '.png'
            else:
                ext = '.jpg'  # Default to JPEG

            # Generate unique filename using album ID and content hash
            content_hash = hashlib.md5(artwork_data).hexdigest()[:8]
            filename = f"album_{album_id}_{content_hash}{ext}"

            artwork_path = self.artwork_dir / filename

            # Save artwork data
            with open(artwork_path, 'wb') as f:
                f.write(artwork_data)

            info(f"Saved artwork to {artwork_path}")
            return str(artwork_path)

        except Exception as e:
            error(f"Failed to save artwork: {e}")
            return None

    def get_artwork_path(self, album_id: int) -> Optional[str]:
        """
        Get artwork path for album ID

        Args:
            album_id: Album ID

        Returns:
            Path to artwork file if exists, None otherwise
        """
        # Search for artwork files matching the album ID
        pattern = f"album_{album_id}_*"
        matches = list(self.artwork_dir.glob(pattern))

        if matches:
            return str(matches[0])

        return None

    def delete_artwork(self, artwork_path: str) -> bool:
        """
        Delete artwork file

        Args:
            artwork_path: Path to artwork file

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            path = Path(artwork_path)
            if path.exists():
                path.unlink()
                info(f"Deleted artwork: {artwork_path}")
                return True
        except Exception as e:
            error(f"Failed to delete artwork {artwork_path}: {e}")

        return False


def create_artwork_extractor(artwork_directory: str) -> ArtworkExtractor:
    """
    Factory function to create artwork extractor

    Args:
        artwork_directory: Base directory for artwork storage

    Returns:
        ArtworkExtractor instance
    """
    return ArtworkExtractor(artwork_directory)
