"""Workers that lose a claim race try the next track instead of quitting (#6080).

claim_next_unfingerprinted_track returned None both for "queue empty" and for "another
worker claimed this row first" (IntegrityError). All workers start with the same cursor
and find() the same row, so most lost the first race, read None as "queue empty", and
left the pool for good: 3 of 8 workers survived in the audit's repro.
"""

import tempfile
import threading
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auralis.library.migration_manager import MigrationManager
from auralis.library.models import Track
from auralis.library.repositories.fingerprint_scheduler_repository import (
    FingerprintSchedulerRepository,
)

TRACKS = 40
WORKERS = 8


def _repo():
    db_path = Path(tempfile.mkdtemp()) / "library.db"
    assert MigrationManager(str(db_path)).migrate_to_latest()
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False, "timeout": 30})
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        for i in range(1, TRACKS + 1):
            session.add(Track(
                id=i, filepath=f"/tmp/t{i}.flac", title=f"T{i}", duration=60.0,
                sample_rate=44100, channels=2, format="FLAC",
            ))
        session.commit()
    return FingerprintSchedulerRepository(session_factory)


def test_concurrent_claimers_each_get_distinct_tracks_until_the_queue_is_empty():
    repo = _repo()
    claimed: list[int] = []
    lock = threading.Lock()
    barrier = threading.Barrier(WORKERS)

    def worker():
        barrier.wait()  # every worker calls find() with the same cursor
        while True:
            track = repo.claim_next_unfingerprinted_track()
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


def test_a_worker_that_loses_the_first_race_still_gets_a_track():
    repo = _repo()
    barrier = threading.Barrier(WORKERS)
    first_claims: list[object] = [None] * WORKERS

    def worker(index):
        barrier.wait()
        first_claims[index] = repo.claim_next_unfingerprinted_track()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(WORKERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert all(claim is not None for claim in first_claims), "a worker lost its race and got None"
    assert len({c.id for c in first_claims}) == WORKERS  # type: ignore[union-attr]
