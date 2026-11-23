"""enqueue-all fetches track ids only, and no more than the queue can hold (#6509).

The route used only `track.id`, but get_missing_fingerprints loaded every column of every track
without a fingerprint (lyrics and comments included) for the whole library, of which the queue
accepts MAX_QUEUE_SIZE. The repository now returns ids, and the route fetches at most the queue's
capacity, still counting the rest as dropped because the queue is full.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.library.migration_manager import MigrationManager  # noqa: E402
from auralis.library.repositories.fingerprint_repository import FingerprintRepository  # noqa: E402
from tests.auralis.library.test_reference_cloud_v15 import _seed_track_and_fp  # noqa: E402


def test_the_repository_returns_ordered_ids_of_tracks_without_a_fingerprint():
    db_path = Path(tempfile.mkdtemp()) / "library.db"
    manager = MigrationManager(str(db_path))
    assert manager.migrate_to_latest()
    engine = create_engine(f"sqlite:///{db_path}")
    factory = sessionmaker(bind=engine)
    from auralis.library.models import Track
    with factory() as session:
        _seed_track_and_fp(session, 2)  # fingerprinted
        for track_id in (7, 3, 9):
            session.add(Track(id=track_id, filepath=f"/m/{track_id}.flac", title=str(track_id),
                              lyrics="la " * 1000, duration=1.0, sample_rate=44100, channels=2, format="FLAC"))
        session.commit()

    repo = FingerprintRepository(factory)
    try:
        assert repo.get_missing_fingerprint_ids() == [3, 7, 9]
        assert repo.get_missing_fingerprint_ids(limit=2) == [3, 7]
    finally:
        engine.dispose()
        manager.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("limit, fetched, dropped", [(None, 3, 7), (2, 2, 0), (8, 3, 5)])
async def test_the_route_fetches_at_most_the_queue_capacity(limit, fetched, dropped):
    from routers import fingerprint_queue as route

    repos = MagicMock()
    repos.fingerprint_stats.get_fingerprint_stats.return_value = {"total": 12, "fingerprinted": 2, "pending": 10}
    repos.fingerprints.get_missing_fingerprint_ids.side_effect = lambda limit: list(range(1, limit + 1))
    queue = MagicMock(MAX_QUEUE_SIZE=3)
    queue.enqueue_many.side_effect = lambda ids: (len(ids), 0, 0)

    with patch("analysis.fingerprint_queue.get_fingerprint_queue", return_value=queue):
        result = await route.enqueue_all_missing_fingerprints(limit=limit, repos=repos)

    repos.fingerprints.get_missing_fingerprint_ids.assert_called_once_with(limit=min(limit or 3, 3))
    assert result["enqueued"] == fetched
    assert result["dropped_queue_full"] == dropped
