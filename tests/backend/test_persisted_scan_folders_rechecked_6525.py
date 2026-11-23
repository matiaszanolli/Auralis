"""Persisted scan folders are re-checked when read, not only when saved (#6525).

``validate_user_chosen_directory`` refuses operating-system trees and the app's
scratch roots when a folder is added. Startup registration and the auto-scanner
read the settings row back without those checks, so a profile saved before they
existed (or a local write to the settings DB) kept ``/`` on the file allowlist
and in every scan.
"""

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.library.data_dir import get_data_dir  # noqa: E402
from config.startup.components import _register_scan_folders  # noqa: E402
from security.path_allowlist import clear_extra_allowed_directories, get_allowed_directories  # noqa: E402
from security.path_security import trusted_scan_folders  # noqa: E402
from services.library_auto_scanner import LibraryAutoScanner  # noqa: E402


@pytest.fixture
def music(tmp_path):
    folder = tmp_path / "Music"
    folder.mkdir()
    return folder


@pytest.fixture(autouse=True)
def _clean_allowlist():
    clear_extra_allowed_directories()
    yield
    clear_extra_allowed_directories()


def test_root_system_and_scratch_roots_are_dropped(music):
    unmounted = music.parent / "ExternalDrive" / "Albums"  # does not exist: kept for when it returns
    folders = ["/", "/usr", tempfile.gettempdir(), str(get_data_dir()), str(music), str(unmounted)]

    assert trusted_scan_folders(folders) == [str(music), str(unmounted)]


def test_startup_registers_only_the_trusted_folders(music):
    settings = SimpleNamespace(scan_folders=json.dumps(["/", str(music)]))
    repo = MagicMock(get_settings=MagicMock(return_value=settings))
    before = set(get_allowed_directories())

    _register_scan_folders({"settings_repository": repo})

    assert set(get_allowed_directories()) - before == {music.resolve()}
    assert Path("/") not in get_allowed_directories()


@pytest.mark.asyncio
async def test_an_auto_scan_cycle_never_scans_or_watches_a_stored_root(music):
    settings = SimpleNamespace(auto_scan=True, scan_folders=json.dumps(["/", str(music)]), scan_interval=3600)
    scanner = LibraryAutoScanner(
        settings_repo=MagicMock(get_settings=MagicMock(return_value=settings)),
        library_database=MagicMock(), fingerprint_queue=None, connection_manager=MagicMock(),
    )
    scanner._do_scan = AsyncMock()  # type: ignore[method-assign]
    scanner._sync_watchdog = AsyncMock()  # type: ignore[method-assign]
    scanner._interruptible_sleep = AsyncMock()  # type: ignore[method-assign]

    await scanner._run_cycle()

    scanner._sync_watchdog.assert_awaited_once_with([str(music)])
    scanner._do_scan.assert_awaited_once_with([str(music)])
