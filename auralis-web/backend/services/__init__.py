"""
Player Services

Business logic services extracted from routers/player.py.
Handles playback control, queue management, recommendations, and navigation.

Only the names with a live importer are re-exported here; the error types
beyond ServiceUnavailable and the queue protocols are imported from their
defining modules (`services.errors`, `services.queue_protocols`,
`services.queue_enrichment`).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .errors import ServiceUnavailable
from .navigation_service import NavigationService
from .playback_service import PlaybackService
from .queue_service import QueueService
from .recommendation_service import RecommendationService

__all__ = [
    'ServiceUnavailable',
    'PlaybackService',
    'QueueService',
    'RecommendationService',
    'NavigationService',
]
