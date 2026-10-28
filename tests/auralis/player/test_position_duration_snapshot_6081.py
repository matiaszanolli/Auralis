"""Position, duration and file are read as one snapshot across a gapless swap (#6081)

``_on_playback_state_change`` / ``get_playback_info`` took position (clamped to the duration seen
at that instant), then the duration, then the file in separate acquisitions. A swap landing
between them reported the outgoing track's end position beside the shorter incoming duration
(``position > duration``). The three are now read under one ``_audio_lock`` hold, which is also
what the swap and its position reset run under.
"""

import threading

import numpy as np

from auralis.player.audio_file_manager import AudioFileManager
from auralis.player.integration_manager import IntegrationManager
from auralis.player.playback_controller import PlaybackController

SR = 1000


def _manager() -> tuple[IntegrationManager, AudioFileManager, PlaybackController]:
    fm = AudioFileManager({"sample_rate": SR})
    playback = PlaybackController()
    mgr = IntegrationManager.__new__(IntegrationManager)
    mgr.file_manager = fm
    mgr.playback = playback
    mgr._position_lock = threading.RLock()
    return mgr, fm, playback


def _install(fm: AudioFileManager, seconds: int, path: str) -> None:
    with fm._audio_lock:
        fm.audio_data = np.zeros((seconds * SR, 2), dtype=np.float32)
        fm.sample_rate = SR
        fm.current_file = path


def test_snapshot_never_pairs_the_old_end_position_with_the_new_duration():
    mgr, fm, playback = _manager()
    _install(fm, 100, "/long.wav")
    playback.position = 100 * SR - 1  # the very end of the outgoing track

    def swap_to_shorter() -> None:
        with fm._audio_lock:  # what advance_with_prebuffer + on_swap do, atomically
            fm.audio_data = np.zeros((10 * SR, 2), dtype=np.float32)
            fm.current_file = "/short.wav"
            playback.position = 0

    original_duration = fm.get_duration
    swapped = False

    def duration_after_a_racing_swap() -> float:
        nonlocal swapped
        if not swapped:  # a swap lands right after the position was read
            swapped = True
            worker = threading.Thread(target=swap_to_shorter)
            worker.start()
            worker.join(timeout=0.2)  # blocks on _audio_lock while the snapshot holds it
        return original_duration()

    fm.get_duration = duration_after_a_racing_swap  # type: ignore[method-assign]

    position, duration, current_file = mgr._track_position_snapshot()

    assert position <= duration
    assert (current_file, duration) in {("/long.wav", 100.0), ("/short.wav", 10.0)}
    assert (position, current_file) in {(99.999, "/long.wav"), (0.0, "/short.wav")}
