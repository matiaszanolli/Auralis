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
            # Derived fallback for degraded builds that cannot import the core.
            # sync_version.py keeps this aligned with auralis/version.py.
            # db_schema_version is sourced directly from auralis/__version__.py
            # (which has no heavy transitive deps) rather than hardcoded, so this
            # can never drift from the live value again (#4053, #5072).
            from auralis.__version__ import __db_schema_version__

            return VersionInfoResponse(
                version="1.5.1",
                major=1,
                minor=5,
                patch=1,
                prerelease="",
                build="",
                build_date="2026-07-24",
                git_commit="",
                api_version="v1",
                db_schema_version=__db_schema_version__,
                display="Auralis v1.5.1",
            )

    return router
