"""
Base Repository
~~~~~~~~~~~~~~~

Shared session-lifecycle plumbing for all data-access repositories.

Every repository takes a ``session_factory`` and opens short-lived sessions
per operation. Centralising that here means a session-lifecycle change
(pooling instrumentation, retry policy, async migration) is a one-file edit
instead of a per-repository sweep.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from typing import Any, TypeVar

from sqlalchemy import ColumnElement, ScalarSelect, Select, String, collate, func, select
from sqlalchemy.orm import Session

from ...utils.logging import error

_T = TypeVar("_T")

def escape_like(query: str) -> str:
    """Neutralise LIKE metacharacters in a user-supplied search string.

    Without this, a query containing ``%`` or ``_`` is interpreted as a
    wildcard and matches far more rows than the user asked for — ``%`` alone
    matches everything (#2405).

    Pair with ``escape='\\'`` on the ``ilike()`` call::

        term = f"%{escape_like(query)}%"
        Model.name.ilike(term, escape='\\')

    ``TrackRepository``, ``AlbumRepository``, ``ArtistRepository`` and
    ``GenreRepository`` all call this helper directly (#5406) rather than
    carrying their own inline copy of the expression.
    """
    return query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def sort_terms(column: Any, tie_breaker: Any, descending: bool = False) -> tuple[ColumnElement[Any], ...]:
    """ORDER BY terms for a paginated list read (#5868, #5869).

    - Text columns sort ``COLLATE NOCASE`` — the collation ``idx_albums_title``
      and ``idx_tracks_title`` are built on, so the sort stays index-backed —
      instead of BINARY, which put every lowercase initial (``alt-J``,
      ``deadmau5``) after ``Z``. NOCASE folds ASCII only.
    - Nullable columns put NULLs last in either direction (SQLite puts them
      first on ASC, so "by year" opened on the undated albums).
    - *tie_breaker* (the primary key) follows the same direction and gives a
      total order, so LIMIT/OFFSET pages neither overlap nor skip rows.
    """
    nullable = getattr(getattr(column, 'expression', column), 'nullable', False)
    if isinstance(getattr(column, 'type', None), String):
        column = collate(column, 'NOCASE')
    primary = column.desc() if descending else column.asc()
    if nullable:
        primary = primary.nulls_last()
    return (primary, tie_breaker.desc() if descending else tie_breaker.asc())


def correlated_count(source: Any, fk_column: Any, parent: Any) -> ScalarSelect[int]:
    """Per-row COUNT of *source* rows whose *fk_column* points at *parent*.

    Evaluated by the database as a correlated scalar subquery — no JOIN and no
    row multiplication, so a parent with no children yields 0 (never NULL; no
    COALESCE needed). *source* is the association table or child model counted
    and *fk_column* its column referencing ``parent.id``. One definition for
    the artist/album/genre/playlist list reads (#4777, #5084, #5111).
    """
    return (
        select(func.count())
        .select_from(source)
        .where(fk_column == parent.id)
        .correlate(parent)
        .scalar_subquery()
    )


def correlated_sum(
    source: Any,
    value_column: Any,
    link_column: Any,
    parent: Any,
    join_model: Any = None,
) -> ScalarSelect[float]:
    """Per-row SUM of *value_column* over the rows of *source* tied to *parent*.

    The SUM twin of :func:`correlated_count` (#6212), replacing the two
    private ``_total_duration_subquery`` copies:

    - direct FK (album durations)::

        correlated_sum(Track, Track.duration, Track.album_id, Album)

    - through an association table (playlist durations)::

        correlated_sum(track_playlist, Track.duration,
                       track_playlist.c.playlist_id, Playlist, join_model=Track)

    COALESCE because SUM over zero rows is NULL, unlike COUNT (#4777).
    """
    stmt = select(func.coalesce(func.sum(value_column), 0.0)).select_from(source)
    if join_model is not None:
        stmt = stmt.join(join_model, join_model.id == source.c.track_id)
    stmt = stmt.where(link_column == parent.id).correlate(parent)
    return stmt.scalar_subquery()


class BaseRepository:
    """Base class providing session-factory storage and session lifecycle.

    Subclasses inherit :meth:`get_session` and :meth:`_session_scope`. A
    subclass only needs its own ``__init__`` if it stores additional
    collaborators; when it does, it should call ``super().__init__(...)``.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def get_session(self) -> Session:
        """Get a new database session from the configured factory."""
        return self.session_factory()

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        """Yield a session, rolling back if an exception escapes, and close it.

        Use for read paths that only need automatic ``close()``::

            with self._session_scope() as session:
                return session.execute(...).scalars().all()

        Callers remain responsible for ``commit()`` on write paths. A failed
        commit that escapes the block is rolled back here before the exception
        re-raises unchanged, so a method no longer needs its own
        ``except Exception: session.rollback(); raise`` (#2238) to leave the
        session clean (#5117). ``close()`` would roll back implicitly anyway;
        this makes it explicit for every write path in one place instead of in
        some methods and not others. Only exceptions that leave the block
        trigger it, so a method that catches its own failure and returns keeps
        the objects it has not yet returned attached (the #2624 hazard).
        """
        session = self.get_session()
        try:
            yield session
        except BaseException:
            # A rollback that fails too (a dropped connection, say) must not
            # replace the exception the caller actually needs to see.
            with suppress(Exception):
                session.rollback()
            raise
        finally:
            session.close()

    def _guarded(self, failure_message: str) -> "_GuardedScope":
        """:meth:`_session_scope` that swallows a failure and logs it once.

        The write paths that report failure through their return value
        (``None`` / ``False`` / ``0``) used to repeat::

            with self._session_scope() as session:
                try:
                    ...
                except Exception as e:
                    session.rollback()
                    error(f"Failed to X: {e}")
                    return None

        and now read::

            with self._guarded("Failed to X") as session:
                ...
            return None

        An exception leaving the block is rolled back by :meth:`_session_scope`
        (#5117), logged here as ``"<failure_message>: <error>"`` at ERROR, and
        swallowed, so execution continues after the ``with`` -- the line that
        returns the method's failure default. A ``return`` inside the block is
        untouched, so a method still hands back the object it detached before
        returning (the #2624 hazard: detach *before* the commit-expired
        instance leaves the session; close() then has nothing left to expire).

        The failure is not distinguishable from "not found" by the caller; that
        is the existing contract (#5940 tracks changing it) and this helper
        deliberately preserves it.
        """
        return _GuardedScope(self._session_scope(), failure_message)

    def _first_detached(self, session: Session, stmt: Select[tuple[_T]]) -> _T | None:
        """First row of *stmt* (or None), detached together with everything
        eager-loaded under it.

        ``expunge_all()``, not ``expunge(obj)``: a per-item expunge does not
        cascade to related objects, leaving them ``DetachedInstanceError``-prone
        (#2406, #4236). One place owns that policy for the get-one read paths.
        """
        row = session.execute(stmt).scalars().unique().first()
        session.expunge_all()
        return row

    def _all_detached(self, session: Session, stmt: Select[tuple[_T]]) -> list[_T]:
        """All rows of *stmt*, detached together with their eager-loaded
        relatives. The list twin of :meth:`_first_detached`."""
        rows = list(session.execute(stmt).scalars().unique().all())
        session.expunge_all()
        return rows


class _GuardedScope:
    """Context manager behind :meth:`BaseRepository._guarded`.

    A class rather than ``@contextmanager`` because its ``__exit__`` is typed
    ``-> bool``: that is how mypy learns the block can swallow an exception, so
    the ``return <default>`` after a ``with`` whose body returns on every path
    is not flagged unreachable.
    """

    def __init__(self, scope: Any, failure_message: str) -> None:
        self._scope = scope
        self._failure_message = failure_message

    def __enter__(self) -> Session:
        session: Session = self._scope.__enter__()
        return session

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        # _session_scope rolls back and closes; for an escaping exception it
        # reports "not suppressed", and we decide here whether to swallow it.
        self._scope.__exit__(exc_type, exc, tb)
        if exc_type is not None and issubclass(exc_type, Exception):
            error(f"{self._failure_message}: {exc}")
            return True
        return False
