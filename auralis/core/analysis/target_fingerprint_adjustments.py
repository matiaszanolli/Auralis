"""
Target fingerprint adjustments
~~~~~~~~~~~~~~~~~~~~~~~

Split from ``AdaptiveTargetGenerator`` (#6272); each function takes the
generator as its first argument and the class method stays a thin delegator.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""


from typing import Any

from ...dsp.utils.loudness_targets import DEFAULT_TARGET_LUFS

from ..utils.fingerprint_unpacker import FingerprintUnpacker
from ...utils.logging import debug


def apply_fingerprint_enhancements(
    generator, targets: dict[str, Any],
                                   fingerprint: dict[str, float]) -> dict[str, Any]:
    """
    Apply intelligent enhancements based on 25D audio fingerprint.

    This uses the complete acoustic fingerprint to make precise, content-aware
    adjustments beyond simple rule-based heuristics.

    Args:
        targets: Base processing targets
        fingerprint: 25D audio fingerprint

    Returns:
        Enhanced targets with fingerprint-driven adjustments
    """
    debug("Applying 25D fingerprint-driven enhancements")

    enhanced = targets.copy()

    # 1. FREQUENCY-AWARE EQ ADJUSTMENTS (7D frequency distribution)
    # Use actual frequency distribution instead of guessing from spectral centroid
    # TODO(#5858): these are fractions in the 25D fingerprint but are compared
    # to percent thresholds below, so every real track takes the "light" branch.
    # The percent-scale defaults are kept as-is until that is decided.
    bass_pct = fingerprint.get("bass_pct", 15.0)
    mid_pct = fingerprint.get("mid_pct", 30.0)
    presence_pct = fingerprint.get("presence_pct", 10.0)
    air_pct = fingerprint.get("air_pct", 5.0)

    # Bass adjustment: compensate for deficiency/excess
    if bass_pct < 10.0:  # Bass-light
        enhanced["bass_boost_db"] = targets.get("bass_boost_db", 0.0) + 1.5
    elif bass_pct > 25.0:  # Bass-heavy
        enhanced["bass_boost_db"] = targets.get("bass_boost_db", 0.0) - 1.0

    # Mid-range adjustment
    if mid_pct < 20.0:  # Mid-scooped
        enhanced["midrange_clarity_db"] = targets.get("midrange_clarity_db", 0.0) + 1.2
    elif mid_pct > 40.0:  # Mid-heavy
        enhanced["midrange_clarity_db"] = targets.get("midrange_clarity_db", 0.0) - 0.8

    # Presence/Air adjustment
    high_freq_total = presence_pct + air_pct
    if high_freq_total < 10.0:  # Dark mix
        enhanced["treble_enhancement_db"] = targets.get("treble_enhancement_db", 0.0) + 1.8
    elif high_freq_total > 25.0:  # Bright mix
        enhanced["treble_enhancement_db"] = targets.get("treble_enhancement_db", 0.0) - 1.2

    # 2. DYNAMICS-AWARE COMPRESSION (3D dynamics characteristics)
    fp = FingerprintUnpacker.from_dict(fingerprint)
    lufs = fp.lufs
    crest_db = fp.crest_db

    # Adjust compression based on current dynamics
    if crest_db > 16.0:  # High dynamic range (classical, live recordings)
        enhanced["compression_ratio"] = max(1.5, targets.get("compression_ratio", 2.5) * 0.6)
        debug(f"High crest ({crest_db:.1f}dB) - reducing compression to preserve dynamics")
    elif crest_db < 8.0:  # Already brick-walled (loudness wars)
        enhanced["compression_ratio"] = max(1.2, targets.get("compression_ratio", 2.5) * 0.3)
        debug(f"Low crest ({crest_db:.1f}dB) - minimal compression, already squashed")

    # Adjust target LUFS based on current loudness
    if lufs > -10.0:  # Already very loud
        enhanced["target_lufs"] = max(DEFAULT_TARGET_LUFS, targets.get("target_lufs", DEFAULT_TARGET_LUFS) - 2.0)
        debug(f"Already loud ({lufs:.1f}LUFS) - conservative target")
    elif lufs < -25.0:  # Very quiet
        enhanced["target_lufs"] = min(-12.0, targets.get("target_lufs", DEFAULT_TARGET_LUFS) + 2.0)
        debug(f"Quiet input ({lufs:.1f}LUFS) - boost target")

    # 3. TEMPORAL-AWARE PROCESSING (4D temporal characteristics)
    transient_density = fp.transient_density

    # Adjust processing based on transient content
    if transient_density > 0.7:  # Drum-heavy, percussive
        # Preserve transients, reduce attack time
        enhanced["mastering_intensity"] = targets.get("mastering_intensity", 0.8) * 0.85
        debug(f"High transient density ({transient_density:.2f}) - preserving punch")
    elif transient_density < 0.3:  # Smooth, pad-heavy
        # Can be more aggressive
        enhanced["mastering_intensity"] = targets.get("mastering_intensity", 0.8) * 1.1

    # 4. HARMONIC-AWARE PROCESSING (3D harmonic characteristics)
    harmonic_ratio = fp.harmonic_ratio
    pitch_stability = fp.pitch_stability

    # Reduce processing intensity for highly harmonic content (vocals, strings)
    if harmonic_ratio > 0.7 and pitch_stability > 0.8:
        enhanced["mastering_intensity"] = targets.get("mastering_intensity", 0.8) * 0.9
        debug(f"Highly harmonic content (ratio={harmonic_ratio:.2f}) - gentle processing")

    # 5. STEREO-AWARE ADJUSTMENTS (2D stereo characteristics)
    stereo_width = fp.stereo_width
    phase_correlation = fp.phase_correlation

    # Adjust stereo width target based on current width
    if stereo_width < 0.3:  # Narrow/mono
        enhanced["stereo_width"] = min(0.9, targets.get("stereo_width", 0.7) + 0.2)
        debug(f"Narrow stereo ({stereo_width:.2f}) - expanding width")
    elif stereo_width > 0.85:  # Already very wide
        enhanced["stereo_width"] = max(0.5, targets.get("stereo_width", 0.7) - 0.1)
        debug(f"Already wide stereo ({stereo_width:.2f}) - slight reduction")

    # Check phase correlation - warn if problematic
    if phase_correlation < 0.5:
        debug(f"WARNING: Low phase correlation ({phase_correlation:.2f}) - potential mono compatibility issues")
        enhanced["stereo_width"] = min(enhanced.get("stereo_width", 0.7), 0.6)  # Reduce width

    # 6. VARIATION-AWARE ADJUSTMENTS (3D variation characteristics)
    loudness_variation = fp.loudness_variation_std

    # If material has intentional loudness variation (dynamics), preserve it
    if loudness_variation > 0.7:
        enhanced["compression_ratio"] = max(1.5, enhanced.get("compression_ratio", 2.5) * 0.8)
        debug(f"High loudness variation ({loudness_variation:.2f}) - preserving intentional dynamics")

    # Store fingerprint metadata for downstream processors
    enhanced["fingerprint_driven"] = True
    enhanced["fingerprint_version"] = "25D_v1"

    debug(f"Fingerprint enhancements applied: Bass {enhanced.get('bass_boost_db', 0):.1f}dB, "
          f"Comp {enhanced.get('compression_ratio', 0):.1f}:1, "
          f"Stereo width {enhanced.get('stereo_width', 0):.2f}")

    return enhanced
