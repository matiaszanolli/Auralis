# -*- coding: utf-8 -*-

"""
XSPF Playlist Format Handler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handles XSPF (XML Shareable Playlist Format) export and import for queue operations.

XSPF Format:
- XML-based playlist format with rich metadata support
- Industry standard with proper encoding
- Supports track titles, artists, albums, durations
- More structured than M3U

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import List, Dict, Any, Tuple
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom
import logging

logger = logging.getLogger(__name__)


class XSPFHandler:
    """Handler for XSPF playlist format"""

    XSPF_NS = 'http://xspf.org/ns/0/'
    XSPF_VERSION = '1'

    @staticmethod
    def export(tracks: List[Dict[str, Any]], title: str = 'Queue') -> str:
        """
        Export tracks to XSPF format

        Args:
            tracks: List of track dictionaries
            title: Playlist title

        Returns:
            XSPF format string (XML)

        Example:
            >>> tracks = [
            ...     {
            ...         'filepath': 'file:///music/song1.mp3',
            ...         'title': 'Song 1',
            ...         'artists': ['Artist Name'],
            ...         'duration': 180
            ...     }
            ... ]
            >>> xspf_content = XSPFHandler.export(tracks)
        """
        # Create root playlist element
        playlist = ET.Element('playlist')
        playlist.set('version', XSPFHandler.XSPF_VERSION)
        playlist.set('xmlns', XSPFHandler.XSPF_NS)

        # Add metadata
        title_elem = ET.SubElement(playlist, 'title')
        title_elem.text = title

        # Add track list
        tracklist = ET.SubElement(playlist, 'trackList')

        for track in tracks:
            track_elem = ET.SubElement(tracklist, 'track')

            # File location (required in XSPF)
            location = ET.SubElement(track_elem, 'location')
            filepath = track.get('filepath', '')
            # Convert to file:// URI if not already
            if filepath and not filepath.startswith(('http://', 'https://', 'file://')):
                filepath = f'file://{Path(filepath).as_posix()}'
            location.text = filepath

            # Title
            title_elem = ET.SubElement(track_elem, 'title')
            title_elem.text = track.get('title', Path(track.get('filepath', '')).stem)

            # Artist(s)
            artists = track.get('artists', [])
            if artists:
                if isinstance(artists, list):
                    for artist in artists:
                        creator = ET.SubElement(track_elem, 'creator')
                        creator.text = str(artist)
                else:
                    creator = ET.SubElement(track_elem, 'creator')
                    creator.text = str(artists)

            # Album
            album = track.get('album')
            if album:
                album_elem = ET.SubElement(track_elem, 'album')
                album_elem.text = str(album)

            # Duration in milliseconds
            duration = track.get('duration')
            if duration:
                duration_elem = ET.SubElement(track_elem, 'duration')
                # Convert seconds to milliseconds
                duration_ms = int(float(duration) * 1000)
                duration_elem.text = str(duration_ms)

        # Pretty print XML
        xml_str = minidom.parseString(ET.tostring(playlist)).toprettyxml(indent='  ')

        # Remove XML declaration and extra newlines
        lines = xml_str.split('\n')
        lines = [line for line in lines if line.strip()]
        # Re-add XML declaration
        result = '<?xml version="1.0" encoding="UTF-8"?>\n' + '\n'.join(lines[1:])

        return result

    @staticmethod
    def import_from_string(content: str, base_path: str = '') -> Tuple[List[str], List[str]]:
        """
        Import XSPF format string and extract file paths

        Args:
            content: XSPF content as string
            base_path: Base directory for relative file:// paths

        Returns:
            Tuple of (filepaths, errors)
        """
        filepaths = []
        errors = []

        try:
            root = ET.fromstring(content)

            # Handle namespace
            ns = {'xspf': XSPFHandler.XSPF_NS}

            # Find all track elements
            tracks = root.findall('.//xspf:track', ns)

            if not tracks:
                errors.append('No tracks found in XSPF playlist')
                return filepaths, errors

            for track in tracks:
                location = track.find('xspf:location', ns)

                if location is not None and location.text:
                    filepath = location.text.strip()

                    # Convert file:// URI to filesystem path
                    if filepath.startswith('file://'):
                        filepath = filepath[7:]  # Remove file://

                    # Handle relative paths
                    if base_path and not Path(filepath).is_absolute():
                        filepath = str(Path(base_path) / filepath)

                    filepaths.append(filepath)

            if not filepaths:
                errors.append('No valid track locations found in XSPF')

        except ET.ParseError as e:
            errors.append(f'Invalid XSPF XML: {str(e)}')
        except Exception as e:
            errors.append(f'Error parsing XSPF: {str(e)}')

        return filepaths, errors

    @staticmethod
    def import_from_file(filepath: str) -> Tuple[List[str], List[str]]:
        """
        Import XSPF file and extract file paths

        Args:
            filepath: Path to XSPF file

        Returns:
            Tuple of (filepaths, errors)

        Raises:
            FileNotFoundError: If XSPF file not found
            ValueError: If file cannot be read
        """
        try:
            file_path = Path(filepath)

            if not file_path.exists():
                raise FileNotFoundError(f'XSPF file not found: {filepath}')

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Use directory of XSPF file as base for relative paths
            base_path = str(file_path.parent)

            return XSPFHandler.import_from_string(content, base_path)

        except FileNotFoundError as e:
            raise e
        except Exception as e:
            raise ValueError(f'Failed to read XSPF file: {str(e)}')

    @staticmethod
    def validate(content: str) -> Tuple[bool, List[str]]:
        """
        Validate XSPF content

        Args:
            content: XSPF content to validate

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        try:
            root = ET.fromstring(content)

            # Check root element
            if not root.tag.endswith('playlist'):
                errors.append('Root element is not a playlist')
                return False, errors

            # Check for tracks
            ns = {'xspf': XSPFHandler.XSPF_NS}
            tracks = root.findall('.//xspf:track', ns)

            if not tracks:
                errors.append('No tracks found in XSPF playlist')
                return False, errors

            # Validate each track has location
            valid_tracks = 0
            for track in tracks:
                location = track.find('xspf:location', ns)
                if location is not None and location.text:
                    valid_tracks += 1

            if valid_tracks == 0:
                errors.append('No tracks have valid location elements')
                return False, errors

            return True, errors

        except ET.ParseError as e:
            errors.append(f'Invalid XSPF XML: {str(e)}')
            return False, errors
        except Exception as e:
            errors.append(f'Error validating XSPF: {str(e)}')
            return False, errors

    @staticmethod
    def supports_format(filename: str) -> bool:
        """
        Check if filename suggests XSPF format

        Args:
            filename: Filename to check

        Returns:
            True if XSPF format is indicated
        """
        return filename.lower().endswith(('.xspf', '.spf'))
