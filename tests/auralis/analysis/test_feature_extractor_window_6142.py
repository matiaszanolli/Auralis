"""
FeatureExtractor whole-track windowing (#6142).

Every spectral/MFCC/chroma/autocorrelation feature was computed from the
first 4096/8192 samples only (~93-186 ms), so the genre label — and the
genre-dependent EQ curve — was effectively decided by the track's lead-in:
a fade-in or digital-silence head flipped it. Features are now averaged
over frames spread evenly across the whole track.
"""

from __future__ import annotations

import numpy as np

from auralis.analysis.ml.feature_extractor import FeatureExtractor
from auralis.analysis.ml.genre_classifier import RuleBasedGenreClassifier

SR = 44100


def _tone(freq_hz: float, seconds: float, amp: float = 0.3) -> np.ndarray:
    t = np.arange(int(SR * seconds), dtype=np.float64) / SR
    return (amp * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


def _noise(seconds: float, seed: int, amp: float = 0.3) -> np.ndarray:
    return (amp * np.random.default_rng(seed).uniform(-1, 1, int(SR * seconds))).astype(np.float32)


def test_silent_lead_in_does_not_flip_classification() -> None:
    """The acceptance case from the issue: the same 220 Hz tone with and
    without a 0.3 s silent head classifies identically (a silent head
    used to force 'metal' while the clean tone gave 'classical')."""
    tone = _tone(220.0, 6.0)
    with_lead_in = np.concatenate([np.zeros(int(SR * 0.3), np.float32), tone])
    classifier = RuleBasedGenreClassifier()
    assert classifier.classify(with_lead_in)["primary"] == classifier.classify(tone)["primary"]


def test_features_track_dominant_content_not_the_head() -> None:
    """0.2 s of noise followed by tone must look like the tone, not the
    noise (16 spread frames put at most one frame in the head)."""
    tone = _tone(440.0, 5.8)
    headed = np.concatenate([_noise(0.2, seed=6142), tone])
    fe = FeatureExtractor(sample_rate=SR)
    a = fe.extract_features(tone)
    b = fe.extract_features(headed)
    assert abs(a.spectral_centroid - b.spectral_centroid) / a.spectral_centroid < 0.1
    assert abs(a.fundamental_frequency - b.fundamental_frequency) < 5.0


def test_same_head_different_body_gives_different_features() -> None:
    """Direct anti-regression: two tracks sharing their first 93 ms but
    diverging after must not extract identical features (they used to —
    only the head was analyzed)."""
    head = _noise(0.5, seed=99)
    body_tone = _tone(440.0, 5.5)
    body_noise = _noise(5.5, seed=100)
    fe = FeatureExtractor(sample_rate=SR)
    a = fe.extract_features(np.concatenate([head, body_tone]))
    b = fe.extract_features(np.concatenate([head, body_noise]))
    assert abs(a.spectral_centroid - b.spectral_centroid) > 500.0
    assert abs(a.fundamental_frequency - b.fundamental_frequency) > 50.0


def test_frame_offsets_are_deterministic_and_in_bounds() -> None:
    fe = FeatureExtractor(sample_rate=SR)
    n = SR * 4
    offs = fe._frame_offsets(n, fe.FFT_SIZE, fe.SPECTRAL_FRAMES)
    assert len(offs) == fe.SPECTRAL_FRAMES
    assert offs == fe._frame_offsets(n, fe.FFT_SIZE, fe.SPECTRAL_FRAMES)
    assert all(0 <= o <= n - fe.FFT_SIZE for o in offs)
    assert offs[0] == 0 and offs[-1] == n - fe.FFT_SIZE
    # Short input collapses to a single (zero) frame instead of crashing.
    assert fe._frame_offsets(fe.FFT_SIZE - 1, fe.FFT_SIZE, fe.SPECTRAL_FRAMES) == [0]


def test_short_input_features_are_finite() -> None:
    """Inputs not much longer than one frame (extract_features pads to
    >= 1 s, so this exercises the padding guard in the frame loop)."""
    fe = FeatureExtractor(sample_rate=SR)
    f = fe.extract_features(_tone(440.0, 0.01))  # padded to 1 s internally
    assert np.isfinite(f.spectral_bandwidth)
    assert np.isfinite(f.spectral_flatness)
    assert all(np.isfinite(c) for c in f.mfcc)
    assert all(np.isfinite(c) for c in f.chroma)
