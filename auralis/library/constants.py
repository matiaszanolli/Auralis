"""
Library Constants
~~~~~~~~~~~~~~~~~

Shared constants for the Auralis library subsystem.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pathlib import Path

#: Canonical database path used by LibraryDatabase, migration scripts,
#: and CLI tools.  All code that needs a default DB location should
#: import this rather than hard-coding a path.
DEFAULT_DB_PATH = Path.home() / ".auralis" / "library.db"

#: How long a connection waits on a locked library.db, set per connection as
#: ``PRAGMA busy_timeout`` (milliseconds). Every engine that opens the file
#: (LibraryDatabase, the migration engine, FingerprintService's own engine) must
#: agree, or the one with the shortest wait is the one that raises "database is
#: locked" under contention (#2091, #3312, #5799).
SQLITE_BUSY_TIMEOUT_MS = 60_000

#: The sqlite3 driver's own lock wait (``connect_args["timeout"]``, seconds), the
#: companion to the PRAGMA above and shared by the same three engines.
SQLITE_CONNECT_TIMEOUT_S = 15
