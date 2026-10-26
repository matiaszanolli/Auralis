"""
Removed scan-folder paths stay out of INFO/ERROR log lines (#5990)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

INFO is persisted to electron-log and pasted into bug reports, and
``sanitize_log_value`` only strips control characters, so the absolute scan
folder (home directory name and library layout) must be logged as a basename at
INFO/ERROR, with the full path only at DEBUG.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.missing_tracks import prune_tracks_under_folder  # noqa: E402


def _db(result):
    db = MagicMock()
    if isinstance(result, Exception):
        db.tracks.remove_tracks_under_folder.side_effect = result
    else:
        db.tracks.remove_tracks_under_folder.return_value = result
    return db


@pytest.mark.asyncio
async def test_success_log_names_the_folder_without_its_absolute_path(tmp_path, caplog):
    folder = tmp_path / "user" / "Music"

    with caplog.at_level(logging.DEBUG):
        removed = await prune_tracks_under_folder(_db(3), str(folder), None)

    assert removed == 3
    loud = [r.getMessage() for r in caplog.records if r.levelno >= logging.INFO]
    assert any("Music" in m for m in loud)
    assert not any(str(tmp_path) in m for m in loud)
    assert any(str(folder) in r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG)


@pytest.mark.asyncio
async def test_failure_log_names_the_folder_without_its_absolute_path(tmp_path, caplog):
    folder = tmp_path / "user" / "Music"

    with caplog.at_level(logging.DEBUG):
        removed = await prune_tracks_under_folder(_db(RuntimeError("boom")), str(folder), None)

    assert removed == 0
    loud = [r.getMessage() for r in caplog.records if r.levelno >= logging.INFO]
    assert any("boom" in m and "Music" in m for m in loud)
    assert not any(str(tmp_path) in m for m in loud)
