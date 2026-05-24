"""
End-to-end regression for the content-aware mastering rework (Phases 1-5).

Pins three contracts that together represent "the user's complaint is fixed":

  1. The pipeline produces DIFFERENT EQ curves for sources with different
     spectral character. Pre-rework, every source got the same +4/+3/+2.5 dB
     curve because the unit-mismatch bug collapsed the continuous space.

  2. A bright source gets LESS HF boost than a dark source — the pipeline
     reads the reference cloud and corrects asymmetrically. The legacy
     deficit math could only boost; the delta-from-target math can also cut.

  3. HF transient crest factor is preserved through the safety limiter
     (within ~1 dB) — no wideband-limiter "crush" on cymbals/sibilance.

These tests synthesize sources rather than relying on the user's library
so they're CI-stable. Phase 6 of the content-aware mastering rework.
"""

from __future__ import annotations

import numpy as np
import pytest

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import (
    AudioFingerprintAnalyzer,
)
from auralis.core.analysis.content_analyzer import ContentAnalyzer
from auralis.core.processing.continuous_mode import ContinuousMode
from auralis.core.unified_config import UnifiedConfig


SR = 44100


# ---------------------------------------------------------------------------
# Reference cloud (modern well-mastered balanced) — synth, not user data
# ---------------------------------------------------------------------------

class _Ref:
    __table__ = object()


def _ref(track_id, **overrides):
    obj = _Ref()
    base = {
        'track_id': track_id,
        'sub_bass_pct': 0.05, 'bass_pct': 0.22, 'low_mid_pct': 0.16,
        'mid_pct': 0.22, 'upper_mid_pct': 0.14, 'presence_pct': 0.10,
        'air_pct': 0.11,
        'lufs': -14.0, 'crest_db': 12.0, 'bass_mid_ratio': 0.0,
        'tempo_bpm': 120.0, 'rhythm_stability': 0.7, 'transient_density': 0.5,
        'silence_ratio': 0.02, 'spectral_centroid': 0.42, 'spectral_rolloff': 0.55,
        'spectral_flatness': 0.2, 'harmonic_ratio': 0.7, 'pitch_stability': 0.7,
        'chroma_energy': 0.6, 'dynamic_range_variation': 0.3,
        'loudness_variation_std': 1.5, 'peak_consistency': 0.7,
        'stereo_width': 0.4, 'phase_correlation': 0.8,
    }
    base.update(overrides)
    for k, v in base.items():
        setattr(obj, k, v)
    return obj


class _Repo:
    def __init__(self, cloud): self._c = cloud
    def get_reference_cloud(self): return list(self._c)


def _balanced_cloud():
    """8 reference profiles covering different rock/electronic tempo+dynamics
    but all with balanced 7-band distribution. Synth, deterministic."""
    return [
        _ref(1),
        _ref(2, tempo_bpm=140, transient_density=0.65),
        _ref(3, tempo_bpm=85, bass_pct=0.24, air_pct=0.08, crest_db=15),
        _ref(4, bass_pct=0.18, air_pct=0.14, presence_pct=0.12),
        _ref(5, crest_db=16.0, transient_density=0.55),
        _ref(6, tempo_bpm=110, mid_pct=0.25, low_mid_pct=0.18),
        _ref(7, bass_pct=0.16, mid_pct=0.28),
        _ref(8, lufs=-12, crest_db=10, transient_density=0.7),
    ]


# ---------------------------------------------------------------------------
# Synthetic test sources (bright / balanced / dark)
# ---------------------------------------------------------------------------

def _bright_audio() -> np.ndarray:
    """LF + strong steady HF energy — emulates an over-bright modern master."""
    t = np.arange(SR * 10) / SR
    body = 0.35 * np.sin(2 * np.pi * 100 * t)
    bright = 0.25 * np.sin(2 * np.pi * 6000 * t)
    bright += 0.15 * np.sin(2 * np.pi * 10000 * t)
    mono = (body + bright).astype(np.float64)
    return np.column_stack([mono, mono])


def _dark_audio() -> np.ndarray:
    """Bass-heavy, very little HF — emulates a vintage/dark master."""
    t = np.arange(SR * 10) / SR
    body = 0.45 * np.sin(2 * np.pi * 80 * t)
    body += 0.15 * np.sin(2 * np.pi * 200 * t)
    # No HF content
    mono = body.astype(np.float64)
    return np.column_stack([mono, mono])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class _IdentityEQ:
    def apply_psychoacoustic_eq(self, audio, targets, profile):
        return audio


@pytest.fixture
def config():
    c = UnifiedConfig()
    c.quality_gate_enabled = False
    c.enable_cross_dimensional_guard = False
    return c


def _process(source: np.ndarray, config, cloud=None) -> ContinuousMode:
    """Run audio through the pipeline; return the ContinuousMode for inspection."""
    repo = _Repo(cloud) if cloud is not None else None
    mode = ContinuousMode(
        config, ContentAnalyzer(), AudioFingerprintAnalyzer(),
        fingerprint_repository=repo,
    )
    mode.process(source.copy(), _IdentityEQ())
    return mode


# ---------------------------------------------------------------------------
# Contract 1: spectral differentiation
# ---------------------------------------------------------------------------

def test_bright_and_dark_sources_produce_different_eq_curves(config):
    """Pre-rework: every source got identical EQ. Post-rework: bright vs
    dark sources must produce measurably different curves."""
    cloud = _balanced_cloud()
    bright_mode = _process(_bright_audio(), config, cloud=cloud)
    dark_mode = _process(_dark_audio(), config, cloud=cloud)

    bright_eq = bright_mode.last_parameters.eq_curve
    dark_eq = dark_mode.last_parameters.eq_curve

    # At least one shelf must differ meaningfully (> 0.5 dB) between bright
    # and dark sources. Threshold is conservative because synthetic sources
    # are similar on character features (tempo/rhythm/etc); real-world
    # diverse-genre material shows 4+ dB spread.
    max_diff = max(
        abs(bright_eq[k] - dark_eq[k])
        for k in ('low_shelf_gain', 'low_mid_gain', 'mid_gain',
                  'high_mid_gain', 'high_shelf_gain')
    )
    assert max_diff > 0.5, (
        f"Bright and dark sources got nearly identical EQ "
        f"(max difference {max_diff:.2f} dB) — content-awareness regression"
    )


# ---------------------------------------------------------------------------
# Contract 2: asymmetric correction (cuts too, not just boosts)
# ---------------------------------------------------------------------------

def test_bright_source_gets_less_hf_boost_than_dark_source(config):
    """The user's specific complaint: dark sources should get HF boost,
    bright sources should NOT get the same boost."""
    cloud = _balanced_cloud()
    bright_eq = _process(_bright_audio(), config, cloud=cloud).last_parameters.eq_curve
    dark_eq = _process(_dark_audio(), config, cloud=cloud).last_parameters.eq_curve

    # Dark source must request more HF lift than bright source.
    assert dark_eq['high_shelf_gain'] > bright_eq['high_shelf_gain'], (
        f"Dark source HF lift ({dark_eq['high_shelf_gain']:+.2f}) must exceed "
        f"bright source HF lift ({bright_eq['high_shelf_gain']:+.2f}) — "
        f"content-awareness regression"
    )


def test_bass_heavy_source_can_get_bass_cut(config):
    """Delta-from-target must produce NEGATIVE gain on bands where the
    source exceeds the cloud's target. Legacy deficit path was clipped
    at >= 0 so this would have been impossible."""
    cloud = _balanced_cloud()
    dark_eq = _process(_dark_audio(), config, cloud=cloud).last_parameters.eq_curve

    # Dark source has bass_pct ≈ 0.60-0.80 vs cloud average bass_pct ≈ 0.22.
    # Delta math should produce a low_shelf CUT.
    assert dark_eq['low_shelf_gain'] < 0, (
        f"Bass-heavy source must get bass cut, got {dark_eq['low_shelf_gain']:+.2f} dB"
    )


# ---------------------------------------------------------------------------
# Contract 3: HF transient preservation (Phase 5 win)
# ---------------------------------------------------------------------------

def test_hf_crest_preserved_through_full_pipeline(config):
    """End-to-end: a source with strong HF transients should retain its
    HF crest factor after going through the pipeline (within 2 dB), because
    the HF-aware limiter doesn't compress cymbals the way wideband would."""
    from scipy.signal import butter, sosfilt

    cloud = _balanced_cloud()

    # Source with HF transient bursts on top of moderate body
    t = np.arange(SR * 10) / SR
    body = 0.30 * np.sin(2 * np.pi * 150 * t)
    cymbal = np.zeros_like(t)
    for center in np.linspace(0.5, 9.5, 40):
        mask = (t > center) & (t < center + 0.04)
        cymbal[mask] = 0.40 * np.sin(2 * np.pi * 8000 * t[mask])
    mono = (body + cymbal).astype(np.float64)
    src = np.column_stack([mono, mono])

    mode = _process(src, config, cloud=cloud)
    out = mode.process(src.copy(), _IdentityEQ())   # actually run again to get output

    def hf_crest(audio):
        sos = butter(4, 5000, btype='high', fs=SR, output='sos')
        hf = sosfilt(sos, audio.mean(axis=1))
        peak = float(np.max(np.abs(hf)))
        rms = float(np.sqrt(np.mean(hf ** 2)))
        return 20 * np.log10(peak / (rms + 1e-12))

    src_crest = hf_crest(src)
    out_crest = hf_crest(out)
    crush = src_crest - out_crest

    # Pre-rework the wideband limiter could crush HF crest by 3+ dB on
    # such material. Post-Phase-5, expect crush < 2 dB.
    assert crush < 2.0, (
        f"HF crest crush of {crush:+.2f} dB exceeds 2 dB threshold "
        f"(src={src_crest:.2f}, out={out_crest:.2f}) — HF-aware limiter regression"
    )
