"""Regression coverage for shared clamp bounds in dynamics settings (#5022).

CompressorSettings.ratio/DynamicsSettings.gate_ratio and
CompressorSettings.lookahead_ms/LimiterSettings.lookahead_ms used to clamp via
independently re-typed bare literal bounds. This locks the shared constants
and proves the sibling dataclasses still clamp to the same value.
"""

import pytest

from auralis.dsp.dynamics.settings import (
    LOOKAHEAD_MS_BOUNDS,
    RATIO_BOUNDS,
    THRESHOLD_DB_BOUNDS,
    CompressorSettings,
    DynamicsSettings,
    LimiterSettings,
)


@pytest.mark.regression
class TestSharedClampBounds:
    def test_ratio_and_gate_ratio_share_upper_bound(self) -> None:
        compressor = CompressorSettings(ratio=150.0)
        dynamics = DynamicsSettings(gate_ratio=150.0)

        assert compressor.ratio == RATIO_BOUNDS[1] == 100.0
        assert dynamics.gate_ratio == RATIO_BOUNDS[1] == 100.0

    def test_lookahead_ms_shares_upper_bound_across_compressor_and_limiter(self) -> None:
        compressor = CompressorSettings(lookahead_ms=999.0)
        limiter = LimiterSettings(lookahead_ms=999.0)

        assert compressor.lookahead_ms == LOOKAHEAD_MS_BOUNDS[1] == 50.0
        assert limiter.lookahead_ms == LOOKAHEAD_MS_BOUNDS[1] == 50.0

    def test_threshold_db_and_gate_threshold_db_share_lower_bound(self) -> None:
        compressor = CompressorSettings(threshold_db=-200.0)
        dynamics = DynamicsSettings(gate_threshold_db=-200.0)

        assert compressor.threshold_db == THRESHOLD_DB_BOUNDS[0] == -80.0
        assert dynamics.gate_threshold_db == THRESHOLD_DB_BOUNDS[0] == -80.0
