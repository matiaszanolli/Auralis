"""The startup wiring connects JobStore to the real repository factory (#5502).

_init_processing_engine builds JobStore(_job_repository), where `_job_repository` looks
`repository_factory.processing_jobs` up in globals_dict at call time. The dedicated persistence
tests construct a JobStore by hand, and the one test that ran the real init used an empty
globals_dict, so only the `None` branch of the closure ran. A rename of that attribute, or a
startup reordering, would have silently put job persistence back to "lost on restart" (#5278).
"""

import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.startup.workers import _init_processing_engine  # noqa: E402
from core.job_models import ProcessingStatus  # noqa: E402
from core.job_store import INTERRUPTED_MESSAGE  # noqa: E402

from auralis.library.database import LibraryDatabase  # noqa: E402

pytestmark = pytest.mark.asyncio


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "library.db"
    LibraryDatabase(database_path=str(path))
    return path


async def _boot(db_path: Path) -> dict[str, Any]:
    """Run the real startup step against a library, as a fresh process would."""
    db = LibraryDatabase(database_path=str(db_path))
    globals_dict: dict[str, Any] = {"repository_factory": db.repositories}
    with patch("config.startup.workers.reclaim_stale_temp_entries"):
        await _init_processing_engine(True, globals_dict)
    return globals_dict


def _rows(db_path: Path) -> dict[str, str]:
    with closing(sqlite3.connect(db_path)) as connection:
        return dict(connection.execute("SELECT job_id, status FROM processing_jobs").fetchall())


async def test_a_job_created_after_startup_is_written_through_the_real_factory(db_path):
    booted = await _boot(db_path)

    job = await booted["processing_engine"].create_job(input_path="/in.wav", settings={"output_format": "wav"})

    assert _rows(db_path) == {job.job_id: "queued"}


async def test_the_next_startup_restores_it_as_interrupted(db_path):
    first = await _boot(db_path)
    job = await first["processing_engine"].create_job(input_path="/in.wav", settings={"output_format": "wav"})

    second = await _boot(db_path)

    restored = await second["processing_engine"].get_job(job.job_id)
    assert restored is not None
    assert restored.status == ProcessingStatus.INTERRUPTED
    assert restored.error_message == INTERRUPTED_MESSAGE
    assert _rows(db_path) == {job.job_id: "interrupted"}


async def test_without_a_repository_factory_the_engine_still_starts_and_persists_nothing(db_path):
    globals_dict: dict[str, Any] = {}
    with patch("config.startup.workers.reclaim_stale_temp_entries"):
        await _init_processing_engine(True, globals_dict)

    job = await globals_dict["processing_engine"].create_job(input_path="/in.wav", settings={})

    assert await globals_dict["processing_engine"].get_job(job.job_id) is not None
    assert _rows(db_path) == {}
