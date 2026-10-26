"""The scan progress bridge shared by the manual and auto scan paths (#5912).

Replaces an older copy-of-the-closure test (#3864) that exercised its own
re-implementation rather than the code in production. These drive the real
``services.scan_events.make_progress_callback`` on a live loop.
"""

import asyncio
import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.scan_events import make_progress_callback  # noqa: E402

pytestmark = pytest.mark.asyncio


async def _settle() -> None:
    # The callback hops onto the loop via call_soon_threadsafe, then creates a
    # task: two yields run both, a few more let the done-callback fire.
    for _ in range(5):
        await asyncio.sleep(0)


def _bridge(fallback_dirs=("/music",)):
    manager = MagicMock()
    manager.broadcast = AsyncMock()
    callback = make_progress_callback(asyncio.get_running_loop(), manager, list(fallback_dirs))
    return callback, manager


def _frames(manager) -> list[dict]:
    return [call.args[0] for call in manager.broadcast.await_args_list]


class TestProgressFrames:
    async def test_started_event_becomes_library_scan_started_with_the_fallback_dirs(self):
        callback, manager = _bridge(["/music", "/more"])

        callback({"stage": "started"})
        await _settle()

        assert _frames(manager) == [
            {"type": "library_scan_started", "data": {"directories": ["/music", "/more"]}}
        ]

    async def test_started_event_prefers_the_directories_the_scanner_reports(self):
        callback, manager = _bridge()

        callback({"stage": "started", "directories": ["/resolved"]})
        await _settle()

        assert _frames(manager)[0]["data"] == {"directories": ["/resolved"]}

    async def test_progress_prefers_the_pre_counted_total_and_real_fraction(self):
        callback, manager = _bridge()

        callback({
            "stage": "processing", "processed": 50, "total_found": 60,
            "total_expected": 200, "progress": 0.25, "current_file": "/music/a.mp3",
        })
        await _settle()

        assert _frames(manager) == [{
            "type": "scan_progress",
            "data": {
                "current": 50, "total": 200, "percentage": 25,
                "current_file": "/music/a.mp3", "phase": "processing",
            },
        }]

    async def test_counting_frame_names_its_directory_when_it_has_no_file(self):
        """Both scan paths share this fallback (#5912): the manual one used to send null."""
        callback, manager = _bridge()

        callback({
            "stage": "counting", "directory": "/music/rock",
            "total_found": 500, "processed": 0, "progress": None,
        })
        await _settle()

        data = _frames(manager)[0]["data"]
        assert data["current_file"] == "/music/rock"
        assert data["total"] == 500
        assert data["percentage"] is None
        assert data["phase"] == "counting"


class TestFailuresAreLogged:
    """A failure on the bridge must leave a trail, not vanish (#3864, #5912)."""

    @pytest.mark.parametrize("malformed", ["not a dict", None, 42])
    async def test_malformed_progress_data_is_logged(self, malformed, caplog):
        callback, _ = _bridge()

        with caplog.at_level(logging.ERROR):
            callback(malformed)  # type: ignore[arg-type]
            await _settle()

        assert any("Background task" in r.getMessage() for r in caplog.records)

    async def test_a_failed_broadcast_is_logged(self, caplog):
        callback, manager = _bridge()
        manager.broadcast.side_effect = RuntimeError("socket closed")

        with caplog.at_level(logging.ERROR):
            callback({"stage": "processing", "processed": 1})
            await _settle()

        assert any(
            "Background task" in r.getMessage() and r.exc_info and "socket closed" in str(r.exc_info[1])
            for r in caplog.records
        )
