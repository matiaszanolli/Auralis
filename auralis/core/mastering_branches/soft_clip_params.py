"""
Adaptive Soft-Clip Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Multi-dimensional-aware threshold/ceiling computation for the QuietBranch soft
clipper. Extracted from ``QuietBranch.apply`` (#4252) as a pure function so the
branch module stays under the 300-line convention and the parameter logic is
independently testable.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any

from ..utils import SmoothCurveUtilities


def compute_soft_clip_threshold(
    unpacker: Any, config: Any, verbose: bool
) -> tuple[float, float]:
    """Compute the adaptive soft-clip ``(threshold_db, ceiling)`` for quiet material.

    Starts from a loudness-scaled base and relaxes (raises threshold / lifts
    ceiling) for content that soft clipping would harm: tonal/harmonic material,
    high dynamic-range variation, noisy/flat spectra, and bass-heavy mixes (whose
    low end otherwise takes the brunt of full-band saturation). The high-DR
    bypass/relax decision and the ``soft_clip`` call itself remain in the caller.

    Args:
        unpacker: Fingerprint unpacker with the 25 dimensions.
        config: Mastering configuration (preservation thresholds).
        verbose: Print which preservation adjustments engaged.

    Returns:
        ``(threshold_db, ceiling)`` for ``soft_clip``.
    """
    loudness_factor = max(0.0, min(1.0, (-11.0 - unpacker.lufs) / 9.0))
    threshold_db = -2.0 + (1.5 * (1.0 - loudness_factor))
    ceiling = 0.92 + (0.07 * loudness_factor)

    # Harmonic preservation - gentler clipping for tonal/harmonic content
    harmonic_preservation = (unpacker.harmonic_ratio * 0.7 + unpacker.pitch_stability * 0.3)
    if harmonic_preservation > config.HARMONIC_PRESERVATION_THRESHOLD:
        harmonic_factor = SmoothCurveUtilities.ramp_to_s_curve(
            harmonic_preservation, config.HARMONIC_PRESERVATION_THRESHOLD, 1.0
        )
        threshold_db += 0.5 * harmonic_factor
        ceiling += 0.03 * harmonic_factor
        if verbose:
            print(f"   🎼 Harmonic preservation ({harmonic_preservation:.2f})")

    # Variation awareness - gentler on inconsistent material
    variation_metric = unpacker.dynamic_range_variation * 0.6 + (1.0 - unpacker.peak_consistency) * 0.4
    if variation_metric > config.VARIATION_PRESERVATION_THRESHOLD:
        variation_factor = SmoothCurveUtilities.ramp_to_s_curve(
            variation_metric, config.VARIATION_PRESERVATION_THRESHOLD, 1.0
        )
        threshold_db += 0.4 * variation_factor
        if verbose:
            print(f"   📊 Variation preservation ({variation_metric:.2f})")

    # Spectral flatness awareness - noisy/percussive vs tonal
    if unpacker.spectral_flatness > config.FLATNESS_PRESERVATION_THRESHOLD:
        flatness_factor = SmoothCurveUtilities.ramp_to_s_curve(
            unpacker.spectral_flatness, config.FLATNESS_PRESERVATION_THRESHOLD, 1.0
        )
        threshold_db += 0.3 * flatness_factor
        if verbose:
            print(f"   🔊 Noise-aware processing ({unpacker.spectral_flatness:.2f})")

    # Bass-aware adjustment. The soft clipper is full-band, so on bass-heavy
    # material the low end dominates the peaks and takes the brunt of the
    # saturation. Lowering the threshold here used to drive that dominant
    # band *harder* into clipping — audible as an "overdriven"/gritty low
    # end. Instead RAISE the threshold for bass-heavy sources so the kick/
    # bass stays clean, and leave the ceiling alone (lowering it only cost
    # loudness). Peak control for these sources comes from the final
    # transient-safe limiter, not from saturating the bass.
    bass_intensity = SmoothCurveUtilities.ramp_to_s_curve(
        unpacker.bass_pct, 0.20, 0.70
    )
    threshold_db += 0.5 * bass_intensity

    return threshold_db, ceiling
