"""
Regression tests: one shared scanner-stop grace period (#5196)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The manual-scan endpoint and the auto-scanner each hand-rolled the same
stop_scan() + shielded wait with a bare 5-second literal. Both now call
services.scanner_stop.stop_scanner, whose grace period is one env-overridable
constant.

The auto-scanner's copy also only caught TimeoutError/CancelledError, so a scan
that failed during the grace wait raised out of its `except CancelledError`
block and replaced the cancellation being unwound.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import importlib
import logging

import pytest

# tests/backend/conftest.py puts auralis-web/backend on sys.path.
from routers import library_scan
from services import library_auto_scanner, scanner_stop


class _Scanner:
    def __init__(self) -> None:
        self.stopped = False

    def stop_scan(self) -> None:
        self.stopped = True


def test_both_scan_paths_call_the_shared_helper():
    # Compared by name, not identity: the reload test below rebinds the function.
    for module in (library_scan, library_auto_scanner):
        helper = module.stop_scanner
        assert (helper.__module__, helper.__qualname__) == ("services.scanner_stop", "stop_scanner")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, 5.0), ("12", 12.0), ("not-a-number", 5.0), ("0", 5.0)],
)
def test_grace_period_default_and_env_override(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("AURALIS_SCAN_STOP_GRACE_SECONDS", raising=False)
    else:
        monkeypatch.setenv("AURALIS_SCAN_STOP_GRACE_SECONDS", raw)
    try:
        assert importlib.reload(scanner_stop).SCANNER_STOP_GRACE_SECONDS == expected
    finally:
        monkeypatch.undo()
        importlib.reload(scanner_stop)


def test_warns_when_thread_outlives_grace_period(monkeypatch, caplog):
    monkeypatch.setattr(scanner_stop, "SCANNER_STOP_GRACE_SECONDS", 0.01)
    scanner = _Scanner()

    async def stop_a_scan_that_never_finishes() -> None:
        never = asyncio.get_running_loop().create_future()
        await scanner_stop.stop_scanner(scanner, never, label="Auto-scanner")
        never.cancel()

    with caplog.at_level(logging.WARNING, logger="services.scanner_stop"):
        asyncio.run(stop_a_scan_that_never_finishes())

    assert scanner.stopped
    assert "Auto-scanner thread did not exit within 0.01s of stop_scan()" in caplog.text


def test_scan_failure_during_grace_wait_does_not_escape():
    scanner = _Scanner()

    async def stop_a_scan_that_fails() -> None:
        failed = asyncio.get_running_loop().create_future()
        failed.set_exception(RuntimeError("scan blew up"))
        await scanner_stop.stop_scanner(scanner, failed)

    asyncio.run(stop_a_scan_that_fails())  # must not raise
    assert scanner.stopped
