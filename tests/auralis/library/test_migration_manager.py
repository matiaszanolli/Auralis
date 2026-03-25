# -*- coding: utf-8 -*-

"""
Tests for MigrationManager
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression tests for database migration session handling

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
from sqlalchemy import text

from auralis.library.migration_manager import MigrationManager


@pytest.fixture
def empty_db(tmp_path):
    """Create a MigrationManager pointing at a fresh empty database (no tables)."""
    db_path = tmp_path / "empty.db"
    return MigrationManager(str(db_path))


def test_get_current_version_returns_zero_on_fresh_db(empty_db):
    """get_current_version() should return 0 when schema_version table doesn't exist."""
    version = empty_db.get_current_version()
    assert version == 0


def test_session_usable_after_get_current_version_on_fresh_db(empty_db):
    """Sessions must remain usable after get_current_version() fails to find the table.

    Regression test for commit 9c66abd4 / issue #2694: the session-per-call
    design means each call gets a fresh session, so there is no invalidated
    state to worry about.  Verify by opening a new session and running a query.
    """
    empty_db.get_current_version()

    # A fresh session should work fine after get_current_version()
    with empty_db._get_session() as session:
        result = session.execute(text("SELECT 1")).scalar()
    assert result == 1
