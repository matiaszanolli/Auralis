# -*- coding: utf-8 -*-

"""
Metadata Readers
~~~~~~~~~~~~~~~~

Format-specific metadata reading functions

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any, Dict, Optional

from .tag_mappings import TAG_MAPPINGS


class MetadataReaders:
    """Format-specific metadata readers"""

    @staticmethod
    def read_mp3_metadata(audio_file: Any) -> Dict[str, Optional[str]]:
        """
        Read metadata from MP3 file

        Args:
            audio_file: Mutagen audio file object

        Returns:
            Dictionary of metadata fields
        """
        metadata = {}
        tag_map = TAG_MAPPINGS['mp3']

        for field, tag_key in tag_map.items():
            if tag_key in audio_file:
                value = audio_file[tag_key]
                if field in ('track', 'disc'):
                    # Handle track/disc as string "number/total"
                    metadata[field] = str(value) if value else None
                else:
                    metadata[field] = str(value) if value else None

        return metadata

    @staticmethod
    def read_flac_metadata(audio_file: Any) -> Dict[str, Optional[str]]:
        """
        Read metadata from FLAC file

        Args:
            audio_file: Mutagen audio file object

        Returns:
            Dictionary of metadata fields
        """
        metadata = {}
        tag_map = TAG_MAPPINGS['flac']

        for field, tag_key in tag_map.items():
            if tag_key in audio_file:
                value = audio_file[tag_key]
                if isinstance(value, list) and value:
                    value = value[0]
                metadata[field] = str(value) if value else None

        return metadata

    @staticmethod
    def read_mp4_metadata(audio_file: Any) -> Dict[str, Optional[str]]:
        """
        Read metadata from MP4/M4A file

        Args:
            audio_file: Mutagen audio file object

        Returns:
            Dictionary of metadata fields
        """
        metadata: Dict[str, Optional[str]] = {}
        tag_map = TAG_MAPPINGS['m4a']

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

    @staticmethod
    def read_ogg_metadata(audio_file: Any) -> Dict[str, Optional[str]]:
        """
        Read metadata from OGG file

        Args:
            audio_file: Mutagen audio file object

        Returns:
            Dictionary of metadata fields
        """
        # Same as FLAC (Vorbis comments)
        return MetadataReaders.read_flac_metadata(audio_file)

    @staticmethod
    def read_generic_metadata(audio_file: Any) -> Dict[str, Optional[str]]:
        """
        Read metadata using generic method

        Args:
            audio_file: Mutagen audio file object

        Returns:
            Dictionary of metadata fields
        """
        metadata = {}
        if hasattr(audio_file, 'tags') and audio_file.tags:
            for key, value in audio_file.tags.items():
                if isinstance(value, list) and value:
                    value = value[0]
                metadata[str(key).lower()] = str(value) if value else None
        return metadata
