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

#: Longest tag text the library stores or serves, in characters. Frames can be
#: megabytes, so a short tag (title, artist, album, genre...) is cut at ingest
#: before any regex or the repository sees it (#6154). The free-text tags get
#: more room. The metadata PUT validates against these, and the lyrics fallback
#: and the metadata GET's tag readers cut to them (#5266, #6515).
MAX_TAG_TEXT_CHARS = 1000

# Per-track caps on the multi-valued tags: each artist is an Artist row and a link, each genre a
# Genre row, and both are returned in every track payload (#6165 genres, #6510 artists).
MAX_ARTISTS_PER_TRACK = 20
MAX_GENRES_PER_TRACK = 20
MAX_COMMENT_CHARS = 10_000
MAX_LYRICS_CHARS = 100_000
