# -*- coding: utf-8 -*-

"""
Duplicate Detector
~~~~~~~~~~~~~~~~~

Audio file duplicate detection based on content hashing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import List, Dict

from ...utils.logging import error


class DuplicateDetector:
    """
    Detects duplicate audio files based on content hash

    Strategy:
    - Uses fast content-based hashing
    - Groups files with identical hashes
    - Can scan directories or entire library
    """

    def __init__(self, file_discovery, audio_analyzer):
        """
        Initialize duplicate detector

        Args:
            file_discovery: FileDiscovery instance
            audio_analyzer: AudioAnalyzer instance
        """
        self.file_discovery = file_discovery
        self.audio_analyzer = audio_analyzer

    def find_duplicates(self, directories: List[str] = None) -> List[List[str]]:
        """
        Find duplicate audio files based on content hash

        Args:
            directories: Specific directories to check, or None for entire library

        Returns:
            List of lists, where each inner list contains paths of duplicate files
        """
        try:
            duplicates = []
            hash_to_files: Dict[str, List[str]] = {}

            if directories:
                # Scan specific directories
                for directory in directories:
                    for file_path in self.file_discovery.discover_audio_files(directory, True):
                        file_hash = self.audio_analyzer.calculate_file_hash(file_path)
                        if file_hash:
                            if file_hash in hash_to_files:
                                hash_to_files[file_hash].append(file_path)
                            else:
                                hash_to_files[file_hash] = [file_path]
            else:
                # Check entire library
                # This would query the database for all tracks with file hashes
                # For now, return empty list
                pass

            # Find duplicates (files with same hash)
            for file_hash, files in hash_to_files.items():
                if len(files) > 1:
                    duplicates.append(files)

            return duplicates

        except Exception as e:
            error(f"Duplicate detection failed: {e}")
            return []
