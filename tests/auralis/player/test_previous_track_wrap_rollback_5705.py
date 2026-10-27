"""
Regression: a failed previous_track() after a wrap restores the queue (#5705)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``previous_track()`` rolled back with ``expected_current=saved_index - 1``,
which is only where a non-wrapping move lands. With repeat on at index 0 the
move lands on the last track, the compare-and-set failed and was ignored, and
the queue pointed at a track other than the loaded audio.
"""

from unittest.mock import MagicMock

from auralis.player.components.queue_manager import QueueManager
from auralis.player.queue_controller import QueueController
from auralis.player.player_queue_navigation_mixin import PlayerQueueNavigationMixin
import threading


def _player(current_index: int):
    controller = QueueController.__new__(QueueController)
    controller.queue = QueueManager()
    controller._notify_changed = MagicMock()
    for n, name in enumerate(("a", "missing1", "missing2")):
        controller.queue.add_track({"id": n, "title": name, "file_path": f"/{name}.wav"})
    controller.queue.repeat_enabled = True
    controller.queue.current_index = current_index

    class Player(PlayerQueueNavigationMixin):
        pass

    player = Player.__new__(Player)
    player.queue = controller
    player.playback = MagicMock()
    player.playback.is_playing.return_value = False
    player.load_file = MagicMock(return_value=False)
    player._stop_requested = threading.Event()
    player._pause_requested = threading.Event()
    return player


def test_failed_previous_from_the_first_track_with_repeat_keeps_the_first_track():
    player = _player(current_index=0)

    assert player.previous_track() is False

    assert player.queue.queue.current_index == 0
    assert player.queue.get_current_track()["title"] == "a"


def test_failed_previous_from_index_minus_one_with_repeat_keeps_it():
    player = _player(current_index=-1)

    assert player.previous_track() is False

    assert player.queue.queue.current_index == -1


def test_failed_previous_without_a_wrap_still_rolls_back():
    player = _player(current_index=2)

    assert player.previous_track() is False

    assert player.queue.queue.current_index == 2
