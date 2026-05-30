"""
Regression tests: LibraryAutoScanner._run() outer crash-loop error sanitisation (#3846)

The outer _run() handler must broadcast only the exception *class name*, never
the raw str(exc), so OS paths / permission details don't leak to every connected
WebSocket client.

This is the sibling of the inner _do_scan() fix from #3543.
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.library_auto_scanner import LibraryAutoScanner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scanner() -> tuple[LibraryAutoScanner, MagicMock]:
    """Return a (scanner, broadcast_mock) pair with a minimal mock setup."""
    settings_repo = MagicMock()
    library_manager = MagicMock()
    connection_manager = MagicMock()
    broadcast_mock = AsyncMock()
    scanner = LibraryAutoScanner(
        settings_repo=settings_repo,
        library_manager=library_manager,
        fingerprint_queue=None,
        connection_manager=connection_manager,
    )
    return scanner, broadcast_mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRunOuterErrorSanitisation:
    """_run() outer except branch must not broadcast raw exception text (#3846)."""

    @pytest.mark.asyncio
    async def test_outer_crash_broadcasts_class_name_not_raw_exc(self):
        """
        When _run_cycle() raises with sensitive detail in the message,
        the WS broadcast must contain only the exception class name.
        """
        sensitive_msg = "PermissionError: /home/alice/private/music"
        scanner, _ = _make_scanner()

        call_count = 0
        broadcast_calls: list[dict] = []

        async def _fake_broadcast(manager: object, payload: dict) -> None:
            broadcast_calls.append(payload)

        async def _failing_run_cycle() -> None:
            nonlocal call_count
            call_count += 1
            # First iteration: raise; subsequent: stop the loop
            if call_count == 1:
                raise RuntimeError(sensitive_msg)
            scanner._stop_event.set()

        scanner._run_cycle = _failing_run_cycle  # type: ignore[method-assign]

        with patch(
            "services.library_auto_scanner.connection_manager_safe_broadcast",
            side_effect=_fake_broadcast,
        ):
            # _interruptible_sleep(30) would stall the test — patch it to skip.
            async def _instant_sleep(_seconds: float) -> None:
                pass

            scanner._interruptible_sleep = _instant_sleep  # type: ignore[method-assign]
            await scanner._run()

        assert len(broadcast_calls) == 1, "expected exactly one broadcast after the crash"
        payload = broadcast_calls[0]
        assert payload["type"] == "library_scan_error"
        error_text = payload["data"]["error"]

        # Must NOT contain the raw exception string with sensitive detail
        assert sensitive_msg not in error_text, (
            f"Raw exception leaked in broadcast: {error_text!r}"
        )
        # Must contain the exception class name
        assert "RuntimeError" in error_text

    @pytest.mark.asyncio
    async def test_outer_crash_broadcast_format_matches_inner_handler(self):
        """
        The outer broadcast format is `f"{type(exc).__name__} during library scan"`,
        matching the inner _do_scan() handler (consistency check, #3543 sibling).
        """
        scanner, _ = _make_scanner()
        broadcast_calls: list[dict] = []

        async def _fake_broadcast(manager: object, payload: dict) -> None:
            broadcast_calls.append(payload)

        call_count = 0

        async def _failing_run_cycle() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("internal detail that must not leak")
            scanner._stop_event.set()

        scanner._run_cycle = _failing_run_cycle  # type: ignore[method-assign]

        async def _instant_sleep(_seconds: float) -> None:
            pass

        scanner._interruptible_sleep = _instant_sleep  # type: ignore[method-assign]

        with patch(
            "services.library_auto_scanner.connection_manager_safe_broadcast",
            side_effect=_fake_broadcast,
        ):
            await scanner._run()

        assert broadcast_calls, "expected at least one broadcast"
        error_text = broadcast_calls[0]["data"]["error"]
        assert error_text == "ValueError during library scan"
