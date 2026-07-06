"""
Base Repository
~~~~~~~~~~~~~~~

Shared session-lifecycle plumbing for all data-access repositories.

Every repository takes a ``session_factory`` and opens short-lived sessions
per operation. Centralising that here means a session-lifecycle change
(pooling instrumentation, retry policy, async migration) is a one-file edit
instead of a ~13-file sweep.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session


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
        """Yield a session and guarantee it is closed.

        Use for read paths that only need automatic ``close()``::

            with self._session_scope() as session:
                return session.execute(...).scalars().all()

        Callers remain responsible for ``commit()``/``rollback()`` semantics
        on write paths.
        """
        session = self.get_session()
        try:
            yield session
        finally:
            session.close()
