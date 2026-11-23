"""A scan folder removed while a scan walks it keeps no rows once the scan ends (#6556).

Removing a folder prunes its rows once (#5467), but an auto or manual scan
already walking it went on adding rows under it, which then stayed in the
library; outside the default directories their files were no longer trusted,
so they were visible-but-broken. Both scan paths now record the scan folders
when they start and prune again under any the settings no longer list once
the scan thread is done. The fake scans below add a track under each folder,
let the removal land (settings write plus its one-shot prune, as the settings
router does), then add one more track under the removed folder.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import services.library_auto_scanner as auto_scanner_mod  # noqa: E402
from routers.library_scan_events import publish_scan_result  # noqa: E402
from services.library_auto_scanner import LibraryAutoScanner  # noqa: E402
from tests.backend.test_scan_start_and_cancel_frames import _CapturingManager  # noqa: E402

from auralis.library.database import LibraryDatabase  # noqa: E402
from auralis.library.scan_models import ScanResult  # noqa: E402


@pytest.fixture
def library():
    root = Path(tempfile.mkdtemp())
    library_database = LibraryDatabase(str(root / "library.db"))
    removed, kept = str(root / "removed"), str(root / "kept")
    for folder in (removed, kept):
        library_database.settings.add_scan_folder(folder)
    yield library_database, removed, kept
    library_database.shutdown()


def _add(library_database, folder, name):
    track = library_database.tracks.add({
        "filepath": f"{folder}/{name}.flac", "title": name, "artists": ["Artist"],
        "duration": 60.0, "sample_rate": 44100, "channels": 2, "format": "FLAC",
    })
    assert track is not None


def _walk_while_removed(library_database, removed, kept):
    """What a scan thread does when the user removes ``removed`` halfway through."""
    _add(library_database, removed, "before")
    _add(library_database, kept, "kept")
    library_database.settings.remove_scan_folder(removed)
    library_database.tracks.remove_tracks_under_folder(removed, keep_folders=[kept])
    _add(library_database, removed, "after")  # the walk goes on
    return ScanResult(files_found=3, files_processed=3, files_added=3, scan_time=1.0, directories_scanned=2)


def _paths(library_database):
    tracks, _total = library_database.tracks.get_all(limit=100)
    return sorted(Path(t.filepath).name for t in tracks)


@pytest.mark.asyncio
async def test_auto_scan_leaves_no_rows_under_a_folder_removed_mid_scan(library, monkeypatch):
    library_database, removed, kept = library
    import auralis.library.scanner as scanner_mod

    class _Scanner:
        def __init__(self, _db):
            pass

        def set_progress_callback(self, _cb):
            pass

        def scan_directories(self, directories, **_kwargs):
            assert directories == [removed, kept]
            return _walk_while_removed(library_database, removed, kept)

    monkeypatch.setattr(scanner_mod, "LibraryScanner", _Scanner)
    monkeypatch.setattr(auto_scanner_mod, "prune_missing_tracks", AsyncMock(return_value=0))  # files are fake
    scanner = LibraryAutoScanner(
        settings_repo=MagicMock(), library_database=library_database,
        fingerprint_queue=None, connection_manager=_CapturingManager(),
    )

    await scanner._do_scan([removed, kept])

    assert _paths(library_database) == ["kept.flac"]


@pytest.mark.asyncio
async def test_manual_scan_leaves_no_rows_under_a_folder_removed_mid_scan(library, monkeypatch):
    library_database, removed, kept = library
    monkeypatch.setattr("routers.library_scan_events.prune_missing_tracks", AsyncMock(return_value=0))
    result = _walk_while_removed(library_database, removed, kept)

    await publish_scan_result(_CapturingManager(), library_database, result, [removed, kept])

    assert _paths(library_database) == ["kept.flac"]


@pytest.mark.asyncio
async def test_an_unreadable_folder_list_prunes_nothing(library, monkeypatch):
    """A scan_folders value that cannot be parsed is unknown, not empty: pruning every folder
    the scan started with as 'removed' would empty the library."""
    library_database, removed, kept = library
    _add(library_database, removed, "a")
    monkeypatch.setattr(library_database.settings, "get_settings", lambda: MagicMock(scan_folders="{not json"))
    monkeypatch.setattr("routers.library_scan_events.prune_missing_tracks", AsyncMock(return_value=0))

    await publish_scan_result(_CapturingManager(), library_database, ScanResult(), [removed, kept])

    assert _paths(library_database) == ["a.flac"]
