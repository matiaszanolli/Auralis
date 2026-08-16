"""
Path Security Utilities
~~~~~~~~~~~~~~~~~~~~~~~

Path validation and sanitization to prevent directory traversal attacks.

Fixes #2069: Path traversal in directory scanning endpoint

Trust model (#4799): Auralis is a single-user desktop app where directories
come from the user's own file picker, not an untrusted network client. Every
real directory entry point (``LibraryScanRequest.validate_directory_paths``
in ``schemas.py``, ``POST /api/settings/scan-folders``) validates through
``validate_user_chosen_directory()`` / ``validate_directory_list()``, which
enforce basic safety (no traversal, must exist, must be readable) but
deliberately do NOT restrict to a fixed allowlist — the user's choice is
trusted. Registering a folder via ``register_allowed_directory()`` then
widens the allowlist ``validate_file_path()`` consults for the rest of the
session. There is intentionally no separate allowlist-enforcing directory
validator in this module — an earlier one (``validate_scan_path``) existed
unused alongside this posture and was removed as dead code rather than left
implying a containment guarantee the app doesn't actually enforce.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Default allowed base directories — intentionally excludes bare Path.home()
# to prevent traversal to sensitive files like ~/.ssh or ~/.gnupg (#2562).
DEFAULT_ALLOWED_DIRS = [
    Path.home() / "Music",      # Standard music directory
    Path.home() / "Documents",  # Documents directory
]

# Extra directories registered at runtime (populated by startup.py after
# reading user-configured scan folders from the database).
_extra_allowed_dirs: list[Path] = []


def register_allowed_directory(directory: Path) -> None:
    """Register an additional allowed directory (called during startup or when adding scan folders)."""
    resolved = directory.resolve()
    if resolved not in _extra_allowed_dirs:
        _extra_allowed_dirs.append(resolved)


def unregister_allowed_directory(directory: Path) -> None:
    """Remove a directory registered via `register_allowed_directory` (fixes #3842).

    Called when a user removes a scan folder, so `validate_file_path()` stops
    trusting it for the rest of the session instead of only on next restart.
    """
    resolved = directory.resolve()
    if resolved in _extra_allowed_dirs:
        _extra_allowed_dirs.remove(resolved)


def clear_extra_allowed_directories() -> None:
    """Remove all runtime-registered extra directories (fixes #3842).

    Called on settings reset, since `reset_to_defaults` wipes the configured
    `scan_folders` list — none of the previously-registered extra directories
    should remain implicitly trusted afterward.
    """
    _extra_allowed_dirs.clear()


class PathValidationError(Exception):
    """Raised when path validation fails."""
    pass


def get_allowed_directories() -> list[Path]:
    """
    Get list of allowed base directories for scanning.

    Returns:
        List of allowed directory paths

    The allow-list is DEFAULT_ALLOWED_DIRS (home plus the standard music
    folders) widened by two configured sources: XDG_MUSIC_DIR, and the scan
    folders registered at runtime into _extra_allowed_dirs. Startup seeds the
    latter from the settings-backed scan-folder allowlist, so this list is
    already configuration-driven — it is not a hardcoded stand-in awaiting one
    (#5145). Non-existent entries are dropped rather than resolved.
    """
    allowed_dirs = DEFAULT_ALLOWED_DIRS.copy()

    # Add XDG_MUSIC_DIR if available (Linux)
    xdg_music = os.environ.get('XDG_MUSIC_DIR')
    if xdg_music:
        allowed_dirs.append(Path(xdg_music))

    # Include user-configured scan folders registered at runtime
    allowed_dirs.extend(_extra_allowed_dirs)

    # Resolve all paths to absolute and normalize
    return [path.resolve() for path in allowed_dirs if path.exists()]


def validate_file_path(
    filepath: str,
    allowed_base_dirs: list[Path] | None = None
) -> Path:
    """
    Validate and sanitize a file path against allowed directories.

    Security checks:
    - Path must be absolute or relative (will be resolved)
    - No path traversal sequences (../)
    - Must fall within allowed base directories
    - Must exist
    - Must be readable

    Args:
        filepath: File path to validate
        allowed_base_dirs: Allowed base directories (default: user home, Music, Documents)

    Returns:
        Resolved absolute Path if valid

    Raises:
        PathValidationError: If path fails validation
    """
    if not filepath:
        raise PathValidationError("File path cannot be empty")

    try:
        path = Path(filepath)
    except (ValueError, TypeError) as e:
        raise PathValidationError(f"Invalid path format: {e}")

    try:
        resolved_path = path.resolve()
    except (OSError, RuntimeError) as e:
        raise PathValidationError(f"Failed to resolve path: {e}")

    if ".." in Path(filepath).parts:
        raise PathValidationError(
            "Path traversal sequences (..) are not allowed."
        )

    if allowed_base_dirs is None:
        allowed_base_dirs = get_allowed_directories()

    is_allowed = False
    for base_dir in allowed_base_dirs:
        try:
            resolved_path.relative_to(base_dir)
            is_allowed = True
            break
        except ValueError:
            continue

    if not is_allowed:
        allowed_dirs_str = ", ".join(str(d) for d in allowed_base_dirs)
        raise PathValidationError(
            f"Path '{resolved_path}' is outside allowed directories. "
            f"Allowed directories: {allowed_dirs_str}"
        )

    if not resolved_path.exists():
        raise PathValidationError(f"File does not exist: {resolved_path}")

    if not resolved_path.is_file():
        raise PathValidationError(f"Path is not a file: {resolved_path}")

    if not os.access(resolved_path, os.R_OK):
        raise PathValidationError(f"File is not readable: {resolved_path}")

    # Debug, not info (#3844): validators run very frequently and the
    # resolved path is sensitive (the user's media library layout) — at INFO
    # it floods logs and gets persisted to electron-log on disk. This one
    # runs 5x per /api/metadata/tracks/{id} request.
    logger.debug(f"File path validation successful: {resolved_path}")
    return resolved_path


def validate_user_chosen_directory(directory: str) -> Path:
    """
    Validate a directory path explicitly chosen by the user (e.g., via file picker).

    Auralis is a single-user desktop app. When the user explicitly selects a
    folder to scan, we trust their choice and only enforce basic safety checks
    (no traversal, must exist, must be readable) without restricting to
    predefined allowed directories.

    Args:
        directory: Directory path chosen by the user

    Returns:
        Resolved absolute Path object if valid

    Raises:
        PathValidationError: If path fails basic safety checks
    """
    if not directory:
        raise PathValidationError("Directory path cannot be empty")

    try:
        path = Path(directory)
    except (ValueError, TypeError) as e:
        raise PathValidationError(f"Invalid path format: {e}")

    try:
        resolved_path = path.resolve()
    except (OSError, RuntimeError) as e:
        raise PathValidationError(f"Failed to resolve path: {e}")

    if ".." in Path(directory).parts:
        raise PathValidationError(
            "Path traversal sequences (..) are not allowed. "
            "Please use absolute paths."
        )

    if not resolved_path.exists():
        raise PathValidationError(f"Directory does not exist: {resolved_path}")

    if not resolved_path.is_dir():
        raise PathValidationError(f"Path is not a directory: {resolved_path}")

    if not os.access(resolved_path, os.R_OK):
        raise PathValidationError(f"Directory is not readable: {resolved_path}")

    # Debug, not info (#3844): avoid persisting the user's chosen folder path
    # to logs on every validation.
    logger.debug(f"User-chosen directory validated: {resolved_path}")
    return resolved_path


def validate_directory_list(directories: list[str]) -> list[str]:
    """Validate a batch of user-chosen directory paths with
    ``validate_user_chosen_directory``, returning the resolved, stringified
    list.

    Shared by every write path that persists ``scan_folders`` — the Pydantic
    ``LibraryScanRequest.directories`` field_validator and ``PUT
    /api/settings``'s ``SettingsUpdateRequest.scan_folders`` handling (#4765)
    — so an entry rejected by one is rejected by the other identically,
    instead of one validating and the other writing it through unchecked.
    Raises on the first invalid entry; a mixed batch does not silently drop
    the bad one and proceed with the rest.

    Raises:
        PathValidationError: naming the offending path, on the first invalid entry.
    """
    validated = []
    for directory in directories:
        try:
            validated.append(str(validate_user_chosen_directory(directory)))
        except PathValidationError as e:
            raise PathValidationError(f"Invalid directory path '{directory}': {e}") from e
    return validated


def sanitize_path_for_response(path: Path | str) -> str:
    """
    Sanitize a file path for inclusion in API responses.

    Converts absolute paths to be relative to user's home directory
    to avoid exposing full system paths.

    Args:
        path: File path to sanitize

    Returns:
        Sanitized path string (relative to home if possible)

    Examples:
        >>> sanitize_path_for_response("/home/user/Music/song.mp3")
        "~/Music/song.mp3"
        >>> sanitize_path_for_response("/var/system/file")
        "/var/system/file"  # Not in home, return as-is
    """
    path_obj = Path(path).resolve()
    home = Path.home()

    try:
        # Try to make relative to home directory
        relative = path_obj.relative_to(home)
        return f"~/{relative}"
    except ValueError:
        # Path is not in home directory, return as-is
        # (This shouldn't happen for music files, but handle gracefully)
        return str(path_obj)
