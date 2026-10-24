"""
Player transport payloads — wire payload contracts for backend WebSocket broadcasts (#6269).

Part of the ``websocket/outbound/`` payload split of ``outbound_messages.py``;
:func:`websocket.outbound_messages.broadcast_typed` and its overloads remain
the single broadcast entry point that ties these TypedDicts to their message
discriminators.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any, Literal, NotRequired, TypedDict

from schemas import EnhancementPresetLiteral as EnhancementPreset

RepeatMode = Literal["off", "all", "one"]


class TrackPayload(TypedDict, total=False):
    id: int
    title: str
    artist: str
    album: str
    duration: float
    artwork_url: str | None
    format: str | None


class PlayerStatePayload(TypedDict):
    seq: int
    server_instance_id: str
    state: Literal["playing", "paused", "stopped", "loading", "error"]
    is_playing: bool
    is_paused: bool
    current_track: TrackPayload | None
    current_time: float
    duration: float
    volume: int
    is_muted: bool
    queue: list[TrackPayload]
    queue_index: int
    queue_size: int
    shuffle_enabled: bool
    repeat_mode: RepeatMode
    mastering_enabled: bool
    current_preset: EnhancementPreset
    analysis: dict[str, Any] | None


class PlaybackStartedPayload(TypedDict):
    state: Literal["playing"]
    seq: int


class PlaybackPausedPayload(TypedDict):
    state: Literal["paused"]
    seq: int


class PlaybackStoppedPayload(TypedDict):
    state: Literal["stopped"]
    seq: int


class TrackLoadedPayload(TypedDict):
    track_id: int


class TrackChangedPayload(TypedDict):
    action: Literal["next", "previous"]
    track_index: int
    seq: int


class PositionChangedPayload(TypedDict):
    position: float
    seq: int


class VolumeChangedPayload(TypedDict):
    volume: int
    seq: int
