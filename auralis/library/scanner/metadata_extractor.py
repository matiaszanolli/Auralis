# -*- coding: utf-8 -*-

"""
Metadata Extractor
~~~~~~~~~~~~~~~~~

Music metadata extraction from audio files

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from pathlib import Path
from typing import Any, Dict, Optional

try:
    from mutagen import File as MutagenFile  # type: ignore[attr-defined]
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    MutagenFile = None

from ...utils.logging import debug
from ..scan_models import AudioFileInfo
from ..utils.artist_normalizer import parse_featured_artists


class MetadataExtractor:
    """
    Extracts music metadata from audio files

    Supports:
    - ID3 tags (MP3)
    - Vorbis comments (FLAC, OGG)
    - iTunes tags (M4A)
    - Common metadata fields
    """

    # Tag mappings for different audio formats
    TAG_MAPPINGS = {
        'title': ['TIT2', 'TITLE', '\xa9nam'],
        'artist': ['TPE1', 'ARTIST', '\xa9ART'],
        'album': ['TALB', 'ALBUM', '\xa9alb'],
        'albumartist': ['TPE2', 'ALBUMARTIST', 'aART'],
        'date': ['TDRC', 'DATE', '\xa9day'],
        'year': ['TDRC', 'DATE', '\xa9day', 'YEAR'],
        'genre': ['TCON', 'GENRE', '\xa9gen'],
        'track': ['TRCK', 'TRACKNUMBER', 'trkn'],
        'disc': ['TPOS', 'DISCNUMBER', 'disk'],
        'comment': ['COMM::eng', 'COMMENT', '\xa9cmt']
    }

    def extract_metadata_from_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Extract metadata from audio file

        Args:
            file_path: Path to audio file

        Returns:
            Dictionary of metadata fields or None if extraction fails
        """
        if not MUTAGEN_AVAILABLE:
            debug("Mutagen not available, skipping metadata extraction")
            return None

        try:
            audio_file = MutagenFile(file_path)
            if audio_file:
                return self.extract_metadata(audio_file)
        except Exception as e:
            debug(f"Metadata extraction failed for {file_path}: {e}")

        return None

    def extract_metadata(self, audio_file: Any) -> Dict[str, Any]:
        """
        Extract metadata from mutagen audio file object

        Args:
            audio_file: Mutagen audio file object

        Returns:
            Dictionary of normalized metadata
        """
        metadata = {}

        for field, keys in self.TAG_MAPPINGS.items():
            for key in keys:
                if key in audio_file:
                    value = audio_file[key]
                    if isinstance(value, list) and value:
                        value = value[0]

                    if value:
                        normalized_value = self._normalize_field_value(field, value)
                        if normalized_value is not None:
                            metadata[field] = normalized_value
                            break

        return metadata

    def _normalize_field_value(self, field: str, value: Any) -> Optional[Any]:
        """
        Normalize metadata field value to appropriate type

        Args:
            field: Field name
            value: Raw value

        Returns:
            Normalized value or None if normalization fails
        """
        try:
            if field in ['track', 'disc']:
                # Handle track/disc numbers
                if '/' in str(value):
                    value = int(str(value).split('/')[0])
                else:
                    value = int(value)
                return value

            elif field in ['year', 'date']:
                # Handle year/date
                year_str = str(value)[:4]
                return int(year_str)

            else:
                # String fields
                return str(value)

        except (ValueError, TypeError):
            return None

    def audio_info_to_track_info(self, audio_info: AudioFileInfo) -> Dict[str, Any]:
        """
        Convert AudioFileInfo to track_info dict for library manager

        Args:
            audio_info: AudioFileInfo object

        Returns:
            Dictionary in format expected by library manager
        """
        track_info: Dict[str, Any] = {
            'filepath': audio_info.filepath,
            'title': audio_info.filename,  # Default to filename
            'duration': audio_info.duration,
            'sample_rate': audio_info.sample_rate,
            'channels': audio_info.channels,
            'format': audio_info.format,
            'filesize': audio_info.filesize,
        }

        # Add metadata if available
        if audio_info.metadata:
            metadata = audio_info.metadata

            # Map metadata to track_info
            if 'title' in metadata:
                track_info['title'] = metadata['title']
            else:
                # Use filename without extension as title
                track_info['title'] = Path(audio_info.filepath).stem

            if 'artist' in metadata:
                # Handle multiple artists and parse featured artists
                artists = metadata['artist']
                if isinstance(artists, str):
                    # Parse "Artist A feat. Artist B" -> ["Artist A", "Artist B"]
                    track_info['artists'] = parse_featured_artists(artists)
                else:
                    # Handle list of artists - parse each one for featured artists
                    all_artists = []
                    for a in artists:
                        parsed = parse_featured_artists(str(a))
                        all_artists.extend(parsed)
                    track_info['artists'] = all_artists

            if 'album' in metadata:
                track_info['album'] = metadata['album']

            if 'genre' in metadata:
                genres = metadata['genre']
                if isinstance(genres, str):
                    track_info['genres'] = [genres]
                else:
                    track_info['genres'] = [str(g) for g in genres]

            if 'track' in metadata:
                track_info['track_number'] = metadata['track']

            if 'disc' in metadata:
                track_info['disc_number'] = metadata['disc']

            if 'year' in metadata:
                track_info['year'] = metadata['year']

        return track_info
