"""Regression coverage for runtime dynamics settings (#4917, #4931, #4983)."""

import inspect

import pytest

from auralis.dsp.dynamics import AdaptiveCompressor, DynamicsSettings


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
