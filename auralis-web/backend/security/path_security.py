"""
Path Security Utilities
~~~~~~~~~~~~~~~~~~~~~~~

Path validation and sanitization to prevent directory traversal attacks.

Fixes #2069: Path traversal in directory scanning endpoint

Trust model (#4799): Auralis is a single-user desktop app where directories
come from the user's own file picker, not an untrusted network client. Every
real directory entry point (``LibraryScanRequest.validate_directory_paths``
in ``schemas/library.py``, ``POST /api/settings/scan-folders``) validates through
``validate_user_chosen_directory()`` / ``validate_directory_list()``, which
enforce basic safety (no traversal, no operating-system roots, must exist and
be readable) but
deliberately do NOT restrict to a fixed allowlist — the user's choice is
trusted. Registering a folder via ``register_allowed_directory()`` then
widens the allowlist ``validate_file_path()`` consults for the rest of the
session. There is intentionally no separate allowlist-enforcing directory
validator in this module: an allowlist validator here would imply a
containment guarantee the app doesn't actually enforce. Do not re-add one.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# The names callers import from here; the error classes and allow-list helpers live in
# path_errors / path_allowlist and are re-exported so mypy treats them as public.
__all__ = [
    "DEFAULT_ALLOWED_DIRS",
    "PathMissingError",
    "PathValidationError",
    "get_allowed_directories",
    "validate_directory_list",
    "validate_file_path",
    "validate_user_chosen_directory",
]

from .path_allowlist import (  # noqa: E402  (split #6271; body-used below)
    DEFAULT_ALLOWED_DIRS,
    _extra_allowed_dirs,
    _is_system_directory,
    get_allowed_directories,
)
from .path_errors import (  # noqa: E402
    PathMissingError,
    PathValidationError,
    _logs_rejections,
)

@_logs_rejections
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
        PathMissingError: If the path is contained but does not exist on disk
            (or is not a regular file). A ``PathValidationError`` subclass, so
            callers that do not care about the distinction are unaffected.
        PathValidationError: If path fails any other validation check
            (empty, unresolvable, traversal, outside allowed dirs, unreadable)

    Deliberate non-callers (#5303, #5322): the playback load path
    (``services/queue_set_mixin.py`` / ``queue_edit_mixin.py`` /
    ``services/navigation_service.py`` → the player's ``load_file``) and the
    streamlined cache worker (``core/streamlined_worker.py``) intentionally do
    NOT validate DB-sourced track filepaths. The scanner's accepted policy is
    to follow symlinked subdirectories with no containment (#4823, closed as
    "keep current behavior" — symlinked libraries spanning volumes are a
    legitimate use case), so a library track's stored path can legitimately
    resolve outside ``get_allowed_directories()``. Those tracks must play;
    validating here would break exactly that. The asymmetry is accepted:
    request-scoped REST features (lyrics, metadata, WAV streaming) reject
    symlink-escaped tracks while playback serves them.
    """
    if not filepath:
        raise PathValidationError("File path cannot be empty")

    try:
        path = Path(filepath)
    except (ValueError, TypeError) as e:
        raise PathValidationError(f"Invalid path format: {e}")

    try:
        resolved_path = path.resolve()
    except (OSError, RuntimeError, ValueError) as e:
        # ValueError: an embedded NUL byte ("embedded null character in path"),
        # which would otherwise escape every `except PathValidationError` as a 500 (#6159).
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
        # Full detail (resolved path + every allowed directory -- the user's
        # entire configured library layout) at DEBUG only, not in the
        # exception's own string form (#4807). Four HTTP routes used to
        # reflect str(e) verbatim into a 400 body; they now return a fixed
        # generic message regardless of what PathValidationError says, but
        # keeping the enumeration out of the exception itself removes the
        # fragility at its root instead of relying on every future caller
        # remembering not to reflect it. Matches startup.py's existing
        # DEBUG-for-sensitive-paths convention (#3844/#4376).
        allowed_dirs_str = ", ".join(str(d) for d in allowed_base_dirs)
        logger.debug(
            f"Path '{resolved_path}' is outside allowed directories. "
            f"Allowed directories: {allowed_dirs_str}"
        )
        raise PathValidationError("Path is outside allowed directories")

    # PathMissingError, not a bare PathValidationError (#5080): the path is
    # well-formed and inside an allowed directory — it simply is not there.
    # Callers map this to 404, and the containment failures above to 400.
    if not resolved_path.exists():
        raise PathMissingError(f"File does not exist: {resolved_path}")

    if not resolved_path.is_file():
        raise PathMissingError(f"Path is not a file: {resolved_path}")

    if not os.access(resolved_path, os.R_OK):
        raise PathValidationError(f"File is not readable: {resolved_path}")

    # Debug, not info (#3844): validators run very frequently and the
    # resolved path is sensitive (the user's media library layout) — at INFO
    # it floods logs and gets persisted to electron-log on disk. This one
    # runs 5x per /api/metadata/tracks/{id} request.
    logger.debug(f"File path validation successful: {resolved_path}")
    return resolved_path


@_logs_rejections
def validate_user_chosen_directory(directory: str) -> Path:
    """
    Validate a directory path explicitly chosen by the user (e.g., via file picker).

    Auralis is a single-user desktop app. When the user explicitly selects a
    folder to scan, we trust their choice outside operating-system-owned
    directory trees and enforce basic safety checks (no traversal, must exist,
    must be readable) without restricting to predefined media directories.

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

    if ".." in path.parts:
        raise PathValidationError(
            "Path traversal sequences (..) are not allowed. "
            "Please use absolute paths."
        )

    try:
        resolved_path = path.resolve(strict=True)
    except FileNotFoundError:
        raise PathValidationError(f"Directory does not exist: {path}")
    except (OSError, RuntimeError, ValueError) as e:
        # ValueError: an embedded NUL byte ("embedded null character in path"),
        # which would otherwise escape every `except PathValidationError` as a 500 (#6159).
        raise PathValidationError(f"Failed to resolve path: {e}")

    if _is_system_directory(resolved_path):
        raise PathValidationError(
            "Operating-system directories cannot be used as library scan roots"
        )

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
