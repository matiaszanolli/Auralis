"""
Regression test: a non-finite fingerprint dimension must not silence a master (#5505)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The #5103 guard ran only inside ``compute_windowed_fingerprint()``. Live
mastering calls ``AudioFingerprintAnalyzer.analyze()`` directly, so a NaN
dimension from the Rust engine became a NaN coordinate (``tanh(nan)`` is
``nan``), NaN parameters, an all-NaN buffer — and the final normalization's
repair step zeroed the whole track. ``_smooth_unit`` maps non-finite input to
the neutral midpoint, and ``analyze()`` rejects a non-finite result (#6144), so
the master fails visibly instead of coming out silent or wrong.

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


def test_analyze_rejects_non_finite_engine_output(monkeypatch, real_fingerprint):
    """#6144: replacing a NaN dimension with 0.0 stored a plausible but wrong
    fingerprint (LUFS 0.0); a non-finite result is a failed extraction now."""
    poisoned = dict(real_fingerprint)
    poisoned["crest_db"] = float("nan")
    poisoned["lufs"] = float("inf")
    monkeypatch.setattr(afa, "compute_fingerprint_schema", lambda *a: dict(poisoned))

    with pytest.raises(afa.FingerprintUnavailable, match="crest_db"):
        AudioFingerprintAnalyzer().analyze(_noise(), 44100)


def test_poisoned_fingerprint_fails_the_master_instead_of_silencing_it(monkeypatch, real_fingerprint):
    """WIRING: the live HybridProcessor → ContinuousMode path. A NaN dimension
    used to become NaN parameters and an all-zero master (#5505); it is now
    surfaced as a failure (#6107) rather than mastered with wrong parameters."""
    from auralis.core.config import UnifiedConfig
    from auralis.core.hybrid_processor import HybridProcessor

    poisoned = dict(real_fingerprint)
    poisoned["crest_db"] = float("nan")
    monkeypatch.setattr(afa, "compute_fingerprint_schema", lambda *a: dict(poisoned))

    processor = HybridProcessor(UnifiedConfig(internal_sample_rate=44100))
    try:
        with pytest.raises(afa.FingerprintUnavailable):
            processor.process(_noise())
    finally:
        processor.close()
