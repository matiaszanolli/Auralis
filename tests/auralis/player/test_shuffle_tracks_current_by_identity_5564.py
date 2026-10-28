"""Shuffle / unshuffle keep the playing track by identity, not by 'id' (#5564).

Queue entries from QueueController.set_queue are {'filepath': ...} with no 'id', so the old id lookup
never matched: after a shuffle current_index pointed at whatever track landed on the old slot, and
unshuffle could not put the index back on the playing track.
"""

import random

from auralis.player.queue_controller import QueueController


def _controller(count=12, current=5):
    controller = QueueController(lambda: None)
    controller.set_queue([f"/m/{i}.flac" for i in range(count)], current)
    return controller


def test_shuffle_keeps_the_playing_idless_track_current_and_first():
    for seed in range(20):
        random.seed(seed)
        controller = _controller()
        playing = controller.get_current_track()["filepath"]

        controller.shuffle()

        assert controller.queue.current_index == 0
        assert controller.get_current_track()["filepath"] == playing


def test_unshuffle_restores_the_order_and_keeps_the_same_track_current():
    random.seed(3)
    controller = _controller()
    original = [t["filepath"] for t in controller.get_queue()]
    playing = controller.get_current_track()["filepath"]
    controller.shuffle()

    assert controller.unshuffle() is True

    assert [t["filepath"] for t in controller.get_queue()] == original
    assert controller.get_current_track()["filepath"] == playing
    assert controller.queue.current_index == original.index(playing)


def test_duplicate_ids_do_not_pick_the_wrong_entry():
    controller = QueueController(lambda: None)
    controller.set_queue([{"id": 1, "filepath": "/m/a.flac"}, {"id": 1, "filepath": "/m/b.flac"}, {"id": 2, "filepath": "/m/c.flac"}], 1)
    for seed in range(20):
        random.seed(seed)
        controller.queue.current_index = controller.queue.tracks.index(
            next(t for t in controller.queue.tracks if t["filepath"] == "/m/b.flac")
        )
        controller.shuffle()
        assert controller.get_current_track()["filepath"] == "/m/b.flac"
        controller.unshuffle()
