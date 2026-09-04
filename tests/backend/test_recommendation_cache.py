"""Regression tests for the shared mastering-recommendation cache.

The REST endpoint and playback recommendation service must use the same
threshold-aware, TTL-bounded cache (#3865, #4657, #5280).
"""

import sys
from pathlib import Path
from unittest.mock import patch

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from cache.manager import RECOMMENDATION_TTL_S, StreamlinedCacheManager  # noqa: E402


class TestRecommendationCache:
    def setup_method(self):
        self.cache = StreamlinedCacheManager()

    def test_set_then_get_round_trips(self):
        result = {"preset": "adaptive", "confidence": 0.9}

        self.cache.set_mastering_recommendation(42, result)

        assert self.cache.get_mastering_recommendation(42) is result

    def test_hit_refreshes_lru_order(self):
        first = {"track": 1}
        second = {"track": 2}
        self.cache.set_mastering_recommendation(1, first)
        self.cache.set_mastering_recommendation(2, second)

        assert self.cache.get_mastering_recommendation(1) is first

        assert list(self.cache.mastering_recommendations)[-1] == (1, 0.4)

    def test_expired_entry_is_removed(self):
        result = {"track": 7}
        with patch("cache.manager.time.monotonic", return_value=100.0):
            self.cache.set_mastering_recommendation(7, result)

        with patch(
            "cache.manager.time.monotonic",
            return_value=100.0 + RECOMMENDATION_TTL_S,
        ):
            assert self.cache.get_mastering_recommendation(7) is None

        assert (7, 0.4) not in self.cache.mastering_recommendations

    def test_different_confidence_thresholds_have_separate_keys(self):
        result_04 = {"preset": "adaptive"}
        result_07 = {"preset": "warm"}
        self.cache.set_mastering_recommendation(5, result_04, 0.4)
        self.cache.set_mastering_recommendation(5, result_07, 0.7)

        assert self.cache.get_mastering_recommendation(5, 0.4) is result_04
        assert self.cache.get_mastering_recommendation(5, 0.7) is result_07

    def test_ttl_constant_is_60_seconds(self):
        assert RECOMMENDATION_TTL_S == 60.0
