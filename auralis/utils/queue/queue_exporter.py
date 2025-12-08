# -*- coding: utf-8 -*-

"""
Queue Exporter & Importer
~~~~~~~~~~~~~~~~~~~~~~~~~~

High-level utility for exporting and importing queue configurations in multiple formats.

Supported Formats:
- M3U: Simple text format with optional Extended M3U metadata
- XSPF: XML Shareable Playlist Format with rich metadata

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import List, Dict, Any, Tuple, Literal, Optional, cast
from pathlib import Path
import logging

from .m3u_handler import M3UHandler
from .xspf_handler import XSPFHandler

logger = logging.getLogger(__name__)


class QueueExporter:
    """High-level queue export/import utility"""

    SUPPORTED_FORMATS = ('m3u', 'xspf')
    DEFAULT_FORMAT = 'm3u'

    @staticmethod
    def export(tracks: List[Dict[str, Any]],
               format: Literal['m3u', 'xspf'] = 'm3u',
               **kwargs: Any) -> str:
        """
        Export queue to specified format

        Args:
            tracks: List of track dictionaries with 'filepath' and optional metadata
            format: Export format ('m3u' or 'xspf')
            **kwargs: Format-specific options:
                - extended (m3u): Use Extended M3U format (default: True)
                - title (xspf): Playlist title (default: 'Queue')

        Returns:
            Exported playlist content as string

        Raises:
            ValueError: If format not supported

        Example:
            >>> tracks = [{'filepath': '/music/song.mp3', 'title': 'Song'}]
            >>> m3u_content = QueueExporter.export(tracks, format='m3u')
            >>> xspf_content = QueueExporter.export(tracks, format='xspf', title='My Queue')
        """
        format_lower = format.lower()

        if format_lower not in QueueExporter.SUPPORTED_FORMATS:
            raise ValueError(f'Unsupported format: {format_lower}. Supported: {QueueExporter.SUPPORTED_FORMATS}')

        if not tracks:
            logger.warning('Exporting empty queue')

        if format_lower == 'm3u':
            extended = kwargs.get('extended', True)
            return M3UHandler.export(tracks, extended=extended)
        elif format_lower == 'xspf':
            title = kwargs.get('title', 'Queue')
            return XSPFHandler.export(tracks, title=title)
        else:
            raise ValueError(f'Unsupported format: {format_lower}')

    @staticmethod
    def export_to_file(tracks: List[Dict[str, Any]], filepath: str,
                       format: Optional[str] = None, **kwargs: Any) -> Tuple[bool, str]:
        """
        Export queue to file

        Args:
            tracks: List of track dictionaries
            filepath: Path where to save playlist file
            format: Export format (auto-detect from extension if None)
            **kwargs: Format-specific options

        Returns:
            Tuple of (success, message)

        Example:
            >>> success, msg = QueueExporter.export_to_file(
            ...     tracks, '/tmp/my_queue.m3u'
            ... )
        """
        try:
            file_path = Path(filepath)

            # Auto-detect format from extension if not specified
            format_lower = format
            if format_lower is None:
                if M3UHandler.supports_format(str(file_path)):
                    format_lower = 'm3u'
                elif XSPFHandler.supports_format(str(file_path)):
                    format_lower = 'xspf'
                else:
                    format_lower = QueueExporter.DEFAULT_FORMAT

            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Generate content
            content = QueueExporter.export(tracks, format=cast(Literal['m3u', 'xspf'], format_lower), **kwargs)

            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            return True, f'Exported {len(tracks)} tracks to {filepath}'

        except Exception as e:
            error_msg = f'Failed to export queue: {str(e)}'
            logger.error(error_msg)
            return False, error_msg

    @staticmethod
    def import_from_string(content: str, format: Optional[str] = None) -> Tuple[List[str], List[str]]:
        """
        Import queue from string content

        Args:
            content: Playlist content as string
            format: Format type ('m3u' or 'xspf', auto-detect if None)

        Returns:
            Tuple of (filepaths, errors)

        Example:
            >>> m3u_content = '#EXTM3U\\n/music/song.mp3'
            >>> paths, errors = QueueExporter.import_from_string(m3u_content)
        """
        format_lower = format
        if format_lower is None:
            # Auto-detect format
            if content.strip().startswith('<?xml') or content.strip().startswith('<playlist'):
                format_lower = 'xspf'
            else:
                format_lower = 'm3u'

        format_lower = format_lower.lower()

        if format_lower == 'm3u':
            return M3UHandler.import_from_string(content)
        elif format_lower == 'xspf':
            return XSPFHandler.import_from_string(content)
        else:
            return [], [f'Unsupported format: {format_lower}']

    @staticmethod
    def import_from_file(filepath: str, format: Optional[str] = None) -> Tuple[List[str], List[str]]:
        """
        Import queue from file

        Args:
            filepath: Path to playlist file
            format: Format type (auto-detect from extension if None)

        Returns:
            Tuple of (filepaths, errors)

        Raises:
            FileNotFoundError: If file not found
            ValueError: If file cannot be read

        Example:
            >>> paths, errors = QueueExporter.import_from_file('/tmp/my_queue.m3u')
        """
        try:
            file_path = Path(filepath)

            if not file_path.exists():
                raise FileNotFoundError(f'Playlist file not found: {filepath}')

            # Auto-detect format from extension if not specified
            format_lower = format
            if format_lower is None:
                if M3UHandler.supports_format(str(file_path)):
                    format_lower = 'm3u'
                elif XSPFHandler.supports_format(str(file_path)):
                    format_lower = 'xspf'
                else:
                    raise ValueError(f'Cannot auto-detect format for file: {filepath}')

            format_lower = format_lower.lower()

            if format_lower == 'm3u':
                return M3UHandler.import_from_file(filepath)
            elif format_lower == 'xspf':
                return XSPFHandler.import_from_file(filepath)
            else:
                raise ValueError(f'Unsupported format: {format_lower}')

        except (FileNotFoundError, ValueError) as e:
            raise e
        except Exception as e:
            raise ValueError(f'Failed to import playlist: {str(e)}')

    @staticmethod
    def validate(content: str, format: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Validate playlist content

        Args:
            content: Playlist content as string
            format: Format type (auto-detect if None)

        Returns:
            Tuple of (is_valid, errors)

        Example:
            >>> is_valid, errors = QueueExporter.validate(content)
        """
        format_lower = format
        if format_lower is None:
            # Auto-detect format
            if content.strip().startswith('<?xml') or content.strip().startswith('<playlist'):
                format_lower = 'xspf'
            else:
                format_lower = 'm3u'

        format_lower = format_lower.lower()

        if format_lower == 'm3u':
            return M3UHandler.validate(content)
        elif format_lower == 'xspf':
            return XSPFHandler.validate(content)
        else:
            return False, [f'Unsupported format: {format_lower}']

    @staticmethod
    def detect_format(filepath: str) -> str:
        """
        Detect playlist format from filename

        Args:
            filepath: Path to playlist file

        Returns:
            Detected format ('m3u', 'xspf', or 'unknown')
        """
        if M3UHandler.supports_format(filepath):
            return 'm3u'
        elif XSPFHandler.supports_format(filepath):
            return 'xspf'
        else:
            return 'unknown'
