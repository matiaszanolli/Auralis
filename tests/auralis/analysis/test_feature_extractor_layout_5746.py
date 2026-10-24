"""
FeatureExtractor channel layout (#5746).

The extractor downmixed with the channels-first assumption (originally
``np.mean(audio, axis=0)``, later ``to_mono(audio, 'channels_samples')``),
while the engine and ContentAnalyzer hand it ``(samples, channels)`` arrays.
An ``(N, 2)`` track was reduced to a 2-element array, zero-padded to 1 s,
and every feature described near-silence — classify() returned a constant
genre for all stereo input. The extractor now uses to_mono()'s engine-layout
default and rejects channels-first misuse explicitly.
"""

from __future__ import annotations

import numpy as np
import pytest

from auralis.analysis.ml.feature_extractor import FeatureExtractor
from auralis.analysis.ml.genre_classifier import RuleBasedGenreClassifier
from auralis.core.analysis.content_analyzer import ContentAnalyzer

SR = 44100


def _tone_plus_noise(seconds: float = 4.0) -> np.ndarray:
    t = np.arange(int(SR * seconds), dtype=np.float64) / SR
    tone = 0.2 * np.sin(2 * np.pi * 220.0 * t)
    noise = 0.05 * np.random.default_rng(5244).uniform(-1, 1, len(t))
    return (tone + noise).astype(np.float32)


def test_stereo_samples_channels_matches_mono_features() -> None:
    """(N, 2) and its mono mix must give the same features — the core
    acceptance criterion of #5746."""
    mono = _tone_plus_noise()
    stereo = np.stack([mono, mono], axis=1)
    extractor = FeatureExtractor(sample_rate=SR)
    a = extractor.extract_features(mono)
    b = extractor.extract_features(stereo)
    for field in ("rms", "spectral_centroid", "tempo", "zero_crossing_rate"):
        assert getattr(a, field) == pytest.approx(getattr(b, field), rel=1e-6), field


def test_stereo_features_are_not_silence() -> None:
    """Before the fix an (N, 2) input yielded rms ~1e-7 (a 2-sample signal
    padded to 1 s of zeros)."""
    mono = _tone_plus_noise()
    stereo = np.stack([mono, mono], axis=1)
    features = FeatureExtractor(sample_rate=SR).extract_features(stereo)
    assert features.rms > 0.1


def test_classify_stereo_same_primary_genre_as_mono() -> None:
    mono = _tone_plus_noise()
    stereo = np.stack([mono, mono], axis=1)
    classifier = RuleBasedGenreClassifier()
    assert classifier.classify(stereo)["primary"] == classifier.classify(mono)["primary"]


def test_content_analyzer_genre_from_non_silent_stereo() -> None:
    """The production path: ContentAnalyzer.analyze_content on (N, 2)."""
    mono = _tone_plus_noise()
    stereo = np.stack([mono, mono], axis=1)
    analyzer = ContentAnalyzer(sample_rate=SR)
    genre = analyzer.analyze_content(stereo)["genre_info"]
    # Near-silence used to force the low-confidence "pop" fallback with
    # confidence exactly 0.5; a real signal classifies with evidence.
    assert not (genre["primary"] == "pop" and genre["confidence"] == 0.5)


def test_channels_first_input_rejected_explicitly() -> None:
    """(2, N) channels-first input must not be silently misread."""
    mono = _tone_plus_noise()
    channels_first = np.stack([mono, mono], axis=0)
    with pytest.raises(ValueError, match="samples, channels"):
        FeatureExtractor(sample_rate=SR).extract_features(channels_first)
