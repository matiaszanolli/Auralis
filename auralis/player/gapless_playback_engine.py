"""
GaplessPlaybackEngine - Handles prebuffering and seamless track transitions

Responsibilities:
- Background prebuffering of next track (gapless_prebuffer.PrebufferMixin)
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
from ..utils.logging import error, info, warning
from .audio_file_manager import AudioFileManager
from .gapless_prebuffer import PrebufferMixin
from .queue_controller import QueueController
from .queue_entry import entry_path


class GaplessPlaybackEngine(PrebufferMixin):
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
        # RLock, not Lock (#3782): advance_with_prebuffer() nests
        # file_manager._audio_lock inside update_lock (to swap audio_data
        # atomically with get_audio_chunk() readers, #2423).
        #
        # #5331: since #5105, next_track() no longer holds _audio_lock on
        # entry, so the geometry documented here used to be
        # `_audio_lock -> update_lock -> _audio_lock` (reentrant) is stale —
        # today the only nesting this file exercises is `update_lock ->
        # _audio_lock`, the reverse of what that comment said was the
        # invariant. Ordering invariant, current: update_lock is always the
        # outer lock — never acquire _audio_lock first and then update_lock.
        self.update_lock = threading.RLock()
        self._thread_lock = threading.Lock()   # guards thread creation (#2075)
        self._shutdown = threading.Event()     # signals worker to exit cleanly (#2075)

    def _load_audio(self, file_path: str) -> tuple[np.ndarray, int]:
        """The one decode call both the advance fallback and the prebuffer worker use.

        Kept on the engine, resolving ``load`` from this module, so a test that
        patches ``gapless_playback_engine.load`` reaches every decode path.
        """
        return load(file_path, "target")

    def advance_with_prebuffer(
        self,
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

            file_path = entry_path(next_track)
            if not file_path:
                return False

            # Use the prebuffer only if it matches the expected next track (#2303: the queue may
            # have changed since). Read buffer and info in one lock scope and match inside it
            # (#5583 helper) so invalidate_prebuffer() cannot slip between two acquisitions (#2589).
            with self.update_lock:
                if (self.next_track_buffer is not None and
                        self.next_track_info is not None):
                    audio_data = self.next_track_buffer
                    sample_rate = self.next_track_sample_rate
                else:
                    audio_data = None
                    sample_rate = None
                prebuffer_matches = self._prebuffer_matches(next_track)

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
            audio_data, sample_rate = self._load_audio(file_path)
            return audio_data, sample_rate
        except Exception as e:
            error(f"Failed to load file {file_path}: {e}")
            return None, None

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
