"""
Player Services

Business logic services extracted from routers/player.py.
Handles playback control, queue management, recommendations, and navigation.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from .errors import (
    InvalidRequest,
    OperationFailed,
    ResourceNotFound,
    ServiceError,
    ServiceUnavailable,
)
from .navigation_service import NavigationService
from .playback_service import PlaybackService
from .queue_enrichment import QueueEnricher
from .queue_protocols import AudioPlayerWithQueue, QueueManager
from .queue_service import QueueService
from .recommendation_service import RecommendationService

__all__ = [
    # Typed service-layer failures — routers map these by type, not by
    # message substring (#4700).
    'ServiceError',
    'ServiceUnavailable',
    'InvalidRequest',
    'ResourceNotFound',
    'OperationFailed',
    'PlaybackService',
    'QueueService',
    # Split out of queue_service in #4260.
    'QueueEnricher',
    'AudioPlayerWithQueue',
    'QueueManager',
    'RecommendationService',
    'NavigationService',
]
