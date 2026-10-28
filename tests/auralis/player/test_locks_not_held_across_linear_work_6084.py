"""O(n) work runs before the locks the audio thread waits on (#6084)

``load_playlist`` serialised every row (``Track.to_dict``) inside ``queue._lock``, and
``RealtimeLevelMatcher.set_reference_audio`` measured the whole reference's RMS inside its
``_lock`` -- both stall ``has_next_track()`` / ``process()`` on the real-time path.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from auralis.player.config import PlayerConfig
from auralis.player.queue_controller import QueueController
from auralis.player.realtime.level_matcher import RealtimeLevelMatcher


def test_load_playlist_serialises_rows_outside_the_queue_lock():
    factory = MagicMock()
    ctrl = QueueController(get_repository_factory=lambda: factory)
    held_during_to_dict: list[bool] = []

    def to_dict() -> dict:
        held_during_to_dict.append(ctrl.queue._lock._is_owned())
        return {"id": len(held_during_to_dict), "filepath": f"/t{len(held_during_to_dict)}.wav"}

    playlist = MagicMock()
    playlist.name = "P"
    playlist.tracks = [MagicMock(to_dict=to_dict) for _ in range(3)]
    factory.playlists.get_by_id.return_value = playlist

    assert ctrl.load_playlist(1) is True

    assert held_during_to_dict == [False, False, False]
    assert ctrl.get_queue_size() == 3


class _LockProbe(np.ndarray):
    """Records whether the matcher's lock was held when the RMS is computed."""

    matcher: RealtimeLevelMatcher
    held: list[bool]

    def __pow__(self, power):  # noqa: ANN001
        self.held.append(self.matcher._lock.locked())
        return np.asarray(self).__pow__(power)


def test_reference_rms_is_measured_before_the_matcher_lock_is_taken():
    config = PlayerConfig()
    matcher = RealtimeLevelMatcher(config)
    reference = np.full((4096, 2), 0.1, dtype=np.float32).view(_LockProbe)
    reference.matcher = matcher
    reference.held = []

    assert matcher.set_reference_audio(reference) is True

    assert reference.held == [False]
    assert float(matcher.reference_rms) == pytest.approx(0.1, abs=1e-6)
    assert matcher.enabled is True
