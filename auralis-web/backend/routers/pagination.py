"""
Shared pagination utilities and response models for routers.

This module consolidates pagination logic that appears across multiple routers,
reducing boilerplate and ensuring consistency.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic paginated response model with consistent structure.

    This eliminates the duplication of pagination fields and has_more calculation
    that appears in 6+ router response models.

    Type Parameters:
        T: The type of items in the paginated list

    Attributes:
        items: List of items for the current page
        total: Total number of items across all pages
        offset: Number of items skipped (pagination offset)
        limit: Maximum number of items per page
        has_more: Whether more items are available beyond current page

    Example:
        ```python
        class ArtistResponse(BaseModel):
            id: int
            name: str

        @router.get("/api/artists")
        async def get_artists(limit: int = 50, offset: int = 0):
            artists, total = repos.artists.get_all(limit=limit, offset=offset)
            return PaginatedResponse.create(
                items=artists,
                total=total,
                limit=limit,
                offset=offset
            )
        ```
    """
    items: list[T] = Field(..., description="List of items for current page")
    total: int = Field(..., description="Total number of items across all pages", ge=0)
    offset: int = Field(..., description="Number of items skipped", ge=0)
    limit: int = Field(..., description="Maximum items per page", ge=1)
    has_more: bool = Field(..., description="Whether more items are available")

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        limit: int,
        offset: int
    ) -> PaginatedResponse[T]:
        """
        Create a paginated response with automatic has_more calculation.

        This factory method ensures consistent has_more logic across all endpoints.

        Args:
            items: List of items for the current page
            total: Total count of items across all pages
            limit: Maximum items per page
            offset: Number of items skipped

        Returns:
            PaginatedResponse instance with has_more calculated

        Note:
            has_more is calculated as: (offset + limit) < total
        """
        return cls(
            items=items,
            total=total,
            offset=offset,
            limit=limit,
            has_more=(offset + limit) < total
        )


class PaginationParams:
    """
    Standard pagination parameters with validation.

    This provides a consistent way to handle pagination query parameters
    across all endpoints.

    Attributes:
        limit: Maximum number of items to return (1-200, default 50)
        offset: Number of items to skip (0+, default 0)

    Example:
        ```python
        @router.get("/api/artists")
        async def get_artists(
            limit: int = Query(50, ge=1, le=200),
            offset: int = Query(0, ge=0)
        ):
            # Use limit and offset directly
            artists, total = repos.artists.get_all(limit=limit, offset=offset)
        ```
    """
    DEFAULT_LIMIT = 50
    MAX_LIMIT = 200
    MIN_LIMIT = 1
    DEFAULT_OFFSET = 0
    MIN_OFFSET = 0
