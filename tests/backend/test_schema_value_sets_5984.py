"""Closed vocabularies are Literals, not bare str/int (#5984)."""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.processing_models import ProcessingSettings  # noqa: E402
from routers.settings_models import SettingsUpdateRequest  # noqa: E402
from schemas import BitDepth, CacheTierStats, HealthResponse, TrackCacheStatusResponse  # noqa: E402


class TestBitDepthIsDefinedOnce:
    @pytest.mark.parametrize("depth", [16, 24, 32])
    def test_both_models_accept_the_supported_depths(self, depth):
        assert SettingsUpdateRequest(bit_depth=depth).bit_depth == depth
        assert ProcessingSettings(bit_depth=depth).bit_depth == depth

    @pytest.mark.parametrize("depth", [0, 8, 12, 20, 64, -16])
    def test_both_models_reject_anything_else(self, depth):
        with pytest.raises(ValidationError):
            SettingsUpdateRequest(bit_depth=depth)
        with pytest.raises(ValidationError):
            ProcessingSettings(bit_depth=depth)

    def test_the_settings_field_is_optional_for_a_partial_update(self):
        assert SettingsUpdateRequest().bit_depth is None

    def test_it_is_one_shared_type(self):
        assert BitDepth.__args__ == (16, 24, 32)


class TestSystemSchemas:
    def test_health_status_is_only_healthy(self):
        assert HealthResponse(status="healthy", auralis_available=True).status == "healthy"
        with pytest.raises(ValidationError):
            HealthResponse(status="degraded", auralis_available=True)

    @pytest.mark.parametrize("tier", ["tier1", "tier2"])
    def test_tier_name_accepts_the_two_tiers(self, tier):
        stats = CacheTierStats(tier_name=tier, chunks=0, size_mb=0.0, hits=0, misses=0, hit_rate=0.0)
        assert stats.tier_name == tier

    def test_tier_name_rejects_anything_else(self):
        with pytest.raises(ValidationError):
            CacheTierStats(tier_name="tier3", chunks=0, size_mb=0.0, hits=0, misses=0, hit_rate=0.0)

    def test_the_never_populated_estimate_field_is_gone(self):
        assert "estimated_cache_time_seconds" not in TrackCacheStatusResponse.model_fields
