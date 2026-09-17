"""
Regression test: every queue edit invalidates the gapless prebuffer (#5508)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Only AudioPlayer's own clear_queue/set_shuffle/set_repeat wrappers used to
call gapless.invalidate_prebuffer(). The backend edits the queue through
QueueController directly, so a reorder/remove/insert/set_queue left a stale
prebuffered "next" track. QueueController now notifies a change listener,
which AudioPlayer wires to the gapless engine.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from auralis.player.queue_controller import QueueController


def _track(n: int) -> dict:
    return {'id': n, 'title': f'Track {n}', 'filepath': f'/music/track_{n}.mp3'}


def _controller(n_tracks: int = 4) -> tuple[QueueController, MagicMock]:
    ctrl = QueueController(get_repository_factory=lambda: MagicMock())
    ctrl.set_queue([_track(i) for i in range(n_tracks)])
    listener = MagicMock()
    ctrl.set_change_listener(listener)
    return ctrl, listener


# (description, mutation) — each must notify exactly once.
_MUTATIONS = [
    ("add_track", lambda c: c.add_track(_track(9))),
    ("insert_track", lambda c: c.insert_track(1, _track(9))),
    ("remove_track", lambda c: c.remove_track(2)),
    ("remove_if_index_matches_current", lambda c: c.remove_if_index_matches_current(2)),
    ("reorder_tracks", lambda c: c.reorder_tracks([3, 2, 1, 0])),
    ("move_track", lambda c: c.move_track(0, 3)),
    ("shuffle", lambda c: c.shuffle()),
    ("set_queue", lambda c: c.set_queue([_track(7), _track(8)])),
    ("clear_queue", lambda c: c.clear_queue()),
    ("clear", lambda c: c.clear()),
    ("set_shuffle", lambda c: c.set_shuffle(True)),
    ("set_repeat", lambda c: c.set_repeat(True)),
]


@pytest.mark.parametrize("name,mutate", _MUTATIONS, ids=[m[0] for m in _MUTATIONS])
def test_mutation_notifies_listener(name, mutate):
    ctrl, listener = _controller()
    mutate(ctrl)
    assert listener.call_count == 1, name


def test_unshuffle_notifies_only_when_restored():
    ctrl, listener = _controller()
    assert ctrl.unshuffle() is False
    assert listener.call_count == 0

    ctrl.shuffle()
    assert ctrl.unshuffle() is True
    assert listener.call_count == 2


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c.remove_track(99),
        lambda c: c.reorder_tracks([0, 0, 0, 0]),
        lambda c: c.move_track(0, 99),
    ],
)
def test_rejected_mutation_does_not_notify(mutate):
    ctrl, listener = _controller()
    mutate(ctrl)
    assert listener.call_count == 0


def test_navigation_does_not_notify():
    ctrl, listener = _controller()
    ctrl.next_track()
    ctrl.previous_track()
    ctrl.peek_next_track()
    ctrl.get_queue()
    assert listener.call_count == 0


def test_listener_runs_outside_the_queue_lock():
    """LOCK: the gapless engine takes update_lock before the queue lock."""
    ctrl, _ = _controller()
    held = []

    def listener():
        # _lock is an RLock; _is_owned() reports whether this thread holds it.
        held.append(ctrl.queue._lock._is_owned())

    ctrl.set_change_listener(listener)
    ctrl.set_queue([_track(1), _track(2)])
    ctrl.add_track(_track(3))
    assert held == [False, False]


def test_listener_failure_does_not_break_the_edit():
    ctrl, _ = _controller()
    ctrl.set_change_listener(MagicMock(side_effect=RuntimeError("boom")))
    ctrl.add_track(_track(9))
    assert ctrl.get_queue_size() == 5


def test_audio_player_wires_the_gapless_engine():
    """WIRING: a direct QueueController edit drops AudioPlayer's prebuffer."""
    from auralis.player.config import PlayerConfig
    from auralis.player.enhanced_audio_player import AudioPlayer

    player = AudioPlayer(PlayerConfig(), get_repository_factory=lambda: MagicMock())
    try:
        player.queue.set_queue([_track(i) for i in range(3)])
        gapless = player.gapless
        with gapless.update_lock:
            gapless.next_track_buffer = np.zeros((16, 2), dtype=np.float32)
            gapless.next_track_info = _track(1)

        # What the backend's QueueService does: bypass AudioPlayer entirely.
        player.queue.move_track(1, 2)

        assert gapless.next_track_buffer is None
        assert gapless.next_track_info is None
    finally:
        player.cleanup()
