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
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ============================================================================
# Generic Response Wrappers
# ============================================================================

T = TypeVar('T')


class SuccessResponse(BaseModel, Generic[T]):
    """Successful API response wrapper."""
    status: str = Field(default="success", description="Response status")
    data: T = Field(description="Response payload")
    message: str | None = Field(default=None, description="Optional message")
    timestamp: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "status": "success",
            "data": {},
            "message": "Operation completed",
            "timestamp": "2024-11-28T10:00:00Z"
        }
    })


class ErrorResponse(BaseModel):
    """Error API response wrapper."""
    status: str = Field(default="error", description="Response status")
    error: str = Field(description="Error type/code")
    message: str = Field(description="Human-readable error message")
    details: dict[str, Any] | None = Field(default=None, description="Additional error details")
    timestamp: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "status": "error",
            "error": "validation_error",
            "message": "Invalid request parameters",
            "details": {"field": "limit", "issue": "Must be positive"},
            "timestamp": "2024-11-28T10:00:00Z"
        }
    })


# ============================================================================
# Pagination Models
# ============================================================================

class PaginationMeta(BaseModel):
    """Pagination metadata for response."""
    limit: int = Field(description="Items per page")
    offset: int = Field(description="Items skipped")
    total: int = Field(description="Total items available")
    remaining: int = Field(description="Items remaining after this page")
    has_more: bool = Field(description="Are there more items available")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "limit": 50,
            "offset": 0,
            "total": 1000,
            "remaining": 950,
            "has_more": True
        }
    })


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response."""
    status: str = Field(default="success")
    data: list[T] = Field(description="Page of items")
    pagination: PaginationMeta = Field(description="Pagination metadata")
    timestamp: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "status": "success",
            "data": [],
            "pagination": {
                "limit": 50,
                "offset": 0,
                "total": 1000,
                "remaining": 950,
                "has_more": True
            },
            "timestamp": "2024-11-28T10:00:00Z"
        }
    })


# ============================================================================
# Batch Operation Models
# ============================================================================

class BatchItem(BaseModel):
    """Single item in a batch operation."""
    id: str = Field(description="Item identifier")
    action: str = Field(description="Operation type (e.g., 'add', 'remove', 'update')")
    data: dict[str, Any] | None = Field(default=None, description="Item data")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": "track_123",
            "action": "favorite",
            "data": {"rating": 5}
        }
    })


class BatchRequest(BaseModel):
    """Batch operation request."""
    items: list[BatchItem] = Field(description="Items to operate on")
    atomic: bool = Field(default=False, description="All-or-nothing execution")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "items": [
                {"id": "track_1", "action": "favorite"},
                {"id": "track_2", "action": "favorite"}
            ],
            "atomic": True
        }
    })


class BatchItemResult(BaseModel):
    """Result of a single batch item operation."""
    id: str = Field(description="Item identifier")
    status: str = Field(description="Operation status (success, error)")
    message: str | None = Field(default=None, description="Result message")
    error: str | None = Field(default=None, description="Error message if failed")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": "track_123",
            "status": "success",
            "message": "Track favorited"
        }
    })


class BatchResponse(BaseModel):
    """Batch operation response."""
    status: str = Field(description="Overall batch status")
    results: list[BatchItemResult] = Field(description="Results for each item")
    successful: int = Field(description="Number of successful operations")
    failed: int = Field(description="Number of failed operations")
    timestamp: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "status": "completed",
            "results": [
                {"id": "track_1", "status": "success"},
                {"id": "track_2", "status": "success"}
            ],
            "successful": 2,
            "failed": 0,
            "timestamp": "2024-11-28T10:00:00Z"
        }
    })


# ============================================================================
# Status Enums
# ============================================================================

class ErrorType(str, Enum):
    """Error type codes."""
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    CONFLICT = "conflict"
    INTERNAL_ERROR = "internal_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    TIMEOUT = "timeout"


# ============================================================================
# WebSocket Message Models (Security: #2156)
# ============================================================================

class WebSocketMessageType(str, Enum):
    """Valid WebSocket message types."""
    PING = "ping"
    PONG = "pong"
    HEARTBEAT = "heartbeat"
    PROCESSING_SETTINGS_UPDATE = "processing_settings_update"
    PROCESSING_SETTINGS_APPLIED = "processing_settings_applied"
    AB_TRACK_LOADED = "ab_track_loaded"
    AB_TRACK_READY = "ab_track_ready"
    PLAY_ENHANCED = "play_enhanced"
    PLAY_NORMAL = "play_normal"
    PAUSE = "pause"
    STOP = "stop"
    SEEK = "seek"
    SEEK_STARTED = "seek_started"
    SUBSCRIBE_JOB_PROGRESS = "subscribe_job_progress"
    JOB_PROGRESS = "job_progress"
    AUDIO_STREAM_ERROR = "audio_stream_error"
    PLAYBACK_PAUSED = "playback_paused"
    PLAYBACK_STOPPED = "playback_stopped"


class WebSocketMessageBase(BaseModel):
    """Base WebSocket message with type validation."""
    type: WebSocketMessageType = Field(description="Message type")
    data: dict[str, Any] | None = Field(default=None, description="Message payload")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "type": "ping",
            "data": None
        }
    })


class LibraryScanRequest(BaseModel):
    """Library scan request (POST /api/library/scan)."""
    directories: list[str] = Field(description="List of directory paths to scan")
    recursive: bool = Field(default=True, description="Whether to scan subdirectories")
    skip_existing: bool = Field(default=True, description="Skip files already in library")

    @field_validator('directories')
    @classmethod
    def validate_directory_paths(cls, v: list[str]) -> list[str]:
        """Validate all directory paths to prevent path traversal."""
        from security.path_security import PathValidationError, validate_scan_path

        validated = []
        for path in v:
            try:
                validated_path = validate_scan_path(path)
                validated.append(str(validated_path))
            except PathValidationError as e:
                raise ValueError(f"Invalid directory path '{path}': {e}")
        return validated

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "directories": ["/home/user/Music"],
            "recursive": True,
            "skip_existing": True
        }
    })


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
# Entity Base Models
# ============================================================================

class TrackBase(BaseModel):
    """Minimal track representation for API responses."""
    id: str = Field(description="Track identifier")
    title: str = Field(description="Track title")
    artist: str = Field(description="Artist name")
    album: str = Field(description="Album name")
    duration: float = Field(description="Duration in seconds")


class ArtistBase(BaseModel):
    """Minimal artist representation for API responses."""
    id: str = Field(description="Artist identifier")
    name: str = Field(description="Artist name")
    track_count: int = Field(description="Number of tracks by this artist")


class AlbumBase(BaseModel):
    """Minimal album representation for API responses."""
    id: str = Field(description="Album identifier")
    title: str = Field(description="Album title")
    artist: str = Field(description="Artist name")
    track_count: int = Field(description="Number of tracks in this album")


# ============================================================================
# Request Parameter Models
# ============================================================================

class PaginationParams(BaseModel):
    """Standard pagination query parameters."""
    limit: int = Field(default=50, ge=1, le=500, description="Items per page (1–500)")
    offset: int = Field(default=0, ge=0, description="Number of items to skip")


class CursorPaginationParams(BaseModel):
    """Cursor-based pagination parameters."""
    limit: int = Field(default=50, ge=1, le=500, description="Items per page (1–500)")
    cursor: str | None = Field(default=None, description="Opaque cursor from previous response")


class SearchRequest(BaseModel):
    """Generic search request."""
    query: str = Field(description="Search query string")
    fields: list[str] | None = Field(default=None, description="Fields to search in")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of results")
    offset: int = Field(default=0, ge=0, description="Number of results to skip")


# ============================================================================
# System / Health Response Models
# ============================================================================

class ResponseStatus(str, Enum):
    """Standard response status values."""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


class HealthCheckResponse(BaseModel):
    """Health check endpoint response."""
    status: str = Field(default="healthy", description="Service status")
    version: str | None = Field(default=None, description="Service version")
    uptime_seconds: float | None = Field(default=None, description="Service uptime in seconds")
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class VersionResponse(BaseModel):
    """Version information response."""
    version: str = Field(description="Application version string")
    build: str | None = Field(default=None, description="Build identifier")
    python_version: str | None = Field(default=None, description="Python runtime version")


# ============================================================================
# Cache Schemas (Phase B.2)
# ============================================================================

class CacheSource(str, Enum):
    """Cache tier source indicator."""
    TIER1 = "tier1"
    TIER2 = "tier2"
    MISS = "miss"


class ChunkCacheMetadata(BaseModel):
    """Metadata for a single cached audio chunk."""
    track_id: int = Field(description="Track identifier")
    chunk_index: int = Field(description="Zero-based chunk index")
    preset: str = Field(description="Processing preset name")
    intensity: float = Field(description="Processing intensity value")
    source: CacheSource = Field(description="Which cache tier served this chunk")
    timestamp: datetime.datetime = Field(description="When the chunk was cached")
    access_count: int = Field(default=0, description="Number of times this chunk was accessed")


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


class CacheAwareResponse(BaseModel, Generic[T]):
    """Response wrapper that includes cache hit/miss metadata."""
    status: str = Field(default="success", description="Response status")
    data: T = Field(description="Response payload")
    cache_source: CacheSource = Field(description="Cache tier that served the response")
    cache_hit: bool = Field(description="Whether the response was served from cache")
    processing_time_ms: float = Field(description="Time to generate the response in ms")
    message: str | None = Field(default=None, description="Optional message")


class CacheStatsResponse(BaseModel):
    """Full cache statistics response."""
    tier1: CacheTierStats = Field(description="Tier 1 (memory) statistics")
    tier2: CacheTierStats = Field(description="Tier 2 (disk) statistics")
    overall: OverallCacheStats = Field(description="Aggregate statistics")
    tracks: dict[int, Any] = Field(default_factory=dict, description="Per-track cache status")
