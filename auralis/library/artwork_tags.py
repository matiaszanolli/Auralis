"""
Embedded-artwork readers for ArtworkExtractor (split from artwork.py, #5837):
one reader per tag family, each returning ``(image bytes, mime type)`` or
``(None, None)`` and never raising.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3
from mutagen.mp4 import MP4, MP4Cover

from ..utils.logging import debug


class TagArtworkReadersMixin:
    """The per-format ``_extract_from_*`` readers."""

    def _extract_from_id3(self, audio_file: Any) -> tuple[bytes | None, str | None]:
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

    def _extract_from_mp4(self, audio_file: MP4) -> tuple[bytes | None, str | None]:
        """Extract artwork from MP4/M4A files"""
        try:
            if audio_file.tags and 'covr' in audio_file.tags:  # type: ignore[unreachable]
                cover = audio_file.tags['covr'][0]  # type: ignore[unreachable]
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

    def _extract_from_flac(self, audio_file: FLAC) -> tuple[bytes | None, str | None]:
        """Extract artwork from FLAC files"""
        try:
            if audio_file.pictures:
                picture = audio_file.pictures[0]  # Get first picture
                return picture.data, picture.mime

        except Exception as e:
            debug(f"Failed to extract from FLAC: {e}")

        return None, None

    def _extract_from_generic(self, audio_file: Any) -> tuple[bytes | None, str | None]:
        """Extract artwork from generic tag formats (OGG, etc.)"""
        try:
            tags = audio_file.tags

            # Try common artwork tag names
            artwork_keys = ['COVERART', 'COVER', 'METADATA_BLOCK_PICTURE']

            import base64

            for key in artwork_keys:
                if key in tags:
                    # Handle base64-encoded artwork (Vorbis comments)
                    if key == 'METADATA_BLOCK_PICTURE':
                        picture_data = base64.b64decode(tags[key][0])
                        # Parse FLAC Picture block
                        picture = Picture(picture_data)  # type: ignore[no-untyped-call]
                        return picture.data, picture.mime
                    else:
                        # Legacy COVERART/COVER store the image as a base64 STRING;
                        # decode to bytes so _save_artwork (hashlib.md5 / binary
                        # write) doesn't TypeError and silently drop the art (#4121).
                        return base64.b64decode(tags[key][0]), 'image/jpeg'

        except Exception as e:
            debug(f"Failed to extract from generic tags: {e}")

        return None, None
