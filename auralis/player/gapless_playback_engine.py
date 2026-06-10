"""
GaplessPlaybackEngine - Handles prebuffering and seamless track transitions

Responsibilities:
- Background prebuffering of next track
- Seamless track transitions (gapless playback)
- Thread management for prebuffering
- Buffer validation and synchronization
"""

import threading
from typing import Any
from collections.abc import Callable

import numpy as np

from ..io.loader import load
from ..utils.logging import debug, info, warning
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
        self.update_lock = threading.Lock()
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
        if not self.prebuffer_enabled or self._shutdown.is_set():
            return

        with self._thread_lock:
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

    def advance_with_prebuffer(self, was_playing: bool) -> bool:
        """
        Advance to next track using prebuffered audio if available.

        This provides gapless playback (<10ms gap vs ~100ms for normal load).

        Args:
            was_playing: Whether playback was active before transition

        Returns:
            bool: True if successfully advanced, False if no next track
        """
        # Peek first — only advance the queue index after a successful load
        # so a failed load_file() doesn't permanently corrupt navigation (#2882).
        next_track = self.queue.peek_next_track()
        if not next_track:
            info("No next track to advance to")
            return False

        file_path = next_track.get('file_path') or next_track.get('path')
        if not file_path:
            return False

        # Check for prebuffered track — validate it matches the expected next track
        # before using it (fixes #2303: queue modified after prebuffering started).
        # Read both audio_data and next_track_info in a single lock scope to
        # prevent TOCTOU: invalidate_prebuffer() could clear the buffer between
        # two separate lock acquisitions (#2589).
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
                 or (prebuffered_info.get('file_path') or prebuffered_info.get('path'))
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
            # Use prebuffered audio (gapless!)
            info(f"Using prebuffered track (gapless): {file_path}")

            # #3352 (PTS-9): commit the advance via the atomic peek+match
            # operation so a queue mutation between our earlier peek and this
            # commit cannot leave the engine with audio for one track and a
            # queue index pointing at a different one. On mismatch the queue
            # changed under us — invalidate the prebuffer and fall back to a
            # fresh load against whatever the queue says is next now.
            advanced = self.queue.advance_if_next_matches(next_track)
            if not advanced:
                warning(
                    "Queue changed between prebuffer and commit — discarding "
                    "stale prebuffer and falling back to normal load"
                )
                self.invalidate_prebuffer()
                fresh_next = self.queue.peek_next_track()
                if not fresh_next:
                    return False
                fresh_path = fresh_next.get('file_path') or fresh_next.get('path')
                if not fresh_path:
                    return False
                # #4100: load_file() atomically swaps audio_data/sample_rate/
                # current_file. If the queue mutates AGAIN before we commit the
                # advance below, we must roll that swap back — otherwise we
                # return False with audio_data pointing at the new track while
                # current_index still points at the old one (the caller only
                # resets position / reloads the fingerprint on True), so the new
                # audio would play at the old position with the old fingerprint.
                # Snapshot the prior track under _audio_lock so the restore is
                # atomic with get_audio_chunk() readers.
                with self.file_manager._audio_lock:
                    old_audio = self.file_manager.audio_data
                    old_sr = self.file_manager.sample_rate
                    old_file = self.file_manager.current_file
                if not self.file_manager.load_file(fresh_path):
                    return False
                if not self.queue.advance_if_next_matches(fresh_next):
                    # Queue mutated again — roll back the audio swap so
                    # audio_data stays consistent with the un-advanced index,
                    # then abort rather than commit a stale advance.
                    with self.file_manager._audio_lock:
                        self.file_manager.audio_data = old_audio
                        if old_sr is not None:
                            self.file_manager.sample_rate = old_sr
                        self.file_manager.current_file = old_file
                    warning("Queue mutated during fallback load — aborting advance")
                    return False
                self.start_prebuffering()
                return True

            with self.update_lock:
                # Hold _audio_lock while swapping audio_data so get_audio_chunk()
                # cannot slice the old (shorter) array after we replace it (#2423).
                with self.file_manager._audio_lock:
                    self.file_manager.audio_data = audio_data
                    self.file_manager.sample_rate = sample_rate
                    self.file_manager.current_file = file_path

                # Clear prebuffer
                self.next_track_buffer = None
                self.next_track_info = None
                self.next_track_sample_rate = None

            info(f"Gapless transition complete: {file_path}")
        else:
            # Prebuffer unavailable or stale — fall back to normal loading
            if audio_data is not None and not prebuffer_matches:
                info(f"Discarding stale prebuffer (track mismatch): {file_path}")
                self.invalidate_prebuffer()
            else:
                info(f"Prebuffer not available, loading: {file_path}")
            # #4212: load_file() atomically swaps audio_data/sample_rate/
            # current_file to track N+1. If the queue mutates before we commit
            # the advance below, we must roll that swap back — otherwise we
            # return False with audio_data pointing at N+1 while current_index
            # still points at N (the caller only resets position / reloads the
            # fingerprint on True), so the new audio would play at the old
            # position with the old fingerprint. Mirror the prebuffer fallback
            # rollback above (#4100). Snapshot under _audio_lock so the restore
            # is atomic with get_audio_chunk() readers.
            with self.file_manager._audio_lock:
                old_audio = self.file_manager.audio_data
                old_sr = self.file_manager.sample_rate
                old_file = self.file_manager.current_file
            if not self.file_manager.load_file(file_path):
                return False
            # Load succeeded — commit the queue advance via the same atomic
            # peek+match operation (#3352). If the queue mutated between our
            # earlier peek and now, the load was wasted — roll back the audio
            # swap so audio_data stays consistent with the un-advanced index,
            # then abort rather than commit a stale advance.
            if not self.queue.advance_if_next_matches(next_track):
                with self.file_manager._audio_lock:
                    self.file_manager.audio_data = old_audio
                    if old_sr is not None:
                        self.file_manager.sample_rate = old_sr
                    self.file_manager.current_file = old_file
                warning(
                    "Queue changed during fallback load — aborting advance to "
                    "avoid pointing current_index at a different track"
                )
                return False

        # Start prebuffering next track for smooth chain
        self.start_prebuffering()

        return True

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
        """
        self._shutdown.set()

        if self.prebuffer_thread and self.prebuffer_thread.is_alive():
            self.prebuffer_thread.join(timeout=5.0)
            if self.prebuffer_thread.is_alive():
                warning("Prebuffer thread did not stop within 5s after shutdown signal")

        self.invalidate_prebuffer()
        info("GaplessPlaybackEngine cleaned up")
