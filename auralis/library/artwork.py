"""
Auralis Artwork Extraction
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Album artwork extraction and management for music library

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import hashlib
from pathlib import Path

from mutagen import File as MutagenFile
from mutagen.flac import FLAC
from mutagen.id3 import ID3
from mutagen.mp4 import MP4

from ..utils.artwork_security import (
    MAX_LOCAL_ARTWORK_BYTES,
    bound_artwork_dimensions,
    detect_image_extension,
)
from ..utils.logging import debug, error, info
from .artwork_tags import TagArtworkReadersMixin

# Cap the largest side of stored artwork (#4439). Embedded/folder covers can be
# arbitrarily large (e.g. 6000x6000); bounding the source here keeps disk usage
# and client-side decode cost in check while retaining more than enough
# resolution for the largest served thumbnail bucket (1024px) and full-size
# display. Matches the GET endpoint's maximum requestable size (le=2048).
_MAX_ARTWORK_DIMENSION = 2048


class ArtworkExtractor(TagArtworkReadersMixin):
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

    def extract_artwork(self, audio_filepath: str, album_id: int) -> str | None:
        """
        Extract artwork from audio file and save to artwork directory

        Prioritizes embedded artwork in audio files, then falls back to
        folder.jpg/folder.png if no embedded artwork is found.

        Args:
            audio_filepath: Path to audio file
            album_id: Album ID for organizing artwork

        Returns:
            Path to saved artwork file, or None if no artwork found
        """
        try:
            # First priority: Extract embedded artwork from audio file
            audio_file = MutagenFile(audio_filepath)
            if audio_file:
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

                if artwork_data:
                    # A rejected embedded cover (#6153) falls through to folder art.
                    saved_path = self._save_artwork(artwork_data, album_id, mime_type)
                    if saved_path:
                        return saved_path

            # Fallback: Look for folder artwork if no embedded artwork found
            folder_artwork = self._find_folder_artwork(audio_filepath, album_id)
            if folder_artwork:
                return folder_artwork

            debug(f"No artwork found in {audio_filepath}")
            return None

        except Exception as e:
            debug(f"Failed to extract artwork from {audio_filepath}: {e}")
            return None

    def _find_folder_artwork(self, audio_filepath: str, album_id: int) -> str | None:
        """
        Look for folder.jpg/folder.png or cover.jpg/cover.png in the album directory

        Supports multiple naming conventions:
        - folder.jpg, cover.jpg (standard)
        - front.jpg (common in digital music collections)
        - AlbumArtSmall.jpg (Windows Media Player)
        - Various case variations

        Args:
            audio_filepath: Path to audio file (to determine album directory)
            album_id: Album ID for organizing artwork

        Returns:
            Path to saved artwork file, or None if not found
        """
        try:
            # Get the directory containing the audio file (album folder)
            album_dir = Path(audio_filepath).parent

            # Priority order: check most common artwork filenames first
            # Standard naming (highest priority)
            artwork_names = [
                'folder.jpg', 'folder.jpeg', 'folder.png',
                'Folder.jpg', 'Folder.jpeg', 'Folder.png',
                'cover.jpg', 'cover.jpeg', 'cover.png',
                'Cover.jpg', 'Cover.jpeg', 'Cover.png',
            ]

            # Front artwork (very common in many music libraries)
            artwork_names.extend([
                'front.jpg', 'front.jpeg', 'front.png',
                'Front.jpg', 'Front.jpeg', 'Front.png',
                'FRONT.jpg', 'FRONT.jpeg', 'FRONT.png',
            ])

            # Windows Media Player and other naming conventions
            artwork_names.extend([
                'AlbumArtSmall.jpg', 'AlbumArt.jpg',
                'albumart.jpg', 'albumartsmall.jpg',
            ])

            for artwork_name in artwork_names:
                artwork_file = album_dir / artwork_name
                if artwork_file.exists() and artwork_file.stat().st_size <= MAX_LOCAL_ARTWORK_BYTES:
                    # Read the artwork file
                    with open(artwork_file, 'rb') as f:
                        artwork_data = f.read()

                    # Determine MIME type from extension
                    mime_type = 'image/png' if artwork_file.suffix.lower() in ['.png'] else 'image/jpeg'

                    # Save to artwork directory
                    saved_path = self._save_artwork(artwork_data, album_id, mime_type)
                    if saved_path:
                        info(f"Found folder artwork: {artwork_file}")
                        return saved_path

        except Exception as e:
            debug(f"Failed to check for folder artwork: {e}")

        return None

    def _save_artwork(self, artwork_data: bytes, album_id: int, mime_type: str | None) -> str | None:
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
            # Skip an oversized picture before anything decodes it (#6153).
            if len(artwork_data) > MAX_LOCAL_ARTWORK_BYTES:
                debug(f"Skipping artwork of {len(artwork_data)} bytes (over the local artwork cap)")
                return None

            # Bound the stored image to a sane maximum dimension (#4439) so an
            # oversized embedded/folder cover isn't persisted and later streamed
            # at full resolution. Best-effort — falls back to the original bytes.
            bounded = bound_artwork_dimensions(artwork_data)
            if bounded is None:  # decompression bomb: drop it (#6153)
                debug("Dropped artwork that exceeds the pixel budget")
                return None
            artwork_data = bounded

            # Sniff the real extension from the (possibly re-encoded) bytes
            # rather than trusting the tag's declared mime_type (#4849) —
            # mirrors services/artwork_downloader.py's #4419 fix. Sniffing
            # AFTER bounding means the extension always matches what actually
            # gets written to disk, even when an oversized non-JPEG/PNG image
            # was re-encoded above. mime_type is kept only as the last-resort
            # default for bytes neither sniff recognises.
            default_ext = 'png' if mime_type and 'png' in mime_type.lower() else 'jpg'
            ext = '.' + detect_image_extension(artwork_data, default=default_ext)

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

    @staticmethod
    def delete_artwork(artwork_path: str) -> bool:
        """Delete the artwork file (stateless, so callable on the class: #5596).

        Returns True if deleted, False otherwise.
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
