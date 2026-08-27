"""
Regression tests for lifespan shutdown step isolation (#4569)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The shutdown block used to be one large try/except whose three earliest steps —
the BACKGROUND_WORKER_KEYS stop loop, `streamlined_worker.stop()` and
`processing_engine.stop_worker()` — had no individual guards. A single failing
worker jumped to the outer handler and skipped *every* remaining step, including
`LibraryManager.shutdown()` and its SQLite WAL checkpoint. Repeated occurrences
grow `library.db-wal` and leave the DB needing recovery on next open.

`config/background_workers.stop_background_workers` already guarded each worker
individually; the lifespan re-implemented the same loop without that protection,
so the two paths #4111 unified had diverged on error handling.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import inspect
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.background_workers import BACKGROUND_WORKER_KEYS, WORKER_STOP_KWARGS
from config.startup import _ROLLBACK_SERVICES_TO_STOP, _shutdown_components

pytestmark = pytest.mark.asyncio


def _globals(**overrides):
    """A globals_dict with every shutdown participant present and healthy."""
    base = {key: Mock(stop=AsyncMock()) for key in BACKGROUND_WORKER_KEYS}
    base['streamlined_worker'] = Mock(stop=AsyncMock())
    base['processing_engine'] = Mock(stop_worker=AsyncMock(), close_processor_pool=AsyncMock())
    base['audio_player'] = Mock(stop=Mock(), cleanup=Mock())
    base['library_database'] = Mock(shutdown=Mock())
    base.update(overrides)
    return base


def _quiet_externals():
    """Patch the three module-level imports the shutdown path reaches for."""
    return (
        patch("core.processor_factory.get_processor_factory", MagicMock()),
        patch("services.artwork_downloader.close_artwork_downloader", AsyncMock()),
        patch("analysis.fingerprint_generator.shutdown_fingerprint_executor_bounded", AsyncMock()),
    )


async def _run(globals_dict):
    factory, artwork, fingerprint = _quiet_externals()
    with factory, artwork, fingerprint:
        await _shutdown_components(globals_dict)


class TestOneFailingStepDoesNotSkipTheRest:
    """The core regression: no step may abort the ones after it."""

    async def test_failing_background_worker_still_checkpoints_wal(self):
        g = _globals()
        g['auto_scanner'].stop = AsyncMock(side_effect=RuntimeError("scanner wedged"))

        await _run(g)

        g['library_database'].shutdown.assert_called_once()
        # And the workers *after* the failing one still stopped.
        g['fingerprint_queue'].stop.assert_awaited_once()

    async def test_failing_streamlined_worker_does_not_skip_later_steps(self):
        g = _globals()
        g['streamlined_worker'].stop = AsyncMock(side_effect=RuntimeError("boom"))

        await _run(g)

        g['processing_engine'].stop_worker.assert_awaited_once()
        g['library_database'].shutdown.assert_called_once()

    async def test_failing_processing_engine_does_not_skip_library_shutdown(self):
        g = _globals()
        g['processing_engine'].stop_worker = AsyncMock(side_effect=RuntimeError("boom"))

        await _run(g)

        g['audio_player'].stop.assert_called_once()
        g['library_database'].shutdown.assert_called_once()

    async def test_failing_processor_pool_drain_does_not_skip_library_shutdown(self):
        """#5061: close_processor_pool sits right after stop_worker/before the
        library shutdown; it must be as isolated as every other step."""
        g = _globals()
        g['processing_engine'].close_processor_pool = AsyncMock(side_effect=RuntimeError("boom"))

        await _run(g)

        g['audio_player'].stop.assert_called_once()
        g['library_database'].shutdown.assert_called_once()

    async def test_every_step_failing_still_reaches_the_last_one(self):
        g = _globals()
        for key in BACKGROUND_WORKER_KEYS:
            g[key].stop = AsyncMock(side_effect=RuntimeError(key))
        g['streamlined_worker'].stop = AsyncMock(side_effect=RuntimeError("sw"))
        g['processing_engine'].stop_worker = AsyncMock(side_effect=RuntimeError("pe"))
        g['audio_player'].stop = Mock(side_effect=RuntimeError("ap"))

        await _run(g)

        g['library_database'].shutdown.assert_called_once()

    async def test_library_database_failure_is_contained(self):
        g = _globals()
        g['library_database'].shutdown = Mock(side_effect=RuntimeError("wal locked"))

        await _run(g)  # must not raise


class TestHappyPath:
    async def test_stops_every_component_exactly_once(self):
        g = _globals()

        await _run(g)

        for key in BACKGROUND_WORKER_KEYS:
            g[key].stop.assert_awaited_once()
        g['streamlined_worker'].stop.assert_awaited_once()
        g['processing_engine'].stop_worker.assert_awaited_once()
        # #5061 WIRING check: close_processor_pool must actually be invoked
        # from the shutdown path, not just exist as a dead method.
        g['processing_engine'].close_processor_pool.assert_awaited_once()
        g['audio_player'].stop.assert_called_once()
        g['audio_player'].cleanup.assert_called_once()
        g['library_database'].shutdown.assert_called_once()

    async def test_stop_order_is_documented_order(self):
        """auto_scanner first — it may enqueue into the fingerprint queues."""
        order: list[str] = []
        g = _globals()
        for key in BACKGROUND_WORKER_KEYS:
            g[key].stop = AsyncMock(side_effect=lambda *a, k=key, **kw: order.append(k))

        await _run(g)

        assert order == list(BACKGROUND_WORKER_KEYS)
        assert order[0] == "auto_scanner"

    async def test_fingerprint_queue_still_receives_its_timeout(self):
        """Routing through the shared helper must not drop the stop kwargs."""
        g = _globals()

        await _run(g)

        g['fingerprint_queue'].stop.assert_awaited_once_with(timeout=30.0)
        g['auto_scanner'].stop.assert_awaited_once_with()

    async def test_absent_components_are_skipped(self):
        """An empty globals_dict (startup failed early) must not raise."""
        await _run({})


class TestFingerprintExecutorShutdown:
    """#4756: the fingerprint ThreadPoolExecutor used to be torn down only
    via atexit — never by the lifespan — so it ran after (not before) the
    library-database shutdown step, and could race an in-flight fingerprint
    computation against the WAL checkpoint. shutdown_fingerprint_executor_bounded()
    must now run as its own guarded step, ordered before library_database.shutdown()."""

    async def test_called_before_library_shutdown(self):
        order: list[str] = []
        g = _globals()
        g['library_database'].shutdown = Mock(side_effect=lambda: order.append("library"))

        factory, artwork, _ = _quiet_externals()
        fingerprint_mock = AsyncMock(side_effect=lambda **kw: order.append("fingerprint"))
        with factory, artwork, patch(
            "analysis.fingerprint_generator.shutdown_fingerprint_executor_bounded",
            fingerprint_mock,
        ):
            await _shutdown_components(g)

        assert order == ["fingerprint", "library"], (
            "fingerprint executor shutdown must run before the library database "
            "shutdown step (#4756)"
        )

    async def test_fingerprint_shutdown_is_awaited(self):
        g = _globals()
        factory, artwork, _ = _quiet_externals()
        with factory, artwork, patch(
            "analysis.fingerprint_generator.shutdown_fingerprint_executor_bounded",
            new_callable=AsyncMock,
        ) as fingerprint_mock:
            await _shutdown_components(g)

        fingerprint_mock.assert_awaited_once()

    async def test_failing_fingerprint_shutdown_does_not_skip_library_shutdown(self):
        """A raising fingerprint-shutdown step must not abort the rest —
        matching every other step's isolation guarantee (#4569's pattern)."""
        g = _globals()
        factory, artwork, _ = _quiet_externals()
        with factory, artwork, patch(
            "analysis.fingerprint_generator.shutdown_fingerprint_executor_bounded",
            AsyncMock(side_effect=RuntimeError("executor wedged")),
        ):
            await _shutdown_components(g)  # must not raise

        g['library_database'].shutdown.assert_called_once()


class TestSingleSourceOfTruth:
    """#4569 CONSISTENCY/SIBLING — one definition of how a worker is stopped."""

    def test_rollback_kwargs_derive_from_the_canonical_set(self):
        assert _ROLLBACK_SERVICES_TO_STOP == tuple(
            (key, WORKER_STOP_KWARGS.get(key, {})) for key in BACKGROUND_WORKER_KEYS
        )

    def test_shutdown_uses_the_shared_helper_not_an_inline_loop(self):
        src = inspect.getsource(_shutdown_components)
        assert "stop_background_workers(" in src, (
            "shutdown must delegate to the guarded helper (#4569)"
        )
        assert "for _worker_key in BACKGROUND_WORKER_KEYS" not in src, (
            "the unguarded inline loop must not come back"
        )

    def test_every_teardown_call_sits_inside_its_own_try(self):
        """No shutdown step may rely on the outer catch-all.

        AST-based rather than textual: find every `.stop()` / `.stop_worker()` /
        `.shutdown()` call in the function and assert each one is nested inside a
        `try` *other than* the outermost last-resort net. The fleet stop is
        exempt — `stop_background_workers` guards each worker internally.
        """
        import ast
        import textwrap

        TEARDOWN = {"stop", "stop_worker", "shutdown", "cleanup"}
        fn = ast.parse(textwrap.dedent(inspect.getsource(_shutdown_components))).body[0]
        body = [n for n in fn.body if not isinstance(n, ast.Expr)]
        assert len(body) == 1 and isinstance(body[0], ast.Try), (
            "expected a single outer try as the last-resort net"
        )
        outer = body[0]

        def teardown_calls(node):
            return {
                n.lineno
                for n in ast.walk(node)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr in TEARDOWN
            }

        all_calls = teardown_calls(outer)
        guarded = set()
        for node in ast.walk(outer):
            if isinstance(node, ast.Try) and node is not outer:
                guarded |= teardown_calls(node)

        assert all_calls, "no teardown calls found — test is looking at the wrong thing"
        assert not (all_calls - guarded), (
            f"unguarded teardown call(s) at relative line(s) {sorted(all_calls - guarded)} "
            "— a failure there skips every later step, including the WAL checkpoint (#4569)"
        )
