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
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from auralis.dsp.utils.conversion import SILENCE_STD_THRESHOLD  # noqa: F401 (re-exported guard constant)
import numpy as np
from scipy.signal import butter

from ..basic import mid_side_decode, mid_side_encode
from .filters import normalized_corner, sosfiltfilt_safe

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
    # #6230: one named digital-silence threshold for the stereo-correlation
    # guard — the identical line used to live here and in
    # core/processing/stage_snapshot.py.
    if np.std(left) < SILENCE_STD_THRESHOLD or np.std(right) < SILENCE_STD_THRESHOLD:
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
    # float(): a numpy-scalar factor would promote a float32 side signal to float64 (#6117)
    side_gain = float(width_factor) * 2.0
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
    # The lows (<300 Hz) stay mono at every rate: the old 0.01 floor moved this
    # edge to 441/480/960 Hz at 88.2/96/192 kHz (#6300).
    freq_lowmid_lo = normalized_corner(300.0, sample_rate)
    freq_lowmid_hi = normalized_corner(2000.0, sample_rate)
    freq_highmid_lo = normalized_corner(2000.0, sample_rate)
    freq_highmid_hi = normalized_corner(8000.0, sample_rate)
    freq_high = normalized_corner(8000.0, sample_rate)

    # Simple bandpass filters for extraction (order 2 is gentle enough)
    sos_lowmid = butter(2, [freq_lowmid_lo, freq_lowmid_hi], btype='band', output='sos')
    sos_highmid = butter(2, [freq_highmid_lo, freq_highmid_hi], btype='band', output='sos')
    sos_high = butter(2, freq_high, btype='high', output='sos')

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

    # PARALLEL processing: add each band's WIDTH DIFFERENCE on top of the
    # original, so nothing is split and recombined and no crossover notch
    # appears. Widening a band only rescales its side channel:
    # adjust_stereo_width() maps (mid, side) to (mid, side * 2w), so
    # widened(band) - band is the band's side times (2w - 1), added to L and
    # subtracted from R, with mid untouched. Filtering is linear and
    # per-channel, so a band's side is the band-pass of the input's side.
    # The bands are therefore extracted from the mono side signal alone. That
    # matches widening three stereo band copies to rounding error, filters
    # half as many samples, and keeps the peak at a few mono buffers where
    # the stereo version held ~11 full-length stereo arrays at once (#6717).
    #
    # sosfiltfilt_safe casts back to the input dtype (sosfiltfilt returns
    # float64, which would promote a float32 signal, #3468) and returns the
    # band as silence when the buffer is shorter than scipy's padlen instead
    # of raising mid-DSP (#4520; 16 samples at order 2). "zeros", NOT
    # passthrough: each result is one band's content, so an empty band adds
    # nothing and audio too short to filter comes back unwidened, whereas
    # passing the full signal through as all three bands would widen it
    # three times over.
    _mid, side = mid_side_encode(stereo_audio)
    added_side = np.zeros_like(side)
    for sos, band_width, context in (
        (sos_lowmid, width_lowmid, "stereo width low-mid"),
        (sos_highmid, width_highmid, "stereo width high-mid"),
        (sos_high, width_high, "stereo width high"),
    ):
        band_side = sosfiltfilt_safe(sos, side, context=context, on_too_short="zeros")
        # float(): a numpy-scalar gain would promote a float32 side to float64 (#6117)
        added_side += float(2.0 * band_width - 1.0) * band_side

    result = stereo_audio.copy()
    result[:, 0] += added_side
    result[:, 1] -= added_side
    return result
