"""
Unified Player State Schema
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Single source of truth for player state shared between backend and frontend.
This ensures consistency across WebSocket and REST endpoints.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from auralis.player.playback_controller import PlaybackState as PlaybackState  # re-exported: one enum for engine and wire
from schemas import DEFAULT_PRESET, EnhancementPresetLiteral


# Minted once per backend process (#5487). The session itself (queue, current
# track, position) lives only in memory, so a restart hands a reconnecting
# client an empty snapshot; a changed id is how the client tells that apart
# from "nothing was playing".
SERVER_INSTANCE_ID: str = uuid.uuid4().hex


class TrackInfo(BaseModel):
    """Track information for frontend display.

    Field names match the REST serializer (routers/serializers.py) and
    the frontend TrackInfo type in src/types/websocket.ts:
      - `filepath` (not file_path)
      - `artwork_url` (not album_art)
    There is deliberately no `is_enhanced` field: nothing ever set it true
    and the frontend type never carried it (#3505 / BE-NEW-47).
    """
    id: int
    title: str
    # One shape with the library's TrackResponse (#6508): every artist, and no sentinel strings; the
    # "Unknown ..." labels belong to the frontend (#5905). `artist` is the joined display string,
    # kept for the clients that read it ("" when there is none).
    artists: list[str] = Field(default_factory=list)
    artist: str
    album: str | None = None
    duration: float
    # Server-only; excluded from API responses (#3205)
    filepath: str = Field(exclude=True)
    artwork_url: str | None = None
    # Audio container/codec (e.g. "flac", "mp3"). #4586: the frontend queue
    # utilities want the *format*, and used to derive it by parsing `filepath`
    # — which #3205 deliberately withholds, so they always fell back to
    # "unknown" for every queue-sourced track. Shipping the format explicitly
    # gives them the data without leaking a server path.
    format: str | None = None
    # The album the artwork belongs to (#6586). Sent even without artwork: a track whose album gains
    # art later (artwork_updated) can only build the URL from it.
    album_id: int | None = None


class PlayerState(BaseModel):
    """Complete player state - single source of truth"""
    # Monotonic broadcast sequence number (fixes #3732). update_state()
    # broadcasts outside its lock so concurrent calls can deliver WS
    # messages out of order; the frontend drops snapshots with
    # seq < last-seen instead of relying on in-order delivery.
    seq: int = 0

    # Identifies the backend process that produced this snapshot (#5487).
    server_instance_id: str = SERVER_INSTANCE_ID

    # Playback state
    state: PlaybackState = PlaybackState.STOPPED
    is_playing: bool = False
    is_paused: bool = False

    # Current track
    current_track: TrackInfo | None = None

    # Playback position
    current_time: float = 0.0
    duration: float = 0.0

    # Audio controls. 0-100, matching SetVolumeRequest and the WS broadcast the
    # frontend reads — NOT the normalised 0.0-1.0 scale that
    # SettingsUpdateRequest.volume and the persisted UserSettings.volume column
    # use under the same field name (#4711). Anything bridging settings volume
    # into player volume (or back) needs a x100 / ÷100.
    volume: int = Field(default=80, description="Playback volume on a 0-100 scale.")
    is_muted: bool = False

    # Queue management
    queue: list[TrackInfo] = []
    queue_index: int = 0
    queue_size: int = 0

    # Playback modes
    shuffle_enabled: bool = False
    # repeat_mode uses the frontend's vocabulary ('off' | 'one' | 'all').
    # Prior code stored 'none' here and translated 'off' -> 'none' at the
    # REST boundary, but the broadcast still carried 'none' which the
    # frontend Literal does not recognise — the UI toggle got stuck (#3501).
    # Typed as the closed set rather than `str` (#4710) so it drives OpenAPI
    # and matches RepeatModeRequest.mode, which already uses this Literal.
    # Note this constrains construction only: PlayerStateManager._mutate_state
    # assigns via setattr and the model does not set validate_assignment, so
    # this is a documented contract rather than a runtime gate.
    repeat_mode: Literal["off", "one", "all"] = "off"

    # Enhancement
    mastering_enabled: bool = True
    # #4424 made EnhancementPresetLiteral the single source of truth; the
    # response side was migrated in #4710. Same setattr caveat as above.
    current_preset: EnhancementPresetLiteral = DEFAULT_PRESET

    # Real-time analysis (optional)
    analysis: dict[str, Any] | None = None


def track_artist_names(track: Any) -> list[str]:
    """Every artist of a Track row (or a plain ``artist`` string), in order; [] when there is none (#6508)."""
    artists = getattr(track, 'artists', None)
    if artists:
        return [a.name for a in artists if getattr(a, 'name', None)]
    artist = getattr(track, 'artist', None)
    return [artist] if isinstance(artist, str) and artist else []


def track_album_title(track: Any) -> str | None:
    """The album title of a Track row (or a plain ``album`` string); None when there is none (#6508)."""
    album = getattr(track, 'album', None)
    if isinstance(album, str):
        return album or None
    title = getattr(album, 'title', None) if album is not None else None
    return title if isinstance(title, str) and title else None


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

    artist_names = track_artist_names(track)
    album_name = track_album_title(track)

    # Audio format (#4586). Coerce anything that isn't a real string to None:
    # `getattr` on a Mock auto-creates a Mock attribute, and other callers pass
    # partially-populated rows — neither should fail TrackInfo validation over
    # a purely informational field.
    raw_format = getattr(track, 'format', None)
    track_format = raw_format if isinstance(raw_format, str) else None

    # Build artwork URL from album ID
    album_art_url: str | None = None
    album_id = getattr(track, 'album_id', None)
    album = getattr(track, 'album', None)
    if not album_id and album and not isinstance(album, str) and hasattr(album, 'id'):
        album_id = album.id
    if not isinstance(album_id, int):  # a Mock or partial row, as for `format` above
        album_id = None
    if album_id and getattr(album, 'artwork_path', None):
        album_art_url = f"/api/albums/{album_id}/artwork"

    return TrackInfo(
        id=track.id,
        title=track.title or "Unknown Title",
        artists=artist_names,
        artist=", ".join(artist_names),
        album=album_name,
        duration=track.duration or 0.0,
        filepath=track.filepath,
        artwork_url=album_art_url,
        format=track_format,
        album_id=album_id,
    )
