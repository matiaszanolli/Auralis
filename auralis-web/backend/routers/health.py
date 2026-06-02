"""
Health Router
~~~~~~~~~~~~~

System health and version endpoints, extracted from the WebSocket system router
to keep infrastructure routes separate from real-time communication.

Endpoints:
- GET /api/health   - Liveness check
- GET /api/version  - Detailed version information

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging

from fastapi import APIRouter
from schemas import HealthResponse, VersionInfoResponse

logger = logging.getLogger(__name__)


def create_health_router(
    HAS_AURALIS: bool,
) -> APIRouter:
    """Factory: health and version routes."""
    router = APIRouter(tags=["system"])

    @router.get("/api/health", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        """Liveness check."""
        return HealthResponse(status="healthy", auralis_available=HAS_AURALIS)

    @router.get("/api/version", response_model=VersionInfoResponse)
    async def get_version() -> VersionInfoResponse:
        """Get version information.

        Returns detailed version info including semantic version components,
        build date, API version, and database schema version.
        """
        try:
            from auralis.version import get_version_info
            return VersionInfoResponse(**get_version_info())
        except ImportError:
            logger.warning("auralis.version not available, using fallback")
            # Keep in sync with auralis/version.py — the single source of truth (fixes #2335).
            return VersionInfoResponse(
                version="1.2.1-beta.1",
                major=1,
                minor=2,
                patch=1,
                prerelease="beta.1",
                build="",
                build_date="2026-02-20",
                git_commit="",
                api_version="v1",
                db_schema_version=3,
                display="Auralis v1.2.1-beta.1",
            )

    return router
