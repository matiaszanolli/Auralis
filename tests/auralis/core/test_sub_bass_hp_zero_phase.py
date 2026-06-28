"""Regression: sub_bass_control rumble HP must be zero-phase (#4097).

The rumble-removal high-pass was the last causal `sosfilt` on the direct
mastered-audio path; every sibling DSP stage uses zero-phase `sosfiltfilt`.
Causal IIR group delay smears low-frequency transients (softened kick attack,
pre-echo). This pins the HP to zero-phase behaviour, preserved dtype, and
preserved sample count.

Setup note: `intensity=0.0` zeroes the low-shelf reduction so ONLY the HP runs
(`sub_bass_pct=0.5 >= SUB_HP_ACTIVATE_PCT=0.33` fires it), isolating the filter
under test.
"""

import numpy as np
import pytest
from scipy.signal import butter, sosfilt, sosfiltfilt

from auralis.core.mastering_config import SimpleMasteringConfig
from auralis.core.stages import sub_bass_control

SR = 44100


def _hp_sos(cfg: SimpleMasteringConfig):
    """Reconstruct the exact filter sub_bass_control designs."""
    nyq = SR / 2.0
    hp_norm = min(0.99, max(1e-4, cfg.SUBBASS_HP_FREQ_HZ / nyq))
    return butter(cfg.SUBBASS_HP_ORDER, hp_norm, btype='high', output='sos')


def _make_signal() -> np.ndarray:
    """Mono impulse at the centre plus 25 Hz rumble, float32."""
    n = 8192
    t = np.arange(n) / SR
    sig = 0.2 * np.sin(2 * np.pi * 25.0 * t).astype(np.float32)
    sig[n // 2] += 1.0
    return sig.astype(np.float32)


def _apply_hp(audio: np.ndarray) -> np.ndarray:
    cfg = SimpleMasteringConfig()
    # sub_bass_pct above SUB_HP_ACTIVATE_PCT, intensity 0 → HP only, no shelf.
    out, info = sub_bass_control.apply(audio, 0.5, 0.3, 0.0, SR, False, cfg)
    assert info is not None and info['hp_applied'] is True
    return out


def test_hp_is_zero_phase_matches_sosfiltfilt_not_sosfilt():
    cfg = SimpleMasteringConfig()
    sig = _make_signal()
    out = _apply_hp(sig)

    sos = _hp_sos(cfg)
    expected_zero_phase = np.asarray(sosfiltfilt(sos, sig), dtype=np.float32)
    causal = np.asarray(sosfilt(sos, sig), dtype=np.float32)

    # Output must equal the zero-phase reference…
    assert np.allclose(out, expected_zero_phase, atol=1e-5)
    # …and must NOT equal the causal reference (proves the migration).
    assert not np.allclose(out, causal, atol=1e-5)


def test_hp_impulse_response_is_symmetric_about_the_impulse():
    """Zero-phase ⇒ the impulse response is symmetric (no group-delay smear)."""
    n = 8192
    p = n // 2
    sig = np.zeros(n, dtype=np.float32)
    sig[p] = 1.0

    out = _apply_hp(sig)

    # Compare a window before/after the impulse, flipped. Causal filtering puts
    # the energy after p (asymmetric); zero-phase is symmetric about p.
    half = 64
    left = out[p - half:p][::-1]
    right = out[p + 1:p + 1 + half]
    assert np.allclose(left, right, atol=1e-6)

    # Peak stays at the impulse index (not shifted later by group delay).
    assert int(np.argmax(np.abs(out))) == p


def test_hp_preserves_dtype_float32():
    sig = _make_signal()
    out = _apply_hp(sig)
    assert out.dtype == np.float32


def test_hp_preserves_sample_count_mono_and_stereo():
    mono = _make_signal()
    assert len(_apply_hp(mono)) == len(mono)

    # Stereo [channels, samples] — apply() filters along axis=-1.
    stereo = np.vstack([mono, mono * 0.9]).astype(np.float32)
    out = _apply_hp(stereo)
    assert out.shape == stereo.shape
    assert out.dtype == np.float32
