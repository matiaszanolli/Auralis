"""
Playback reporting for IntegrationManager (split from integration_manager.py,
#5836): the comprehensive info snapshot, the session counters, and the
clamped position read.

Lock order is unchanged: ``_position_lock`` -> ``_audio_lock`` /
``PlaybackController._lock``, and ``_stats_lock`` is only taken after
``_position_lock`` is released.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
import time
from typing import Any
from collections.abc import Callable

from .audio_file_manager import AudioFileManager
from .playback_controller import PlaybackController
from .queue_controller import QueueController


class PlaybackReportingMixin:
    """Read-side views over the player; the state is created by IntegrationManager.__init__."""

    playback: PlaybackController
    file_manager: AudioFileManager
    queue: QueueController
    processor: Any
    auto_reference_selection: bool
    tracks_played: int
    total_play_time: float
    session_start_time: float
    _current_track_dict: dict[str, Any] | None
    _position_lock: "threading.RLock"
    _stats_lock: "threading.Lock"

    # Provided by IntegrationManager's own body (also annotated in
    # IntegrationLibraryMixin — one runtime definition, two typing sites).
    _notify_callbacks: "Callable[[dict[str, Any]], None]"

    def get_playback_info(self) -> dict[str, Any]:
        """Get comprehensive playback information"""
        queue_info = self.queue.get_queue_info()

        with self._position_lock:
            # #3691: take both state.value and is_playing in a single
            # PlaybackController._lock acquisition so a state transition
            # between the two reads can't produce an inconsistent snapshot
            # (e.g. state="paused" + is_playing=True).
            state_value, is_playing = self.playback.get_state_snapshot()
            # #3785: current_file is AudioFileManager state written under its
            # own _audio_lock — read it under _audio_lock rather than as a
            # raw attribute access (matches the _position_lock -> _audio_lock
            # order already used by _get_position_seconds() just above).
            with self.file_manager._audio_lock:
                current_file = self.file_manager.current_file
            playback_info = {
                'state': state_value,
                'position_seconds': self._get_position_seconds(),
                'duration_seconds': self.file_manager.get_duration(),
                'current_file': current_file,
                'is_playing': is_playing,
            }
            # #4102: read current_track inside the SAME _position_lock block
            # that took position/current_file, so the returned `playback` and
            # `library.current_track` always describe one track. The write side
            # is locked under _position_lock (#3786); reading it after the lock
            # released could pair the new track's position with the old track's
            # metadata for one WebSocket poll during a gapless/seek transition.
            # #4552: this is the dict materialised at assignment time, so the
            # invariant is kept without any ORM access inside the lock.
            current_track_snapshot = self._current_track_dict

        # #4552: read the session counters under _stats_lock, matching the
        # write side in record_track_completion (#2472). Unlocked, a poll could
        # observe a torn tracks_played / total_play_time pair mid-update.
        # Taken after _position_lock is released, so the two never nest.
        with self._stats_lock:
            session_info = {
                'tracks_played': self.tracks_played,
                'session_duration': time.time() - self.session_start_time,
                'total_play_time': self.total_play_time,
            }

        return {
            'playback': playback_info,
            'queue': queue_info,
            'library': {
                'current_track': current_track_snapshot,
                'auto_reference_selection': self.auto_reference_selection,
            },
            'processing': self.processor.get_processing_info(),
            'session': session_info,
        }

    def record_track_completion(self) -> None:
        """Record that current track completed (fixes #2472: atomic increment)."""
        with self._stats_lock:
            self.tracks_played += 1
            count = self.tracks_played
        self._notify_callbacks({
            'action': 'track_completed',
            'tracks_played': count
        })

    def _get_position_seconds(self) -> float:
        """Get current playback position in seconds (clamped to duration).

        Reads position via PlaybackController.get_position_snapshot() which
        holds PlaybackController._lock, then snapshots the file_manager's
        audio state atomically under its own _audio_lock. Pre-fix (#3474)
        the reader checked `audio_data is None` and then read `sample_rate`
        / `get_duration()` separately — a concurrent `clear_audio()` could
        slip between those reads, producing inconsistent state or
        ZeroDivisionError. The dedicated snapshot helper closes that window.

        _position_lock continues to guard the broader gapless-transition
        consistency (#2899, #3363); the new helper handles audio-state
        atomicity orthogonally so no lock-ordering concern arises.
        """
        with self._position_lock:
            is_loaded, sample_rate, duration, _total = self.file_manager.get_state_snapshot()
            if not is_loaded:
                return 0.0
            position_samples = self.playback.get_position_snapshot()
            position_seconds = position_samples / sample_rate
        return min(position_seconds, duration)
