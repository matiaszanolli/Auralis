"""
Callback registration and deferred dispatch for PlaybackController (split out of
playback_controller.py, #6273).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from ..utils.logging import debug
from .lock_held_hooks import LockHeldNotificationError, active_lock_held_hook


class PlaybackNotifierMixin:
    """State is created by PlaybackController.__init__."""

    _lock: "threading.RLock"
    callbacks: list[Callable[[dict[str, Any] | None], None]]
    _defer_state: threading.local

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
        hook = active_lock_held_hook()
        if hook is not None:
            # Dispatching here, under _audio_lock, is the AB-BA deadlock defer_notifications()
            # exists to prevent (#3781); fail the call rather than hang the player (#6085).
            raise LockHeldNotificationError(
                f"playback notification fired inside the lock-held {hook} hook; open "
                f"playback.defer_notifications() around the call, outside _audio_lock"
            )
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
