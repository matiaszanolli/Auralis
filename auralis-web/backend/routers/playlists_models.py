"""
Playlist router limits and request/response bodies (split from playlists.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pydantic import BaseModel, Field
from schemas import PlaylistResponse, QueueIndex, TrackId, TrackIdList, TrackResponse


#: Playlist names and descriptions are free text but not unbounded — a name is
#: a label, not a payload, and the column behind it is a plain String.
MAX_PLAYLIST_NAME = 255


MAX_PLAYLIST_DESCRIPTION = 4096


class CreatePlaylistRequest(BaseModel):
    """Request model for creating a playlist"""
    name: str = Field(min_length=1, max_length=MAX_PLAYLIST_NAME)
    description: str = Field(default="", max_length=MAX_PLAYLIST_DESCRIPTION)
    track_ids: TrackIdList = []


class UpdatePlaylistRequest(BaseModel):
    """Request model for updating a playlist"""
    name: str | None = Field(default=None, min_length=1, max_length=MAX_PLAYLIST_NAME)
    description: str | None = Field(default=None, max_length=MAX_PLAYLIST_DESCRIPTION)


class AddTracksRequest(BaseModel):
    """Request model for adding tracks to playlist"""
    track_ids: TrackIdList


class AddTrackRequest(BaseModel):
    """Request model for adding a single track at an explicit position (#4658).

    Distinct from :class:`AddTracksRequest`: the batch route assigns positions
    by appending, which cannot express "drop this track at index N" — the
    operation drag-and-drop actually performs.
    """
    track_id: TrackId
    position: QueueIndex | None = None


class ReorderTrackRequest(BaseModel):
    """Request model for reordering a track within a playlist (#4658)."""
    from_index: QueueIndex
    to_index: QueueIndex


class PlaylistListResponse(BaseModel):
    """Paginated playlist listing."""
    playlists: list[PlaylistResponse] = Field(default_factory=list, description="Playlists in this page")
    total: int = Field(description="Total playlists in the library")
    limit: int = Field(description="Requested page size")
    offset: int = Field(description="Number of playlists skipped")
    has_more: bool = Field(description="True when further pages exist")


class PlaylistDetailResponse(PlaylistResponse):
    """A single playlist with its full track list.

    Extends :class:`PlaylistResponse` rather than redeclaring it, so the
    detail route cannot drift from the listing shape. `tracks` comes from
    `Track.to_dict()` directly here, not `serialize_tracks`.
    """
    tracks: list[TrackResponse] = Field(
        default_factory=list,
        description="Tracks in playlist order (association-table `position`)",
    )


class PlaylistMessageResponse(BaseModel):
    """Bare confirmation returned by the mutating playlist routes."""
    message: str = Field(description="Human-readable confirmation")


class CreatePlaylistResponse(BaseModel):
    """Result of creating a playlist."""
    message: str = Field(description="Human-readable confirmation")
    playlist: PlaylistResponse = Field(description="The newly created playlist")


class AddTracksResponse(BaseModel):
    """Result of a batch track add."""
    message: str = Field(description="Human-readable confirmation")
    added_count: int = Field(description="Number of tracks actually added")
