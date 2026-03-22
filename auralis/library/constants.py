"""
Library Constants
~~~~~~~~~~~~~~~~~

Shared constants for the Auralis library subsystem.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from pathlib import Path

#: Canonical database path used by LibraryManager, migration scripts,
#: and CLI tools.  All code that needs a default DB location should
#: import this rather than hard-coding a path.
DEFAULT_DB_PATH = Path.home() / ".auralis" / "library.db"
