"""
Tests for the Rust->schema fingerprint glue (auralis.analysis.fingerprint.rust_fingerprint).

Verifies that compute_fingerprint_schema() produces schema-conformant 25D
fingerprints from the in-process Rust engine: correct keys, ranges, band-sum,
and the centroid/rolloff/DRV/bass_mid_ratio transforms.
"""
import math

import numpy as np
import pytest

from auralis.analysis.fingerprint.rust_fingerprint import (
    compute_fingerprint_schema,
    rust_fingerprint_to_schema,
)
from auralis.analysis.fingerprint.schema import DIMENSION_SCHEMA

SCHEMA_KEYS = set(DIMENSION_SCHEMA.keys())
BANDS = ["sub_bass_pct", "bass_pct", "low_mid_pct", "mid_pct",
         "upper_mid_pct", "presence_pct", "air_pct"]


def _signal(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 3, 44100 * 3, dtype=np.float32)
    return (0.3 * np.sin(2 * np.pi * 220 * t)
            + 0.2 * np.sin(2 * np.pi * 440 * t)
            + 0.05 * rng.standard_normal(len(t))).astype(np.float32)


def test_output_has_exactly_the_schema_keys():
    fp = compute_fingerprint_schema(_signal(), 44100, 1)
    assert set(fp.keys()) == SCHEMA_KEYS
    assert len(fp) == 25


def test_all_values_finite():
    fp = compute_fingerprint_schema(_signal(), 44100, 1)
    for k, v in fp.items():
        assert math.isfinite(v), f"{k} is not finite: {v}"


def test_band_fractions_sum_to_one():
    fp = compute_fingerprint_schema(_signal(), 44100, 1)
    assert abs(sum(fp[b] for b in BANDS) - 1.0) < 0.05


def test_normalized_dims_in_unit_range():
    fp = compute_fingerprint_schema(_signal(), 44100, 1)
    for k in ("spectral_centroid", "spectral_rolloff", "dynamic_range_variation"):
        assert 0.0 <= fp[k] <= 1.0, f"{k}={fp[k]} out of 0-1"


def test_bass_mid_ratio_is_db_scaled():
    # A raw fraction of 0.5 (bass==mid) must map to 0 dB.
    raw = _make_raw(bass_mid_ratio=0.5)
    assert abs(rust_fingerprint_to_schema(raw)["bass_mid_ratio"]) < 1e-6
    # Bass-dominant (>0.5) -> positive dB; mid-dominant (<0.5) -> negative dB.
    assert rust_fingerprint_to_schema(_make_raw(bass_mid_ratio=0.9))["bass_mid_ratio"] > 0
    assert rust_fingerprint_to_schema(_make_raw(bass_mid_ratio=0.1))["bass_mid_ratio"] < 0


def test_centroid_rolloff_normalization():
    raw = _make_raw(spectral_centroid=4000.0, spectral_rolloff=5000.0)
    fp = rust_fingerprint_to_schema(raw)
    assert abs(fp["spectral_centroid"] - 0.5) < 1e-6      # 4000 / 8000
    assert abs(fp["spectral_rolloff"] - 0.5) < 1e-6       # 5000 / 10000


def test_loudness_variation_renamed_not_rescaled():
    raw = _make_raw(loudness_variation=4.2)
    fp = rust_fingerprint_to_schema(raw)
    assert "loudness_variation_std" in fp
    assert fp["loudness_variation_std"] == pytest.approx(4.2)


def test_missing_rust_key_raises():
    raw = _make_raw()
    del raw["spectral_centroid"]
    with pytest.raises(KeyError):
        rust_fingerprint_to_schema(raw)


def _make_raw(**overrides):
    """A complete raw Rust-shaped fingerprint dict with sane defaults, for
    testing the pure mapper without invoking Rust."""
    raw = {
        "sub_bass": 0.1, "bass": 0.3, "low_mid": 0.2, "mid": 0.2,
        "upper_mid": 0.1, "presence": 0.05, "air": 0.05,
        "lufs": -14.0, "crest_db": 12.0, "bass_mid_ratio": 0.5,
        "tempo_bpm": 120.0, "rhythm_stability": 0.8, "transient_density": 0.2,
        "silence_ratio": 0.05, "spectral_centroid": 2000.0,
        "spectral_rolloff": 4000.0, "spectral_flatness": 0.1,
        "harmonic_ratio": 0.7, "pitch_stability": 0.6, "chroma_energy": 0.2,
        "dynamic_range_variation": 3.0, "loudness_variation": 2.0,
        "peak_consistency": 0.5, "stereo_width": 0.3, "phase_correlation": 0.9,
    }
    raw.update(overrides)
    return raw
