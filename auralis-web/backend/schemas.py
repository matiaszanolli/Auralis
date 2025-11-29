"""
Standardized Request/Response Schemas
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Defines Pydantic models for all API request/response payloads.
Ensures consistent structure across all endpoints.

Phase B.1: Backend Endpoint Standardization

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import TypeVar, Generic, Optional, List, Any, Dict
from enum import Enum
import datetime

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
