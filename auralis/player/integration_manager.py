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
from typing import Any
from collections.abc import Callable

from sqlalchemy.exc import SQLAlchemyError

from ..library.models import Track
from ..utils.logging import debug, info, warning
from .audio_file_manager import AudioFileManager
from .playback_controller import PlaybackController
from .integration_library import LibraryLoadingMixin
from .integration_reporting import PlaybackReportingMixin
from .queue_controller import QueueController


class IntegrationManager(LibraryLoadingMixin, PlaybackReportingMixin):
    """
    Coordinates library, DSP, and external callbacks.

    Decoupled from playback state, file I/O, and queue operations.
    Handles library integration and effect management.


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
            position_seconds, duration_seconds, current_file = self._track_position_snapshot()
            state_info.update({
                'position_seconds': position_seconds,
                'duration_seconds': duration_seconds,
                'current_file': current_file,
                # Pre-materialised at assignment time (#4552) — no ORM access,
                # and therefore no SQL, under _position_lock.
                'current_track': self._current_track_dict,
            })
        self._notify_callbacks(state_info)

    def set_effect_enabled(self, effect_name: str, enabled: bool) -> None:
        """Set specific DSP effect"""
        self.processor.set_effect_enabled(effect_name, enabled)
        self._notify_callbacks({
            'action': 'effect_changed',
            'effect': effect_name,
            'enabled': enabled
        })

    def cleanup(self) -> None:
        """Clean up resources"""
        self.processor.reset_all_effects()
        info("IntegrationManager cleaned up")
