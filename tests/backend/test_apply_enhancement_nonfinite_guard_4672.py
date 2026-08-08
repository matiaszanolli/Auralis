"""Regression tests for AudioProcessingPipeline.apply_enhancement (#4672).

np.clip does NOT sanitize NaN (np.clip(nan, -1, 1) is still nan), so an
unguarded non-finite value returned by processor.process() would reach the
PCM_16 encoder as an undefined sample and poison
LevelManager.calculate_rms -> rms_history for every subsequent chunk in the
track (NaN comparisons are always False, so smooth_transition's level-change
guard silently stops applying instead of erroring).

apply_enhancement must detect non-finite output and fall back to the
unprocessed (already-validated-finite) audio rather than propagate it.
"""

import sys
from pathlib import Path

import numpy as np

# Backend package is rooted at auralis-web/backend
_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from core.audio_processing_pipeline import AudioProcessingPipeline  # noqa: E402


class _NaNProcessor:
    """Processor that returns a NaN-poisoned array at a known index."""

    def __init__(self, index: int = 5) -> None:
        self.index = index

    def process(self, audio: np.ndarray) -> np.ndarray:
        out = audio.copy()
        out[self.index] = np.nan
        return out


class _InfProcessor:
    def process(self, audio: np.ndarray) -> np.ndarray:
        out = audio.copy()
        out[0] = np.inf
        return out


class _IdentityProcessor:
    def process(self, audio: np.ndarray) -> np.ndarray:
        return audio.copy()


def _make_audio(n: int = 1000) -> np.ndarray:
    return np.linspace(-0.5, 0.5, n, dtype=np.float32).reshape(-1, 1)


def test_nan_output_falls_back_to_unprocessed_audio() -> None:
    audio = _make_audio()
    out = AudioProcessingPipeline.apply_enhancement(
        audio, _NaNProcessor(index=5), intensity=1.0
    )
    assert np.all(np.isfinite(out)), "a NaN from the processor reached the caller"
    np.testing.assert_array_equal(out, audio)


def test_inf_output_falls_back_to_unprocessed_audio() -> None:
    audio = _make_audio()
    out = AudioProcessingPipeline.apply_enhancement(
        audio, _InfProcessor(), intensity=1.0
    )
    assert np.all(np.isfinite(out)), "an Inf from the processor reached the caller"
    np.testing.assert_array_equal(out, audio)


def test_nan_output_falls_back_even_with_intensity_blending() -> None:
    """The fallback must happen before intensity blending — blending a NaN
    array with audio * (1 - intensity) still produces NaN (nan * 0.5 == nan),
    so the guard must short-circuit ahead of that step."""
    audio = _make_audio()
    out = AudioProcessingPipeline.apply_enhancement(
        audio, _NaNProcessor(index=5), intensity=0.5
    )
    assert np.all(np.isfinite(out))


def test_finite_output_is_unaffected_by_the_guard() -> None:
    audio = _make_audio()
    out = AudioProcessingPipeline.apply_enhancement(
        audio, _IdentityProcessor(), intensity=1.0
    )
    assert len(out) == len(audio)
    np.testing.assert_array_equal(out, audio)


def test_fallback_preserves_sample_count_and_array_type() -> None:
    audio = _make_audio()
    out = AudioProcessingPipeline.apply_enhancement(
        audio, _NaNProcessor(index=0), intensity=1.0
    )
    assert isinstance(out, np.ndarray)
    assert len(out) == len(audio)


def test_nonfinite_warning_includes_chunk_index(caplog) -> None:
    import logging

    audio = _make_audio()
    with caplog.at_level(logging.WARNING, logger="core.audio_processing_pipeline"):
        AudioProcessingPipeline.apply_enhancement(
            audio, _NaNProcessor(index=5), intensity=1.0, chunk_index=7
        )
    assert any("chunk_index=7" in r.message for r in caplog.records)
