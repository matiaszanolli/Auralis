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
from enum import Enum
from typing import Any
from collections.abc import Callable

from ..utils.logging import debug, info, warning
from .playback_notifier import PlaybackNotifierMixin


class PlaybackState(str, Enum):
    """Playback state enumeration.

    A ``str`` enum so the backend can serialise it directly: the WebSocket and
    REST payloads carry these values on the wire (the backend re-exports this
    class from ``player_state``).
    """
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    LOADING = "loading"
    ERROR = "error"


class PlaybackController(PlaybackNotifierMixin):
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
        # Stamped onto every state event under `_lock`, in transition order (#6129).
        self._event_seq = 0
        # #3781: thread-local deferral state for defer_notifications(). Must be
        # thread-local (not an instance flag) — two threads can each be inside
        # their own defer_notifications() scope concurrently, and an instance
        # flag would let one thread's scope flush (or suppress) the other's
        # queued notifications.
        self._defer_state = threading.local()

    def _event(self, action: str, **extra: Any) -> dict[str, Any]:
        """The state-change payload for the transition just made. Call with ``_lock`` held.

        Dispatch happens after the lock is released (#2291), so two threads' events can reach a
        listener in either order; ``seq`` is assigned under the lock, in transition order, so a
        listener that mirrors state keeps the highest ``seq`` it has seen and drops older ones
        instead of ending on a stale ``play`` while the state is paused (#6129).
        """
        self._event_seq += 1
        return {"state": self.state.value, "action": action, "seq": self._event_seq, **extra}

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
            state_info = self._event("play")

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
                state_info = self._event("pause")
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
                state_info = self._event("stop")
            else:
                return False

        self._notify_callbacks(state_info)
        return True

    def read_and_advance_position(self, advance_by: int, max_samples: int) -> int:
        """Atomically read current position and advance by given amount.

        Prevents a concurrent seek() from being overwritten by a stale
        read-modify-write in the playback loop (#2153).

        The stored position is clamped to max_samples (#5114) — the final
        chunk of a track otherwise advances position past total_samples and
        it sits there, violating the documented position <= duration
        invariant, until the async auto-advance's seek(0, ...) closes the
        window. Same max_samples-threading pattern seek() already uses.
        Only the stored position is clamped: the *returned* value is always
        the exact pre-advance position, unclamped, since callers use it as
        the chunk read offset (clamping it would silently truncate the last
        chunk's read length). End-of-track detection in the caller compares
        that returned pre-advance offset against total_samples directly, not
        the post-advance stored position, so this clamp cannot mask it.

        Args:
            advance_by: Number of samples to advance
            max_samples: Upper bound for the stored position (total track length)

        Returns:
            int: The position before advancing (use as chunk read offset)
        """
        with self._lock:
            pos = self.position
            self.position = min(pos + advance_by, max_samples)
            return pos

    def read_and_advance_if_playing(self, advance_by: int, max_samples: int) -> int | None:
        """``read_and_advance_position()`` only while PLAYING, else None.

        The state test and the advance share one ``_lock`` hold (RLock), so a
        stop() between them can no longer have its position reset overwritten
        by a stale advance and one extra chunk emitted after it (#6308).
        """
        with self._lock:
            if self.state != PlaybackState.PLAYING:
                return None
            return self.read_and_advance_position(advance_by, max_samples)

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
            state_info = self._event("seek", position_samples=position_samples)

        self._notify_callbacks(state_info)
        return True

    def load_and_stop(self) -> bool:
        """Atomically transition from current state through LOADING to STOPPED.

        Prevents concurrent observers from seeing the intermediate LOADING
        state, which caused previous_track() to skip resume (#3293). Position
        is reset even when the controller is already stopped because a stopped
        seek may have left it non-zero before the next track load (#4945).

        Returns:
            True if the transition succeeded, False if already stopped.
        """
        with self._lock:
            self.position = 0
            if self.state == PlaybackState.STOPPED:
                return False
            self.state = PlaybackState.STOPPED
            info("Playback stopped (atomic load)")
            state_info = self._event("stop")

        self._notify_callbacks(state_info)
        return True

    def set_error(self) -> None:
        """Set state to ERROR"""
        with self._lock:
            if self.state == PlaybackState.ERROR:
                return  # Already in error — no-op
            self.state = PlaybackState.ERROR
            # Snapshot inside lock, notify outside (issue #2291)
            state_info = self._event("error")
        self._notify_callbacks(state_info)

    def is_playing(self) -> bool:
        """Check if currently playing"""
        with self._lock:
            return self.state == PlaybackState.PLAYING

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
