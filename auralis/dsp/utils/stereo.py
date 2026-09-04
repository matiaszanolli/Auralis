"""
Stereo Processing Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Utilities for stereo width analysis and manipulation

THREE DIFFERENT "WIDTH" SCALES EXIST IN THIS CODEBASE (#4503). They are not
interchangeable, and mixing them silently produces a plausible-looking number
that means the wrong thing:

1. **Decorrelation width** — :func:`stereo_width_analysis` here.
   ``1 - |corr(L, R)|``. 0.0 = mono, 1.0 = fully decorrelated. A *measurement*
   of the signal; there is no "unity" value.
2. **Width factor / side gain** — the ``width_factor`` argument to
   :func:`adjust_stereo_width` and :func:`adjust_stereo_width_multiband`.
   ``side_gain = 2 * width_factor``, so :data:`WIDTH_FACTOR_UNITY` (0.5) means
   "leave unchanged". An *instruction*, not a measurement.
3. **Side-energy ratio** — the ``stereo_width`` fingerprint dimension
   (``vendor/auralis-dsp/src/stereo_analysis.rs::compute_stereo_width``).
   ``side_energy / (mid_energy + side_energy)``. 0.0 = mono.

Scale 1 and scale 2 both live in the 0..1 interval and both have 0.5 near the
middle, which is exactly why comparing them looks reasonable and is wrong. To
ask "does this instruction widen the signal?", compare the width factor against
:data:`WIDTH_FACTOR_UNITY` — never against a measurement on scale 1 or 3.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from scipy.signal import butter

from ..basic import mid_side_decode, mid_side_encode
from .filters import sosfiltfilt_safe

#: Width factor that leaves the signal unchanged (side gain of exactly 1.0).
#: Audio that has not been width-adjusted sits here *by definition*, which is
#: what makes it the correct reference point for "would this widen or narrow?"
#: — no measurement of the input is needed or valid for that question (#4503).
WIDTH_FACTOR_UNITY: float = 0.5


def stereo_width_analysis(stereo_audio: np.ndarray) -> float:
    """
    Analyze stereo width of audio signal

    Calculates the stereo width based on the correlation between
    left and right channels.

    Args:
        stereo_audio: Stereo audio signal [samples, 2]

    Returns:
        Stereo width factor (0-1)
        - 0.0 = mono (identical channels)
        - 0.5 = normal stereo
        - 1.0 = maximum width (completely uncorrelated)
    """
    if stereo_audio.ndim != 2 or stereo_audio.shape[1] != 2:
        return 0.5  # Default for non-stereo

    left = stereo_audio[:, 0]
    right = stereo_audio[:, 1]

    # Guard: constant/silent channels have zero variance — np.corrcoef returns NaN.
    # Treat them as perfectly correlated (mono) → width = 0.0 (fixes #2611).
    if np.std(left) < 1e-9 or np.std(right) < 1e-9:
        return 0.0

    # Calculate correlation
    correlation = np.corrcoef(left, right)[0, 1]

    # Convert correlation to width (inverse relationship)
    # correlation = 1.0 -> width = 0.0 (mono)
    # correlation = 0.0 -> width = 1.0 (maximum stereo)
    width = 1.0 - np.abs(correlation)

    return float(np.clip(width, 0.0, 1.0))


def adjust_stereo_width(stereo_audio: np.ndarray, width_factor: float) -> np.ndarray:
    """
    Adjust stereo width of audio signal

    Uses mid-side processing to adjust the stereo image width.

    Args:
        stereo_audio: Stereo audio signal [samples, 2]
        width_factor: Width adjustment factor
                     - 0.0 = mono
                     - 0.5 = normal stereo (no change)
                     - 1.0 = maximum width (doubled side signal)

    Returns:
        Width-adjusted stereo audio
    """
    if stereo_audio.ndim != 2 or stereo_audio.shape[1] != 2:
        return stereo_audio.copy()

    # Convert to mid-side
    mid, side = mid_side_encode(stereo_audio)

    # Adjust side component based on width factor
    # width_factor of 0.5 = no change, 0 = mono, 1 = maximum width
    side_gain = width_factor * 2.0
    adjusted_side = side * side_gain

    # Convert back to stereo
    return mid_side_decode(mid, adjusted_side)


def adjust_stereo_width_multiband(
    stereo_audio: np.ndarray,
    width_factor: float,
    sample_rate: int,
) -> np.ndarray:
    """
    Adjust stereo width with frequency-dependent processing.

    sample_rate is required (#4622) — the per-band filters below derive
    their edges from it, so a missing/wrong value silently mis-places
    every frequency band this function widens.

    Uses PARALLEL processing to avoid crossover phase/magnitude issues.
    Instead of splitting bands and recombining (which causes notches with
    filtfilt), we extract each band, widen it, and ADD the difference
    on top of the original signal. This preserves flat frequency response.

    Frequency bands:
    - Lows (<300Hz): No expansion - keeps bass/kick centered and punchy
    - Low-mids (300-2kHz): Gentle expansion - body and warmth
    - High-mids (2k-8kHz): Moderate expansion - presence, guitars
    - Highs (>8kHz): Full expansion - air, cymbals

    On the low band: "no expansion below 300 Hz" is the *intent*, not a brick
    wall. The order-2 extraction bandpass has a gentle skirt, so measured side
    gain at max widening tapers off gradually — ~1.19x at 250-300 Hz, ~1.09x at
    200-250 Hz, ~1.04x at 160-200 Hz, and effectively 1.00x below ~120 Hz.
    Kick and bass fundamentals are genuinely protected; the upper bass is
    partially widened. Measured, not assumed (#4504).

    Args:
        stereo_audio: Stereo audio signal [samples, 2]
        width_factor: Base width factor (0.5 = no change, 1.0 = max width)
        sample_rate: Audio sample rate

    Returns:
        Width-adjusted stereo audio with frequency-appropriate widening
    """
    if stereo_audio.ndim != 2 or stereo_audio.shape[1] != 2:
        return stereo_audio.copy()

    # No change needed
    if abs(width_factor - 0.5) < 0.01:
        return stereo_audio.copy()

    nyquist = sample_rate / 2

    # Band extraction frequencies (using simple Butterworth, not LR4)
    # We only need to extract bands, not split perfectly.
    #
    # The SHARED 2 kHz edge between low-mid and high-mid is correct and
    # load-bearing — do not "fix" it into non-overlapping edges (#4505).
    # An order-2 Butterworth run through `sosfiltfilt` (zero-phase, so the
    # magnitude response is squared) sits at exactly 0.5 amplitude at its
    # cutoff, so at 2 kHz the two bandpasses sum to ~1.0: the region is
    # amplitude-complementary and each frequency is widened exactly ONCE.
    # Splitting the edge apart would open a genuine hole at the seam.
    # Verified by measurement, not inspection — see
    # tests/auralis/dsp/test_stereo_width_scales_4503.py, which pins the width
    # response as monotonic across 1.5-2.5 kHz.
    freq_lowmid_lo = min(0.99, max(0.01, 300.0 / nyquist))
    freq_lowmid_hi = min(0.99, max(0.01, 2000.0 / nyquist))
    freq_highmid_lo = min(0.99, max(0.01, 2000.0 / nyquist))
    freq_highmid_hi = min(0.99, max(0.01, 8000.0 / nyquist))
    freq_high = min(0.99, max(0.01, 8000.0 / nyquist))

    # Simple bandpass filters for extraction (order 2 is gentle enough)
    sos_lowmid = butter(2, [freq_lowmid_lo, freq_lowmid_hi], btype='band', output='sos')
    sos_highmid = butter(2, [freq_highmid_lo, freq_highmid_hi], btype='band', output='sos')
    sos_high = butter(2, freq_high, btype='high', output='sos')

    # Extract bands (for width calculation only, not recombination).
    #
    # sosfiltfilt_safe both casts back to the input dtype — sosfiltfilt returns
    # float64, and an unguarded call would silently promote a float32 signal
    # through the final `stereo_audio + diff_*` add (#3468) — and returns the
    # band unfiltered when the buffer is shorter than scipy's padlen instead of
    # raising mid-DSP (#4520). At order 2 that threshold is 16 samples, so a
    # buffer of 15 or fewer used to crash here for ANY width factor far enough
    # from unity to reach this line.
    # on_too_short="zeros", NOT passthrough: each result is one band's content,
    # and the `diff_* = widened(band) - band` sums below add every band's
    # contribution on top of the input. Empty bands give diff == 0, so audio too
    # short to filter comes back unwidened; passing the full signal through as
    # all three "bands" would instead widen it three times over.
    band_lowmid = sosfiltfilt_safe(
        sos_lowmid, stereo_audio, context="stereo width low-mid", on_too_short="zeros"
    )
    band_highmid = sosfiltfilt_safe(
        sos_highmid, stereo_audio, context="stereo width high-mid", on_too_short="zeros"
    )
    band_high = sosfiltfilt_safe(
        sos_high, stereo_audio, context="stereo width high", on_too_short="zeros"
    )

    # Calculate expansion amount from base factor
    expansion = width_factor - 0.5  # 0 to 0.5 range

    # Frequency-dependent expansion factors
    # Lower frequencies get less expansion to avoid phase issues on cheap headphones
    f_min = 300.0
    f_max = 16000.0
    log_range = np.log(f_max / f_min)

    def expansion_factor(f_center: float) -> float:
        """Smooth logarithmic curve: higher freq = more expansion"""
        log_pos = np.log(f_center / f_min) / log_range  # 0.0 to 1.0
        # float(): np.log returns a numpy scalar, which mypy widens to Any and
        # would leak out of this `-> float` signature.
        return float(0.3 + (log_pos * 0.7))  # Ramp from 0.3 to 1.0 with frequency

    # Width factors for each band
    width_lowmid = 0.5 + expansion * expansion_factor(775.0)    # ~0.6
    width_highmid = 0.5 + expansion * expansion_factor(4000.0)  # ~0.75
    width_high = 0.5 + expansion * expansion_factor(11314.0)    # ~0.95

    # Calculate widened versions of each band
    band_lowmid_w = adjust_stereo_width(band_lowmid, width_lowmid)
    band_highmid_w = adjust_stereo_width(band_highmid, width_highmid)
    band_high_w = adjust_stereo_width(band_high, width_high)

    # PARALLEL processing: add the WIDTH DIFFERENCE on top of original
    # This avoids crossover notches because we never split and recombine
    # diff = widened - original_band
    # result = original + diff = original + (widened - band) = original with added width
    diff_lowmid = band_lowmid_w - band_lowmid
    diff_highmid = band_highmid_w - band_highmid
    diff_high = band_high_w - band_high

    # Cast the final sum back to the input dtype. Even with the band-level
    # cast above, the per-band width factors are `np.float64` scalars (because
    # `expansion_factor` calls `np.log`), so `adjust_stereo_width` ends up
    # multiplying the side signal by a float64 scalar and promotes its
    # output. Cast once at the end to preserve the project's float32
    # invariant for downstream mastering stages (#3468).
    result = stereo_audio + diff_lowmid + diff_highmid + diff_high
    return np.asarray(result, dtype=stereo_audio.dtype)
