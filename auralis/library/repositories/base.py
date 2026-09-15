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

from sqlalchemy.orm import Session

# Backslash is the escape character every repository passes as
# ``ilike(..., escape='\\')``.
LIKE_ESCAPE = '\\'


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
