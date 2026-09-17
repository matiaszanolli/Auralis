"""
Regression test: a non-finite fingerprint dimension must not silence a master (#5505)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The #5103 guard ran only inside ``compute_windowed_fingerprint()``. Live
mastering calls ``AudioFingerprintAnalyzer.analyze()`` directly, so a NaN
dimension from the Rust engine became a NaN coordinate (``tanh(nan)`` is
``nan``), NaN parameters, an all-NaN buffer — and the final normalization's
repair step zeroed the whole track. The guard now lives in ``analyze()`` and
``_smooth_unit`` maps non-finite input to the neutral midpoint.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import math

import numpy as np
import pytest

import auralis.analysis.fingerprint.audio_fingerprint_analyzer as afa
from auralis.analysis.fingerprint.audio_fingerprint_analyzer import (
    AudioFingerprintAnalyzer,
)
from auralis.core.processing.continuous_space import ProcessingSpaceMapper

# Every dimension the space mapper reads.
_MAPPED_DIMS = [
    "sub_bass_pct", "bass_pct", "low_mid_pct", "upper_mid_pct",
    "presence_pct", "air_pct", "spectral_centroid", "crest_db",
    "loudness_variation_std", "lufs",
]


def _noise(seconds: float = 3.0, sr: int = 44100) -> np.ndarray:
    rng = np.random.default_rng(5505)
    return (rng.standard_normal((int(seconds * sr), 2)) * 0.1).astype(np.float32)


@pytest.fixture(scope="module")
def real_fingerprint() -> dict[str, float]:
    fp = AudioFingerprintAnalyzer().analyze(_noise(), 44100)
    assert len(fp) == 25
    return fp


@pytest.mark.parametrize("dim", _MAPPED_DIMS)
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_mapper_coordinates_stay_finite(real_fingerprint, dim, bad):
    fp = dict(real_fingerprint)
    fp[dim] = bad
    coords = ProcessingSpaceMapper().map_fingerprint_to_space(fp)
    for value in (coords.spectral_balance, coords.dynamic_range, coords.energy_level):
        assert math.isfinite(value) and 0.0 <= value <= 1.0, (dim, bad, coords)


def test_analyze_sanitizes_engine_output(monkeypatch, real_fingerprint):
    poisoned = dict(real_fingerprint)
    poisoned["crest_db"] = float("nan")
    poisoned["lufs"] = float("inf")
    monkeypatch.setattr(afa, "compute_fingerprint_schema", lambda *a: dict(poisoned))

    fp = AudioFingerprintAnalyzer().analyze(_noise(), 44100)

    assert fp["crest_db"] == 0.0 and fp["lufs"] == 0.0
    assert all(math.isfinite(v) for v in fp.values())


def test_poisoned_fingerprint_does_not_silence_the_master(monkeypatch, real_fingerprint):
    """WIRING: the live HybridProcessor → ContinuousMode path gets the guard."""
    from auralis.core.config import UnifiedConfig
    from auralis.core.hybrid_processor import HybridProcessor

    poisoned = dict(real_fingerprint)
    poisoned["crest_db"] = float("nan")
    monkeypatch.setattr(afa, "compute_fingerprint_schema", lambda *a: dict(poisoned))

    audio = _noise()
    processor = HybridProcessor(UnifiedConfig(internal_sample_rate=44100))
    try:
        out = processor.process(audio)
    finally:
        processor.close()

    assert out is not None
    assert out.shape == audio.shape
    assert np.all(np.isfinite(out))
    assert float(np.sqrt(np.mean(out.astype(np.float64) ** 2))) > 1e-4, (
        "master came out silent — a non-finite fingerprint dimension reached "
        "parameter generation"
    )
