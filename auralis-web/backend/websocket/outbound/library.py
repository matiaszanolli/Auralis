"""
Library, playlist, artwork and scan payloads — wire payload contracts for backend WebSocket broadcasts (#6269).

Part of the ``websocket/outbound/`` payload split of ``outbound_messages.py``;
:func:`websocket.outbound_messages.broadcast_typed` and its overloads remain
the single broadcast entry point that ties these TypedDicts to their message
discriminators.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any, Literal, TypedDict

PlaylistUpdateAction = Literal[
    "renamed", "track_added", "track_removed", "reordered", "cleared"
]


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
    # `'counting'` is the scanner's pre-count pass (scanner.py), forwarded
    # verbatim by both bridges; `'started'` is consumed bridge-side and never
    # forwarded as a phase (#5475).
    phase: Literal["discovering", "counting", "processing"]


class ScanFailurePayload(TypedDict):
    # A bare file name: this is broadcast to every subscriber (#5341).
    filename: str
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
