"""
Shared dependency injection and validation utilities for routers.

This module consolidates common dependency checks that appear across multiple routers,
reducing boilerplate and improving consistency.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from fastapi import HTTPException
import logging
import warnings
import functools
from typing import Callable, Any, cast, TypeVar, ParamSpec
from auralis import EnhancedAudioPlayer
from auralis.library import LibraryManager
from .errors import handle_query_error

logger = logging.getLogger(__name__)

# Type variables for generic decorator support
P = ParamSpec('P')
T = TypeVar('T')


def require_library_manager(get_library_manager: Callable[[], Any]) -> LibraryManager:
    """
    Validate that library manager is available.

    .. deprecated:: 1.1.0
        Use :func:`require_repository_factory` instead. LibraryManager will be
        removed in version 2.0.0. See MIGRATION_GUIDE.md for migration instructions.

    Args:
        get_library_manager: Callable that returns LibraryManager instance

    Returns:
        LibraryManager: The library manager instance

    Raises:
        HTTPException: 503 if library manager is not available
    """
    warnings.warn(
        "require_library_manager is deprecated and will be removed in v2.0.0. "
        "Use require_repository_factory instead. "
        "See MIGRATION_GUIDE.md for migration instructions.",
        DeprecationWarning,
        stacklevel=2
    )
    library_manager = get_library_manager()
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")
    return cast(LibraryManager, library_manager)


def require_audio_player(get_audio_player: Callable[[], Any]) -> EnhancedAudioPlayer:
    """
    Validate that audio player is available.

    Args:
        get_audio_player: Callable that returns EnhancedAudioPlayer instance

    Returns:
        EnhancedAudioPlayer: The audio player instance

    Raises:
        HTTPException: 503 if audio player is not available
    """
    audio_player = get_audio_player()
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")
    return cast(EnhancedAudioPlayer, audio_player)


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
        raise HTTPException(status_code=503, detail="Player state manager not available")
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
        raise HTTPException(status_code=503, detail="Connection manager not available")
    return connection_manager


def require_repository_factory(get_repository_factory: Callable[[], Any]) -> Any:
    """
    Validate that repository factory is available.

    This is the Phase 2 dependency injection mechanism that enables
    gradual migration from LibraryManager to direct repository usage.

    Args:
        get_repository_factory: Callable that returns RepositoryFactory instance

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
    repository_factory = get_repository_factory()
    if not repository_factory:
        raise HTTPException(
            status_code=503,
            detail="Repository factory not available"
        )
    return repository_factory


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
