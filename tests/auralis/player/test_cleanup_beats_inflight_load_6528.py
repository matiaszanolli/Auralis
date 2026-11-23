"""A load still decoding when cleanup() runs cannot repopulate the player afterwards (#6528).

cleanup() polled its abort flag once and then cleared the audio, and AudioFileManager.load_file
had no check at all: a load from another thread (the backend's next/previous/play-track) that was
mid-decode installed its buffer after the clear, keeping a decoded track alive, and play() could
then reach PLAYING. The file manager now closes in one _audio_lock hold with the clear, every swap
checks that inside the same lock, and play() tests and transitions in one hold.
"""

import threading
from unittest.mock import Mock

import numpy as np
import soundfile as sf

from auralis.player import audio_file_manager
from auralis.player.config import PlayerConfig
from auralis.player.enhanced_audio_player import AudioPlayer
from auralis.player.playback_controller import PlaybackState


def test_a_load_finishing_after_cleanup_installs_nothing(tmp_path, monkeypatch):
    path = tmp_path / "t.wav"
    sf.write(str(path), np.zeros((22050, 2), dtype="float32"), 22050)
    player = AudioPlayer(config=PlayerConfig(), get_repository_factory=lambda: Mock())
    decoding, release = threading.Event(), threading.Event()
    real_load = audio_file_manager.load

    def slow_load(file_path, kind):
        decoding.set()
        release.wait(5)
        return real_load(file_path, kind)

    monkeypatch.setattr(audio_file_manager, "load", slow_load)
    results = []
    loader = threading.Thread(target=lambda: results.append(player.load_file(str(path))))
    loader.start()
    assert decoding.wait(5)

    player.cleanup()
    release.set()
    loader.join(10)

    assert results == [False]
    assert player.file_manager.is_loaded() is False
    assert player.play() is False
    assert player.playback.state != PlaybackState.PLAYING


def test_a_closed_file_manager_refuses_even_a_direct_load(tmp_path):
    path = tmp_path / "t.wav"
    sf.write(str(path), np.zeros((22050, 2), dtype="float32"), 22050)
    manager = audio_file_manager.AudioFileManager()

    manager.close()

    assert manager.load_file(str(path)) is False
    assert manager.is_loaded() is False
