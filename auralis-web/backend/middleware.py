"""
API Middleware
~~~~~~~~~~~~~~

Middleware for request/response validation, error handling, and cross-cutting concerns.

Phase B.1: Backend Endpoint Standardization

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
import time
from typing import Any
from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from fastapi.applications import FastAPI
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from schemas import ErrorResponse, ErrorType
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


class ValidationErrorMiddleware(BaseHTTPMiddleware):
    """
    Middleware to catch and standardize validation errors.
    Converts Pydantic ValidationError to standardized ErrorResponse.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        try:
            response = await call_next(request)
            return response
        except ValidationError as e:
            error_response = ErrorResponse(
                status="error",
                error=ErrorType.VALIDATION_ERROR,
                message="Request validation failed",
                details={
                    "errors": [
                        {
                            "field": str(err["loc"][-1]),
                            "type": err["type"],
                            "message": err["msg"]
                        }
                        for err in e.errors()
                    ]
                }
            )
            return JSONResponse(
                status_code=422,
                content=error_response.model_dump()
            )
        except RequestValidationError as e:
            error_response = ErrorResponse(
                status="error",
                error=ErrorType.VALIDATION_ERROR,
                message="Request validation failed",
                details={
                    "errors": [
                        {
                            "field": str(err["loc"][-1]),
                            "type": err["type"],
                            "message": err["msg"]
                        }
                        for err in e.errors()
                    ]
                }
            )
            return JSONResponse(
                status_code=422,
                content=error_response.model_dump()
            )


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to catch and standardize HTTP exceptions.
    Converts HTTPException to standardized ErrorResponse.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        try:
            response = await call_next(request)
            return response
        except HTTPException as e:
            error_response = ErrorResponse(
                status="error",
                error=self._get_error_type(e.status_code),
                message=e.detail or "An error occurred"
            )
            return JSONResponse(
                status_code=e.status_code,
                content=error_response.model_dump()
            )
        except Exception as e:
            logger.exception(f"Unhandled exception: {e}")
            error_response = ErrorResponse(
                status="error",
                error=ErrorType.INTERNAL_ERROR,
                message="Internal server error"
            )
            return JSONResponse(
                status_code=500,
                content=error_response.model_dump()
            )

    @staticmethod
    def _get_error_type(status_code: int) -> str:
        """Map HTTP status code to error type."""
        status_map = {
            400: ErrorType.VALIDATION_ERROR,
            401: ErrorType.UNAUTHORIZED,
            403: ErrorType.FORBIDDEN,
            404: ErrorType.NOT_FOUND,
            409: ErrorType.CONFLICT,
            503: ErrorType.SERVICE_UNAVAILABLE,
            504: ErrorType.TIMEOUT,
        }
        return status_map.get(status_code, ErrorType.INTERNAL_ERROR)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware.
    Limits requests per client based on IP address.
    """

    def __init__(self, app: Any, requests_per_minute: int = 100) -> None:
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_log: dict[str, list[tuple[float, int]]] = {}  # {ip: [(timestamp, request_count)]}

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        minute_ago = now - 60

        # Clean old entries
        if client_ip in self.request_log:
            self.request_log[client_ip] = [
                (ts, count) for ts, count in self.request_log[client_ip]
                if ts > minute_ago
            ]

        # Count requests in last minute
        if client_ip not in self.request_log:
            self.request_log[client_ip] = []

        total_requests = sum(count for ts, count in self.request_log[client_ip])

        if total_requests >= self.requests_per_minute:
            error_response = ErrorResponse(
                status="error",
                error="rate_limit_exceeded",
                message=f"Rate limit exceeded: {self.requests_per_minute} requests per minute"
            )
            return JSONResponse(
                status_code=429,
                content=error_response.model_dump(),
                headers={"Retry-After": "60"}
            )

        # Record this request
        self.request_log[client_ip].append((now, 1))

        response = await call_next(request)
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all requests and responses.
    Includes timing information.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start_time = time.time()
        request_id = request.headers.get("X-Request-ID", "unknown")

        # Log request
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )

        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            # Log response
            logger.info(
                f"[{request_id}] {request.method} {request.url.path} "
                f"completed with {response.status_code} in {process_time:.2f}s"
            )

            response.headers["X-Process-Time"] = str(process_time)
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"[{request_id}] {request.method} {request.url.path} "
                f"failed after {process_time:.2f}s: {e}"
            )
            raise


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request ID to all requests.
    Useful for tracing and debugging.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        import uuid

        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class CORSPreflightMiddleware(BaseHTTPMiddleware):
    """
    Simplified CORS handling middleware.
    Works alongside FastAPI's CORSMiddleware for better control.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.method == "OPTIONS":
            return JSONResponse(
                status_code=200,
                content={},
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization",
                }
            )

        response = await call_next(request)
        return response


def setup_middleware(app: FastAPI) -> None:
    """
    Setup all middleware for the FastAPI application.
    Order matters: request processing goes bottom-to-top.
    """
    # Add middleware in order (last added = first executed on request)
    app.add_middleware(CORSPreflightMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=100)
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(ValidationErrorMiddleware)
