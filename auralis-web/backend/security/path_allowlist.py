"""
Path Allowlist
~~~~~~~~~~~~~~

The allowed-directory registry split from path_security.py (#6271):
DEFAULT_ALLOWED_DIRS, the runtime extra-directory list (#2562 note) and the
register/unregister/clear/get accessors.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import os
import sys
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


def _system_directory_roots() -> tuple[Path, ...]:
    """Return OS-owned directory trees that must never become scan roots."""
    if os.name == "nt":
        candidates = {
            Path(os.environ.get("SystemRoot", r"C:\Windows")),
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        }
    else:
        candidates = {
            Path("/"), Path("/bin"), Path("/boot"), Path("/dev"),
            Path("/etc"), Path("/proc"), Path("/root"), Path("/sbin"),
            Path("/sys"), Path("/usr"), Path("/var"),
        }
        if sys.platform == "darwin":
            candidates.update({Path("/Library"), Path("/System")})
    return tuple(path.resolve() for path in candidates)


def _is_system_directory(path: Path) -> bool:
    filesystem_root = Path(path.anchor)
    return any(
        path == root or (root != filesystem_root and path.is_relative_to(root))
        for root in _system_directory_roots()
    )


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
