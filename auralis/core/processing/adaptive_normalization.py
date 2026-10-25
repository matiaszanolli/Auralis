"""
Adaptive Final Normalization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``_apply_final_normalization`` split from AdaptiveMode (#6272): the final
peak/LUFS normalization pass, as a function over the mode processor.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from auralis.dsp.utils.conversion import amplitude_to_db, db_to_amplitude
from typing import TYPE_CHECKING, Any

import numpy as np

from ...dsp.utils.conversion import SILENCE_FLOOR_DB
from ...utils.audio_validation import MAX_IN_STAGE_REPAIR_FRACTION, validate_audio_finite
from ...utils.logging import debug, info
from ...dsp.basic import rms
from ...dsp.utils.adaptive import calculate_loudness_units
from ...dsp.utils.adaptive_loudness import AdaptiveLoudnessControl
from .base.normalization_step import NormalizationStep
from .base.peak_management import SafetyLimiter
from .base.peak_management import PeakNormalizer
from .base.processing_logger import ProcessingLogger

if TYPE_CHECKING:
    from .adaptive_mode import AdaptiveMode


def apply_final_normalization(mode: "AdaptiveMode", audio: np.ndarray, spectrum_params: Any) -> np.ndarray:
    """Apply final gain boost and peak normalization using LUFS-based adaptive control"""

    # Catch NaN/Inf before any of the below computations — an unguarded
    # NaN/Inf here would propagate through calculate_loudness_units/
    # np.max/rms into makeup_gain and the peak normalizer, exactly the
    # failure class #3429 fixed for HybridMode's reference-blend path.
    # This method is HybridMode's own no-reference fallback (reachable
    # directly whenever no reference track is set — the common case),
    # so it needed the same guard (fixes #4237). The repair is bounded
    # (#6105): a mostly non-finite buffer raises instead of being zeroed,
    # so the mode-output fail-fast guard and the pipeline's fallback fire.
    audio = validate_audio_finite(
        audio,
        context="adaptive_mode final normalization",
        repair=True,
        repair_max_fraction=MAX_IN_STAGE_REPAIR_FRACTION,
    )

    # Step 0: Calculate source LUFS and crest factor for adaptive loudness control
    source_lufs = calculate_loudness_units(audio, mode.config.internal_sample_rate)

    # Calculate crest factor (peak-to-RMS ratio) for transient preservation
    current_peak = np.max(np.abs(audio))
    current_peak_db = amplitude_to_db(current_peak)
    current_rms = rms(audio)
    current_rms_db = amplitude_to_db(current_rms)
    crest_factor_db = current_peak_db - current_rms_db

    debug(f"[Adaptive Loudness] Source LUFS: {source_lufs:.2f} dB, Crest: {crest_factor_db:.2f} dB")

    # Step 1: LUFS-based adaptive gain (replaces RMS boost)
    makeup_gain_step = NormalizationStep("Adaptive Makeup Gain", stage_label="Pre-Final")
    makeup_gain_step.measure_before(audio)

    # Get adaptive makeup gain based on source LUFS and crest factor
    # Intensity from spectrum params (if available), otherwise 1.0
    intensity = getattr(spectrum_params, 'intensity', 1.0)

    # Extract bass and transient info from content profile for bass-aware gain reduction
    # This prevents kick/bass harmonic overlap in bass-heavy material
    bass_pct = float(
        mode.last_content_profile.get('bass_energy_pct', 0.0)
        if mode.last_content_profile else 0.0
    )
    transient_density = float(
        mode.last_content_profile.get('transient_density', 0.0)
        if mode.last_content_profile else 0.0
    )

    makeup_gain, gain_reasoning = AdaptiveLoudnessControl.calculate_adaptive_gain(
        source_lufs, intensity, crest_factor_db, bass_pct, transient_density
    )

    if mode.last_content_profile:
        debug(
            f"[Bass-Aware Gain] Bass: {bass_pct:.1%}, "
            f"Transients: {transient_density:.2f} - {gain_reasoning}"
        )

    # Only apply makeup gain if not in expansion mode AND gain is > 0.5 dB
    should_apply_gain = (
        makeup_gain > 0.5 and
        spectrum_params.expansion_amount < 0.1
    )

    if should_apply_gain:
        audio = makeup_gain_step.apply_gain(audio, makeup_gain)
        makeup_gain_step.measure_after(audio)
        ProcessingLogger.gain_applied("Adaptive Makeup Gain", makeup_gain, AdaptiveLoudnessControl.TARGET_LUFS)
        debug(f"[Adaptive Loudness] {gain_reasoning}")
    else:
        if makeup_gain > 0.5:
            ProcessingLogger.skipped("Adaptive Makeup Gain", "Expansion mode active")
        else:
            ProcessingLogger.skipped("Adaptive Makeup Gain", gain_reasoning)

    # Step 2: Adaptive peak normalization based on source LUFS
    # Use LUFS-based adaptive target instead of fixed preset target
    target_peak, target_peak_db = AdaptiveLoudnessControl.calculate_adaptive_peak_target(source_lufs)

    # Check current peak before normalizing
    current_peak = np.max(np.abs(audio))
    current_peak_db = amplitude_to_db(current_peak)

    # Only normalize if peak is significantly below adaptive target (> 1.5 dB headroom)
    # This prevents over-boosting material that's already at reasonable levels
    if current_peak_db < (target_peak_db - 1.5):
        preset_name = mode.config.mastering_profile
        audio, _ = PeakNormalizer.normalize_to_target(audio, target_peak_db, preset_name)
        debug(f"[Adaptive Loudness] Normalized to adaptive peak: {target_peak * 100:.1f}% ({target_peak_db:.2f} dB)")
    else:
        ProcessingLogger.skipped("Peak Normalization", f"Peak already at {current_peak_db:.2f} dB (adaptive target: {target_peak_db:.2f} dB)")
        debug(f"[Adaptive Loudness] Skipped normalization - peak already appropriate for {source_lufs:.1f} LUFS source")

    # Log final pre-limiter metrics
    final_peak = np.max(np.abs(audio))
    final_peak_db = amplitude_to_db(final_peak)
    final_rms = rms(audio)
    final_rms_db = amplitude_to_db(final_rms)
    final_crest = final_peak_db - final_rms_db
    ProcessingLogger.pre_stage("Final", final_peak_db, final_rms_db, final_crest)

    # Step 3: Safety limiter
    audio, _ = SafetyLimiter.apply_if_needed(audio)

    # Final metrics
    final_peak = np.max(np.abs(audio))
    final_peak_db = amplitude_to_db(final_peak)
    final_rms = rms(audio)
    final_rms_db = amplitude_to_db(final_rms)
    final_crest = final_peak_db - final_rms_db

    debug(f"[Final Result] Peak: {final_peak_db:.2f} dB, RMS: {final_rms_db:.2f} dB, Crest: {final_crest:.2f} dB")

    return audio
