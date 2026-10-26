"""
Enhancement Router
~~~~~~~~~~~~~~~~~~

Handles real-time audio enhancement settings for the player.

Endpoints:
- POST /api/player/enhancement/toggle - Enable/disable enhancement
- POST /api/player/enhancement/preset - Change enhancement preset
- POST /api/player/enhancement/intensity - Adjust enhancement intensity
- GET /api/player/enhancement/status - Get current enhancement settings

Split by responsibility (#5831). This module is the coordinator:
create_enhancement_router() registers every route, and every handler, model and
provider is re-exported here so `from routers.enhancement import X` and
dependency_overrides keyed on routers.enhancement providers keep working.
- enhancement_models.py          request/response bodies
- enhancement_deps.py            per-router dependency binding + Depends() providers
- enhancement_controls.py        toggle / preset / intensity / status handlers
- enhancement_recommendation.py  mastering-recommendation handler

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends
from schemas import (
    MasteringRecommendationResponse,
)

from .enhancement_models import EnhancementSettings, EnhancementSettingsResponse
from .enhancement_deps import _EnhancementDeps, _deps
from .enhancement_recommendation import (
    get_mastering_recommendation,
)
from .enhancement_controls import (
    get_enhancement_status,
    set_enhancement_intensity,
    set_enhancement_preset,
    toggle_enhancement,
)

logger = logging.getLogger(__name__)

# EnhancementPresetLiteral is the single source of truth in schemas.py (#4424),
# imported above. It drives OpenAPI so the preset constraint shows up in the docs,
# not just as a free-form string (#3549 / BE-NEW-91).


# ============================================================================
# DEPENDENCY WIRING (#4670)
#
# create_enhancement_router() used to be a 380-line closure: every handler
# below was nested inside it purely to reach get_enhancement_settings/
# connection_manager/get_player_state_manager/etc. via closure capture, which
# made a handler impossible to import or call without first building the whole
# router. Handlers are now module level; they reach the same dependencies
# through FastAPI Depends() instead.
#
# _EnhancementDeps holds the raw callables/objects one create_enhancement_router()
# call received. It is bound per router instance through RouterDeps
# (dependencies.py): a router-level dependency publishes it for the duration of
# a request, so a second factory call (every test that builds its own router)
# cannot repoint the live router at its stubs (#5262, #5762). It does NOT
# reproduce the #4361 module-level-`APIRouter()` hazard -- the router instance
# itself is built fresh, per call, inside the factory below.
#
# A handler's Depends() default is only consulted when FastAPI itself invokes
# it for a real request; a direct unit-test call passes the dependency
# explicitly as a keyword argument and never touches _EnhancementDeps at all
# -- that's the seam #4670 asked for.
#
# The optional dependencies (player state manager, streamlined cache,
# repository factory) resolve to None when the factory was not given the
# corresponding callable, so the handlers' original "is it wired up at all?"
# guards become plain truthiness checks on the resolved object.
# ============================================================================


# Moved to routers/processing_api.py (#5073): GET /api/processing/parameters
# was owned by this router but registered unconditionally, unlike its 8
# HAS_PROCESSING-gated siblings under the same /api/processing prefix. It
# now lives on create_processing_router() so ownership, gating, and the
# OpenAPI "audio-processing" tag are consistent with the rest of that
# namespace.


def create_enhancement_router(
    get_enhancement_settings: Callable[[], dict[str, Any]],
    connection_manager: Any,
    get_streamlined_cache: Callable[[], Any] | None = None,
    get_player_state_manager: Callable[[], Any] | None = None,
    get_repository_factory: Callable[[], Any] | None = None,
) -> APIRouter:
    """
    Factory function to create enhancement router with dependencies.

    Args:
        get_enhancement_settings: Callable that returns enhancement settings dict
        connection_manager: WebSocket connection manager for broadcasts
        get_player_state_manager: Optional callable that returns PlayerStateManager
        get_repository_factory: Optional callable that returns RepositoryFactory

    Returns:
        APIRouter: Configured router instance
    """
    deps = _EnhancementDeps(
        get_enhancement_settings=get_enhancement_settings,
        connection_manager=connection_manager,
        get_streamlined_cache=get_streamlined_cache,
        get_player_state_manager=get_player_state_manager,
        get_repository_factory=get_repository_factory,
    )

    router = APIRouter(tags=["enhancement"], dependencies=[Depends(_deps.bind(deps))])

    router.add_api_route("/api/player/enhancement/toggle", toggle_enhancement, methods=["POST"], response_model=EnhancementSettingsResponse)
    router.add_api_route("/api/player/enhancement/preset", set_enhancement_preset, methods=["POST"], response_model=EnhancementSettingsResponse)
    router.add_api_route("/api/player/enhancement/intensity", set_enhancement_intensity, methods=["POST"], response_model=EnhancementSettingsResponse)
    router.add_api_route("/api/player/enhancement/status", get_enhancement_status, methods=["GET"], response_model=EnhancementSettings)
    router.add_api_route(
        "/api/player/mastering/recommendation/{track_id}",
        get_mastering_recommendation,
        methods=["GET"],
        response_model=MasteringRecommendationResponse,
    )

    return router
