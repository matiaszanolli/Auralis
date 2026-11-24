"""
The startup sweep of the ``.25d`` store runs off the loop and can never stop startup (#6501)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``sweep_fingerprint_store()`` (#6004) is housekeeping: an exception from it must be logged and
read as "nothing swept", or the lifespan, which awaits it bare, aborts with "Application startup
failed". The engine-side ``sweep_orphans`` had tests; the startup step and its wiring did not.
"""

import sys
import threading
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.startup import create_lifespan  # noqa: E402
from config.startup.fingerprint_store import sweep_fingerprint_store  # noqa: E402

pytestmark = pytest.mark.asyncio


class FakeApp:
    """Unused by the startup phase under test."""


def _deps():
    return {
        'HAS_AURALIS': False,
        'HAS_PROCESSING': False,
        'HAS_STREAMLINED_CACHE': False,
        'HAS_SIMILARITY': False,
        'manager': None,
        'globals': {},
    }


async def test_a_failing_sweep_is_logged_and_counts_as_nothing_swept(caplog):
    with patch("config.startup.fingerprint_store.sweep_orphans", side_effect=PermissionError("denied")):
        with caplog.at_level("WARNING", logger="config.startup.fingerprint_store"):
            assert await sweep_fingerprint_store() == 0

    assert any("Fingerprint store sweep failed: PermissionError" in r.getMessage() for r in caplog.records)


async def test_the_sweep_runs_in_a_worker_thread_and_returns_its_count():
    ran_on: list[threading.Thread] = []

    def fake_sweep():
        ran_on.append(threading.current_thread())
        return 7

    with patch("config.startup.fingerprint_store.sweep_orphans", fake_sweep):
        assert await sweep_fingerprint_store() == 7

    assert ran_on and ran_on[0] is not threading.main_thread()


async def test_the_lifespan_runs_the_sweep_and_starts_when_it_fails():
    started = False
    with (
        patch("config.startup._cleanup_temp_directories", AsyncMock()),
        patch("config.startup.sweep_thumbnail_store", AsyncMock(return_value=0)),
        patch("config.startup.fingerprint_store.sweep_orphans", side_effect=OSError("store unreadable")) as sweep,
    ):
        async with create_lifespan(_deps())(FakeApp()):
            started = True

    assert started
    sweep.assert_called_once_with()
