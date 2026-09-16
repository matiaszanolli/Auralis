"""
Player Router Models

Request and response bodies for the /api/player endpoints (#5472). Split out
of routers/player.py, which re-exports every name here.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from player_state import TrackInfo
from schemas import QueueIndex, QueueIndexList, TrackId, TrackIdList


class SetQueueRequest(BaseModel):
    """Request model for setting the playback queue"""
    tracks: TrackIdList
    start_index: QueueIndex = 0


class ReorderQueueRequest(BaseModel):
    """Request model for reordering the queue.

    ``new_order`` is a permutation of the queue's current *indices*, not track
    ids. Bounds are per-element and on length; whether the list is actually a
    permutation of the live queue is a runtime question QueueService answers,
    not one a body model can.
    """
    new_order: QueueIndexList


class MoveQueueTrackRequest(BaseModel):
    """Request model for moving a track within the queue (drag-and-drop)"""
    from_index: QueueIndex
    to_index: QueueIndex


class AddTrackToQueueRequest(BaseModel):
    """Request model for adding a track to queue with position"""
    track_id: TrackId
    position: QueueIndex | None = None  # None = append to end


class LoadTrackRequest(BaseModel):
    """Request model for loading a track"""
    track_id: TrackId


class SeekRequest(BaseModel):
    """Request model for seek operation with input validation.

    Deliberately has no upper bound (#4681). The only meaningful ceiling is the
    loaded track's duration, which a body model cannot see; the route applies
    that check when a track is loaded, and
    `tests/backend/test_player_api_comprehensive.py::test_seek_overflow_protection`
    pins the no-track-loaded case to a pass-through 200. A fixed numeric cap
    here would be arbitrary and would break that documented contract.
    """
    position: float

    @field_validator('position')
    @classmethod
    def validate_position(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Position must be a finite number")
        if v < 0:
            raise ValueError("Position must be non-negative")
        return v


class SetVolumeRequest(BaseModel):
    """Request model for volume control (0–100)."""
    # #3896 proposed replacing the validator with Field(ge=0, le=100) so the
    # bounds appear in OpenAPI. Deliberately not done: that converts a forgiving
    # clamp into a 422, and tests/integration/test_phase4_player_workflow.py::
    # test_volume_out_of_range sends 150 and -50 and asserts a SUCCESSFUL
    # response with a clamped value. Clamping is the intended contract, so the
    # range is documented instead of enforced.
    volume: float = Field(
        description="Playback volume on a 0-100 scale. Values outside the "
                    "range are clamped, not rejected.",
    )

    @field_validator('volume')
    @classmethod
    def clamp_volume(cls, v: float) -> float:
        return max(0.0, min(100.0, v))


class ShuffleRequest(BaseModel):
    """Request model for shuffle toggle."""
    enabled: bool = True


class RepeatModeRequest(BaseModel):
    """Request model for setting repeat mode."""
    mode: Literal["off", "all", "one"]


class QueueHistoryStateSnapshot(BaseModel):
    """Queue state snapshot carried by a history entry (#3805)."""
    track_ids: TrackIdList
    current_index: QueueIndex = 0
    is_shuffled: bool = False
    repeat_mode: Literal["off", "all", "one"] = "off"


class RecordQueueHistoryRequest(BaseModel):
    """Request model for POST /api/player/queue/history (#3805)."""
    operation: Literal["set", "add", "remove", "reorder", "shuffle", "clear"]
    state_snapshot: QueueHistoryStateSnapshot
    operation_metadata: dict[str, Any] = {}


# ============================================================================
# RESPONSE MODELS (#2751 — OpenAPI schema documentation)
# ============================================================================

class MessageResponse(BaseModel):
    """Generic response with a message."""
    message: str


class LoadTrackResponse(BaseModel):
    """Response for POST /api/player/load."""
    message: str
    track_id: int


class SeekResponse(BaseModel):
    """Response for POST /api/player/seek."""
    message: str
    position: float


class VolumeResponse(BaseModel):
    """Response for POST /api/player/volume."""
    message: str
    # int (#5050): matches PlaybackService.set_volume()'s rounded volume_100
    # and the paired volume_changed WS broadcast, both already ints.
    volume: int


class QueueInfoResponse(BaseModel):
    """Response for GET /api/player/queue."""
    # tracks/current_track are canonical TrackInfo (#4374): queue_service
    # enriches the engine queue's filepath-only entries into full TrackInfo
    # before returning, so the schema is real rather than `Any`.
    tracks: list[TrackInfo]
    current_index: int
    track_count: int | None = None
    current_track: TrackInfo | None = None
    has_next: bool | None = None
    has_previous: bool | None = None
    shuffle_enabled: bool | None = None
    # repeat_mode, not the engine's repeat_enabled bool (#3896). The engine
    # queue only knows "repeat the queue: yes/no", but the canonical
    # PlayerState.repeat_mode is three-valued, so a bool here silently collapsed
    # "all" and "one" into the same response. That made this endpoint unable to
    # populate the frontend's Queue.repeatMode, forcing callers to
    # GET /api/player/status instead and defeating the queue endpoint.
    # Matches PlayerState.repeat_mode above.
    repeat_mode: Literal["off", "all", "one"] | None = None

    model_config = ConfigDict(extra='allow')


class SetQueueResponse(BaseModel):
    """Response for POST /api/player/queue."""
    message: str
    track_count: int
    start_index: int


class QueueSizeResponse(BaseModel):
    """Response for queue operations that return message + queue_size."""
    message: str
    queue_size: int


class AddTrackToQueueResponse(BaseModel):
    """Response for POST /api/player/queue/add-track."""
    message: str
    track_id: int
    position: int | None
    queue_size: int


class RemoveFromQueueResponse(BaseModel):
    """Response for DELETE /api/player/queue/{index}."""
    message: str
    index: int
    queue_size: int


class MoveQueueTrackResponse(BaseModel):
    """Response for PUT /api/player/queue/move."""
    message: str
    from_index: int
    to_index: int
    queue_size: int


class QueueHistoryEntryResponse(BaseModel):
    """Single queue history entry (#3805)."""
    id: int
    operation: str
    state_snapshot: dict[str, Any]
    operation_metadata: dict[str, Any]
    created_at: str | None = None

    model_config = ConfigDict(extra='allow')


class QueueHistoryListResponse(BaseModel):
    """Response for GET /api/player/queue/history (#3805)."""
    history: list[QueueHistoryEntryResponse]
    count: int


class UndoQueueResponse(BaseModel):
    """Response for POST /api/player/queue/undo (#3805)."""
    message: str
    queue_state: dict[str, Any]
