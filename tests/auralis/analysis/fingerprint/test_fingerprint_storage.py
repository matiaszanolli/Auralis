"""
Regression tests for FingerprintStorage — #3464, #3451.

Prior bug: `FingerprintStorage.load()` rejected every cache entry whose
``mastering_targets`` field was an empty dict (because ``not {}`` is True).
The player's adaptive-mastering path writes targets as ``{}``, so the
file-tier of the 3-tier (DB → .25d → on-demand) cache returned None
for every entry — every fingerprint lookup paid the full recomputation
cost despite a populated cache directory.

These tests pin the contract: an empty/missing ``mastering_targets`` is
acceptable as long as the ``fingerprint`` itself is present.
"""

from __future__ import annotations

import json

import pytest

from auralis.analysis.fingerprint.fingerprint_storage import FingerprintStorage


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    """Redirect FingerprintStorage cache directory to a tmp path."""
    cache = tmp_path / "fingerprints"
    cache.mkdir()
    monkeypatch.setattr(
        FingerprintStorage,
        "_get_cache_dir",
        staticmethod(lambda: cache),
    )
    return cache


@pytest.fixture
def audio_file(tmp_path):
    """Create a small fake audio file (used only for path/signature hashing)."""
    path = tmp_path / "track.flac"
    path.write_bytes(b"FAKE FLAC HEADER " + b"\x00" * 4096)
    return path


@pytest.fixture
def sample_fingerprint() -> dict[str, float]:
    return {
        "sub_bass_pct": 0.1, "bass_pct": 0.15, "low_mid_pct": 0.2, "mid_pct": 0.25,
        "upper_mid_pct": 0.1, "presence_pct": 0.1, "air_pct": 0.1,
        "lufs": -14.0, "crest_db": 12.0, "bass_mid_ratio": 0.6,
        "tempo_bpm": 120.0, "rhythm_stability": 0.8, "transient_density": 0.5,
        "silence_ratio": 0.02, "spectral_centroid": 2400.0, "spectral_rolloff": 8000.0,
        "spectral_flatness": 0.3, "harmonic_ratio": 0.7, "pitch_stability": 0.85,
        "chroma_energy": 0.65, "dynamic_range_variation": 0.4,
        "loudness_variation_std": 2.1, "peak_consistency": 0.9,
        "stereo_width": 0.55, "phase_correlation": 0.9,
    }


def test_load_returns_fingerprint_with_empty_targets(
    cache_dir, audio_file, sample_fingerprint
):
    """The fingerprint_service path saves targets as {}; load() must still hit."""
    FingerprintStorage.save(audio_file, sample_fingerprint, {})

    result = FingerprintStorage.load(audio_file)
    assert result is not None, "load() must accept empty targets dict"
    fp, targets = result
    assert fp == sample_fingerprint
    assert targets == {}


def test_load_returns_fingerprint_with_real_targets(
    cache_dir, audio_file, sample_fingerprint
):
    """Mastering-target service saves real targets; round-trip preserves them."""
    real_targets = {"target_lufs": -14.0, "target_crest_db": 10.0}
    FingerprintStorage.save(audio_file, sample_fingerprint, real_targets)

    result = FingerprintStorage.load(audio_file)
    assert result is not None
    fp, targets = result
    assert fp == sample_fingerprint
    assert targets == real_targets


def test_load_rejects_missing_fingerprint(cache_dir, audio_file):
    """A .25d with no fingerprint dimension is still rejected."""
    cache_key = FingerprintStorage._get_cache_key(audio_file)
    cache_path = cache_dir / f"{cache_key}.25d"
    cache_path.write_text(json.dumps({
        "version": FingerprintStorage.VERSION,
        "cache_key": cache_key,
        "fingerprint": {},
        "mastering_targets": {"target_lufs": -14.0},
    }))

    assert FingerprintStorage.load(audio_file) is None


def test_load_normalizes_missing_targets_to_empty_dict(
    cache_dir, audio_file, sample_fingerprint
):
    """If ``mastering_targets`` key is absent entirely, return {} for type safety."""
    cache_key = FingerprintStorage._get_cache_key(audio_file)
    cache_path = cache_dir / f"{cache_key}.25d"
    cache_path.write_text(json.dumps({
        "version": FingerprintStorage.VERSION,
        "cache_key": cache_key,
        "fingerprint": sample_fingerprint,
        # mastering_targets intentionally omitted
    }))

    result = FingerprintStorage.load(audio_file)
    assert result is not None
    fp, targets = result
    assert fp == sample_fingerprint
    assert targets == {}, "missing targets key should normalize to empty dict, not None"


def test_is_valid_true_for_empty_targets(cache_dir, audio_file, sample_fingerprint):
    """`is_valid` mirrors `load() is not None` — empty targets must qualify."""
    FingerprintStorage.save(audio_file, sample_fingerprint, {})
    assert FingerprintStorage.is_valid(audio_file) is True
