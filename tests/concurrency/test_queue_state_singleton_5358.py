"""
Concurrent first history pushes create one QueueState row (issue #5358)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

QueueHistoryRepository.push_to_history created the queue-state row with
"select the first row, else insert one". Two concurrent first pushes could
both miss the row and both insert, leaving two QueueState rows that later reads
chose between arbitrarily. The row is now created at a fixed primary key with
INSERT ... ON CONFLICT DO NOTHING.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from auralis.library.models import Base, QueueState
from auralis.library.repositories import QueueHistoryRepository
from auralis.library.repositories import queue_history_repository as qhr


@pytest.fixture
def repo(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'queue.db'}",
        connect_args={"timeout": 15, "check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    yield QueueHistoryRepository(sessionmaker(bind=engine))
    engine.dispose()


def _queue_state_ids(repo: QueueHistoryRepository) -> list[int]:
    with repo._session_scope() as session:
        return list(session.execute(select(QueueState.id)).scalars())


def test_concurrent_first_pushes_create_one_row(repo, monkeypatch):
    """Force every thread past the lookup at once, so all of them insert."""
    n_threads = 4
    barrier = threading.Barrier(n_threads)
    real_lookup = qhr._current_queue_state
    seen = threading.local()

    def racing_lookup(session):
        if not getattr(seen, "missed", False):
            seen.missed = True
            barrier.wait(timeout=5)
            return None
        return real_lookup(session)

    monkeypatch.setattr(qhr, "_current_queue_state", racing_lookup)
    errors: list[BaseException] = []

    def push(i: int) -> None:
        try:
            repo.push_to_history("add", {"track_ids": [i], "current_index": 0})
        except BaseException as exc:  # pragma: no cover - surfaced via assert below
            errors.append(exc)

    threads = [threading.Thread(target=push, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
    monkeypatch.undo()

    assert not errors, f"concurrent pushes raised: {errors}"
    assert _queue_state_ids(repo) == [qhr.QUEUE_STATE_ID]
    assert repo.get_history_count() == n_threads


def test_existing_row_is_reused_whatever_its_id(repo):
    """A database written before #5358 may hold the row under another id."""
    with repo._session_scope() as session:
        session.add(QueueState(id=7))
        session.commit()

    repo.push_to_history("set", {"track_ids": [1]})

    assert _queue_state_ids(repo) == [7]
    assert repo.get_history_count() == 1


def test_reads_resolve_duplicates_to_the_lowest_id(repo):
    """Where a duplicate already exists, every read picks the same row."""
    with repo._session_scope() as session:
        session.add_all([QueueState(id=3), QueueState(id=2)])
        session.commit()

    entry = repo.push_to_history("set", {"track_ids": [1]})

    assert entry.queue_state_id == 2
    assert repo.get_history_count() == 1
    with repo._session_scope() as session:
        count = session.execute(select(func.count()).select_from(QueueState)).scalar_one()
    assert count == 2  # existing duplicates are left alone, not merged
