"""
Auralis Audio Player
~~~~~~~~~~~~~~~~~~~~

Real-time audio player with advanced DSP processing and library integration

Refactored from monolithic design into 5 focused components:
- PlaybackController: State machine (PLAYING, PAUSED, STOPPED, etc.)
- AudioFileManager: File I/O and audio data access
- QueueController: Queue and playlist management
- GaplessPlaybackEngine: Prebuffering and seamless transitions
- IntegrationManager: Library, callbacks, statistics

Uses Facade pattern to maintain backward-compatible API.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import threading
from pathlib import Path
from typing import Any
from collections.abc import Callable

import numpy as np

from ..analysis.fingerprint.fingerprint_service import FingerprintService
from ..utils.logging import debug, info, warning
from .audio_file_manager import AudioFileManager
from .config import PlayerConfig
from .gapless_playback_engine import GaplessPlaybackEngine
from .integration_manager import IntegrationManager
from .playback_controller import PlaybackController, PlaybackState
from .queue_controller import QueueController
from .realtime_processor import RealtimeProcessor

# Backward compatibility alias for old test code
QueueManager = QueueController


class AudioPlayer:
    """
    Real-time audio player with advanced DSP and library integration.

    Facade that coordinates 5 specialized components for clean separation of concerns:
    - PlaybackController: State machine
    - AudioFileManager: File I/O
    - QueueController: Queue/playlist
    - GaplessPlaybackEngine: Prebuffering
    - IntegrationManager: Library/callbacks

    Features:
    - Advanced real-time DSP processing
    - Automatic mastering with multiple profiles
    - Queue management and playlist support
    - Gapless playback with prebuffering
    - Library integration and auto-reference selection
    - Performance monitoring and statistics

    API compatible with AudioPlayer.

    Phase 6C: Fully migrated to RepositoryFactory pattern (no LibraryManager fallback)
    """

    def __init__(
        self,
        config: PlayerConfig | None = None,
        get_repository_factory: Callable[[], Any] | None = None,
        library_manager: Any | None = None
    ) -> None:
        """
        Initialize the enhanced audio player with components.

        Args:
            config: Player configuration (PlayerConfig)
            get_repository_factory: Callable that returns RepositoryFactory instance (REQUIRED)
            library_manager: Deprecated, kept for backward compatibility only
        """
        if config is None:
            config = PlayerConfig()

        # Validate required parameter
        if get_repository_factory is None:
            raise ValueError("get_repository_factory is required")

        self.config = config
        self.get_repository_factory = get_repository_factory

        # Initialize components
        self.playback = PlaybackController()
        self.file_manager = AudioFileManager(config.sample_rate)
        self.queue = QueueController(get_repository_factory, library_manager)
        self.processor = RealtimeProcessor(config)
        self.gapless = GaplessPlaybackEngine(self.file_manager, self.queue)
        self.integration = IntegrationManager(
            self.playback,
            self.file_manager,
            self.queue,
            self.processor,
            get_repository_factory,
        )

        # Fingerprinting service for adaptive mastering
        self.fingerprint_service = FingerprintService()
        self._current_fingerprint: dict | None = None
        # Protects _current_fingerprint against a background loader writing
        # concurrently with the playback thread reading it for adaptive DSP
        # parameters (fixes #2491).
        self._fingerprint_lock = threading.Lock()
        # Monotonic counter incremented on each track load; fingerprint
        # callbacks check their generation matches before applying (#3445).
        self._track_generation: int = 0

        # Control flags
        self.auto_advance = True
        self._auto_advancing = threading.Event()
        self._advance_generation = 0  # Monotonic counter for compare-and-clear (#3350)
        self._stop_requested = threading.Event()  # Prevents auto-advance after stop() (#3296)
        # #3694: hold a reference to the most recently spawned auto-advance
        # thread so cleanup() can join it. Without this, an in-flight advance
        # thread that has already passed its _stop_requested check can call
        # load_file() *after* cleanup() returns, leaving audio_data non-None
        # post-teardown (test flakiness; benign in Electron production where
        # the process exits immediately after cleanup).
        self._advance_thread: threading.Thread | None = None
        # #3727: covers the timeout path of #3694. cleanup() sets this
        # before the join; _auto_advance_next() checks it after the
        # is_playing() guard so a thread that gets past the
        # _stop_requested check (timeout window in cleanup) still aborts
        # before invoking next_track() and the subsequent audio_data
        # swap. Without this, a 2 s join timeout on slow I/O could
        # leave audio_data non-None after cleanup() returns.
        self._cleanup_in_progress = threading.Event()

        info("Enhanced AudioPlayer initialized (refactored architecture, RepositoryFactory support enabled, fingerprinting enabled)")

    # ========== Playback Control (delegates to PlaybackController) ==========

    def play(self) -> bool:
        """Start playback"""
        if not self.file_manager.is_loaded():
            warning("No audio file loaded")
            return False
        # #3669: clear `_stop_requested` AFTER `playback.play()` succeeds.
        # Previous order (clear → play) allowed a concurrent stop() to set
        # the flag between the clear and the state transition, leaving
        # state=PLAYING with _stop_requested=SET. Auto-advance is then
        # permanently suppressed for the rest of the session (line 474
        # checks `_stop_requested.is_set()` and bails).
        started = self.playback.play()
        if started:
            self._stop_requested.clear()
        return started

    def pause(self) -> bool:
        """Pause playback"""
        return self.playback.pause()

    def stop(self) -> bool:
        """Stop playback"""
        self._stop_requested.set()
        self._auto_advancing.clear()
        return self.playback.stop()

    def seek(self, position_seconds: float) -> bool:
        """
        Seek to a position in seconds.

        Args:
            position_seconds: Target position in seconds

        Returns:
            bool: True if successful
        """
        # #3713: hold `_audio_lock` across the ENTIRE seek, including the
        # `playback.seek()` call. The original #3357 fix only snapshotted
        # `max_samples` and `sample_rate` atomically — but a gapless
        # `advance_with_prebuffer` could still swap to a shorter track
        # between the snapshot and the seek, leaving the clamp using the
        # old (larger) length. The new track would then receive a
        # position > its own length → empty slice → silence + immediate
        # auto-advance. PlaybackController.seek() takes only its own
        # `_lock`; the canonical nesting `_audio_lock → PlaybackController._lock`
        # is already used by `get_audio_chunk` so no inversion risk.
        with self.file_manager._audio_lock:
            if not self.file_manager.is_loaded():
                warning("No audio file loaded")
                return False
            max_samples = self.file_manager.get_total_samples()
            sample_rate = self.file_manager.sample_rate
            position_samples = int(position_seconds * sample_rate)
            return self.playback.seek(position_samples, max_samples)

    @property
    def state(self) -> PlaybackState:
        """Get current playback state"""
        return self.playback.state

    def is_playing(self) -> bool:
        """Check if currently playing"""
        return self.playback.is_playing()

    # ========== File Loading (delegates to AudioFileManager) ==========

    def load_file(self, file_path: str) -> bool:
        """
        Load an audio file for playback with automatic fingerprinting for adaptive mastering.

        Args:
            file_path: Path to the audio file

        Returns:
            bool: True if successful
        """
        if self.file_manager.load_file(file_path):
            # #3667: hold _audio_lock while the playback controller resets
            # position so no concurrent get_audio_chunk() can observe the
            # new audio_data at the old position. file_manager.load_file
            # has already swapped audio_data inside _audio_lock — re-taking
            # the RLock here (it's reentrant) keeps swap+reset visible to
            # readers as a single critical section.
            with self.file_manager._audio_lock:
                self.playback.load_and_stop()

            self._schedule_fingerprint_load(file_path)

            # Start prebuffering next track
            self.gapless.start_prebuffering()

            self.integration._notify_callbacks({
                'action': 'file_loaded',
                'file': file_path
            })
            return True
        else:
            self.playback.set_error()
            return False

    def _schedule_fingerprint_load(self, file_path: str) -> None:
        """
        Bump the generation counter and spawn a background fingerprint loader.

        Called by every track-load entry point (``load_file``,
        ``load_track_from_library``, gapless ``next_track``) so that stale
        in-flight fingerprint threads are invalidated and the new track gets
        its adaptive-mastering fingerprint applied (#3445, #3463).

        Increment + publish runs under ``_fingerprint_lock`` so two
        concurrent loads don't both observe the same value and pass the
        same generation to their loaders (#3473). Plain ``self._x += 1`` is
        LOAD_ATTR/STORE_ATTR at bytecode level — not atomic.

        Args:
            file_path: Path of the now-current audio file.
        """
        with self._fingerprint_lock:
            self._track_generation += 1
            generation = self._track_generation

        threading.Thread(
            target=self._load_fingerprint_for_file,
            args=(file_path, generation),
            daemon=True,
            name="fingerprint-loader",
        ).start()

    def _load_fingerprint_for_file(self, file_path: str, generation: int) -> None:
        """
        Load 25D fingerprint for file and apply to processor for adaptive mastering.

        Uses 3-tier caching: database → .25d file → on-demand computation.
        Non-blocking operation (uses cache hits when available).

        Args:
            file_path: Path to audio file
            generation: Track generation counter — result is discarded if the
                track has changed since this thread was started (#3445).
        """
        try:
            audio_path = Path(file_path)
            fingerprint = self.fingerprint_service.get_or_compute(audio_path)

            # #3719: hold `_fingerprint_lock` across the staleness check
            # AND the processor write. Previously the check was an
            # unlocked atomic int read (#3445) and the
            # `processor.set_fingerprint()` write was OUTSIDE the lock
            # entirely. Race: thread T_A (fp for track 5) passes the
            # check; user skips to track 6 → T_B spawned; T_B hits cache,
            # passes check, calls set_fingerprint(fp6); T_A (still in
            # flight) then calls set_fingerprint(fp5) — overwriting fp6.
            # Holding the lock across check+act serialises the two threads
            # so the newer generation always wins.
            if fingerprint:
                with self._fingerprint_lock:
                    if self._track_generation != generation:
                        debug(f"Discarding stale fingerprint for {audio_path.name} (generation {generation} != {self._track_generation})")
                        return
                    self._current_fingerprint = fingerprint
                    self.processor.set_fingerprint(fingerprint)
                info(f"Fingerprint loaded for adaptive mastering: "
                     f"LUFS {fingerprint.get('lufs', 0):.1f} dB, "
                     f"crest {fingerprint.get('crest_db', 0):.1f} dB")
            else:
                debug(f"Failed to load fingerprint for {audio_path.name}, using profile-based mastering")
                with self._fingerprint_lock:
                    if self._track_generation != generation:
                        return
                    self._current_fingerprint = None
                    self.processor.set_fingerprint(None)

        except Exception as e:
            warning(f"Error loading fingerprint: {e}")
            # Same lock discipline on the error path — check generation
            # and write under the same lock so a newer load doesn't get
            # its fingerprint reset by this stale error handler.
            with self._fingerprint_lock:
                if self._track_generation != generation:
                    return
                self._current_fingerprint = None
                self.processor.set_fingerprint(None)

    def load_reference(self, file_path: str) -> bool:
        """
        Load a reference file for real-time mastering.

        Args:
            file_path: Path to the reference audio file

        Returns:
            bool: True if successful
        """
        ref_data = self.file_manager.load_reference(file_path)
        if ref_data is not None:
            self.processor.set_reference_audio(ref_data)
            self.integration._notify_callbacks({
                'action': 'reference_loaded',
                'file': file_path
            })
        return ref_data is not None

    def load_track_from_library(self, track_id: int) -> bool:
        """
        Load a track from the library by ID.

        Args:
            track_id: Database ID of the track

        Returns:
            bool: True if successful
        """
        if self.integration.load_track_from_library(track_id):
            # Mirror load_file (#3667): hold _audio_lock so the position
            # reset is atomic with the audio swap already done by
            # integration.load_track_from_library -> file_manager.load_file.
            # The DB session is closed before we reach here, so no
            # lock-ordering issue.
            with self.file_manager._audio_lock:
                self.playback.load_and_stop()
            # IntegrationManager.load_track_from_library() calls
            # file_manager.load_file() internally, which sets current_file.
            # Schedule the fingerprint loader here (the player wrapper
            # bypasses AudioPlayer.load_file()) so adaptive mastering picks
            # up the new track instead of keeping the previous one (#3463).
            current_file = self.file_manager.current_file
            if current_file:
                self._schedule_fingerprint_load(current_file)
            self.gapless.start_prebuffering()
            return True
        else:
            self.playback.set_error()
            return False

    # ========== Queue Management (delegates to QueueController) ==========

    def next_track(self) -> bool:
        """
        Skip to next track in queue with gapless playback support.

        Returns:
            bool: True if advanced, False if no next track
        """
        # #3717: hold `_audio_lock` across the entire swap-and-reset
        # sequence. Previously the gapless engine released the lock
        # after swapping `audio_data`, leaving a window where the
        # audio callback could acquire the lock, call
        # `read_and_advance_position(chunk_size)` against the new
        # (shorter) `audio_data` at the OLD position, and return
        # silence — defeating the gapless guarantee. RLock re-entry
        # by the same thread means the inner gapless acquisition is
        # free. Lock nesting `_audio_lock → PlaybackController._lock`
        # is consistent with `get_audio_chunk()` (the prior caller of
        # this pattern), so no inversion risk.
        with self.file_manager._audio_lock:
            was_playing = self.playback.is_playing()

            if self.gapless.advance_with_prebuffer(was_playing):
                self.integration.record_track_completion()

                # Reset position to 0 for the incoming track (#2283).
                # Both the gapless (prebuffer) and fallback paths inside
                # advance_with_prebuffer() bypass AudioPlayer.load_file(), so
                # the playback.stop() that normally resets position is never
                # called.  seek(0, ...) is the lock-safe way to do this.
                # Now atomic with the swap (#3717).
                self.playback.seek(0, self.file_manager.get_total_samples())

                # The gapless advance also bypasses AudioPlayer.load_file(), so
                # schedule the fingerprint loader here too — otherwise adaptive
                # mastering keeps the previous track's fingerprint, and any
                # in-flight fingerprint thread for the previous file would pass
                # the staleness guard and be applied to the new track (#3463).
                current_file = self.file_manager.current_file
                if current_file:
                    self._schedule_fingerprint_load(current_file)

                # #3712: use `_stop_requested.is_set()` for the cancellation
                # check — identical pattern to previous_track() so the two
                # paths cannot drift. Today the gapless path is safe because
                # it doesn't call load_and_stop (so `is_stopped()` would also
                # be False), but a future refactor that adds a stop+load
                # could re-introduce the previous_track regression here too.
                # #4126: double-check after play() — stop() sets _stop_requested
                # without holding _audio_lock, so a concurrent stop() may have
                # won the race between the first check and the play() call.
                if was_playing and not self._stop_requested.is_set():
                    self.playback.play()
                    if self._stop_requested.is_set():
                        self.playback.stop()

                return True

        return False

    def previous_track(self) -> bool:
        """Skip to previous track in queue.

        The queue index is only kept if the file loads successfully;
        on failure the index is rolled back so the queue stays valid (#3442).
        """
        was_playing = self.playback.is_playing()
        # #3726: capture the index atomically under QueueManager._lock so
        # a concurrent next_track / remove_track / reorder_tracks cannot
        # make `saved_index` stale relative to the queue contents.
        # #3668 already locked the rollback WRITE side; this closes the
        # remaining read-side race.
        saved_index = self.queue.snapshot_index()
        prev_track = self.queue.previous_track()
        if prev_track:
            file_path = prev_track.get('file_path') or prev_track.get('path')
            if file_path and self.load_file(file_path):
                # #3712: use `_stop_requested.is_set()` as the cancellation
                # signal instead of `is_stopped()`. `load_file()` calls
                # `playback.load_and_stop()` which unconditionally writes
                # state=STOPPED, so the previous `not is_stopped()` guard
                # was always False after the load — `play()` was unreachable
                # and every previous-track press silently halted playback
                # (regression of #2684). `_stop_requested` is the explicit
                # user-stop event (#3296) and is NOT changed by load_file,
                # so it correctly distinguishes "user pressed stop" from
                # "load_file reset state as part of loading".
                # #4126: double-check after play() — stop() sets _stop_requested
                # without holding _audio_lock, so a concurrent stop() may have
                # won the race between the first check and the play() call.
                if was_playing and not self._stop_requested.is_set():
                    self.playback.play()
                    if self._stop_requested.is_set():
                        self.playback.stop()
                return True
            # File load failed — roll back queue index under lock.
            self.queue.rollback_index(saved_index)
        return False

    def add_to_queue(self, track_info: dict[str, Any]) -> None:
        """Add a track to the playback queue"""
        self.queue.add_track(track_info)

        # #3656: previous version held `_audio_lock` across the entire
        # `load_track_from_library` / `load_file` call, which performs
        # blocking disk I/O before its own inner lock acquisition. Holding
        # the lock during I/O blocked `get_audio_chunk()` (which also takes
        # `_audio_lock`) for the full load duration → audible audio
        # dropout on first track add.
        #
        # The check + load no longer needs to be atomic under `_audio_lock`:
        # `load_file()` internally locks before mutating shared state, and
        # the inner critical section is the actual race window (#3359). The
        # narrow TOCTOU between the check here and the load itself is
        # acceptable — `load_file()` is idempotent (an in-progress load
        # from a concurrent caller will simply overwrite once and settle).
        needs_load = False
        with self.file_manager._audio_lock:
            if not self.file_manager.is_loaded():
                needs_load = True

        if needs_load:
            file_path = track_info.get('file_path') or track_info.get('filepath')
            track_id = track_info.get('id')

            if track_id:
                self.load_track_from_library(track_id)
            elif file_path:
                self.load_file(file_path)

    def add_track_to_queue(self, track_id: int) -> bool:
        """Add a track from the library to the queue"""
        return self.queue.add_track_from_library(track_id)

    def search_and_add_to_queue(self, query: str, limit: int = 10) -> int:
        """Search library and add results to queue"""
        return self.queue.search_and_add(query, limit)

    def load_playlist(self, playlist_id: int, start_index: int = 0) -> bool:
        """Load a playlist from the library"""
        if self.queue.load_playlist(playlist_id, start_index):
            current = self.queue.get_current_track()
            if current:
                track_id = current.get('id')
                if track_id:
                    return self.load_track_from_library(track_id)
        return False

    def clear_queue(self) -> None:
        """Clear the playback queue"""
        self.queue.clear_queue()
        self.gapless.invalidate_prebuffer()

    # ========== Audio Output (delegates to AudioFileManager + Processor) ==========

    def get_audio_chunk(self, chunk_size: int | None = None) -> np.ndarray:
        """
        Get a chunk of processed audio for playback.

        Args:
            chunk_size: Size of audio chunk to return

        Returns:
            Processed audio chunk (stereo, float32)
        """
        if chunk_size is None:
            chunk_size = self.config.buffer_size

        # Hold _audio_lock across the is_loaded check, position read, chunk
        # fetch, end-of-track test, AND the auto-advance test-and-spawn so a
        # concurrent stop()/load_file() cannot unload audio between
        # is_loaded() and the slice (#3295), AND so two concurrent callers
        # cannot both pass the `not _auto_advancing.is_set()` check and spawn
        # duplicate advance threads (#3434 — Event.is_set + .set is TOCTOU).
        # Spawning a thread doesn't block, so we never deadlock; the advance
        # thread acquires the lock independently when it runs.
        with self.file_manager._audio_lock:
            # Return silence if not playing
            if not self.file_manager.is_loaded() or not self.playback.is_playing():
                return np.zeros((chunk_size, 2), dtype=np.float32)

            # Atomically read position and advance to prevent seek race (#2153)
            pos = self.playback.read_and_advance_position(chunk_size)

            # Get raw audio chunk using the captured position
            chunk = self.file_manager.get_audio_chunk(pos, chunk_size)

            # Check for end of track — use atomic flag to prevent concurrent auto-advance
            end_of_track = pos + chunk_size >= self.file_manager.get_total_samples()

            if end_of_track:
                # #3692: gate on has_next_track() instead of
                # is_queue_empty(). is_queue_empty() returns False for
                # "1 track in queue already playing" — we'd spawn
                # auto-advance threads at ~21 Hz against a phantom next
                # track. has_next_track() returns True only when
                # peek_next() would return non-None.
                if self.auto_advance and self.queue.has_next_track():
                    if not self._auto_advancing.is_set():
                        self._auto_advancing.set()
                        self._advance_generation += 1
                        gen = self._advance_generation
                        advance_thread = threading.Thread(
                            target=self._auto_advance_next,
                            args=(gen,),
                            daemon=True
                        )
                        self._advance_thread = advance_thread  # joined in cleanup() (#3694)
                        advance_thread.start()

        # Apply advanced real-time processing (outside the lock — pure CPU
        # work on the captured chunk, no shared state touched).
        processed_chunk = self.processor.process_chunk(chunk)

        return processed_chunk

    def _auto_advance_next(self, generation: int) -> None:
        """Auto-advance to next track (background thread, runs at most once)"""
        try:
            if self._stop_requested.is_set():
                return  # User called stop() — don't start next track (#3296)
            # #3727: also bail if cleanup() is in progress. A 2 s join
            # timeout in cleanup (slow disk I/O during a load_file
            # already in flight) could allow this thread to continue
            # past the _stop_requested check and then call next_track()
            # — which would swap audio_data into a freshly-cleared
            # player. This guard combined with the post-cleanup join
            # makes the test invariant "audio_data is None after
            # cleanup()" hold deterministically.
            if self._cleanup_in_progress.is_set():
                return
            if self.playback.is_playing():
                self.next_track()
        except Exception:
            # next_track() failed (e.g. queue race before lock fix, file error).
            # Stop playback so the audio callback's early-return guard fires and
            # prevents this method from being re-triggered on every subsequent
            # chunk — which would happen because _auto_advancing is cleared in
            # the finally block regardless of outcome (fixes #2441).
            self.playback.stop()
        finally:
            # #3718: hold `_audio_lock` for the compare-and-clear so it is
            # atomic w.r.t. the spawn site in get_audio_chunk() (which
            # also holds _audio_lock when incrementing _advance_generation
            # and spawning the next thread). Previously the unlocked
            # compare allowed: thread A reads gen==5 → True, then
            # get_audio_chunk increments to 6 and spawns thread B, then
            # A clears _auto_advancing while B is still running — the
            # next get_audio_chunk sees the flag clear and spawns thread
            # C, leaving B and C concurrent. The lock guarantees the
            # generation read and the clear happen as one critical
            # section relative to the spawner. #3350 introduced the
            # compare; this fix closes the residual race window.
            with self.file_manager._audio_lock:
                if self._advance_generation == generation:
                    self._auto_advancing.clear()

    # ========== Effects Control (delegates to IntegrationManager) ==========

    def set_effect_enabled(self, effect_name: str, enabled: bool) -> None:
        """Enable/disable specific DSP effects"""
        self.integration.set_effect_enabled(effect_name, enabled)

    def set_auto_master_profile(self, profile: str) -> None:
        """Set auto-mastering profile"""
        self.integration.set_auto_master_profile(profile)

    # ========== Callbacks and State (delegates to various components) ==========

    def add_callback(self, callback: Callable[..., Any]) -> None:
        """Add callback for state updates"""
        # Route through IntegrationManager only — it already bridges
        # PlaybackController state changes via _on_playback_state_change,
        # enriches the dict, and forwards to integration.callbacks.
        # Adding to playback.callbacks directly would invoke cb twice per event
        # (fixes #2471).
        self.integration.add_callback(callback)

    def _notify_callbacks(self, info: dict[str, Any] | None = None) -> None:
        """
        Notify all registered callbacks with current playback information.

        Args:
            info: Optional custom playback info dict to pass to callbacks.
                  If not provided, uses get_playback_info()
        """
        if info is None:
            info = self.get_playback_info()
        self.integration._notify_callbacks(info)

    def get_playback_info(self) -> dict[str, Any]:
        """
        Get comprehensive playback information.

        Returns a flattened view for backward compatibility.
        """
        full_info = self.integration.get_playback_info()

        # Flatten the nested structure for backward compatibility
        return {
            'state': full_info['playback']['state'],
            'position_seconds': full_info['playback']['position_seconds'],
            'duration_seconds': full_info['playback']['duration_seconds'],
            'current_file': full_info['playback']['current_file'],
            'is_playing': full_info['playback']['is_playing'],
            # Also include full nested structure for new code that expects it
            'playback': full_info['playback'],
            'queue': full_info['queue'],
            'library': full_info['library'],
            'processing': full_info['processing'],
            'session': full_info['session'],
        }

    def get_queue_info(self) -> dict[str, Any]:
        """Get detailed queue information"""
        return self.queue.get_queue_info()

    # ========== Shuffle and Repeat (delegates to QueueController) ==========

    def set_shuffle(self, enabled: bool) -> None:
        """Enable/disable shuffle mode"""
        self.queue.set_shuffle(enabled)
        # Shuffle reorders the queue, so the prebuffered next track is stale (fixes #2154)
        self.gapless.invalidate_prebuffer()
        self.integration._notify_callbacks({'action': 'shuffle_changed', 'enabled': enabled})

    def set_repeat(self, enabled: bool) -> None:
        """Enable/disable repeat mode"""
        self.queue.set_repeat(enabled)
        # Repeat changes what the "next" track is (wraps to start) — invalidate (fixes #2154)
        self.gapless.invalidate_prebuffer()
        self.integration._notify_callbacks({'action': 'repeat_changed', 'enabled': enabled})

    # ========== Properties for backward compatibility ==========

    @property
    def current_file(self) -> str | None:
        """Get current audio file path"""
        return self.file_manager.current_file

    @property
    def current_track(self) -> Any:
        """Get current track object from library"""
        return self.integration.current_track

    @current_track.setter
    def current_track(self, value: Any) -> None:
        """Set current track (for compatibility)"""
        self.integration.current_track = value

    @property
    def reference_file(self) -> str | None:
        """Get current reference file path"""
        return self.file_manager.reference_file

    @property
    def audio_data(self) -> Any:
        """Get raw audio data"""
        return self.file_manager.audio_data

    @audio_data.setter
    def audio_data(self, value: Any) -> None:
        """Set audio data under lock with dtype enforcement (#3443)"""
        import numpy as np
        with self.file_manager._audio_lock:
            if value is not None and isinstance(value, np.ndarray):
                if value.dtype not in (np.float32, np.float64):
                    value = value.astype(np.float32)
            self.file_manager.audio_data = value

    @property
    def reference_data(self) -> Any:
        """Get raw reference audio data"""
        return self.file_manager.reference_data

    @reference_data.setter
    def reference_data(self, value: Any) -> None:
        """Set reference data (for compatibility)"""
        self.file_manager.reference_data = value

    @property
    def position(self) -> int:
        """Get current position in samples"""
        return self.playback.position

    @position.setter
    def position(self, value: int) -> None:
        """Set position in samples — thread-safe via PlaybackController.seek()"""
        max_samples = self.file_manager.get_total_samples()
        self.playback.seek(value, max_samples)

    @property
    def sample_rate(self) -> int:
        """Get current sample rate"""
        return self.file_manager.sample_rate

    @sample_rate.setter
    def sample_rate(self, value: int) -> None:
        """Set sample rate (for compatibility)"""
        self.file_manager.sample_rate = value

    # ========== Cleanup ==========

    def cleanup(self) -> None:
        """Clean up resources"""
        # #3727: signal in-flight advance threads BEFORE stop() so the
        # _auto_advance_next early-bail (after the _stop_requested
        # check) sees the cleanup signal. Combined with the join below
        # this closes the timeout-path window left by #3694 alone.
        self._cleanup_in_progress.set()
        # #3438: bump the fingerprint generation counter so any in-flight
        # `_load_fingerprint_for_file` thread (spawned by the most recent
        # track load, still running because they're daemon threads) will
        # fail its `self._track_generation != generation` staleness check
        # under `_fingerprint_lock` and discard rather than write into the
        # freshly-cleaned processor. The existing #3719 lock discipline
        # handles the write-side; the cleanup-time bump just guarantees
        # there's always a newer generation to compare against post-stop.
        with self._fingerprint_lock:
            self._track_generation += 1
        self.stop()
        # #3694: wait for any in-flight auto-advance thread to finish before
        # clearing audio_data. _stop_requested was set by stop() above, but
        # an advance thread already past that gate can still call load_file()
        # and re-populate audio_data after clear_all(). Daemon=True saves us
        # at process exit, but tests that reuse the player (or assert on
        # post-cleanup state) need a deterministic barrier.
        advance_thread = self._advance_thread
        if advance_thread is not None and advance_thread.is_alive():
            advance_thread.join(timeout=2.0)
            if advance_thread.is_alive():
                warning("Auto-advance thread did not exit within cleanup timeout")
        self.file_manager.clear_all()
        self.gapless.cleanup()
        self.integration.cleanup()
        info("AudioPlayer cleanup completed")
