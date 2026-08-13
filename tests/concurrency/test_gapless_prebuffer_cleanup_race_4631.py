"""
Regression tests for the prebuffer start-vs-cleanup race (#4631)

``start_prebuffering()`` assigns ``self.prebuffer_thread`` only while holding
``_thread_lock``, but ``cleanup()`` used to read that same field **without** the
lock — and ``start_prebuffering()`` checked ``_shutdown`` only *outside* it. Both
halves were needed for the race:

  thread A enters ``start_prebuffering()``, passes the outside ``_shutdown``
  check (not yet set), and stalls. Thread B runs ``cleanup()``: it sets
  ``_shutdown``, reads the *old* ``prebuffer_thread`` (often ``None``) and joins
  it. Thread A resumes, takes ``_thread_lock``, and starts a **new non-daemon**
  thread that ``cleanup()`` has already passed — leaving it unjoined and
  outliving cleanup. Because the thread is deliberately non-daemon (#2075) it can
  hold a file handle past interpreter shutdown.

The fix mirrors the ``_advance_thread`` discipline in
``enhanced_audio_player.cleanup()`` (#3694/#4227): ``cleanup()`` sets
``_shutdown`` first, snapshots the handle *under* ``_thread_lock``, and joins
*outside* it; ``start_prebuffering()`` re-checks ``_shutdown`` *inside* the lock
so no thread can be created once cleanup has begun.

Covers the issue's four test-plan items:
- concurrent start/cleanup leaves no live "GaplessPlayback-Prebuffer" thread
- ``start_prebuffering()`` is a no-op after ``cleanup()``
- the sequential start-then-cleanup path is unregressed
- ``cleanup()`` does not join while holding ``_thread_lock`` (no deadlock)

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import ast
import inspect
import textwrap
import threading
import time
from unittest.mock import Mock

import pytest

from auralis.player.gapless_playback_engine import GaplessPlaybackEngine

PREBUFFER_THREAD_NAME = "GaplessPlayback-Prebuffer"


def _make_engine(**kwargs) -> GaplessPlaybackEngine:
    """An engine whose queue has no next track, so the worker exits promptly.

    The race under test is entirely in the start/cleanup handshake — it does not
    need real audio to be loaded, only for a thread to be *created*.
    """
    queue = Mock()
    queue.peek_next.return_value = None
    queue.has_next_track.return_value = False
    return GaplessPlaybackEngine(file_manager=Mock(), queue_controller=queue, **kwargs)


def _live_prebuffer_threads() -> list[threading.Thread]:
    return [
        t for t in threading.enumerate()
        if t.name == PREBUFFER_THREAD_NAME and t.is_alive()
    ]


@pytest.fixture(autouse=True)
def _no_leaked_prebuffer_threads():
    """Fail loudly rather than leaking a thread into the next test."""
    yield
    for t in _live_prebuffer_threads():
        t.join(timeout=5.0)


class TestStartIsRefusedAfterCleanup:
    """The lock-held ``_shutdown`` re-check is the half that closes the window."""

    def test_start_prebuffering_is_a_noop_after_cleanup(self):
        engine = _make_engine()
        engine.cleanup()

        engine.start_prebuffering()

        assert engine.prebuffer_thread is None, (
            "start_prebuffering() created a thread after cleanup() — the "
            "_shutdown re-check inside _thread_lock is missing (#4631)"
        )

    def test_shutdown_is_rechecked_after_the_fast_path_already_passed(self):
        """Deterministic model of the stall, with no reliance on timing.

        The race needs a caller that passed the *outside* ``_shutdown`` check
        before cleanup set the flag. A plain two-thread test almost never lands
        that interleaving, so drive it directly: an event proxy reports "not
        shutting down" to the fast path exactly once, then tells the truth. That
        is precisely the state a stalled caller resumes into.

        Pre-fix there is no second check, so a non-daemon thread is created after
        cleanup has already run.
        """
        engine = _make_engine()

        class _StallingEvent:
            """Answers the fast path once with False, truthfully thereafter."""

            def __init__(self, inner: threading.Event) -> None:
                self._inner = inner
                self.fast_path_answered = False

            def is_set(self) -> bool:
                if not self.fast_path_answered:
                    self.fast_path_answered = True
                    return False
                return self._inner.is_set()

            def __getattr__(self, name: str):
                return getattr(self._inner, name)

        real_shutdown = engine._shutdown
        real_shutdown.set()  # cleanup() has already run
        engine._shutdown = _StallingEvent(real_shutdown)  # type: ignore[assignment]

        engine.start_prebuffering()

        assert engine._shutdown.fast_path_answered, (
            "fast path was never consulted — test no longer models the stall"
        )
        assert engine.prebuffer_thread is None, (
            "start_prebuffering() created a non-daemon thread even though "
            "_shutdown was set: the check inside _thread_lock is missing, so a "
            "stalled caller can outrun cleanup() (#4631)"
        )
        assert _live_prebuffer_threads() == []


class TestConcurrentStartAndCleanup:
    """The direct regression guard from the issue's test plan."""

    def test_no_prebuffer_thread_survives_concurrent_start_and_cleanup(self):
        """Hammer start() against cleanup() and assert nothing outlives it."""
        iterations = 60
        for _ in range(iterations):
            engine = _make_engine()
            start_barrier = threading.Barrier(2)

            def _starter() -> None:
                start_barrier.wait(timeout=5.0)
                for _ in range(20):
                    engine.start_prebuffering()

            def _cleaner() -> None:
                start_barrier.wait(timeout=5.0)
                engine.cleanup()

            starter = threading.Thread(target=_starter, name="test-starter")
            cleaner = threading.Thread(target=_cleaner, name="test-cleaner")
            starter.start()
            cleaner.start()
            starter.join(timeout=10.0)
            cleaner.join(timeout=10.0)
            assert not starter.is_alive() and not cleaner.is_alive()

            # A thread created after cleanup() passed the join is the bug.
            leaked = _live_prebuffer_threads()
            assert leaked == [], (
                f"prebuffer thread survived cleanup(): {leaked} — a thread was "
                "started after cleanup() read the handle (#4631)"
            )

    def test_cleanup_reads_the_handle_under_the_lock_that_guards_it(self):
        """Deterministic model of the unguarded read in ``cleanup()``.

        A helper holds ``_thread_lock`` — exactly as ``start_prebuffering()``
        does around its assignment — and publishes the thread handle only just
        before releasing it. A ``cleanup()`` that reads the field without the
        lock sees the stale ``None``, skips the join, and returns while the
        thread is still running; a ``cleanup()`` that reads it *under* the lock
        blocks until the handle is published and then joins it.

        Both halves of that are asserted: that cleanup waited for the lock, and
        that it joined what it found.
        """
        engine = _make_engine()
        hold_duration = 0.5

        # The worker exits as soon as cleanup() signals shutdown, so the join
        # below is fast once it actually happens.
        live = threading.Thread(
            target=lambda: engine._shutdown.wait(timeout=10.0),
            daemon=True,
            name=PREBUFFER_THREAD_NAME,
        )
        live.start()

        holder_has_lock = threading.Event()

        def _holder() -> None:
            with engine._thread_lock:
                holder_has_lock.set()
                time.sleep(hold_duration)
                # Publish under the lock, as start_prebuffering() does.
                engine.prebuffer_thread = live

        holder = threading.Thread(target=_holder, name="test-lock-holder")
        holder.start()
        assert holder_has_lock.wait(timeout=5.0)

        started = time.monotonic()
        engine.cleanup()
        elapsed = time.monotonic() - started

        holder.join(timeout=5.0)
        live.join(timeout=5.0)

        assert elapsed >= hold_duration * 0.8, (
            f"cleanup() returned in {elapsed:.3f}s without waiting for "
            f"_thread_lock (held for {hold_duration}s) — it is reading "
            "prebuffer_thread unguarded and can miss a handle published by a "
            "concurrent start_prebuffering() (#4631)"
        )
        assert not live.is_alive(), (
            "cleanup() did not join the prebuffer thread published while it was "
            "waiting for the lock (#4631)"
        )


class TestSequentialPathUnregressed:
    """The fix must not break the ordinary start-then-cleanup flow."""

    def test_start_then_cleanup_joins_the_thread(self):
        engine = _make_engine()

        engine.start_prebuffering()
        created = engine.prebuffer_thread
        assert created is not None, "sequential start must still create a thread"

        engine.cleanup()

        assert not created.is_alive(), "cleanup() did not join the prebuffer thread"

    def test_prebuffering_disabled_still_creates_nothing(self):
        engine = _make_engine(prebuffer_enabled=False)
        engine.start_prebuffering()
        assert engine.prebuffer_thread is None

    def test_repeat_start_does_not_stack_threads(self):
        """The #2075 in-lock double-check must survive the new guard."""
        engine = _make_engine()
        try:
            engine.start_prebuffering()
            first = engine.prebuffer_thread
            engine.start_prebuffering()
            assert engine.prebuffer_thread is first or not first.is_alive()
        finally:
            engine.cleanup()


class TestJoinIsNotHeldUnderTheLock:
    """A join inside ``_thread_lock`` would deadlock a lock-taking worker."""

    def test_cleanup_returns_while_a_worker_is_mid_flight(self):
        """cleanup() must complete within its 5s join budget, not block forever.

        The worker here blocks until released, and the test verifies cleanup()
        gives up at its timeout instead of hanging — which is only observable if
        the join is not serialised behind a lock the worker also needs.
        """
        engine = _make_engine()
        worker_running = threading.Event()
        release_worker = threading.Event()

        def _slow_worker() -> None:
            worker_running.set()
            release_worker.wait(timeout=20.0)

        engine.prebuffer_thread = threading.Thread(
            target=_slow_worker, daemon=True, name=PREBUFFER_THREAD_NAME
        )
        engine.prebuffer_thread.start()
        assert worker_running.wait(timeout=5.0)

        started = time.monotonic()
        engine.cleanup()
        elapsed = time.monotonic() - started

        release_worker.set()
        engine.prebuffer_thread.join(timeout=5.0)

        assert elapsed < 10.0, (
            f"cleanup() took {elapsed:.1f}s — it should time out at its 5s join "
            "budget, not block indefinitely"
        )

    def test_thread_lock_is_released_before_the_join(self):
        """Source-level guard: the join must not be nested in the lock block.

        A timing test can pass by luck if the worker never contends the lock, so
        pin the structure too — this is the property the #3694/#4227 template
        exists to preserve.
        """
        tree = ast.parse(textwrap.dedent(inspect.getsource(GaplessPlaybackEngine.cleanup)))

        with_nodes = [n for n in ast.walk(tree) if isinstance(n, ast.With)]
        assert len(with_nodes) == 1, (
            "expected exactly one `with` block in cleanup(); update this test if "
            "the lock structure changed"
        )
        lock_block = with_nodes[0]

        # The snapshot must be inside the lock...
        assert any(
            isinstance(n, ast.Attribute) and n.attr == "prebuffer_thread"
            for n in ast.walk(lock_block)
        ), "cleanup() no longer snapshots prebuffer_thread under _thread_lock (#4631)"

        # ...and the join must not be. Indentation is not a proxy for this: the
        # join lives inside an `if`, so it is *more* indented than the `with`
        # while still being a sibling of it.
        joins_in_lock = [
            n for n in ast.walk(lock_block)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "join"
        ]
        assert joins_in_lock == [], (
            "join() is nested inside the `with self._thread_lock` block — this "
            "deadlocks against any worker that needs _thread_lock (#4631)"
        )

        all_joins = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "join"
        ]
        assert all_joins, "cleanup() no longer joins the prebuffer thread at all"
