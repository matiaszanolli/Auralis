"""
Regression test: a lost commit race never leaves audio/queue de-synced (#4100, #4212, #5105)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Originally (#4100/#4212): advance_with_prebuffer()'s fallback path called
file_manager.load_file() — which atomically swaps audio_data/sample_rate/
current_file — and only then re-checked queue.advance_if_next_matches(). If a
concurrent mutation failed that re-check, the method returned False with
audio_data already on the new track while current_index still pointed at the old
one (the caller only resets position / reloads the fingerprint on True). The fix
added an explicit rollback of the swap.

#5105 reordered the method to load → commit → swap, so the audio is prepared in
a local buffer and `file_manager` is not touched until after the commit
succeeds. The de-sync is now impossible by construction and the explicit
rollback blocks were deleted. These tests therefore assert the same observable
invariant — a lost race leaves the previous track fully intact — but it now
holds because nothing was ever mutated, not because it was restored.

The load seam is `_load_track_audio()` rather than `file_manager.load_file()`:
that split is what keeps the blocking disk read off `_audio_lock`, so a test
mocking the old seam would silently exercise a path production no longer takes.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from unittest.mock import MagicMock

import numpy as np


def _prime_prebuffer(engine, next_track, sr):
    with engine.update_lock:
        engine.next_track_buffer = np.zeros(2048, dtype=np.float32)
        engine.next_track_info = dict(next_track)
        engine.next_track_sample_rate = sr


def _install_old_track(fm):
    old_audio = np.full(1000, 0.1, dtype=np.float32)
    with fm._audio_lock:
        fm.audio_data = old_audio
        fm.sample_rate = 44100
        fm.current_file = "/old.wav"
    return old_audio


def _fake_loader(new_audio, sr=48000):
    """Stand in for the real decode: returns a buffer, touches no player state."""
    return MagicMock(return_value=(new_audio, sr))


def test_fallback_double_mutation_restores_prior_track(gapless_playback_engine):
    """Both the prebuffer commit and the retry lose the race → previous track intact."""
    engine = gapless_playback_engine
    fm = engine.file_manager
    old_audio = _install_old_track(fm)

    next_track = {"id": 1, "file_path": "/next.wav"}
    fresh_next = {"id": 2, "file_path": "/fresh.wav"}
    # Prebuffer matches next_track AND its sample rate matches current playback,
    # so we reach the commit path.
    _prime_prebuffer(engine, next_track, sr=44100)

    engine.queue = MagicMock()
    # peek: first the prebuffered next_track, then the fresh next after mutation.
    engine.queue.peek_next_track.side_effect = [next_track, fresh_next]
    # Both advance attempts lose the race (first → retry, second → abort).
    engine.queue.advance_if_next_matches.return_value = False

    new_audio = np.full(3000, 0.9, dtype=np.float32)
    engine._load_track_audio = _fake_loader(new_audio)
    engine.start_prebuffering = MagicMock()  # should not be reached

    result = engine.advance_with_prebuffer(was_playing=True)

    assert result is False
    # Never mutated: audio_data still matches the un-advanced index.
    assert fm.audio_data is old_audio
    assert fm.sample_rate == 44100
    assert fm.current_file == "/old.wav"
    engine.start_prebuffering.assert_not_called()


def test_no_prebuffer_fallback_mutation_restores_prior_track(gapless_playback_engine):
    """#4212: the non-prebuffer path must be as safe as the prebuffer one.

    With no prebuffer primed, advance_with_prebuffer() decodes the next track
    directly then commits the advance. If the queue mutates and every commit
    fails, audio_data must still be on the old track.
    """
    engine = gapless_playback_engine
    fm = engine.file_manager
    old_audio = _install_old_track(fm)

    next_track = {"id": 1, "file_path": "/next.wav"}

    # No prebuffer primed → prebuffer_matches is False → the load path runs.
    engine.queue = MagicMock()
    engine.queue.peek_next_track.return_value = next_track
    engine.queue.advance_if_next_matches.return_value = False  # every commit loses

    new_audio = np.full(3000, 0.9, dtype=np.float32)
    engine._load_track_audio = _fake_loader(new_audio)
    engine.start_prebuffering = MagicMock()  # should not be reached

    result = engine.advance_with_prebuffer(was_playing=True)

    assert result is False
    assert fm.audio_data is old_audio
    assert fm.sample_rate == 44100
    assert fm.current_file == "/old.wav"
    engine.start_prebuffering.assert_not_called()


def test_fallback_success_keeps_new_track(gapless_playback_engine):
    """A lost prebuffer commit retries against the fresh queue and succeeds.

    This is the behaviour that makes a queue mutation during a transition follow
    the mutation rather than abandoning the advance.
    """
    engine = gapless_playback_engine
    fm = engine.file_manager
    _install_old_track(fm)

    next_track = {"id": 1, "file_path": "/next.wav"}
    fresh_next = {"id": 2, "file_path": "/fresh.wav"}
    _prime_prebuffer(engine, next_track, sr=44100)

    engine.queue = MagicMock()
    engine.queue.peek_next_track.side_effect = [next_track, fresh_next]
    # First commit fails (→ retry); second succeeds.
    engine.queue.advance_if_next_matches.side_effect = [False, True]

    new_audio = np.full(3000, 0.9, dtype=np.float32)
    engine._load_track_audio = _fake_loader(new_audio)
    engine.start_prebuffering = MagicMock()

    result = engine.advance_with_prebuffer(was_playing=True)

    assert result is True
    assert fm.audio_data is new_audio
    assert fm.current_file == "/fresh.wav"
    engine.start_prebuffering.assert_called_once()


def test_load_failure_leaves_previous_track_intact(gapless_playback_engine):
    """#2882: a failed decode must not advance the queue index."""
    engine = gapless_playback_engine
    fm = engine.file_manager
    old_audio = _install_old_track(fm)

    engine.queue = MagicMock()
    engine.queue.peek_next_track.return_value = {"id": 1, "file_path": "/next.wav"}
    engine._load_track_audio = MagicMock(return_value=(None, None))
    engine.start_prebuffering = MagicMock()

    result = engine.advance_with_prebuffer(was_playing=True)

    assert result is False
    engine.queue.advance_if_next_matches.assert_not_called()
    assert fm.audio_data is old_audio
    assert fm.current_file == "/old.wav"


def test_swap_and_on_swap_share_one_audio_lock_acquisition(gapless_playback_engine):
    """#3717/#5105: the position reset must be atomic with the swap.

    on_swap observes the NEW audio already installed and runs before the lock is
    released, so the audio callback can never see new audio at the old position.
    """
    engine = gapless_playback_engine
    fm = engine.file_manager
    _install_old_track(fm)

    engine.queue = MagicMock()
    engine.queue.peek_next_track.return_value = {"id": 1, "file_path": "/next.wav"}
    engine.queue.advance_if_next_matches.return_value = True

    new_audio = np.full(3000, 0.9, dtype=np.float32)
    engine._load_track_audio = _fake_loader(new_audio)
    engine.start_prebuffering = MagicMock()

    observed = {}

    def on_swap():
        observed["audio_is_new"] = fm.audio_data is new_audio
        observed["current_file"] = fm.current_file
        observed["sample_rate"] = fm.sample_rate

    assert engine.advance_with_prebuffer(was_playing=True, on_swap=on_swap) is True

    assert observed["audio_is_new"] is True, "on_swap ran before the swap"
    assert observed["current_file"] == "/next.wav"
    assert observed["sample_rate"] == 48000


def test_blocking_load_runs_without_audio_lock_held():
    """#5105: the decode must not hold _audio_lock — that was the dropout.

    Driven through AudioPlayer.next_track(), because that is where the bug
    lived: next_track() wrapped the whole advance in `_audio_lock`, so the
    fallback's blocking read ran inside the critical section and the real-time
    audio callback blocked for its full duration. Calling
    advance_with_prebuffer() directly would pass even against the old code.

    `_audio_lock` is an RLock, so a same-thread re-entry check would pass
    vacuously. Probe from another thread instead: if the decoding thread holds
    the lock, the probe cannot acquire it.
    """
    import threading
    from unittest.mock import patch

    from auralis.player.enhanced_audio_player import AudioPlayer

    # Real GaplessPlaybackEngine, PlaybackController and AudioFileManager;
    # everything else stubbed.
    with (
        patch("auralis.player.enhanced_audio_player.QueueController"),
        patch("auralis.player.enhanced_audio_player.IntegrationManager"),
        patch("auralis.player.enhanced_audio_player.FingerprintService"),
        patch("auralis.player.enhanced_audio_player.RealtimeProcessor"),
    ):
        player = AudioPlayer(get_repository_factory=MagicMock())

    fm = player.file_manager
    _install_old_track(fm)

    player.gapless.queue = MagicMock()
    player.gapless.queue.peek_next_track.return_value = {
        "id": 1, "file_path": "/next.wav"
    }
    player.gapless.queue.advance_if_next_matches.return_value = True
    player.gapless.start_prebuffering = MagicMock()

    acquired_during_load = threading.Event()
    probe_ran = threading.Event()

    def slow_load(path):
        def probe():
            probe_ran.set()
            if fm._audio_lock.acquire(timeout=2.0):
                acquired_during_load.set()
                fm._audio_lock.release()

        t = threading.Thread(target=probe)
        t.start()
        t.join(timeout=3.0)
        return np.full(3000, 0.9, dtype=np.float32), 48000

    player.gapless._load_track_audio = MagicMock(side_effect=slow_load)

    assert player.next_track() is True
    assert probe_ran.is_set(), "probe thread never ran — test is vacuous"
    assert acquired_during_load.is_set(), (
        "_audio_lock was held across the blocking decode — the real-time "
        "audio callback would have stalled for its full duration (#5105)"
    )
