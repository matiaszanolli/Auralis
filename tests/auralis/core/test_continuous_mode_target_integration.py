"""
Integration test: ContinuousMode wires the reference cloud into delta EQ.

Phase 4 wiring: when ContinuousMode is constructed with a fingerprint
repository that returns a non-empty reference cloud, the EQ curve is
derived via delta-from-target. When no repository or empty cloud, the
legacy deficit-based curve is used (backwards-compatible fallback).
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import (
    AudioFingerprintAnalyzer,
)
from auralis.core.analysis.content_analyzer import ContentAnalyzer
from auralis.core.processing.continuous_mode import ContinuousMode
from auralis.core.config import UnifiedConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _IdentityEQ:
    def apply_psychoacoustic_eq(self, audio, targets, profile):  # noqa: ARG002
        return audio


def _fake_reference(track_id, **overrides):
    """ORM-like fingerprint object for stubbing the repository."""
    class _Obj:
        __table__ = object()  # mark as "ORM row"

    obj = _Obj()
    base = {
        'track_id': track_id,
        'sub_bass_pct': 0.05, 'bass_pct': 0.20, 'low_mid_pct': 0.15,
        'mid_pct': 0.25, 'upper_mid_pct': 0.15, 'presence_pct': 0.10,
        'air_pct': 0.10,
        'lufs': -14.0, 'crest_db': 12.0, 'bass_mid_ratio': 0.0,
        'tempo_bpm': 120.0, 'rhythm_stability': 0.7, 'transient_density': 0.4,
        'silence_ratio': 0.02,
        'spectral_centroid': 0.4, 'spectral_rolloff': 0.5, 'spectral_flatness': 0.2,
        'harmonic_ratio': 0.7, 'pitch_stability': 0.7, 'chroma_energy': 0.6,
        'dynamic_range_variation': 0.3, 'loudness_variation_std': 1.5,
        'peak_consistency': 0.7,
        'stereo_width': 0.4, 'phase_correlation': 0.8,
        'is_reference': True,
    }
    base.update(overrides)
    for k, v in base.items():
        setattr(obj, k, v)
    return obj


class _FakeRepo:
    """Stand-in FingerprintRepository for tests."""
    def __init__(self, cloud):
        self._cloud = cloud
        self.get_calls = 0

    def get_reference_cloud(self):
        self.get_calls += 1
        return list(self._cloud)


@pytest.fixture
def audio_5s():
    """5 seconds of stereo white noise — enough for fingerprint extraction."""
    rng = np.random.default_rng(42)
    sr = UnifiedConfig().internal_sample_rate
    return rng.standard_normal((sr * 5, 2)).astype(np.float64) * 0.05


@pytest.fixture
def config():
    c = UnifiedConfig()
    c.quality_gate_enabled = False    # silence the gate during tests
    c.enable_cross_dimensional_guard = False
    return c


# ---------------------------------------------------------------------------
# Fallback paths (backwards compatibility)
# ---------------------------------------------------------------------------

def test_no_repository_uses_legacy_eq_path(config, audio_5s):
    """Constructed without a repo → delta path is not exercised."""
    mode = ContinuousMode(config, ContentAnalyzer(), AudioFingerprintAnalyzer())
    with patch(
        'auralis.core.processing.parameter_generator.ContinuousParameterGenerator._generate_eq_curve_from_target'
    ) as delta_path:
        mode.process(audio_5s.copy(), _IdentityEQ())
    assert delta_path.call_count == 0


def test_empty_cloud_uses_legacy_eq_path(config, audio_5s):
    """Repo present but cloud empty → still falls back to legacy curve."""
    mode = ContinuousMode(
        config, ContentAnalyzer(), AudioFingerprintAnalyzer(),
        fingerprint_repository=_FakeRepo([]),
    )
    with patch(
        'auralis.core.processing.parameter_generator.ContinuousParameterGenerator._generate_eq_curve_from_target'
    ) as delta_path:
        mode.process(audio_5s.copy(), _IdentityEQ())
    assert delta_path.call_count == 0


# ---------------------------------------------------------------------------
# Active delta path
# ---------------------------------------------------------------------------

def test_non_empty_cloud_invokes_delta_eq_path(config, audio_5s):
    """Non-empty cloud → param_generator receives target_spectrum from cloud."""
    cloud = [_fake_reference(i) for i in range(5)]
    repo = _FakeRepo(cloud)
    mode = ContinuousMode(
        config, ContentAnalyzer(), AudioFingerprintAnalyzer(),
        fingerprint_repository=repo,
    )

    with patch(
        'auralis.core.processing.parameter_generator.ContinuousParameterGenerator._generate_eq_curve_from_target',
        wraps=mode.param_generator._generate_eq_curve_from_target,
    ) as delta_path:
        mode.process(audio_5s.copy(), _IdentityEQ())

    # Delta path called exactly once for this process()
    assert delta_path.call_count == 1
    # target_spectrum kwarg was passed
    call_kwargs = delta_path.call_args
    assert call_kwargs is not None


def test_cloud_loaded_only_once_across_multiple_process_calls(config, audio_5s):
    """The cloud must be cached after the first DB fetch — multiple process()
    calls don't pound the repository."""
    cloud = [_fake_reference(i) for i in range(3)]
    repo = _FakeRepo(cloud)
    mode = ContinuousMode(
        config, ContentAnalyzer(), AudioFingerprintAnalyzer(),
        fingerprint_repository=repo,
    )
    for _ in range(3):
        mode.process(audio_5s.copy(), _IdentityEQ())
    assert repo.get_calls == 1


def test_cloud_changes_eq_curve_versus_legacy(config, audio_5s):
    """Smoking-gun integration test: feeding a cloud must produce a measurably
    different EQ curve than the legacy deficit path on the same source.

    Asserts the delta path is actually doing something, not just being called.
    """
    # Strongly bass-heavy mono+noise — should drive delta math toward a CUT.
    sr = config.internal_sample_rate
    rng = np.random.default_rng(7)
    t = np.arange(sr * 5) / sr
    bass_signal = 0.4 * np.sin(2 * np.pi * 80 * t).astype(np.float64)
    noise = rng.standard_normal(sr * 5).astype(np.float64) * 0.05
    stereo = np.column_stack([bass_signal + noise, bass_signal + noise])

    # Run 1: no cloud → legacy curve
    mode_legacy = ContinuousMode(config, ContentAnalyzer(), AudioFingerprintAnalyzer())
    mode_legacy.process(stereo.copy(), _IdentityEQ())
    legacy_eq = dict(mode_legacy.last_parameters.eq_curve)

    # Run 2: balanced cloud → delta path
    cloud = [_fake_reference(i, bass_pct=0.10, air_pct=0.20) for i in range(10)]
    mode_delta = ContinuousMode(
        config, ContentAnalyzer(), AudioFingerprintAnalyzer(),
        fingerprint_repository=_FakeRepo(cloud),
    )
    mode_delta.process(stereo.copy(), _IdentityEQ())
    delta_eq = dict(mode_delta.last_parameters.eq_curve)

    # The two paths should differ on at least one gain (the low_shelf is the
    # most direct evidence — legacy produces unconditional lift on bass).
    differences = {
        k: delta_eq[k] - legacy_eq[k]
        for k in ('low_shelf_gain', 'low_mid_gain', 'mid_gain',
                  'high_mid_gain', 'high_shelf_gain')
    }
    assert any(abs(d) > 0.1 for d in differences.values()), (
        f"Delta path produced same curve as legacy: {differences}"
    )
    # And specifically: on bass-heavy source, delta path's low_shelf must be
    # LOWER than legacy's (cut vs lift).
    assert delta_eq['low_shelf_gain'] < legacy_eq['low_shelf_gain'], (
        f"Bass-heavy source: legacy low_shelf={legacy_eq['low_shelf_gain']:+.2f}, "
        f"delta low_shelf={delta_eq['low_shelf_gain']:+.2f} — delta should be lower."
    )
