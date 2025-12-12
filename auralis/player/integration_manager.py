# -*- coding: utf-8 -*-

"""
IntegrationManager - Coordinates library, DSP, and callbacks

Responsibilities:
- Library track loading and reference selection
- Auto-mastering profile control
- Effect management
- Callback coordination
- Session statistics
"""

import time
import os
from typing import Dict, Any, Optional, Callable, List, cast
from .playback_controller import PlaybackController
from .audio_file_manager import AudioFileManager
from .queue_controller import QueueController
from ..library.manager import LibraryManager
from ..library.repositories.factory import RepositoryFactory
from ..library.models import Track
from ..utils.logging import debug, info, warning, error


class IntegrationManager:
    """
    Coordinates library, DSP, and external callbacks.

    Decoupled from playback state, file I/O, and queue operations.
    Handles library integration and effect management.
    Uses RepositoryFactory if available, falls back to LibraryManager for backward compatibility.
    """

    def __init__(
        self,
        playback: PlaybackController,
        file_manager: AudioFileManager,
        queue: QueueController,
        processor: Any,  # RealtimeProcessor
        library_manager: Optional[LibraryManager] = None,
        get_repository_factory: Optional[Callable[[], Any]] = None
    ):
        self.playback = playback
        self.file_manager = file_manager
        self.queue = queue
        self.processor = processor
        self.library = library_manager or LibraryManager()
        self.get_repository_factory = get_repository_factory

        # Library integration
        self.current_track: Optional[Track] = None
        self.auto_reference_selection = True

        # External callbacks (application-level)
        self.callbacks: List[Callable[[Dict[str, Any]], None]] = []

        # Statistics
        self.tracks_played = 0
        self.total_play_time = 0.0
        self.session_start_time = time.time()

        # Register to receive playback state changes
        self.playback.add_callback(self._on_playback_state_change)

    def _get_repos(self) -> Any:
        """Get repository factory or LibraryManager for data access."""
        if self.get_repository_factory:
            try:
                factory = self.get_repository_factory()
                if factory:
                    return factory
            except (TypeError, AttributeError):
                pass
        return self.library

    def add_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register callback for integration events"""
        self.callbacks.append(callback)

    def _notify_callbacks(self, state_info: Dict[str, Any]) -> None:
        """Notify all callbacks"""
        for callback in self.callbacks:
            try:
                callback(state_info)
            except Exception as e:
                debug(f"Callback error: {e}")

    def _on_playback_state_change(self, state_info: Dict[str, Any]) -> None:
        """Receive and propagate playback state changes"""
        # Enrich state info with current context
        state_info.update({
            'position_seconds': self._get_position_seconds(),
            'duration_seconds': self.file_manager.get_duration(),
            'current_file': self.file_manager.current_file,
            'current_track': self.current_track.to_dict() if self.current_track else None,
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

            # Store track reference
            self.current_track = track

            # Record play count
            if hasattr(repos, 'tracks') and hasattr(repos.tracks, 'record_play'):
                repos.tracks.record_play(track_id)
            else:
                # Fallback to LibraryManager for backward compatibility
                self.library.record_track_play(track_id)

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
            if track.recommended_reference and os.path.exists(track.recommended_reference):
                if self.file_manager.load_reference(cast(str, track.recommended_reference)):
                    info(f"Using recommended reference: {track.recommended_reference}")
                    self._notify_callbacks({
                        'action': 'reference_loaded',
                        'reference_file': track.recommended_reference
                    })
                    return

            # Find and try similar tracks as references
            repos = self._get_repos()
            references = []

            if hasattr(repos, 'tracks') and hasattr(repos.tracks, 'find_similar'):
                references, _ = repos.tracks.find_similar(track, limit=3)
            else:
                # Fallback to LibraryManager for backward compatibility
                references = self.library.find_reference_tracks(track, limit=3)

            for ref_track in references:
                if os.path.exists(cast(str, ref_track.filepath)):
                    if self.file_manager.load_reference(cast(str, ref_track.filepath)):
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

    def get_playback_info(self) -> Dict[str, Any]:
        """Get comprehensive playback information"""
        queue_info = self.queue.get_queue_info()

        return {
            'playback': {
                'state': self.playback.state.value,
                'position_seconds': self._get_position_seconds(),
                'duration_seconds': self.file_manager.get_duration(),
                'current_file': self.file_manager.current_file,
                'is_playing': self.playback.is_playing(),
            },
            'queue': queue_info,
            'library': {
                'current_track': self.current_track.to_dict() if self.current_track else None,
                'auto_reference_selection': self.auto_reference_selection,
                'database_path': self.library.database_path,
            },
            'processing': self.processor.get_processing_info(),
            'session': {
                'tracks_played': self.tracks_played,
                'session_duration': time.time() - self.session_start_time,
                'total_play_time': self.total_play_time,
            },
        }

    def record_track_completion(self) -> None:
        """Record that current track completed"""
        self.tracks_played += 1
        self._notify_callbacks({
            'action': 'track_completed',
            'tracks_played': self.tracks_played
        })

    def _get_position_seconds(self) -> float:
        """Get current playback position in seconds"""
        if self.file_manager.audio_data is None:
            return 0.0
        return self.playback.position / self.file_manager.sample_rate

    def cleanup(self) -> None:
        """Clean up resources"""
        self.processor.reset_all_effects()
        info("IntegrationManager cleaned up")
