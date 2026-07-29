"""Tests for the continuous corpus-calibrated bass counterweight."""

import numpy as np
import pytest

from auralis.core.mastering_config import SimpleMasteringConfig
from auralis.core.stages import bass_enhancement


def test_bright_leaning_source_gets_small_low_shelf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, float] = {}

    def fake_shelf(
        audio: np.ndarray,
        *,
        boost_db: float,
        freq_hz: float,
        sample_rate: int,
    ) -> np.ndarray:
        del sample_rate
        captured["boost_db"] = boost_db
        captured["freq_hz"] = freq_hz
        return audio.copy()

    monkeypatch.setattr(
        bass_enhancement.ParallelEQUtilities,
        "apply_low_shelf_boost",
        fake_shelf,
    )
    config = SimpleMasteringConfig()
    audio = np.zeros((2, 128), dtype=np.float32)

    _, info = bass_enhancement.apply(
        audio,
        bass_pct=0.443,
        intensity=1.0,
        sample_rate=48_000,
        verbose=False,
        config=config,
        mid_pct=0.108,
        upper_mid_pct=0.215,
        presence_pct=0.060,
    )

    assert info is not None
    assert info["counterweight_db"] == pytest.approx(0.57, abs=0.02)
    assert captured["boost_db"] == pytest.approx(info["boost_db"])
    assert captured["freq_hz"] == config.BASS_SHELF_HZ


def test_counterweight_changes_smoothly_with_spectral_tilt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        bass_enhancement.ParallelEQUtilities,
        "apply_low_shelf_boost",
        lambda audio, **kwargs: audio.copy(),
    )
    config = SimpleMasteringConfig()
    audio = np.zeros((2, 128), dtype=np.float32)

    weights = []
    for presence_pct in (0.049, 0.050, 0.051):
        _, info = bass_enhancement.apply(
            audio,
            bass_pct=0.443,
            intensity=1.0,
            sample_rate=48_000,
            verbose=False,
            config=config,
            upper_mid_pct=0.215,
            presence_pct=presence_pct,
        )
        assert info is not None
        weights.append(info["counterweight_db"])

    assert weights[0] < weights[1] < weights[2]
    assert max(weights[1] - weights[0], weights[2] - weights[1]) < 0.01
