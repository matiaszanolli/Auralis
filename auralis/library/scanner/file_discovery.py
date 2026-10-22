"""
File Discovery
~~~~~~~~~~~~~

Recursive directory scanning and audio file discovery

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
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
                for file_path in directory_path.iterdir():
                    if self.should_stop:
                        return
                    if (
                        file_path.is_file()
                        and file_path.suffix.lower() in AUDIO_EXTENSIONS
                        and not self.should_skip_path(file_path)
                    ):
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

        Deliberately no containment check: a symlinked subdirectory is
        followed even when its resolved target lies outside the originally
        scanned root, with no comparison against that root anywhere in this
        function (#4823). This is intentional, not an oversight — it matches
        `validate_user_chosen_directory()`'s explicit policy of trusting a
        user-selected scan folder without restricting to predefined media
        directories (single-user desktop app, no privilege boundary crossed).
        Symlinked libraries spanning multiple physical volumes are a
        legitimate use case this would otherwise break. The concrete side
        effect this produces — a `Track.filepath` that can fall outside
        `get_allowed_directories()`, readable via routes that skip
        `validate_file_path` while rejected by routes that call it — is
        addressed by making every DB-filepath consumer call
        `validate_file_path` consistently (#4814/#4817/#4818/#4345, all
        fixed), not by adding containment here.
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
                        if self._claim_subdirectory(entry, entry_path, visited_inodes):
                            yield from self._walk_directory(entry_path, visited_inodes, depth + 1)

                    elif entry.is_file(follow_symlinks=True):
                        if self._is_wanted_file(entry_path):
                            yield str(entry_path)

        except PermissionError:
            warning(f"Permission denied accessing directory: {directory}")
        except OSError as e:
            error(f"Error scanning directory {directory}: {e}")

    @staticmethod
    def _claim_subdirectory(
        entry: os.DirEntry[str], entry_path: Path, visited_inodes: set[tuple[int, int]]
    ) -> bool:
        """True if ``entry`` should be descended into; marks its inode visited.

        Skips excluded and hidden names before the stat, directories that
        cannot be stat'ed, and inodes already seen (a circular or duplicate
        symlink -- warned about when the entry is a symlink).
        """
        if entry.name in SKIP_DIRECTORIES:
            return False
        if entry.name.startswith('.') and len(entry.name) > 1:
            return False

        try:
            real_stat = entry_path.stat()
            inode_key = (real_stat.st_dev, real_stat.st_ino)
        except OSError:
            return False

        if inode_key in visited_inodes:
            if entry.is_symlink():
                warning(f"Circular symlink detected, skipping: {entry_path}")
            return False

        visited_inodes.add(inode_key)
        return True

    def _is_wanted_file(self, entry_path: Path) -> bool:
        """An audio-extension file that is not under a skipped path."""
        return entry_path.suffix.lower() in AUDIO_EXTENSIONS and not self.should_skip_path(entry_path)

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
