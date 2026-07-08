"""
PlaybackController - Manages playback state machine

Handles: play/pause/stop/seek operations and state transitions
Responsibilities:
- Playback state (PLAYING, PAUSED, STOPPED, ERROR)
- Position tracking during playback
- Callback notifications for state changes

Note: ``PlaybackState.LOADING`` is defined in the enum because the
WebSocket-facing backend (``auralis-web/backend/core/state_manager.py``)
publishes it during track-load, but the engine-level controller itself
deliberately never enters LOADING — ``load_and_stop`` skips it to keep
observers from seeing an intermediate state during ``previous_track`` /
queue-driven loads (see #3293, #3693).
"""

import threading
from contextlib import contextmanager
from enum import Enum
from typing import Any
from collections.abc import Callable, Iterator

from ..utils.logging import debug, info, warning


class PlaybackState(Enum):
    """Playback state enumeration"""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    LOADING = "loading"
    ERROR = "error"


class PlaybackController:
    """
    Manages playback state and position tracking.

    Decoupled from audio I/O, file loading, and queue management.
    Only responsible for state machine and playback timeline.

    All state access is protected by an RLock for thread safety.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.state = PlaybackState.STOPPED
        self.position = 0  # Position in samples
        self.callbacks: list[Callable[[dict[str, Any] | None], None]] = []
        # #3781: thread-local deferral state for defer_notifications(). Must be
        # thread-local (not an instance flag) — two threads can each be inside
        # their own defer_notifications() scope concurrently, and an instance
        # flag would let one thread's scope flush (or suppress) the other's
        # queued notifications.
        self._defer_state = threading.local()

    def add_callback(self, callback: Callable[[dict[str, Any] | None], None]) -> None:
        """Register a callback for state changes"""
        with self._lock:
            self.callbacks.append(callback)

    def _is_deferring(self) -> bool:
        return getattr(self._defer_state, "deferring", False)

    @contextmanager
    def defer_notifications(self) -> Iterator[None]:
        """Queue notify_callbacks() calls made inside this scope instead of
        firing them immediately; flush them in order once the scope exits.

        Fixes #3781: mutators (seek/play/stop/load_and_stop) snapshot state
        under `self._lock` then notify callbacks AFTER releasing it — but
        callers in enhanced_audio_player.py invoke those mutators while still
        holding the OUTER `AudioFileManager._audio_lock`. One registered
        callback (`IntegrationManager._on_playback_state_change`) acquires
        `_position_lock` then re-enters `_audio_lock` via
        `file_manager.get_duration()`. A concurrent `get_playback_info()` call
        acquires the same two locks in the OPPOSITE order
        (`_position_lock` -> `_audio_lock`), producing a classic AB-BA
        deadlock.

        Wrapping the `_audio_lock`-holding block in
        `with self.playback.defer_notifications(), self.file_manager._audio_lock:`
        (defer_notifications OUTER so it exits — and flushes — LAST, after
        `_audio_lock` has already been released) queues notifications raised
        during the block and fires them only once `_audio_lock` is free,
        closing the inversion without changing any mutator's call signature.

        Re-entrant: nested scopes on the same thread flush once, when the
        outermost scope exits.
        """
        already_deferring = self._is_deferring()
        if not already_deferring:
            self._defer_state.deferring = True
            self._defer_state.queue = []
        try:
            yield
        finally:
            # Flush inline within `finally` (never `return` here) so an
            # exception raised inside the `with` block still propagates
            # normally instead of being silently swallowed.
            pending: list[dict[str, Any]] | None = None
            if not already_deferring:
                # Outermost scope — pop the queue and stop deferring.
                pending = self._defer_state.queue
                self._defer_state.deferring = False
                self._defer_state.queue = []
            # Nested scope: leave deferring on, let the outer scope flush.
            if pending:
                for state_info in pending:
                    self._dispatch_callbacks(state_info)

    def _notify_callbacks(self, state_info: dict[str, Any]) -> None:
        """Notify all callbacks of state change, or queue if deferring (#3781).

        Takes a snapshot of the callback list under the lock, then invokes each
        callback outside the lock so that callbacks can themselves read or
        transition player state without deadlocking (issue #2291).  The snapshot
        pattern also prevents RuntimeError if add_callback() races with iteration
        (fixes #2308).
        """
        if self._is_deferring():
            self._defer_state.queue.append(state_info)
            return
        self._dispatch_callbacks(state_info)

    def _dispatch_callbacks(self, state_info: dict[str, Any]) -> None:
        """Actually invoke every registered callback with `state_info`."""
        with self._lock:
            callbacks = list(self.callbacks)
        for callback in callbacks:
            try:
                callback(state_info)
            except Exception as e:
                debug(f"Callback error: {e}")

    def play(self) -> bool:
        """
        Start playback.

        Returns:
            bool: True if state changed, False if already playing
        """
        with self._lock:
            if self.state == PlaybackState.PAUSED:
                self.state = PlaybackState.PLAYING
                info("Playback resumed")
            elif self.state == PlaybackState.STOPPED:
                self.state = PlaybackState.PLAYING
                info("Playback started")
            elif self.state == PlaybackState.ERROR:
                warning("play() rejected: player is in ERROR state — load a new file first")
                return False
            else:
                return False
            # Snapshot inside lock, notify outside (issue #2291)
            state_info = {"state": self.state.value, "action": "play"}

        self._notify_callbacks(state_info)
        return True

    def pause(self) -> bool:
        """
        Pause playback.

        Returns:
            bool: True if paused, False if not playing
        """
        with self._lock:
            if self.state == PlaybackState.PLAYING:
                self.state = PlaybackState.PAUSED
                info("Playback paused")
                # Snapshot inside lock, notify outside (issue #2291)
                state_info = {"state": self.state.value, "action": "pause"}
            else:
                return False

        self._notify_callbacks(state_info)
        return True

    def stop(self) -> bool:
        """
        Stop playback and reset position.

        Returns:
            bool: True if stopped, False if already stopped
        """
        with self._lock:
            if self.state in [PlaybackState.PLAYING, PlaybackState.PAUSED]:
                self.state = PlaybackState.STOPPED
                self.position = 0
                info("Playback stopped")
                # Snapshot inside lock, notify outside (issue #2291)
                state_info = {"state": self.state.value, "action": "stop"}
            else:
                return False

        self._notify_callbacks(state_info)
        return True

    def read_and_advance_position(self, advance_by: int) -> int:
        """Atomically read current position and advance by given amount.

        Prevents a concurrent seek() from being overwritten by a stale
        read-modify-write in the playback loop (#2153).

        Args:
            advance_by: Number of samples to advance

        Returns:
            int: The position before advancing (use as chunk read offset)
        """
        with self._lock:
            pos = self.position
            self.position += advance_by
            return pos

    def get_position_snapshot(self) -> int:
        """Return current position sample atomically (thread-safe)."""
        with self._lock:
            return self.position

    def seek(self, position_samples: int, max_samples: int) -> bool:
        """
        Seek to a position (in samples).

        Args:
            position_samples: Target position in samples
            max_samples: Maximum valid position (total track length)

        Returns:
            bool: True if seek succeeded
        """
        with self._lock:
            # Clamp to valid range
            position_samples = max(0, min(position_samples, max_samples))
            self.position = position_samples
            debug(f"Seeked to sample {position_samples}")
            # Snapshot inside lock, notify outside (issue #2291)
            state_info = {
                "state": self.state.value,
                "action": "seek",
                "position_samples": position_samples,
            }

        self._notify_callbacks(state_info)
        return True

    def load_and_stop(self) -> bool:
        """Atomically transition from current state through LOADING to STOPPED.

        Prevents concurrent observers from seeing the intermediate LOADING
        state, which caused previous_track() to skip resume (#3293).

        Returns:
            True if the transition succeeded, False if already stopped.
        """
        with self._lock:
            if self.state == PlaybackState.STOPPED:
                return False
            self.state = PlaybackState.STOPPED
            self.position = 0
            info("Playback stopped (atomic load)")
            state_info = {"state": self.state.value, "action": "stop"}

        self._notify_callbacks(state_info)
        return True

    def set_error(self) -> None:
        """Set state to ERROR"""
        with self._lock:
            if self.state == PlaybackState.ERROR:
                return  # Already in error — no-op
            self.state = PlaybackState.ERROR
            # Snapshot inside lock, notify outside (issue #2291)
            state_info = {"state": self.state.value, "action": "error"}
        self._notify_callbacks(state_info)

    def is_playing(self) -> bool:
        """Check if currently playing"""
        with self._lock:
            return self.state == PlaybackState.PLAYING

    def is_stopped(self) -> bool:
        """Check if stopped"""
        with self._lock:
            return self.state == PlaybackState.STOPPED

    def is_paused(self) -> bool:
        """Check if paused"""
        with self._lock:
            return self.state == PlaybackState.PAUSED

    def get_state_snapshot(self) -> tuple[str, bool]:
        """#3691: atomic read of (state.value, is_playing) under a single
        _lock acquisition. Previously callers read state.value as a raw
        attribute and is_playing() separately, allowing a state transition
        between the two reads to produce an inconsistent snapshot."""
        with self._lock:
            return self.state.value, self.state == PlaybackState.PLAYING
