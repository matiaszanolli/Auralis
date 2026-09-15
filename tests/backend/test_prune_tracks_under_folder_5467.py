"""
prune_tracks_under_folder() service-level tests (#5467)

Sibling of prune_missing_tracks (#5458): best-effort delegation to the
repository, broadcasting library_tracks_removed only when something was
actually removed, and never raising into the caller on a repository
failure.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from services.missing_tracks import prune_tracks_under_folder
from tests.backend.test_scan_start_and_cancel_frames import _CapturingManager


@pytest.mark.asyncio
async def test_broadcasts_when_tracks_removed():
    library_database = MagicMock()
    library_database.tracks.remove_tracks_under_folder = Mock(return_value=3)
    manager = _CapturingManager()

    removed = await prune_tracks_under_folder(library_database, "/music/old", manager)

    assert removed == 3
    library_database.tracks.remove_tracks_under_folder.assert_called_once_with("/music/old")
    assert manager.frames == [{"type": "library_tracks_removed", "data": {"count": 3}}]


@pytest.mark.asyncio
async def test_no_broadcast_when_nothing_removed():
    library_database = MagicMock()
    library_database.tracks.remove_tracks_under_folder = Mock(return_value=0)
    manager = _CapturingManager()

    removed = await prune_tracks_under_folder(library_database, "/music/old", manager)

    assert removed == 0
    assert manager.frames == []


@pytest.mark.asyncio
async def test_repository_failure_is_swallowed():
    library_database = MagicMock()
    library_database.tracks.remove_tracks_under_folder = Mock(side_effect=RuntimeError("db locked"))
    manager = _CapturingManager()

    removed = await prune_tracks_under_folder(library_database, "/music/old", manager)

    assert removed == 0
    assert manager.frames == []


@pytest.mark.asyncio
async def test_works_without_a_connection_manager():
    library_database = MagicMock()
    library_database.tracks.remove_tracks_under_folder = Mock(return_value=2)

    removed = await prune_tracks_under_folder(library_database, "/music/old", None)

    assert removed == 2
