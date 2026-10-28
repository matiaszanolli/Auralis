"""
Library router response models (split from library.py, #5832).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pydantic import BaseModel, Field


class RefreshReferencesResponse(BaseModel):
    """Result of rebuilding the mastering reference cloud (#3479)."""
    cleared: int = Field(description="Existing is_reference flags cleared")
    selected: int = Field(description="Fingerprints newly flagged as references")


class LibraryStatsResponse(BaseModel):
    """Library-wide statistics (`StatsRepository.get_library_stats`).

    `average_dr` is the one dynamic-range average (the `avg_dr_rating` twin had no reader,
    #6288). There is no loudness average: tracks never carried one (#5755).

    Every counter carries a default even though the repository always
    populates all of them. A `response_model` validates as well as filters, so
    required fields would turn any partial payload — a stub repository, a
    future query that stops computing one aggregate — into a 500 with an empty
    body. Defaulting degrades to zero instead, matching the
    `_safe_collection`/`_safe_scalar` posture the ORM layer already takes, and
    the OpenAPI schema is equally complete either way.
    """
    total_tracks: int = Field(default=0, description="Number of tracks")
    total_albums: int = Field(default=0, description="Number of albums")
    total_artists: int = Field(default=0, description="Number of artists")
    total_genres: int = Field(default=0, description="Number of genres")
    total_playlists: int = Field(default=0, description="Number of playlists")
    total_duration: float = Field(default=0.0, description="Summed track duration in seconds")
    total_duration_formatted: str = Field(default="", description="Human-readable total duration")
    total_filesize: int = Field(default=0, description="Summed file size in bytes")
    total_filesize_gb: float = Field(default=0.0, description="Summed file size in GB (2 dp)")
    total_plays: int = Field(default=0, description="Summed play count")
    favorite_count: int = Field(default=0, description="Number of favorited tracks")
    average_dr: float | None = Field(default=None, description="Mean dynamic-range rating")


class LibraryResetResponse(BaseModel):
    """Confirmation returned by the destructive library reset."""
    message: str = Field(description="Human-readable confirmation")
