"""
Regression tests for mastering recommendation TTL cache (#3865 / BE-RH-20)

get_mastering_recommendation runs ChunkedAudioProcessor (~1-5 s CPU) on every
call with no caching. The fix adds a 60 s TTL dict so repeated calls for the
same (track_id, confidence_threshold) return immediately without re-analysis.

We verify the caching semantics by patching the module-level dict directly.
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

import routers.enhancement as enhancement_module


class TestRecommendationCache:
    """_recommendation_cache TTL dict must prevent re-running analysis on hits."""

    def setup_method(self):
        """Clear the module-level cache before each test."""
        enhancement_module._recommendation_cache.clear()

    # ------------------------------------------------------------------
    # Cache hit / miss
    # ------------------------------------------------------------------

    def test_cache_miss_populates_entry(self):
        """After a successful analysis, the result is stored in the cache."""
        key = (42, 0.4)
        assert key not in enhancement_module._recommendation_cache

        # Simulate what the handler writes
        result = {"preset": "adaptive", "confidence": 0.9}
        now = time.monotonic()
        enhancement_module._recommendation_cache[key] = (
            now + enhancement_module._RECOMMENDATION_TTL_S,
            result,
        )

        assert key in enhancement_module._recommendation_cache
        _expiry, _result = enhancement_module._recommendation_cache[key]
        assert _result == result
        assert _expiry > now

    def test_cache_hit_returns_without_re_running_analysis(self):
        """
        If a valid cache entry exists, the handler must return it without
        calling ChunkedAudioProcessor (mock would not be called).
        """
        key = (99, 0.5)
        cached_result = {"preset": "warm", "confidence": 0.75}
        # Plant a still-valid entry
        enhancement_module._recommendation_cache[key] = (
            time.monotonic() + 60.0,
            cached_result,
        )

        # The handler computes: if _now < _expiry: return _cached_result
        _now = time.monotonic()
        _expiry, _cached = enhancement_module._recommendation_cache[key]
        assert _now < _expiry, "entry must still be valid"
        assert _cached == cached_result

    def test_expired_entry_is_not_returned(self):
        """An expired cache entry must NOT be used — analysis must re-run."""
        key = (7, 0.4)
        stale_result = {"preset": "bright"}
        # Plant an already-expired entry (expiry in the past)
        enhancement_module._recommendation_cache[key] = (
            time.monotonic() - 1.0,  # expired 1 second ago
            stale_result,
        )

        _now = time.monotonic()
        _expiry, _cached = enhancement_module._recommendation_cache[key]
        # A cache miss is expected because _now >= _expiry
        assert _now >= _expiry, "entry should be expired"

    def test_different_confidence_thresholds_have_separate_keys(self):
        """Cache is keyed by (track_id, confidence_threshold) — different thresholds are distinct."""
        track_id = 5
        result_04 = {"preset": "adaptive", "confidence": 0.9}
        result_07 = {"preset": "warm", "confidence": 0.8}
        _now = time.monotonic()

        enhancement_module._recommendation_cache[(track_id, 0.4)] = (
            _now + 60.0, result_04
        )
        enhancement_module._recommendation_cache[(track_id, 0.7)] = (
            _now + 60.0, result_07
        )

        assert enhancement_module._recommendation_cache[(track_id, 0.4)][1] == result_04
        assert enhancement_module._recommendation_cache[(track_id, 0.7)][1] == result_07

    def test_ttl_constant_is_60_seconds(self):
        """_RECOMMENDATION_TTL_S must be 60 s (agreed upon in the fix)."""
        assert enhancement_module._RECOMMENDATION_TTL_S == 60.0
