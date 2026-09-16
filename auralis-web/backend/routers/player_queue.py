"""
Player Queue Endpoints

Queue read/replace/mutation and repeat-mode routes under /api/player/queue.
Split out of routers/player.py (#5472), whose create_player_router()
registers them.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Annotated, Any

from fastapi import Depends, Path

from services import QueueService, ServiceUnavailable
from websocket.outbound_messages import broadcast_typed

from .dependencies import with_error_handling
from .errors import raise_for_service_error
from .player_deps import (
    _get_connection_manager,
    _get_player_state_manager,
    _get_queue_service,
)
from .player_models import (
    AddTrackToQueueRequest,
    MoveQueueTrackRequest,
    ReorderQueueRequest,
    RepeatModeRequest,
    SetQueueRequest,
    ShuffleRequest,
)


@with_error_handling("get queue")
async def get_queue(service: QueueService = Depends(_get_queue_service)) -> dict[str, Any]:
    """Get current playback queue."""
    try:
        return await service.get_queue_info()
    except ValueError as e:
        raise_for_service_error(e, "get queue")


@with_error_handling("set queue")
async def set_queue(
    request: SetQueueRequest,
    service: QueueService = Depends(_get_queue_service),
) -> dict[str, Any]:
    """Set the playback queue (updates single source of truth)."""
    try:
        return await service.set_queue(request.tracks, request.start_index)
    except ValueError as e:
        raise_for_service_error(e, "set queue")


@with_error_handling("remove from queue")
async def remove_from_queue(
    index: Annotated[int, Path(ge=0)],
    service: QueueService = Depends(_get_queue_service),
) -> dict[str, Any]:
    """Remove track from queue at specified index."""
    try:
        return await service.remove_track_from_queue(index)
    except ValueError as e:
        raise_for_service_error(e, "remove from queue")


@with_error_handling("reorder queue")
async def reorder_queue(
    request: ReorderQueueRequest,
    service: QueueService = Depends(_get_queue_service),
) -> dict[str, Any]:
    """Reorder the playback queue."""
    try:
        return await service.reorder_queue(request.new_order)
    except ValueError as e:
        raise_for_service_error(e, "reorder queue")


@with_error_handling("clear queue")
async def clear_queue(service: QueueService = Depends(_get_queue_service)) -> dict[str, Any]:
    """Clear the entire playback queue."""
    try:
        return await service.clear_queue()
    except ValueError as e:
        raise_for_service_error(e, "clear queue")


@with_error_handling("add track to queue")
async def add_track_to_queue(
    request: AddTrackToQueueRequest,
    service: QueueService = Depends(_get_queue_service),
) -> dict[str, Any]:
    """Add a track to queue at specific position (for drag-and-drop)."""
    try:
        return await service.add_track_to_queue(request.track_id, request.position)
    except ValueError as e:
        raise_for_service_error(e, "add track to queue")


@with_error_handling("move track")
async def move_queue_track(
    request: MoveQueueTrackRequest,
    service: QueueService = Depends(_get_queue_service),
) -> dict[str, Any]:
    """Move a track within the queue (for drag-and-drop)."""
    try:
        return await service.move_track_in_queue(request.from_index, request.to_index)
    except ValueError as e:
        raise_for_service_error(e, "move track")


@with_error_handling("shuffle queue")
async def shuffle_queue(
    request: ShuffleRequest,
    service: QueueService = Depends(_get_queue_service),
) -> dict[str, Any]:
    """Shuffle or unshuffle the playback queue."""
    try:
        if request.enabled:
            return await service.shuffle_queue()
        else:
            return await service.unshuffle_queue()
    except ValueError as e:
        raise_for_service_error(e, "shuffle queue")


@with_error_handling("set repeat mode")
async def set_repeat_mode(
    request: RepeatModeRequest,
    player_state_manager: Any = Depends(_get_player_state_manager),
    connection_manager: Any = Depends(_get_connection_manager),
) -> dict[str, Any]:
    """Set the playback repeat mode (off, all, one)."""
    try:
        if not player_state_manager:
            raise ServiceUnavailable("Player state manager not available")

        # Pass through 'off' / 'one' / 'all' — backend now uses the same
        # vocabulary as the frontend Literal (#3501 / BE-NEW-43).
        await player_state_manager.update_state(repeat_mode=request.mode)

        # Broadcast canonical value so WS and REST always agree
        await broadcast_typed(
            connection_manager,
            "repeat_mode_changed",
            {"repeat_mode": request.mode},
        )

        return {"message": f"Repeat mode set to {request.mode}"}
    except ValueError as e:
        raise_for_service_error(e, "set repeat mode")
