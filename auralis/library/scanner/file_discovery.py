"""
File Discovery
~~~~~~~~~~~~~

Recursive directory scanning and audio file discovery

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import errno
import os
import threading
from pathlib import Path
from collections.abc import Callable, Generator

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

    def __init__(self, should_stop: threading.Event | None = None) -> None:
        """
        Args:
            should_stop: Cancellation Event, shared with the owning scanner so
                one set() stops every stage. A private Event when omitted
                (#6100: a plain bool is an unsynchronised cross-thread publish
                under free-threaded CPython).
        """
        self.should_stop = should_stop if should_stop is not None else threading.Event()
        # #5877: every unreadable directory was a log line only, so a scan of a
        # missing root, a permission-denied album folder or a share that
        # dropped mid-walk reported a normal completion. The owner wires this
        # to ScanResult.record_directory_error; the reason never names a path.
        self.on_directory_error: Callable[[str, str], None] | None = None
        # Whether the last discover_audio_files() root could not be read at
        # all, so the caller does not count it in directories_scanned.
        self.last_root_failed = False

    def _directory_error(self, path: str | Path, reason: str) -> None:
        if self.on_directory_error is not None:
            self.on_directory_error(str(path), reason)

    def stop(self) -> None:
        """Signal discovery to stop"""
        self.should_stop.set()

    def discover_audio_files(self, directory: str, recursive: bool = True) -> Generator[str]:
        """
        Discover audio files in directory

        Args:
            directory: Directory path to scan
            recursive: Whether to scan subdirectories

        Yields:
            Absolute file paths of discovered audio files
        """
        self.last_root_failed = False
        try:
            directory_path = Path(directory)
            if not directory_path.exists():
                warning(f"Directory does not exist: {directory}")
                self._root_failed(directory, "folder not found")
                return

            if not directory_path.is_dir():
                warning(f"Path is not a directory: {directory}")
                self._root_failed(directory, "not a folder")
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
                    if self.should_stop.is_set():
                        return
                    if (
                        file_path.is_file()
                        and file_path.suffix.lower() in AUDIO_EXTENSIONS
                        and not self.should_skip_path(file_path)
                    ):
                        yield str(file_path)

        except PermissionError:
            warning(f"Permission denied accessing directory: {directory}")
            self._root_failed(directory, "permission denied")
        except Exception as e:
            error(f"Error scanning directory {directory}: {e}")
            self._root_failed(directory, f"could not be read ({type(e).__name__})")

    def _root_failed(self, directory: str, reason: str) -> None:
        self.last_root_failed = True
        self._directory_error(directory, reason)

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
            self._directory_error(directory, f"nested deeper than {MAX_SCAN_DEPTH} folders, not scanned")
            return

        try:
            with os.scandir(directory) as it:
                for entry in it:
                    if self.should_stop.is_set():
                        return
                    yield from self._walk_entry(entry, visited_inodes, depth)

        except PermissionError:
            warning(f"Permission denied accessing directory: {directory}")
            self._directory_error(directory, "permission denied")
        except OSError as e:
            error(f"Error scanning directory {directory}: {e}")
            # strerror, not str(e): the latter embeds the path.
            self._directory_error(directory, f"could not be read ({e.strerror or type(e).__name__})")

    def _walk_entry(
        self,
        entry: os.DirEntry[str],
        visited_inodes: set[tuple[int, int]],
        depth: int,
    ) -> Generator[str]:
        """Yield the audio paths under one scandir entry (recursing into
        directories). An entry that cannot be classified is skipped on its own
        (#6116); errors from the recursion are handled by the nested walk."""
        entry_path = Path(entry.path)

        try:
            is_dir = entry.is_dir(follow_symlinks=True)
            is_file = not is_dir and entry.is_file(follow_symlinks=True)
        except OSError as e:
            # DirEntry.is_dir/is_file swallow only FileNotFoundError; a looping
            # or unreadable symlink raised here and aborted the whole directory
            # walk, taking every later sibling and subdirectory with it.
            warning(f"Skipping unreadable entry {entry_path}: {e.strerror or type(e).__name__}")
            if e.errno != errno.ELOOP:  # a symlink loop holds no files, so nothing went unscanned
                self._directory_error(entry_path, f"could not be read ({e.strerror or type(e).__name__})")
            return

        if is_dir:
            if self._claim_subdirectory(entry, entry_path, visited_inodes):
                yield from self._walk_directory(entry_path, visited_inodes, depth + 1)
        elif is_file and self._is_wanted_file(entry_path):
            yield str(entry_path)

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
        """An audio-extension file that is not hidden (directories were filtered on the way down)."""
        return entry_path.suffix.lower() in AUDIO_EXTENSIONS and not self.should_skip_path(entry_path)

    def should_skip_path(self, file_path: Path) -> bool:
        """
        Whether a discovered FILE is hidden (its own name starts with a dot).

        Only the file's own name counts. Excluded and hidden directories below the
        scan root are never descended into (``_claim_subdirectory``), and the root
        itself and its ancestors are the user's choice: testing every component of
        the absolute path made a root such as ``~/.local/share/music`` (or any path
        containing ``node_modules``/``.git`` above the root) skip every file and
        report an empty scan (#5594).

        Args:
            file_path: Path to check

        Returns:
            True if the file is hidden
        """
        name = file_path.name
        return name.startswith('.') and len(name) > 1
