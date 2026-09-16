"""
Standardized Request/Response Schemas
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Defines Pydantic models for all API request/response payloads.
Ensures consistent structure across all endpoints.

A package since #5479, split by domain. Every name is re-exported here, so
`from schemas import X` is unchanged:
- enhancement.py     preset and intensity constraints
- websocket.py       inbound message validation, error envelope
- library.py         scan request/result, track/album/playlist/fingerprint
- request_bounds.py  bounded id/index types for request bodies
- system.py          health, version and cache statistics
- mastering.py       mastering recommendation

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .enhancement import (
    INTENSITY_MAX,
    INTENSITY_MIN,
    VALID_PRESETS,
    EnhancementIntensity,
    EnhancementPresetLiteral,
    is_valid_intensity,
)
from .library import (
    AlbumListResponse,
    AlbumResponse,
    FingerprintVectorResponse,
    LibraryScanRequest,
    PlaylistResponse,
    ScanResultResponse,
    TrackListResponse,
    TrackResponse,
)
from .mastering import (
    MasteringRecommendationResponse,
    WeightedProfileResponse,
)
from .request_bounds import (
    MAX_TRACK_ID_LIST,
    QueueIndex,
    QueueIndexList,
    TrackId,
    TrackIdList,
)
from .system import (
    CacheHealthResponse,
    CacheStatsResponse,
    CacheTierStats,
    HealthResponse,
    OverallCacheStats,
    TrackCacheStatusResponse,
    VersionInfoResponse,
)
from .websocket import (
    WebSocketErrorResponse,
    WebSocketMessageBase,
    WebSocketMessageType,
)

__all__ = [
    "INTENSITY_MAX",
    "INTENSITY_MIN",
    "MAX_TRACK_ID_LIST",
    "VALID_PRESETS",
    "AlbumListResponse",
    "AlbumResponse",
    "CacheHealthResponse",
    "CacheStatsResponse",
    "CacheTierStats",
    "EnhancementIntensity",
    "EnhancementPresetLiteral",
    "FingerprintVectorResponse",
    "HealthResponse",
    "LibraryScanRequest",
    "MasteringRecommendationResponse",
    "OverallCacheStats",
    "PlaylistResponse",
    "QueueIndex",
    "QueueIndexList",
    "ScanResultResponse",
    "TrackCacheStatusResponse",
    "TrackId",
    "TrackIdList",
    "TrackListResponse",
    "TrackResponse",
    "VersionInfoResponse",
    "WebSocketErrorResponse",
    "WebSocketMessageBase",
    "WebSocketMessageType",
    "WeightedProfileResponse",
    "is_valid_intensity",
]
