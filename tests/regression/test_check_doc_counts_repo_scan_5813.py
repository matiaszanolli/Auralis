"""
Repository-count drift gate (#5813).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#5526 retired the queue-history repository and left "13 repos" in five places.
``scripts/check_doc_counts.py`` already scanned for the count, but only in the
long spelling ("13 repositories") and only under ``.claude/`` — so the shorthand
that CLAUDE.md's Codebase Map and ``_audit-common.md`` use, and CLAUDE.md
itself, were invisible to it. This pins the wider scan.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import importlib.util
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "check_doc_counts.py"


@pytest.fixture(scope="module")
def doc_counts():
    spec = importlib.util.spec_from_file_location("check_doc_counts", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "text",
    ["13 repositories", "13 repos + base.py", "all 13 repos,", "13 repository classes"],
)
def test_both_spellings_are_counted(doc_counts, text):
    match = doc_counts._REPO_COUNT_PATTERN.search(text)
    assert match is not None and match.group(1) == "13"


@pytest.mark.parametrize("text", ["13 reposted", "the repository count", "repos without a number"])
def test_unrelated_words_are_not_counted(doc_counts, text):
    assert doc_counts._REPO_COUNT_PATTERN.search(text) is None


def test_scan_covers_claude_md_and_the_architecture_docs(doc_counts):
    scanned = {p.relative_to(doc_counts.PROJECT_ROOT).as_posix() for p in doc_counts._repo_count_doc_paths()}
    assert "CLAUDE.md" in scanned
    assert "docs/architecture/module-map.md" in scanned
    assert ".claude/commands/_audit-common.md" in scanned


def test_no_documented_repository_count_has_drifted(doc_counts):
    live = doc_counts.count_repositories()
    assert doc_counts.check_stale_repository_counts(live) == []


# --- #5815: the same drift for the DB schema version ---------------------------

@pytest.mark.parametrize(
    "text, stated",
    [("DB migrations (schema v21)", 21), ("schema history (currently v18)", 18), ("Schema V16", 16)],
)
def test_stated_schema_versions_are_parsed(doc_counts, text, stated):
    match = doc_counts._SCHEMA_VERSION_PATTERN.search(text)
    assert match is not None and int(match.group(1)) == stated


def test_live_schema_version_matches_the_version_module(doc_counts):
    from auralis.__version__ import __db_schema_version__

    assert doc_counts.live_schema_version() == __db_schema_version__


def test_no_documented_schema_version_has_drifted(doc_counts):
    assert doc_counts.check_stale_schema_versions(doc_counts.live_schema_version()) == []
