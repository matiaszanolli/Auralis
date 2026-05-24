"""
HF-Aware Limiter (Pre/De-emphasis Wrapper)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Wraps the wideband SafetyLimiter with a pre-emphasis / de-emphasis pair so
that HF transients (cymbals, sibilance, snare overtones) survive limiting
with less compression than a naive wideband approach would inflict.

How it works:
  1. Split the signal into LOW (< split_freq) and HIGH (>= split_freq) bands
     via a linear-summing complementary pair: `high = audio - low`.
  2. PRE-emphasis: attenuate the HIGH band by `shelf_db` dB. The composite
     signal is now darker — the limiter's peak detector sees less HF energy.
  3. Run the standard SafetyLimiter (soft-clip) on the composite.
  4. DE-emphasis: re-split the (limited) composite and BOOST the HIGH band
     back by the same `shelf_db` dB. Restores the original HF level on
     anything that survived the limiter; sections where the limiter *did*
     fire on HF transients are recovered partially (full perfect recovery
     is impossible after non-linear soft-clip — that's the whole point of
     pre-emphasis: the limiter saw a *smaller* HF peak and clipped less).

When no limiting is needed (peak already below SAFETY_THRESHOLD_DB), the
wrapper short-circuits to a no-op — no filter overhead.

Why complementary subtraction split:
  low + high == audio exactly (perfect reconstruction in the absence of the
  limiter). No phase distortion artifacts from band-split filter mismatch.
  When the gain matters, only the high band's amplitude is shaped.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfilt

from .base.peak_management import SafetyLimiter
from .base.db_conversion import DBConversion


# Defaults tuned for typical mastering material:
#   6 kHz split → cymbal, hi-hat, vocal sibilance all land in HIGH
#   3 dB shelf  → noticeable HF protection without coloring untouched material
DEFAULT_SPLIT_FREQ_HZ = 6000.0
DEFAULT_SHELF_DB = 3.0


def apply_hf_aware_limiter(
    audio: np.ndarray,
    sample_rate: int,
    *,
    split_freq_hz: float = DEFAULT_SPLIT_FREQ_HZ,
    shelf_db: float = DEFAULT_SHELF_DB,
) -> tuple[np.ndarray, bool]:
    """Apply the safety limiter with HF pre/de-emphasis protection.

    Args:
        audio: Audio array (mono 1-D or stereo 2-D shape (samples, channels)).
        sample_rate: Sample rate in Hz.
        split_freq_hz: Crossover between LOW and HIGH bands.
        shelf_db: How much to duck HIGH band before the limiter (and boost
            it back after). 0 disables HF protection — wrapper becomes a
            pass-through to the wideband limiter.

    Returns:
        (processed_audio, was_limiter_applied) — preserves the existing
        SafetyLimiter return contract.
    """
    # Same dtype/shape guarantees as SafetyLimiter (#audio integrity).
    in_dtype = audio.dtype
    in_shape = audio.shape

    # Short-circuit when no limiting needed at all — pure pass-through.
    peak_db = DBConversion.to_db(float(np.max(np.abs(audio))))
    if peak_db <= SafetyLimiter.SAFETY_THRESHOLD_DB:
        return audio, False

    # shelf_db == 0 disables HF protection — fall through to wideband path.
    if shelf_db <= 0:
        return SafetyLimiter.apply_if_needed(audio)

    duck_linear = float(10 ** (-shelf_db / 20.0))
    boost_linear = float(10 ** (shelf_db / 20.0))

    sos = butter(2, split_freq_hz, btype='low', fs=sample_rate, output='sos')

    # Split → pre-emphasis (duck HF)
    low_band = _band_low(audio, sos)
    high_band = audio - low_band                       # perfect-reconstruction split
    ducked = low_band + high_band * duck_linear

    # Run the existing safety limiter (soft-clip) on the now-darker composite.
    # May or may not fire — if pre-emphasis brought composite below the
    # threshold, it's a no-op (good — that's exactly the HF protection win).
    limited, _ = SafetyLimiter.apply_if_needed(ducked)

    # Re-split the (possibly-limited) composite → de-emphasis (boost HF back).
    low_after = _band_low(limited, sos)
    high_after = limited - low_after
    restored = low_after + high_after * boost_linear

    # The de-emphasis boost can push the composite past 0 dBFS on extreme
    # material. Hard-clamp to ±1.0 (the digital ceiling) — saver.py also
    # clamps before PCM encode (commit a9e5f0b6) so this is belt-and-
    # suspenders. Crucially we do NOT re-run the wideband limiter or scale
    # the whole signal: both would compress the HF we just worked to
    # preserve. A few samples kissing 0 dBFS is acceptable; the perceptual
    # gain from HF transient preservation outweighs the inaudible clip.
    restored = np.clip(restored, -1.0, 1.0)

    # Preserve dtype/shape exactly (sosfilt can upcast float32 -> float64).
    if restored.dtype != in_dtype:
        restored = restored.astype(in_dtype, copy=False)
    assert restored.shape == in_shape, (
        f"HF-aware limiter shape changed: in={in_shape}, out={restored.shape}"
    )
    return restored, True


def _band_low(audio: np.ndarray, sos: np.ndarray) -> np.ndarray:
    """Apply the low-pass filter along the sample axis for mono or stereo."""
    return sosfilt(sos, audio, axis=0)


__all__ = [
    "DEFAULT_SPLIT_FREQ_HZ",
    "DEFAULT_SHELF_DB",
    "apply_hf_aware_limiter",
]
