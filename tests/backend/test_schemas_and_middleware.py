"""
Tests for Backend Schemas and Middleware
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive tests for Phase B.1 endpoint standardization.

Test Coverage:
- Schemas: Request/response validation and serialization
- Middleware: Validation, error handling, rate limiting, logging
- Helpers: Pagination, batch operations, filtering

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))

from helpers import (
    apply_filters,
    apply_search,
    create_paginated_response,
    create_pagination_meta,
    create_success_response,
    execute_batch_operation_sync,
    paginate_list,
    validate_batch_request,
    validate_pagination_params,
)
from schemas import (
    AlbumBase,
    ArtistBase,
    BatchItem,
    BatchItemResult,
    BatchRequest,
    BatchResponse,
    CursorPaginationParams,
    ErrorResponse,
    ErrorType,
    HealthCheckResponse,
    PaginatedResponse,
    PaginationMeta,
    PaginationParams,
    ResponseStatus,
    SearchRequest,
    SuccessResponse,
    TrackBase,
    VersionResponse,
)

# ============================================================================
# Schema Tests
# ============================================================================

class TestSuccessResponse:
    """Test SuccessResponse schema."""

    def test_success_response_creation(self):
        """Test creating a success response."""
        response = SuccessResponse(
            status="success",
            data={"key": "value"},
            message="Operation successful"
        )
        assert response.status == "success"
        assert response.data == {"key": "value"}
        assert response.message == "Operation successful"
        assert response.timestamp is not None

    def test_success_response_serialization(self):
        """Test serializing success response to JSON."""
        response = SuccessResponse(
            status="success",
            data={"test": "data"},
        )
        json_data = response.model_dump()
        assert json_data["status"] == "success"
        assert json_data["data"] == {"test": "data"}
        assert "timestamp" in json_data

    def test_success_response_without_message(self):
        """Test success response with optional message omitted."""
        response = SuccessResponse(data={"key": "value"})
        assert response.message is None
        json_data = response.model_dump()
        assert json_data["message"] is None


class TestErrorResponse:
    """Test ErrorResponse schema."""

    def test_error_response_creation(self):
        """Test creating an error response."""
        response = ErrorResponse(
            status="error",
            error=ErrorType.VALIDATION_ERROR,
            message="Validation failed"
        )
        assert response.status == "error"
        assert response.error == ErrorType.VALIDATION_ERROR
        assert response.message == "Validation failed"
        assert response.timestamp is not None

    def test_error_response_with_details(self):
        """Test error response with additional details."""
        response = ErrorResponse(
            status="error",
            error=ErrorType.NOT_FOUND,
            message="Track not found",
            details={"track_id": "123"}
        )
        assert response.details == {"track_id": "123"}
        json_data = response.model_dump()
        assert json_data["details"]["track_id"] == "123"

    def test_error_response_types(self):
        """Test all error response types."""
        for error_type in ErrorType:
            response = ErrorResponse(
                error=error_type,
                message=f"Test {error_type}"
            )
            assert response.error == error_type


class TestPaginationSchemas:
    """Test pagination-related schemas."""

    def test_pagination_params_validation(self):
        """Test PaginationParams validation."""
        # Valid params
        params = PaginationParams(limit=50, offset=0)
        assert params.limit == 50
        assert params.offset == 0

        # Default values
        params = PaginationParams()
        assert params.limit == 50
        assert params.offset == 0

    def test_pagination_params_constraints(self):
        """Test PaginationParams constraints."""
        # Limit must be at least 1
        with pytest.raises(ValueError):
            PaginationParams(limit=0)

        # Limit max is 500 - values above are rejected by Pydantic validation
        with pytest.raises(ValueError):
            PaginationParams(limit=600)

        # Boundary test: limit=500 should be valid
        params = PaginationParams(limit=500)
        assert params.limit == 500

        # Offset cannot be negative
        with pytest.raises(ValueError):
            PaginationParams(offset=-1)

    def test_pagination_meta_creation(self):
        """Test creating pagination metadata."""
        meta = PaginationMeta(
            limit=50,
            offset=0,
            total=1000,
            remaining=950,
            has_more=True
        )
        assert meta.limit == 50
        assert meta.has_more is True
        assert meta.remaining == 950

    def test_paginated_response_creation(self):
        """Test creating a paginated response."""
        data = [{"id": "1"}, {"id": "2"}]
        response = PaginatedResponse(
            data=data,
            pagination=PaginationMeta(
                limit=50, offset=0, total=100, remaining=98, has_more=True
            )
        )
        assert len(response.data) == 2
        assert response.pagination.total == 100


class TestBatchSchemas:
    """Test batch operation schemas."""

    def test_batch_item_creation(self):
        """Test creating a batch item."""
        item = BatchItem(
            id="track_1",
            action="favorite",
            data={"rating": 5}
        )
        assert item.id == "track_1"
        assert item.action == "favorite"
        assert item.data == {"rating": 5}

    def test_batch_request_creation(self):
        """Test creating a batch request."""
        items = [
            BatchItem(id="track_1", action="favorite"),
            BatchItem(id="track_2", action="favorite")
        ]
        request = BatchRequest(items=items, atomic=True)
        assert len(request.items) == 2
        assert request.atomic is True

    def test_batch_item_result_creation(self):
        """Test creating a batch item result."""
        result = BatchItemResult(
            id="track_1",
            status="success",
            message="Track favorited"
        )
        assert result.status == "success"
        assert result.error is None

        error_result = BatchItemResult(
            id="track_2",
            status="error",
            error="Track not found"
        )
        assert error_result.status == "error"
        assert error_result.error == "Track not found"

    def test_batch_response_creation(self):
        """Test creating a batch response."""
        results = [
            BatchItemResult(id="1", status="success"),
            BatchItemResult(id="2", status="success")
        ]
        response = BatchResponse(
            status="completed",
            results=results,
            successful=2,
            failed=0
        )
        assert response.status == "completed"
        assert response.successful == 2
        assert response.failed == 0


class TestDataModelSchemas:
    """Test data model schemas."""

    def test_track_base_schema(self):
        """Test TrackBase schema."""
        track = TrackBase(
            id="track_1",
            title="Song Name",
            artist="Artist Name",
            album="Album Name",
            duration=180.5
        )
        assert track.title == "Song Name"
        assert track.duration == 180.5

    def test_artist_base_schema(self):
        """Test ArtistBase schema."""
        artist = ArtistBase(
            id="artist_1",
            name="Artist Name",
            track_count=25
        )
        assert artist.name == "Artist Name"
        assert artist.track_count == 25

    def test_album_base_schema(self):
        """Test AlbumBase schema."""
        album = AlbumBase(
            id="album_1",
            title="Album Name",
            artist="Artist Name",
            track_count=12
        )
        assert album.title == "Album Name"
        assert album.track_count == 12


# ============================================================================
# Helper Function Tests
# ============================================================================

class TestPaginationHelpers:
    """Test pagination helper functions."""

    def test_create_pagination_meta(self):
        """Test creating pagination metadata."""
        meta = create_pagination_meta(
            limit=50,
            offset=0,
            total=1000
        )
        assert meta.limit == 50
        assert meta.offset == 0
        assert meta.total == 1000
        assert meta.has_more is True
        assert meta.remaining == 950

    def test_pagination_meta_last_page(self):
        """Test pagination metadata for last page."""
        meta = create_pagination_meta(
            limit=50,
            offset=950,
            total=1000
        )
        assert meta.has_more is False
        assert meta.remaining == 0

    def test_create_paginated_response(self):
        """Test creating a paginated response."""
        data = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
        response = create_paginated_response(
            data=data,
            limit=50,
            offset=0,
            total=1000
        )
        assert len(response.data) == 3
        assert response.pagination.total == 1000
        assert response.pagination.has_more is True

    def test_validate_pagination_params(self):
        """Test validating pagination parameters."""
        limit, offset = validate_pagination_params(
            limit=50,
            offset=0
        )
        assert limit == 50
        assert offset == 0

    def test_validate_pagination_params_exceeds_max(self):
        """Test validation when limit exceeds maximum."""
        limit, offset = validate_pagination_params(
            limit=1000,
            offset=0,
            max_limit=500
        )
        assert limit == 500

    def test_validate_pagination_params_errors(self):
        """Test pagination validation errors."""
        with pytest.raises(ValueError):
            validate_pagination_params(limit=0, offset=0)

        with pytest.raises(ValueError):
            validate_pagination_params(limit=50, offset=-1)

    def test_paginate_list(self):
        """Test paginating a list."""
        items = list(range(100))
        paginated, total = paginate_list(items, limit=10, offset=0)
        assert len(paginated) == 10
        assert total == 100
        assert paginated == list(range(10))

    def test_paginate_list_middle_page(self):
        """Test paginating to middle of list."""
        items = list(range(100))
        paginated, total = paginate_list(items, limit=10, offset=50)
        assert len(paginated) == 10
        assert paginated[0] == 50
        assert paginated[-1] == 59


class TestBatchOperationHelpers:
    """Test batch operation helper functions."""

    def test_validate_batch_request(self):
        """Test validating batch request."""
        request = BatchRequest(
            items=[BatchItem(id="1", action="favorite")],
            atomic=False
        )
        assert validate_batch_request(request) is True

    def test_validate_batch_request_empty(self):
        """Test validation of empty batch request."""
        request = BatchRequest(items=[], atomic=False)
        with pytest.raises(ValueError):
            validate_batch_request(request)

    def test_validate_batch_request_too_large(self):
        """Test validation of oversized batch request."""
        items = [BatchItem(id=str(i), action="test") for i in range(101)]
        request = BatchRequest(items=items, atomic=False)
        with pytest.raises(ValueError):
            validate_batch_request(request)

    @pytest.mark.asyncio
    async def test_execute_batch_operation_sync(self):
        """Test executing synchronous batch operations."""
        executed = []

        def favorite_handler(item_id: str, data: Dict[str, Any]):
            executed.append(item_id)

        handlers = {"favorite": favorite_handler}
        request = BatchRequest(
            items=[
                BatchItem(id="track_1", action="favorite"),
                BatchItem(id="track_2", action="favorite")
            ],
            atomic=False
        )

        response = await execute_batch_operation_sync(request, handlers)
        assert response.successful == 2
        assert response.failed == 0
        assert len(executed) == 2

    @pytest.mark.asyncio
    async def test_execute_batch_operation_with_error(self):
        """Test batch operation with errors."""
        def handler_with_error(item_id: str, data: Dict[str, Any]):
            if item_id == "error_track":
                raise ValueError("Test error")

        handlers = {"test": handler_with_error}
        request = BatchRequest(
            items=[
                BatchItem(id="ok_track", action="test"),
                BatchItem(id="error_track", action="test"),
                BatchItem(id="ok_track2", action="test")
            ],
            atomic=False
        )

        response = await execute_batch_operation_sync(request, handlers)
        assert response.failed == 1
        assert response.successful == 2


class TestFilteringHelpers:
    """Test data filtering helper functions."""

    def test_apply_filters(self):
        """Test applying filters to items."""
        items = [
            {"id": "1", "name": "Track A", "artist": "Artist 1"},
            {"id": "2", "name": "Track B", "artist": "Artist 1"},
            {"id": "3", "name": "Track C", "artist": "Artist 2"}
        ]
        filtered = apply_filters(items, {"artist": "Artist 1"})
        assert len(filtered) == 2
        assert all(item["artist"] == "Artist 1" for item in filtered)

    def test_apply_filters_multiple(self):
        """Test applying multiple filters."""
        items = [
            {"id": "1", "artist": "A", "year": 2020},
            {"id": "2", "artist": "A", "year": 2021},
            {"id": "3", "artist": "B", "year": 2020}
        ]
        filtered = apply_filters(items, {"artist": "A", "year": 2020})
        assert len(filtered) == 1
        assert filtered[0]["id"] == "1"

    def test_apply_filters_empty(self):
        """Test applying empty filters (no change)."""
        items = [{"id": "1"}, {"id": "2"}]
        filtered = apply_filters(items, {})
        assert filtered == items

    def test_apply_search(self):
        """Test searching in items."""
        items = [
            {"title": "Song A", "artist": "Artist One"},
            {"title": "Song B", "artist": "Artist Two"},
            {"title": "Another", "artist": "Someone"}
        ]
        results = apply_search(items, "Song", ["title", "artist"])
        assert len(results) == 2
        assert results[0]["title"] == "Song A"

    def test_apply_search_case_insensitive(self):
        """Test case-insensitive search."""
        items = [
            {"title": "SONG A", "artist": "artist one"},
            {"title": "Song B", "artist": "Artist Two"}
        ]
        results = apply_search(items, "song", ["title", "artist"])
        assert len(results) == 2


class TestResponseHelpers:
    """Test response helper functions."""

    def test_create_success_response(self):
        """Test creating a success response."""
        response = create_success_response(
            data={"key": "value"},
            message="Success"
        )
        assert response.status == "success"
        assert response.data == {"key": "value"}
        assert response.message == "Success"

    def test_create_success_response_without_message(self):
        """Test success response without message."""
        response = create_success_response(data=[1, 2, 3])
        assert response.message is None
        assert response.data == [1, 2, 3]


# ============================================================================
# Integration Tests
# ============================================================================

class TestSchemaIntegration:
    """Integration tests for schemas."""

    def test_full_paginated_response_flow(self):
        """Test complete paginated response flow."""
        # Create data
        items = [
            TrackBase(id="1", title="A", artist="X", album="1", duration=180),
            TrackBase(id="2", title="B", artist="Y", album="2", duration=200)
        ]

        # Create response
        response = create_paginated_response(
            data=items,
            limit=50,
            offset=0,
            total=100
        )

        # Serialize
        json_data = response.model_dump()

        # Verify structure
        assert json_data["status"] == "success"
        assert len(json_data["data"]) == 2
        assert json_data["pagination"]["total"] == 100
        assert json_data["pagination"]["has_more"] is True

    def test_batch_operation_end_to_end(self):
        """Test complete batch operation flow."""
        # Create request
        request = BatchRequest(
            items=[
                BatchItem(id="1", action="favorite"),
                BatchItem(id="2", action="favorite")
            ],
            atomic=True
        )

        # Validate
        assert validate_batch_request(request)

        # Execute
        handlers = {
            "favorite": lambda item_id, data: None
        }
        response = execute_batch_operation_sync(request, handlers)

        # Verify response
        assert response.status == "completed"
        assert response.successful == 2
        assert response.failed == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
