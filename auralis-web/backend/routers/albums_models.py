"""
Albums router response bodies (split from albums.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pydantic import BaseModel, Field
from schemas import FingerprintVectorResponse, TrackResponse


class AlbumTracksResponse(BaseModel):
    """Track listing for one album, in the snake_case shape its consumer expects.

    Deliberately snake_case while the sibling `GET /api/albums/{id}` is
    camelCase — `useAlbumDetails.ts` reads the album-level keys directly here
    and runs `tracks` through the frontend's canonical `transformTracks()`
    (#4568).
    """
    album_id: int = Field(description="Album database ID")
    album_title: str | None = Field(default=None, description="Album title")
    artist: str | None = Field(default=None, description="Album artist name, or null when the album has none")
    year: int | None = Field(default=None, description="Release year")
    genre: str | None = Field(
        default=None,
        description=(
            "Most common genre across the album's tracks, or None if no track "
            "is tagged. Derived, not stored — Album has no genre column (#5170)."
        ),
    )
    artwork_url: str | None = Field(default=None, description="Artwork API URL")
    tracks: list[TrackResponse] = Field(
        default_factory=list,
        description="Tracks ordered by disc number then track number",
    )
    total_tracks: int = Field(description="Number of tracks returned")


class AlbumFingerprintResponse(BaseModel):
    """Median 25D fingerprint aggregated across an album's fingerprinted tracks.

    `fingerprint` keys are the API-side dimension names, which differ from the
    DB column names for five dimensions (#2477) — see `_DB_TO_API` in albums_fingerprint.py.
    """
    album_id: int = Field(description="Album database ID")
    album_title: str | None = Field(default=None, description="Album title")
    track_count: int = Field(description="Total tracks in the album")
    fingerprinted_track_count: int = Field(description="Tracks that actually had a fingerprint")
    fingerprint: FingerprintVectorResponse = Field(
        default_factory=FingerprintVectorResponse,
        description="Median value per fingerprint dimension (25 entries)",
    )


class AlbumFingerprintEntry(BaseModel):
    """One album of ``GET /api/albums/fingerprints``."""
    album_id: int = Field(description="Album database ID")
    fingerprinted_track_count: int = Field(description="Tracks that actually had a fingerprint")
    fingerprint: FingerprintVectorResponse = Field(
        default_factory=FingerprintVectorResponse,
        description="Median value per fingerprint dimension (25 entries)",
    )


class AlbumFingerprintsResponse(BaseModel):
    """Batch album fingerprints (#5873). Requested albums with no fingerprinted
    track are absent, not 404s."""
    albums: list[AlbumFingerprintEntry] = Field(default_factory=list)
