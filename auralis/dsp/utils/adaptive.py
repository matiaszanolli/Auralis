"""
Adaptive Processing Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Utilities for adaptive and intelligent audio processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np

from ...analysis.loudness_meter import LoudnessMeter
from ..basic import rms  # noqa: F401  — re-exported; tests/validation imports it from here
from .audio_info import mono_to_stereo


def adaptive_gain_calculation(target_rms: float,
                             reference_rms: float,
                             adaptation_factor: float = 0.8) -> float:
    """
    Calculate adaptive gain with smoother transitions

    Computes the gain needed to match target RMS to reference RMS,
    with optional smoothing for gradual adaptation.

    Args:
        target_rms: RMS of target signal
        reference_rms: RMS of reference or target level
        adaptation_factor: How aggressively to adapt (0-1)
                          1.0 = full adaptation, 0.0 = no adaptation

    Returns:
        Gain factor (linear)
    """
    if target_rms > 0:
        raw_gain = reference_rms / target_rms

        # Special case: if adaptation_factor is 1.0, return raw gain
        if adaptation_factor >= 0.99:
            return float(np.clip(raw_gain, 0.1, 10.0))

        # Apply adaptation factor for smoother transitions
        # adaptation_factor of 0.8 means 80% of the way to the target
        gain = 1.0 + (raw_gain - 1.0) * adaptation_factor

        # Limit gain to reasonable range
        return float(np.clip(gain, 0.1, 10.0))
    return 1.0


def smooth_parameter_transition(current_value: float,
                               target_value: float,
                               smoothing_factor: float = 0.1) -> float:
    """
    Smooth parameter transitions to avoid artifacts

    Implements a simple low-pass filter for parameter changes,
    preventing abrupt changes that could cause clicks or pops.

    Args:
        current_value: Current parameter value
        target_value: Target parameter value
        smoothing_factor: Speed of transition (0-1)
                         0.0 = no change, 1.0 = instant change

    Returns:
        Smoothed parameter value
    """
    return current_value + (target_value - current_value) * smoothing_factor


def calculate_loudness_units(audio: np.ndarray, sample_rate: int) -> float:
    """
    Measure programme loudness in LUFS, K-weighted per ITU-R BS.1770-4.

    #5221: this used to return ``to_db(rms(audio)) - 23.0``. Both halves of
    that were wrong. There is no K-weighting in plain RMS, and -23.0 is the
    EBU R128 *target* level (``EBU_R128_TARGET_LUFS`` in
    ``analysis/quality_assessors/utilities/assessment_constants.py``), not a
    dBFS->LUFS scale offset — BS.1770-4's absolute-scale constant is -0.691,
    as ``loudness_meter.calculate_block_loudness`` and the fingerprint's own
    proxy (``fingerprint/windowed_compute.py``) both already use. The result
    read ~25 LU below true loudness, on a scale no other part of the pipeline
    speaks.

    That mattered because every consumer of this value is calibrated in real
    LUFS: ``continuous_dsp_ops`` normalizes toward ``params.target_lufs``
    (derived from the fingerprint's -0.691-scale ``lufs`` and from
    ``PresetProfile.target_lufs``, e.g. -14.0), ``AdaptiveLoudnessControl``
    compares against ``TARGET_LUFS = -11.0`` / ``VERY_LOUD_THRESHOLD = -12.0``,
    and ``adaptive_mode``'s ``loudness_coordinate`` tanh is centred on
    -14.3887. Reading 25 LU low turned the first into a systematic ~+25 dB
    over-boost that the peak limiter then clawed back to the -0.3 dBFS
    ceiling (making "LUFS normalization" behave as peak normalization), and
    starved the other two: the tanh sat at ~0.0005 instead of ~0.45, and the
    "already loud" branch was unreachable. So this is a calibration repair,
    not a rescaling — the downstream constants were always written for true
    LUFS and need no re-tuning.

    Gating is deliberately not applied. BS.1770-4 gating is defined over a
    sequence of 400 ms blocks and is undefined for the sub-400 ms buffers this
    function is called with; on full chunks it moves the result by <0.05 LU
    while costing ~4.6x more. The K-weighted mean-square over the supplied
    buffer is exactly ``LoudnessMeter.calculate_block_loudness``, so a caller
    that needs gated integrated loudness should use ``LoudnessMeter`` directly
    (as ``core/mastering_prepare.py`` does).

    Args:
        audio: Input audio signal
        sample_rate: Sample rate in Hz. Required (#4622) — every DSP entry
            point in this module takes it explicitly rather than assuming
            44.1kHz. Now genuinely load-bearing: it sets the K-weighting
            filter design.

    Returns:
        Loudness in LUFS, floored at -70.0 for silence.
    """
    if audio.size == 0:
        return -70.0

    if audio.ndim == 1:
        audio = mono_to_stereo(audio)

    # A fresh meter per call. `apply_k_weighting()` carries filter state
    # (pre_filter_zi/rlb_filter_zi) across calls, so a shared instance would
    # let one buffer's filter tail colour the next measurement — and the
    # pipeline measures unrelated buffers from several threads. Construction
    # is ~0.07 ms against ~45 ms of filtering for a 15 s chunk, so it is not
    # worth caching behind a lock.
    meter = LoudnessMeter(sample_rate=sample_rate)
    lufs = meter.calculate_block_loudness(meter.apply_k_weighting(audio))

    # Silence gives -inf; callers subtract from this value and feed it to tanh
    # curves, so hand back the same finite floor the old implementation used.
    if not np.isfinite(lufs):
        return -70.0
    return float(lufs)
