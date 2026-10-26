"""Build a create_all database and an upgraded one, and diff their schemas (#5753)."""

import sqlite3
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine

import auralis.library.migrations as migrations_pkg
from auralis.library.migration_manager import MigrationManager
from auralis.library.models import Base

_INITIAL_SCHEMA = Path(migrations_pkg.__file__).parent / "migration_v000_to_v001_initial_schema.sql"


def build_fresh(path: Path) -> None:
    """What a new install gets: the ORM's create_all."""
    manager = MigrationManager(str(path))
    manager.initialize_fresh_database()
    manager.close()


def build_upgraded(path: Path) -> None:
    """What a long-lived install holds: the v1 schema plus every migration.

    The v1 script predates some tables (e.g. user_settings), which a running app
    got from create_all, so those are created from the models at v1 exactly as
    an older release's startup would have, then migrate_to_latest() applies the
    chain.
    """
    conn = sqlite3.connect(path)
    conn.executescript(_INITIAL_SCHEMA.read_text())
    conn.commit()
    conn.close()
    engine = create_engine(f"sqlite:///{path}")
    existing = set(sa.inspect(engine).get_table_names())
    Base.metadata.create_all(
        engine, tables=[t for name, t in Base.metadata.tables.items() if name not in existing]
    )
    engine.dispose()
    manager = MigrationManager(str(path))
    assert manager.migrate_to_latest()
    manager.close()


def _affinity(declared: str) -> str:
    """SQLite's type-affinity rules (https://sqlite.org/datatype3.html#affinity)."""
    t = declared.upper()
    if "INT" in t:
        return "INTEGER"
    if any(k in t for k in ("CHAR", "CLOB", "TEXT")):
        return "TEXT"
    if "BLOB" in t or not t:
        return "BLOB"
    if any(k in t for k in ("REAL", "FLOA", "DOUB")):
        return "REAL"
    return "NUMERIC"


def _describe(path: Path) -> dict[str, dict]:
    conn = sqlite3.connect(path)
    schema: dict[str, dict] = {}
    for (table,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall():
        columns = {}
        for _cid, name, ctype, notnull, default, pk in conn.execute(f"PRAGMA table_info({table})"):
            # A PRIMARY KEY column is NOT NULL by definition whatever the DDL says.
            columns[name] = {
                "affinity": _affinity(ctype), "notnull": bool(notnull) or bool(pk), "default": default,
            }
        indexes = {}
        for _seq, name, unique, *_ in conn.execute(f"PRAGMA index_list({table})"):
            if name.startswith("sqlite_autoindex"):
                continue
            indexes[name] = {
                "unique": bool(unique),
                "columns": tuple(r[2] for r in conn.execute(f"PRAGMA index_info({name})")),
            }
        ddl = conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (table,)).fetchone()[0]
        schema[table] = {
            "columns": columns, "indexes": indexes, "autoincrement": "AUTOINCREMENT" in ddl.upper(),
        }
    conn.close()
    return schema


def schema_differences(upgraded: Path, fresh: Path) -> set[str]:
    """Human-readable keys, one per difference between the two databases."""
    up, new = _describe(upgraded), _describe(fresh)
    found: set[str] = set()
    for table in up.keys() - new.keys():
        found.add(f"table {table}: only on upgraded databases")
    for table in new.keys() - up.keys():
        found.add(f"table {table}: only on fresh databases")
    for table in sorted(up.keys() & new.keys()):
        u, n = up[table], new[table]
        if u["autoincrement"] != n["autoincrement"]:
            found.add(f"table {table}: AUTOINCREMENT differs (upgraded={u['autoincrement']})")
        for col in u["columns"].keys() | n["columns"].keys():
            cu, cn = u["columns"].get(col), n["columns"].get(col)
            if cu is None or cn is None:
                side = "upgraded" if cn is None else "fresh"
                found.add(f"column {table}.{col}: only on {side} databases")
                continue
            for attr in ("affinity", "notnull", "default"):
                if cu[attr] != cn[attr]:
                    found.add(f"column {table}.{col}: {attr} differs")
        for idx in u["indexes"].keys() | n["indexes"].keys():
            iu, inw = u["indexes"].get(idx), n["indexes"].get(idx)
            if iu is None or inw is None:
                side = "upgraded" if inw is None else "fresh"
                found.add(f"index {table}.{idx}: only on {side} databases")
            elif iu != inw:
                found.add(f"index {table}.{idx}: definition differs (upgraded unique={iu['unique']})")
    return found


def build_both(directory: Path) -> tuple[Path, Path]:
    upgraded, fresh = directory / "upgraded.db", directory / "fresh.db"
    build_upgraded(upgraded)
    build_fresh(fresh)
    return upgraded, fresh

