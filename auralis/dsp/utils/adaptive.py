"""
Adaptive Processing Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Utilities for adaptive and intelligent audio processing

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np

from ...analysis.loudness_meter import LoudnessMeter
from ...io.processing import downmix_to_stereo, requires_layout_aware_downmix
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


# calculate_loudness_units() reports silence as this finite floor, never -inf.
LOUDNESS_FLOOR_LUFS = -70.0

# Normalisation guard rails (#5551). Because the meter floors silence at a
# finite value, "is it silent?" can no longer be answered with isfinite(); a
# buffer at or below SILENCE_FLOOR_LUFS (dither, room tone, a decoded-MP3 gap)
# is left alone rather than raised to programme loudness, and no buffer is
# ever moved by more than MAX_NORMALIZATION_GAIN_DB. Shared so the live chunk
# path and any other loudness-targeting stage use one definition.
SILENCE_FLOOR_LUFS = -50.0

#: Width of the ramp above the floor over which a normalisation gain fades in (#6108).
SILENCE_KNEE_DB = 5.0
MAX_NORMALIZATION_GAIN_DB = 24.0
# Largest K-weighted-vs-proxy gap accepted as a real scale offset. Stereo
# material sits ~+3 to +4 dB above the fingerprint proxy (summed channels plus
# the K-weighting shelf); beyond this the chunk is degenerate, not mis-scaled.
MAX_PROXY_TO_K_OFFSET_DB = 10.0


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
        return LOUDNESS_FLOOR_LUFS

    # Measure on a stereo view: the meter's per-channel sum is only correct for
    # mono/stereo. A single-column (N, 1) array is mono exactly like 1-D (#5550);
    # canonical 5.1/7.1 uses the shared BS.775 downmix; other layouts keep the
    # plain per-channel sum, since channel roles cannot be inferred from count.
    if audio.ndim == 1:
        audio = mono_to_stereo(audio)
    elif audio.shape[1] == 1:
        audio = mono_to_stereo(audio[:, 0])
    elif audio.shape[1] > 2 and not requires_layout_aware_downmix(audio.shape[1]):
        audio = downmix_to_stereo(audio)

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
        return LOUDNESS_FLOOR_LUFS
    return float(lufs)


def proxy_to_k_offset_db(audio: np.ndarray, fingerprint_lufs: float, sample_rate: int) -> float:
    """dB to add to a fingerprint-proxy loudness to put it on this module's K scale.

    The fingerprint's ``lufs`` is an RMS proxy and ``calculate_loudness_units``
    is K-weighted and channel-summed, so the same audio reads ~3-4 dB higher on
    the latter (+4.0 dB on correlated stereo pink noise). A target built as
    ``fingerprint_lufs + lift`` and then chased with ``calculate_loudness_units``
    therefore realises ``lift - offset``: loud masters were turned down although
    the generator never intends attenuation (#5700).

    Measuring the offset on the chunk itself keeps the correction exact for that
    chunk's spectrum and channel correlation instead of assuming a constant.
    Returns 0.0 when either side is unusable (silence, non-finite).
    """
    measured = calculate_loudness_units(audio, sample_rate)
    if not (np.isfinite(measured) and np.isfinite(fingerprint_lufs)):
        return 0.0
    if measured <= SILENCE_FLOOR_LUFS:
        return 0.0
    return float(np.clip(
        measured - fingerprint_lufs,
        -MAX_PROXY_TO_K_OFFSET_DB,
        MAX_PROXY_TO_K_OFFSET_DB,
    ))
