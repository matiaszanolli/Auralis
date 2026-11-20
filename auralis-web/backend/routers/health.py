"""
Health Router
~~~~~~~~~~~~~

System health and version endpoints, extracted from the WebSocket system router
to keep infrastructure routes separate from real-time communication.

Endpoints:
- GET /api/health   - Liveness check
- GET /api/ready    - Engine and library readiness
- GET /api/version  - Detailed version information

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import os
from collections.abc import Callable
from typing import Any

from auralis.analysis.fingerprint.rust_fingerprint import fingerprint_engine_error
from auralis.version import get_version_info
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from schemas import HealthResponse, VersionInfoResponse

from .dependencies import RouterDeps


class _HealthDeps:
    def __init__(
        self,
        has_auralis: bool = False,
        get_library_database: Callable[[], Any] | None = None,
        get_player_state_manager: Callable[[], Any] | None = None,
    ) -> None:
        self.has_auralis = has_auralis
        self.get_library_database = get_library_database
        self.get_player_state_manager = get_player_state_manager

    def library_available(self) -> bool:
        return self.has_auralis and (
            self.get_library_database is not None and self.get_library_database() is not None
        )


_deps = RouterDeps("health", _HealthDeps())


def _get_deps() -> _HealthDeps:
    return _deps.current()


async def health_check(deps: _HealthDeps = Depends(_get_deps)) -> HealthResponse:
    """Liveness check, plus whether the engine is actually usable.

    #4684: ``auralis_available`` used to echo the import-time HAS_AURALIS
    flag, which was a hardcoded True — so a backend whose Auralis init had
    failed and rolled every component back to None (#3812) still reported
    itself available while every data route returned 503. It now also
    requires the live library database to exist.

    ``status`` stays "healthy" with HTTP 200 for existing liveness callers.
    """
    return HealthResponse(status="healthy", auralis_available=deps.library_available(),
                          fingerprint_engine_available=fingerprint_engine_error() is None)


async def readiness_check(deps: _HealthDeps = Depends(_get_deps)) -> JSONResponse:
    ready = (
        deps.library_available()
        and deps.get_player_state_manager is not None
        and deps.get_player_state_manager() is not None
        and fingerprint_engine_error() is None
    )
    headers = {"Cache-Control": "no-store"}
    # Supervisors check this against the value given to their child. A server
    # that wins a port-bind race cannot accidentally satisfy their probe.
    if launch_id := os.environ.get("AURALIS_LAUNCH_ID"):
        headers["X-Auralis-Launch-Id"] = launch_id
    return JSONResponse({"ready": ready}, status_code=200 if ready else 503, headers=headers)


async def get_version() -> VersionInfoResponse:
    """Get version information.

    Returns detailed version info including semantic version components,
    build date and database schema version.
    """
    return VersionInfoResponse(**get_version_info())


def create_health_router(
    HAS_AURALIS: bool,
    get_library_database: Callable[[], Any] | None = None,
    get_player_state_manager: Callable[[], Any] | None = None,
) -> APIRouter:
    """Factory: liveness, readiness, and version routes."""
    deps = _HealthDeps(HAS_AURALIS, get_library_database, get_player_state_manager)
    router = APIRouter(tags=["system"], dependencies=[Depends(_deps.bind(deps))])
    router.add_api_route("/api/health", health_check, methods=["GET"], response_model=HealthResponse)
    router.add_api_route("/api/ready", readiness_check, methods=["GET"])
    router.add_api_route("/api/version", get_version, methods=["GET"], response_model=VersionInfoResponse)
    return router
