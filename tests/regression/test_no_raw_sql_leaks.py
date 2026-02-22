"""
Regression test: raw SQL must not leak outside repository pattern (#2370)

Scans the codebase to ensure that direct SQL execution (conn.execute,
cursor.execute, text()) only appears in allowed locations:
- auralis/library/repositories/ (repository implementations)
- auralis/library/migration_manager.py (migrations)
- auralis/library/migrations/ (SQL migration files)
- auralis/analysis/fingerprint/fingerprint_service.py (sqlite3 cache)
- auralis/library/manager.py (PRAGMA statements only)

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import re
from pathlib import Path

import pytest


# Allowed locations for raw SQL
ALLOWED_SQL_PATHS = {
    "auralis/library/repositories",
    "auralis/library/migration_manager.py",
    "auralis/library/migrations",
    "auralis/analysis/fingerprint/fingerprint_service.py",
    "auralis/library/manager.py",
}

# Patterns that indicate raw SQL usage
SQL_PATTERNS = [
    re.compile(r'\bcursor\.execute\s*\('),
    re.compile(r'\bconn\.execute\s*\('),
    re.compile(r'\bconnection\.execute\s*\('),
    re.compile(r'\bsession\.execute\s*\(\s*text\s*\('),
]

ROOT = Path(__file__).parent.parent.parent


def _is_allowed(filepath: Path) -> bool:
    """Check if raw SQL is allowed at this path."""
    rel = str(filepath.relative_to(ROOT))
    return any(rel.startswith(allowed) for allowed in ALLOWED_SQL_PATHS)


class TestNoRawSQLLeaks:
    """Regression: all DB access must go through repository pattern."""

    def test_no_raw_sql_outside_repositories(self):
        """Scan auralis/ for raw SQL outside allowed locations."""
        violations = []

        for py_file in ROOT.glob("auralis/**/*.py"):
            if _is_allowed(py_file):
                continue
            # Skip test files
            if "test" in str(py_file).lower():
                continue

            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for i, line in enumerate(content.splitlines(), 1):
                # Skip comments
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                for pattern in SQL_PATTERNS:
                    if pattern.search(line):
                        rel = py_file.relative_to(ROOT)
                        violations.append(f"{rel}:{i}: {stripped[:100]}")

        assert not violations, (
            f"Raw SQL found outside repository pattern:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
