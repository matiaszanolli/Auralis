"""A reference-cloud refresh is one transaction, not three (#6554).

refresh_cloud() used to clear every flag (commit 1), flag the selection
(commit 2) and write its weights (commit 3). A get_reference_cloud() between
them read an empty cloud, or a flagged one whose weights were all 0.0. The test
reads the cloud after every commit a refresh makes.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from auralis.learning.reference_seeder import SeederConfig, refresh_cloud
from auralis.library.migration_manager import MigrationManager
from auralis.library.repositories.fingerprint_repository import FingerprintRepository
from tests.auralis.library.test_reference_cloud_v15 import _seed_track_and_fp


@pytest.fixture
def repo_and_factory():
    db_path = Path(tempfile.mkdtemp()) / "library.db"
    manager = MigrationManager(str(db_path))
    assert manager.migrate_to_latest()
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False, "timeout": 10})
    factory = sessionmaker(bind=engine)
    yield FingerprintRepository(factory), factory
    engine.dispose()
    manager.close()


def _cloud(repo):
    return {fp.track_id: fp.reference_weight for fp in repo.get_reference_cloud()}


def test_a_reader_never_sees_a_partial_cloud_mid_refresh(repo_and_factory, monkeypatch):
    repo, factory = repo_and_factory
    with factory() as session:
        _seed_track_and_fp(session, 1, is_reference=True, reference_weight=0.7, lufs=-25.0)  # dropped
        _seed_track_and_fp(session, 2)
        _seed_track_and_fp(session, 3)
    before = _cloud(repo)

    seen = []
    real_commit = Session.commit

    def commit(self):
        real_commit(self)
        seen.append(_cloud(repo))

    monkeypatch.setattr(Session, "commit", commit)
    refresh_cloud(repo, SeederConfig(max_references_library_fraction=1.0))
    monkeypatch.undo()

    after = _cloud(repo)
    assert set(after) == {2, 3} and all(w > 0.0 for w in after.values())
    partial = [cloud for cloud in seen if cloud not in (before, after)]
    assert not partial, f"a reader saw a half-built cloud mid-refresh: {partial}"

