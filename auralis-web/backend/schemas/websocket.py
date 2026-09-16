"""
WebSocket Schemas

Inbound message validation and the error envelope (#2156). Split out of
schemas.py (#5479).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ============================================================================
# WebSocket Message Models (Security: #2156)
# ============================================================================

class WebSocketMessageType(str, Enum):
    """Inbound WebSocket message types (client -> server).

    NOTE: despite the bare name, this enum enumerates ONLY the subset of
    types that the server validates on the receive path
    (websocket_security.py:187). Outbound (server -> client) types are
    NOT listed here — they live in the frontend's WebSocketMessageType
    Literal in src/types/websocket.ts. Renaming is deferred to avoid
    churn in callers; the docstring is the authoritative scope statement
    (#3551 / BE-NEW-93).
    """
    # `data` shapes below are documented from the actual handler each type
    # dispatches to (ws_handlers/connection.py:dispatch_message) — NOT
    # separately validated: `WebSocketMessageBase.data` stays `dict[str, Any]
    # | None` (#3873) rather than a per-type model, so a handler's own
    # inline isinstance()/is_valid_*() checks (see e.g. playback_commands.py)
    # remain the actual enforcement. This is a documentation-only pass; a
    # real per-type Pydantic `data` model is tracked by the broader WS-
    # contract-drift cluster (#4058, #4406, #4421, #4617, #4654, #4676,
    # #4585, #4680) rather than duplicated here piecemeal.
    PING = "ping"  # data: ignored. Server replies {"type": "pong"}.
    PONG = "pong"  # data: ignored. Client's reply to a server-issued ping.
    HEARTBEAT = "heartbeat"  # data: ignored. Liveness keepalive (RealTimeAnalysisStream).
    PLAY_ENHANCED = "play_enhanced"
    # data: {track_id: int (required, >0), preset?: str, intensity?: float
    # (0.0-1.0), force?: bool}. preset/intensity fall back through
    # ws-connection settings, then stored enhancement_settings, when absent
    # or invalid (#4600/#4677). force explicitly opts out of the stored
    # `enabled` gate (#3773).
    PLAY_NORMAL = "play_normal"
    # data: {track_id: int (required, >0), start_position?: float (seconds,
    # default 0.0)}.
    PAUSE = "pause"  # data: ignored (handle_pause takes no message/data param).
    STOP = "stop"  # data: ignored (handle_stop takes no message/data param).
    SEEK = "seek"
    # data: {track_id: int (required, >0), position: float (required,
    # seconds, >=0), preset?: str, intensity?: float} — same preset/
    # intensity precedence as PLAY_ENHANCED (#4677).
    SEEK_STARTED = "seek_started"  # server->client only; see class docstring.
    SUBSCRIBE_JOB_PROGRESS = "subscribe_job_progress"
    # data: {job_id: str (required)}. Subscribes this connection to
    # `job_progress` broadcasts for the named job.
    JOB_PROGRESS = "job_progress"  # server->client only; see class docstring.
    AUDIO_STREAM_ERROR = "audio_stream_error"  # server->client only; see class docstring.
    RESUME = "resume"  # data: ignored (handle_resume takes no message/data param).
    BUFFER_FULL = "buffer_full"  # data: ignored — flow-control signal only.
    BUFFER_READY = "buffer_ready"  # data: ignored — flow-control signal only.
    PLAYBACK_PAUSED = "playback_paused"  # server->client only; see class docstring.
    PLAYBACK_RESUMED = "playback_resumed"  # server->client only; see class docstring.
    PLAYBACK_STOPPED = "playback_stopped"  # server->client only; see class docstring.
    PLAYER_STATE = "player_state"  # server->client only; see class docstring.
    ENHANCEMENT_SETTINGS_CHANGED = "enhancement_settings_changed"  # server->client only; see class docstring.


class WebSocketMessageBase(BaseModel):
    """Base WebSocket message with type validation.

    extra='allow' preserves protocol envelope fields sent by WebSocketProtocolClient
    (correlation_id, timestamp, priority, response_required, timeout_seconds) so that
    request-response correlation does not time out (fixes #2281). This is deliberate
    envelope permissiveness, not a validation gap: `type` must still be a real
    WebSocketMessageType member, so an unknown message type is still rejected before
    it reaches a handler. `data`'s shape is per-type, documented on each
    WebSocketMessageType member above rather than enforced here — see that enum's
    class docstring for why (#3873).
    """
    type: WebSocketMessageType = Field(description="Message type")
    data: dict[str, Any] | None = Field(default=None, description="Message payload")

    model_config = ConfigDict(
        extra='allow',
        json_schema_extra={
            "example": {
                "type": "ping",
                "data": None
            }
        }
    )


class WebSocketErrorResponse(BaseModel):
    """WebSocket error response."""
    type: str = Field(default="error", description="Message type")
    error: str = Field(description="Error code")
    message: str = Field(description="Human-readable error message")
    timestamp: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC))

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "type": "error",
            "error": "validation_error",
            "message": "Invalid message format",
            "timestamp": "2024-11-28T10:00:00Z"
        }
    })
