"""
GaplessPlaybackEngine - Handles prebuffering and seamless track transitions

Responsibilities:
- Background prebuffering of next track
- Seamless track transitions (gapless playback)
- Thread management for prebuffering
- Buffer validation and synchronization
"""

import threading
from pathlib import Path
from typing import Any
from collections.abc import Callable

import numpy as np

from ..io.loader import load
from ..utils.logging import debug, error, info, warning
from .audio_file_manager import AudioFileManager
from .queue_controller import QueueController


class GaplessPlaybackEngine:
    """
    Manages prebuffering and gapless playback transitions.

    Decoupled from playback state and queue management.
    Handles threading and buffer management for seamless transitions.
    """

    def __init__(
        self,
        file_manager: AudioFileManager,
        queue_controller: QueueController,
        prebuffer_enabled: bool = True
    ) -> None:
        self.file_manager = file_manager
        self.queue = queue_controller
        self.prebuffer_enabled = prebuffer_enabled

        # Prebuffer state
        self.next_track_buffer: np.ndarray | None = None
        self.next_track_info: dict[str, Any] | None = None
        self.next_track_sample_rate: int | None = None
        self.prebuffer_thread: threading.Thread | None = None

        # Threading
        # RLock, not Lock (#3782): advance_with_prebuffer() is only ever
        # called by enhanced_audio_player.next_track() while it already
        # holds AudioFileManager._audio_lock, and advance_with_prebuffer()
        # itself nests file_manager._audio_lock inside update_lock (to swap
        # audio_data atomically with get_audio_chunk() readers, #2423). The
        # resulting geometry is `_audio_lock -> update_lock -> _audio_lock`
        # (reentrant). That inner reentry only works today because
        # _audio_lock is itself an RLock; making update_lock reentrant too
        # removes the second half of that fragility so this nesting stays
        # safe even if a future change touches either lock's acquisition
        # order. Ordering invariant: _audio_lock is always the outer lock —
        # never acquire update_lock first and then _audio_lock.
        self.update_lock = threading.RLock()
        self._thread_lock = threading.Lock()   # guards thread creation (#2075)
        self._shutdown = threading.Event()     # signals worker to exit cleanly (#2075)
        self.prebuffer_callbacks: list[Callable[[dict[str, Any]], None]] = []

    def add_prebuffer_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register callback when prebuffering completes"""
        with self.update_lock:
            self.prebuffer_callbacks.append(callback)

    def _notify_prebuffer_callbacks(self, track_info: dict[str, Any]) -> None:
        """Notify callbacks that prebuffering completed"""
        # Snapshot under lock so concurrent add_prebuffer_callback calls
        # cannot mutate the list while we iterate (#2412).
        with self.update_lock:
            callbacks = list(self.prebuffer_callbacks)
        for callback in callbacks:
            try:
                callback(track_info)
            except Exception as e:
                debug(f"Prebuffer callback error: {e}")

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
                    _load_result.append(load(file_path, "target"))
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

            # Store in buffer (thread-safe)
            with self.update_lock:
                self.next_track_buffer = audio_data
                self.next_track_info = next_track
                self.next_track_sample_rate = sample_rate

            info(f"Prebuffered: {file_path} ({len(audio_data) / sample_rate:.1f}s)")
            self._notify_prebuffer_callbacks(next_track)

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

    def advance_with_prebuffer(
        self,
        was_playing: bool,
        on_swap: Callable[[], None] | None = None,
    ) -> bool:
        """
        Advance to next track using prebuffered audio if available.

        This provides gapless playback (<10ms gap vs ~100ms for normal load).

        Ordering contract (#5105): the audio is obtained into a local buffer
        *before* any lock is taken, the queue advance is committed next, and
        `file_manager` is mutated last — once, under a single `_audio_lock`
        acquisition shared with ``on_swap``.

        That ordering is what keeps the blocking disk read off the real-time
        path. `next_track()` used to wrap this whole call in `_audio_lock` so
        the prebuffer swap stayed atomic with `get_audio_chunk()` (#3717), but
        on the fallback branches that meant `load_file()`'s disk read ran
        inside the critical section — `_audio_lock` is an RLock, so re-entry
        from the same thread succeeded silently and the audio callback blocked
        for the whole read. That is the exact dropout #3656 fixed for
        `add_to_queue`, at a sibling this fix never reached.

        Committing the queue advance *before* the swap also removes the need
        for the #4100/#4212 rollback machinery: nothing has been mutated when
        the commit fails, so there is nothing to restore.

        Args:
            was_playing: Whether playback was active before transition
            on_swap: Invoked while `_audio_lock` is held, immediately after the
                new audio is installed. `next_track()` passes the `seek(0, …)`
                position reset here so it is atomic with the swap (#3717,
                #2283). Lock nesting is `_audio_lock → PlaybackController._lock`,
                the same order `get_audio_chunk()` uses, so no inversion risk.

        Returns:
            bool: True if successfully advanced, False if no next track
        """
        # Peek-load-commit, retried once. A queue mutation landing between the
        # peek that chose what to load and the commit that advances the index
        # invalidates the prepared audio, so the attempt is discarded and retried
        # against whatever the queue now says is next. One retry, matching the
        # pre-#5105 behaviour, which re-peeked exactly once after a lost
        # prebuffer commit; a mutation storm gives up rather than spinning.
        audio_data: np.ndarray | None = None
        sample_rate: int | None = None
        file_path: str | None = None
        used_prebuffer = False
        committed = False

        for attempt in range(2):
            # Peek first — only advance the queue index after a successful load
            # so a failed load doesn't permanently corrupt navigation (#2882).
            next_track = self.queue.peek_next_track()
            if not next_track:
                info("No next track to advance to")
                return False

            file_path = next_track.get('file_path') or next_track.get('path')
            if not file_path:
                return False

            # Check for prebuffered track — validate it matches the expected
            # next track before using it (fixes #2303: queue modified after
            # prebuffering started). Read both audio_data and next_track_info in
            # a single lock scope to prevent TOCTOU: invalidate_prebuffer() could
            # clear the buffer between two separate acquisitions (#2589).
            with self.update_lock:
                if (self.next_track_buffer is not None and
                        self.next_track_info is not None):
                    audio_data = self.next_track_buffer
                    sample_rate = self.next_track_sample_rate
                    prebuffered_info = self.next_track_info
                else:
                    audio_data = None
                    sample_rate = None
                    prebuffered_info = None
            prebuffer_matches = (
                audio_data is not None
                and sample_rate is not None
                and prebuffered_info is not None
                and (prebuffered_info.get('id') == next_track.get('id')
                     or (prebuffered_info.get('file_path')
                         or prebuffered_info.get('path'))
                     == file_path)
            )

            if prebuffer_matches:
                # Validate sample rate matches current playback (#2408)
                with self.file_manager._audio_lock:
                    current_sr = self.file_manager.sample_rate
                if current_sr is not None and sample_rate != current_sr:
                    warning(
                        f"Sample rate mismatch: prebuffered={sample_rate}Hz, "
                        f"current={current_sr}Hz — falling back to normal load "
                        f"to avoid pitch/speed error"
                    )
                    self.invalidate_prebuffer()
                    prebuffer_matches = False

            if prebuffer_matches:
                # `prebuffer_matches` is only True when both of these are
                # non-None (see its definition above). Restate it here so the
                # narrowing holds for the swap below — mypy cannot carry a
                # None-check made inside a separate boolean expression across
                # the intervening block.
                assert audio_data is not None and sample_rate is not None
                info(f"Using prebuffered track (gapless): {file_path}")
                used_prebuffer = True
            else:
                # Prebuffer unavailable or stale — fall back to a normal load.
                if audio_data is not None:
                    info(f"Discarding stale prebuffer (track mismatch): {file_path}")
                    self.invalidate_prebuffer()
                else:
                    info(f"Prebuffer not available, loading: {file_path}")

                # #5105: THE blocking disk read. It runs here — before any lock
                # is taken and before the queue is touched — so the audio
                # callback, seek() and cleanup() can all keep acquiring
                # `_audio_lock` while it is in flight. Reading into a local also
                # means a failure or a mid-flight queue mutation leaves
                # `file_manager` completely untouched, which is what makes the
                # old rollback blocks (#4100/#4212) unnecessary rather than
                # merely relocated.
                audio_data, sample_rate = self._load_track_audio(file_path)
                if audio_data is None or sample_rate is None:
                    return False
                used_prebuffer = False

            # #3352 (PTS-9): commit via the atomic peek+match operation so a
            # queue mutation between the peek above and this commit cannot leave
            # the engine with audio for one track and an index pointing at
            # another. Nothing has been mutated yet, so losing the race costs
            # only the prepared buffer.
            if self.queue.advance_if_next_matches(next_track):
                committed = True
                break

            if used_prebuffer:
                self.invalidate_prebuffer()
            warning(
                "Queue changed between peek and commit — discarding the "
                f"prepared audio (attempt {attempt + 1}/2)"
            )

        if not committed:
            warning("Queue kept changing during advance — aborting")
            return False

        assert audio_data is not None and sample_rate is not None
        assert file_path is not None

        with self.update_lock:
            # Hold _audio_lock while swapping audio_data so get_audio_chunk()
            # cannot slice the old (shorter) array after we replace it (#2423).
            # `on_swap` (the caller's seek(0, …) position reset) runs inside the
            # same acquisition so the swap and the reset are atomic with the
            # audio callback's chunk read (#3717, #2283).
            with self.file_manager._audio_lock:
                self.file_manager.audio_data = audio_data
                self.file_manager.sample_rate = sample_rate
                self.file_manager.current_file = file_path
                if on_swap is not None:
                    on_swap()

            # Clear prebuffer
            self.next_track_buffer = None
            self.next_track_info = None
            self.next_track_sample_rate = None

        if used_prebuffer:
            info(f"Gapless transition complete: {file_path}")

        # Start prebuffering next track for smooth chain
        self.start_prebuffering()

        return True

    def _load_track_audio(
        self, file_path: str
    ) -> tuple[np.ndarray | None, int | None]:
        """Decode a track into memory without touching any player state.

        Split out of the fallback path so the blocking read has no lock held
        and no `file_manager` mutation attached to it (#5105). Mirrors
        `AudioFileManager.load_file()`'s error handling, but returns the buffer
        instead of installing it.
        """
        try:
            if not Path(file_path).exists():
                error(f"File not found: {file_path}")
                return None, None
            audio_data, sample_rate = load(file_path, "target")
            return audio_data, sample_rate
        except Exception as e:
            error(f"Failed to load file {file_path}: {e}")
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

    def cleanup(self) -> None:
        """Clean up threads and resources.

        Signals the prebuffer worker to stop at the next safe point, then
        waits up to 5s for it to finish.  Non-daemon threads are used so
        the OS never kills the thread while it holds a file handle (#2075).

        Order matters: set _shutdown *before* taking _thread_lock, so a
        start_prebuffering() call that wins the race for the lock sees the flag
        and declines to create a thread. Mirrors the #3694/#4227 _advance_thread
        discipline in enhanced_audio_player.cleanup() (#4631).
        """
        self._shutdown.set()

        # #4631: snapshot the handle under the lock that guards its creation.
        # An unlocked read can observe the pre-assignment value (or tear under
        # free-threaded 3.14+) and skip the join entirely.
        with self._thread_lock:
            prebuffer_thread = self.prebuffer_thread

        # Join OUTSIDE the lock: _prebuffer_worker does not take _thread_lock
        # today, but joining while holding it would deadlock the moment it did.
        # The project's discipline is "callbacks and joins outside locks".
        if prebuffer_thread is not None and prebuffer_thread.is_alive():
            prebuffer_thread.join(timeout=5.0)
            if prebuffer_thread.is_alive():
                warning("Prebuffer thread did not stop within 5s after shutdown signal")

        self.invalidate_prebuffer()
        info("GaplessPlaybackEngine cleaned up")
