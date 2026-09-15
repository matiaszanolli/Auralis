"""
A failed write rolls back in BaseRepository._session_scope (#5117)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#2238 added ``except Exception: session.rollback(); raise`` to two
AlbumRepository methods, and later write paths copied it in some methods and
not others. Every hand-rolled repository write path runs inside
``_session_scope``, so the rollback now happens there, once, for all of them.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from auralis.library.models import Base, Genre
from auralis.library.repositories.base import BaseRepository


class _GenreWriter(BaseRepository):
    """A write path with no rollback of its own, like the #5117 sites."""

    def add(self, name: str) -> None:
        with self._session_scope() as session:
            session.add(Genre(name=name))
            session.commit()


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'scope.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(engine)
    engine.dispose()


def test_failed_commit_propagates_and_the_pool_stays_usable(session_factory):
    writer = _GenreWriter(session_factory)
    writer.add('Duplicate')

    with pytest.raises(IntegrityError):
        writer.add('Duplicate')

    writer.add('Next')
    with session_factory() as session:
        assert session.execute(select(func.count()).select_from(Genre)).scalar_one() == 2


def test_rollback_runs_before_close_only_when_an_exception_escapes():
    session = MagicMock()
    repository = BaseRepository(lambda: session)

    with pytest.raises(RuntimeError, match='commit failed'), repository._session_scope():
        raise RuntimeError('commit failed')

    assert [call[0] for call in session.method_calls] == ['rollback', 'close']

    session.reset_mock()
    with repository._session_scope():
        pass

    assert [call[0] for call in session.method_calls] == ['close']


def test_a_failing_rollback_does_not_mask_the_original_error():
    session = MagicMock()
    session.rollback.side_effect = OSError('connection lost')
    repository = BaseRepository(lambda: session)

    with pytest.raises(IntegrityError), repository._session_scope():
        raise IntegrityError('INSERT', {}, Exception('UNIQUE constraint failed'))

    session.close.assert_called_once()
