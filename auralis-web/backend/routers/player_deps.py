"""
Player Router Dependency Wiring

The Depends() providers every /api/player handler resolves its services
through (#4670), shared by the routers/player.py modules (#5472).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from typing import Any

from fastapi import Depends

from services import (
    NavigationService,
    PlaybackService,
    QueueService,
    RecommendationService,
)

from .dependencies import RouterDeps


# ============================================================================
# DEPENDENCY WIRING (#4670)
#
# create_player_router() used to be a 515-line closure: every /api/player
# handler was nested inside it purely to reach get_library_database/get_audio_player/
# etc. via closure capture, which made a handler impossible to import or
# call without first building the whole router. Handlers are now module
# level; they reach the same callables through FastAPI Depends() instead.
#
# _PlayerDeps holds the raw callables/objects one create_player_router() call
# received. It is bound per router instance through RouterDeps
# (dependencies.py): a router-level dependency publishes it for the duration of
# a request, so a second factory call (every test that builds its own player
# router) cannot repoint the live router at its stubs (#5262, #5762). It does
# NOT reproduce the #4361 module-level-`APIRouter()` hazard, since the router
# instance itself is built fresh, per call, inside the factory.
#
# A handler's Depends() default is only consulted when FastAPI itself
# invokes it for a real request; a direct unit-test call passes the
# service/dependency explicitly as a keyword argument and never touches
# _PlayerDeps at all -- that's the seam #4670 asked for.
# ============================================================================


def _unavailable() -> Any:
    """Getter used before any router has been built: resolves to nothing."""
    return None


class _PlayerDeps:
    def __init__(
        self,
        get_library_database: Callable[[], Any] = _unavailable,
        get_audio_player: Callable[[], Any] = _unavailable,
        get_player_state_manager: Callable[[], Any] = _unavailable,
        connection_manager: Any = None,
        create_track_info_fn: Callable[[Any], Any] = lambda _track: None,
    ) -> None:
        self.get_library_database = get_library_database
        self.get_audio_player = get_audio_player
        self.get_player_state_manager = get_player_state_manager
        self.connection_manager = connection_manager
        self.create_track_info_fn = create_track_info_fn


_deps = RouterDeps("player", _PlayerDeps())


def _get_audio_player() -> Any:
    return _deps.current().get_audio_player()


def _get_library_database() -> Any:
    return _deps.current().get_library_database()


def _get_player_state_manager() -> Any:
    return _deps.current().get_player_state_manager()


def _get_connection_manager() -> Any:
    return _deps.current().connection_manager


def _get_playback_service(
    audio_player: Any = Depends(_get_audio_player),
    player_state_manager: Any = Depends(_get_player_state_manager),
    connection_manager: Any = Depends(_get_connection_manager),
) -> PlaybackService:
    """Lazy service initialization"""
    return PlaybackService(
        audio_player=audio_player,
        player_state_manager=player_state_manager,
        connection_manager=connection_manager,
    )


def _get_queue_service(
    audio_player: Any = Depends(_get_audio_player),
    player_state_manager: Any = Depends(_get_player_state_manager),
    library_database: Any = Depends(_get_library_database),
    connection_manager: Any = Depends(_get_connection_manager),
) -> QueueService:
    """Lazy service initialization"""
    return QueueService(
        audio_player=audio_player,
        player_state_manager=player_state_manager,
        library_database=library_database,
        connection_manager=connection_manager,
        create_track_info_fn=_deps.current().create_track_info_fn,
    )


def _get_recommendation_service(
    connection_manager: Any = Depends(_get_connection_manager),
) -> RecommendationService:
    """Lazy service initialization"""
    return RecommendationService(connection_manager=connection_manager)


def _get_navigation_service(
    audio_player: Any = Depends(_get_audio_player),
    player_state_manager: Any = Depends(_get_player_state_manager),
    connection_manager: Any = Depends(_get_connection_manager),
) -> NavigationService:
    """Lazy service initialization"""
    return NavigationService(
        audio_player=audio_player,
        player_state_manager=player_state_manager,
        connection_manager=connection_manager,
        create_track_info_fn=_deps.current().create_track_info_fn,
    )


