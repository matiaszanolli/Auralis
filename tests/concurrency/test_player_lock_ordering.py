# -*- coding: utf-8 -*-

"""
Tests for the AudioFileManager._audio_lock <-> IntegrationManager._position_lock
lock-ordering deadlock (fixes #3781).

seek(), load_file(), load_track_from_library(), next_track(), and the
`position` setter all hold `_audio_lock` while triggering a callback chain
(PlaybackController._notify_callbacks -> IntegrationManager._on_playback_state_change)
that acquires `_position_lock` and then re-enters `_audio_lock` via
`file_manager.get_duration()`. `get_playback_info()` acquires the same two
locks in the OPPOSITE order (`_position_lock` -> `_audio_lock`), so a
concurrent seek/load/skip + a WS-broadcaster poll could hard-deadlock.

The fix wraps every `_audio_lock`-holding block in
`PlaybackController.defer_notifications()` so callback notification is
queued and only fires after `_audio_lock` has been released.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import threading
import time
from unittest.mock import Mock

from auralis.player.config import PlayerConfig
from auralis.player.enhanced_audio_player import AudioPlayer


def _make_player() -> AudioPlayer:
    return AudioPlayer(
        config=PlayerConfig(),
        get_repository_factory=lambda: Mock(),
    )


# ---------------------------------------------------------------------------
# Deterministic proof: notify never fires while _audio_lock is held (#3781)
# ---------------------------------------------------------------------------
#
# RLock exposes `_is_owned()` (CPython, both C and Python fallback
# implementations) — True iff the CURRENT thread currently holds the lock.
# A probe callback recording this value at notify-time gives a deterministic
# assertion instead of a timing-dependent deadlock race.

class TestNotifyFiresAfterAudioLockReleased:
    def test_seek_notify_does_not_hold_audio_lock(self, test_audio_files):
        player = _make_player()
        assert player.load_file(test_audio_files[0])

        owned_at_notify: list[bool] = []
        player.playback.add_callback(
            lambda state_info: owned_at_notify.append(player.file_manager._audio_lock._is_owned())
        )

        assert player.seek(0.1)

        assert owned_at_notify, "seek() must fire at least one notification"
        assert not any(owned_at_notify), (
            "seek()'s notify callback fired while _audio_lock was still held "
            "by the calling thread — regression of #3781"
        )

    def test_load_file_notify_does_not_hold_audio_lock(self, test_audio_files):
        player = _make_player()
        assert player.load_file(test_audio_files[0])
        # load_and_stop() is a no-op (no notify) if already STOPPED — play()
        # first so the second load_file()'s load_and_stop() actually
        # transitions state and fires a notification.
        player.play()

        owned_at_notify: list[bool] = []
        player.playback.add_callback(
            lambda state_info: owned_at_notify.append(player.file_manager._audio_lock._is_owned())
        )

        assert player.load_file(test_audio_files[1])

        assert owned_at_notify, "load_file() must fire at least one notification"
        assert not any(owned_at_notify), (
            "load_file()'s notify callback fired while _audio_lock was still "
            "held by the calling thread — regression of #3781"
        )

    def test_next_track_notify_does_not_hold_audio_lock(self, test_audio_files):
        player = _make_player()
        assert player.load_file(test_audio_files[0])
        player.queue.add_track({'title': 'Next', 'file_path': test_audio_files[1]})

        owned_at_notify: list[bool] = []
        player.playback.add_callback(
            lambda state_info: owned_at_notify.append(player.file_manager._audio_lock._is_owned())
        )

        assert player.next_track()

        assert owned_at_notify, "next_track() must fire at least one notification"
        assert not any(owned_at_notify), (
            "next_track()'s notify callback fired while _audio_lock was "
            "still held by the calling thread — regression of #3781"
        )

    def test_position_setter_notify_does_not_hold_audio_lock(self, test_audio_files):
        player = _make_player()
        assert player.load_file(test_audio_files[0])

        owned_at_notify: list[bool] = []
        player.playback.add_callback(
            lambda state_info: owned_at_notify.append(player.file_manager._audio_lock._is_owned())
        )

        player.position = 1000

        assert owned_at_notify, "position setter must fire at least one notification"
        assert not any(owned_at_notify), (
            "position setter's notify callback fired while _audio_lock was "
            "still held by the calling thread — regression of #3781"
        )


# ---------------------------------------------------------------------------
# Live concurrency regression (issue Test Plan PTS-1.a/b/c)
# ---------------------------------------------------------------------------

def _run_concurrent(target_a, target_b, duration_seconds: float = 2.0) -> tuple[bool, bool, list[Exception]]:
    """Run two loop functions concurrently for `duration_seconds`, then join
    with a generous timeout. Returns (a_finished, b_finished, errors)."""
    stop = threading.Event()
    errors: list[Exception] = []

    def wrap(fn):
        def _inner():
            while not stop.is_set():
                try:
                    fn()
                except Exception as e:
                    errors.append(e)
        return _inner

    t_a = threading.Thread(target=wrap(target_a), daemon=True)
    t_b = threading.Thread(target=wrap(target_b), daemon=True)
    t_a.start()
    t_b.start()

    time.sleep(duration_seconds)
    stop.set()
    t_a.join(timeout=10.0)
    t_b.join(timeout=10.0)

    return (not t_a.is_alive(), not t_b.is_alive(), errors)


class TestConcurrentSeekAndGetPlaybackInfo:
    """PTS-1.a: seek() vs get_playback_info() must not deadlock."""

    def test_no_deadlock(self, test_audio_files):
        player = _make_player()
        assert player.load_file(test_audio_files[0])
        positions = [0.05 * i for i in range(20)]
        counter = {"i": 0}

        def seek_step():
            counter["i"] += 1
            player.seek(positions[counter["i"] % len(positions)])

        def info_step():
            player.get_playback_info()

        a_done, b_done, errors = _run_concurrent(seek_step, info_step)

        assert a_done, "seek() loop did not complete — deadlock (regression of #3781)"
        assert b_done, "get_playback_info() loop did not complete — deadlock (regression of #3781)"
        assert not errors, f"Unexpected errors: {errors}"


class TestConcurrentNextTrackAndGetPlaybackInfo:
    """PTS-1.b: next_track() vs get_playback_info() must not deadlock."""

    def test_no_deadlock(self, test_audio_files):
        player = _make_player()
        assert player.load_file(test_audio_files[0])
        for f in test_audio_files[1:]:
            player.queue.add_track({'title': 'T', 'file_path': f})
        player.queue.repeat_enabled = True  # keep the queue non-exhausting (wraps at the end)

        def next_step():
            player.next_track()

        def info_step():
            player.get_playback_info()

        a_done, b_done, errors = _run_concurrent(next_step, info_step)

        assert a_done, "next_track() loop did not complete — deadlock (regression of #3781)"
        assert b_done, "get_playback_info() loop did not complete — deadlock (regression of #3781)"
        assert not errors, f"Unexpected errors: {errors}"


class TestConcurrentLoadFileAndGetPlaybackInfo:
    """PTS-1.c: load_file() vs get_playback_info() must not deadlock."""

    def test_no_deadlock(self, test_audio_files):
        player = _make_player()
        assert player.load_file(test_audio_files[0])
        files = test_audio_files[:2]
        counter = {"i": 0}

        def load_step():
            counter["i"] += 1
            player.load_file(files[counter["i"] % len(files)])

        def info_step():
            player.get_playback_info()

        a_done, b_done, errors = _run_concurrent(load_step, info_step)

        assert a_done, "load_file() loop did not complete — deadlock (regression of #3781)"
        assert b_done, "get_playback_info() loop did not complete — deadlock (regression of #3781)"
        assert not errors, f"Unexpected errors: {errors}"
