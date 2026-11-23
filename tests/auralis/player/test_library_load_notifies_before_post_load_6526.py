"""A library load's stop event reaches observers before the post-load work (#6526).

AudioPlayer.load_track_from_library held playback.defer_notifications() open around the
whole integration call, so the `stop` queued by the swap hook was flushed only after the DB
read, the decode, record_play and the reference auto-selection (a second decode plus a
similarity search): seconds late, and after events other threads raised meanwhile. The scope
now encloses only the decode and swap, which is all the lock-held hook needs.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import soundfile as sf

from auralis.player.config import PlayerConfig
from auralis.player.enhanced_audio_player import AudioPlayer


def test_the_stop_event_precedes_record_play_and_reference_selection(tmp_path):
    path = tmp_path / "track.wav"
    sf.write(str(path), np.zeros((22050, 2), dtype="float32"), 22050)
    order: list[str] = []
    track = SimpleNamespace(id=7, title="T", filepath=str(path), recommended_reference=None,
                            to_dict=lambda: {"id": 7})
    repos = MagicMock()
    repos.tracks.get_by_id.return_value = track
    repos.tracks.record_play.side_effect = lambda _id: order.append("record_play")

    player = AudioPlayer(config=PlayerConfig(), get_repository_factory=lambda: repos)
    player.integration.auto_reference_selection = True
    player.integration._auto_select_reference = lambda _track: order.append("reference")
    assert player.load_file(str(path)) and player.play()  # playing, so the load has a stop to report
    player.playback.add_callback(lambda event: order.append(f"event:{event['action']}") if event else None)

    assert player.load_track_from_library(7) is True

    assert "event:stop" in order
    assert order.index("event:stop") < order.index("record_play") < order.index("reference")
