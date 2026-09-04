"""Typed contracts for backend WebSocket broadcasts.

Every broadcast must pass through :func:`broadcast_typed`.  Its overloads tie
each message discriminator to one ``TypedDict`` payload, so a missing field,
misspelled key, or wrong literal is rejected by static type checking at the
emitter instead of becoming an undocumented wire-format change.
"""

import logging
from typing import Any, Literal, NotRequired, Protocol, TypedDict, overload

logger = logging.getLogger(__name__)

EnhancementPreset = Literal["adaptive", "gentle", "warm", "bright", "punchy"]
RepeatMode = Literal["off", "all", "one"]
QueueChangeAction = Literal[
    "added",
    "removed",
    "reordered",
    "shuffled",
    "unshuffled",
    "cleared",
    "undo",
]
PlaylistUpdateAction = Literal[
    "renamed", "track_added", "track_removed", "reordered", "cleared"
]


class BroadcastManager(Protocol):
    """Small structural boundary shared by the real manager and test doubles."""

    async def broadcast(self, message: dict[str, Any]) -> None: ...


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
    action: Literal["next", "previous", "jumped"]
    track_index: int
    seq: int


class PositionChangedPayload(TypedDict):
    position: float
    seq: int


class VolumeChangedPayload(TypedDict):
    volume: int
    seq: int


class QueueChangedPayload(TypedDict):
    action: QueueChangeAction
    tracks: NotRequired[list[dict[str, Any]]]
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


class LibraryUpdatedPayload(TypedDict):
    action: Literal["scan", "import", "update"]
    track_count: NotRequired[int]
    album_count: NotRequired[int]
    artist_count: NotRequired[int]


class MetadataUpdatedPayload(TypedDict):
    track_id: int
    updated_fields: list[str]


class MetadataBatchUpdatedPayload(TypedDict):
    track_ids: list[int]
    count: int


class PlaylistCreatedPayload(TypedDict):
    playlist_id: int
    name: str


class PlaylistUpdatedPayload(TypedDict):
    playlist_id: int
    action: PlaylistUpdateAction


class PlaylistDeletedPayload(TypedDict):
    playlist_id: int


class EnhancementSettingsChangedPayload(TypedDict):
    enabled: bool
    preset: EnhancementPreset
    intensity: float


class WeightedProfilePayload(TypedDict):
    profile_id: str
    profile_name: str
    weight: float


class AlternativeProfilePayload(TypedDict):
    profile_id: str
    profile_name: str
    confidence_score: float


class MasteringRecommendationPayload(TypedDict):
    track_id: int
    primary_profile_id: str
    primary_profile_name: str
    confidence_score: float
    predicted_loudness_change: float
    predicted_crest_change: float
    predicted_centroid_change: float
    weighted_profiles: NotRequired[list[WeightedProfilePayload]]
    reasoning: str
    is_hybrid: bool
    alternative_profiles: NotRequired[list[AlternativeProfilePayload]]
    created: NotRequired[str]


class ArtworkUpdatedPayload(TypedDict):
    action: Literal["extracted", "downloaded", "deleted"]
    album_id: int
    artwork_url: NotRequired[str]


class CacheClearedPayload(TypedDict):
    message: str


class LibraryScanStartedPayload(TypedDict):
    directories: list[str]


class ScanProgressPayload(TypedDict):
    current: int
    total: int
    percentage: float | None
    current_file: str | None
    phase: Literal["discovering", "processing"]


class ScanFailurePayload(TypedDict):
    filepath: str
    reason: str


class ScanCompletePayload(TypedDict):
    files_processed: int
    files_added: int
    files_updated: int
    files_skipped: int
    files_failed: int
    failures: list[ScanFailurePayload]
    duration: float
    directories_scanned: int


class LibraryScanErrorPayload(TypedDict):
    error: str


class LibraryTracksRemovedPayload(TypedDict):
    count: int


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
    manager: BroadcastManager,
    message_type: Literal["player_state"],
    data: PlayerStatePayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["playback_started"],
    data: PlaybackStartedPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["playback_paused"],
    data: PlaybackPausedPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["playback_stopped"],
    data: PlaybackStoppedPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["track_loaded"],
    data: TrackLoadedPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["track_changed"],
    data: TrackChangedPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["position_changed"],
    data: PositionChangedPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["volume_changed"],
    data: VolumeChangedPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["queue_changed"],
    data: QueueChangedPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["queue_shuffled"],
    data: QueueShuffledPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["repeat_mode_changed"],
    data: RepeatModeChangedPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["library_updated"],
    data: LibraryUpdatedPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["metadata_updated"],
    data: MetadataUpdatedPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["metadata_batch_updated"],
    data: MetadataBatchUpdatedPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["playlist_created"],
    data: PlaylistCreatedPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["playlist_updated"],
    data: PlaylistUpdatedPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["playlist_deleted"],
    data: PlaylistDeletedPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["enhancement_settings_changed"],
    data: EnhancementSettingsChangedPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["mastering_recommendation"],
    data: MasteringRecommendationPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["artwork_updated"],
    data: ArtworkUpdatedPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["cache_cleared"],
    data: CacheClearedPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["library_scan_started"],
    data: LibraryScanStartedPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["scan_progress"],
    data: ScanProgressPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["scan_complete"],
    data: ScanCompletePayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["library_scan_error"],
    data: LibraryScanErrorPayload,
    *,
    suppress_errors: bool = False,
) -> None: ...
@overload
async def broadcast_typed(
    manager: BroadcastManager,
    message_type: Literal["library_tracks_removed"],
    data: LibraryTracksRemovedPayload,
    *,
    suppress_errors: bool = False,
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
