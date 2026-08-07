"""
Regression: fingerprint queue module global cleared on rollback/shutdown (#4803)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Startup installs the on-demand fingerprint queue in two places — the
component registry (globals_dict['ondemand_fingerprint_queue']) and a
module-level global via set_fingerprint_queue(). Rollback/teardown only
knew about the registry entry; nothing ever called set_fingerprint_queue(None),
so all 8 real consumers (which read the module global via
get_fingerprint_queue(), not the registry) kept enqueueing into a stopped
queue after a failed boot.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from analysis.fingerprint_queue import get_fingerprint_queue, set_fingerprint_queue
from config.startup import _rollback_partial_startup, _shutdown_components

pytestmark = pytest.mark.asyncio


def _running_service() -> Mock:
    svc = Mock()
    svc.stop = AsyncMock()
    return svc


@pytest.fixture(autouse=True)
def _reset_module_global():
    """The module global is process-wide state — isolate each test from
    whatever the previous one (or a real startup elsewhere in the suite)
    left behind, and restore it afterward so this file can't poison others."""
    set_fingerprint_queue(None)
    yield
    set_fingerprint_queue(None)


class TestRollbackClearsTheModuleGlobal:
    async def test_get_fingerprint_queue_returns_none_after_rollback(self):
        stopped_queue = _running_service()
        set_fingerprint_queue(stopped_queue)
        assert get_fingerprint_queue() is stopped_queue  # sanity: it was live

        globals_dict = {'ondemand_fingerprint_queue': stopped_queue}
        await _rollback_partial_startup(globals_dict)

        assert get_fingerprint_queue() is None, (
            "the module global must be cleared, not left pointing at the "
            "now-stopped queue object the registry entry was nulled to"
        )

    async def test_registry_and_module_global_agree_after_rollback(self):
        """Both the registry entry and the module global consumers actually
        read must report the same 'unavailable' state — this is the specific
        divergence #4803 is about."""
        stopped_queue = _running_service()
        set_fingerprint_queue(stopped_queue)
        globals_dict = {'ondemand_fingerprint_queue': stopped_queue}

        await _rollback_partial_startup(globals_dict)

        assert globals_dict['ondemand_fingerprint_queue'] is None
        assert get_fingerprint_queue() is None

    async def test_a_failing_stop_still_clears_the_module_global(self):
        """The module-global clear must run even when the queue's own
        .stop() raised — matching the existing 'best-effort, one failure
        doesn't skip the rest' contract of rollback."""
        broken_queue = Mock()
        broken_queue.stop = AsyncMock(side_effect=RuntimeError("stop failed"))
        set_fingerprint_queue(broken_queue)
        globals_dict = {'ondemand_fingerprint_queue': broken_queue}

        await _rollback_partial_startup(globals_dict)  # must not raise

        assert get_fingerprint_queue() is None

    async def test_rollback_without_a_queue_ever_started_does_not_raise(self):
        """Rollback can fire before the fingerprint queue was ever created —
        clearing an already-None global must be a safe no-op."""
        await _rollback_partial_startup({})  # must not raise
        assert get_fingerprint_queue() is None


class TestNormalShutdownAlsoClearsTheModuleGlobal:
    """Completeness check: the fix must apply at every path that stops the
    queue, not just _rollback_partial_startup."""

    async def test_shutdown_components_clears_the_module_global(self):
        stopped_queue = _running_service()
        set_fingerprint_queue(stopped_queue)
        globals_dict = {'ondemand_fingerprint_queue': stopped_queue}

        await _shutdown_components(globals_dict)

        assert get_fingerprint_queue() is None


class TestConsumersTakeTheUnavailableBranchAfterRollback:
    """Integration-style: a real consumer call path must observe the
    unavailable state, not silently enqueue onto a dead queue."""

    async def test_similarity_router_enqueue_takes_the_unavailable_branch(self):
        stopped_queue = _running_service()
        stopped_queue.enqueue = Mock(return_value=True)
        set_fingerprint_queue(stopped_queue)

        await _rollback_partial_startup({'ondemand_fingerprint_queue': stopped_queue})

        # Mirrors routers/similarity.py's own call pattern exactly.
        queue = get_fingerprint_queue()
        assert queue is None, "consumer must see None and skip queue.enqueue(...)"
        stopped_queue.enqueue.assert_not_called()
