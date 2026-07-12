"""
Duplicate Detector
~~~~~~~~~~~~~~~~~

Audio file duplicate detection based on content hashing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any

from ...utils.logging import debug, error

# Page size for the whole-library scan (#4241) — mirrors the batching
# pattern used elsewhere (e.g. TrackRepository.cleanup_missing_files) to
# keep memory bounded regardless of library size.
_LIBRARY_SCAN_BATCH_SIZE = 500


class DuplicateDetector:
    """
    Detects duplicate audio files based on content hash

    Strategy:
    - Uses fast content-based hashing
    - Groups files with identical hashes
    - Can scan directories or entire library
    """

    def __init__(self, file_discovery: Any, audio_analyzer: Any, library_manager: Any | None = None) -> None:
        """
        Initialize duplicate detector

        Args:
            file_discovery: FileDiscovery instance
            audio_analyzer: AudioAnalyzer instance
            library_manager: Optional LibraryManager, required for
                find_duplicates(directories=None) (whole-library dedup, #4241).
        """
        self.file_discovery = file_discovery
        self.audio_analyzer = audio_analyzer
        self.library_manager = library_manager

    def find_duplicates(self, directories: list[str] | None = None) -> list[list[str]]:
        """
        Find duplicate audio files based on content hash

        Args:
            directories: Specific directories to check, or None for entire library

        Returns:
            List of lists, where each inner list contains paths of duplicate files

        Raises:
            NotImplementedError: If directories is None and no library_manager
                was supplied at construction time (#4241).
        """
        try:
            duplicates = []
            hash_to_files: dict[str, list[str]] = {}

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
                self._hash_entire_library(hash_to_files)

            # Find duplicates (files with same hash)
            for file_hash, files in hash_to_files.items():
                if len(files) > 1:
                    duplicates.append(files)

            return duplicates

        except NotImplementedError:
            raise
        except Exception as e:
            error(f"Duplicate detection failed: {e}")
            return []

    def _hash_entire_library(self, hash_to_files: dict[str, list[str]]) -> None:
        """Page through every track in the library and hash its file, in place (#4241).

        There is no persisted file-hash column on Track, so this mirrors the
        directory branch's per-file hashing, just sourced from the DB instead
        of a filesystem walk. Tracks whose file has moved or been deleted
        since the last scan are skipped (cleanup_missing_files handles that
        separately) rather than aborting the whole scan.
        """
        if self.library_manager is None:
            raise NotImplementedError(
                "find_duplicates(directories=None) requires a library_manager "
                "to query the entire library; pass directories explicitly or "
                "construct DuplicateDetector with a library_manager."
            )

        offset = 0
        while True:
            tracks, total = self.library_manager.get_all_tracks(
                limit=_LIBRARY_SCAN_BATCH_SIZE, offset=offset
            )
            if not tracks:
                break
            for track in tracks:
                file_path = track.filepath
                try:
                    file_hash = self.audio_analyzer.calculate_file_hash(file_path)
                except OSError as e:
                    debug(f"Skipping unreadable file during whole-library dedup: {file_path} ({e})")
                    continue
                if file_hash:
                    hash_to_files.setdefault(file_hash, []).append(file_path)
            offset += _LIBRARY_SCAN_BATCH_SIZE
            if offset >= total:
                break
