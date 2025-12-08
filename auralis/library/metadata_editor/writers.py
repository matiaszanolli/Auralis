# -*- coding: utf-8 -*-

"""
Metadata Writers
~~~~~~~~~~~~~~~~

Format-specific metadata writing functions

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Dict, Any

from .tag_mappings import TAG_MAPPINGS

try:
    from mutagen.id3 import TIT2, TPE1, TALB, TPE2, TDRC, TCON, TRCK, TPOS, COMM  # type: ignore[attr-defined]
    MUTAGEN_ID3_AVAILABLE: bool = True
except ImportError:
    MUTAGEN_ID3_AVAILABLE = False


class MetadataWriters:
    """Format-specific metadata writers"""

    @staticmethod
    def write_mp3_metadata(audio_file: Any, metadata: Dict[str, Any]) -> None:
        """
        Write metadata to MP3 file

        Args:
            audio_file: Mutagen audio file object
            metadata: Dictionary of metadata fields to write
        """
        # Ensure ID3 tags exist
        if audio_file.tags is None:
            audio_file.add_tags()

        tag_map: Dict[str, str] = TAG_MAPPINGS['mp3']

        for field, value in metadata.items():
            if field not in tag_map:
                continue

            tag_key: str = tag_map[field]

            if value is None or value == '':
                # Remove tag
                if tag_key in audio_file:
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
                    audio_file['TRCK'] = TRCK(encoding=3, text=str(value))  # type: ignore[no-untyped-call]
                elif field == 'disc':
                    audio_file['TPOS'] = TPOS(encoding=3, text=str(value))  # type: ignore[no-untyped-call]
                elif field == 'comment':
                    audio_file['COMM::eng'] = COMM(encoding=3, lang='eng', desc='', text=str(value))  # type: ignore[no-untyped-call]

    @staticmethod
    def write_flac_metadata(audio_file: Any, metadata: Dict[str, Any]) -> None:
        """
        Write metadata to FLAC file

        Args:
            audio_file: Mutagen audio file object
            metadata: Dictionary of metadata fields to write
        """
        tag_map: Dict[str, str] = TAG_MAPPINGS['flac']

        for field, value in metadata.items():
            if field not in tag_map:
                continue

            tag_key: str = tag_map[field]

            if value is None or value == '':
                # Remove tag
                if tag_key in audio_file:
                    del audio_file[tag_key]
            else:
                # Set tag
                audio_file[tag_key] = str(value)

    @staticmethod
    def write_mp4_metadata(audio_file: Any, metadata: Dict[str, Any]) -> None:
        """
        Write metadata to MP4/M4A file

        Args:
            audio_file: Mutagen audio file object
            metadata: Dictionary of metadata fields to write
        """
        tag_map: Dict[str, str] = TAG_MAPPINGS['m4a']

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
                        audio_file[tag_key] = [(int(parts[0]), 0)]
                else:
                    audio_file[tag_key] = [str(value)]

    @staticmethod
    def write_ogg_metadata(audio_file: Any, metadata: Dict[str, Any]) -> None:
        """
        Write metadata to OGG file

        Args:
            audio_file: Mutagen audio file object
            metadata: Dictionary of metadata fields to write
        """
        # Same as FLAC (Vorbis comments)
        MetadataWriters.write_flac_metadata(audio_file, metadata)

    @staticmethod
    def write_generic_metadata(audio_file: Any, metadata: Dict[str, Any]) -> None:
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
