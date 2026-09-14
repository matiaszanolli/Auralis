"""Fingerprint claim queries search from a cursor, not the table start (#5310).

Both claim methods used to re-run a query that walked their table from the
lowest id on every claim, past every row already claimed, so a full-library
run was O(N^2). Each queue now searches after the highest id it has claimed
and wraps to the start once when that finds nothing.

Work per claim is measured in SQLite VM steps (a progress handler), not wall
time, so the scaling assertion is deterministic.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import Float, create_engine, event, select
from sqlalchemy.orm import sessionmaker

from auralis.library.models import Base, Track, TrackFingerprint
from auralis.library.repositories.fingerprint_scheduler_repository import (
    FingerprintSchedulerRepository,
)

# Outdated-queue tests use their own versions so they do not depend on the
# shipped FINGERPRINT_ALGORITHM_VERSION having been bumped.
CURRENT_VERSION = 3
OUTDATED_VERSION = 2

_ZEROED_DIMENSIONS = {
    column.name: 0.0
    for column in TrackFingerprint.__table__.columns
    if isinstance(column.type, Float) and column.name not in ("lufs", "reference_weight")
}


class _Library:
    """A file-backed SQLite library that counts VM steps across all connections."""

    VM_STEPS_PER_TICK = 100

    def __init__(self, path: str) -> None:
        self.ticks = 0
        self.engine = create_engine(
            f"sqlite:///{path}", connect_args={"check_same_thread": False, "timeout": 30}
        )
        event.listen(self.engine, "connect", self._on_connect)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

    def _on_connect(self, dbapi_connection: Any, _record: Any) -> None:
        dbapi_connection.execute("PRAGMA synchronous=OFF")  # test speed only

        def tick() -> int:
            self.ticks += 1
            return 0

        dbapi_connection.set_progress_handler(tick, self.VM_STEPS_PER_TICK)

    def add_tracks(self, count: int) -> list[int]:
        with self.session_factory() as session:
            session.add_all(
                Track(title=f"t{i}", filepath=f"/music/t{i}.flac") for i in range(count)
            )
            session.commit()
            return list(session.execute(select(Track.id).order_by(Track.id)).scalars())

    def add_fingerprints(self, track_ids: list[int], version: int) -> None:
        with self.session_factory() as session:
            session.add_all(
                TrackFingerprint(
                    track_id=track_id, lufs=-14.0, fingerprint_version=version,
                    **_ZEROED_DIMENSIONS,
                )
                for track_id in track_ids
            )
            session.commit()

    def cost(self, claim: Callable[[], Any]) -> tuple[int, Any]:
        before = self.ticks
        result = claim()
        return self.ticks - before, result


@pytest.fixture
def library(tmp_path):
    lib = _Library(str(tmp_path / "library.db"))
    yield lib
    lib.engine.dispose()


@pytest.fixture
def tiny_library(tmp_path):
    lib = _Library(str(tmp_path / "tiny.db"))
    yield lib
    lib.engine.dispose()


def _claimer(library: _Library, queue: str) -> tuple[FingerprintSchedulerRepository, Callable[[], Any]]:
    scheduler = FingerprintSchedulerRepository(library.session_factory)
    if queue == "unfingerprinted":
        return scheduler, scheduler.claim_next_unfingerprinted_track
    return scheduler, lambda: scheduler.claim_next_outdated_fingerprint(CURRENT_VERSION)


def _seed(library: _Library, queue: str, count: int) -> list[int]:
    ids = library.add_tracks(count)
    if queue == "outdated":
        library.add_fingerprints(ids, OUTDATED_VERSION)
    return ids


@pytest.mark.parametrize("queue", ["unfingerprinted", "outdated"])
def test_claim_work_does_not_grow_with_library_size(library, tiny_library, queue):
    """Every claim in a 1,500-track run costs about what a claim costs on 5 tracks.

    Comparing against the run's own first claim is not enough: before the fix
    the unfingerprinted query's cost *fell* as rows were claimed (its first
    claim was the most expensive), and the outdated query's cost rose. Both
    shapes scale with the library, which is what this rules out.
    """
    _seed(tiny_library, queue, 5)
    _tiny_scheduler, tiny_claim = _claimer(tiny_library, queue)
    tiny_cost, _ = tiny_library.cost(tiny_claim)
    bound = tiny_cost * 4 + 20

    ids = _seed(library, queue, 1500)
    _scheduler, claim = _claimer(library, queue)
    costs: dict[str, int] = {}
    costs["first"], first = library.cost(claim)
    for _ in range(len(ids) // 2 - 1):
        claim()
    costs["middle"], _ = library.cost(claim)
    for _ in range(len(ids) - len(ids) // 2 - 2):
        claim()
    costs["last"], last = library.cost(claim)

    assert first.id == ids[0]
    assert last.id == ids[-1]
    assert max(costs.values()) <= bound, (tiny_cost, costs)


def test_a_released_unfingerprinted_claim_is_picked_up_on_the_wrap(library):
    ids = _seed(library, "unfingerprinted", 5)
    scheduler, claim = _claimer(library, "unfingerprinted")

    assert [claim().id for _ in range(3)] == ids[:3]
    assert scheduler.release_claim(ids[0]) is True

    assert [claim().id for _ in range(3)] == [ids[3], ids[4], ids[0]]
    assert claim() is None


def test_a_released_outdated_claim_is_picked_up_on_the_wrap(library):
    ids = _seed(library, "outdated", 4)
    scheduler, claim = _claimer(library, "outdated")

    assert [claim().id for _ in range(2)] == ids[:2]
    assert scheduler.release_claim(ids[0]) is True  # version 0 -> 1, outdated again

    assert [claim().id for _ in range(3)] == [ids[2], ids[3], ids[0]]
    assert claim() is None


@pytest.mark.parametrize("queue", ["unfingerprinted", "outdated"])
def test_concurrent_claimers_claim_every_track_exactly_once(library, queue):
    ids = _seed(library, queue, 200)
    _scheduler, claim = _claimer(library, queue)
    claimed: list[int] = []
    claimed_lock = threading.Lock()

    def worker() -> None:
        misses = 0
        while misses < 20:  # a race lost to another worker also returns None
            track = claim()
            if track is None:
                misses += 1
                continue
            misses = 0
            with claimed_lock:
                claimed.append(track.id)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert sorted(claimed) == ids
