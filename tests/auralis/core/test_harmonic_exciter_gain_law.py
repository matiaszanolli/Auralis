"""Tests for the harmonic exciter's continuous wet-mix gain law."""

from typing import Any

import numpy as np
import pytest

from auralis.core.mastering_config import SimpleMasteringConfig
from auralis.core.stages import harmonic_exciter


def _capture_wet_levels(
    monkeypatch: pytest.MonkeyPatch,
) -> list[float]:
    wet_levels: list[float] = []

    def fake_apply(
        audio: np.ndarray,
        *,
        wet_db: float,
        **kwargs: object,
    ) -> np.ndarray:
        del kwargs
        wet_levels.append(wet_db)
        return audio.copy()

    monkeypatch.setattr(harmonic_exciter.HarmonicExciter, "apply", fake_apply)
    return wet_levels


def _apply(
    audio: np.ndarray,
    *,
    intensity: float,
    spectral_need: float,
) -> tuple[np.ndarray, dict[str, Any] | None]:
    return harmonic_exciter.apply(
        audio,
        presence_pct=0.0,
        air_pct=0.0,
        spectral_rolloff=0.0,
        intensity=intensity,
        sample_rate=48_000,
        verbose=False,
        config=SimpleMasteringConfig(),
        hf_lift=spectral_need,
    )


def test_lower_intensity_reduces_wet_amplitude(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wet_levels = _capture_wet_levels(monkeypatch)
    audio = np.zeros((2, 128), dtype=np.float32)

    _apply(audio, intensity=1.0, spectral_need=1.0)
    full_wet_db = wet_levels[0]
    wet_levels.clear()
    _apply(audio, intensity=0.5, spectral_need=1.0)
    half_wet_db = wet_levels[0]

    assert half_wet_db == pytest.approx(full_wet_db - 6.0206, abs=1e-4)


def test_small_spectral_need_approaches_dry_mix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wet_levels = _capture_wet_levels(monkeypatch)
    audio = np.zeros((2, 128), dtype=np.float32)

    _, info = _apply(audio, intensity=1.0, spectral_need=0.1)

    assert info is not None
    assert wet_levels[0] == pytest.approx(-40.1)
    assert info["spectral_need"] == pytest.approx(0.1)


def test_zero_intensity_is_an_exact_no_op() -> None:
    audio = np.ones((2, 128), dtype=np.float32)

    processed, info = _apply(audio, intensity=0.0, spectral_need=1.0)

    assert info is None
    assert processed is not audio
    np.testing.assert_array_equal(processed, audio)
