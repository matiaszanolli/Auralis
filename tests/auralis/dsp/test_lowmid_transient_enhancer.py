"""
Tests for LowMidTransientEnhancer expansion envelope fix (issue #2202)

Verifies that:
- expansion_env (np.power) is used, not discarded
- fade_in / fade_out ramps are assigned and applied
- Transient windows get shaped expansion, not a uniform additive boost
- Output edges of each window transition smoothly (no abrupt step)
- Sample count is preserved
- Stereo is handled
- No clipping on normal-range input
"""

import numpy as np
import pytest

from auralis.dsp.dynamics.lowmid_transient_enhancer import LowMidTransientEnhancer


SR = 44100
ENHANCER = LowMidTransientEnhancer(sample_rate=SR)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sine(freq: float, duration: float = 0.5, amp: float = 0.3) -> np.ndarray:
    """Generate a mono sine wave."""
    t = np.linspace(0, duration, int(SR * duration), endpoint=False)
    return (np.sin(2 * np.pi * freq * t) * amp).astype(np.float64)


def _with_transient(base: np.ndarray, pos: int, width: int = 50,
                    amp: float = 0.8) -> np.ndarray:
    """Inject a band-limited transient click at position `pos`."""
    sig = base.copy()
    half = width // 2
    start = max(0, pos - half)
    end = min(len(sig), pos + half)
    sig[start:end] += amp * np.hanning(end - start)
    return np.clip(sig, -1.0, 1.0)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_sample_count_preserved():
    """Output must have the same number of samples as input."""
    audio = _with_transient(_sine(300), SR // 4)
    enhanced = ENHANCER.enhance_transients(audio, intensity=0.5)
    assert len(enhanced) == len(audio)


def test_zero_intensity_returns_unchanged():
    """intensity=0.0 must return the input array unchanged."""
    audio = _with_transient(_sine(300), SR // 4)
    enhanced = ENHANCER.enhance_transients(audio, intensity=0.0)
    np.testing.assert_array_equal(enhanced, audio)


def test_no_clipping_after_enhancement():
    """Output samples must stay in [-1, 1] after anti-clip normalisation."""
    audio = _with_transient(_sine(300, amp=0.5), SR // 4)
    enhanced = ENHANCER.enhance_transients(audio, intensity=1.0)
    assert np.max(np.abs(enhanced)) <= 1.0 + 1e-9


def test_stereo_output_shape_preserved():
    """Stereo input must produce stereo output with identical shape."""
    mono = _with_transient(_sine(300), SR // 4)
    stereo = np.column_stack([mono, mono * 0.9])
    enhanced = ENHANCER.enhance_transients(stereo, intensity=0.5)
    assert enhanced.shape == stereo.shape


def test_enhancement_is_not_uniform_additive_boost():
    """
    The crude additive boost (bug) applied the same scalar to every sample
    in the transient window: output[w] += boost * low_mid[w].

    With the expansion envelope, samples whose level is *above* the RMS
    get a larger relative gain than samples *at* the RMS, so the boost is
    not uniform.  We verify this by checking that at least two samples in a
    transient window receive noticeably different per-sample gain.
    """
    rng = np.random.default_rng(42)
    # Mix 300 Hz tone (in the low-mid band) with wideband click
    base = _sine(300, amp=0.25)
    audio = _with_transient(base, SR // 4, amp=0.6)

    original = audio.copy()
    enhanced = ENHANCER.enhance_transients(audio.copy(), intensity=0.6)

    delta = enhanced - original  # per-sample change

    # Find the peak region actually modified
    modified_mask = np.abs(delta) > 1e-9
    if not np.any(modified_mask):
        pytest.skip("No transients detected — test precondition not met")

    modified_delta = delta[modified_mask]
    # Ratio between max and min absolute per-sample change should differ
    # significantly if the envelope is level-dependent (not uniform)
    max_d = np.max(np.abs(modified_delta))
    min_d = np.min(np.abs(modified_delta))
    # With uniform boost: max_d / min_d ≈ 1 for same-sign low_mid samples.
    # With expansion envelope: ratio is typically >> 1 due to level weighting.
    assert max_d > min_d * 1.5, (
        "Per-sample changes are suspiciously uniform — expansion_env may not "
        "be applied (bug #2202: result of np.power() discarded)"
    )


def test_window_edges_are_smooth():
    """
    The blend envelope must ramp up from 0 at the very first sample and ramp
    down to 0 at the very last sample of each transient window, so there are
    no discontinuous steps.

    Strategy: compare the per-sample delta at the first modified sample vs the
    peak modified sample — the edge delta must be < peak delta.
    """
    base = _sine(300, amp=0.25)
    audio = _with_transient(base, SR // 4, amp=0.7)

    enhanced = ENHANCER.enhance_transients(audio.copy(), intensity=0.7)
    delta = np.abs(enhanced - audio)

    significant = delta > 1e-9
    if not np.any(significant):
        pytest.skip("No transients detected — test precondition not met")

    indices = np.where(significant)[0]
    first_idx = indices[0]
    peak_idx = indices[np.argmax(delta[indices])]

    edge_delta = delta[first_idx]
    peak_delta = delta[peak_idx]

    assert edge_delta < peak_delta, (
        f"Edge delta ({edge_delta:.6f}) >= peak delta ({peak_delta:.6f}). "
        "Crossfade ramps are not smoothing window edges (bug #2202)."
    )


def test_silent_audio_unchanged():
    """Silent input must return silent output (no divide-by-zero, no NaN)."""
    audio = np.zeros(SR // 2, dtype=np.float64)
    enhanced = ENHANCER.enhance_transients(audio, intensity=0.8)
    assert np.all(np.isfinite(enhanced))
    np.testing.assert_array_equal(enhanced, audio)


def test_dtype_preserved():
    """Output dtype must match input dtype."""
    audio = _with_transient(_sine(300), SR // 4).astype(np.float32)
    enhanced = ENHANCER.enhance_transients(audio, intensity=0.5)
    assert enhanced.dtype == np.float32
