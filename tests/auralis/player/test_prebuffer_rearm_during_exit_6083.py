"""A queue edit landing as the prebuffer worker finishes is not lost (#6083)

``on_queue_changed`` invalidates the buffer and calls ``start_prebuffering()``, which is a no-op
while a worker is alive. If the edit landed after the worker's final re-peek, the worker stored
the buffer for the OLD next track and exited; nothing re-armed, so the next transition took the
blocking-decode fallback. ``start_prebuffering()`` now leaves a re-arm request the worker honours
before it exits.
"""

from unittest.mock import MagicMock

import numpy as np


def _entry(n: int) -> dict:
    return {"id": n, "file_path": f"/t{n}.wav"}


def test_queue_edit_after_the_final_repeek_gets_a_second_pass(gapless_playback_engine):
    engine = gapless_playback_engine
    engine.prebuffer_enabled = True
    engine._load_audio = MagicMock(side_effect=lambda path: (np.zeros(512, dtype=np.float32), 44100))

    state = {"next": _entry(1), "calls": 0}

    def peek():
        state["calls"] += 1
        result = state["next"]
        # Call 3 is the worker's final re-peek (1: start of pass, 2: nothing, see below). The queue
        # is edited right after it returns the old entry, and the listener runs while the worker
        # is still alive.
        if state["calls"] == 2:
            state["next"] = _entry(2)
            engine.on_queue_changed()
        return result

    engine.queue = MagicMock()
    engine.queue.peek_next_track.side_effect = peek

    engine.start_prebuffering()
    engine.prebuffer_thread.join(timeout=5)

    assert not engine.prebuffer_thread.is_alive()
    assert engine.next_track_info == _entry(2)
    assert engine._load_audio.call_args_list[-1].args == ("/t2.wav",)


def test_a_worker_with_no_pending_request_exits_and_a_later_start_spawns_a_new_one(gapless_playback_engine):
    engine = gapless_playback_engine
    engine.prebuffer_enabled = True
    engine._load_audio = MagicMock(side_effect=lambda path: (np.zeros(512, dtype=np.float32), 44100))
    engine.queue = MagicMock()
    engine.queue.peek_next_track.return_value = _entry(1)

    engine.start_prebuffering()
    first = engine.prebuffer_thread
    first.join(timeout=5)
    engine.invalidate_prebuffer()
    engine.start_prebuffering()
    second = engine.prebuffer_thread
    second.join(timeout=5)

    assert second is not first
    assert engine.next_track_info == _entry(1)
