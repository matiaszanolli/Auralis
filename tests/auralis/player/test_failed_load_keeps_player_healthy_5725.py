"""A failed load does not wedge a healthy player in ERROR (#5725).

AudioFileManager.load_file leaves the previous audio and position untouched when it fails, but
load_file() / load_track_from_library() called playback.set_error() on any failure. ERROR rejects
play() and stop(), so one bad file left the player unusable until another load succeeded. A player
with nothing loaded still goes to ERROR.
"""

from unittest.mock import Mock

import numpy as np
import pytest
import soundfile as sf

from auralis.player.config import PlayerConfig
from auralis.player.enhanced_audio_player import AudioPlayer
from auralis.player.playback_controller import PlaybackState


@pytest.fixture
def player():
    return AudioPlayer(config=PlayerConfig(), get_repository_factory=lambda: Mock())


@pytest.fixture
def good_file(tmp_path):
    path = tmp_path / "good.wav"
    sf.write(str(path), np.zeros((22050, 2), dtype="float32"), 22050)
    return str(path)


@pytest.fixture
def bad_file(tmp_path):
    path = tmp_path / "bad.wav"
    path.write_bytes(b"this is not audio" * 50)
    return str(path)


def test_failed_load_with_audio_already_loaded_keeps_the_player_usable(player, good_file, bad_file):
    assert player.load_file(good_file)
    assert player.playback.state != PlaybackState.ERROR

    assert player.load_file(bad_file) is False

    assert player.playback.state != PlaybackState.ERROR
    assert player.play() is True  # the previous track is still there to play


def test_failed_first_load_with_nothing_loaded_is_still_an_error(player, bad_file):
    assert player.load_file(bad_file) is False

    assert player.playback.state == PlaybackState.ERROR
