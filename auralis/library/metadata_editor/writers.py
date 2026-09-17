"""
Metadata Writers
~~~~~~~~~~~~~~~~

Format-specific metadata writing functions

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

from .tag_mappings import TAG_MAPPINGS

try:
    from mutagen.id3 import (
        COMM,
        TALB,
        TCON,
        TDRC,
        TIT2,
        TPE1,
        TPE2,
        TPOS,
        TRCK,
    )
    MUTAGEN_ID3_AVAILABLE: bool = True
except ImportError:
    MUTAGEN_ID3_AVAILABLE = False


def _del_id3_frames_by_type(audio_file: Any, frame_id: str) -> None:
    """Delete all ID3 frames of a type regardless of language/description.

    COMM/USLT frame keys carry a language+desc suffix (e.g. ``COMM::eng``,
    ``COMM:remark:fra``); deleting only ``COMM::eng`` leaves other-language
    frames behind, and a subsequent write would accumulate duplicates (#4133).
    """
    stale = [k for k in audio_file.keys() if k == frame_id or k.startswith(frame_id + ':')]
    for key in stale:
        del audio_file[key]


def _existing_total(existing: Any) -> str | None:
    """Return the ``M`` of an existing ``"N/M"`` track/disc tag, if any.

    Accepts the shapes mutagen hands back: an ID3 frame (``.text`` list), a
    Vorbis comment list of strings, or a plain string.
    """
    if existing is None:
        return None
    text = getattr(existing, 'text', existing)
    if isinstance(text, (list, tuple)):
        text = text[0] if text else None
    if text is None:
        return None
    parts = str(text).split('/')
    if len(parts) == 2 and parts[1].strip():
        return parts[1].strip()
    return None


def _with_existing_total(value: Any, existing: Any) -> str:
    """Keep the stored total when ``value`` carries only a number (#5506).

    The API types track/disc as a bare int, and the edit dialog re-sends the
    whole form, so a title-only edit used to rewrite ``"3/12"`` as ``"3"``.
    A value that names its own total (``"4/10"``) is written as given.
    """
    text = str(value)
    if '/' in text:
        return text
    total = _existing_total(existing)
    return f"{text}/{total}" if total is not None else text


class MetadataWriters:
    """Format-specific metadata writers"""

    @staticmethod
    def write_mp3_metadata(audio_file: Any, metadata: dict[str, Any]) -> None:
        """
        Write metadata to MP3 file

        Args:
            audio_file: Mutagen audio file object
            metadata: Dictionary of metadata fields to write
        """
        # Ensure ID3 tags exist
        if audio_file.tags is None:
            audio_file.add_tags()

        tag_map: dict[str, str] = TAG_MAPPINGS['mp3']

        for field, value in metadata.items():
            if field not in tag_map:
                continue

            tag_key: str = tag_map[field]

            if value is None or value == '':
                # Remove tag. For language-tagged frames (COMM/USLT) clear every
                # language variant, not just the ::eng one (#4133).
                if '::' in tag_key:
                    _del_id3_frames_by_type(audio_file, tag_key.split('::', 1)[0])
                elif tag_key in audio_file:
                    del audio_file[tag_key]
            else:
                # Set tag
                if field == 'title':
                    audio_file['TIT2'] = TIT2(encoding=3, text=str(value))  # type: ignore[no-untyped-call]
                elif field == 'artist':
                    audio_file['TPE1'] = TPE1(encoding=3, text=str(value))  # type: ignore[no-untyped-call]
                elif field == 'album':
                    audio_file['TALB'] = TALB(encoding=3, text=str(value))  # type: ignore[no-untyped-call]
                elif field == 'albumartist':
                    audio_file['TPE2'] = TPE2(encoding=3, text=str(value))  # type: ignore[no-untyped-call]
                elif field == 'year':
                    audio_file['TDRC'] = TDRC(encoding=3, text=str(value))  # type: ignore[no-untyped-call]
                elif field == 'genre':
                    audio_file['TCON'] = TCON(encoding=3, text=str(value))  # type: ignore[no-untyped-call]
                elif field == 'track':
                    text = _with_existing_total(value, audio_file.get('TRCK'))
                    audio_file['TRCK'] = TRCK(encoding=3, text=text)  # type: ignore[no-untyped-call]
                elif field == 'disc':
                    text = _with_existing_total(value, audio_file.get('TPOS'))
                    audio_file['TPOS'] = TPOS(encoding=3, text=text)  # type: ignore[no-untyped-call]
                elif field == 'comment':
                    # Replace any existing comment frame (any language) so we
                    # don't accumulate duplicate COMM frames (#4133).
                    _del_id3_frames_by_type(audio_file, 'COMM')
                    audio_file['COMM::eng'] = COMM(encoding=3, lang='eng', desc='', text=str(value))  # type: ignore[no-untyped-call]

    @staticmethod
    def write_flac_metadata(audio_file: Any, metadata: dict[str, Any]) -> None:
        """
        Write metadata to FLAC file

        Args:
            audio_file: Mutagen audio file object
            metadata: Dictionary of metadata fields to write
        """
        tag_map: dict[str, str] = TAG_MAPPINGS['flac']

        for field, value in metadata.items():
            if field not in tag_map:
                continue

            tag_key: str = tag_map[field]

            if value is None or value == '':
                # Remove tag
                if tag_key in audio_file:
                    del audio_file[tag_key]
            elif field in ('track', 'disc'):
                audio_file[tag_key] = _with_existing_total(value, audio_file.get(tag_key))
            else:
                # Set tag
                audio_file[tag_key] = str(value)

    @staticmethod
    def write_mp4_metadata(audio_file: Any, metadata: dict[str, Any]) -> None:
        """
        Write metadata to MP4/M4A file

        Args:
            audio_file: Mutagen audio file object
            metadata: Dictionary of metadata fields to write
        """
        tag_map: dict[str, str] = TAG_MAPPINGS['m4a']

        for field, value in metadata.items():
            if field not in tag_map:
                continue

            tag_key: str = tag_map[field]

            if value is None or value == '':
                # Remove tag
                if tag_key in audio_file:
                    del audio_file[tag_key]
            else:
                # Set tag (handle special MP4 types)
                if field in ('track', 'disc'):
                    # Parse "number/total" format
                    parts: list[str] = str(value).split('/')
                    if len(parts) == 2:
                        audio_file[tag_key] = [(int(parts[0]), int(parts[1]))]
                    else:
                        # A bare number keeps the stored total (#5506).
                        existing = audio_file.get(tag_key)
                        total = existing[0][1] if existing and len(existing[0]) > 1 else 0
                        audio_file[tag_key] = [(int(parts[0]), total)]
                else:
                    audio_file[tag_key] = [str(value)]

    @staticmethod
    def write_ogg_metadata(audio_file: Any, metadata: dict[str, Any]) -> None:
        """
        Write metadata to OGG file

        Args:
            audio_file: Mutagen audio file object
            metadata: Dictionary of metadata fields to write
        """
        # Same as FLAC (Vorbis comments)
        MetadataWriters.write_flac_metadata(audio_file, metadata)

    @staticmethod
    def write_generic_metadata(audio_file: Any, metadata: dict[str, Any]) -> None:
        """
        Write metadata using generic method

        Args:
            audio_file: Mutagen audio file object
            metadata: Dictionary of metadata fields to write
        """
        if audio_file.tags is None:
            audio_file.add_tags()

        for field, value in metadata.items():
            if value is None or value == '':
                if field in audio_file:
                    del audio_file[field]
            else:
                audio_file[field] = str(value)
