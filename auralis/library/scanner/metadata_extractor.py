"""
Metadata Extractor
~~~~~~~~~~~~~~~~~

Music metadata extraction from audio files

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pathlib import Path
from typing import Any

from mutagen import File as MutagenFile  # a required dependency (#6655)

from ...utils.logging import debug
from ..constants import MAX_ARTISTS_PER_TRACK, MAX_GENRES_PER_TRACK, MAX_TAG_TEXT_CHARS
from ..scan_models import AudioFileInfo
from ..utils.artist_normalizer import parse_featured_artists

# A track or disc number above this is a corrupt or hostile tag, not a position: a value past
# SQLite's int64 raised OverflowError in the insert and blocked the track's ingest (#5732).
MAX_TRACK_NUMBER = 99_999

# Tags whose several values are all kept (the track model holds lists of artists and genres, #5732).
MULTI_VALUED_FIELDS = frozenset({'artist', 'genre'})
# The repository keeps at most this many of either; extracting more is wasted work (#6510).
MAX_TAG_VALUES = max(MAX_ARTISTS_PER_TRACK, MAX_GENRES_PER_TRACK)


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
        'title': ['TIT2', 'TITLE', '\xa9nam', 'Title'],
        'artist': ['TPE1', 'ARTIST', '\xa9ART', 'Author'],
        'album': ['TALB', 'ALBUM', '\xa9alb', 'WM/AlbumTitle'],
        'albumartist': ['TPE2', 'ALBUMARTIST', 'aART', 'WM/AlbumArtist'],
        'date': ['TDRC', 'DATE', '\xa9day', 'WM/Year'],
        'year': ['TDRC', 'DATE', '\xa9day', 'YEAR', 'WM/Year'],
        'genre': ['TCON', 'GENRE', '\xa9gen', 'WM/Genre'],
        'track': ['TRCK', 'TRACKNUMBER', 'trkn', 'WM/TrackNumber'],
        'disc': ['TPOS', 'DISCNUMBER', 'disk', 'WM/PartOfSet'],
        'comment': ['COMM::eng', 'COMMENT', '\xa9cmt', 'Description']
    }

    def extract_metadata_from_file(self, file_path: str) -> dict[str, Any] | None:
        """
        Extract metadata from audio file

        Args:
            file_path: Path to audio file

        Returns:
            Dictionary of metadata fields or None if extraction fails
        """
        try:
            audio_file = MutagenFile(file_path)
            if audio_file:
                return self.extract_metadata(audio_file)
        except Exception as e:
            debug(f"Metadata extraction failed for {file_path}: {e}")

        return None

    def extract_metadata(self, audio_file: Any) -> dict[str, Any]:
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
                try:
                    if key not in audio_file:
                        continue
                    value = audio_file[key]
                except ValueError:
                    # TAG_MAPPINGS mixes ID3 (MP3), Vorbis-comment (FLAC/OGG)
                    # and MP4 atom key spellings per field so one table covers
                    # every format. Vorbis-comment keys are restricted to
                    # printable ASCII excluding '=' (mutagen's
                    # vorbis.is_valid_key) — an MP4 atom name like '\xa9nam'
                    # violates that and raises ValueError from `key in
                    # audio_file` on a FLAC/OGG file, regardless of whether
                    # that key is actually present. Uncaught, this used to
                    # propagate out of the whole method on the first
                    # not-actually-set field reaching its MP4-style
                    # candidate, discarding every field already matched and
                    # silently returning no metadata at all for the file —
                    # not just skipping the one inapplicable key.
                    continue

                values = self._raw_values(value)
                if field in MULTI_VALUED_FIELDS:
                    # Repeated ARTIST/GENRE (Vorbis), a multi-valued ID3 frame or an MP4 list: keep every
                    # value. A single one stays a string, so single-valued files read exactly as before.
                    kept = self._distinct(self._normalize_field_value(field, v) for v in values if v)
                    if kept:
                        metadata[field] = kept[0] if len(kept) == 1 else kept
                        break
                elif values and values[0]:
                    normalized_value = self._normalize_field_value(field, values[0])
                    if normalized_value is not None:
                        metadata[field] = normalized_value
                        break

        return metadata

    @staticmethod
    def _raw_values(value: Any) -> list[Any]:
        """Every value a tag holds: a list as is, an ID3 TextFrame's ``text`` list (``str()`` of a
        multi-valued frame is mutagen's NUL-joined text, #6133), otherwise the value itself."""
        if isinstance(value, list):
            return value
        frame_text = getattr(value, 'text', None)
        if isinstance(frame_text, list):
            return frame_text
        return [value]

    @staticmethod
    def _distinct(values: Any) -> list[Any]:
        """The non-empty values in order, without repeats, at most MAX_TAG_VALUES of them (#6510).

        A list-membership dedup was quadratic, and nothing bounded the count: a 16 MiB Vorbis block of
        distinct ARTIST values froze the scan in pure Python. A dict dedups in linear time, and the
        loop stops (so ``values``, a generator, stops normalizing) once the cap is reached.
        """
        seen: dict[Any, None] = {}
        for value in values:
            if value is not None:
                seen.setdefault(value, None)
                if len(seen) >= MAX_TAG_VALUES:
                    break
        return list(seen)

    def _normalize_field_value(self, field: str, value: Any) -> Any | None:
        """
        Normalize metadata field value to appropriate type

        Args:
            field: Field name
            value: Raw value

        Returns:
            Normalized value or None if normalization fails
        """
        try:
            if hasattr(value, 'value'):
                value = value.value

            if field in ['track', 'disc']:
                # Disallow boolean or binary attributes as track/disc numbers
                if isinstance(value, (bool, bytes, bytearray)):
                    return None

                # Handle track/disc numbers (tuple/list for MP4, string for Vorbis/ID3/ASF)
                if isinstance(value, (tuple, list)):
                    track_no = int(value[0]) if value else 0
                    return track_no if 0 < track_no <= MAX_TRACK_NUMBER else None

                val_str = str(value).strip()
                if '/' in val_str:
                    num = int(val_str.split('/')[0])
                else:
                    num = int(val_str)
                return num if 0 < num <= MAX_TRACK_NUMBER else None

            elif field in ['year', 'date']:
                # Handle year/date
                if isinstance(value, (bool, bytes, bytearray)):
                    return None
                year_str = str(value).strip()[:4]
                year_num = int(year_str)
                return year_num if year_num > 0 else None

            else:
                # String fields
                if isinstance(value, (bool, bytes, bytearray)):
                    return None
                val_str = str(value).strip()[:MAX_TAG_TEXT_CHARS]
                return val_str if val_str else None

        except (ValueError, TypeError):
            return None

    def audio_info_to_track_info(self, audio_info: AudioFileInfo) -> dict[str, Any]:
        """
        Convert AudioFileInfo to track_info dict for the library

        Args:
            audio_info: AudioFileInfo object

        Returns:
            Dictionary in format expected by the track repository
        """
        track_info: dict[str, Any] = {
            'filepath': audio_info.filepath,
            'title': Path(audio_info.filepath).stem,  # Default: filename without extension (#6148)
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

            if 'albumartist' in metadata:
                # The album's owner (#6332), one name. Parsed like a track artist so
                # "Iron & Wine" stays whole and a stray "A feat. B" yields the main credit.
                track_info['album_artist'] = parse_featured_artists(metadata['albumartist'])[0]

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
