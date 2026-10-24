"""Regression tests: queue edits re-validate and re-arm the prebuffer (#5583)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#5508's listener was `invalidate_prebuffer` bare: every queue edit cleared
the buffer — including appends that leave the next track untouched — and
nothing called `start_prebuffering()` afterwards, so the next transition
always took the blocking-decode fallback instead of a gapless swap.

The listener is now `on_queue_changed`: keep the buffer when the peek still
matches it (shared #2303 match rule), otherwise invalidate and re-arm; the
worker re-peeks before storing so a queue edit during its load discards the
stale result and loads the fresh next track.

Real GaplessPlaybackEngine + QueueController; the blocking decode is
stubbed at the module's `load` so no filesystem is involved.
"""

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from auralis.player import gapless_playback_engine
from auralis.player.gapless_playback_engine import GaplessPlaybackEngine
from auralis.player.queue_controller import QueueController


def _track(n: int) -> dict:
    return {'id': n, 'title': f'Track {n}', 'file_path': f'/music/track_{n}.mp3'}


def _fake_audio() -> np.ndarray:
    return np.zeros((4410, 2), dtype=np.float32)


def _wait_until(predicate, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


@pytest.fixture
def setup() -> tuple[GaplessPlaybackEngine, QueueController, list[str]]:
    queue = QueueController(get_repository_factory=lambda: MagicMock())
    queue.set_queue([_track(1), _track(2), _track(3)], 0)
    engine = GaplessPlaybackEngine(queue, queue)
    # Wire the listener exactly as EnhancedAudioPlayer does (#5583).
    queue.set_change_listener(engine.on_queue_changed)
    loaded: list[str] = []

    with patch.object(gapless_playback_engine, "load") as load_mock:
        load_mock.side_effect = lambda file_path, file_type="audio": (
            loaded.append(file_path) or (_fake_audio(), 44100)
        )
        yield engine, queue, loaded

    engine.cleanup()


def _start_and_wait_prebuffered(engine: GaplessPlaybackEngine) -> bool:
    engine.start_prebuffering()
    return _wait_until(
        lambda: engine.next_track_buffer is not None
        or engine.next_track_info is not None
    )


class TestOnQueueChanged:
    def test_append_that_keeps_next_keeps_the_buffer(self, setup):
        """The #5583 defect: add_track(C) cleared a still-valid buffer for B
        and nothing re-armed it. The buffer must survive the edit."""
        eng, queue, _ = setup
        assert _start_and_wait_prebuffered(eng)
        buffered_id = eng.next_track_info['id']

        queue.add_track(_track(9))  # append: next track unchanged

        with eng.update_lock:
            assert eng.next_track_buffer is not None
            assert eng.next_track_info['id'] == buffered_id

    def test_edit_that_changes_next_invalidates_and_re_arms(self, setup):
        eng, queue, _ = setup
        assert _start_and_wait_prebuffered(eng)

        # Remove the currently-playing track 1: the next track becomes a
        # different one, so the old buffer is stale — it must be dropped and
        # prebuffering re-armed for the new next track.
        queue.remove_track(0)

        assert _wait_until(
            lambda: eng.next_track_info is not None
            and eng.next_track_info['id'] == queue.peek_next_track()['id']
        )
        with eng.update_lock:
            assert eng.next_track_buffer is not None

    def test_worker_discards_a_stale_load_and_loads_the_fresh_next(self, setup):
        """A queue edit landing during the worker's blocking decode must not
        leave a stale buffer stored (and no buffer for the real next track):
        the worker re-peeks, discards, and loads the fresh next."""
        eng, queue, loaded = setup

        gate = {"release": False}
        entered: list[str] = []

        def gated_load(file_path: str, file_type: str = "audio"):
            entered.append(file_path)  # the worker has reached load()
            # Hold the first load until the queue edit has landed.
            while not gate["release"]:
                time.sleep(0.01)
            loaded.append(file_path)
            return _fake_audio(), 44100

        with patch.object(gapless_playback_engine, "load", side_effect=gated_load):
            eng.start_prebuffering()  # worker peeks track 2, blocks in load
            # `loaded` only grows after the gate releases (three lines down),
            # so the reachable-here signal is `entered`. The original wait
            # watched `loaded`, a predicate that could never fire, and a
            # short-circuiting truthy operand hid both facts (#6237).
            assert _wait_until(
                lambda: len(entered) > 0 or eng._shutdown.is_set()
            ), (
                "prebuffer worker never reached load() before the queue change"
            )

            queue.remove_track(0)  # next track is now track 3, not 2
            gate["release"] = True

        assert _wait_until(
            lambda: eng.next_track_info is not None
            and eng.next_track_info['id'] == queue.peek_next_track()['id']
        )
        with eng.update_lock:
            assert eng.next_track_buffer is not None
            # The stale track 2 buffer must not have been kept.
            assert eng.next_track_info['id'] != 2
