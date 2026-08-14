"""
IntegrationManager - Coordinates library, DSP, and callbacks

Responsibilities:
- Library track loading and reference selection
- Auto-mastering profile control
- Effect management
- Callback coordination (thread-safe)
- Session statistics
"""

import threading
import time
from pathlib import Path
from typing import Any, cast
from collections.abc import Callable

from sqlalchemy.exc import SQLAlchemyError

from ..library.models import Track
from ..utils.logging import debug, error, info, warning
from .audio_file_manager import AudioFileManager
from .playback_controller import PlaybackController
from .queue_controller import QueueController


class IntegrationManager:
    """
    Coordinates library, DSP, and external callbacks.

    Decoupled from playback state, file I/O, and queue operations.
    Handles library integration and effect management.

    Phase 6C: Fully migrated to RepositoryFactory pattern (no LibraryManager fallback)

    Callback registration order (fixes #3354 / PTS-10)
    --------------------------------------------------
    1. The internal enricher ``_on_playback_state_change`` is registered
       with ``PlaybackController`` as the **final** step of ``__init__``. It
       enriches state dicts with file/track context before any external
       callback receives them. This must remain the last line of ``__init__``
       so that ``_position_lock`` and ``file_manager`` are guaranteed to be
       initialized before the first event can fire.
    2. External callbacks added via :py:meth:`add_callback` are notified in
       *registration order* by ``_notify_callbacks``. Callers that depend on
       seeing every state change (e.g. UI synchronisers) **must** register
       before playback starts; registration after the first event has been
       dispatched is allowed but emits a warning, since earlier events were
       missed.
    """

    def __init__(
        self,
        playback: PlaybackController,
        file_manager: AudioFileManager,
        queue: QueueController,
        processor: Any,  # RealtimeProcessor
        get_repository_factory: Callable[[], Any],
    ):
        """
        Initialize integration manager.

        Args:
            playback: PlaybackController instance
            file_manager: AudioFileManager instance
            queue: QueueController instance
            processor: RealtimeProcessor instance
            get_repository_factory: Callable that returns RepositoryFactory instance (REQUIRED)
        """
        self.playback = playback
        self.file_manager = file_manager
        self.queue = queue
        self.processor = processor
        self.get_repository_factory = get_repository_factory

        # Library integration. Backing fields for the `current_track` property;
        # assigned directly here because `_position_lock` is not built until
        # further down this constructor.
        self._current_track: Track | None = None
        # Pre-materialised `current_track.to_dict()` (#4552). Readers use this
        # instead of touching the ORM object, so no lazy-load SQL can be
        # emitted while `_position_lock` is held. Swapped atomically with
        # `_current_track` by `set_current_track`.
        self._current_track_dict: dict[str, Any] | None = None
        self.auto_reference_selection = True

        # External callbacks (application-level)
        self.callbacks: list[Callable[[dict[str, Any]], None]] = []
        self._callbacks_lock = threading.Lock()  # Protects callbacks list (fixes #2433)
        # Tracks whether any event has already been delivered; late
        # registration is allowed but warns about missed earlier events (#3354).
        self._first_event_dispatched: bool = False

        # Statistics
        self.tracks_played = 0
        self.total_play_time = 0.0
        self.session_start_time = time.time()
        self._stats_lock = threading.Lock()  # guards tracks_played (fixes #2472)
        # Cross-component lock: ensures position + sample_rate are read atomically
        # during gapless transitions when file_manager swaps to the new track (fixes #2899).
        self._position_lock = threading.RLock()

        # Register to receive playback state changes
        self.playback.add_callback(self._on_playback_state_change)

    def set_current_track(self, track: "Track | None") -> None:
        """Set ``current_track`` under ``_position_lock`` (#3786, #4574).

        The lock owner lives here rather than at the call site so every writer
        — the internal ``load_track_from_library`` path and the public
        ``AudioPlayer.current_track`` setter alike — goes through one guarded
        entry point, matching the lock that ``_on_playback_state_change`` and
        ``get_playback_info`` hold when they read it.

        #4552: the ``to_dict()`` snapshot is materialised **here, before the
        lock is taken**, rather than by the readers inside their critical
        sections. ``Track.to_dict()`` walks ``artists`` / ``album``, which lazy
        loads and therefore emits SQL; doing that under ``_position_lock`` put
        a library round-trip inside a player lock (inverting the documented
        Player-lock -> Library-session ordering) and could raise
        ``DetachedInstanceError`` while the lock was held, out of the playback
        state-change callback. Both values are then swapped together under the
        lock, so #4102's "playback and library.current_track describe one
        track" invariant is preserved.
        """
        snapshot = self._materialise_track(track)
        with self._position_lock:
            self._current_track = track
            self._current_track_dict = snapshot

    @property
    def current_track(self) -> "Track | None":
        """The live ORM track object (unchanged shape for existing readers)."""
        return self._current_track

    @current_track.setter
    def current_track(self, track: "Track | None") -> None:
        """Route raw assignment through :py:meth:`set_current_track` (#4552).

        Production code already went through ``set_current_track``, but the
        attribute stayed publicly writable — and a direct write would now set
        the ORM reference while leaving ``_current_track_dict`` stale, which is
        precisely the drift the fix has to prevent. Making it a property means
        there is exactly one way to write this state.
        """
        self.set_current_track(track)

    @staticmethod
    def _materialise_track(track: "Track | None") -> dict[str, Any] | None:
        """Build a plain-dict snapshot of ``track`` outside any player lock.

        Returns ``None`` for a ``None`` track, preserving the shape every
        consumer already handles. A detached/expired ORM instance degrades to
        ``None`` with a warning rather than propagating — the alternative is an
        exception escaping a playback callback, which is exactly what #4552
        set out to remove.

        ``AttributeError`` is caught alongside the SQLAlchemy errors because
        ``current_track`` is a public attribute that accepts any object; test
        stand-ins and duck-typed tracks without ``to_dict`` must not break
        assignment. Before #4552 such an object raised at *read* time instead
        (inside ``_position_lock``), so degrading here is strictly safer.
        """
        if track is None:
            return None
        try:
            return track.to_dict()
        except (SQLAlchemyError, AttributeError) as e:
            warning(f"Could not snapshot current track metadata (#4552): {e}")
            return None

    def _get_repos(self) -> Any:
        """Get repository factory for data access."""
        try:
            factory = self.get_repository_factory()
            if factory:
                return factory
        except (TypeError, AttributeError) as e:
            error(f"Failed to get repository factory: {e}")

        raise RuntimeError(
            "Repository factory not available. "
            "Ensure get_repository_factory is properly configured during startup."
        )

    def add_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register a callback for integration events.

        Thread-safe (fixes #2433). Callbacks are invoked in registration
        order by :py:meth:`_notify_callbacks` (fixes #3354).

        Register all callbacks **before** playback begins. Callbacks added
        after the first state event has already been dispatched are still
        accepted, but a warning is emitted because they will not see any
        events that fired prior to registration.
        """
        with self._callbacks_lock:
            already_dispatched = self._first_event_dispatched
            self.callbacks.append(callback)
        if already_dispatched:
            warning(
                "IntegrationManager.add_callback called after first event "
                "dispatched; earlier state events were missed by this "
                "callback (see #3354 — register callbacks before play()/load)."
            )

    def _notify_callbacks(self, state_info: dict[str, Any]) -> None:
        """Notify all callbacks (snapshot pattern to avoid holding lock during execution, fixes #2433)"""
        with self._callbacks_lock:
            snapshot = list(self.callbacks)
            self._first_event_dispatched = True
        for callback in snapshot:
            try:
                callback(state_info)
            except Exception as e:
                debug(f"Callback error: {e}")

    def _on_playback_state_change(self, state_info: dict[str, Any] | None) -> None:
        """Receive and propagate playback state changes"""
        # Initialize state_info if None
        if state_info is None:
            state_info = {}
        # Enrich state info with current context (atomic snapshot, fixes #2899)
        with self._position_lock:
            # #3785: current_file is AudioFileManager state written under its
            # own _audio_lock, not _position_lock — read it under _audio_lock
            # too instead of as a raw attribute access, closing the torn/stale
            # read window against a concurrent load/advance.
            with self.file_manager._audio_lock:
                current_file = self.file_manager.current_file
            state_info.update({
                'position_seconds': self._get_position_seconds(),
                'duration_seconds': self.file_manager.get_duration(),
                'current_file': current_file,
                # Pre-materialised at assignment time (#4552) — no ORM access,
                # and therefore no SQL, under _position_lock.
                'current_track': self._current_track_dict,
            })
        self._notify_callbacks(state_info)

    def load_track_from_library(self, track_id: int) -> bool:
        """
        Load a track from the library by ID.

        Args:
            track_id: Database ID of track

        Returns:
            bool: True if successful
        """
        try:
            repos = self._get_repos()
            track = repos.tracks.get_by_id(track_id)
            if not track:
                error(f"Track not found in library: {track_id}")
                return False

            # Load the audio file
            if not self.file_manager.load_file(cast(str, track.filepath)):
                return False

            # #3786: write `current_track` under the same lock used by
            # `_on_playback_state_change` and `get_playback_info` to read
            # it. Without this, a concurrent reader could see
            # `current_track` pointing at the new track while
            # `position_seconds` still reflected the previous one.
            self.set_current_track(track)

            # Record play count
            repos.tracks.record_play(track_id)

            # Auto-select reference if enabled
            if self.auto_reference_selection:
                self._auto_select_reference(track)

            info(f"Loaded track from library: {track.title}")
            self._notify_callbacks({
                'action': 'track_loaded',
                'track': track.to_dict()
            })
            return True

        except Exception as e:
            error(f"Failed to load track from library: {e}")
            return False

    def _auto_select_reference(self, track: Track) -> None:
        """Automatically select a suitable reference track"""
        try:
            # Try recommended reference first
            if track.recommended_reference and Path(track.recommended_reference).exists():
                # The truthiness check above already narrows this to `str`, so
                # the cast mypy used to need here is now redundant.
                if self.file_manager.load_reference(track.recommended_reference) is not None:
                    info(f"Using recommended reference: {track.recommended_reference}")
                    self._notify_callbacks({
                        'action': 'reference_loaded',
                        'reference_file': track.recommended_reference
                    })
                    return

            # Find and try similar tracks as references
            repos = self._get_repos()
            # find_similar returns list[Track], not a 2-tuple (#4935) — the
            # old `references, _ = ...` destructuring raised ValueError for
            # any result count other than exactly 2, silently swallowed by
            # the broad except below on almost every real invocation.
            references = repos.tracks.find_similar(track, limit=3)

            for ref_track in references:
                if Path(cast(str, ref_track.filepath)).exists():
                    if self.file_manager.load_reference(cast(str, ref_track.filepath)) is not None:
                        ref_name = f"{ref_track.title} by {ref_track.artists[0].name if ref_track.artists else 'Unknown'}"
                        info(f"Auto-selected reference: {ref_name}")
                        self._notify_callbacks({
                            'action': 'reference_loaded',
                            'reference_file': ref_track.filepath
                        })
                        return

            warning(f"No suitable reference found for: {track.title}")

        except Exception as e:
            warning(f"Auto reference selection failed: {e}")

    def set_effect_enabled(self, effect_name: str, enabled: bool) -> None:
        """Enable/disable specific DSP effect"""
        self.processor.set_effect_enabled(effect_name, enabled)
        self._notify_callbacks({
            'action': 'effect_changed',
            'effect': effect_name,
            'enabled': enabled
        })

    def set_auto_master_profile(self, profile: str) -> None:
        """Set auto-mastering profile"""
        self.processor.set_auto_master_profile(profile)
        self._notify_callbacks({
            'action': 'profile_changed',
            'profile': profile
        })

    def get_playback_info(self) -> dict[str, Any]:
        """Get comprehensive playback information"""
        queue_info = self.queue.get_queue_info()

        with self._position_lock:
            # #3691: take both state.value and is_playing in a single
            # PlaybackController._lock acquisition so a state transition
            # between the two reads can't produce an inconsistent snapshot
            # (e.g. state="paused" + is_playing=True).
            state_value, is_playing = self.playback.get_state_snapshot()
            # #3785: current_file is AudioFileManager state written under its
            # own _audio_lock — read it under _audio_lock rather than as a
            # raw attribute access (matches the _position_lock -> _audio_lock
            # order already used by _get_position_seconds() just above).
            with self.file_manager._audio_lock:
                current_file = self.file_manager.current_file
            playback_info = {
                'state': state_value,
                'position_seconds': self._get_position_seconds(),
                'duration_seconds': self.file_manager.get_duration(),
                'current_file': current_file,
                'is_playing': is_playing,
            }
            # #4102: read current_track inside the SAME _position_lock block
            # that took position/current_file, so the returned `playback` and
            # `library.current_track` always describe one track. The write side
            # is locked under _position_lock (#3786); reading it after the lock
            # released could pair the new track's position with the old track's
            # metadata for one WebSocket poll during a gapless/seek transition.
            # #4552: this is the dict materialised at assignment time, so the
            # invariant is kept without any ORM access inside the lock.
            current_track_snapshot = self._current_track_dict

        # #4552: read the session counters under _stats_lock, matching the
        # write side in record_track_completion (#2472). Unlocked, a poll could
        # observe a torn tracks_played / total_play_time pair mid-update.
        # Taken after _position_lock is released, so the two never nest.
        with self._stats_lock:
            session_info = {
                'tracks_played': self.tracks_played,
                'session_duration': time.time() - self.session_start_time,
                'total_play_time': self.total_play_time,
            }

        return {
            'playback': playback_info,
            'queue': queue_info,
            'library': {
                'current_track': current_track_snapshot,
                'auto_reference_selection': self.auto_reference_selection,
            },
            'processing': self.processor.get_processing_info(),
            'session': session_info,
        }

    def record_track_completion(self) -> None:
        """Record that current track completed (fixes #2472: atomic increment)."""
        with self._stats_lock:
            self.tracks_played += 1
            count = self.tracks_played
        self._notify_callbacks({
            'action': 'track_completed',
            'tracks_played': count
        })

    def _get_position_seconds(self) -> float:
        """Get current playback position in seconds (clamped to duration).

        Reads position via PlaybackController.get_position_snapshot() which
        holds PlaybackController._lock, then snapshots the file_manager's
        audio state atomically under its own _audio_lock. Pre-fix (#3474)
        the reader checked `audio_data is None` and then read `sample_rate`
        / `get_duration()` separately — a concurrent `clear_audio()` could
        slip between those reads, producing inconsistent state or
        ZeroDivisionError. The dedicated snapshot helper closes that window.

        _position_lock continues to guard the broader gapless-transition
        consistency (#2899, #3363); the new helper handles audio-state
        atomicity orthogonally so no lock-ordering concern arises.
        """
        with self._position_lock:
            is_loaded, sample_rate, duration, _total = self.file_manager.get_state_snapshot()
            if not is_loaded:
                return 0.0
            position_samples = self.playback.get_position_snapshot()
            position_seconds = position_samples / sample_rate
        return min(position_seconds, duration)

    def cleanup(self) -> None:
        """Clean up resources"""
        self.processor.reset_all_effects()
        info("IntegrationManager cleaned up")
