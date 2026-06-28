"""
FeatureExtractor crest factor uses the padded mono signal (#4138).

extract_features() builds mono_audio (channel-averaged, padded to >= sample_rate)
and computes every feature from it — except crest_factor, which used the original
unpadded stereo array (inter-channel rather than temporal dynamics for short
clips). It now matches the siblings.
"""

import numpy as np

from auralis.analysis.ml.feature_extractor import FeatureExtractor
from auralis.dsp.utils.spectral import crest_factor


def test_crest_factor_matches_padded_mono_for_short_stereo():
    fe = FeatureExtractor()
    sr = fe.sample_rate

    rng = np.random.RandomState(0)
    audio = (rng.randn(2, 1000) * 0.2).astype(np.float32)  # short stereo (< 1 s)

    # Reproduce the function's mono + min-length padding.
    mono = np.mean(audio, axis=0)
    padded = np.zeros(sr)
    padded[: len(mono)] = mono
    expected = crest_factor(padded)

    feats = fe.extract_features(audio)
    assert abs(feats.crest_factor_db - float(expected)) < 1e-6


def test_crest_factor_differs_from_raw_stereo_for_short_clip():
    """Guard: the value should no longer equal crest_factor(original stereo)."""
    fe = FeatureExtractor()
    rng = np.random.RandomState(1)
    audio = (rng.randn(2, 1000) * 0.2).astype(np.float32)

    feats = fe.extract_features(audio)
    raw_stereo = float(crest_factor(audio))
    # Padding with zeros changes peak/RMS, so the padded-mono crest differs.
    assert abs(feats.crest_factor_db - raw_stereo) > 1e-3
