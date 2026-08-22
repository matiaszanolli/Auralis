"""
Player Queue Navigation Mixin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Queue navigation (next/previous/add/playlist) for AudioPlayer, extracted
from enhanced_audio_player.py (#4249). Pairs with
``player_file_loading_mixin.py`` — every navigation entry point loads a
file as part of advancing — kept in a separate module purely to stay under
the project's 300-line convention; both are always mixed into AudioPlayer
together.

Mixed into AudioPlayer (rather than composed as a separate object) so the
existing lock discipline — every method below acquires
``self.file_manager._audio_lock`` / ``self.playback`` locks directly on the
player instance, exactly as before the extraction — continues to work
unchanged. Moving code here does NOT change lock acquisition order or scope
relative to the fixed state of #4141 / #3735 / #5105.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import threading
from collections.abc import Callable
from typing import Any

from .audio_file_manager import AudioFileManager
from .gapless_playback_engine import GaplessPlaybackEngine
from .integration_manager import IntegrationManager
from .playback_controller import PlaybackController
from .queue_controller import QueueController


class PlayerQueueNavigationMixin:
    """Queue navigation, delegating to component objects.

    Instance state below is initialized by AudioPlayer.__init__ or provided
    by sibling mixins, not here — declared here only so type checkers know
    this mixin depends on it. The ``load_file`` / ``load_track_from_library``
    annotations are bare (no assignment) so they stay pure type hints and
    don't shadow PlayerFileLoadingMixin's real implementations via MRO.
    """

    file_manager: AudioFileManager
    playback: PlaybackController
    queue: QueueController
    gapless: GaplessPlaybackEngine
    integration: IntegrationManager
    _stop_requested: threading.Event
    # Provided by PlayerFileLoadingMixin.
    load_file: Callable[[str], bool]
    load_track_from_library: Callable[[int], bool]
    # Provided by PlayerFingerprintLoaderMixin.
    _schedule_fingerprint_load: Callable[[str], None]

    def next_track(self) -> bool:
        """
        Skip to next track in queue with gapless playback support.

        Returns:
            bool: True if advanced, False if no next track
        """
        # #3717: the swap and the position reset must be atomic with the audio
        # callback's chunk read. Otherwise the callback can acquire
        # `_audio_lock` between them, call
        # `read_and_advance_position(chunk_size)` against the new (shorter)
        # `audio_data` at the OLD position, and return silence — defeating the
        # gapless guarantee.
        #
        # #5105: that atomicity is now provided by the `on_swap` callback
        # below, which `advance_with_prebuffer()` invokes inside the same
        # `_audio_lock` acquisition as the swap itself. This method no longer
        # takes `_audio_lock` at all.
        #
        # It used to wrap the whole call, which made the fallback branches'
        # `load_file()` — a genuinely blocking disk read with no timeout — run
        # inside the critical section. `_audio_lock` is an RLock, so re-entry
        # from this thread succeeded silently and the read stalled the
        # real-time playback thread for its full duration (tens to hundreds of
        # ms), plus any concurrent `seek()`/`cleanup()`. Hoisting the I/O out
        # of the lock is the same correction #3656 applied to `add_to_queue`.
        #
        # #3781: defer_notifications() still wraps the call so seek()'s notify
        # fires only after `_audio_lock` releases (see AudioPlayer.seek() for
        # full rationale).
        #
        # #3735: the callback dispatch, fingerprint scheduling, and
        # play()/stop() below are not time-critical and don't touch
        # file_manager state, so they stay outside — matching previous_track().
        current_file: str | None = None

        def _on_swap() -> None:
            # Runs with `_audio_lock` held, immediately after the new audio is
            # installed. Lock nesting `_audio_lock → PlaybackController._lock`
            # matches `get_audio_chunk()`, so no inversion risk.
            nonlocal current_file
            # Reset position to 0 for the incoming track (#2283). Both the
            # prebuffer and fallback paths bypass AudioPlayer.load_file(), so
            # the playback.stop() that normally resets position never runs.
            self.playback.seek(0, self.file_manager.get_total_samples())
            # current_file is file_manager state guarded by `_audio_lock` —
            # capture it here so the fingerprint scheduling below (after the
            # lock releases) can't race a concurrent load/advance.
            current_file = self.file_manager.current_file

        with self.playback.defer_notifications():
            was_playing = self.playback.is_playing()
            advanced = self.gapless.advance_with_prebuffer(
                was_playing, on_swap=_on_swap
            )

        if not advanced:
            return False

        self.integration.record_track_completion()

        # The gapless advance also bypasses AudioPlayer.load_file(), so
        # schedule the fingerprint loader here too — otherwise adaptive
        # mastering keeps the previous track's fingerprint, and any
        # in-flight fingerprint thread for the previous file would pass
        # the staleness guard and be applied to the new track (#3463).
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
