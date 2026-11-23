"""
Integration test: ContinuousMode wires the reference cloud into the EQ law.

When ContinuousMode is constructed with a fingerprint repository that returns a
non-empty reference cloud, the targets law receives the cloud's soft k-NN band
centers. With no repository or an empty cloud it receives the corpus centers.
Either way it is the one law the streaming fixed targets use too (#6356).
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import (
    AudioFingerprintAnalyzer,
)
from auralis.core.analysis.content_analyzer import ContentAnalyzer
from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.processing import continuous_mode as cm
from auralis.core.processing.continuous_mode import ContinuousMode
from auralis.dsp.constants import CORPUS_BAND_CENTERS

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


def _centers_used(mode, audio):
    """The band_centers ContinuousMode handed the targets law for one process()."""
    with patch.object(
        cm, 'generate_targets_from_fingerprint', wraps=cm.generate_targets_from_fingerprint,
    ) as law:
        mode.process(audio.copy(), _IdentityEQ())
    assert law.call_count == 1
    return law.call_args.args[1]


# ---------------------------------------------------------------------------
# No cloud: corpus centers
# ---------------------------------------------------------------------------

def test_no_repository_uses_corpus_centers(config, audio_5s):
    mode = ContinuousMode(config, ContentAnalyzer(), AudioFingerprintAnalyzer())
    assert _centers_used(mode, audio_5s) == CORPUS_BAND_CENTERS


def test_mastering_path_has_no_recording_type_classifier(config):
    """Mastering parameters must come from measurements, never a music tag."""
    mode = ContinuousMode(config, ContentAnalyzer(), AudioFingerprintAnalyzer())
    processor = HybridProcessor(config)

    for instance in (mode, processor):
        assert not hasattr(instance, 'recording_type_detector')
        assert not hasattr(instance, 'last_recording_type')
        assert not hasattr(instance, 'last_adaptive_params')


def test_empty_cloud_uses_corpus_centers(config, audio_5s):
    mode = ContinuousMode(
        config, ContentAnalyzer(), AudioFingerprintAnalyzer(),
        fingerprint_repository=_FakeRepo([]),
    )
    assert _centers_used(mode, audio_5s) == CORPUS_BAND_CENTERS


# ---------------------------------------------------------------------------
# Non-empty cloud: k-NN centers
# ---------------------------------------------------------------------------

def test_non_empty_cloud_supplies_the_band_centers(config, audio_5s):
    """Identical references -> the k-NN target is exactly their band shares."""
    cloud = [_fake_reference(i) for i in range(5)]
    mode = ContinuousMode(
        config, ContentAnalyzer(), AudioFingerprintAnalyzer(),
        fingerprint_repository=_FakeRepo(cloud),
    )

    centers = _centers_used(mode, audio_5s)

    assert centers['bass'] == pytest.approx(0.20)
    assert centers['mid'] == pytest.approx(0.25)
    assert centers['presence'] == pytest.approx(0.10)


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


def test_cloud_changes_eq_curve_versus_corpus_centers(config, audio_5s):
    """Smoking-gun integration test: feeding a cloud must produce a measurably
    different EQ curve than the corpus centers on the same source.

    Asserts the cloud's centers actually reach the curve, not just the call.
    """
    # Strongly bass-heavy mono+noise — should drive the EQ law toward a CUT.
    sr = config.internal_sample_rate
    rng = np.random.default_rng(7)
    t = np.arange(sr * 5) / sr
    bass_signal = 0.4 * np.sin(2 * np.pi * 80 * t).astype(np.float64)
    noise = rng.standard_normal(sr * 5).astype(np.float64) * 0.05
    stereo = np.column_stack([bass_signal + noise, bass_signal + noise])

    # Run 1: no cloud → corpus centers
    mode_corpus = ContinuousMode(config, ContentAnalyzer(), AudioFingerprintAnalyzer())
    mode_corpus.process(stereo.copy(), _IdentityEQ())
    corpus_eq = dict(mode_corpus.last_parameters.eq_curve)

    # Run 2: a cloud with far less bass than the corpus → k-NN centers
    cloud = [_fake_reference(i, bass_pct=0.10, air_pct=0.20) for i in range(10)]
    mode_cloud = ContinuousMode(
        config, ContentAnalyzer(), AudioFingerprintAnalyzer(),
        fingerprint_repository=_FakeRepo(cloud),
    )
    mode_cloud.process(stereo.copy(), _IdentityEQ())
    cloud_eq = dict(mode_cloud.last_parameters.eq_curve)

    # The two continuous target sources should differ on at least one gain.
    differences = {
        k: cloud_eq[k] - corpus_eq[k]
        for k in ('low_shelf_gain', 'low_mid_gain', 'mid_gain',
                  'high_mid_gain', 'high_shelf_gain')
    }
    assert any(abs(d) > 0.1 for d in differences.values()), (
        f"Cloud centers produced the same curve as corpus centers: {differences}"
    )
    # Both respond with a signed cut on this bass-heavy source, the cloud harder.
    assert cloud_eq['low_shelf_gain'] < 0.0
    assert cloud_eq['low_shelf_gain'] < corpus_eq['low_shelf_gain']
    assert corpus_eq['low_shelf_gain'] < 0.0, (
        f"Bass-heavy source: corpus low_shelf={corpus_eq['low_shelf_gain']:+.2f}, "
        f"cloud low_shelf={cloud_eq['low_shelf_gain']:+.2f}"
    )
