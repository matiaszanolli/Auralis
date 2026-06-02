"""Stereo Expansion Stage — gentle adaptive multiband stereo widening."""

import numpy as np

from ...dsp.utils.stereo import adjust_stereo_width_multiband
from ..utils import SmoothCurveUtilities


def apply(
    audio: np.ndarray,
    current_width: float,
    intensity: float,
    sample_rate: int,
    verbose: bool,
    bass_pct: float = 0.3,
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
        bass_pct: Bass content percentage (for multiband weighting)
        spectral_centroid: Brightness indicator 0-1 (higher = brighter)
        air_pct: High-frequency air content 0-1
        phase_correlation: Stereo phase correlation (-1 to +1)

    Returns:
        (processed_audio, stage_info) or (audio, None) if no expansion applied
    """
    if current_width >= 0.40:
        return audio, None  # Already has decent width

    # Poor phase correlation — skip
    if phase_correlation < 0.3:
        if verbose:
            print(f"   ⚠️  Skipping stereo expansion (poor phase correlation: {phase_correlation:.2f})")
        return audio, None

    # Phase correlation factor: 0.3-0.7 fades in smoothly, 0.7+ = full
    if phase_correlation < 0.7:
        phase_factor = SmoothCurveUtilities.ramp_to_s_curve(phase_correlation, 0.3, 0.7)
    else:
        phase_factor = 1.0

    # Width expansion curve: bell curve with peak at 25% width
    if current_width < 0.15:
        width_curve = SmoothCurveUtilities.ramp_to_s_curve(current_width, 0.0, 0.15)
        narrowness_factor = 0.3 * width_curve
    elif current_width < 0.30:
        center = 0.225
        width_offset = current_width - center
        narrowness_factor = 0.6 * np.exp(-(width_offset**2) / (2 * 0.05**2))
    else:
        fade_curve = 1.0 - SmoothCurveUtilities.ramp_to_s_curve(current_width, 0.30, 0.40)
        narrowness_factor = 0.3 * fade_curve

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
    max_expansion = 0.08 * intensity
    expansion_amount = max_expansion * combined_factor

    if expansion_amount < 0.01:
        return audio, None

    width_factor = 0.5 + expansion_amount

    # adjust_stereo_width_multiband expects [samples, channels]
    audio_t = audio.T
    expanded = adjust_stereo_width_multiband(
        audio_t, width_factor, sample_rate,
        original_width=current_width,
        bass_content=bass_pct,
    )
    processed = expanded.T

    if verbose:
        expansion_pct = (width_factor - 0.5) * 200
        print(f"   Stereo expand: {current_width:.0%} → +{expansion_pct:.0f}% width (multiband)")

    return processed, {
        'stage': 'stereo_expand',
        'original_width': current_width,
        'width_factor': width_factor,
    }
