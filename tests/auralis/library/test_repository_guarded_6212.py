"""BaseRepository._guarded / _first_detached / _all_detached (#6212).

``_guarded`` replaced twenty hand-rolled ``except Exception: session.rollback();
error(...); return <default>`` blocks; the detach helpers replaced the per-file
``expunge`` / ``expunge_all`` get-one scaffolds.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auralis.library.models import Album, Artist, Base, Track
from auralis.library.repositories.base import BaseRepository


@pytest.fixture
def repo():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    return BaseRepository(sessionmaker(bind=engine))


class TestGuarded:
    def test_failure_is_swallowed_logged_once_and_rolled_back(self, repo):
        def op() -> str | None:
            with repo._guarded("Failed to do the thing") as session:
                session.add(Artist(name="x", normalized_name="x"))
                session.flush()
                raise RuntimeError("boom")
            return None

        with patch("auralis.library.repositories.base.error") as log_error:
            assert op() is None

        log_error.assert_called_once_with("Failed to do the thing: boom")
        # rolled back: nothing persisted
        with repo._session_scope() as session:
            assert session.execute(select(Artist)).scalars().all() == []

    def test_return_inside_the_block_is_untouched(self, repo):
        def op() -> int | None:
            with repo._guarded("Failed to do the thing") as session:
                session.add(Artist(name="y", normalized_name="y"))
                session.commit()
                return session.execute(select(Artist.id)).scalar_one()
            return None

        assert op() == 1

    def test_non_exception_base_exceptions_are_not_swallowed(self, repo):
        with pytest.raises(KeyboardInterrupt):
            with repo._guarded("Failed to do the thing"):
                raise KeyboardInterrupt

    def test_session_is_closed_on_success_and_failure(self):
        session = MagicMock()
        repo = BaseRepository(MagicMock(return_value=session))
        with repo._guarded("ok"):
            pass
        with repo._guarded("bad"):
            raise ValueError("x")
        assert session.close.call_count == 2
        session.rollback.assert_called_once()


class TestDetachedReads:
    def _seed(self, repo):
        with repo._session_scope() as session:
            artist = Artist(name="A", normalized_name="a")
            album = Album(title="Alb", artist=artist)
            album.tracks.append(Track(title="T1", filepath="/t1", filepath_key="/t1"))
            album.tracks.append(Track(title="T2", filepath="/t2", filepath_key="/t2"))
            session.add(album)
            session.commit()

    def test_first_detached_returns_none_when_absent(self, repo):
        with repo._session_scope() as session:
            assert repo._first_detached(session, select(Album).where(Album.id == 99)) is None

    def test_first_detached_detaches_the_row_and_its_eager_loaded_relatives(self, repo):
        from sqlalchemy.orm import selectinload

        self._seed(repo)
        with repo._session_scope() as session:
            album = repo._first_detached(
                session, select(Album).options(selectinload(Album.tracks), selectinload(Album.artist))
            )
            assert album is not None
            assert album not in session
            assert all(t not in session for t in album.tracks)
            assert album.artist not in session
        assert {t.title for t in album.tracks} == {"T1", "T2"}  # usable after close
        assert album.artist.name == "A"

    def test_all_detached_returns_a_list_of_detached_rows(self, repo):
        self._seed(repo)
        with repo._session_scope() as session:
            rows = repo._all_detached(session, select(Track).order_by(Track.title))
            assert isinstance(rows, list)
            assert all(r not in session for r in rows)
        assert [r.title for r in rows] == ["T1", "T2"]


class TestNoHandRolledSwallowingLeft:
    def test_no_repository_method_swallows_with_an_explicit_rollback(self):
        """The acceptance criterion: no `except Exception` that rolls back and
        returns a default remains in the repositories package."""
        import ast
        from pathlib import Path

        import auralis.library.repositories as pkg

        offenders = []
        for path in Path(pkg.__file__).parent.glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if (
                    isinstance(node, ast.ExceptHandler)
                    and isinstance(node.type, ast.Name)
                    and node.type.id == "Exception"
                    and any("rollback" in ast.unparse(c) for c in ast.walk(node) if isinstance(c, ast.Call))
                    and not any(isinstance(n, ast.Raise) for n in ast.walk(node))
                ):
                    offenders.append(f"{path.name}:{node.lineno}")
        assert offenders == []
