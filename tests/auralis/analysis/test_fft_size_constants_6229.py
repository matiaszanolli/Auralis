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

# Captured from the pre-change extractor (fixture below), 2026-10-24.
GOLDEN = {
    "rms": 0.19790193438529968,
    "spectral_centroid": 9561.338354300538,
    "spectral_bandwidth": 7009.442047814222,
    "spectral_flatness": 0.7424149513244629,
    "spectral_contrast": [3.1104531288146973, 27.180679321289062, 4.990277290344238,
                          3.25449800491333, 3.161407947540283, 3.3202109336853027],
    "energy_low": 0.0011264081113040447,
    "energy_mid": 0.9449585676193237,
    "energy_high": 0.05391504988074303,
    "mfcc": [76.62372159957886, -5.149407649909679, 2.2621086297201867, 0.32659959313357323,
             0.48554545698850315, -0.7605758294278413, -1.2929165939697507, -1.9155152661664028,
             -1.973081890066947, -2.2046515094976034, -1.8849252174686093, -1.203520799502414,
             -0.5657029952064666],
    "chroma": [0.07886670009845664, 0.08399545725835932, 0.08683916620059472, 0.09687981157144164,
               0.0825400440814434, 0.05491715242129186, 0.06100715656039607, 0.06688802773843348,
               0.07551545987263462, 0.15955858064844017, 0.07550873929378656, 0.07748370425472154],
    "tonnetz": [-0.014352931413063867, 0.08130423614662063, 0.013567141997756651,
                -0.057219646763494336, 0.09446837331810161, 0.01227745649333356],
    "harmonic_ratio": 1739.3985595703125,
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
