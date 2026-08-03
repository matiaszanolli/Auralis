"""Regression coverage for runtime dynamics settings (#4917, #4931, #4983)."""

import inspect
from unittest.mock import Mock

import numpy as np
import pytest

from auralis.dsp.advanced_dynamics import DynamicsProcessor
from auralis.dsp.dynamics import AdaptiveCompressor, DynamicsSettings


@pytest.mark.regression
class TestDynamicsRuntimeStageFlags:
    """Runtime flags must control stages that were built at construction."""

    def setup_method(self) -> None:
        settings = DynamicsSettings(enable_gate=False)
        self.processor = DynamicsProcessor(settings)
        self.audio = np.full((64, 2), 0.25, dtype=np.float32)

    def test_runtime_compressor_disable_skips_existing_compressor(self) -> None:
        compressor = Mock()
        compressor.process.return_value = (self.audio * 0.5, {"applied": True})
        self.processor.compressor = compressor
        self.processor.settings.enable_compressor = False
        self.processor.settings.enable_limiter = False

        output, info = self.processor.process(self.audio)

        compressor.process.assert_not_called()
        np.testing.assert_array_equal(output, self.audio)
        assert "compressor" not in info

    def test_runtime_limiter_disable_skips_existing_limiter(self) -> None:
        limiter = Mock()
        limiter.process.return_value = (self.audio * 0.5, {"applied": True})
        self.processor.limiter = limiter
        self.processor.settings.enable_compressor = False
        self.processor.settings.enable_limiter = False

        output, info = self.processor.process(self.audio)

        limiter.process.assert_not_called()
        np.testing.assert_array_equal(output, self.audio)
        assert "limiter" not in info

    def test_gate_runtime_behavior_is_unchanged(self) -> None:
        processor = DynamicsProcessor(
            DynamicsSettings(
                enable_gate=True,
                gate_threshold_db=0.0,
                enable_compressor=False,
                enable_limiter=False,
            )
        )

        gated, info = processor.process(self.audio)
        assert bool(info["gate"]["active"])
        assert not np.array_equal(gated, self.audio)

        processor.settings.enable_gate = False
        bypassed, info = processor.process(self.audio)
        np.testing.assert_array_equal(bypassed, self.audio)
        assert "gate" not in info


@pytest.mark.regression
def test_compressor_has_no_inert_detection_mode_parameter() -> None:
    """Do not reintroduce a caller-selected mode unless it changes DSP behavior."""
    assert (
        "detection_mode" not in inspect.signature(AdaptiveCompressor.process).parameters
    )


@pytest.mark.regression
@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("gate_threshold_db", -100.0, -80.0),
        ("gate_threshold_db", 6.0, 0.0),
        ("gate_ratio", -5.0, 1.0),
        ("gate_ratio", 0.0, 1.0),
        ("gate_ratio", 200.0, 100.0),
        ("adaptation_speed", -0.1, 0.0),
        ("adaptation_speed", 1.1, 1.0),
        ("target_lufs", -100.0, -70.0),
        ("target_lufs", 3.0, 0.0),
        ("target_lra", -1.0, 0.0),
        ("target_lra", 30.0, 25.0),
    ],
)
def test_dynamics_settings_clamp_numeric_fields(
    field: str,
    value: float,
    expected: float,
) -> None:
    settings = DynamicsSettings(**{field: value})

    assert getattr(settings, field) == expected


@pytest.mark.regression
def test_zero_gate_ratio_is_safe_when_processing() -> None:
    settings = DynamicsSettings(
        gate_threshold_db=0.0,
        gate_ratio=0.0,
        enable_compressor=False,
        enable_limiter=False,
    )
    processor = DynamicsProcessor(settings)
    audio = np.zeros(32, dtype=np.float32)

    output, info = processor.process(audio)

    assert settings.gate_ratio == 1.0
    assert np.all(np.isfinite(output))
    assert info["gate"]["active"]
