"""
Player File Loading Mixin
~~~~~~~~~~~~~~~~~~~~~~~~~

Track/reference file loading for AudioPlayer, extracted from
enhanced_audio_player.py (#4249). Split out from queue navigation
(``player_queue_navigation_mixin.py``) purely to keep both modules under
the project's 300-line convention — the two remain a tightly coupled pair
(every navigation entry point loads a file as part of advancing) and are
always mixed into ``AudioPlayer`` together.

Mixed into AudioPlayer (rather than composed as a separate object) so the
existing lock discipline — every method below acquires
``self.file_manager._audio_lock`` / ``self.playback`` locks directly on the
player instance, exactly as before the extraction — continues to work
unchanged. Moving code here does NOT change lock acquisition order or scope
relative to the fixed state of #4141 / #3735 / #5105.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable

from .audio_file_manager import AudioFileManager
from .gapless_playback_engine import GaplessPlaybackEngine
from .integration_manager import IntegrationManager
from .playback_controller import PlaybackController
from .realtime import RealtimeProcessor


class PlayerFileLoadingMixin:
    """Track/reference file loading, delegating to component objects.

    Instance state below is initialized by AudioPlayer.__init__ or provided
    by sibling mixins, not here — declared here only so type checkers know
    this mixin depends on it.
    """

    file_manager: AudioFileManager
    playback: PlaybackController
    gapless: GaplessPlaybackEngine
    integration: IntegrationManager
    processor: RealtimeProcessor
    # Provided by PlayerFingerprintLoaderMixin. Bare annotation only (no
    # assignment) — this must NOT become a real attribute in this class's
    # __dict__, or it would shadow PlayerFingerprintLoaderMixin's actual
    # implementation via MRO regardless of base-class order.
    _schedule_fingerprint_load: Callable[[str], None]

    def load_file(self, file_path: str) -> bool:
        """
        Load an audio file for playback with automatic fingerprinting for adaptive mastering.

        Args:
            file_path: Path to the audio file

        Returns:
            bool: True if successful
        """
        # #5581: pass the position reset as an on_loaded hook so it runs in
        # the SAME _audio_lock critical section as the buffer swap inside
        # file_manager.load_file. The previous two-step form (load_file
        # swaps under the lock and releases; the mixin re-took the RLock for
        # load_and_stop) left a window where a concurrent get_audio_chunk()
        # saw the new track's audio at the old position.
        # #3781 (unchanged): defer_notifications() stays OUTER — the hook
        # runs under _audio_lock, so its notify must be queued and flushed
        # only after the lock releases (callbacks under _audio_lock are the
        # AB-BA deadlock defer_notifications exists to prevent).
        with self.playback.defer_notifications():
            loaded = self.file_manager.load_file(
                file_path, on_loaded=self.playback.load_and_stop
            )
        if loaded:
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
        # #5581 (mirror of load_file): pass the position reset as an on_loaded
        # hook so it runs inside file_manager.load_file's swap critical
        # section — swap+reset is atomic for chunk readers. The reset fires
        # before integration's post-load steps (set_current_track,
        # record_play, reference auto-selection) rather than after all of
        # them; the chunk-reader invariant the old re-lock guarded is
        # swap-vs-position, which this closes at the swap itself. #3785: the
        # hook captures current_file inside the same critical section.
        current_file: str | None = None

        def _on_loaded() -> None:
            nonlocal current_file
            self.playback.load_and_stop()
            current_file = self.file_manager.current_file

        # #3781: defer_notifications() outer — the hook runs under
        # _audio_lock, so its notify must be queued and flushed only after
        # the lock releases.
        with self.playback.defer_notifications():
            loaded = self.integration.load_track_from_library(track_id, on_loaded=_on_loaded)

        if loaded:
            # IntegrationManager.load_track_from_library() calls
            # file_manager.load_file() internally, which sets current_file.
            # Schedule the fingerprint loader here (the player wrapper
            # bypasses AudioPlayer.load_file()) so adaptive mastering picks
            # up the new track instead of keeping the previous one (#3463).
            if current_file:
                self._schedule_fingerprint_load(current_file)
            self.gapless.start_prebuffering()
            return True
        else:
            self.playback.set_error()
            return False
