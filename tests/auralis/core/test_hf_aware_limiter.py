"""
Tests for the HF-aware limiter (pre/de-emphasis wrapper).

Pins these properties:
  * Pass-through when no limiting needed (no filter overhead)
  * Audio invariants: same length, same dtype, same channel count
  * Output peak respects SafetyLimiter ceiling (no clipping past limit)
  * HF transients are LESS compressed than the wideband SafetyLimiter would
    inflict — the user's actual complaint
  * shelf_db=0 reduces to a wideband-only path (sanity check)
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.signal import butter, sosfilt

from auralis.core.processing.base.peak_management import SafetyLimiter
from auralis.core.processing.hf_aware_limiter import (
    DEFAULT_SHELF_DB,
    DEFAULT_SPLIT_FREQ_HZ,
    apply_hf_aware_limiter,
)


SR = 44100


@pytest.fixture
def safe_audio():
    """3 seconds of stereo noise well below the safety threshold (~-15 dBFS peak)."""
    rng = np.random.default_rng(42)
    audio = rng.standard_normal((SR * 3, 2)).astype(np.float32) * 0.15
    return audio


def _make_lf_dominated_hot_audio() -> np.ndarray:
    """Body well under the limiter threshold, but transient HF bursts push
    composite past it. This is the scenario where HF-aware shines: ducking
    the HF before the limiter brings the composite back under threshold so
    the limiter NEVER FIRES, then de-emphasis restores HF transients intact.
    A wideband limiter sees the full HF peak and compresses everything.
    """
    t = np.arange(SR * 2) / SR
    body = 0.55 * np.sin(2 * np.pi * 200 * t).astype(np.float64)    # safe alone
    # Eight 50-ms HF bursts at 8 kHz, amplitude 0.55, spaced through the clip
    cymbal = np.zeros_like(t, dtype=np.float64)
    burst_centers = np.linspace(0.2, 1.8, 8)
    for center in burst_centers:
        mask = (t > center) & (t < center + 0.05)
        cymbal[mask] = 0.55 * np.sin(2 * np.pi * 8000 * t[mask])
    mono = body + cymbal  # peaks of body+burst ≈ 1.1, well past -0.1 dBFS
    return np.column_stack([mono, mono]).astype(np.float32)


# ---------------------------------------------------------------------------
# Pass-through and invariants
# ---------------------------------------------------------------------------

def test_passes_through_when_audio_already_safe(safe_audio):
    """Audio comfortably below threshold → wrapper returns it untouched."""
    out, applied = apply_hf_aware_limiter(safe_audio, SR)
    assert applied is False
    assert np.array_equal(out, safe_audio)


def test_preserves_length_dtype_channels():
    audio = _make_lf_dominated_hot_audio()
    out, applied = apply_hf_aware_limiter(audio, SR)
    assert applied is True
    assert out.shape == audio.shape, "sample count must be preserved"
    assert out.dtype == audio.dtype, "dtype must be preserved"


def test_output_respects_safety_ceiling():
    """Output peak must not exceed digital ceiling (1.0). The second-pass
    SafetyLimiter at the end of apply_hf_aware_limiter exists for this so
    that the de-emphasis boost can't push samples past 0 dBFS."""
    audio = _make_lf_dominated_hot_audio()
    out, _ = apply_hf_aware_limiter(audio, SR)
    peak = float(np.max(np.abs(out)))
    # SafetyLimiter's soft-clip targets ~-0.1 dBFS (0.989 linear). Allow
    # a small epsilon for measurement noise.
    assert peak <= 1.0, f"Output peak {20*np.log10(peak):+.3f} dBFS clipped past 0 dBFS"


# ---------------------------------------------------------------------------
# The actual point: HF transient preservation
# ---------------------------------------------------------------------------

def _hf_energy_db(audio: np.ndarray, sr: int, cutoff: float = 5000.0) -> float:
    """RMS in the HF band (>= cutoff), in dB."""
    sos = butter(4, cutoff, btype='high', fs=sr, output='sos')
    hp = sosfilt(sos, audio.mean(axis=1) if audio.ndim == 2 else audio)
    rms = float(np.sqrt(np.mean(hp ** 2)))
    return 20 * np.log10(rms + 1e-12)


def test_hf_aware_limiter_preserves_more_hf_than_wideband():
    """The user's complaint, pinned: wideband SafetyLimiter compresses HF
    transients more than HF-aware does. After both run on the same source,
    the HF-aware output must retain MORE high-frequency energy.

    This is the smoking-gun test for Phase 5.
    """
    audio = _make_lf_dominated_hot_audio()

    wide_out, _ = SafetyLimiter.apply_if_needed(audio.copy())
    hf_aware_out, _ = apply_hf_aware_limiter(audio.copy(), SR)

    hf_wide = _hf_energy_db(wide_out, SR)
    hf_aware = _hf_energy_db(hf_aware_out, SR)

    assert hf_aware > hf_wide, (
        f"HF-aware path should preserve more HF energy than wideband. "
        f"Wideband HF={hf_wide:.2f} dB, HF-aware HF={hf_aware:.2f} dB"
    )


def test_shelf_zero_reduces_to_wideband():
    """shelf_db=0 means no HF protection — should match SafetyLimiter exactly."""
    audio = _make_lf_dominated_hot_audio()
    wide_out, wide_applied = SafetyLimiter.apply_if_needed(audio.copy())
    bypass_out, bypass_applied = apply_hf_aware_limiter(audio.copy(), SR, shelf_db=0)
    assert wide_applied == bypass_applied
    np.testing.assert_array_equal(wide_out, bypass_out)


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------

def test_mono_input_supported():
    """Wrapper must handle 1-D mono arrays too, not just stereo."""
    audio = _make_lf_dominated_hot_audio()[:, 0]   # take left channel
    out, applied = apply_hf_aware_limiter(audio, SR)
    assert out.shape == audio.shape
    assert applied is True


def test_no_nan_in_output():
    """Even with aggressive material, output is finite everywhere."""
    audio = _make_lf_dominated_hot_audio() * 2.0   # extra hot
    out, _ = apply_hf_aware_limiter(audio, SR)
    assert np.all(np.isfinite(out))


def test_default_constants_sensible():
    """6 kHz split / 3 dB shelf are the documented defaults."""
    assert DEFAULT_SPLIT_FREQ_HZ == 6000.0
    assert DEFAULT_SHELF_DB == 3.0
