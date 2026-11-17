"""
Case-insensitive substring search that folds every script, not only ASCII.

SQLite's ``lower()`` and ``LIKE`` fold ASCII letters only, so ``ilike()`` (which
SQLAlchemy renders as ``lower(col) LIKE lower(?)``) never matched a stored
"Sigur Rós" for "SIGUR RÓS", nor "Édith" for "édith" (#6115). Every library
connection gets a ``casefold()`` SQL function backed by Python's
``str.casefold()``, and the search filters compare both sides through it.

A ``'%term%'`` pattern cannot use an index whatever the collation, so the
per-row Python call does not cost the search an index it had.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sqlite3
from typing import Any

from sqlalchemy import ColumnElement, event, func
from sqlalchemy.engine import Engine

from .base import escape_like


def _casefold(value: Any) -> Any:
    return value.casefold() if isinstance(value, str) else value


# Registered on every engine, not only LibraryDatabase's: the migration and
# fingerprint engines and the test fixtures build their own, and a session on
# any of them can reach a repository search. auralis.library's package import
# loads the repositories, so this runs before any library connection is opened.
@event.listens_for(Engine, "connect")
def _register_casefold(dbapi_connection: Any, _record: Any) -> None:
    if isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.create_function("casefold", 1, _casefold, deterministic=True)


def contains_text(column: Any, query: str) -> ColumnElement[bool]:
    """*column* contains *query*, ignoring case in any script.

    ``%``, ``_`` and ``\\`` in *query* match literally (escape_like, #2405).
    Accents are not folded: "Beyonce" does not find "Beyoncé".
    """
    term = f"%{escape_like(query.casefold())}%"
    return func.casefold(column).like(term, escape='\\')
