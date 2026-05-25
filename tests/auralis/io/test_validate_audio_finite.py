"""
Regression test for #3472 — `validate_audio` at the I/O boundary must
sanitize NaN/Inf samples before they reach the chunked playback path.

Pre-fix: `auralis/io/processing.py::validate_audio` checked shape, length,
silence, and clipping but never `np.isfinite`. A corrupt source file
producing NaN/Inf samples passed through; downstream limiters propagated
NaN across whole chunks and the player emitted clicks / silence / wrap.

Post-fix: `validate_audio` calls `sanitize_audio` (existing utility from
auralis/utils/audio_validation.py) which replaces NaN/Inf with silence
and emits a warning. Policy choice = sanitize (not fail-fast) because the
loader feeds streamed playback — fail-fast would crash mid-queue on one
corrupt file. HybridProcessor still fails fast on its own input path.
"""

from __future__ import annotations

import numpy as np
import pytest

from auralis.io.processing import validate_audio


def _sine(samples: int = 4096, sr: int = 44100) -> np.ndarray:
    """Generate a finite stereo sine for baseline tests."""
    t = np.arange(samples) / sr
    mono = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    return np.column_stack([mono, mono])


# ---------------------------------------------------------------------------
# Sanitization contract
# ---------------------------------------------------------------------------

def test_nan_samples_are_replaced_with_silence():
    audio = _sine()
    audio[100, 0] = np.nan
    audio[200, 1] = np.nan

    out, _ = validate_audio(audio.copy(), sample_rate=44100, file_type="wav")

    assert np.all(np.isfinite(out)), "Output must contain no NaN/Inf"
    assert out[100, 0] == 0.0, "NaN sample should be replaced with silence"
    assert out[200, 1] == 0.0


def test_inf_samples_are_replaced_with_silence():
    audio = _sine()
    audio[50, 0] = np.inf
    audio[60, 1] = -np.inf

    out, _ = validate_audio(audio.copy(), sample_rate=44100, file_type="flac")

    assert np.all(np.isfinite(out))
    assert out[50, 0] == 0.0
    assert out[60, 1] == 0.0


def test_mixed_nan_and_inf_handled():
    audio = _sine(samples=8192)
    # Spread NaN/Inf samples across both channels
    audio[100:110, 0] = np.nan
    audio[200:205, 1] = np.inf
    audio[300, :] = -np.inf

    out, _ = validate_audio(audio.copy(), sample_rate=44100, file_type="mp3")

    assert np.all(np.isfinite(out))
    # All previously-non-finite locations must be silence
    assert np.all(out[100:110, 0] == 0.0)
    assert np.all(out[200:205, 1] == 0.0)
    assert np.all(out[300, :] == 0.0)


# ---------------------------------------------------------------------------
# Clean-input passthrough — fix must not alter normal audio
# ---------------------------------------------------------------------------

def test_finite_audio_unchanged():
    audio = _sine()
    original = audio.copy()

    out, _ = validate_audio(audio, sample_rate=44100, file_type="wav")

    # Finite audio must pass through value-equal (dtype may change but values
    # stay the same — validate_audio casts non-float to float32).
    np.testing.assert_array_equal(out, original)


def test_finite_audio_preserves_shape_and_sample_count():
    audio = _sine(samples=12345)
    out, sr = validate_audio(audio.copy(), sample_rate=44100, file_type="wav")
    assert out.shape == audio.shape, "Sample count / channels must be preserved"
    assert sr == 44100


# ---------------------------------------------------------------------------
# Misfire guard — NaN-bearing audio must not break the peak/clipping check
# ---------------------------------------------------------------------------

def test_amplitude_checks_run_after_sanitization():
    """Pre-fix bug: np.max(np.abs(nan_audio)) returns NaN, so the silence
    and clipping branches would silently misfire. Post-fix: sanitize first,
    then the peak measurement returns a real number."""
    audio = _sine()
    audio[5] = np.nan      # would poison np.max(np.abs(...)) if unsanitized

    out, _ = validate_audio(audio.copy(), sample_rate=44100, file_type="wav")
    peak = float(np.max(np.abs(out)))
    assert np.isfinite(peak), "Peak measurement on sanitized output must be finite"
    assert peak > 0.0, "Peak should be the actual signal peak, not NaN"


# ---------------------------------------------------------------------------
# Existing validations still fire (regression guard)
# ---------------------------------------------------------------------------

def test_empty_audio_still_raises():
    """The sanitize step must not silently accept empty arrays."""
    from auralis.utils.logging import ModuleError
    with pytest.raises(ModuleError):
        validate_audio(np.array([], dtype=np.float32), sample_rate=44100, file_type="wav")
