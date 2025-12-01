# -*- coding: utf-8 -*-

"""
M3U Playlist Format Handler
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handles M3U playlist format export and import for queue operations.

M3U Format:
- Simple text format with one file per line
- Supports optional Extended M3U (#EXTM3U, #EXTINF) for metadata
- Industry standard for playlists

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import List, Dict, Any, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class M3UHandler:
    """Handler for M3U playlist format"""

    # M3U file signatures
    EXTM3U_HEADER = '#EXTM3U'
    EXTINF_PREFIX = '#EXTINF:'
    EXT_ENCODING_PREFIX = '#EXT-X-ENCODING:'

    @staticmethod
    def export(tracks: List[Dict[str, Any]], extended: bool = True) -> str:
        """
        Export tracks to M3U format

        Args:
            tracks: List of track dictionaries with 'filepath' and optional metadata
            extended: Use Extended M3U format (with #EXTINF metadata)

        Returns:
            M3U format string

        Example:
            >>> tracks = [
            ...     {'filepath': '/music/song1.mp3', 'title': 'Song 1', 'duration': 180},
            ...     {'filepath': '/music/song2.mp3', 'title': 'Song 2', 'duration': 240}
            ... ]
            >>> m3u_content = M3UHandler.export(tracks)
        """
        lines = []

        # Add extended M3U header if requested
        if extended:
            lines.append(M3UHandler.EXTM3U_HEADER)
            lines.append(f'{M3UHandler.EXT_ENCODING_PREFIX}UTF-8')

        # Add tracks
        for track in tracks:
            filepath = track.get('filepath', '')

            if extended:
                # Extended M3U format with metadata
                duration = int(track.get('duration', 0)) if track.get('duration') else -1
                title = track.get('title', Path(filepath).stem)
                artist = track.get('artists', ['Unknown'])

                # Format artist string
                if isinstance(artist, list):
                    artist_str = ', '.join(artist) if artist else 'Unknown'
                else:
                    artist_str = str(artist)

                extinf = f'{M3UHandler.EXTINF_PREFIX}{duration},{artist_str} - {title}'
                lines.append(extinf)

            # Add filepath
            lines.append(filepath)

        return '\n'.join(lines)

    @staticmethod
    def import_from_string(content: str, base_path: str = '') -> Tuple[List[str], List[str]]:
        """
        Import M3U format string and extract file paths

        Args:
            content: M3U file content as string
            base_path: Base directory for relative paths

        Returns:
            Tuple of (filepaths, errors) where:
            - filepaths: List of file paths from playlist
            - errors: List of validation warnings/errors

        Example:
            >>> m3u_content = '''#EXTM3U
            ... #EXTINF:180,Artist - Song 1
            ... /music/song1.mp3
            ... /music/song2.mp3
            ... '''
            >>> paths, errors = M3UHandler.import_from_string(m3u_content)
        """
        filepaths = []
        errors = []
        lines = content.strip().split('\n')

        for line in lines:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Handle relative paths
            if base_path and not Path(line).is_absolute():
                full_path = str(Path(base_path) / line)
            else:
                full_path = line

            filepaths.append(full_path)

        if not filepaths:
            errors.append('No valid file paths found in M3U file')

        return filepaths, errors

    @staticmethod
    def import_from_file(filepath: str) -> Tuple[List[str], List[str]]:
        """
        Import M3U file and extract file paths

        Args:
            filepath: Path to M3U file

        Returns:
            Tuple of (filepaths, errors)

        Raises:
            FileNotFoundError: If M3U file not found
            ValueError: If file cannot be read
        """
        try:
            file_path = Path(filepath)

            if not file_path.exists():
                raise FileNotFoundError(f'M3U file not found: {filepath}')

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Use directory of M3U file as base for relative paths
            base_path = str(file_path.parent)

            return M3UHandler.import_from_string(content, base_path)

        except FileNotFoundError as e:
            raise e
        except Exception as e:
            raise ValueError(f'Failed to read M3U file: {str(e)}')

    @staticmethod
    def validate(content: str) -> Tuple[bool, List[str]]:
        """
        Validate M3U content

        Args:
            content: M3U content to validate

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []
        lines = content.strip().split('\n')

        if not lines:
            errors.append('M3U file is empty')
            return False, errors

        # Check for M3U signature (optional but recommended)
        if not content.startswith('#EXTM3U') and not content.startswith('#M3U'):
            # Not a fatal error, but worth noting
            logger.warning('M3U file does not start with #EXTM3U or #M3U header')

        # Count valid entries
        valid_entries = 0
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                valid_entries += 1

        if valid_entries == 0:
            errors.append('M3U file contains no valid file paths')
            return False, errors

        return True, errors

    @staticmethod
    def supports_format(filename: str) -> bool:
        """
        Check if filename suggests M3U format

        Args:
            filename: Filename to check

        Returns:
            True if M3U format is indicated
        """
        return filename.lower().endswith(('.m3u', '.m3u8'))
