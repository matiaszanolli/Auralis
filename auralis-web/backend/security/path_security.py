"""
Path Security Utilities
~~~~~~~~~~~~~~~~~~~~~~~

Path validation and sanitization to prevent directory traversal attacks.

Fixes #2069: Path traversal in directory scanning endpoint

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default allowed base directories
DEFAULT_ALLOWED_DIRS = [
    Path.home(),  # User's home directory
    Path.home() / "Music",  # Standard music directory
    Path.home() / "Documents",  # Documents directory
]


class PathValidationError(Exception):
    """Raised when path validation fails."""
    pass


def get_allowed_directories() -> list[Path]:
    """
    Get list of allowed base directories for scanning.

    Returns:
        List of allowed directory paths

    Note:
        In production, this should read from configuration.
        For now, we default to user's home directory and standard music folders.
    """
    allowed_dirs = DEFAULT_ALLOWED_DIRS.copy()

    # Add XDG_MUSIC_DIR if available (Linux)
    xdg_music = os.environ.get('XDG_MUSIC_DIR')
    if xdg_music:
        allowed_dirs.append(Path(xdg_music))

    # Resolve all paths to absolute and normalize
    return [path.resolve() for path in allowed_dirs if path.exists()]


def validate_scan_path(
    directory: str,
    allowed_base_dirs: list[Path] | None = None
) -> Path:
    """
    Validate and sanitize a directory path for scanning.

    Security checks:
    - Path must be absolute or relative (will be resolved)
    - No path traversal sequences (../)
    - Must fall within allowed base directories
    - Must be an existing directory
    - Must be readable

    Args:
        directory: Directory path to validate (str or Path)
        allowed_base_dirs: List of allowed base directories (default: user home, Music, Documents)

    Returns:
        Resolved absolute Path object if valid

    Raises:
        PathValidationError: If path fails validation

    Examples:
        >>> validate_scan_path("/home/user/Music")  # OK
        >>> validate_scan_path("../../etc")  # Raises PathValidationError
        >>> validate_scan_path("/etc")  # Raises PathValidationError (not in allowed dirs)
    """
    if not directory:
        raise PathValidationError("Directory path cannot be empty")

    # Convert to Path object
    try:
        path = Path(directory)
    except (ValueError, TypeError) as e:
        raise PathValidationError(f"Invalid path format: {e}")

    # Resolve to absolute path (resolves symlinks and normalizes)
    try:
        resolved_path = path.resolve()
    except (OSError, RuntimeError) as e:
        raise PathValidationError(f"Failed to resolve path: {e}")

    # Check for path traversal attempts in original path
    # This catches things like "../../etc" even before resolution
    if ".." in Path(directory).parts:
        raise PathValidationError(
            "Path traversal sequences (..) are not allowed. "
            "Please use absolute paths or paths relative to your home directory."
        )

    # Get allowed base directories
    if allowed_base_dirs is None:
        allowed_base_dirs = get_allowed_directories()

    # Check if path falls within any allowed base directory
    is_allowed = False
    for base_dir in allowed_base_dirs:
        try:
            # Check if resolved path is relative to base_dir
            # This will raise ValueError if not relative
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

    # Check if path exists
    if not resolved_path.exists():
        raise PathValidationError(f"Directory does not exist: {resolved_path}")

    # Check if it's actually a directory
    if not resolved_path.is_dir():
        raise PathValidationError(f"Path is not a directory: {resolved_path}")

    # Check if directory is readable
    if not os.access(resolved_path, os.R_OK):
        raise PathValidationError(f"Directory is not readable: {resolved_path}")

    logger.info(f"Path validation successful: {resolved_path}")
    return resolved_path


def validate_file_path(
    filepath: str,
    allowed_base_dirs: list[Path] | None = None
) -> Path:
    """
    Validate and sanitize a file path against allowed directories.

    Same security checks as validate_scan_path but for files instead of
    directories.

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

    logger.info(f"File path validation successful: {resolved_path}")
    return resolved_path


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


def is_safe_filename(filename: str) -> bool:
    """
    Check if a filename is safe (no path traversal or special chars).

    Args:
        filename: Filename to check

    Returns:
        True if safe, False otherwise

    Examples:
        >>> is_safe_filename("song.mp3")
        True
        >>> is_safe_filename("../../../etc/passwd")
        False
        >>> is_safe_filename("valid-file_name.mp3")
        True
    """
    if not filename:
        return False

    # Check for path separators (should be just a filename)
    if os.sep in filename or (os.altsep and os.altsep in filename):
        return False

    # Check for path traversal
    if ".." in filename:
        return False

    # Check for null bytes
    if "\0" in filename:
        return False

    # Filename should not start with . (hidden files) unless it's a valid music file
    if filename.startswith(".") and not any(
        filename.endswith(ext) for ext in [".mp3", ".flac", ".wav", ".m4a", ".ogg"]
    ):
        return False

    return True
