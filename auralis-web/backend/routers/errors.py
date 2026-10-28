"""
Centralized error handling and exception definitions for routers.

This module consolidates common HTTP exceptions and error patterns used across
the backend, reducing boilerplate and improving consistency.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import Any, NoReturn

from fastapi import HTTPException

logger = logging.getLogger(__name__)


class ServiceUnavailableError(HTTPException):
    """Service temporarily unavailable (503 Service Unavailable)"""
    def __init__(self, detail: str = "Service temporarily unavailable") -> None:
        super().__init__(status_code=503, detail=detail)


class NotFoundError(HTTPException):
    """Resource not found (404 Not Found)"""
    def __init__(
        self, resource_type: str, resource_id: Any | None = None, *, detail: str | None = None
    ) -> None:
        if detail is None:
            if resource_id is not None:
                detail = f"{resource_type} {resource_id} not found"
            else:
                detail = f"{resource_type} not found"
        super().__init__(status_code=404, detail=detail)


class BadRequestError(HTTPException):
    """Invalid request (400 Bad Request)"""
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=400, detail=detail)


class UnprocessableAudioFileError(HTTPException):
    """The track's file exists but mutagen cannot read it (422 Unprocessable Entity).

    The detail is fixed: exception text names the absolute file path (#5993).
    """
    def __init__(self) -> None:
        super().__init__(status_code=422, detail="Unreadable or unsupported audio file")


class InternalServerError(HTTPException):
    """Internal server error (500 Internal Server Error)"""
    def __init__(self, operation: str, error: Exception | None = None) -> None:
        detail = f"Failed to {operation}"
        if error:
            logger.error(f"Internal error during {operation}: {error}", exc_info=True)
        else:
            logger.error(f"Internal error during {operation}")
        super().__init__(status_code=500, detail=detail)


class LibraryUnavailableError(ServiceUnavailableError):
    """Library service unavailable"""
    def __init__(self) -> None:
        super().__init__("Library not available")


class AudioPlayerUnavailableError(ServiceUnavailableError):
    """Audio player service unavailable"""
    def __init__(self) -> None:
        super().__init__("Audio player not available")


def raise_for_service_error(error: ValueError, operation: str) -> NoReturn:
    """
    Map a service-layer failure to its HTTP status by exception TYPE (#4700).

    Replaces the substring sniffing the queue handlers used to do
    (``400 if "valid" in str(e) else ...``), which reported every
    service-outage condition as 400 Bad Request and re-broke whenever a
    message was reworded.

    Args:
        operation: Description of the failed operation, used for the 500 detail
            (e.g. "set queue")
        error: The service-layer exception, normally a ``ServiceError`` subclass

    Raises:
        HTTPException: 503 unavailable, 404 not found, 400 invalid request,
            500 operation failure. A plain ``ValueError`` from a not-yet-typed
            raiser keeps the historical 400 default.
    """
    from services.errors import (
        InvalidRequest,
        OperationFailed,
        ResourceNotFound,
        ServiceUnavailable,
    )

    if isinstance(error, ServiceUnavailable):
        raise ServiceUnavailableError(str(error))
    if isinstance(error, ResourceNotFound):
        raise NotFoundError("Resource", detail=str(error))
    if isinstance(error, InvalidRequest):
        raise BadRequestError(str(error))
    if isinstance(error, OperationFailed):
        raise InternalServerError(operation, error)

    # Untyped ValueError — historical behaviour was 400 with the raw message.
    raise BadRequestError(str(error))


def handle_query_error(operation: str, error: Exception) -> NoReturn:
    """
    Centralized error handler for query operations.

    Maps transient SQLite/SQLAlchemy errors to HTTP 503 (retryable), a vanished or
    unreadable file to 404 / 403 (#5081), and reserves HTTP 500 for truly
    unexpected failures (#3222).

    Args:
        operation: Description of the operation that failed (e.g., "get tracks")
        error: The exception that was raised

    Raises:
        HTTPException: 503 for transient DB errors, 404 / 403 for a missing /
            unreadable file, 500 for others

    Example:
        try:
            tracks = library_database.get_all_tracks()
        except Exception as e:
            raise handle_query_error("get tracks", e)
    """
    logger.error(f"Query error during {operation}: {error}", exc_info=True)

    # Transient SQLite errors → 503 so clients know to retry
    from sqlalchemy.exc import OperationalError
    if isinstance(error, OperationalError):
        raise ServiceUnavailableError(f"Database temporarily unavailable during {operation}")

    # Filesystem races under a handler (a file removed or locked between the DB
    # lookup and the read) are not server bugs, mirroring core/job_error_mapping's
    # FileNotFoundError / PermissionError categories (#5081). Fixed details: the
    # exception text names the absolute path. FileNotFoundError and
    # PermissionError are OSErrors, so they must be tested before any broader catch.
    if isinstance(error, FileNotFoundError):
        raise NotFoundError("File")
    if isinstance(error, PermissionError):
        raise HTTPException(status_code=403, detail="Permission denied")

    raise InternalServerError(operation, error)
