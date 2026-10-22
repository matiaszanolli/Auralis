"""
Library-backed track loading for IntegrationManager (split from
integration_manager.py, #5836): load by id, record the play, and auto-select a
reference.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from ..library.models import Track
from ..utils.logging import error, info, warning
from .audio_file_manager import AudioFileManager
from .repository_access import resolve_repository_factory


class LibraryLoadingMixin:
    """Loads library tracks; the state and callbacks live on IntegrationManager."""

    file_manager: AudioFileManager
    processor: Any
    get_repository_factory: Callable[[], Any]
    auto_reference_selection: bool

    def set_current_track(self, track: "Track | None") -> None:
        raise NotImplementedError

    def _notify_callbacks(self, state_info: dict[str, Any]) -> None:
        raise NotImplementedError

    def _get_repos(self) -> Any:
        """Get repository factory for data access."""
        return resolve_repository_factory(self.get_repository_factory)

    def load_track_from_library(
        self, track_id: int, on_loaded: Callable[[], None] | None = None
    ) -> bool:
        """
        Load a track from the library by ID.

        Args:
            track_id: Database ID of track
            on_loaded: Optional callback forwarded to
                ``file_manager.load_file`` so the caller's playback-state
                reset runs inside the buffer-swap critical section (#5581).

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
            if not self.file_manager.load_file(
                cast(str, track.filepath), on_loaded=on_loaded
            ):
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
                ref_data = self.file_manager.load_reference(track.recommended_reference)
                if ref_data is not None:
                    # #5585: wire the audio into the processor exactly as the
                    # explicit load_reference path does. Without this the
                    # decode fed only the broadcast — the real-time level
                    # matcher (enabled solely by set_reference_audio) stayed
                    # off and file_manager.reference_data had no consumer.
                    self.processor.set_reference_audio(ref_data)
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
                    ref_data = self.file_manager.load_reference(cast(str, ref_track.filepath))
                    if ref_data is not None:
                        # #5585: same wiring as the recommended-reference
                        # branch above.
                        self.processor.set_reference_audio(ref_data)
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
