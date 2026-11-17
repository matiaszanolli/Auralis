"""
Playback state events carry a transition-ordered sequence number (#6129)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each mutator snapshots its event under ``_lock`` but dispatches after releasing it (#2291), so two
threads' events can reach a listener in either order: a listener mirroring the last callback can
end on ``play`` while the controller is paused. ``seq`` is assigned under the lock in transition
order, so a listener that keeps the highest ``seq`` it has seen ends on the true state.
"""

import threading

from auralis.player.playback_controller import PlaybackController, PlaybackState


def _recording_controller():
    controller = PlaybackController()
    events: list[dict] = []
    controller.add_callback(lambda info: events.append(dict(info)))
    return controller, events


def test_every_mutator_stamps_a_strictly_increasing_seq():
    controller, events = _recording_controller()

    controller.play()
    controller.seek(10, 100)
    controller.pause()
    controller.stop()
    controller.set_error()

    assert [e["action"] for e in events] == ["play", "seek", "pause", "stop", "error"]
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)


def test_a_rejected_transition_does_not_consume_a_seq():
    controller, events = _recording_controller()

    controller.play()
    assert controller.play() is False  # already playing: no event
    controller.pause()

    assert [e["seq"] for e in events] == [1, 2]


def test_a_listener_keeping_the_highest_seq_survives_reordered_dispatch():
    controller = PlaybackController()
    arrived: list[dict] = []
    release_first = threading.Event()
    first_in_callback = threading.Event()
    calls = []

    def callback(info):
        calls.append(info["action"])
        if info["action"] == "play":
            first_in_callback.set()
            assert release_first.wait(5)  # T1's dispatch is held up after it already transitioned
        arrived.append(dict(info))

    controller.add_callback(callback)

    t1 = threading.Thread(target=controller.play)  # transitions first -> seq 1
    t1.start()
    assert first_in_callback.wait(5)
    controller.pause()  # transitions second -> seq 2, and is DISPATCHED first
    release_first.set()
    t1.join(5)

    assert [e["action"] for e in arrived] == ["pause", "play"], "dispatch order was reversed"
    newest = max(arrived, key=lambda e: e["seq"])
    assert newest["action"] == "pause" and newest["state"] == controller.state.value == PlaybackState.PAUSED.value
