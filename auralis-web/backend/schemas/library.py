"""
Library Schemas

Library scan request/result and the library domain response models
(#3838). Split out of schemas.py (#5479).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LibraryScanRequest(BaseModel):
    """Library scan request (POST /api/library/scan)."""
    directories: list[str] = Field(description="List of directory paths to scan")
    recursive: bool = Field(default=True, description="Whether to scan subdirectories")
    skip_existing: bool = Field(default=True, description="Skip files already in library")

    @field_validator('directories')
    @classmethod
    def validate_directory_paths(cls, v: list[str]) -> list[str]:
        """Validate all directory paths to prevent path traversal.

        Shared with PUT /api/settings' scan_folders handling via
        validate_directory_list (#4765) — see its docstring.
        """
        from security.path_security import PathValidationError, validate_directory_list

        try:
            return validate_directory_list(v)
        except PathValidationError as e:
            raise ValueError(str(e))

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "directories": ["/home/user/Music"],
            "recursive": True,
            "skip_existing": True
        }
    })


class ScanResultResponse(BaseModel):
    """Library scan result (POST /api/library/scan).

    Field name `duration` mirrors the paired `scan_complete` WebSocket
    broadcast (fixes #3839 — REST previously returned the same value under
    a different key, `scan_time`).
    """
    files_found: int
    files_added: int
    files_updated: int
    files_skipped: int
    files_failed: int
    duration: float
    directories_scanned: int
    # #4841: a bounded list of {filename, reason} for the files that failed
    # (a bare name, never the absolute path, #5341).
    # `files_failed` stays the exact count; this names the first N so the UI can
    # tell the user *which* files to look at instead of only how many.
    failures: list[dict[str, str]] = Field(default_factory=list)


# ============================================================================
# Library Domain Response Models (#3838)
# ============================================================================
#
# These mirror what the API actually emits, which is the union of two shapes:
# the ORM `Model.to_dict()` (preferred by `routers/serializers.serialize_object`)
# and the `DEFAULT_*_FIELDS` getattr fallback it uses for Mocks and detached
# objects. Both paths are live, and they do NOT agree — `DEFAULT_TRACK_FIELDS`
# carries `artist`/`genre`/`date_added`/`date_modified`, which `Track.to_dict()`
# never emits, while `to_dict()` carries a dozen analysis fields the fallback
# omits. A `response_model` FILTERS anything it does not declare, so a model
# built from only one of the two would silently delete fields from responses.
# `tests/backend/test_response_model_coverage.py` pins the union mechanically.
#
# Every field is optional with a default for the same reason: `Track.to_dict()`
# has an except-branch that returns only 11 of its 36 keys for a detached
# instance, and a required field missing from the payload is a 500, not a
# degraded response.


class TrackResponse(BaseModel):
    """A serialized library track (`serializers.serialize_tracks`).

    `filepath` is deliberately absent — #3205 made the server-side path
    server-only, and neither serialization path emits it.
    """

    # Core identity
    id: int | None = Field(default=None, description="Track database ID")
    title: str | None = Field(default=None, description="Track title")
    duration: float | None = Field(default=None, description="Duration in seconds")

    # Audio format
    sample_rate: int | None = Field(default=None, description="Sample rate in Hz")
    bit_depth: int | None = Field(default=None, description="Bit depth")
    bitrate: int | None = Field(default=None, description="Bitrate in kbps")
    channels: int | None = Field(default=None, description="Channel count")
    format: str | None = Field(default=None, description="Container/codec format")
    filesize: int | None = Field(default=None, description="File size in bytes")

    # Audio analysis
    peak_level: float | None = Field(default=None, description="Peak level")
    rms_level: float | None = Field(default=None, description="RMS level")
    dr_rating: float | None = Field(default=None, description="Dynamic range rating")
    lufs_level: float | None = Field(default=None, description="Integrated loudness (LUFS)")
    mastering_quality: float | None = Field(default=None, description="Quality score (0–1)")
    loudness: float | None = Field(default=None, description="Loudness (fallback path)")
    recommended_reference: str | None = Field(default=None, description="Best reference track")
    processing_profile: str | None = Field(default=None, description="Optimal mastering profile")

    # Metadata / navigation
    album_id: int | None = Field(default=None, description="Owning album ID")
    album: str | None = Field(default=None, description="Album title")
    artist: str | None = Field(default=None, description="Primary artist name (fallback path)")
    artists: list[str] = Field(default_factory=list, description="All artist names")
    genre: str | None = Field(default=None, description="Primary genre name (fallback path)")
    genres: list[str] = Field(default_factory=list, description="All genre names")
    track_number: int | None = Field(default=None, description="Track number within the disc")
    disc_number: int | None = Field(default=None, description="Disc number")
    year: int | None = Field(default=None, description="Release year")
    comments: str | None = Field(default=None, description="Free-text comments")
    lyrics: str | None = Field(default=None, description="Plain-text or LRC lyrics")
    artwork_url: str | None = Field(default=None, description="Album artwork API URL")

    # Playback statistics
    play_count: int | None = Field(default=None, description="Times played")
    last_played: str | None = Field(default=None, description="Last play timestamp (ISO 8601)")
    skip_count: int | None = Field(default=None, description="Times skipped")
    favorite: bool = Field(default=False, description="Favorite flag")

    # Timestamps. `created_at`/`updated_at` come from to_dict(); the
    # `date_added`/`date_modified` aliases come from the getattr fallback.
    created_at: str | None = Field(default=None, description="Row creation timestamp (ISO 8601)")
    updated_at: str | None = Field(default=None, description="Row update timestamp (ISO 8601)")
    date_added: str | None = Field(default=None, description="Alias of created_at (fallback path)")
    date_modified: str | None = Field(default=None, description="Alias of updated_at (fallback path)")


class TrackListResponse(BaseModel):
    """Paginated track listing."""
    tracks: list[TrackResponse] = Field(default_factory=list, description="Tracks in this page")
    total: int = Field(description="Total matching tracks in the library")
    limit: int = Field(description="Requested page size")
    offset: int = Field(description="Number of tracks skipped")
    has_more: bool = Field(description="True when further pages exist")


class AlbumResponse(BaseModel):
    """A serialized album in the snake_case listing shape.

    `serialize_album` normalizes `artwork_url` to an API URL so internal
    filesystem paths are never leaked (#2270).
    """
    id: int | None = Field(default=None, description="Album database ID")
    title: str | None = Field(default=None, description="Album title")
    artist: str | None = Field(default=None, description="Album artist name")
    artist_id: int | None = Field(default=None, description="Album artist ID")
    year: int | None = Field(default=None, description="Release year")
    total_tracks: int | None = Field(default=None, description="Track count declared by tags")
    total_discs: int | None = Field(default=None, description="Disc count declared by tags")
    artwork_url: str | None = Field(default=None, description="Artwork API URL")
    avg_dr_rating: float | None = Field(default=None, description="Mean dynamic-range rating")
    avg_lufs: float | None = Field(default=None, description="Mean integrated loudness")
    mastering_consistency: float | None = Field(default=None, description="Mastering consistency score")
    track_count: int | None = Field(default=None, description="Actual number of tracks held")
    total_duration: float | None = Field(default=None, description="Summed track duration in seconds")
    created_at: str | None = Field(default=None, description="Row creation timestamp (ISO 8601)")
    updated_at: str | None = Field(default=None, description="Row update timestamp (ISO 8601)")


class AlbumListResponse(BaseModel):
    """Paginated album listing."""
    albums: list[AlbumResponse] = Field(default_factory=list, description="Albums in this page")
    total: int = Field(description="Total matching albums in the library")
    limit: int = Field(description="Requested page size")
    offset: int = Field(description="Number of albums skipped")
    has_more: bool = Field(description="True when further pages exist")


class PlaylistResponse(BaseModel):
    """A serialized playlist (`serializers.serialize_playlist`)."""
    id: int | None = Field(default=None, description="Playlist database ID")
    name: str | None = Field(default=None, description="Playlist name")
    description: str | None = Field(default=None, description="Playlist description")
    is_smart: bool = Field(default=False, description="True for rule-driven smart playlists")
    smart_criteria: str | None = Field(default=None, description="Smart-playlist rules (JSON string)")
    auto_master_enabled: bool | None = Field(default=None, description="Auto-mastering enabled")
    mastering_profile: str | None = Field(default=None, description="Playlist mastering profile")
    normalize_levels: bool | None = Field(default=None, description="Level normalization enabled")
    track_count: int | None = Field(default=None, description="Number of tracks held")
    total_duration: float | None = Field(default=None, description="Summed track duration in seconds")
    created_at: str | None = Field(default=None, description="Creation timestamp (ISO 8601)")
    updated_at: str | None = Field(default=None, description="Update timestamp (ISO 8601)")


class FingerprintVectorResponse(BaseModel):
    """The 25-dimensional audio fingerprint, in API field names.

    Five dimensions are renamed relative to their `TrackFingerprint` DB
    columns — `pitch_stability`→`pitch_confidence`,
    `chroma_energy`→`chroma_energy_mean`,
    `phase_correlation`→`stereo_correlation`, and the seven `*_pct` frequency
    bands drop the suffix. Both the per-track and the album-median endpoints
    emit this exact key set, so they share one model (#2477 is precisely the
    bug where they did not).
    """
    # 7D frequency distribution
    sub_bass: float | None = Field(default=None, description="Sub-bass energy share")
    bass: float | None = Field(default=None, description="Bass energy share")
    low_mid: float | None = Field(default=None, description="Low-mid energy share")
    mid: float | None = Field(default=None, description="Mid energy share")
    upper_mid: float | None = Field(default=None, description="Upper-mid energy share")
    presence: float | None = Field(default=None, description="Presence energy share")
    air: float | None = Field(default=None, description="Air energy share")
    # 3D loudness / dynamics
    lufs: float | None = Field(default=None, description="Integrated loudness (LUFS)")
    crest_db: float | None = Field(default=None, description="Crest factor (dB)")
    bass_mid_ratio: float | None = Field(default=None, description="Bass-to-mid energy ratio")
    # 4D temporal
    tempo_bpm: float | None = Field(default=None, description="Tempo (BPM)")
    rhythm_stability: float | None = Field(default=None, description="Rhythm stability")
    transient_density: float | None = Field(default=None, description="Transient density")
    silence_ratio: float | None = Field(default=None, description="Fraction of near-silence")
    # 3D spectral shape
    spectral_centroid: float | None = Field(default=None, description="Spectral centroid (Hz)")
    spectral_rolloff: float | None = Field(default=None, description="Spectral rolloff (Hz)")
    spectral_flatness: float | None = Field(default=None, description="Spectral flatness")
    # 3D harmonic content
    harmonic_ratio: float | None = Field(default=None, description="Harmonic-to-percussive ratio")
    pitch_confidence: float | None = Field(default=None, description="Pitch stability (DB: pitch_stability)")
    chroma_energy_mean: float | None = Field(default=None, description="Mean chroma energy (DB: chroma_energy)")
    # 3D dynamics variation
    dynamic_range_variation: float | None = Field(default=None, description="Dynamic-range variation")
    loudness_variation_std: float | None = Field(default=None, description="Loudness variation (std dev)")
    peak_consistency: float | None = Field(default=None, description="Peak consistency")
    # 2D stereo
    stereo_width: float | None = Field(default=None, description="Stereo width")
    stereo_correlation: float | None = Field(default=None, description="Phase correlation (DB: phase_correlation)")
