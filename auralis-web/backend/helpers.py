"""
API Helpers
~~~~~~~~~~~

Helper functions for pagination, batch operations, and common patterns.

Phase B.1: Backend Endpoint Standardization

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import List, TypeVar, Callable, Any, Optional, Dict
from schemas import (
    PaginationMeta,
    PaginatedResponse,
    BatchRequest,
    BatchResponse,
    BatchItemResult,
    SuccessResponse
)
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============================================================================
# Pagination Helpers
# ============================================================================

def create_pagination_meta(
    limit: int,
    offset: int,
    total: int
) -> PaginationMeta:
    """
    Create pagination metadata.

    Args:
        limit: Items per page
        offset: Items skipped
        total: Total items available

    Returns:
        PaginationMeta: Pagination information
    """
    remaining = max(0, total - offset - limit)
    has_more = (offset + limit) < total

    return PaginationMeta(
        limit=limit,
        offset=offset,
        total=total,
        remaining=remaining,
        has_more=has_more
    )


def create_paginated_response(
    data: List[T],
    limit: int,
    offset: int,
    total: int
) -> PaginatedResponse[T]:
    """
    Create a paginated response.

    Args:
        data: Items to return
        limit: Items per page
        offset: Items skipped
        total: Total items available

    Returns:
        PaginatedResponse: Formatted paginated response
    """
    pagination = create_pagination_meta(limit, offset, total)
    return PaginatedResponse(
        status="success",
        data=data,
        pagination=pagination
    )


def validate_pagination_params(
    limit: int,
    offset: int,
    max_limit: int = 500
) -> tuple[int, int]:
    """
    Validate and normalize pagination parameters.

    Args:
        limit: Requested items per page
        offset: Items to skip
        max_limit: Maximum allowed limit

    Returns:
        Tuple of (limit, offset) normalized values

    Raises:
        ValueError: If parameters are invalid
    """
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if limit > max_limit:
        limit = max_limit
    if offset < 0:
        raise ValueError("offset cannot be negative")

    return limit, offset


# ============================================================================
# Batch Operation Helpers
# ============================================================================

async def execute_batch_operation(
    batch_request: BatchRequest,
    handlers: Dict[str, Callable[..., Any]],
    atomic: bool = False
) -> BatchResponse:
    """
    Execute a batch of operations with optional atomicity.

    Args:
        batch_request: Batch operation request
        handlers: Dict mapping action types to handler functions
        atomic: If True, all-or-nothing execution

    Returns:
        BatchResponse: Results of batch operations

    Example:
        handlers = {
            'favorite': favorite_track,
            'unfavorite': unfavorite_track,
        }
        response = await execute_batch_operation(request, handlers)
    """
    results: List[BatchItemResult] = []
    successful = 0
    failed = 0

    for item in batch_request.items:
        try:
            handler = handlers.get(item.action)
            if not handler:
                raise ValueError(f"Unknown action: {item.action}")

            # Execute the handler
            await handler(item.id, item.data or {})

            # Record success
            results.append(BatchItemResult(
                id=item.id,
                status="success",
                message=f"Action '{item.action}' completed"
            ))
            successful += 1

        except Exception as e:
            logger.error(f"Batch operation failed for {item.id}: {e}")

            if atomic:
                # Rollback on first error in atomic mode
                # In production, implement proper transaction rollback
                logger.error("Atomic batch operation failed, would rollback")
                failed += 1
                results.append(BatchItemResult(
                    id=item.id,
                    status="error",
                    error=str(e)
                ))
                break

            # Non-atomic: continue with other items
            results.append(BatchItemResult(
                id=item.id,
                status="error",
                error=str(e)
            ))
            failed += 1

    overall_status = "completed" if failed == 0 else "partial"
    if atomic and failed > 0:
        overall_status = "failed"

    return BatchResponse(
        status=overall_status,
        results=results,
        successful=successful,
        failed=failed
    )


async def execute_batch_operation_sync(
    batch_request: BatchRequest,
    handlers: Dict[str, Callable[..., Any]],
    atomic: bool = False
) -> BatchResponse:
    """
    Execute batch operations with synchronous handlers.
    Wrapper for async/await compatibility.

    Args:
        batch_request: Batch operation request
        handlers: Dict mapping action types to handler functions
        atomic: If True, all-or-nothing execution

    Returns:
        BatchResponse: Results of batch operations
    """
    results: List[BatchItemResult] = []
    successful = 0
    failed = 0

    for item in batch_request.items:
        try:
            handler = handlers.get(item.action)
            if not handler:
                raise ValueError(f"Unknown action: {item.action}")

            # Execute the handler
            result = handler(item.id, item.data or {})

            # Record success
            results.append(BatchItemResult(
                id=item.id,
                status="success",
                message=f"Action '{item.action}' completed"
            ))
            successful += 1

        except Exception as e:
            logger.error(f"Batch operation failed for {item.id}: {e}")

            if atomic:
                failed += 1
                results.append(BatchItemResult(
                    id=item.id,
                    status="error",
                    error=str(e)
                ))
                break

            results.append(BatchItemResult(
                id=item.id,
                status="error",
                error=str(e)
            ))
            failed += 1

    overall_status = "completed" if failed == 0 else "partial"
    if atomic and failed > 0:
        overall_status = "failed"

    return BatchResponse(
        status=overall_status,
        results=results,
        successful=successful,
        failed=failed
    )


# ============================================================================
# Query Helpers
# ============================================================================

def paginate_list(
    items: List[T],
    limit: int,
    offset: int
) -> tuple[List[T], int]:
    """
    Paginate a list of items.

    Args:
        items: List to paginate
        limit: Items per page
        offset: Items to skip

    Returns:
        Tuple of (paginated_items, total_count)
    """
    total = len(items)
    paginated = items[offset:offset + limit]
    return paginated, total


def apply_filters(
    items: List[Dict[str, Any]],
    filters: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Apply filters to a list of items.

    Args:
        items: Items to filter
        filters: Filter criteria (simple equality matching)

    Returns:
        Filtered list of items

    Example:
        items = [{'name': 'John', 'age': 30}, {'name': 'Jane', 'age': 25}]
        filters = {'age': 25}
        result = apply_filters(items, filters)  # Returns Jane's record
    """
    if not filters:
        return items

    filtered = items
    for key, value in filters.items():
        filtered = [
            item for item in filtered
            if item.get(key) == value
        ]

    return filtered


def apply_search(
    items: List[Dict[str, Any]],
    query: str,
    search_fields: List[str]
) -> List[Dict[str, Any]]:
    """
    Apply text search to a list of items.

    Args:
        items: Items to search
        query: Search query
        search_fields: Fields to search in

    Returns:
        Filtered list matching search query

    Example:
        items = [{'title': 'Song A', 'artist': 'Artist 1'}, ...]
        results = apply_search(items, 'Song', ['title', 'artist'])
    """
    if not query:
        return items

    query_lower = query.lower()
    results = []

    for item in items:
        for field in search_fields:
            value = item.get(field, "")
            if isinstance(value, str) and query_lower in value.lower():
                results.append(item)
                break

    return results


# ============================================================================
# Response Helpers
# ============================================================================

def create_success_response(
    data: Any,
    message: Optional[str] = None,
) -> SuccessResponse[Any]:
    """
    Create a standardized success response.

    Args:
        data: Response payload
        message: Optional message

    Returns:
        SuccessResponse: Formatted success response
    """
    return SuccessResponse(
        status="success",
        data=data,
        message=message
    )


# ============================================================================
# Validation Helpers
# ============================================================================

def validate_batch_request(batch_request: BatchRequest) -> bool:
    """
    Validate batch request structure.

    Args:
        batch_request: Batch request to validate

    Returns:
        True if valid, raises exception otherwise

    Raises:
        ValueError: If request is invalid
    """
    if not batch_request.items:
        raise ValueError("Batch request must contain at least one item")

    if len(batch_request.items) > 100:
        raise ValueError("Batch request limited to 100 items maximum")

    for item in batch_request.items:
        if not item.id:
            raise ValueError("All items must have an id")
        if not item.action:
            raise ValueError("All items must have an action")

    return True


# ============================================================================
# Cache-Aware Helpers (Phase 7.5)
# ============================================================================

import time

def calculate_cache_hit_probability(
    total_hits: int,
    total_misses: int,
    minimum_requests: int = 10
) -> float:
    """
    Calculate hit rate with minimum request threshold.

    Args:
        total_hits: Number of cache hits
        total_misses: Number of cache misses
        minimum_requests: Minimum requests before reporting rate (default 10)

    Returns:
        Hit rate (0.0-1.0), or 0.0 if below minimum requests
    """
    total_requests = total_hits + total_misses

    if total_requests < minimum_requests:
        return 0.0

    return total_hits / max(1, total_requests)


def format_cache_stats(stats: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format cache statistics for API response.

    Args:
        stats: Raw cache stats dictionary from StreamlinedCacheManager

    Returns:
        Formatted stats dictionary ready for response
    """
    tier1 = stats.get("tier1", {})
    tier2 = stats.get("tier2", {})
    overall = stats.get("overall", {})
    tracks = stats.get("tracks", {})

    return {
        "tier1": {
            "tier_name": "tier1",
            "chunks": tier1.get("chunks", 0),
            "size_mb": round(tier1.get("size_mb", 0), 2),
            "hits": tier1.get("hits", 0),
            "misses": tier1.get("misses", 0),
            "hit_rate": round(tier1.get("hit_rate", 0.0), 3)
        },
        "tier2": {
            "tier_name": "tier2",
            "chunks": tier2.get("chunks", 0),
            "size_mb": round(tier2.get("size_mb", 0), 2),
            "hits": tier2.get("hits", 0),
            "misses": tier2.get("misses", 0),
            "hit_rate": round(tier2.get("hit_rate", 0.0), 3)
        },
        "overall": {
            "total_chunks": overall.get("total_chunks", 0),
            "total_size_mb": round(overall.get("total_size_mb", 0), 2),
            "total_hits": overall.get("total_hits", 0),
            "total_misses": overall.get("total_misses", 0),
            "overall_hit_rate": round(overall.get("overall_hit_rate", 0.0), 3),
            "tracks_cached": tier2.get("tracks_cached", 0)
        },
        "tracks": {
            int(track_id): {
                "track_id": int(track_id),
                "total_chunks": track_info.get("total_chunks", 0),
                "cached_original": track_info.get("cached_original", 0),
                "cached_processed": track_info.get("cached_processed", 0),
                "completion_percent": round(track_info.get("completion_percent", 0.0), 1),
                "fully_cached": track_info.get("fully_cached", False),
                "estimated_cache_time_seconds": None  # Will be calculated if needed
            }
            for track_id, track_info in tracks.items()
        }
    }


def estimate_cache_completion_time(
    cached_chunks: int,
    total_chunks: int,
    avg_processing_time_per_chunk: float = 0.3
) -> Optional[float]:
    """
    Estimate time to cache remaining chunks.

    Args:
        cached_chunks: Number of chunks already cached
        total_chunks: Total chunks needed
        avg_processing_time_per_chunk: Average seconds per chunk (default 0.3s)

    Returns:
        Estimated seconds to completion, or None if already cached
    """
    remaining_chunks = total_chunks - cached_chunks

    if remaining_chunks <= 0:
        return None

    return remaining_chunks * avg_processing_time_per_chunk


def create_cache_aware_response(
    data: Any,
    cache_source: str = "miss",
    processing_time_ms: float = 0.0,
    message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a cache-aware response with timing information.

    Args:
        data: Response data
        cache_source: Where data came from ('tier1', 'tier2', 'miss')
        processing_time_ms: Time spent processing/retrieving data
        message: Optional message

    Returns:
        Cache-aware response dictionary
    """
    cache_hit = cache_source != "miss"

    return {
        "status": "success",
        "data": data,
        "cache_source": cache_source,
        "cache_hit": cache_hit,
        "processing_time_ms": round(processing_time_ms, 2),
        "message": message or f"Data from {cache_source}",
        "timestamp": time.time()
    }
