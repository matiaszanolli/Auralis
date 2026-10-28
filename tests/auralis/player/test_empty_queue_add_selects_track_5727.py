"""The first track added to an empty queue becomes the current one (#5727).

add_to_queue() loaded the track but left current_index at -1, so get_current_track() was None and
peek_next() returned the same track again: it played twice.
"""

from unittest.mock import Mock

import numpy as np
import pytest
import soundfile as sf

from auralis.player.config import PlayerConfig
from auralis.player.enhanced_audio_player import AudioPlayer


@pytest.fixture
def player():
    return AudioPlayer(config=PlayerConfig(), get_repository_factory=lambda: Mock())


def _wav(path):
    sf.write(str(path), np.zeros((11025, 2), dtype="float32"), 22050)
    return str(path)


def test_first_add_to_an_empty_queue_is_current_and_not_its_own_next(player, tmp_path):
    entry = {"title": "A", "filepath": _wav(tmp_path / "a.wav")}

    player.add_to_queue(entry)

    assert player.queue.get_current_track() is entry
    assert player.queue.peek_next_track() is None  # nothing queued after it: it does not play twice
    assert player.queue.queue.current_index == 0


def test_a_second_add_does_not_move_the_current_track(player, tmp_path):
    first = {"title": "A", "filepath": _wav(tmp_path / "a.wav")}
    second = {"title": "B", "filepath": _wav(tmp_path / "b.wav")}

    player.add_to_queue(first)
    player.add_to_queue(second)

    assert player.queue.get_current_track() is first
    assert player.queue.peek_next_track() is second


def test_a_failed_load_leaves_nothing_selected(player, tmp_path):
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not audio" * 40)

    player.add_to_queue({"title": "X", "filepath": str(bad)})

    assert player.queue.get_current_track() is None
