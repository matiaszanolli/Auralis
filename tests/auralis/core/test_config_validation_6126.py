"""Config validation survives `python -O` and from_dict leaves its input alone (#6126).

UnifiedConfig, AdaptiveConfig and GenreProfile validated with `assert`, which -O
strips, so out-of-range DSP parameters were accepted in optimised runs. They are
real ValueErrors now. `UnifiedConfig.from_dict` also popped keys out of the
caller's dict.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from auralis.core.config.settings import AdaptiveConfig, GenreProfile
from auralis.core.config.unified_config import UnifiedConfig

ROOT = Path(__file__).resolve().parents[3]

PROFILE = dict(
    name="x", target_lufs=-14.0, bass_boost_db=0.0, midrange_clarity_db=0.0,
    treble_enhancement_db=0.0, compression_ratio=2.0, stereo_width=1.0, mastering_intensity=0.5,
)


class TestUnifiedConfig:
    @pytest.mark.parametrize("kwargs", [
        {"internal_sample_rate": 0}, {"internal_sample_rate": -44100}, {"internal_sample_rate": 44100.5},
        {"internal_sample_rate": "44100"}, {"max_length": 0}, {"max_length": -1},
        {"fft_size": 1}, {"fft_size": 1000}, {"fft_size": 0},
    ])
    def test_invalid_core_settings_raise_value_error(self, kwargs):
        with pytest.raises(ValueError):
            UnifiedConfig(**kwargs)

    def test_defaults_construct(self):
        assert UnifiedConfig().fft_size > 1


class TestAdaptiveConfig:
    @pytest.mark.parametrize("field, value", [
        ("adaptation_strength", -0.1), ("adaptation_strength", 1.1), ("adaptation_strength", float("nan")),
        ("chunk_size_ms", 4.0), ("chunk_size_ms", 101.0), ("latency_budget_ms", 9.0), ("latency_budget_ms", 101.0),
    ])
    def test_out_of_range_values_raise(self, field, value):
        with pytest.raises(ValueError, match="got"):
            AdaptiveConfig(**{field: value})


class TestGenreProfile:
    @pytest.mark.parametrize("field, value", [
        ("target_lufs", 1.0), ("target_lufs", -31.0), ("bass_boost_db", 13.0),
        ("midrange_clarity_db", -13.0), ("treble_enhancement_db", 12.5), ("compression_ratio", 0.5),
        ("compression_ratio", 10.5), ("stereo_width", 2.1), ("mastering_intensity", -0.1),
    ])
    def test_out_of_range_values_raise(self, field, value):
        with pytest.raises(ValueError):
            GenreProfile(**{**PROFILE, field: value})

    def test_a_valid_profile_constructs(self):
        assert GenreProfile(**PROFILE).name == "x"


def test_the_guards_survive_python_optimize_mode():
    code = (
        "from auralis.core.config.settings import AdaptiveConfig\n"
        "try:\n"
        "    AdaptiveConfig(adaptation_strength=5.0)\n"
        "except ValueError:\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(1)\n"
    )
    assert subprocess.run([sys.executable, "-O", "-c", code], cwd=ROOT).returncode == 0


def test_from_dict_does_not_modify_the_callers_dict():
    config = {
        "internal_sample_rate": 48000, "fft_size": 2048,
        "processing_mode": "adaptive", "adaptation_strength": 0.5, "chunk_size_ms": 20.0,
    }
    snapshot = dict(config)

    built = UnifiedConfig.from_dict(config)

    assert config == snapshot
    assert built.internal_sample_rate == 48000 and built.adaptive.adaptation_strength == 0.5


def test_no_assert_statements_remain_in_the_config_package():
    for path in (ROOT / "auralis/core/config").glob("*.py"):
        offenders = [l for l in path.read_text().splitlines() if l.lstrip().startswith("assert ")]
        assert offenders == [], f"{path.name}: {offenders}"
