"""
Player Router Dependency Wiring

The Depends() providers every /api/player handler resolves its services
through (#4670), shared by routers/player.py, player_queue.py and
player_queue_history.py (#5472).

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

from .errors import LibraryManagerUnavailableError

# ============================================================================
# DEPENDENCY WIRING (#4670)
#
# create_player_router() used to be a 515-line closure: every /api/player
# handler was nested inside it purely to reach get_library_database/get_audio_player/
# etc. via closure capture, which made a handler impossible to import or
# call without first building the whole router. Handlers are now module
# level; they reach the same callables through FastAPI Depends() instead.
#
# _PlayerDeps holds the raw callables/objects the factory receives. It is
# populated exactly once, by create_player_router() itself -- same as the
# old closure, which only ever ran once per process (config/routes.py calls
# the factory a single time at startup; the test `client` fixture imports
# the already-built `main.app` once per process too). This is a deliberate
# simplification, not a new hazard: nothing in this codebase calls
# create_player_router() more than once in the same process. It does NOT
# reproduce the #4361 module-level-`APIRouter()` hazard, since the router
# instance itself is still built fresh, per call, inside the factory.
#
# A handler's Depends() default is only consulted when FastAPI itself
# invokes it for a real request; a direct unit-test call passes the
# service/dependency explicitly as a keyword argument and never touches
# _PlayerDeps at all -- that's the seam #4670 asked for.
# ============================================================================


class _PlayerDeps:
    get_library_database: Callable[[], Any]
    get_audio_player: Callable[[], Any]
    get_player_state_manager: Callable[[], Any]
    connection_manager: Any
    create_track_info_fn: Callable[[Any], Any]


_deps = _PlayerDeps()


def _get_audio_player() -> Any:
    return _deps.get_audio_player()


def _get_library_database() -> Any:
    return _deps.get_library_database()


def _get_player_state_manager() -> Any:
    return _deps.get_player_state_manager()


def _get_connection_manager() -> Any:
    return _deps.connection_manager


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
        create_track_info_fn=_deps.create_track_info_fn,
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
        create_track_info_fn=_deps.create_track_info_fn,
    )


def _get_queue_history_repo(library_database: Any = Depends(_get_library_database)) -> Any:
    """Lazy repository initialization (#3805).

    Constructed directly from the library manager's session factory
    rather than via RepositoryFactory — this router only receives
    get_library_database, not get_repository_factory. QueueHistoryRepository
    is cheap to construct (BaseRepository just holds the session factory;
    no per-instance caching needed for occasional undo/history calls).
    """
    if not library_database:
        raise LibraryManagerUnavailableError()
    from auralis.library.repositories.queue_history_repository import (
        QueueHistoryRepository,
    )
    return QueueHistoryRepository(library_database.SessionLocal)
