"""
File Discovery
~~~~~~~~~~~~~

Recursive directory scanning and audio file discovery

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import os
from pathlib import Path
from collections.abc import Generator

from ...utils.logging import debug, error, warning
from .config import AUDIO_EXTENSIONS, SKIP_DIRECTORIES

# Maximum directory nesting depth to traverse (guards against very deep trees)
MAX_SCAN_DEPTH = 50


class FileDiscovery:
    """
    Discovers audio files in directories

    Handles:
    - Recursive directory traversal with symlink cycle detection
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

            if recursive:
                try:
                    root_stat = directory_path.stat()
                    visited_inodes: set[tuple[int, int]] = {(root_stat.st_dev, root_stat.st_ino)}
                except OSError:
                    visited_inodes = set()
                yield from self._walk_directory(directory_path, visited_inodes, depth=0)
            else:
                for ext in AUDIO_EXTENSIONS:
                    for file_path in directory_path.glob(f"*{ext}"):
                        if self.should_stop:
                            return
                        if not self.should_skip_path(file_path) and file_path.is_file():
                            yield str(file_path)

        except PermissionError:
            warning(f"Permission denied accessing directory: {directory}")
        except Exception as e:
            error(f"Error scanning directory {directory}: {e}")

    def _walk_directory(
        self,
        directory: Path,
        visited_inodes: set[tuple[int, int]],
        depth: int,
    ) -> Generator[str]:
        """
        Recursively walk directory, yielding audio file paths.

        Tracks visited directory inodes so that circular symlinks are detected
        and skipped with a warning rather than causing an infinite loop.
        A globally-shared visited set also prevents the same physical directory
        from being emitted twice when multiple symlinks point to it.
        """
        if depth > MAX_SCAN_DEPTH:
            warning(f"Max scan depth ({MAX_SCAN_DEPTH}) exceeded at: {directory}")
            return

        try:
            with os.scandir(directory) as it:
                for entry in it:
                    if self.should_stop:
                        return

                    entry_path = Path(entry.path)

                    if entry.is_dir(follow_symlinks=True):
                        # Skip excluded or hidden directory names before stat
                        if entry.name in SKIP_DIRECTORIES:
                            continue
                        if entry.name.startswith('.') and len(entry.name) > 1:
                            continue

                        try:
                            real_stat = entry_path.stat()
                            inode_key = (real_stat.st_dev, real_stat.st_ino)
                        except OSError:
                            continue

                        if inode_key in visited_inodes:
                            if entry.is_symlink():
                                warning(f"Circular symlink detected, skipping: {entry_path}")
                            continue

                        visited_inodes.add(inode_key)
                        yield from self._walk_directory(entry_path, visited_inodes, depth + 1)

                    elif entry.is_file(follow_symlinks=True):
                        if entry_path.suffix.lower() not in AUDIO_EXTENSIONS:
                            continue
                        if not self.should_skip_path(entry_path):
                            yield str(entry_path)

        except PermissionError:
            warning(f"Permission denied accessing directory: {directory}")
        except OSError as e:
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
