"""
Processing jobs survive a backend restart (#5278)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

ProcessingEngine kept jobs only in `self.jobs`, so a restart or crash erased
every queued and running job and its status endpoint answered 404. Jobs are
now written to the library's `processing_jobs` table at each lifecycle
transition, and a new engine restores them on startup: unfinished ones as
`interrupted`, expired ones dropped.

A "restart" here is a second ProcessingEngine over the same database file.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import job_execution
from core.job_models import ProcessingStatus
from core.job_store import INTERRUPTED_MESSAGE, JobStore
from core.processing_engine import ProcessingEngine
from routers.processing_jobs import get_job_status

from auralis.__version__ import __db_schema_version__
from auralis.library.database import LibraryDatabase


@pytest.fixture
def db_path(tmp_path: Path) -> Iterator[Path]:
    path = tmp_path / "library.db"
    LibraryDatabase(database_path=str(path))
    yield path


def _engine(db_path: Path, **kwargs: Any) -> ProcessingEngine:
    """A fresh engine (a "process") over the library at ``db_path``."""
    db = LibraryDatabase(database_path=str(db_path))
    return ProcessingEngine(job_store=JobStore(lambda: db.repositories.processing_jobs), **kwargs)


def _rows(db_path: Path) -> dict[str, str]:
    with closing(sqlite3.connect(db_path)) as connection:
        return dict(connection.execute("SELECT job_id, status FROM processing_jobs").fetchall())


async def _create(engine: ProcessingEngine) -> str:
    job = await engine.create_job(input_path="/in.wav", settings={"output_format": "wav"})
    return job.job_id


class TestRestart:

    async def test_a_job_queued_before_a_restart_is_reported_interrupted(self, db_path: Path) -> None:
        job_id = await _create(_engine(db_path))
        assert _rows(db_path) == {job_id: "queued"}

        after = _engine(db_path)
        assert await after.restore_jobs() == 1

        job = await after.get_job(job_id)
        assert job is not None
        assert job.status == ProcessingStatus.INTERRUPTED
        assert job.error_message == INTERRUPTED_MESSAGE
        assert job.completed_at is not None
        response = await get_job_status(job_id, engine=after)
        assert response.status == ProcessingStatus.INTERRUPTED
        assert _rows(db_path) == {job_id: "interrupted"}

    async def test_a_finished_job_comes_back_unchanged(self, db_path: Path) -> None:
        before = _engine(db_path)
        job_id = await _create(before)
        job = await before.get_job(job_id)
        assert job is not None
        job.status = ProcessingStatus.COMPLETED
        job.progress = 100.0
        job.result_data = {"lufs": -14.0}
        job.completed_at = datetime.now()
        await before.job_store.save(job)

        after = _engine(db_path)
        await after.restore_jobs()

        restored = await after.get_job(job_id)
        assert restored is not None
        assert restored.status == ProcessingStatus.COMPLETED
        assert restored.result_data == {"lufs": -14.0}
        assert restored.settings == {"output_format": "wav"}
        assert restored.created_at == job.created_at

    async def test_expired_jobs_are_dropped_on_restore(self, db_path: Path) -> None:
        before = _engine(db_path)
        job_id = await _create(before)
        job = await before.get_job(job_id)
        assert job is not None
        job.status = ProcessingStatus.FAILED
        job.completed_at = datetime.now() - timedelta(hours=2)
        await before.job_store.save(job)

        after = _engine(db_path, completed_job_ttl_hours=1.0)

        assert await after.restore_jobs() == 0
        assert await after.get_job(job_id) is None
        assert _rows(db_path) == {}

    async def test_a_restart_without_a_library_restores_nothing(self) -> None:
        engine = ProcessingEngine(job_store=JobStore(lambda: None))
        await _create(engine)
        assert await ProcessingEngine().restore_jobs() == 0


class TestLifecycleWrites:

    async def test_a_failed_job_is_recorded_running_then_failed(self, db_path: Path) -> None:
        engine = _engine(db_path)
        job_id = await _create(engine)
        job = await engine.get_job(job_id)
        assert job is not None
        seen: list[str] = []
        original_save = engine.job_store.save

        async def spy(saved: Any) -> None:
            seen.append(saved.status.value)
            await original_save(saved)

        with patch.object(engine.job_store, "save", side_effect=spy), \
             patch.object(job_execution, "load_audio", side_effect=OSError("unreadable")):
            await engine.process_job(job)

        assert seen == ["processing", "failed"]
        assert _rows(db_path) == {job_id: "failed"}

    async def test_cancelling_a_queued_job_is_recorded(self, db_path: Path) -> None:
        engine = _engine(db_path)
        job_id = await _create(engine)

        assert await engine.cancel_job(job_id)

        assert _rows(db_path) == {job_id: "cancelled"}

    async def test_expiry_sweep_deletes_the_records(self, db_path: Path) -> None:
        engine = _engine(db_path)
        job_id = await _create(engine)
        job = await engine.get_job(job_id)
        assert job is not None
        job.status = ProcessingStatus.COMPLETED
        job.completed_at = datetime.now() - timedelta(hours=3)
        await engine.job_store.save(job)

        assert await engine.cleanup_old_jobs(max_age_hours=1) == 1
        assert _rows(db_path) == {}

    async def test_a_job_rejected_by_a_full_queue_is_not_persisted(self, db_path: Path) -> None:
        engine = _engine(db_path, max_queue_size=1)
        await engine.submit_job(await engine.create_job(input_path="/a.wav", settings={}))
        rejected = await engine.create_job(input_path="/b.wav", settings={})

        with pytest.raises(asyncio.QueueFull):
            await engine.submit_job(rejected)

        assert rejected.job_id not in _rows(db_path)

    async def test_a_failing_store_never_fails_the_job(self) -> None:
        def broken() -> Any:
            raise RuntimeError("database is locked")

        engine = ProcessingEngine(job_store=JobStore(broken))
        job_id = await _create(engine)

        assert await engine.get_job(job_id) is not None
        assert await engine.restore_jobs() == 0


def test_a_v19_library_gains_the_table_on_upgrade(db_path: Path) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("DROP TABLE processing_jobs")
        connection.execute("DELETE FROM schema_version")
        connection.execute(
            "INSERT INTO schema_version (version, description, migration_script) "
            "VALUES (19, 'test', 'test')"
        )
        connection.commit()
    assert __db_schema_version__ == 20

    LibraryDatabase(database_path=str(db_path))

    assert _rows(db_path) == {}
    with closing(sqlite3.connect(db_path)) as connection:
        versions = [v for (v,) in connection.execute("SELECT version FROM schema_version")]
    assert max(versions) == 20
