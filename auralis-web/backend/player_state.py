"""
Unified Player State Schema
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Single source of truth for player state shared between backend and frontend.
This ensures consistency across WebSocket and REST endpoints.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel


class PlaybackState(str, Enum):
    """Playback state enumeration"""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    LOADING = "loading"
    ERROR = "error"


class TrackInfo(BaseModel):
    """Track information for frontend display"""
    id: int
    title: str
    artist: str
    album: str
    duration: float
    file_path: str
    album_art: str | None = None
    is_enhanced: bool = False


class PlayerState(BaseModel):
    """Complete player state - single source of truth"""
    # Playback state
    state: PlaybackState = PlaybackState.STOPPED
    is_playing: bool = False
    is_paused: bool = False

    # Current track
    current_track: TrackInfo | None = None

    # Playback position
    current_time: float = 0.0
    duration: float = 0.0

    # Audio controls
    volume: int = 80
    is_muted: bool = False

    # Queue management
    queue: list[TrackInfo] = []
    queue_index: int = 0
    queue_size: int = 0

    # Playback modes
    shuffle_enabled: bool = False
    repeat_mode: str = "none"  # "none", "one", "all"

    # Enhancement
    mastering_enabled: bool = True
    current_preset: str = "adaptive"

    # Real-time analysis (optional)
    analysis: dict[str, Any] | None = None


def create_track_info(track: Any) -> TrackInfo | None:
    """
    Convert a Track model to TrackInfo DTO

    Args:
        track: Track model from database

    Returns:
        TrackInfo or None if track is None
    """
    if not track:
        return None

    # Get artist name (handle relationship)
    artist_name = "Unknown Artist"
    if hasattr(track, 'artists') and track.artists:
        artist_name = track.artists[0].name
    elif hasattr(track, 'artist') and track.artist:
        artist_name = track.artist

    # Get album name
    album_name = "Unknown Album"
    if hasattr(track, 'album') and track.album:
        if hasattr(track.album, 'title'):
            album_name = track.album.title
        elif isinstance(track.album, str):
            album_name = track.album

    return TrackInfo(
        id=track.id,
        title=track.title or "Unknown Title",
        artist=artist_name,
        album=album_name,
        duration=track.duration or 0.0,
        file_path=track.filepath,
        album_art=None,  # TODO: Implement album art
        is_enhanced=False
    )
