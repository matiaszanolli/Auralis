"""
FingerprintStorage is algorithm-version aware (#5697)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The central ``~/.auralis/fingerprints/<key>.25d`` cache only validated its
FILE-format version ("2.0"), never ``FINGERPRINT_ALGORITHM_VERSION``. Tier 2
of ``FingerprintService.get_or_compute`` therefore served fingerprints
computed by older algorithms and handed them to ``upsert()``, which stamps
``fingerprint_version = FINGERPRINT_ALGORITHM_VERSION`` unconditionally
(#5572) — so stale values were persisted as current rows the sweep never
revisited.

The rule now lives in ONE place: ``save()`` stamps the algorithm version
into the stored fingerprint, ``load()`` refuses entries whose stamp is
missing or older. The backend's private copy of the check
(``fingerprint_loading.load_from_file``) was collapsed onto the shared one.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION
from auralis.analysis.fingerprint.fingerprint_service import FingerprintService
from auralis.analysis.fingerprint.fingerprint_storage import FingerprintStorage


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    cache = tmp_path / "fingerprints"
    cache.mkdir()
    monkeypatch.setattr(
        FingerprintStorage, "_get_cache_dir", staticmethod(lambda: cache)
    )
    return cache


@pytest.fixture
def audio_file(tmp_path):
    path = tmp_path / "track.flac"
    path.write_bytes(b"FAKE FLAC HEADER " + b"\x00" * 4096)
    return path


def _valid_fingerprint() -> dict[str, float]:
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


def _write_25d(cache_dir, audio_file, fingerprint) -> None:
    """Write a central .25d exactly as an old writer would have."""
    cache_key = FingerprintStorage._get_cache_key(audio_file)
    (cache_dir / f"{cache_key}.25d").write_text(json.dumps({
        "version": FingerprintStorage.VERSION,
        "cache_key": cache_key,
        "fingerprint": fingerprint,
        "mastering_targets": {},
    }))


def test_save_stamps_algorithm_version(cache_dir, audio_file):
    fp = _valid_fingerprint()
    assert "fingerprint_version" not in fp

    FingerprintStorage.save(audio_file, fp, {}, sample_rate=44100, duration=30.0)

    loaded = FingerprintStorage.load(audio_file)
    assert loaded is not None
    assert loaded[0]["fingerprint_version"] == FINGERPRINT_ALGORITHM_VERSION


def test_unversioned_sidecar_is_rejected(cache_dir, audio_file):
    """The pre-stamp central cache (thousands of files on real installs)."""
    _write_25d(cache_dir, audio_file, _valid_fingerprint())

    assert FingerprintStorage.load(audio_file) is None


def test_old_algorithm_sidecar_is_rejected(cache_dir, audio_file):
    """v1 values (pre #5556 stereo layout etc.) must trigger a recompute."""
    fp = _valid_fingerprint()
    fp["fingerprint_version"] = FINGERPRINT_ALGORITHM_VERSION - 1

    _write_25d(cache_dir, audio_file, fp)

    assert FingerprintStorage.load(audio_file) is None


def test_round_trip_does_not_recompute(cache_dir, audio_file):
    """save() -> load() must round-trip, or every fresh compute is thrown
    away on the next access (a recompute loop)."""
    saved = _valid_fingerprint()
    FingerprintStorage.save(audio_file, saved, {}, sample_rate=44100, duration=30.0)

    loaded = FingerprintStorage.load(audio_file)

    assert loaded is not None
    fingerprint, targets = loaded
    assert {name: fingerprint[name] for name in saved} == saved  # load() adds fingerprint_version
    assert targets == {}


def test_get_or_compute_recomputes_instead_of_serving_stale(cache_dir, audio_file):
    """End-to-end tier-2 fix: a stale central sidecar with no DB row must
    lead to a recompute, and the recomputed value is what callers get."""
    stale = _valid_fingerprint()
    stale["lufs"] = -99.0  # marker: the probe value the audit used
    _write_25d(cache_dir, audio_file, stale)

    recomputed = _valid_fingerprint()
    recomputed["lufs"] = -14.0

    service = FingerprintService(db_path=cache_dir / "missing.db")
    with patch.object(
        service,
        "_compute_fingerprint",
        return_value=recomputed,
    ) as compute, patch.object(
        service,
        "_save_to_database",
    ):
        result = service.get_or_compute(audio_file)

    assert compute.called, "tier 2 must not serve the unversioned sidecar"
    assert result is not None
    assert result["lufs"] == -14.0


def test_get_or_compute_tier2_hit_avoids_recompute(cache_dir, audio_file):
    """A current-version sidecar is still served from the file cache."""
    FingerprintStorage.save(audio_file, _valid_fingerprint(), {}, sample_rate=44100, duration=30.0)

    service = FingerprintService(db_path=cache_dir / "missing.db")
    with patch.object(
        service, "_compute_fingerprint", return_value=None
    ) as compute, patch.object(service, "_save_to_database"):
        result = service.get_or_compute(audio_file)

    assert not compute.called
    assert result is not None
    assert result["fingerprint_version"] == FINGERPRINT_ALGORITHM_VERSION
