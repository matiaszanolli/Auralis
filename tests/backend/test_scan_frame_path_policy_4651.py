"""
Regression tests for #4651: one documented path-disclosure policy across the
whole scan-frame family (library_scan_started / scan_progress /
library_scan_error), for both the manual-scan router and the auto-scanner.

The policy (recorded in code comments at each emit site): `directories` and
`current_file` carry paths the user themselves chose (a directory dialog
pick, or a configured auto-scan folder) — not a disclosure, and the frontend
already surfaces `current_file` verbatim in a tooltip (ScanStatusCard.tsx).
`library_scan_error`, by contrast, echoes an *unhandled exception's message*,
which can name paths the user never chose, so it stays class-name-only
(#3543) even though the other two intentionally are not.

This asserts the policy end-to-end for one scan: started → progress → error,
verifying `directories`/`current_file` are NOT redacted while `error` IS.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from routers.library_scan import create_library_scan_router  # noqa: E402
from services.library_auto_scanner import LibraryAutoScanner  # noqa: E402

SECRET_PATH = "/secret/music/track.flac"


# ---------------------------------------------------------------------------
# Manual scan router (routers/library_scan.py)
# ---------------------------------------------------------------------------

class _CapturingManager:
    def __init__(self) -> None:
        self.frames: list[dict] = []

    async def broadcast(self, message: dict) -> None:
        self.frames.append(message)

    def types(self) -> list[str]:
        return [f.get("type") for f in self.frames]


class _ProgressThenExplodeScanner:
    """Emits started, then a progress event carrying a path, then raises with
    that same path in the exception message — so one scan exercises all
    three frames in the family."""

    def __init__(self, _manager) -> None:
        self._cb = None

    def set_progress_callback(self, cb) -> None:
        self._cb = cb

    def scan_directories(self, directories=(), **_kwargs):
        if self._cb:
            self._cb({"stage": "started", "directories": list(directories)})
            self._cb({
                "stage": "processing",
                "current_file": SECRET_PATH,
                "processed": 1,
                "total_found": 2,
            })
        raise ValueError(f"{SECRET_PATH}: permission denied")

    def stop_scan(self) -> None:  # pragma: no cover
        pass


def test_manual_scan_frame_family_follows_the_documented_policy(monkeypatch, tmp_path) -> None:
    import auralis.library.scanner as scanner_mod

    monkeypatch.setattr(scanner_mod, "LibraryScanner", _ProgressThenExplodeScanner)
    manager = _CapturingManager()
    app = FastAPI()
    app.include_router(
        create_library_scan_router(lambda: SimpleNamespace(), connection_manager=manager)
    )
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.post("/api/library/scan", json={"directories": [str(tmp_path)]})

    assert resp.status_code == 500
    assert manager.types() == ["library_scan_started", "scan_progress", "library_scan_error"]

    started, progress, error = manager.frames
    # `directories` carries the real, user-chosen path — not redacted.
    assert str(tmp_path.resolve()) in started["data"]["directories"][0] or \
        started["data"]["directories"] == [str(tmp_path)]
    # `current_file` carries the real path — not redacted.
    assert progress["data"]["current_file"] == SECRET_PATH
    # `error` is class-name-only — the path must NOT appear on the wire.
    assert error["data"]["error"] == "ValueError during library scan"
    assert SECRET_PATH not in error["data"]["error"]


# ---------------------------------------------------------------------------
# Auto-scanner (services/library_auto_scanner.py)
# ---------------------------------------------------------------------------

def _make_auto_scanner() -> LibraryAutoScanner:
    return LibraryAutoScanner(
        settings_repo=MagicMock(),
        library_database=MagicMock(),
        fingerprint_queue=None,
        connection_manager=MagicMock(),
    )


@pytest.mark.asyncio
async def test_auto_scanner_frame_family_follows_the_documented_policy(monkeypatch):
    import auralis.library.scanner as scanner_mod

    monkeypatch.setattr(scanner_mod, "LibraryScanner", _ProgressThenExplodeScanner)
    scanner = _make_auto_scanner()
    broadcast_mock = AsyncMock()
    scanner._connection_manager.broadcast = broadcast_mock

    await scanner._do_scan(["/music/library"])

    frames = [call.args[0] for call in broadcast_mock.await_args_list]
    types = [f.get("type") for f in frames]
    assert types == ["library_scan_started", "scan_progress", "library_scan_error"]

    started, progress, error = frames
    assert started["data"]["directories"] == ["/music/library"]
    assert progress["data"]["current_file"] == SECRET_PATH
    assert error["data"]["error"] == "ValueError during library scan"
    assert SECRET_PATH not in error["data"]["error"]
