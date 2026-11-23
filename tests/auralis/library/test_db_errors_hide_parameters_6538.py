"""A logged database error carries no bound parameter values (#6538).

A DBAPI error stringifies as ``(...Error) msg [SQL: ...] [parameters: (...)]``, and the
parameters are the row being written: a track's filepath, title, artist. Those errors are
logged at ERROR, outside the path-in-log policy (#4366, #6189). Every engine is now built
with ``hide_parameters=True``: the SQL and the error class remain, the values do not.
"""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from auralis.analysis.fingerprint.fingerprint_service import _make_engine
from auralis.library.database_engine import create_library_engine
from auralis.library.migration_engine import create_migration_engine

SECRET_PATH = "/srv/alice/Music/Secret/a.flac"


@pytest.mark.parametrize("make_engine", [create_library_engine, create_migration_engine, _make_engine],
                         ids=["library", "migration", "fingerprint"])
def test_a_unique_violation_does_not_show_the_row(make_engine):
    db = Path(tempfile.mkdtemp()) / "library.db"
    engine = make_engine(str(db) if make_engine is create_library_engine else db)
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE t (filepath TEXT UNIQUE)"))
            conn.execute(text("INSERT INTO t VALUES (:p)"), {"p": SECRET_PATH})
        with pytest.raises(IntegrityError) as raised, engine.begin() as conn:
            conn.execute(text("INSERT INTO t VALUES (:p)"), {"p": SECRET_PATH})
    finally:
        engine.dispose()

    message = str(raised.value)
    assert "UNIQUE constraint failed" in message and "INSERT INTO t" in message
    assert SECRET_PATH not in message
    assert "hidden due to hide_parameters" in message
