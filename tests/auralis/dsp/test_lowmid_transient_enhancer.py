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
from scipy.signal.windows import hann
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
    sig[start:end] += amp * hann(end - start)
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


# ---------------------------------------------------------------------------
# Issue #6104: stacked overlapping peak windows
# ---------------------------------------------------------------------------

def _band_filter(audio: np.ndarray) -> np.ndarray:
    """Extract the 150-1500 Hz low-mid band the enhancer targets."""
    from scipy import signal as _signal
    b, a = _signal.butter(4, [150 / (SR / 2), 1500 / (SR / 2)], btype='band')
    return _signal.filtfilt(b, a, audio, axis=0)


def test_production_buffer_band_gain_bounded():
    """The realtime call (1024-sample buffers, intensity=0.35,
    attack_samples=2205) must not stack overlapping peak windows.

    Before #6104 every detected peak added a whole-buffer boost (the 2205
    sample window exceeds the 1024-sample chunk), measured at ~+20 dB of
    low-mid and heavy hard clipping. The combined-window expansion must
    stay within a single expansion's worth of band gain.
    """
    from scipy import signal as _signal

    rng = np.random.default_rng(6104)
    t = np.arange(1024 * 40) / SR
    # Music-like stereo: low + mid tones plus broadband noise, peak ~0.23
    left = 0.12 * np.sin(2 * np.pi * 110 * t) + 0.08 * np.sin(2 * np.pi * 440 * t)
    left += 0.04 * rng.standard_normal(len(t))
    audio = np.column_stack([left, np.roll(left, 97)])
    audio = audio / np.max(np.abs(audio)) * 0.23

    enhancer = LowMidTransientEnhancer(sample_rate=SR)
    buf_len = 1024
    worst_gain_db = -np.inf
    any_peaks = False

    for start in range(0, len(audio) - buf_len + 1, buf_len):
        chunk = audio[start:start + buf_len]
        out = enhancer.enhance_transients(
            chunk.copy(), intensity=0.35, attack_samples=int(SR * 0.05)
        )
        assert out.shape == chunk.shape
        assert np.max(np.abs(out)) < 1.0, (
            "hard-clipped output for a 0.23-peak input at production parameters"
        )
        band_in = _band_filter(chunk)
        band_out = _band_filter(out)
        energy_in = np.mean(band_in ** 2)
        energy_out = np.mean(band_out ** 2)
        if energy_in < 1e-10 or np.allclose(chunk, out):
            continue  # no transient detected in this buffer
        any_peaks = True
        gain_db = 10 * np.log10(energy_out / energy_in)
        worst_gain_db = max(worst_gain_db, gain_db)

    assert any_peaks, "no transient detected — test precondition not met"
    # One expansion at intensity=0.35 (ratio 1.7, env = rel^0.65) measures
    # ~5-6.5 dB of band gain on tone+noise content — the exact figure
    # depends on the band's crest distribution. The pre-fix stacking
    # measured ~+20 dB (median +22.1 dB, and two stacked windows already
    # clear 12 dB), so 8 dB bounds "one expansion" while still failing
    # loudly on any reintroduced per-peak accumulation.
    assert worst_gain_db < 8.0, (
        f"low-mid band gain {worst_gain_db:.1f} dB exceeds one expansion "
        "— overlapping peak windows are stacking again (#6104)"
    )


def test_overlapping_peak_windows_do_not_stack():
    """A buffer where find_peaks detects several peaks gets ONE bounded
    boost, not one per peak. Directly compares the enhanced output against
    a single-peak reference: multi-peak gain must not exceed it by the
    stacking factor."""
    rng = np.random.default_rng(6104)
    t = np.arange(2048) / SR
    base = 0.2 * np.sin(2 * np.pi * 300 * t) + 0.05 * rng.standard_normal(len(t))

    # Same low-mid content; one signal has a single HF click, the other has
    # five. If windows stacked, five clicks would add ~5x the boost.
    single = base.copy()
    single[1024:1074] += 0.5 * hann(50)
    multi = base.copy()
    for pos in (700, 900, 1100, 1300, 1500):
        multi[pos:pos + 50] += 0.5 * hann(50)

    intensity, attack = 0.35, 256  # windows overlap heavily around center
    out_single = ENHANCER.enhance_transients(single, intensity=intensity, attack_samples=attack)
    out_multi = ENHANCER.enhance_transients(multi, intensity=intensity, attack_samples=attack)

    boost_single = np.max(np.abs(out_single - single))
    boost_multi = np.max(np.abs(out_multi - multi))
    # With stacking, boost_multi approached 5 * boost_single (~+14 dB over
    # the bounded result). Allow generous headroom over the single-peak
    # reference but far below the stacked multiple.
    assert boost_multi <= 2.0 * boost_single + 1e-9, (
        f"multi-peak boost {boost_multi:.4f} vs single {boost_single:.4f} "
        "— overlapping windows are stacking (#6104)"
    )


def test_column_input_shape_preserved():
    """(n, 1) input must return (n, 1) — the old stereo-only branch
    squeezed it to (n,) (#6104)."""
    mono = _with_transient(_sine(300), SR // 4)
    column = mono.reshape(-1, 1)
    enhanced = ENHANCER.enhance_transients(column, intensity=0.5)
    assert enhanced.shape == column.shape
    assert enhanced.ndim == 2


def test_attack_window_clamped_to_buffer():
    """An attack window larger than the buffer must not change the result
    relative to a window of exactly the buffer length — both span the whole
    buffer for every peak, and neither may stack."""
    audio = _with_transient(_sine(300, amp=0.25), 1024)[:2048].copy()
    oversized = ENHANCER.enhance_transients(
        audio, intensity=0.35, attack_samples=2205
    )
    clamped = ENHANCER.enhance_transients(
        audio, intensity=0.35, attack_samples=2048
    )
    np.testing.assert_allclose(oversized, clamped, atol=1e-12)
