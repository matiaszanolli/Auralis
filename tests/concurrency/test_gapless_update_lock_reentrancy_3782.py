"""
Regression tests for GaplessPlaybackEngine.update_lock reentrancy (#3782)

``advance_with_prebuffer()`` is only ever called by
``enhanced_audio_player.next_track()`` while it already holds
``AudioFileManager._audio_lock``, and ``advance_with_prebuffer()`` itself
nests ``file_manager._audio_lock`` inside ``update_lock`` — producing
``_audio_lock -> update_lock -> _audio_lock`` (reentrant). Before the fix,
``update_lock`` was a plain non-reentrant ``threading.Lock``; the nesting only
worked because the inner ``_audio_lock`` re-acquisition is a same-thread RLock
reentry, and the geometry was fragile against any future change that touches
either lock. #3782 promotes ``update_lock`` to ``threading.RLock`` so the
nesting is safe independent of ``_audio_lock``'s own reentrancy.

Covers:
- ``update_lock`` is an ``RLock`` (not a plain ``Lock``)
- concurrent ``next_track()`` calls (the only production path that nests
  ``update_lock`` inside ``_audio_lock``) do not deadlock under load

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import threading
import time
from unittest.mock import Mock

from auralis.player.config import PlayerConfig
from auralis.player.enhanced_audio_player import AudioPlayer
from auralis.player.gapless_playback_engine import GaplessPlaybackEngine


def _make_player() -> AudioPlayer:
    return AudioPlayer(
        config=PlayerConfig(),
        get_repository_factory=lambda: Mock(),
    )


class TestUpdateLockIsReentrant:
    def test_update_lock_allows_same_thread_reentry(self):
        """Behavioral proof: a plain Lock would block/deadlock on the second
        same-thread acquire; an RLock does not (#3782)."""
        player = _make_player()
        lock = player.gapless.update_lock

        assert lock.acquire(timeout=1), "first acquire must succeed"
        try:
            assert lock.acquire(timeout=1), (
                "update_lock did not allow same-thread re-entry — "
                "regression of #3782 (plain Lock deadlocks here)"
            )
            lock.release()
        finally:
            lock.release()

    def test_update_lock_type_is_rlock_class(self):
        engine = GaplessPlaybackEngine(file_manager=Mock(), queue_controller=Mock())
        assert type(engine.update_lock).__name__ == "RLock"


class TestConcurrentNextTrackDoesNotDeadlock:
    """The only production path that nests update_lock inside _audio_lock."""

    def test_no_deadlock_under_concurrent_next_track(self, test_audio_files):
        player = _make_player()
        assert player.load_file(test_audio_files[0])
        for f in test_audio_files:
            player.queue.add_track({'title': 'T', 'file_path': f})
        player.queue.repeat_enabled = True  # keep the queue non-exhausting

        stop = threading.Event()
        errors: list[BaseException] = []

        def worker() -> None:
            try:
                while not stop.is_set():
                    player.next_track()
            except BaseException as exc:  # pragma: no cover - diagnostic
                errors.append(exc)

        threads = [threading.Thread(target=worker, daemon=True) for _ in range(4)]
        for t in threads:
            t.start()

        time.sleep(2.0)
        stop.set()
        for t in threads:
            t.join(timeout=10.0)

        assert not any(t.is_alive() for t in threads), (
            "next_track() loop did not complete — deadlock (regression of #3782)"
        )
        assert not errors, f"Unexpected errors: {errors}"
