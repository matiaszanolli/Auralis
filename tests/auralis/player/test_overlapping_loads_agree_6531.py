"""Overlapping track loads leave the audio and current_track naming the same track (#6531).

load_track_from_library swaps the audio under _audio_lock and writes current_track afterwards
under _position_lock. Two overlapping loads could interleave as A.swap, B.swap, B.current_track,
A.current_track: the audio of B with the current_track of A. Track-changing methods now run under
one engine-level lock (the engine half of #6082). The test widens that window: load A pauses
between its swap and its current_track write while load B is started.
"""

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import soundfile as sf

from auralis.player.config import PlayerConfig
from auralis.player.enhanced_audio_player import AudioPlayer


def test_a_load_overlapping_another_cannot_split_audio_from_current_track(tmp_path, monkeypatch):
    tracks = {}
    for track_id, name in ((1, "a"), (2, "b")):
        path = tmp_path / f"{name}.wav"
        sf.write(str(path), np.zeros((22050, 2), dtype="float32"), 22050)
        tracks[track_id] = SimpleNamespace(id=track_id, title=name, filepath=str(path),
                                           recommended_reference=None, to_dict=lambda: {})
    repos = MagicMock()
    repos.tracks.get_by_id.side_effect = tracks.get
    player = AudioPlayer(config=PlayerConfig(), get_repository_factory=lambda: repos)
    player.integration.auto_reference_selection = False

    a_swapped, b_done = threading.Event(), threading.Event()
    real_set_current_track = player.integration.set_current_track

    def set_current_track(track):
        if track is tracks[1]:
            a_swapped.set()
            b_done.wait(0.5)  # B runs here unless it waits for A to finish
        real_set_current_track(track)

    monkeypatch.setattr(player.integration, "set_current_track", set_current_track)

    first = threading.Thread(target=player.load_track_from_library, args=(1,))
    first.start()
    assert a_swapped.wait(5)
    second = threading.Thread(target=lambda: (player.load_track_from_library(2), b_done.set()))
    second.start()
    first.join(10)
    second.join(10)

    current = player.integration._current_track
    assert current is not None
    assert player.file_manager.current_file == current.filepath, "audio and current_track describe different tracks"
