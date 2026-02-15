"""
PlaybackController - Manages playback state machine

Handles: play/pause/stop/seek operations and state transitions
Responsibilities:
- Playback state (PLAYING, PAUSED, STOPPED, LOADING, ERROR)
- Position tracking during playback
- Callback notifications for state changes
"""

import threading
from enum import Enum
from typing import Any
from collections.abc import Callable

from ..utils.logging import debug, info


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

    def add_callback(self, callback: Callable[[dict[str, Any] | None], None]) -> None:
        """Register a callback for state changes"""
        self.callbacks.append(callback)

    def _notify_callbacks(self, state_info: dict[str, Any] | None = None) -> None:
        """Notify all callbacks of state change"""
        for callback in self.callbacks:
            try:
                callback(state_info or {"state": self.state.value})
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
            else:
                return False

            self._notify_callbacks({"state": self.state.value, "action": "play"})
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
                self._notify_callbacks({"state": self.state.value, "action": "pause"})
                return True
            return False

    def stop(self) -> bool:
        """
        Stop playback and reset position.

        Returns:
            bool: True if stopped, False if already stopped
        """
        with self._lock:
            if self.state in [PlaybackState.PLAYING, PlaybackState.PAUSED,
                              PlaybackState.LOADING]:
                self.state = PlaybackState.STOPPED
                self.position = 0
                info("Playback stopped")
                self._notify_callbacks({"state": self.state.value, "action": "stop"})
                return True
            return False

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
            self._notify_callbacks({
                "state": self.state.value,
                "action": "seek",
                "position_samples": position_samples
            })
            return True

    def set_loading(self) -> None:
        """Set state to LOADING"""
        with self._lock:
            self.state = PlaybackState.LOADING
            self._notify_callbacks({"state": self.state.value, "action": "loading"})

    def set_error(self) -> None:
        """Set state to ERROR"""
        with self._lock:
            self.state = PlaybackState.ERROR
            self._notify_callbacks({"state": self.state.value, "action": "error"})

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
