"""Fingerprint failures are failures; glitch samples are repaired (#6107, #6144).

#6107: ``AudioFingerprintAnalyzer`` swallowed every engine error (missing Rust
module, Rust or resample error, partial dict) into ``{}``, which
``ContinuousMode`` reads as "nothing to do": a missing wheel turned every
adaptive master into the untouched input, reported as success. Engine errors
raise ``FingerprintUnavailable`` now; only the documented skips (empty,
invalid-rate, too-short audio) still return ``{}``.

#6144: one NaN sample went through the Rust FFTs and came back as a plausible
fingerprint (uniform 1/7 band shares, bass_mid_ratio +60 dB). Non-finite
samples are zeroed before the engine runs, so the track gets its real
fingerprint; a NaN ratio from the engine is no longer clamped to +60 dB.
"""

import math

import numpy as np
import pytest

import auralis.analysis.fingerprint.audio_fingerprint_analyzer as afa
from auralis.analysis.fingerprint.audio_fingerprint_analyzer import (
    AudioFingerprintAnalyzer,
    FingerprintUnavailable,
)
from auralis.analysis.fingerprint.rust_fingerprint import rust_fingerprint_to_schema

SR = 44100


def _noise(seconds: float = 3.0) -> np.ndarray:
    rng = np.random.default_rng(6144)
    # Coloured so the band shares are far from uniform (1/7 each was the NaN residue).
    white = rng.standard_normal((int(seconds * SR), 2))
    return (np.cumsum(white, axis=0) * 0.002 + white * 0.02).astype(np.float32)


@pytest.fixture(scope="module")
def clean_fingerprint() -> dict[str, float]:
    return AudioFingerprintAnalyzer().analyze(_noise(), SR)


# --- #6107: engine failures raise, documented skips do not -------------------

def test_missing_engine_raises_instead_of_returning_empty(monkeypatch):
    def missing(*_args):
        raise ModuleNotFoundError("No module named 'auralis_dsp'")

    monkeypatch.setattr(afa, "compute_fingerprint_schema", missing)
    with pytest.raises(FingerprintUnavailable, match="auralis_dsp"):
        AudioFingerprintAnalyzer().analyze(_noise(), SR)


def test_a_partial_engine_result_raises(monkeypatch):
    monkeypatch.setattr(afa, "compute_fingerprint_schema", lambda *_a: rust_fingerprint_to_schema({}))
    with pytest.raises(FingerprintUnavailable):
        AudioFingerprintAnalyzer().analyze(_noise(), SR)


@pytest.mark.parametrize(
    ("audio", "sr"),
    [(np.zeros((0, 2), np.float32), SR), (np.zeros((SR, 2), np.float32), 0), (np.zeros((1000, 2), np.float32), SR)],
    ids=["empty", "invalid-rate", "too-short"],
)
def test_documented_skips_still_return_empty(audio, sr):
    assert AudioFingerprintAnalyzer().analyze(audio, sr) == {}


def test_a_missing_engine_fails_the_master_instead_of_bypassing_it(monkeypatch):
    from auralis.core.config import UnifiedConfig
    from auralis.core.hybrid_processor import HybridProcessor

    def missing(*_args):
        raise ModuleNotFoundError("No module named 'auralis_dsp'")

    monkeypatch.setattr(afa, "compute_fingerprint_schema", missing)
    processor = HybridProcessor(UnifiedConfig(internal_sample_rate=SR))
    try:
        with pytest.raises(FingerprintUnavailable):
            processor.process(_noise(2.0))
    finally:
        processor.close()


def test_a_too_short_buffer_is_still_passed_through():
    from auralis.core.config import UnifiedConfig
    from auralis.core.hybrid_processor import HybridProcessor

    audio = _noise(0.2)  # 8820 samples: above MIN_SAMPLES, below the analyzer's sr // 2
    processor = HybridProcessor(UnifiedConfig(internal_sample_rate=SR))
    try:
        out = processor.process(audio)
    finally:
        processor.close()
    assert out.shape == audio.shape


def test_the_job_layer_names_the_failure():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parents[4] / "auralis-web" / "backend"))
    from core.job_error_mapping import _safe_error_message

    message = _safe_error_message(FingerprintUnavailable("No module named 'auralis_dsp'"))
    assert "not mastered" in message


# --- #6144: a glitch sample is repaired, not propagated ------------------------

def test_one_nan_sample_still_yields_the_real_fingerprint(clean_fingerprint):
    audio = _noise()
    audio[SR, 0] = np.nan
    audio[SR + 7, 1] = np.inf
    fingerprint = AudioFingerprintAnalyzer().analyze(audio, SR)

    assert all(math.isfinite(v) for v in fingerprint.values())
    bands = [fingerprint[k] for k in ("sub_bass_pct", "bass_pct", "low_mid_pct", "mid_pct",
                                      "upper_mid_pct", "presence_pct", "air_pct")]
    assert max(bands) - min(bands) > 0.05, "uniform 1/7 band shares are the NaN residue"
    for key in ("lufs", "crest_db", "bass_mid_ratio", "spectral_flatness", "bass_pct"):
        assert fingerprint[key] == pytest.approx(clean_fingerprint[key], rel=0.02, abs=0.02), key


def test_a_nan_bass_mid_ratio_is_not_clamped_to_plus_60_db():
    raw_keys = {
        "sub_bass": 0.1, "bass": 0.2, "low_mid": 0.2, "mid": 0.2, "upper_mid": 0.1,
        "presence": 0.1, "air": 0.1, "lufs": -14.0, "crest_db": 12.0, "tempo_bpm": 120.0,
        "rhythm_stability": 0.5, "transient_density": 0.5, "silence_ratio": 0.0,
        "spectral_flatness": 0.5, "harmonic_ratio": 0.5, "pitch_stability": 0.5,
        "chroma_energy": 0.5, "peak_consistency": 0.5, "stereo_width": 0.5,
        "phase_correlation": 0.5, "spectral_centroid": 2000.0, "spectral_rolloff": 5000.0,
        "dynamic_range_variation": 2.0, "loudness_variation": 2.0, "bass_mid_ratio": float("nan"),
    }
    assert math.isnan(rust_fingerprint_to_schema(raw_keys)["bass_mid_ratio"])
