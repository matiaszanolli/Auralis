"""Typed contracts for backend WebSocket broadcasts.

Every broadcast must pass through :func:`broadcast_typed`.  Its overloads tie
each message discriminator to one ``TypedDict`` payload, so a missing field,
misspelled key, or wrong literal is rejected by static type checking at the
emitter instead of becoming an undocumented wire-format change.
"""

import logging
from typing import Any, Literal, Protocol, overload

# Payload contracts live in the outbound/ package since #6269 (player, queue,
# library, enhancement); this module owns the broadcast entry point and the
# discriminator overloads that tie each payload to its message type.
from .outbound.enhancement import (
    AlternativeProfilePayload,
    EnhancementSettingsChangedPayload,
    MasteringRecommendationPayload,
    WeightedProfilePayload,
)
from .outbound.library import (
    ArtworkUpdatedPayload,
    CacheClearedPayload,
    LibraryScanErrorPayload,
    LibraryScanStartedPayload,
    LibraryTracksRemovedPayload,
    LibraryUpdatedPayload,
    MetadataBatchUpdatedPayload,
    MetadataUpdatedPayload,
    PlaylistCreatedPayload,
    PlaylistDeletedPayload,
    PlaylistUpdatedPayload,
    ScanCompletePayload,
    ScanFailurePayload,
    ScanProgressPayload,
)
from .outbound.player import (
    PlaybackPausedPayload,
    PlaybackStartedPayload,
    PlaybackStoppedPayload,
    PlayerStatePayload,
    PositionChangedPayload,
    TrackChangedPayload,
    TrackLoadedPayload,
    VolumeChangedPayload,
)
from .outbound.queue import (
    QueueChangedPayload,
    QueueShuffledPayload,
    RepeatModeChangedPayload,
)

logger = logging.getLogger(__name__)


class BroadcastManager(Protocol):
    """Small structural boundary shared by the real manager and test doubles."""

    async def broadcast(self, message: dict[str, Any]) -> None: ...


BroadcastMessageType = Literal[
    "player_state",
    "playback_started",
    "playback_paused",
    "playback_stopped",
    "track_loaded",
    "track_changed",
    "position_changed",
    "volume_changed",
    "queue_changed",
    "queue_shuffled",
    "repeat_mode_changed",
    "library_updated",
    "metadata_updated",
    "metadata_batch_updated",
    "playlist_created",
    "playlist_updated",
    "playlist_deleted",
    "enhancement_settings_changed",
    "mastering_recommendation",
    "artwork_updated",
    "cache_cleared",
    "library_scan_started",
    "scan_progress",
    "scan_complete",
    "library_scan_error",
    "library_tracks_removed",
]


@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["player_state"], data: PlayerStatePayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["playback_started"], data: PlaybackStartedPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["playback_paused"], data: PlaybackPausedPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["playback_stopped"], data: PlaybackStoppedPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["track_loaded"], data: TrackLoadedPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["track_changed"], data: TrackChangedPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["position_changed"], data: PositionChangedPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["volume_changed"], data: VolumeChangedPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["queue_changed"], data: QueueChangedPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["queue_shuffled"], data: QueueShuffledPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["repeat_mode_changed"], data: RepeatModeChangedPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["library_updated"], data: LibraryUpdatedPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["metadata_updated"], data: MetadataUpdatedPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["metadata_batch_updated"],
    data: MetadataBatchUpdatedPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["playlist_created"], data: PlaylistCreatedPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["playlist_updated"], data: PlaylistUpdatedPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["playlist_deleted"], data: PlaylistDeletedPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["enhancement_settings_changed"],
    data: EnhancementSettingsChangedPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["mastering_recommendation"],
    data: MasteringRecommendationPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["artwork_updated"], data: ArtworkUpdatedPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["cache_cleared"], data: CacheClearedPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["library_scan_started"], data: LibraryScanStartedPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["scan_progress"], data: ScanProgressPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["scan_complete"], data: ScanCompletePayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager, message_type: Literal["library_scan_error"], data: LibraryScanErrorPayload,
    *, suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["library_tracks_removed"],
    data: LibraryTracksRemovedPayload,
    *, suppress_errors: bool = False,
) -> None: ...


async def broadcast_typed(
    manager: BroadcastManager,
    message_type: BroadcastMessageType,
    data: object,
    *,
    suppress_errors: bool = False,
) -> None:
    """Broadcast one typed ``{type, data}`` envelope."""
    try:
        await manager.broadcast({"type": message_type, "data": data})
    except Exception as exc:
        if not suppress_errors:
            raise
        logger.debug("WebSocket broadcast skipped: %s", exc)
