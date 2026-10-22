"""
Shared dependency injection and validation utilities for routers.

This module consolidates common dependency checks that appear across multiple routers,
reducing boilerplate and improving consistency.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import functools
import logging
from typing import Any, ParamSpec, TypeVar, cast
from collections.abc import Callable

from fastapi import HTTPException

from auralis import AudioPlayer

from .errors import (
    AudioPlayerUnavailableError,
    ConnectionManagerUnavailableError,
    PlayerStateUnavailableError,
    ServiceUnavailableError,
    handle_query_error,
)

logger = logging.getLogger(__name__)

# Type variables for generic decorator support
P = ParamSpec('P')
T = TypeVar('T')


def require_audio_player(get_audio_player: Callable[[], Any]) -> AudioPlayer:
    """
    Validate that audio player is available.

    Args:
        get_audio_player: Callable that returns AudioPlayer instance

    Returns:
        AudioPlayer: The audio player instance

    Raises:
        HTTPException: 503 if audio player is not available
    """
    audio_player = get_audio_player()
    if not audio_player:
        raise AudioPlayerUnavailableError()
    return cast(AudioPlayer, audio_player)


def require_player_state_manager(get_player_state_manager: Callable[[], Any]) -> Any:
    """
    Validate that player state manager is available.

    Args:
        get_player_state_manager: Callable that returns PlayerStateManager instance

    Returns:
        PlayerStateManager: The player state manager instance

    Raises:
        HTTPException: 503 if player state manager is not available
    """
    state_manager = get_player_state_manager()
    if not state_manager:
        raise PlayerStateUnavailableError()
    return state_manager


def require_connection_manager(connection_manager: Any) -> Any:
    """
    Validate that WebSocket connection manager is available.

    Args:
        connection_manager: WebSocket connection manager instance

    Returns:
        ConnectionManager: The connection manager instance

    Raises:
        HTTPException: 503 if connection manager is not available
    """
    if not connection_manager:
        raise ConnectionManagerUnavailableError()
    return connection_manager


def require_repository_factory(get_repository_factory: Callable[[], Any] | None) -> Any:
    """
    Validate that repository factory is available.

    This is the Phase 2 dependency injection mechanism that enabled the
    migration from the since-deleted LibraryManager facade (#4915) to
    direct repository usage.

    Args:
        get_repository_factory: Callable that returns RepositoryFactory instance
            (or None when the dependency was never wired)

    Returns:
        RepositoryFactory: The repository factory instance

    Raises:
        HTTPException: 503 if repository factory is not available

    Example:
        ```python
        @router.get("/api/tracks")
        async def get_tracks(factory_getter=Depends(get_repository_factory)):
            repos = require_repository_factory(factory_getter)
            tracks, total = repos.tracks.get_all(limit=50)
            return {"tracks": tracks, "total": total}
        ```
    """
    # A missing getter (deps not wired) is the same outage as a getter that
    # returns nothing, so both take the one 503 spelling.
    return require_service(
        get_repository_factory() if get_repository_factory else None,
        "Repository factory",
    )



def require_service(service: T | None, name: str) -> T:
    """Return ``service`` or raise the canonical 503 ``"<name> not available"``.

    The one spelling of "a backend service this endpoint needs is missing"
    (#5783). Routers used to re-type the ``HTTPException(503, ...)`` inline, and
    the wording had already drifted. Truthiness, not ``is None``, matches the
    existing ``require_*`` helpers: an empty/falsy service is as unusable as an
    absent one.

    Raises:
        ServiceUnavailableError: 503 with ``f"{name} not available"``
    """
    if not service:
        raise ServiceUnavailableError(f"{name} not available")
    return service


def require_processing_engine(engine: T | None) -> T:
    """503 unless the processing engine is up (used by the /api/processing routes)."""
    return require_service(engine, "Processing engine")


def with_error_handling(operation: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator that standardizes error handling for router endpoints.

    This decorator wraps endpoint functions to:
    1. Pass through HTTPException unchanged (for proper status codes)
    2. Convert all other exceptions to standardized InternalServerError

    This eliminates the boilerplate try/except pattern that appears in 60+
    router endpoints across the codebase.

    Args:
        operation: Description of the operation (e.g., "fetch artists", "get album")

    Returns:
        Decorator function that wraps async endpoint functions

    Example:
        ```python
        @router.get("/api/artists")
        @with_error_handling("fetch artists")
        async def get_artists(limit: int = 50):
            repos = require_repository_factory(get_repository_factory)
            artists, total = repos.artists.get_all(limit=limit)
            return {"artists": artists, "total": total}
        ```

    Note:
        This replaces the pattern:
        ```python
        try:
            # endpoint logic
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("operation", e)
        ```
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                # Type checker can't understand runtime coroutine check below (line 208)
                return await func(*args, **kwargs)  # type: ignore[misc, no-any-return]
            except HTTPException:
                # Pass through HTTP exceptions unchanged for proper status codes
                raise
            except Exception as e:
                # Convert all other exceptions to standardized error response
                raise handle_query_error(operation, e)

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                raise handle_query_error(operation, e)

        # Return appropriate wrapper based on whether function is async
        import inspect
        if inspect.iscoroutinefunction(func):
            return cast(Callable[P, T], async_wrapper)
        else:
            return cast(Callable[P, T], sync_wrapper)

    return decorator
