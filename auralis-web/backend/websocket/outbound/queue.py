"""
Queue payloads — wire payload contracts for backend WebSocket broadcasts (#6269).

Part of the ``websocket/outbound/`` payload split of ``outbound_messages.py``;
:func:`websocket.outbound_messages.broadcast_typed` and its overloads remain
the single broadcast entry point that ties these TypedDicts to their message
discriminators.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Literal, NotRequired, TypedDict

from .player import RepeatMode, TrackPayload

QueueChangeAction = Literal[
    "added",
    "removed",
    "reordered",
    "shuffled",
    "unshuffled",
    "cleared",
    "undo",
]


class QueueChangedPayload(TypedDict):
    action: QueueChangeAction
    # TrackPayload, not dict[str, Any] (#5455): an untyped list let raw engine
    # queue entries — bare filepaths, no id/title — type-check straight onto
    # the wire.
    tracks: NotRequired[list[TrackPayload]]
    current_index: NotRequired[int]
    track_id: NotRequired[int]
    position: NotRequired[int | None]
    index: NotRequired[int]
    queue_size: NotRequired[int]
    from_index: NotRequired[int]
    to_index: NotRequired[int]


class QueueChangedExtras(TypedDict, total=False):
    track_id: int
    position: int | None
    index: int
    queue_size: int
    from_index: int
    to_index: int


class QueueShuffledPayload(TypedDict):
    is_shuffled: bool


class RepeatModeChangedPayload(TypedDict):
    repeat_mode: RepeatMode
