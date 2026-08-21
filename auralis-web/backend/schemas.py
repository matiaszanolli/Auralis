"""
Standardized Request/Response Schemas
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Defines Pydantic models for all API request/response payloads.
Ensures consistent structure across all endpoints.

Phase B.1: Backend Endpoint Standardization

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ============================================================================
# Enhancement presets — single source of truth (#4424)
# ============================================================================

# Canonical list/Literal of valid enhancement presets. Every validating surface
# (enhancement router, settings PUT, WS playback commands) imports these rather
# than re-declaring an inline copy, so the definitions cannot drift apart.
VALID_PRESETS = ["adaptive", "gentle", "warm", "bright", "punchy"]
EnhancementPresetLiteral = Literal["adaptive", "gentle", "warm", "bright", "punchy"]

# Canonical constraint for enhancement intensity (#4600). The same quantity used
# to be validated three different ways: the enhancement router silently CLAMPED
# and returned 200 with a value the caller never sent, the settings route
# rejected with 422, and the WS path silently discarded and fell back to the
# stored value. The clamp was the dangerous one — `max(0.0, min(1.0, nan))` is
# `1.0`, not `nan` (because `nan < 1.0` is False), so a NaN intensity became
# MAXIMUM enhancement and was written into the runtime settings dict.
#
# `ge`/`le` reject NaN and ±inf for free: every comparison against NaN is False,
# and inf fails the bound. Both REST surfaces now import this, matching how
# `preset` was unified in #4424.
EnhancementIntensity = Annotated[float, Field(ge=0.0, le=1.0)]

# Bounds as plain numbers, for the non-Pydantic surfaces (the WS command handler)
# that need the same range check without a model.
INTENSITY_MIN = 0.0
INTENSITY_MAX = 1.0


def is_valid_intensity(value: Any) -> bool:
    """True when ``value`` is a real number inside the canonical range.

    Shared by the WebSocket path so its bounds cannot drift from the REST
    models'. Rejects NaN and ±inf: the comparison chain is False for NaN, and
    inf fails the upper bound.
    """
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and INTENSITY_MIN <= value <= INTENSITY_MAX
    )


# ============================================================================
# WebSocket Message Models (Security: #2156)
# ============================================================================

class WebSocketMessageType(str, Enum):
    """Inbound WebSocket message types (client -> server).

    NOTE: despite the bare name, this enum enumerates ONLY the subset of
    types that the server validates on the receive path
    (websocket_security.py:187). Outbound (server -> client) types are
    NOT listed here — they live in the frontend's WebSocketMessageType
    Literal in src/types/websocket.ts. Renaming is deferred to avoid
    churn in callers; the docstring is the authoritative scope statement
    (#3551 / BE-NEW-93).
    """
    PING = "ping"
    PONG = "pong"
    HEARTBEAT = "heartbeat"
    # processing_settings_* and ab_track_* removed (#4421): dead both
    # directions — the frontend never sent the inbound types nor subscribed
    # to the outbound ones, and the handlers were never triggered.
    PLAY_ENHANCED = "play_enhanced"
    PLAY_NORMAL = "play_normal"
    PAUSE = "pause"
    STOP = "stop"
    SEEK = "seek"
    SEEK_STARTED = "seek_started"
    SUBSCRIBE_JOB_PROGRESS = "subscribe_job_progress"
    JOB_PROGRESS = "job_progress"
    AUDIO_STREAM_ERROR = "audio_stream_error"
    RESUME = "resume"
    BUFFER_FULL = "buffer_full"
    BUFFER_READY = "buffer_ready"
    PLAYBACK_PAUSED = "playback_paused"
    PLAYBACK_RESUMED = "playback_resumed"
    PLAYBACK_STOPPED = "playback_stopped"
    PLAYER_STATE = "player_state"
    ENHANCEMENT_SETTINGS_CHANGED = "enhancement_settings_changed"


class WebSocketMessageBase(BaseModel):
    """Base WebSocket message with type validation.

    extra='allow' preserves protocol envelope fields sent by WebSocketProtocolClient
    (correlation_id, timestamp, priority, response_required, timeout_seconds) so that
    request-response correlation does not time out (fixes #2281).
    """
    type: WebSocketMessageType = Field(description="Message type")
    data: dict[str, Any] | None = Field(default=None, description="Message payload")

    model_config = ConfigDict(
        extra='allow',
        json_schema_extra={
            "example": {
                "type": "ping",
                "data": None
            }
        }
    )


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
    # #4841: a bounded list of {filepath, reason} for the files that failed.
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
    """A serialized library track (`serializers.serialize_track`).

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
    # Alias of updated_at kept for the frontend Playlist type (#2269).
    modified_at: str | None = Field(default=None, description="Alias of updated_at")


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


class WebSocketErrorResponse(BaseModel):
    """WebSocket error response."""
    type: str = Field(default="error", description="Message type")
    error: str = Field(description="Error code")
    message: str = Field(description="Human-readable error message")
    timestamp: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "type": "error",
            "error": "validation_error",
            "message": "Invalid message format",
            "timestamp": "2024-11-28T10:00:00Z"
        }
    })


# ============================================================================
# Request Parameter Models
# ============================================================================

class PaginationParams(BaseModel):
    """Standard pagination query parameters."""
    limit: int = Field(default=50, ge=1, le=500, description="Items per page (1–500)")
    offset: int = Field(default=0, ge=0, description="Number of items to skip")


# ============================================================================
# System / Health Response Models
# ============================================================================

# Typed response models for /api/health and /api/version (fixes #3863 / BE-RH-18).

class HealthResponse(BaseModel):
    """Response model for GET /api/health."""
    status: str = Field(description="Service status string (always 'healthy')")
    auralis_available: bool = Field(description="True when the Auralis audio engine is loaded")


class VersionInfoResponse(BaseModel):
    """Response model for GET /api/version (matches get_version_info() shape)."""
    version: str = Field(description="Full semantic version string (e.g. '1.2.1-beta.1')")
    major: int = Field(description="Major version number")
    minor: int = Field(description="Minor version number")
    patch: int = Field(description="Patch version number")
    prerelease: str = Field(default="", description="Pre-release identifier (empty for stable)")
    build: str = Field(default="", description="Build metadata (empty if not set)")
    build_date: str = Field(default="", description="Build date (ISO format)")
    git_commit: str = Field(default="", description="Git commit hash (empty if not set)")
    api_version: str = Field(default="v1", description="API version for compatibility")
    db_schema_version: int = Field(default=0, description="Database schema version")
    display: str = Field(description="User-friendly display version string")


# ============================================================================
# Cache Schemas (Phase B.2)
# ============================================================================

class TrackCacheStatusResponse(BaseModel):
    """Per-track cache status summary."""
    track_id: int = Field(description="Track identifier")
    total_chunks: int = Field(description="Total number of chunks for this track")
    cached_original: int = Field(description="Number of unprocessed chunks cached")
    cached_processed: int = Field(description="Number of processed chunks cached")
    completion_percent: float = Field(description="Overall cache completion percentage")
    fully_cached: bool = Field(description="Whether all chunks are cached")
    estimated_cache_time_seconds: float | None = Field(
        default=None,
        description="Estimated seconds until fully cached"
    )


class CacheTierStats(BaseModel):
    """Statistics for a single cache tier."""
    tier_name: str = Field(description="Tier identifier (e.g. 'tier1', 'tier2')")
    chunks: int = Field(description="Number of chunks stored in this tier")
    size_mb: float = Field(description="Total size of cached data in MB")
    hits: int = Field(description="Total cache hits")
    misses: int = Field(description="Total cache misses")
    hit_rate: float = Field(description="Cache hit rate (0–1)")


class OverallCacheStats(BaseModel):
    """Aggregate statistics across all cache tiers."""
    total_chunks: int = Field(description="Total chunks across all tiers")
    total_size_mb: float = Field(description="Total cached data size in MB")
    total_hits: int = Field(description="Total hits across all tiers")
    total_misses: int = Field(description="Total misses across all tiers")
    overall_hit_rate: float = Field(description="Combined hit rate (0–1)")
    tracks_cached: int = Field(description="Number of distinct tracks with cached data")


class CacheHealthResponse(BaseModel):
    """Cache subsystem health report."""
    healthy: bool = Field(description="Overall health indicator")
    tier1_size_mb: float = Field(description="Tier 1 (memory) size in MB")
    tier1_healthy: bool = Field(description="Tier 1 health indicator")
    tier2_size_mb: float = Field(description="Tier 2 (disk) size in MB")
    tier2_healthy: bool = Field(description="Tier 2 health indicator")
    total_size_mb: float = Field(description="Combined cache size in MB")
    memory_healthy: bool = Field(description="Memory pressure indicator")
    tier1_hit_rate: float = Field(description="Tier 1 hit rate (0–1)")
    overall_hit_rate: float = Field(description="Overall hit rate across all tiers (0–1)")


class CacheStatsResponse(BaseModel):
    """Full cache statistics response."""
    tier1: CacheTierStats = Field(description="Tier 1 (memory) statistics")
    tier2: CacheTierStats = Field(description="Tier 2 (disk) statistics")
    overall: OverallCacheStats = Field(description="Aggregate statistics")
    tracks: dict[int, Any] = Field(default_factory=dict, description="Per-track cache status")


# ============================================================================
# Mastering Recommendation
# ============================================================================


class WeightedProfileResponse(BaseModel):
    """A single profile and its weight in a blended (hybrid) recommendation."""
    profile_id: str = Field(description="Mastering profile identifier")
    profile_name: str = Field(description="Human-readable profile name")
    weight: float = Field(description="Blend weight (0–1, all weights sum to 1.0)")


class MasteringRecommendationResponse(BaseModel):
    """Mastering profile recommendation for a track.

    Mirrors the frontend ``MasteringRecommendationResponse`` (``api.ts``) so the
    REST endpoint honors the same contract as the WS broadcast. Declaring this
    as the endpoint's ``response_model`` also strips the internal-only
    ``created`` / ``alternative_profiles`` fields that ``to_dict()`` emits but
    no REST consumer expects (fixes #3840).
    """
    track_id: int = Field(description="Track database ID")
    primary_profile_id: str = Field(description="Best-matching profile identifier")
    primary_profile_name: str = Field(description="Best-matching profile name")
    confidence_score: float = Field(description="Recommendation confidence (0–1)")
    predicted_loudness_change: float = Field(description="Predicted RMS change (dB)")
    predicted_crest_change: float = Field(description="Predicted crest-factor change (dB)")
    predicted_centroid_change: float = Field(description="Predicted spectral-centroid change (Hz)")
    weighted_profiles: list[WeightedProfileResponse] = Field(
        default_factory=list,
        description="Blended profiles when hybrid; empty list otherwise",
    )
    reasoning: str = Field(default="", description="Explanation for the recommendation")
    is_hybrid: bool = Field(description="Whether this is a blended (weighted) recommendation")
