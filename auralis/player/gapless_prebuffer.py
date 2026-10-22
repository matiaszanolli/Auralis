"""
Prebuffer lifecycle for GaplessPlaybackEngine (split from
gapless_playback_engine.py, #5836): the background worker, the stored buffer's
accessors and validity rules, and the queue-change listener.

Lock order (unchanged): ``update_lock`` is always the outer lock, and
``_thread_lock`` is never held while waiting on ``update_lock`` or joining.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from typing import Any

import numpy as np

from ..utils.logging import debug, info, warning
from .queue_controller import QueueController


class PrebufferMixin:
    """Next-track prebuffering; the state is created by ``GaplessPlaybackEngine.__init__``."""

    queue: QueueController
    prebuffer_enabled: bool
    next_track_buffer: np.ndarray | None
    next_track_info: dict[str, Any] | None
    next_track_sample_rate: int | None
    prebuffer_thread: threading.Thread | None
    update_lock: "threading.RLock"
    _thread_lock: "threading.Lock"
    _shutdown: threading.Event

    def _load_audio(self, file_path: str) -> tuple[np.ndarray, int]:
        raise NotImplementedError

    def start_prebuffering(self) -> None:
        """
        Start background prebuffering of next track.

        Safe to call multiple times or concurrently—only one thread runs at a time.
        No-op after cleanup() has been called.
        """
        # Cheap fast path only — the authoritative shutdown check is inside the
        # lock below. Passing here proves nothing: cleanup() can set _shutdown
        # between this line and the acquire (#4631).
        if not self.prebuffer_enabled or self._shutdown.is_set():
            return

        with self._thread_lock:
            # #4631: re-check _shutdown *inside* the lock. cleanup() sets the
            # event and then snapshots prebuffer_thread under this same lock, so
            # once it has done so no new thread can be created here — without
            # this check a caller that passed the fast path above could start a
            # non-daemon thread after cleanup() already joined the old one,
            # leaving it unjoined and outliving cleanup.
            if self._shutdown.is_set():
                debug("Prebuffering not started: engine is shutting down")
                return

            # Double-check inside the lock to close the TOCTOU window (#2075)
            if self.prebuffer_thread and self.prebuffer_thread.is_alive():
                debug("Prebuffer thread already running")
                return

            # Non-daemon: won't be killed mid-I/O on shutdown (#2075)
            self.prebuffer_thread = threading.Thread(
                target=self._prebuffer_worker,
                daemon=False,
                name="GaplessPlayback-Prebuffer"
            )
            self.prebuffer_thread.start()
        debug("Started prebuffer thread")

    def _prebuffer_worker(self) -> None:
        """
        Background worker thread for prebuffering.

        Loads next track from queue without blocking playback.
        Checks _shutdown before each blocking operation so cleanup() can
        stop the thread at the next safe point (#2075).
        """
        if self._shutdown.is_set():
            return

        try:
            # #5583: loop so a queue edit during the blocking load re-peeks
            # and loads the fresh next track instead of storing (and then
            # being discarded for) a stale one. Each iteration re-checks
            # _shutdown before its blocking work.
            while not self._shutdown.is_set():
                # Get next track from queue (without advancing)
                next_track = self.queue.peek_next_track()
                if not next_track:
                    info("No next track to prebuffer")
                    return

                file_path = next_track.get('file_path') or next_track.get('path')
                if not file_path:
                    warning("Next track has no file path")
                    return

                # Check before the potentially long blocking load (#2075)
                if self._shutdown.is_set():
                    return

                info(f"Prebuffering next track: {file_path}")

                # Run the blocking load in an inner daemon thread so cleanup() can
                # preempt it at shutdown without the process hanging indefinitely
                # on a slow/stalled filesystem (#2456).  The outer (non-daemon) thread
                # polls _shutdown every 200 ms; the inner daemon thread is abandoned
                # (and dies with the process) if we exit early.
                _load_result: list[tuple[np.ndarray, int]] = []
                _load_exc: list[BaseException] = []

                def _do_load() -> None:
                    try:
                        _load_result.append(self._load_audio(file_path))
                    except Exception as exc:  # noqa: BLE001
                        _load_exc.append(exc)

                _loader = threading.Thread(
                    target=_do_load,
                    daemon=True,
                    name="GaplessPlayback-Prebuffer-IO",
                )
                _loader.start()
                while _loader.is_alive():
                    if self._shutdown.is_set():
                        return  # abandon; inner daemon thread dies with the process
                    _loader.join(timeout=0.2)

                if _load_exc:
                    raise _load_exc[0]

                audio_data, sample_rate = _load_result[0]

                # Check again: don't store results if shutdown was requested during load
                if self._shutdown.is_set():
                    return

                # #5583: re-peek before storing. The peek that started this load
                # happened before it; a queue edit during the blocking decode may
                # have changed the next track. Storing the stale result would
                # leave a buffer advance_with_prebuffer would discard anyway
                # (#2303 match rule) while the real next track never got
                # buffered — loop to re-peek and load the fresh one.
                latest = self.queue.peek_next_track()
                if not self._entries_match(latest, next_track):
                    debug("Queue changed during prebuffer load; re-peeking")
                    continue
                with self.update_lock:
                    self.next_track_buffer = audio_data
                    self.next_track_info = latest
                    self.next_track_sample_rate = sample_rate

                info(f"Prebuffered: {file_path} ({len(audio_data) / sample_rate:.1f}s)")
                return

        except Exception as e:
            warning(f"Prebuffering failed: {e}")
            with self.update_lock:
                self.next_track_buffer = None
                self.next_track_info = None
                self.next_track_sample_rate = None

    def has_prebuffered_track(self) -> bool:
        """Check if next track is prebuffered and ready"""
        with self.update_lock:
            return (self.next_track_buffer is not None and
                    self.next_track_info is not None)

    def get_prebuffered_track(self) -> tuple[np.ndarray | None, int | None]:
        """
        Get prebuffered track data if available.

        Returns:
            (audio_data, sample_rate) or (None, None) if not ready
        """
        with self.update_lock:
            if (self.next_track_buffer is not None and
                    self.next_track_info is not None):
                audio = self.next_track_buffer
                sr = self.next_track_sample_rate
                return audio, sr
        return None, None

    def invalidate_prebuffer(self) -> None:
        """
        Invalidate prebuffered track.

        Call when queue changes unexpectedly.
        """
        with self.update_lock:
            self.next_track_buffer = None
            self.next_track_info = None
            self.next_track_sample_rate = None
        info("Prebuffer invalidated")

    @staticmethod
    def _entries_match(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
        """Same queue entry: equal id, or equal file path when both carry one
        (#2303's contract, shared by advance_with_prebuffer and the #5583
        re-peek check). The path branch requires a non-None path on both
        sides — two entries that carry neither key must not match on
        ``None == None``."""
        if a is None or b is None:
            return False
        a_id = a.get('id')
        if a_id is not None and a_id == b.get('id'):
            return True
        a_path = a.get('file_path') or a.get('path')
        b_path = b.get('file_path') or b.get('path')
        return a_path is not None and a_path == b_path

    def _prebuffer_matches(self, expected_next: dict[str, Any] | None) -> bool:
        """Whether the stored prebuffer is still valid for *expected_next*.

        Callers must hold ``update_lock`` — the method reads the stored
        next_track_* fields.
        """
        if self.next_track_buffer is None:
            return False
        return self._entries_match(self.next_track_info, expected_next)

    def on_queue_changed(self) -> None:
        """Queue-change listener (the #5508 slot).

        #5583: the previous listener was ``invalidate_prebuffer`` bare —
        every edit cleared the buffer, including appends that leave the next
        track untouched, and nothing re-armed it, so the next transition
        always took the blocking-decode fallback. Re-validate instead: keep
        the buffer when the peek still matches it, otherwise invalidate and
        re-arm. A live worker makes ``start_prebuffering()`` a no-op; the
        worker re-peeks before storing (#5583) so the fresh next track is
        what ends up buffered.
        """
        next_track = self.queue.peek_next_track()
        with self.update_lock:
            if self._prebuffer_matches(next_track):
                debug("Queue changed; prebuffered next track still matches — keeping it")
                return
            self.next_track_buffer = None
            self.next_track_info = None
            self.next_track_sample_rate = None
        # Outside update_lock: start_prebuffering takes its own thread lock.
        self.start_prebuffering()
