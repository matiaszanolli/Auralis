"""Fresh databases carry every index the migrations create (#5321).

A fresh install is built by ``Base.metadata.create_all`` and never runs the
versioned SQL migrations, so any index a migration creates but no model
declares was missing from every fresh install. Among them were the
fingerprint range-query indexes the KNN graph build's prefilter relies on.
``create_all`` also never adds an index to a table that already exists, so
LibraryDatabase repairs existing databases on open.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from auralis.library.models import Base
from auralis.library.schema_indexes import create_missing_declared_indexes

MIGRATIONS = Path(__file__).resolve().parents[3] / "auralis/library/migrations"
_CREATE_INDEX = re.compile(
    r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s+ON\s+(\w+)\s*\(([^)]*)\)",
    re.IGNORECASE,
)
_DROP = re.compile(r"DROP\s+(?:INDEX|TABLE)\s+(?:IF\s+EXISTS\s+)?(\w+)", re.IGNORECASE)


def _migration_indexes() -> dict[str, tuple[str, tuple[str, ...]]]:
    """{name: (table, columns)} the versioned chain leaves on live model tables."""
    created: dict[str, tuple[str, tuple[str, ...]]] = {}
    dropped: set[str] = set()
    for path in sorted(MIGRATIONS.glob("migration_v*.sql")):
        sql = path.read_text()
        for match in _CREATE_INDEX.finditer(sql):
            columns = tuple(part.strip().split()[0] for part in match.group(3).split(","))
            created[match.group(1)] = (match.group(2), columns)
        dropped.update(match.group(1) for match in _DROP.finditer(sql))
    return {
        name: (table, columns)
        for name, (table, columns) in created.items()
        if name not in dropped and table not in dropped and table in Base.metadata.tables
    }


def _run(db: Path, *statements: str) -> list[tuple]:
    with closing(sqlite3.connect(db)) as connection:
        rows: list[tuple] = []
        for statement in statements:
            rows = connection.execute(statement).fetchall()
        connection.commit()
        return rows


def _index_columns(db: Path) -> dict[str, set[tuple[str, ...]]]:
    by_table: dict[str, set[tuple[str, ...]]] = {}
    for name, table in _run(db, "SELECT name, tbl_name FROM sqlite_master WHERE type='index'"):
        columns = tuple(row[2] for row in _run(db, f"PRAGMA index_info('{name}')"))
        by_table.setdefault(table, set()).add(columns)
    return by_table


def _repair(db: Path) -> list[str]:
    engine = create_engine(f"sqlite:///{db}")
    try:
        return create_missing_declared_indexes(engine)
    finally:
        engine.dispose()


@pytest.fixture
def fresh_db(tmp_path) -> Path:
    path = tmp_path / "fresh.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    return path


def test_the_parser_finds_the_migration_indexes():
    """Guards the comparison below against silently comparing nothing."""
    indexes = _migration_indexes()
    assert len(indexes) >= 30
    assert indexes["idx_fingerprints_composite"] == (
        "track_fingerprints", ("lufs", "crest_db", "bass_pct", "tempo_bpm")
    )


def test_fresh_database_has_every_migration_index(fresh_db):
    have = _index_columns(fresh_db)
    missing = sorted(
        f"{table}.{name}{columns}"
        for name, (table, columns) in _migration_indexes().items()
        if columns not in have.get(table, set())
    )
    assert missing == []


def test_collation_order_and_partial_clauses_are_kept(fresh_db):
    sql = dict(_run(fresh_db, "SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"))
    assert "NOCASE" in sql["idx_tracks_title"].upper()
    assert "NOCASE" in sql["idx_albums_title"].upper()
    assert "DESC" in sql["idx_tracks_last_played"].upper()
    assert "DESC" in sql["idx_tracks_fingerprint_computed_at"].upper()
    favorite_title = sql["idx_tracks_favorite_title"].upper()
    assert "WHERE" in favorite_title and "NOCASE" in favorite_title


def test_dimension_range_prefilter_uses_an_index(fresh_db):
    plan = _run(
        fresh_db,
        "EXPLAIN QUERY PLAN SELECT id FROM track_fingerprints WHERE lufs >= -20 AND lufs <= -10",
    )
    detail = " ".join(row[3] for row in plan)
    assert "USING INDEX idx_fingerprints_" in detail or "USING COVERING INDEX idx_fingerprints_" in detail, detail


def test_repair_adds_declared_indexes_to_an_existing_database(fresh_db):
    _run(fresh_db, "DROP INDEX idx_fingerprints_lufs", "DROP INDEX idx_tracks_album_id")

    assert sorted(_repair(fresh_db)) == ["idx_fingerprints_lufs", "idx_tracks_album_id"]
    assert _repair(fresh_db) == []


def test_repair_does_not_duplicate_an_index_present_under_another_name(fresh_db):
    """Upgraded databases hold migration-named equivalents of model indexes."""
    _run(
        fresh_db,
        "DROP INDEX ix_similarity_graph_track_id_rank",
        "CREATE INDEX idx_similarity_graph_track_id ON similarity_graph(track_id, rank)",
    )

    assert _repair(fresh_db) == []


def test_library_database_repairs_indexes_on_open(tmp_path):
    from auralis.library.database import LibraryDatabase

    path = tmp_path / "library.db"
    LibraryDatabase(str(path)).shutdown()
    _run(path, "DROP INDEX idx_fingerprints_composite")

    LibraryDatabase(str(path)).shutdown()

    names = {row[0] for row in _run(path, "SELECT name FROM sqlite_master WHERE type='index'")}
    assert "idx_fingerprints_composite" in names
