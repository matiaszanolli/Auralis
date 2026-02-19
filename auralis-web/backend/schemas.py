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
        from path_security import PathValidationError, validate_scan_path

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
