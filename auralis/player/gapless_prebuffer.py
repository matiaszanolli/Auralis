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
from collections.abc import Callable

import numpy as np

from ..utils.logging import debug, info, warning
from .queue_controller import QueueController
from .queue_entry import entry_path


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
    _rearm_requested: bool = False  # guarded by _thread_lock (#6083)
    _prebuffer_exiting: bool = False

    # Provided by GaplessPlaybackEngine (io.loader.load).
    _load_audio: "Callable[[str], tuple[np.ndarray, int]]"

    def start_prebuffering(self) -> None:
        """
        Start background prebuffering of next track.

        Safe to call concurrently; one thread runs at a time. No-op after cleanup().
        """
        # Cheap fast path only — the authoritative shutdown check is inside the
        # lock below. Passing here proves nothing: cleanup() can set _shutdown
        # between this line and the acquire (#4631).
        if not self.prebuffer_enabled or self._shutdown.is_set():
            return

        with self._thread_lock:
            # #4631: re-check _shutdown inside the lock: cleanup() snapshots
            # prebuffer_thread under it, so no thread may be created after that.
            if self._shutdown.is_set():
                debug("Prebuffering not started: engine is shutting down")
                return

            # Double-check inside the lock to close the TOCTOU window (#2075). A worker
            # that has already decided to exit does not count as running (#6083); one
            # that has not is asked for another pass before it goes.
            if (self.prebuffer_thread and self.prebuffer_thread.is_alive()
                    and not self._prebuffer_exiting):
                self._rearm_requested = True
                debug("Prebuffer thread already running")
                return
            self._prebuffer_exiting = False

            # Non-daemon: won't be killed mid-I/O on shutdown (#2075)
            self.prebuffer_thread = threading.Thread(
                target=self._prebuffer_worker,
                daemon=False,
                name="GaplessPlayback-Prebuffer"
            )
            self.prebuffer_thread.start()
        debug("Started prebuffer thread")

    def _prebuffer_worker(self) -> None:
        """Run prebuffer passes until no re-arm was requested while one was in flight (#6083).

        A queue edit landing after a pass's final re-peek calls ``start_prebuffering()``
        while this thread is still alive; without the flag that request was dropped and the
        stale buffer stored. The exit decision and the flag share ``_thread_lock``.
        """
        while True:
            self._prebuffer_pass()
            with self._thread_lock:
                if self._rearm_requested and not self._shutdown.is_set():
                    self._rearm_requested = False
                    continue
                self._prebuffer_exiting = True
                return

    def _prebuffer_pass(self) -> None:
        """One pass: load the queue's next track, checking _shutdown before each blocking step (#2075)."""
        if self._shutdown.is_set():
            return

        try:
            # #5583: loop so a queue edit during the blocking load re-peeks and
            # loads the fresh next track instead of storing a stale one.
            while not self._shutdown.is_set():
                next_track = self.queue.peek_next_track()
                if not next_track:
                    info("No next track to prebuffer")
                    return

                file_path = entry_path(next_track)
                if not file_path:
                    warning("Next track has no file path")
                    return

                with self.update_lock:
                    if self._prebuffer_matches(next_track):
                        return  # a re-arm pass with nothing left to do

                # Check before the potentially long blocking load (#2075)
                if self._shutdown.is_set():
                    return

                info(f"Prebuffering next track: {file_path}")

                # Blocking load in an inner daemon thread so cleanup() can preempt it
                # on a stalled filesystem (#2456); this thread polls _shutdown every
                # 200 ms and abandons the loader if it is set.
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

                # #5583: re-peek before storing; a queue edit during the decode would
                # leave a buffer advance_with_prebuffer discards (#2303) -- loop instead.
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
        """(audio_data, sample_rate) of the prebuffered track, or (None, None) if not ready."""
        with self.update_lock:
            if (self.next_track_buffer is not None and
                    self.next_track_info is not None):
                audio = self.next_track_buffer
                sr = self.next_track_sample_rate
                return audio, sr
        return None, None

    def invalidate_prebuffer(self) -> None:
        """Invalidate the prebuffered track (the queue changed unexpectedly)."""
        with self.update_lock:
            self.next_track_buffer = None
            self.next_track_info = None
            self.next_track_sample_rate = None
        info("Prebuffer invalidated")

    @staticmethod
    def _entries_match(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
        """Same queue entry: equal id, or equal file path when both carry one (#2303's
        contract, shared by advance_with_prebuffer and the #5583 re-peek check). Two
        entries with neither must not match on ``None == None``."""
        if a is None or b is None:
            return False
        a_id = a.get('id')
        if a_id is not None and a_id == b.get('id'):
            return True
        a_path = entry_path(a)
        return a_path is not None and a_path == entry_path(b)

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

        #5583: keep the buffer when the peek still matches it, otherwise
        invalidate and re-arm (a bare invalidate also dropped buffers for
        appends and never re-armed). With a live worker the re-arm becomes a
        flagged extra pass (#6083); the worker re-peeks before storing.
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
