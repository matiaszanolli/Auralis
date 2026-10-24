"""
FFT-size constants consolidation (#6229).

4096 was a default in four config classes and a bare literal on ~20 lines
of the genre-classifier feature extractor. The pipeline's canonical size
now lives in auralis/dsp/constants.py (DEFAULT_FFT_SIZE), read by
UnifiedConfig and the settings classes; the extractor's model-input
contract is named as FeatureExtractor.FFT_SIZE / N_BINS / AC_SIZE. This
file pins that the refactor changed no extracted value: the golden vector
below was captured from the pre-change code on a fixed fixture.
"""

from __future__ import annotations

import json

import numpy as np

from auralis.analysis.ml.feature_extractor import FeatureExtractor
from auralis.core.config.unified_config import UnifiedConfig
from auralis.dsp.constants import DEFAULT_FFT_SIZE
from auralis.dsp.eq.psychoacoustic_eq import EQSettings
from auralis.analysis.spectrum_analyzer import SpectrumSettings

# Captured from the extractor at the #6229 constants refactor and
# re-baselined once for #6142's whole-track windowing (a deliberate
# feature-semantics change). Pins the current contract so any future
# accidental drift (constants refactor, window change) fails loudly.
GOLDEN = {
    "rms": 0.19790193438529968,
    "spectral_centroid": 9561.338354300538,
    "spectral_bandwidth": 6978.863206657909,
    "spectral_flatness": 0.8782261229514094,
    "spectral_contrast": [0.8386013647541404, 25.90923017989843, 2.1065120786428446,
                          0.88774991966784, 0.8200932320207355, 0.7793722677975894],
    "energy_low": 0.0016011476034777322,
    "energy_mid": 0.9421016003912444,
    "energy_high": 0.05629725200527733,
    "mfcc": [76.59321816075672, -5.164738016015101, 2.6102941753641016, 0.6510047900147367,
             0.5311861359207333, -0.7321944890225627, -1.254176394940333, -1.8977350602406386,
             -1.9924401954792383, -2.0090608187129293, -1.654001785833986, -1.2136390416095388,
             -0.6107718943478527],
    "chroma": [0.07789742988405332, 0.08671398332728064, 0.08739208128793963, 0.09566007005743742,
               0.08757706000439897, 0.05345460163161111, 0.060163459159711295, 0.06510210677807017,
               0.07751218095243273, 0.1556835398348176, 0.07380703080696345, 0.07903645627528366],
    "tonnetz": [-0.02508206381903312, 0.08248989859785137, 0.021624099586270006,
                -0.056053491682917816, 0.08410674840402932, 0.013687410929616464],
    "harmonic_ratio": 1477.0239464770793,
    "fundamental_frequency": 441.0,
}


def _fixture() -> np.ndarray:
    rng = np.random.default_rng(6229)
    t = np.arange(44100 * 2, dtype=np.float64) / 44100
    mono = (0.3 * np.sin(2 * np.pi * 440 * t) + 0.1 * rng.uniform(-1, 1, len(t))).astype(np.float32)
    return np.stack([mono, mono * 0.8], axis=1)


def _extracted() -> dict:
    f = FeatureExtractor(sample_rate=44100).extract_features(_fixture())
    return json.loads(json.dumps({
        "rms": f.rms, "spectral_centroid": f.spectral_centroid,
        "spectral_bandwidth": f.spectral_bandwidth, "spectral_flatness": f.spectral_flatness,
        "spectral_contrast": f.spectral_contrast, "energy_low": f.energy_low,
        "energy_mid": f.energy_mid, "energy_high": f.energy_high,
        "mfcc": f.mfcc, "chroma": f.chroma, "tonnetz": f.tonnetz,
        "harmonic_ratio": f.harmonic_ratio, "fundamental_frequency": f.fundamental_frequency,
    }))


def test_feature_vector_matches_pre_change_golden() -> None:
    got = _extracted()
    assert set(got) == set(GOLDEN)
    for key, want in GOLDEN.items():
        assert np.allclose(got[key], want, rtol=1e-12), key


def test_settings_defaults_follow_canonical_constant() -> None:
    """Bare EQSettings()/SpectrumSettings() can no longer silently
    disagree with the configured pipeline's FFT size."""
    assert DEFAULT_FFT_SIZE == 4096
    assert UnifiedConfig().fft_size == DEFAULT_FFT_SIZE
    assert EQSettings().fft_size == DEFAULT_FFT_SIZE
    assert SpectrumSettings().fft_size == DEFAULT_FFT_SIZE
    assert FeatureExtractor.FFT_SIZE == 4096
    assert FeatureExtractor.N_BINS == FeatureExtractor.FFT_SIZE // 2 + 1
    assert FeatureExtractor.AC_SIZE == 2 * FeatureExtractor.FFT_SIZE
