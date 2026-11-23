"""QueueController's shuffle flag and queue order change under one lock hold (#6536).

shuffle() reordered the queue (one hold of QueueManager._lock) and then set
shuffle_enabled (a second hold). A clear() or set_queue() from another thread
landing in between left shuffle_enabled True over a cleared or restored queue.
The tests run that clear() from a second thread right after the reorder; with the
pair under one hold it waits (up to 0.3 s) and lands after the flag write instead.
"""

import threading

import pytest

from auralis.player.queue_controller import QueueController


def _controller():
    controller = QueueController(lambda: None)
    controller.set_queue([{"id": i, "filepath": f"/m/{i}.flac"} for i in range(8)], start_index=0)
    return controller


def _clear_from_another_thread(controller):
    clearer = threading.Thread(target=controller.queue.clear)
    clearer.start()
    clearer.join(0.3)  # blocks on the queue lock when the caller holds it
    return clearer


@pytest.mark.parametrize("enable", [lambda c: c.shuffle(), lambda c: c.set_shuffle(True)], ids=["shuffle", "set_shuffle"])
def test_a_clear_between_reorder_and_flag_leaves_shuffle_off(monkeypatch, enable):
    controller = _controller()
    real_shuffle = controller.queue.shuffle
    clearers = []

    def shuffle_then_race():
        real_shuffle()
        clearers.append(_clear_from_another_thread(controller))

    monkeypatch.setattr(controller.queue, "shuffle", shuffle_then_race)

    enable(controller)
    clearers[0].join(5)

    assert controller.get_queue() == []
    assert controller.shuffle_enabled is False, "shuffle_enabled left True over a cleared queue"

