"""The outdated-fingerprint claim survives a lost race, and a DB error is not "queue empty" (#6334).

#6080 fixed this for the unfingerprinted queue only. ``claim_next_outdated_fingerprint``
still returned ``None`` when its UPDATE lost the race (``rowcount != 1``), and both claim
methods logged a database error and returned ``None`` through ``_guarded``. A worker reads
``None`` as "queue empty" and leaves the phase for good, so after a version bump most of
the pool quit in the first round, and one lock timeout stranded a worker until restart.
"""

import tempfile
import threading
from pathlib import Path

import pytest
from sqlalchemy import Float, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from auralis.library.migration_manager import MigrationManager
from auralis.library.models import Track, TrackFingerprint
from auralis.library.repositories.fingerprint_scheduler_repository import (
    FingerprintSchedulerRepository,
)

TRACKS = 40
WORKERS = 8
CURRENT_VERSION = 3
OUTDATED_VERSION = 2

_ZEROED_DIMENSIONS = {
    column.name: 0.0
    for column in TrackFingerprint.__table__.columns
    if isinstance(column.type, Float) and column.name not in ("lufs", "reference_weight")
}


def _repo(outdated: int = TRACKS, fresh: int = 0):
    """A library with *outdated* stale-version fingerprints and *fresh* tracks without any."""
    db_path = Path(tempfile.mkdtemp()) / "library.db"
    assert MigrationManager(str(db_path)).migrate_to_latest()
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False, "timeout": 30})
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        for i in range(1, outdated + fresh + 1):
            session.add(Track(
                id=i, filepath=f"/tmp/t{i}.flac", title=f"T{i}", duration=60.0,
                sample_rate=44100, channels=2, format="FLAC",
            ))
        session.commit()
        for i in range(1, outdated + 1):
            session.add(TrackFingerprint(
                track_id=i, lufs=-14.0, fingerprint_version=OUTDATED_VERSION, **_ZEROED_DIMENSIONS,
            ))
        session.commit()
    return FingerprintSchedulerRepository(session_factory), session_factory


def test_concurrent_claimers_each_get_distinct_outdated_tracks_until_none_are_left():
    repo, _ = _repo()
    claimed: list[int] = []
    lock = threading.Lock()
    barrier = threading.Barrier(WORKERS)

    def worker():
        barrier.wait()  # every worker calls find() with the same cursor
        while True:
            track = repo.claim_next_outdated_fingerprint(CURRENT_VERSION)
            if track is None:  # the only way out must be "queue empty"
                return
            with lock:
                claimed.append(track.id)

    threads = [threading.Thread(target=worker) for _ in range(WORKERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert sorted(claimed) == list(range(1, TRACKS + 1))  # nothing lost, nothing claimed twice


def test_a_worker_that_loses_the_first_outdated_race_still_gets_a_track():
    repo, _ = _repo()
    barrier = threading.Barrier(WORKERS)
    first_claims: list[object] = [None] * WORKERS

    def worker(index):
        barrier.wait()
        first_claims[index] = repo.claim_next_outdated_fingerprint(CURRENT_VERSION)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(WORKERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert all(claim is not None for claim in first_claims), "a worker lost its race and got None"
    assert len({c.id for c in first_claims}) == WORKERS  # type: ignore[union-attr]


def test_a_race_lost_after_find_moves_on_to_the_next_track_instead_of_reporting_empty():
    """Deterministic: a competitor claims exactly the row this call just found."""
    repo, session_factory = _repo(outdated=3)
    real_find = repo._find_after_cursor
    raced: list[int] = []

    def find_then_lose_the_row(queue, find):
        row = real_find(queue, find)
        if row is not None and not raced:
            raced.append(row[0])
            with session_factory() as other:
                other.query(TrackFingerprint).filter_by(track_id=row[0]).update({"fingerprint_version": 0})
                other.commit()
        return row

    repo._find_after_cursor = find_then_lose_the_row  # type: ignore[method-assign]

    claimed = repo.claim_next_outdated_fingerprint(CURRENT_VERSION)

    assert raced == [1]
    assert claimed is not None and claimed.id == 2


@pytest.mark.parametrize("method", ["claim_next_unfingerprinted_track", "claim_next_outdated_fingerprint"])
def test_a_database_error_propagates_instead_of_reading_as_an_empty_queue(method):
    repo, _ = _repo(outdated=2, fresh=2)

    def locked(_queue, _find):
        raise OperationalError("SELECT", {}, Exception("database is locked"))

    repo._find_after_cursor = locked  # type: ignore[method-assign]
    claim = getattr(repo, method)
    args = (CURRENT_VERSION,) if method == "claim_next_outdated_fingerprint" else ()

    with pytest.raises(OperationalError):
        claim(*args)


def test_a_transient_error_leaves_the_queue_claimable():
    repo, _ = _repo(outdated=2)
    real_find = repo._find_after_cursor
    calls = {"n": 0}

    def locked_once(queue, find):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OperationalError("SELECT", {}, Exception("database is locked"))
        return real_find(queue, find)

    repo._find_after_cursor = locked_once  # type: ignore[method-assign]

    with pytest.raises(OperationalError):
        repo.claim_next_outdated_fingerprint(CURRENT_VERSION)
    claimed = repo.claim_next_outdated_fingerprint(CURRENT_VERSION)

    assert claimed is not None and claimed.id == 1  # nothing was lost to the failed attempt
