"""
Artwork router response bodies (split from artwork.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pydantic import BaseModel, Field


class ArtworkExtractResponse(BaseModel):
    """Result of extracting embedded artwork from an album's tracks."""
    message: str = Field(description="Human-readable confirmation")
    artwork_url: str = Field(description="Artwork API URL, never a filesystem path (#2508)")
    album_id: int = Field(description="Album that was updated")


class ArtworkDeleteResponse(BaseModel):
    """Result of deleting album artwork.

    Idempotent per RFC 7231 §4.3.5: a repeat call after a successful delete
    still returns 200 (#3563).
    """
    message: str = Field(description="Human-readable confirmation")
    album_id: int = Field(description="Album that was updated")


class ArtworkDownloadResponse(BaseModel):
    """Result of downloading album artwork from an online source."""
    message: str = Field(description="Human-readable confirmation")
    artwork_url: str = Field(description="Artwork API URL, never a filesystem path")
    album_id: int = Field(description="Album that was updated")
    artist: str = Field(description="Artist name used for the lookup")
    album: str | None = Field(default=None, description="Album name used for the lookup")
