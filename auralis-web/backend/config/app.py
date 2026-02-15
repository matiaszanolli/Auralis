"""
FastAPI Application Factory

Creates and configures the FastAPI application instance with metadata,
documentation URLs, and default settings.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from typing import Any

from fastapi import FastAPI


def create_app(lifespan: Any = None) -> FastAPI:
    """
    Create and configure FastAPI application.

    Args:
        lifespan: Optional async context manager for startup/shutdown handling

    Returns:
        Configured FastAPI instance with metadata and documentation URLs
    """
    app = FastAPI(
        title="Auralis Web API",
        description="Modern web backend for Auralis audio processing",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    return app
