"""
QueueManager Concurrency Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Verifies that QueueManager's threading.RLock prevents index-out-of-bounds
errors when next_track() (playback thread) and remove_track() (REST API
thread pool) race on self.tracks and self.current_index.

Acceptance criteria (issue #2427):
- All public methods hold the RLock.
- Concurrent next_track() + remove_track() calls over 10 000 iterations
  produce no exceptions.
"""

import random
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from auralis.player.components.queue_manager import QueueManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

INITIAL_QUEUE_SIZE = 20
ITERATIONS = 10_000


def _make_track(track_id: int) -> dict:
    return {"id": track_id, "title": f"Track {track_id}", "duration": 180}


def _populate(qm: QueueManager, n: int = INITIAL_QUEUE_SIZE) -> None:
    qm.add_tracks([_make_track(i) for i in range(n)])
    qm.set_track_by_index(0)


# ---------------------------------------------------------------------------
# Lock presence
# ---------------------------------------------------------------------------

class TestLockPresence:
    """QueueManager must declare threading.RLock (fixes #2427)."""

    def test_lock_attribute_exists(self):
        qm = QueueManager()
        assert hasattr(qm, "_lock"), "_lock not found on QueueManager"

    def test_lock_is_rlock(self):
        qm = QueueManager()
        # RLock type is not directly importable; check via type name
        lock_type = type(qm._lock).__name__
        assert "RLock" in lock_type, (
            f"_lock should be threading.RLock, got {lock_type}. "
            "A plain Lock would deadlock on reentrant calls "
            "(remove_tracks → remove_track, shuffle → get_current_track, etc.)"
        )


# ---------------------------------------------------------------------------
# Core concurrency test (acceptance criteria)
# ---------------------------------------------------------------------------

class TestConcurrentNextAndRemove:
    """
    Spawn two threads: one calls next_track() in a loop, the other calls
    remove_track() randomly. Assert no exceptions after ITERATIONS total ops.
    """

    def test_no_exception_after_10000_iterations(self):
        qm = QueueManager()
        qm.repeat_enabled = True  # prevent next_track() returning None at end
        _populate(qm)

        errors: list[Exception] = []
        barrier = threading.Barrier(2)

        def advance_thread():
            """Simulates the playback thread advancing through tracks."""
            barrier.wait()
            for _ in range(ITERATIONS // 2):
                try:
                    qm.next_track()
                    # Refill when empty so the test stays active
                    if qm.get_queue_size() == 0:
                        _populate(qm)
                except Exception as exc:
                    errors.append(exc)

        def remove_thread():
            """Simulates REST API handler removing a random queue entry."""
            barrier.wait()
            for i in range(ITERATIONS // 2):
                try:
                    size = qm.get_queue_size()
                    if size > 0:
                        idx = random.randint(0, size - 1)
                        qm.remove_track(idx)
                    # Periodically refill so the queue doesn't stay empty
                    if i % 50 == 0:
                        qm.add_track(_make_track(i + INITIAL_QUEUE_SIZE))
                except Exception as exc:
                    errors.append(exc)

        t1 = threading.Thread(target=advance_thread, daemon=True)
        t2 = threading.Thread(target=remove_thread, daemon=True)
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        assert not t1.is_alive(), "advance_thread timed out"
        assert not t2.is_alive(), "remove_thread timed out"
        assert errors == [], (
            f"Concurrent next_track/remove_track raised {len(errors)} exception(s). "
            f"First: {errors[0]!r}"
        )


# ---------------------------------------------------------------------------
# Additional concurrency scenarios
# ---------------------------------------------------------------------------

class TestConcurrentMixedOps:
    """Multiple simultaneous writers stress-test all public mutators."""

    def test_concurrent_add_and_remove(self):
        qm = QueueManager()
        _populate(qm)

        errors: list[Exception] = []

        def adder():
            for i in range(500):
                try:
                    qm.add_track(_make_track(1000 + i))
                except Exception as exc:
                    errors.append(exc)

        def remover():
            for _ in range(500):
                try:
                    size = qm.get_queue_size()
                    if size > 0:
                        qm.remove_track(random.randint(0, size - 1))
                except Exception as exc:
                    errors.append(exc)

        def navigator():
            for _ in range(500):
                try:
                    qm.next_track()
                    qm.previous_track()
                except Exception as exc:
                    errors.append(exc)

        threads = [
            threading.Thread(target=adder, daemon=True),
            threading.Thread(target=remover, daemon=True),
            threading.Thread(target=navigator, daemon=True),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert all(not t.is_alive() for t in threads), "A thread timed out"
        assert errors == [], f"{len(errors)} exception(s) from mixed ops: {errors[0]!r}"

    def test_concurrent_shuffle_and_remove(self):
        qm = QueueManager()
        _populate(qm, n=30)
        qm.set_track_by_index(5)

        errors: list[Exception] = []

        def shuffler():
            for _ in range(200):
                try:
                    qm.shuffle()
                except Exception as exc:
                    errors.append(exc)

        def remover():
            for _ in range(200):
                try:
                    size = qm.get_queue_size()
                    if size > 0:
                        qm.remove_track(random.randint(0, size - 1))
                except Exception as exc:
                    errors.append(exc)

        t1 = threading.Thread(target=shuffler, daemon=True)
        t2 = threading.Thread(target=remover, daemon=True)
        t1.start(); t2.start()
        t1.join(timeout=10); t2.join(timeout=10)

        assert errors == [], f"shuffle/remove race: {errors}"

    def test_concurrent_reorder_and_next(self):
        qm = QueueManager()
        _populate(qm, n=10)

        errors: list[Exception] = []

        def reorderer():
            for _ in range(100):
                try:
                    size = qm.get_queue_size()
                    if size > 1:
                        order = list(range(size))
                        random.shuffle(order)
                        qm.reorder_tracks(order)
                except Exception as exc:
                    errors.append(exc)

        def advancer():
            for _ in range(200):
                try:
                    qm.next_track()
                except Exception as exc:
                    errors.append(exc)

        t1 = threading.Thread(target=reorderer, daemon=True)
        t2 = threading.Thread(target=advancer, daemon=True)
        t1.start(); t2.start()
        t1.join(timeout=10); t2.join(timeout=10)

        assert errors == [], f"reorder/next race: {errors}"

    def test_concurrent_clear_and_next(self):
        """clear() must not leave current_index dangling for next_track()."""
        qm = QueueManager()
        _populate(qm)

        errors: list[Exception] = []

        def clearer():
            for _ in range(50):
                try:
                    qm.clear()
                    _populate(qm)
                except Exception as exc:
                    errors.append(exc)

        def advancer():
            for _ in range(500):
                try:
                    qm.next_track()
                except Exception as exc:
                    errors.append(exc)

        t1 = threading.Thread(target=clearer, daemon=True)
        t2 = threading.Thread(target=advancer, daemon=True)
        t1.start(); t2.start()
        t1.join(timeout=10); t2.join(timeout=10)

        assert errors == [], f"clear/next race: {errors}"

    def test_remove_tracks_batch_is_atomic(self):
        """remove_tracks() holds the lock for the full batch, not per-item."""
        qm = QueueManager()
        _populate(qm, n=20)

        errors: list[Exception] = []

        def batch_remover():
            for _ in range(100):
                try:
                    size = qm.get_queue_size()
                    if size >= 3:
                        indices = random.sample(range(size), 3)
                        qm.remove_tracks(indices)
                except Exception as exc:
                    errors.append(exc)

        def adder():
            for i in range(300):
                try:
                    qm.add_track(_make_track(100 + i))
                except Exception as exc:
                    errors.append(exc)

        t1 = threading.Thread(target=batch_remover, daemon=True)
        t2 = threading.Thread(target=adder, daemon=True)
        t1.start(); t2.start()
        t1.join(timeout=10); t2.join(timeout=10)

        assert errors == [], f"remove_tracks/add race: {errors}"


# ---------------------------------------------------------------------------
# State invariant checks
# ---------------------------------------------------------------------------

class TestStateInvariants:
    """current_index must always be valid after concurrent operations."""

    def test_current_index_always_valid_after_concurrent_ops(self):
        qm = QueueManager()
        _populate(qm)

        stop = threading.Event()

        def writer():
            i = 0
            while not stop.is_set():
                qm.add_track(_make_track(500 + i))
                size = qm.get_queue_size()
                if size > 5:
                    qm.remove_track(random.randint(0, size - 1))
                qm.next_track()
                i += 1

        t = threading.Thread(target=writer, daemon=True)
        t.start()

        for _ in range(1000):
            size = qm.get_queue_size()
            idx = qm.current_index
            # current_index must be -1 (empty) or within [0, size)
            assert idx == -1 or 0 <= idx < max(size, 1), (
                f"current_index={idx} out of bounds for queue size={size}"
            )

        stop.set()
        t.join(timeout=5)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
