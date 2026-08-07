"""
Regression test for #4929 — residual absolute-path logging at INFO level.

#4366/#4376 demoted absolute-filesystem-path logging (OS username + install
layout) to DEBUG across most of the codebase, following the rationale
established in `auralis-web/backend/security/path_security.py` (#3844). This
issue found four sites that were missed:

- `auralis/library/migration_manager.py` (backup_database, restore_database,
  check_and_migrate_database's pre-migration backup)
- `auralis/analysis/fingerprint/fingerprint_service.py`
  (`_load_from_database`'s stale-band-pct discard)
- `auralis/cli/fetch_artwork.py` (library bootstrap)

`fetch_artwork.py` is a standalone CLI entry point — a source-text check
(matching the existing pattern in
`tests/backend/test_library_database_migration_4619.py`) is simpler and more
robust than driving the whole CLI. `migration_manager.py` and
`fingerprint_service.py` get real caplog-based regression tests alongside
their existing test suites (`tests/test_migrations.py`,
`tests/test_fingerprint_unification_4595.py`); this file guards the grep-able
invariant across all of them plus the CLI script.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

# logger.info(f"...{something_that_looks_like_a_path}...") — same shape the
# issue's own grep used, restricted to the files this issue names.
_LEAKY_INFO_PATH_LOG = re.compile(
    r'logger\.info\(f"[^"]*\{([^}]*(?:path|filepath)[^}]*)\}'
)
# A bare `.name` tail is the established safe pattern (#4351/#4366/#4929) —
# it interpolates only the filename, never the full path — so it's excluded.
_SAFE_NAME_ONLY = re.compile(r"\.name$")

_TARGET_FILES = (
    "auralis/library/migration_manager.py",
    "auralis/analysis/fingerprint/fingerprint_service.py",
    "auralis/cli/fetch_artwork.py",
)


def test_no_full_path_info_logging_in_target_files() -> None:
    """AC: none of the four originally-flagged lines (or a same-pattern
    regrowth) log a raw path variable at INFO across these three files."""
    offenders = []
    for rel_path in _TARGET_FILES:
        source = (_REPO_ROOT / rel_path).read_text()
        for lineno, line in enumerate(source.splitlines(), start=1):
            match = _LEAKY_INFO_PATH_LOG.search(line)
            if match and not _SAFE_NAME_ONLY.search(match.group(1).strip()):
                offenders.append(f"{rel_path}:{lineno}: {line.strip()}")

    assert not offenders, "absolute-path INFO logging found:\n" + "\n".join(offenders)


def test_fetch_artwork_cli_logs_library_path_at_debug_only() -> None:
    source = (_REPO_ROOT / "auralis" / "cli" / "fetch_artwork.py").read_text()
    assert 'logger.info(f"Loading library from: {library_path}")' not in source
    assert "logger.debug(f\"Library path: {library_path}\")" in source
