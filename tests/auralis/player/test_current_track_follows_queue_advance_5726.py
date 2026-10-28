"""current_track describes the track the queue advanced to (#5726).

IntegrationManager.set_current_track ran only from load_track_from_library, so after next_track() /
previous_track() the dict behind every playback payload and the playback_finished event kept naming
the track loaded last.
"""

from unittest.mock import Mock

import numpy as np
import pytest
import soundfile as sf

from auralis.player.config import PlayerConfig
from auralis.player.enhanced_audio_player import AudioPlayer


def _wav(path):
    sf.write(str(path), np.zeros((11025, 2), dtype="float32"), 22050)
    return str(path)


class _Track:
    def __init__(self, track_id, title):
        self.id, self.title = track_id, title

    def to_dict(self):
        return {"id": self.id, "title": self.title}


@pytest.fixture
def player(tmp_path):
    player = AudioPlayer(config=PlayerConfig(), get_repository_factory=lambda: Mock())
    a, b = _wav(tmp_path / "a.wav"), _wav(tmp_path / "b.wav")
    player.queue.set_queue([
        {"id": 1, "title": "A", "filepath": a},
        {"id": 2, "title": "B", "filepath": b},
    ], 0)
    assert player.load_file(a)
    player.current_track = _Track(1, "A")
    return player


def _title(player):
    return player.integration._current_track_dict["title"]


def test_next_track_updates_the_current_track_dict(player):
    assert _title(player) == "A"

    assert player.next_track() is True

    assert _title(player) == "B"
    assert player.integration._current_track_dict["id"] == 2


def test_previous_track_updates_it_back(player):
    player.next_track()

    assert player.previous_track() is True

    assert _title(player) == "A"


def test_the_filesystem_path_is_not_exposed(player):
    player.next_track()

    snapshot = player.integration._current_track_dict
    assert "filepath" not in snapshot and "file_path" not in snapshot
