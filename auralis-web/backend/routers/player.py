"""
Player Router

Handles audio playback control and queue management via FastAPI endpoints.
Delegates business logic to service layer (PlaybackService, QueueService,
RecommendationService, NavigationService).

Split by sub-resource (#5472). This module is the coordinator:
create_player_router() registers every /api/player route, and every handler
and model is re-exported here so `from routers.player import X` and
dependency_overrides keyed on routers.player providers keep working.
- player_models.py         request/response bodies
- player_deps.py           Depends() providers (#4670)
- player_playback.py       status, load, seek, volume, next, previous
- player_queue.py          queue read/replace/mutation, repeat mode

Audio streaming is WebSocket-only; no REST streaming endpoints remain.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends

from player_state import PlayerState

from .player_deps import (  # noqa: F401
    _deps,
    _get_audio_player,
    _get_connection_manager,
    _get_library_database,
    _get_navigation_service,
    _get_playback_service,
    _get_player_state_manager,
    _get_queue_service,
    _get_recommendation_service,
    _PlayerDeps,
)
from .player_models import (  # noqa: F401
    AddTrackToQueueRequest,
    AddTrackToQueueResponse,
    AddTracksToQueueRequest,
    AddTracksToQueueResponse,
    LoadTrackRequest,
    LoadTrackResponse,
    MessageResponse,
    MoveQueueTrackRequest,
    MoveQueueTrackResponse,
    QueueInfoResponse,
    QueueSizeResponse,
    RemoveFromQueueResponse,
    ReorderQueueRequest,
    RepeatModeRequest,
    SeekRequest,
    SeekResponse,
    SetQueueRequest,
    SetQueueResponse,
    SetVolumeRequest,
    ShuffleRequest,
    VolumeResponse,
)
from .player_playback import (
    get_player_status,
    load_track,
    next_track,
    previous_track,
    seek_position,
    set_volume,
)
from .player_queue import (
    add_track_to_queue,
    add_tracks_to_queue,
    clear_queue,
    get_queue,
    move_queue_track,
    remove_from_queue,
    reorder_queue,
    set_queue,
    set_repeat_mode,
    shuffle_queue,
)


def create_player_router(
    get_library_database: Callable[[], Any],
    get_audio_player: Callable[[], Any],
    get_player_state_manager: Callable[[], Any],
    connection_manager: Any,
    create_track_info_fn: Callable[[Any], Any],
) -> APIRouter:
    """
    Factory function to create player router with dependencies.

    Args:
        get_library_database: Callable that returns the LibraryDatabase
        get_audio_player: Callable that returns AudioPlayer instance
        get_player_state_manager: Callable that returns PlayerStateManager instance
        connection_manager: WebSocket connection manager for broadcasts
        create_track_info_fn: Function to create TrackInfo from database track

    Returns:
        APIRouter: Configured router instance
    """
    deps = _PlayerDeps(
        get_library_database=get_library_database,
        get_audio_player=get_audio_player,
        get_player_state_manager=get_player_state_manager,
        connection_manager=connection_manager,
        create_track_info_fn=create_track_info_fn,
    )

    router = APIRouter(tags=["player"], dependencies=[Depends(_deps.bind(deps))])

    # PLAYBACK
    router.add_api_route("/api/player/status", get_player_status, methods=["GET"], response_model=PlayerState)
    router.add_api_route("/api/player/load", load_track, methods=["POST"], response_model=LoadTrackResponse)
    router.add_api_route("/api/player/seek", seek_position, methods=["POST"], response_model=SeekResponse)
    router.add_api_route("/api/player/volume", set_volume, methods=["POST"], response_model=VolumeResponse)

    # QUEUE
    router.add_api_route("/api/player/queue", get_queue, methods=["GET"], response_model=QueueInfoResponse)
    router.add_api_route("/api/player/queue", set_queue, methods=["POST"], response_model=SetQueueResponse)

    router.add_api_route("/api/player/queue/{index}", remove_from_queue, methods=["DELETE"], response_model=RemoveFromQueueResponse)
    router.add_api_route("/api/player/queue/reorder", reorder_queue, methods=["PUT"], response_model=QueueSizeResponse)
    router.add_api_route("/api/player/queue/clear", clear_queue, methods=["POST"], response_model=MessageResponse)
    router.add_api_route("/api/player/queue/add-track", add_track_to_queue, methods=["POST"], response_model=AddTrackToQueueResponse)
    router.add_api_route("/api/player/queue/add-tracks", add_tracks_to_queue, methods=["POST"], response_model=AddTracksToQueueResponse)
    router.add_api_route("/api/player/queue/move", move_queue_track, methods=["PUT"], response_model=MoveQueueTrackResponse)
    router.add_api_route("/api/player/queue/shuffle", shuffle_queue, methods=["POST"], response_model=QueueSizeResponse)
    router.add_api_route("/api/player/queue/repeat", set_repeat_mode, methods=["POST"], response_model=MessageResponse)

    # NAVIGATION
    router.add_api_route("/api/player/next", next_track, methods=["POST"], response_model=MessageResponse)
    router.add_api_route("/api/player/previous", previous_track, methods=["POST"], response_model=MessageResponse)

    return router
