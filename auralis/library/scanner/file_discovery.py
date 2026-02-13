"""
File Discovery
~~~~~~~~~~~~~

Recursive directory scanning and audio file discovery

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from pathlib import Path
from collections.abc import Generator

from ...utils.logging import debug, error, warning
from .config import AUDIO_EXTENSIONS, SKIP_DIRECTORIES


class FileDiscovery:
    """
    Discovers audio files in directories

    Handles:
    - Recursive directory traversal
    - File type filtering
    - Path exclusion (hidden dirs, system dirs)
    - Permission error handling
    """

    def __init__(self) -> None:
        self.should_stop = False

    def stop(self) -> None:
        """Signal discovery to stop"""
        self.should_stop = True

    def discover_audio_files(self, directory: str, recursive: bool = True) -> Generator[str]:
        """
        Discover audio files in directory

        Args:
            directory: Directory path to scan
            recursive: Whether to scan subdirectories

        Yields:
            Absolute file paths of discovered audio files
        """
        try:
            directory_path = Path(directory)
            if not directory_path.exists():
                warning(f"Directory does not exist: {directory}")
                return

            if not directory_path.is_dir():
                warning(f"Path is not a directory: {directory}")
                return

            debug(f"Scanning directory: {directory}")

            # Use appropriate scanning method
            if recursive:
                pattern_method = directory_path.rglob
            else:
                pattern_method = directory_path.glob

            # Find all audio files
            for ext in AUDIO_EXTENSIONS:
                for file_path in pattern_method(f"*{ext}"):
                    if self.should_stop:
                        break

                    # Skip if in excluded directory
                    if self.should_skip_path(file_path):
                        continue

                    # Verify it's actually a file
                    if file_path.is_file():
                        yield str(file_path)

        except PermissionError:
            warning(f"Permission denied accessing directory: {directory}")
        except Exception as e:
            error(f"Error scanning directory {directory}: {e}")

    def should_skip_path(self, file_path: Path) -> bool:
        """
        Check if path should be skipped

        Skips:
        - System directories
        - Hidden directories
        - Version control directories

        Args:
            file_path: Path to check

        Returns:
            True if path should be skipped
        """
        # Check if any parent directory should be skipped
        for parent in file_path.parents:
            if parent.name in SKIP_DIRECTORIES:
                return True

        # Check for hidden files/directories (starting with .)
        for part in file_path.parts:
            if part.startswith('.') and len(part) > 1:
                return True

        return False
