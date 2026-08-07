"""
Regression: lifespan shutdown runs even when cancelled at yield (#4801)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The lifespan generator's `yield` was not wrapped in try/finally, so a
BaseException thrown into the generator at that point — the canonical case
being CancelledError from a forced/second-SIGINT exit tearing down the
lifespan task rather than sending a clean `lifespan.shutdown` message —
propagated straight out and `_shutdown_components` (SQLite WAL checkpoint,
aiohttp session close, worker/thread-pool teardown) never ran.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.startup import create_lifespan  # noqa: E402

pytestmark = pytest.mark.asyncio


def _minimal_deps():
    """HAS_AURALIS/HAS_PROCESSING/HAS_STREAMLINED_CACHE all False so the
    lifespan's startup phase does nothing beyond the (separately tested)
    chunk-dir cleanup and leftover-stream-temp sweep before reaching
    `yield` — no library DB, processing engine, or cache worker needed."""
    return {
        'HAS_AURALIS': False,
        'HAS_PROCESSING': False,
        'HAS_STREAMLINED_CACHE': False,
        'HAS_SIMILARITY': False,
        'manager': None,
        'globals': {},
    }


class FakeApp:
    """Stand-in for the FastAPI app object the lifespan context manager
    receives — unused by the startup phase under test."""


class TestShutdownRunsUnderCancellation:
    async def test_shutdown_runs_when_cancelled_error_thrown_at_yield(self, tmp_path):
        lifespan = create_lifespan(_minimal_deps())

        with (
            patch("tempfile.gettempdir", return_value=str(tmp_path)),
            patch("config.startup._shutdown_components", new=AsyncMock()) as mock_shutdown,
        ):
            with pytest.raises(asyncio.CancelledError):
                async with lifespan(FakeApp()):
                    # Simulates Starlette's Router.lifespan() having a
                    # CancelledError thrown into the `await receive()` inside
                    # `async with self.lifespan_context(app)` — e.g. a forced
                    # second-SIGINT exit rather than a clean shutdown message.
                    raise asyncio.CancelledError()

        mock_shutdown.assert_awaited_once()

    async def test_shutdown_runs_when_any_base_exception_thrown_at_yield(self, tmp_path):
        """Acceptance criterion: 'or any BaseException', not just CancelledError."""
        lifespan = create_lifespan(_minimal_deps())

        class _ForcedTeardown(BaseException):
            pass

        with (
            patch("tempfile.gettempdir", return_value=str(tmp_path)),
            patch("config.startup._shutdown_components", new=AsyncMock()) as mock_shutdown,
        ):
            with pytest.raises(_ForcedTeardown):
                async with lifespan(FakeApp()):
                    raise _ForcedTeardown()

        mock_shutdown.assert_awaited_once()

    async def test_normal_clean_shutdown_still_runs_exactly_once(self, tmp_path):
        """Regression guard: try/finally must not cause shutdown to run
        twice (or zero times) on the ordinary, non-cancelled exit path."""
        lifespan = create_lifespan(_minimal_deps())

        with (
            patch("tempfile.gettempdir", return_value=str(tmp_path)),
            patch("config.startup._shutdown_components", new=AsyncMock()) as mock_shutdown,
        ):
            async with lifespan(FakeApp()):
                pass

        mock_shutdown.assert_awaited_once()
