"""
Centralized error handling and exception definitions for routers.

This module consolidates common HTTP exceptions and error patterns used across
the backend, reducing boilerplate and improving consistency.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
from typing import Any, NoReturn, Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)


class ServiceUnavailableError(HTTPException):
    """Service temporarily unavailable (503 Service Unavailable)"""
    def __init__(self, detail: str = "Service temporarily unavailable") -> None:
        super().__init__(status_code=503, detail=detail)


class NotFoundError(HTTPException):
    """Resource not found (404 Not Found)"""
    def __init__(self, resource_type: str, resource_id: Optional[Any] = None) -> None:
        if resource_id is not None:
            detail = f"{resource_type} {resource_id} not found"
        else:
            detail = f"{resource_type} not found"
        super().__init__(status_code=404, detail=detail)


class BadRequestError(HTTPException):
    """Invalid request (400 Bad Request)"""
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=400, detail=detail)


class InternalServerError(HTTPException):
    """Internal server error (500 Internal Server Error)"""
    def __init__(self, operation: str, error: Optional[Exception] = None) -> None:
        if error:
            detail = f"Failed to {operation}: {str(error)}"
            logger.error(f"Internal error during {operation}: {error}", exc_info=True)
        else:
            detail = f"Failed to {operation}"
            logger.error(f"Internal error during {operation}")
        super().__init__(status_code=500, detail=detail)


class LibraryManagerUnavailableError(ServiceUnavailableError):
    """Library manager service unavailable"""
    def __init__(self) -> None:
        super().__init__("Library manager not available")


class AudioPlayerUnavailableError(ServiceUnavailableError):
    """Audio player service unavailable"""
    def __init__(self) -> None:
        super().__init__("Audio player not available")


class PlayerStateUnavailableError(ServiceUnavailableError):
    """Player state manager service unavailable"""
    def __init__(self) -> None:
        super().__init__("Player state manager not available")


class ConnectionManagerUnavailableError(ServiceUnavailableError):
    """Connection manager service unavailable"""
    def __init__(self) -> None:
        super().__init__("Connection manager not available")


def handle_query_error(operation: str, error: Exception) -> NoReturn:
    """
    Centralized error handler for query operations.

    Args:
        operation: Description of the operation that failed (e.g., "get tracks")
        error: The exception that was raised

    Raises:
        HTTPException: 500 with standardized error message

    Example:
        try:
            tracks = library_manager.get_all_tracks()
        except Exception as e:
            raise handle_query_error("get tracks", e)
    """
    logger.error(f"Query error during {operation}: {error}", exc_info=True)
    raise InternalServerError(operation, error)
