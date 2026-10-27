"""
Regression: no fingerprint-loader thread without auto-mastering (#5708)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The shipped backend builds the player with ``enable_auto_mastering=False``, so
``RealtimeProcessor.auto_master`` is None and ``set_fingerprint()`` returns
immediately -- yet every ``load_file`` spawned a ``fingerprint-loader`` thread
that ran ``get_or_compute()`` (a cache miss decodes the file again and runs the
25D analysis), duplicating the backend's own fingerprint queue.
"""

import threading
from unittest.mock import MagicMock

from auralis.player.fingerprint_loader_mixin import PlayerFingerprintLoaderMixin


class _Player(PlayerFingerprintLoaderMixin):
    def __init__(self, auto_master):
        self.fingerprint_service = MagicMock()
        self.fingerprint_service.get_or_compute.return_value = {"lufs": -14.0, "crest_db": 12.0}
        self.processor = MagicMock()
        self.processor.auto_master = auto_master
        self._current_fingerprint = None
        self._fingerprint_lock = threading.Lock()
        self._track_generation = 0


def _join_loaders() -> None:
    for thread in threading.enumerate():
        if thread.name == "fingerprint-loader":
            thread.join(timeout=5)


def _loader_threads() -> list[threading.Thread]:
    return [t for t in threading.enumerate() if t.name == "fingerprint-loader"]


def test_no_thread_and_no_analysis_without_auto_mastering():
    player = _Player(auto_master=None)

    for n in range(5):
        player._schedule_fingerprint_load(f"/tmp/track_{n}.wav")

    assert _loader_threads() == []
    player.fingerprint_service.get_or_compute.assert_not_called()


def test_the_generation_still_advances_so_stale_loads_stay_invalidated():
    player = _Player(auto_master=None)

    player._schedule_fingerprint_load("/tmp/a.wav")
    player._schedule_fingerprint_load("/tmp/b.wav")

    assert player._track_generation == 2


def test_with_auto_mastering_the_fingerprint_is_still_loaded_and_applied():
    player = _Player(auto_master=MagicMock())

    player._schedule_fingerprint_load("/tmp/a.wav")
    _join_loaders()

    player.fingerprint_service.get_or_compute.assert_called_once()
    player.processor.set_fingerprint.assert_called_once_with({"lufs": -14.0, "crest_db": 12.0})
