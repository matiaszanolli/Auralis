"""
Mastering Recommendation Cache
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A small TTL + LRU cache of per-track mastering recommendations. It shares the
StreamlinedCacheManager singleton but is unrelated to audio-chunk caching, so
it lives apart from it (#5238).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import time
from collections import OrderedDict
from typing import Any

from .models import RECOMMENDATION_TTL_S

logger = logging.getLogger(__name__)


class RecommendationCacheMixin:
    """Per-track mastering recommendation cache.

    State is initialized by StreamlinedCacheManager.__init__, not here —
    declared here only so type checkers know this mixin depends on it.
    """

    mastering_recommendations: OrderedDict[tuple[int, float], tuple[float, dict[str, Any]]]
    MAX_RECOMMENDATIONS: int

    def set_mastering_recommendation(
        self,
        track_id: int,
        recommendation: dict[str, Any],
        confidence_threshold: float = 0.4,
    ) -> None:
        """
        Cache a mastering recommendation for a track (Priority 4).

        LRU-bounded at MAX_RECOMMENDATIONS to prevent unbounded growth in
        the module-level singleton (#3555 / BE-NEW-97).

        Args:
            track_id: Track database ID
            recommendation: Serialized MasteringRecommendation dict from adaptive_mastering_engine.recommend_weighted()
            confidence_threshold: Analysis threshold used to produce the result
        """
        now = time.monotonic()
        stale_keys = [
            key
            for key, (expiry, _) in self.mastering_recommendations.items()
            if expiry <= now
        ]
        for stale_key in stale_keys:
            del self.mastering_recommendations[stale_key]

        cache_key = (track_id, confidence_threshold)
        self.mastering_recommendations[cache_key] = (
            now + RECOMMENDATION_TTL_S,
            recommendation,
        )
        self.mastering_recommendations.move_to_end(cache_key)
        while len(self.mastering_recommendations) > self.MAX_RECOMMENDATIONS:
            self.mastering_recommendations.popitem(last=False)
        logger.info(
            f"📊 Cached mastering recommendation for track {track_id}: "
            f"{recommendation.get('primary_profile_name', 'unknown')}, "
            f"confidence={recommendation.get('confidence_score', 0):.0%}, "
            f"blended={'yes' if recommendation.get('weighted_profiles') else 'no'}"
        )

    def get_mastering_recommendation(
        self, track_id: int, confidence_threshold: float = 0.4
    ) -> dict[str, Any] | None:
        """
        Retrieve cached mastering recommendation for a track (Priority 4).

        Args:
            track_id: Track database ID
            confidence_threshold: Analysis threshold for the cached result

        Returns:
            Serialized MasteringRecommendation dict or None if not cached
        """
        cache_key = (track_id, confidence_threshold)
        cached = self.mastering_recommendations.get(cache_key)
        if cached is None:
            return None

        expiry, recommendation = cached
        if time.monotonic() >= expiry:
            del self.mastering_recommendations[cache_key]
            return None

        self.mastering_recommendations.move_to_end(cache_key)
        return recommendation

    def clear_mastering_recommendations(self) -> None:
        """Clear all cached mastering recommendations."""
        self.mastering_recommendations.clear()
        logger.info("Cleared all mastering recommendations from cache")
