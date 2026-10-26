"""
Where the library's on-disk caches live
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Album artwork, the fingerprint ``.25d`` cache and the backend's thumbnail tree
used to be hard-coded to ``~/.auralis``, whatever database was open. A library
at another path (tests, a portable install, a second library) therefore wrote
into the real profile and served another library's ``album_<id>`` images
(#5751). They now follow the database:

- the default database keeps ``~/.auralis`` (nothing moves for existing users);
- ``LibraryDatabase(database_path=...)`` anywhere else registers that file's
  directory, and the caches go under it;
- ``AURALIS_DATA_DIR`` overrides the default root.

The location is process-wide, so every consumer resolves the same directory;
opening a second library at a different path moves it to that library.
Uploads (``~/.auralis/uploads``) are per-installation, not per-library, and
stay global.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import os
from pathlib import Path

from .constants import DEFAULT_DB_PATH

DATA_DIR_ENV = "AURALIS_DATA_DIR"

# Set while a non-default database is open; None means "use the default root".
_database_data_dir: Path | None = None


def default_data_dir() -> Path:
    """The per-user default root, ``$AURALIS_DATA_DIR`` or ``~/.auralis``."""
    override = os.environ.get(DATA_DIR_ENV)
    return Path(override).expanduser() if override else Path.home() / ".auralis"


def get_data_dir() -> Path:
    """Root directory for the library's caches (not created here)."""
    return _database_data_dir if _database_data_dir is not None else default_data_dir()


def register_database_location(database_path: str | os.PathLike[str]) -> None:
    """Point the cache root at the open database's directory.

    Called by ``LibraryDatabase``. The default database resets to the default
    root, so reopening it after a custom one restores ``~/.auralis``.
    """
    global _database_data_dir
    resolved = Path(database_path).resolve()
    if resolved == Path(DEFAULT_DB_PATH).resolve():
        _database_data_dir = None
    else:
        _database_data_dir = resolved.parent


def artwork_dir() -> Path:
    """Source-artwork cache (thumbnails live under ``artwork_dir()/thumbnails``)."""
    return get_data_dir() / "artwork"


def fingerprints_dir() -> Path:
    """Central ``.25d`` fingerprint cache."""
    return get_data_dir() / "fingerprints"
