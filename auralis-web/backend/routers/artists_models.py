"""
Artists router response bodies (split from artists.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pydantic import BaseModel


# Response models
class ArtistResponse(BaseModel):
    """Artist information response.

    Covers the key set of `Artist.to_dict()`, which `serialize_artist()`
    returns. The five fields below the
    artwork pair were missing until #3838: `response_model` filters anything
    it does not declare, so `/api/artists` was silently stripping them from
    every response with no error and no log line. Pinned by
    `tests/backend/test_response_model_coverage.py`.
    """
    id: int
    name: str
    album_count: int
    track_count: int
    genres: list[str] | None = None
    artwork_url: str | None = None  # Phase 2: Artist artwork
    artwork_source: str | None = None  # Source: 'musicbrainz', 'discogs', etc.
    normalized_name: str | None = None  # Canonical form used for duplicate detection
    total_plays: int | None = None
    avg_mastering_quality: float | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ArtistsListResponse(BaseModel):
    """Paginated artists list response"""
    artists: list[ArtistResponse]
    total: int
    offset: int
    limit: int
    has_more: bool


class TrackInArtist(BaseModel):
    """Track information in artist context"""
    id: int
    title: str
    # null for a track with no album, as on every other track-shaped
    # response (#5905, #5049).
    album: str | None = None
    album_id: int | None = None
    duration: float
    track_number: int | None = None
    disc_number: int | None = None
    # #4586: every other track-returning endpoint ships `format` (it is in
    # Track.to_dict()); this model was the one that did not, so
    # artist-sourced queue entries lost format-aware handling.
    format: str | None = None


class AlbumInArtist(BaseModel):
    """Album information in artist context"""
    id: int
    title: str
    year: int | None = None
    track_count: int
    total_duration: float


class ArtistDetailResponse(BaseModel):
    """Detailed artist information with albums and tracks"""
    id: int
    name: str
    albums: list[AlbumInArtist]
    total_albums: int
    total_tracks: int
    artwork_url: str | None = None  # Phase 2: Artist artwork
    artwork_source: str | None = None  # Source: 'musicbrainz', 'discogs', etc.


class ArtistTracksResponse(BaseModel):
    """Artist's tracks response"""
    id: int
    name: str
    tracks: list[TrackInArtist]
    total_tracks: int
