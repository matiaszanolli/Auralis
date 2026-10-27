"""Stereo Expansion Stage — gentle adaptive multiband stereo widening."""

import numpy as np

from . import no_op

from ...dsp.utils.stereo import adjust_stereo_width_multiband
from ..utils import SmoothCurveUtilities


# Anchors of narrowness_curve on the fingerprint stereo_width axis (0 = mono).
_NARROW_END = 0.15      # linear segment ends here, at 0.6
_BELL_END = 0.30        # bell segment ends here, at 0.3; the fade-out starts
_FADE_END = 0.40        # no widening at or beyond this width
_AT_NARROW_END = 0.6
_AT_BELL_END = 0.3
_BELL_CENTER = 0.225
_BELL_SIGMA = 0.05
_BELL_CENTER_VALUE = 0.6  # the curve's value at the bell centre (the old Gaussian's peak)


def narrowness_curve(current_width: float) -> float:
    """Widening weight for a stereo width in [0, 0.40): one continuous curve (#5724).

    1.0 at mono, falling linearly to 0.6 at 0.15 (the narrowest, in-phase
    material has the most headroom); a bell that passes through 0.6 at 0.225 and
    joins both neighbours; then an S-curve fade from 0.3 at 0.30 to 0 at 0.40.
    The bell used to be a bare Gaussian that started and ended at 0.195, so the
    weight jumped at 0.15 (0.6 -> 0.195) and at 0.30 (0.195 -> 0.3) and two
    tracks 0.0002 apart in width got side gains +2.6 dB vs +0.9 dB. It now rides
    on the straight line from 0.6 to 0.3 and adds a bell that is zero at both
    ends, sized to keep the 0.6 at the centre.
    """
    if current_width < _NARROW_END:
        return 0.6 + 0.4 * (1.0 - current_width / _NARROW_END)
    if current_width < _BELL_END:
        def line(w: float) -> float:
            return _AT_NARROW_END + (_AT_BELL_END - _AT_NARROW_END) * (w - _NARROW_END) / (_BELL_END - _NARROW_END)

        def gaussian(w: float) -> float:
            return float(np.exp(-((w - _BELL_CENTER) ** 2) / (2 * _BELL_SIGMA**2)))

        edge = gaussian(_NARROW_END)  # == gaussian(_BELL_END): the centre is midway
        bell = (gaussian(current_width) - edge) / (1.0 - edge)
        return line(current_width) + (_BELL_CENTER_VALUE - line(_BELL_CENTER)) * bell
    fade_curve = 1.0 - SmoothCurveUtilities.ramp_to_s_curve(current_width, _BELL_END, _FADE_END)
    return float(_AT_BELL_END * fade_curve)


def apply(
    audio: np.ndarray,
    current_width: float,
    intensity: float,
    sample_rate: int,
    verbose: bool,
    spectral_centroid: float = 0.5,
    air_pct: float = 0.1,
    phase_correlation: float = 1.0,
) -> tuple[np.ndarray, dict | None]:
    """Apply gentle adaptive stereo expansion with brightness preservation.

    CONSERVATIVE: Very narrow mixes (< 20%) are likely intentional production choices.
    Only applies subtle widening to avoid unnatural "thin" sound.

    Uses gentle frequency-dependent expansion:
    - Lows (<200Hz): No expansion — keeps kick/bass punchy
    - Low-mids (200-2kHz): Minimal expansion — preserves body
    - High-mids (2k-8kHz): Gentle expansion — subtle width
    - Highs (>8kHz): Reduced expansion — avoids thin/hollow sound

    Args:
        audio: Stereo audio [channels, samples]
        current_width: Fingerprint stereo_width (0=mono, 1=wide)
        intensity: Processing intensity 0.0-1.0
        sample_rate: Audio sample rate in Hz
        verbose: Print progress
        spectral_centroid: Brightness indicator 0-1 (higher = brighter)
        air_pct: High-frequency air content 0-1
        phase_correlation: Stereo phase correlation (-1 to +1)

    Returns:
        (processed_audio, stage_info) or (audio, None) if no expansion applied
    """
    if current_width >= 0.40:
        return no_op(audio)  # Already has decent width

    # Poor phase correlation — skip
    if phase_correlation < 0.3:
        if verbose:
            print(f"   ⚠️  Skipping stereo expansion (poor phase correlation: {phase_correlation:.2f})")
        return no_op(audio)

    # Phase correlation factor: 0.3-0.7 fades in smoothly, 0.7+ = full
    if phase_correlation < 0.7:
        phase_factor = SmoothCurveUtilities.ramp_to_s_curve(phase_correlation, 0.3, 0.7)
    else:
        phase_factor = 1.0

    narrowness_factor = narrowness_curve(current_width)

    # Brightness preservation — reduce expansion for bright tracks
    brightness_metric = max(spectral_centroid, air_pct * 2.0)
    if brightness_metric > 0.6:
        brightness_curve = SmoothCurveUtilities.ramp_to_s_curve(brightness_metric, 0.6, 1.0)
        brightness_factor = 1.0 - (0.5 * brightness_curve)
        if verbose:
            print(f"   💡 Brightness preservation ({brightness_metric:.2f}, factor: {brightness_factor:.2f})")
    else:
        brightness_factor = 1.0

    combined_factor = narrowness_factor * phase_factor * brightness_factor
    # Ceiling raised 0.08 → 0.13: the old cap made even ideal candidates (very
    # narrow, high phase correlation) widen only marginally. Lows <200 Hz stay
    # mono inside adjust_stereo_width_multiband, so kick/bass punch is unharmed.
    max_expansion = 0.13 * intensity
    expansion_amount = max_expansion * combined_factor

    if expansion_amount < 0.01:
        return no_op(audio)

    width_factor = 0.5 + expansion_amount

    # adjust_stereo_width_multiband expects [samples, channels]
    audio_t = audio.T
    expanded = adjust_stereo_width_multiband(audio_t, width_factor, sample_rate)
    processed = expanded.T

    if verbose:
        expansion_pct = (width_factor - 0.5) * 200
        print(f"   Stereo expand: {current_width:.0%} → +{expansion_pct:.0f}% width (multiband)")

    return processed, {
        'stage': 'stereo_expand',
        'original_width': current_width,
        'width_factor': width_factor,
    }
