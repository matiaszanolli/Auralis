"""
ML genre classifier sample-rate threading (#5244).

`create_ml_genre_classifier()` is a process-lifetime singleton whose
`FeatureExtractor` was hardcoded to 44100 Hz with no way to pass the real
sample rate of the audio being classified. `ContentAnalyzer` threads its
configured `sample_rate` into every other feature call but not this one, so
a pipeline constructed at a non-44100 `internal_sample_rate` got spectral /
mel / tempo features silently mis-scaled by the rate-mismatch ratio.

`classify()` now accepts the audio's rate and the classifier caches one
(immutable, shareable) extractor per distinct rate; the mixin passes
`self.sample_rate` through like every sibling feature call.
"""

from __future__ import annotations

import numpy as np
import pytest

import auralis.analysis.ml.genre_classifier as genre_classifier_module
from auralis.analysis.ml.feature_extractor import FeatureExtractor
from auralis.analysis.ml.genre_classifier import RuleBasedGenreClassifier
from auralis.core.analysis.content_analyzer import ContentAnalyzer


def _sine(freq_hz: float, seconds: float, sr: int) -> np.ndarray:
    t = np.arange(int(sr * seconds), dtype=np.float64) / sr
    return (0.5 * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


@pytest.fixture
def captured_rates(monkeypatch) -> list[int]:
    """Spy capturing the configured rate of every extractor that runs."""
    captured: list[int] = []
    real = FeatureExtractor.extract_features

    def spy(self: FeatureExtractor, audio: np.ndarray):
        captured.append(self.sample_rate)
        return real(self, audio)

    monkeypatch.setattr(FeatureExtractor, "extract_features", spy)
    return captured


def test_classify_with_explicit_rate_uses_that_extractor(captured_rates) -> None:
    classifier = RuleBasedGenreClassifier()
    audio = _sine(1000.0, 1.0, 48000)
    result = classifier.classify(audio, sample_rate=48000)
    assert captured_rates == [48000]
    assert result["primary"] in classifier.genres


def test_classify_without_rate_keeps_default_44100(captured_rates) -> None:
    """Backward compatibility: existing callers passing only audio are
    unchanged (default 44100 extractor, as before the fix)."""
    classifier = RuleBasedGenreClassifier()
    audio = _sine(1000.0, 1.0, 44100)
    classifier.classify(audio)
    assert captured_rates == [44100]


def test_content_analyzer_threads_configured_rate(captured_rates) -> None:
    """The production bug path: ContentAnalyzer configured at 48 kHz must
    not have its ML features computed by a 44100 Hz extractor."""
    analyzer = ContentAnalyzer(sample_rate=48000)
    audio = _sine(1000.0, 1.0, 48000)
    analyzer._classify_genre_advanced(audio)
    assert captured_rates == [48000]


def test_extractor_built_once_per_rate(monkeypatch) -> None:
    """The classifier caches per rate rather than rebuilding on every
    classify() call, preserving the singleton's allocate-once behavior
    (the reason create_ml_genre_classifier exists, #2528)."""

    class CountingExtractor(FeatureExtractor):
        built = 0

        def __init__(self, sample_rate: int = 44100):
            CountingExtractor.built += 1
            super().__init__(sample_rate)

    monkeypatch.setattr(
        genre_classifier_module, "FeatureExtractor", CountingExtractor
    )
    classifier = RuleBasedGenreClassifier()
    assert CountingExtractor.built == 1  # the default-rate extractor

    audio = _sine(1000.0, 1.0, 48000)
    classifier.classify(audio, sample_rate=48000)
    classifier.classify(audio, sample_rate=48000)
    classifier.classify(audio)  # default rate — already cached
    assert CountingExtractor.built == 2  # one per distinct rate, no more
