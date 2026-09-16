"""
Player Queue History Endpoints (#3805)

GET/POST/DELETE /api/player/queue/history and POST /api/player/queue/undo.
Split out of routers/player.py (#5472), whose create_player_router()
registers these routes.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from typing import Any, cast

from fastapi import Depends, HTTPException, Query

from services import QueueService
from websocket.outbound_messages import broadcast_typed

from .dependencies import with_error_handling
from .errors import BadRequestError, NotFoundError
from .player_deps import (
    _get_connection_manager,
    _get_player_state_manager,
    _get_queue_history_repo,
    _get_queue_service,
)
from .player_models import RecordQueueHistoryRequest

logger = logging.getLogger(__name__)


# ============================================================================
# QUEUE HISTORY / UNDO ENDPOINTS (#3805)
#
# NOTE: create_player_router() registers these BEFORE the
# `/api/player/queue/{index}` DELETE route (routers/player_queue.py).
# FastAPI/Starlette match routes in registration order, not by
# literal-vs-parameterized specificity — if `/api/player/queue/history`
# were registered after `/api/player/queue/{index}`, a DELETE to
# `.../history` would match `{index}` first and fail int coercion (422)
# instead of ever reaching this route.
# ============================================================================

@with_error_handling("get queue history")
async def get_queue_history(
    limit: int = Query(20, ge=1, le=100),
    repo: Any = Depends(_get_queue_history_repo),
) -> dict[str, Any]:
    """Get recent queue-operation history entries (newest first)."""
    entries = await asyncio.to_thread(repo.get_history, limit)
    history = [entry.to_dict() for entry in entries]
    return {"history": history, "count": len(history)}


@with_error_handling("record queue history")
async def record_queue_history(
    request: RecordQueueHistoryRequest,
    repo: Any = Depends(_get_queue_history_repo),
) -> dict[str, Any]:
    """Record a queue-state snapshot to history, for later undo."""
    try:
        entry = await asyncio.to_thread(
            repo.push_to_history,
            request.operation,
            request.state_snapshot.model_dump(),
            request.operation_metadata,
        )
        return cast(dict[str, Any], entry.to_dict())
    except HTTPException:
        raise
    except ValueError as e:
        # Repository-level ValueError (not a typed ServiceError), so this
        # stays a plain 400 rather than going through raise_for_service_error
        # -- BadRequestError just for consistency with the typed exceptions
        # used elsewhere in this file (#5338).
        raise BadRequestError(str(e))


@with_error_handling("undo queue operation")
async def undo_queue_operation(
    repo: Any = Depends(_get_queue_history_repo),
    queue_service: QueueService = Depends(_get_queue_service),
    player_state_manager: Any = Depends(_get_player_state_manager),
    connection_manager: Any = Depends(_get_connection_manager),
) -> dict[str, Any]:
    """Undo the last recorded queue operation.

    Restores both the persisted QueueState row and the live queue
    (track order + position via QueueService.set_queue, repeat/shuffle
    flags via PlayerStateManager) — restoring only the DB snapshot would
    make "undo" silently do nothing from the user's perspective (#3805).
    """
    try:
        restored = await asyncio.to_thread(repo.undo)
        if restored is None:
            raise NotFoundError("History", detail="No history available to undo")

        restored_dict = restored.to_dict()

        try:
            await queue_service.set_queue(
                restored_dict['track_ids'], start_index=restored_dict['current_index']
            )
        except ValueError as e:
            # Audio player / state manager not available — the DB state
            # was still restored; degrade gracefully rather than failing
            # the whole undo over a live-sync step.
            logger.warning(f"Queue history restored in DB but live queue sync skipped: {e}")

        if player_state_manager:
            await player_state_manager.update_state(
                repeat_mode=restored_dict['repeat_mode'],
                shuffle_enabled=restored_dict['is_shuffled'],
            )

        # Canonical queue event is `queue_changed` (the #3492 rename that
        # this undo straggler missed); `queue_updated` had no FE subscriber
        # so the dedicated broadcast was silently dropped (#4420).
        await broadcast_typed(
            connection_manager,
            "queue_changed",
            {
                "action": "undo",
                "current_index": restored_dict['current_index'],
                "queue_size": len(restored_dict['track_ids']),
            },
        )

        return {"message": "Queue operation undone", "queue_state": restored_dict}
    except HTTPException:
        raise
    except ValueError as e:
        # Repository-level ValueError (repo.undo()), not a typed ServiceError
        # -- see record_queue_history's identical note (#5338).
        raise BadRequestError(str(e))


@with_error_handling("clear queue history")
async def clear_queue_history(repo: Any = Depends(_get_queue_history_repo)) -> dict[str, Any]:
    """Clear all queue history entries."""
    await asyncio.to_thread(repo.clear_history)
    return {"message": "Queue history cleared"}
