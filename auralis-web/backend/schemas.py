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
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

# ============================================================================
# Generic Response Wrappers
# ============================================================================

T = TypeVar('T')


class SuccessResponse(BaseModel, Generic[T]):
    """Successful API response wrapper."""
    status: str = Field(default="success", description="Response status")
    data: T = Field(description="Response payload")
    message: Optional[str] = Field(default=None, description="Optional message")
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

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
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

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

class PaginationParams(BaseModel):
    """Standard pagination parameters."""
    limit: int = Field(default=50, ge=1, le=500, description="Items per page")
    offset: int = Field(default=0, ge=0, description="Items to skip")

    model_config = ConfigDict(json_schema_extra={
        "example": {"limit": 50, "offset": 0}
    })


class CursorPaginationParams(BaseModel):
    """Cursor-based pagination parameters."""
    cursor: Optional[str] = Field(default=None, description="Pagination cursor")
    limit: int = Field(default=50, ge=1, le=500, description="Items per page")

    model_config = ConfigDict(json_schema_extra={
        "example": {"cursor": None, "limit": 50}
    })


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


class CursorPaginationMeta(BaseModel):
    """Cursor-based pagination metadata."""
    cursor: Optional[str] = Field(description="Next page cursor, null if no more items")
    limit: int = Field(description="Items per page")
    has_more: bool = Field(description="Are there more items available")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "cursor": "next_cursor_token",
            "limit": 50,
            "has_more": True
        }
    })


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response."""
    status: str = Field(default="success")
    data: List[T] = Field(description="Page of items")
    pagination: PaginationMeta = Field(description="Pagination metadata")
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

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
    data: Optional[Dict[str, Any]] = Field(default=None, description="Item data")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": "track_123",
            "action": "favorite",
            "data": {"rating": 5}
        }
    })


class BatchRequest(BaseModel):
    """Batch operation request."""
    items: List[BatchItem] = Field(description="Items to operate on")
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
    message: Optional[str] = Field(default=None, description="Result message")
    error: Optional[str] = Field(default=None, description="Error message if failed")

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
    results: List[BatchItemResult] = Field(description="Results for each item")
    successful: int = Field(description="Number of successful operations")
    failed: int = Field(description="Number of failed operations")
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

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
# Health Check Models
# ============================================================================

class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str = Field(description="Service status")
    version: str = Field(description="API version")
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": "2024-11-28T10:00:00Z"
        }
    })


class VersionResponse(BaseModel):
    """Version information response."""
    api_version: str = Field(description="API version")
    app_version: str = Field(description="Application version")
    backend_version: str = Field(description="Backend version")
    components: Dict[str, str] = Field(description="Component versions")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "api_version": "1.0.0",
            "app_version": "1.1.0-beta.4",
            "backend_version": "1.0.0",
            "components": {
                "cache": "2.0.0",
                "processor": "3.5.0"
            }
        }
    })


# ============================================================================
# Common Field Models
# ============================================================================

class TrackBase(BaseModel):
    """Base track fields."""
    id: str = Field(description="Track ID")
    title: str = Field(description="Track title")
    artist: str = Field(description="Artist name")
    album: str = Field(description="Album name")
    duration: float = Field(description="Duration in seconds")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": "track_123",
            "title": "Song Name",
            "artist": "Artist Name",
            "album": "Album Name",
            "duration": 180.5
        }
    })


class ArtistBase(BaseModel):
    """Base artist fields."""
    id: str = Field(description="Artist ID")
    name: str = Field(description="Artist name")
    track_count: int = Field(description="Number of tracks")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": "artist_123",
            "name": "Artist Name",
            "track_count": 25
        }
    })


class AlbumBase(BaseModel):
    """Base album fields."""
    id: str = Field(description="Album ID")
    title: str = Field(description="Album title")
    artist: str = Field(description="Album artist")
    track_count: int = Field(description="Number of tracks")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": "album_123",
            "title": "Album Name",
            "artist": "Artist Name",
            "track_count": 12
        }
    })


# ============================================================================
# Request Models
# ============================================================================

class SearchRequest(BaseModel):
    """Search request."""
    query: str = Field(min_length=1, description="Search query")
    type: Optional[str] = Field(default=None, description="Search type (track, artist, album)")
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "query": "test song",
            "type": "track",
            "limit": 50,
            "offset": 0
        }
    })


class FilterRequest(BaseModel):
    """Filter request."""
    filters: Dict[str, Any] = Field(description="Filter criteria")
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "filters": {"artist": "Artist Name"},
            "limit": 50,
            "offset": 0
        }
    })


# ============================================================================
# Status Enums
# ============================================================================

class ResponseStatus(str, Enum):
    """Response status values."""
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"


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
# Cache Integration Models (Phase 7.5)
# ============================================================================

class CacheSource(str, Enum):
    """Source of cached data."""
    TIER1 = "tier1"  # Hot cache: current + next chunk
    TIER2 = "tier2"  # Warm cache: full track
    MISS = "miss"    # Not cached


class ChunkCacheMetadata(BaseModel):
    """Metadata about a cached chunk."""
    track_id: int = Field(description="Track ID")
    chunk_index: int = Field(description="Chunk index")
    preset: Optional[str] = Field(description="Preset name or 'original'")
    intensity: float = Field(ge=0.0, le=1.0, description="Processing intensity")
    source: CacheSource = Field(description="Cache tier (tier1, tier2, miss)")
    timestamp: datetime.datetime = Field(description="Cache creation time")
    access_count: int = Field(description="Number of accesses")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "track_id": 123,
            "chunk_index": 0,
            "preset": "adaptive",
            "intensity": 1.0,
            "source": "tier1",
            "timestamp": "2024-11-28T10:00:00Z",
            "access_count": 5
        }
    })


class TrackCacheStatusResponse(BaseModel):
    """Cache status for a specific track."""
    track_id: int = Field(description="Track ID")
    total_chunks: int = Field(description="Total chunks in track")
    cached_original: int = Field(description="Cached original chunks")
    cached_processed: int = Field(description="Cached processed chunks")
    completion_percent: float = Field(ge=0.0, le=100.0, description="Cache completion percentage")
    fully_cached: bool = Field(description="Is track fully cached")
    estimated_cache_time_seconds: Optional[float] = Field(description="Time to cache remaining chunks")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "track_id": 123,
            "total_chunks": 50,
            "cached_original": 50,
            "cached_processed": 35,
            "completion_percent": 70.0,
            "fully_cached": False,
            "estimated_cache_time_seconds": 15.5
        }
    })


class CacheTierStats(BaseModel):
    """Statistics for a cache tier."""
    tier_name: str = Field(description="Tier name (tier1 or tier2)")
    chunks: int = Field(description="Number of cached chunks")
    size_mb: float = Field(description="Total size in megabytes")
    hits: int = Field(description="Cache hits")
    misses: int = Field(description="Cache misses")
    hit_rate: float = Field(ge=0.0, le=1.0, description="Hit rate (0.0-1.0)")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "tier_name": "tier1",
            "chunks": 4,
            "size_mb": 6.0,
            "hits": 150,
            "misses": 10,
            "hit_rate": 0.938
        }
    })


class OverallCacheStats(BaseModel):
    """Overall cache statistics."""
    total_chunks: int = Field(description="Total cached chunks across all tiers")
    total_size_mb: float = Field(description="Total cache size in megabytes")
    total_hits: int = Field(description="Total cache hits")
    total_misses: int = Field(description="Total cache misses")
    overall_hit_rate: float = Field(ge=0.0, le=1.0, description="Overall hit rate")
    tracks_cached: int = Field(description="Number of tracks with cached data")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "total_chunks": 150,
            "total_size_mb": 225.0,
            "total_hits": 1500,
            "total_misses": 100,
            "overall_hit_rate": 0.938,
            "tracks_cached": 5
        }
    })


class CacheStatsResponse(BaseModel):
    """Complete cache statistics response."""
    tier1: CacheTierStats = Field(description="Tier 1 (hot) cache stats")
    tier2: CacheTierStats = Field(description="Tier 2 (warm) cache stats")
    overall: OverallCacheStats = Field(description="Overall cache stats")
    tracks: Dict[int, TrackCacheStatusResponse] = Field(description="Per-track cache status")
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "tier1": {
                "tier_name": "tier1",
                "chunks": 4,
                "size_mb": 6.0,
                "hits": 150,
                "misses": 10,
                "hit_rate": 0.938
            },
            "tier2": {
                "tier_name": "tier2",
                "chunks": 146,
                "size_mb": 219.0,
                "hits": 1350,
                "misses": 90,
                "hit_rate": 0.937
            },
            "overall": {
                "total_chunks": 150,
                "total_size_mb": 225.0,
                "total_hits": 1500,
                "total_misses": 100,
                "overall_hit_rate": 0.938,
                "tracks_cached": 5
            },
            "tracks": {
                "123": {
                    "track_id": 123,
                    "total_chunks": 50,
                    "cached_original": 50,
                    "cached_processed": 35,
                    "completion_percent": 70.0,
                    "fully_cached": False,
                    "estimated_cache_time_seconds": 15.5
                }
            },
            "timestamp": "2024-11-28T10:00:00Z"
        }
    })


class CacheHealthResponse(BaseModel):
    """Cache system health status."""
    healthy: bool = Field(description="Is cache system healthy")
    tier1_size_mb: float = Field(description="Tier 1 size in megabytes")
    tier1_healthy: bool = Field(description="Is Tier 1 within healthy limits")
    tier2_size_mb: float = Field(description="Tier 2 size in megabytes")
    tier2_healthy: bool = Field(description="Is Tier 2 within healthy limits")
    total_size_mb: float = Field(description="Total cache size")
    memory_healthy: bool = Field(description="Is total memory usage healthy")
    tier1_hit_rate: float = Field(ge=0.0, le=1.0, description="Tier 1 hit rate")
    overall_hit_rate: float = Field(ge=0.0, le=1.0, description="Overall hit rate")
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "healthy": True,
            "tier1_size_mb": 6.0,
            "tier1_healthy": True,
            "tier2_size_mb": 200.0,
            "tier2_healthy": True,
            "total_size_mb": 206.0,
            "memory_healthy": True,
            "tier1_hit_rate": 0.95,
            "overall_hit_rate": 0.938,
            "timestamp": "2024-11-28T10:00:00Z"
        }
    })


class CacheAwareResponse(BaseModel, Generic[T]):
    """Response wrapper with cache information."""
    status: str = Field(default="success", description="Response status")
    data: T = Field(description="Response payload")
    cache_source: CacheSource = Field(description="Where data came from")
    cache_hit: bool = Field(description="Was this a cache hit")
    processing_time_ms: float = Field(description="Time to process/retrieve in milliseconds")
    message: Optional[str] = Field(default=None, description="Optional message")
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "status": "success",
            "data": {},
            "cache_source": "tier1",
            "cache_hit": True,
            "processing_time_ms": 2.5,
            "message": "Retrieved from hot cache",
            "timestamp": "2024-11-28T10:00:00Z"
        }
    })
