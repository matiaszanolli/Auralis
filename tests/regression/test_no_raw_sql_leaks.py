"""
Regression test: raw SQL must not leak outside repository pattern (#2370)

Scans auralis/ so that direct SQL execution (conn.execute, cursor.execute,
session.execute(text(...))) appears only where the allowlists below say why.

The allowlist named auralis/library/manager.py for years after #4915 deleted it,
so the PRAGMA setup that moved into database_engine.py and database.py, and the
split migration runner, all read as leaks and the test sat in the CI baseline.
Every entry now states its reason, PRAGMA-only files are held to PRAGMA lines,
and a second test fails on an entry that no longer exists or no longer needs to
be there (#6709 follow-up).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

# The home of library database access: no entry needed for any one file in it.
REPOSITORIES = "auralis/library/repositories"

# Files that may run any SQL, and why.
ALLOWED_SQL_FILES = {
    "auralis/library/migration_steps.py": "runs the migration .sql statements inside BEGIN/COMMIT",
    "auralis/library/schema_indexes.py": "drops duplicate rows so a declared unique index can be built on open",
    "auralis/analysis/fingerprint/catalog.py": "its own standalone SQLite catalog (scripts/fingerprint.py), not the library",
}

# Files that may run PRAGMA statements only, and why.
PRAGMA_ONLY_FILES = {
    "auralis/library/database_engine.py": "per-connection SQLite settings (WAL, foreign keys, busy timeout)",
    "auralis/library/database.py": "WAL checkpoint and PRAGMA optimize on shutdown",
    "auralis/library/migration_engine.py": "the migration connection's SQLite settings",
    "auralis/library/sqlite_wal.py": "the WAL switch every engine's connect hook shares, retried on lock contention",
    "auralis/analysis/fingerprint/fingerprint_service.py": "its connection's SQLite settings",
}

# Patterns that indicate raw SQL usage
SQL_PATTERNS = [
    re.compile(r'\bcursor\.execute\s*\('),
    re.compile(r'\bconn\.execute\s*\('),
    re.compile(r'\bconnection\.execute\s*\('),
    re.compile(r'\bsession\.execute\s*\(\s*text\s*\('),
]


def _sql_lines(path: Path) -> list[tuple[int, str]]:
    """(line number, stripped line) for each non-comment line that executes SQL."""
    found = []
    for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        stripped = line.strip()
        if not stripped.startswith("#") and any(p.search(line) for p in SQL_PATTERNS):
            found.append((number, stripped))
    return found


class TestNoRawSQLLeaks:
    """Regression: all DB access must go through repository pattern."""

    def test_no_raw_sql_outside_repositories(self):
        """Scan auralis/ for raw SQL outside allowed locations."""
        violations = []

        for py_file in sorted(ROOT.glob("auralis/**/*.py")):
            rel = py_file.relative_to(ROOT).as_posix()
            if rel.startswith(REPOSITORIES + "/") or rel in ALLOWED_SQL_FILES:
                continue
            for number, stripped in _sql_lines(py_file):
                if rel in PRAGMA_ONLY_FILES and "PRAGMA" in stripped:
                    continue
                violations.append(f"{rel}:{number}: {stripped[:100]}")

        assert not violations, (
            "Raw SQL found outside repository pattern (move it into a repository, "
            "or add the file to an allowlist with its reason):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_every_allowlist_entry_still_exists_and_runs_sql(self):
        """An entry for a deleted or SQL-free file is how the old allowlist went stale."""
        assert (ROOT / REPOSITORIES).is_dir()
        stale = [
            rel for rel in {**ALLOWED_SQL_FILES, **PRAGMA_ONLY_FILES}
            if not (ROOT / rel).is_file() or not _sql_lines(ROOT / rel)
        ]
        assert stale == [], f"allowlist entries with no raw SQL left to allow: {stale}"
