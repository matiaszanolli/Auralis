"""
Adaptive Mode Processing
~~~~~~~~~~~~~~~~~~~~~~~~~

Spectrum-based adaptive processing without reference tracks

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any

import numpy as np

from ...dsp.basic import amplify, rms
from ...dsp.unified import (
    calculate_loudness_units,
    stereo_width_analysis,
)
from ...dsp.utils.adaptive_loudness import AdaptiveLoudnessControl
from ...utils.logging import debug
from .base import (
    CompressionStrategies,
    DBConversion,
    ExpansionStrategies,
    NormalizationStep,
    PeakNormalizer,
    ProcessingLogger,
    SafetyLimiter,
    StereoWidthProcessor,
)


class AdaptiveMode:
    """
    Adaptive processing mode - intelligent mastering without reference tracks
    Uses spectrum-based analysis to determine optimal processing parameters
    """

    def __init__(self, config: Any, content_analyzer: Any, target_generator: Any, spectrum_mapper: Any) -> None:
        """
        Initialize adaptive mode processor

        Args:
            config: UnifiedConfig instance
            content_analyzer: ContentAnalyzer instance
            target_generator: AdaptiveTargetGenerator instance
            spectrum_mapper: SpectrumMapper instance
        """
        self.config = config
        self.content_analyzer = content_analyzer
        self.target_generator = target_generator
        self.spectrum_mapper = spectrum_mapper
        self.last_content_profile = None

    def process(self, target_audio: np.ndarray, eq_processor: Any) -> np.ndarray:
        """
        Process audio using adaptive mastering

        Args:
            target_audio: Input audio array
            eq_processor: EQ processor instance for psychoacoustic EQ

        Returns:
            Processed audio array
        """
        debug("Applying spectrum-based adaptive processing")

        processed_audio = target_audio.copy()

        # Analyze content first
        content_profile = self.content_analyzer.analyze_content(processed_audio)

        # Store content profile for potential user learning
        self.last_content_profile = content_profile

        # Analyze input level and add to content profile
        input_level_info = self.content_analyzer.analyze_input_level(processed_audio)
        content_profile['input_level_info'] = input_level_info

        # SPECTRUM-BASED PROCESSING: Get position on spectrum
        spectrum_position = self.spectrum_mapper.analyze_to_spectrum_position(content_profile)

        # Get user's preset as a hint (not a rigid rule)
        preset_profile = self.config.get_preset_profile()
        preset_hint = preset_profile.name.lower() if preset_profile else 'adaptive'

        # Calculate processing parameters from spectrum position
        spectrum_params = self.spectrum_mapper.calculate_processing_parameters(
            spectrum_position,
            user_preset_hint=preset_hint
        )

        print(f"[Spectrum Position] Level:{spectrum_position.input_level:.2f} "
              f"Dynamics:{spectrum_position.dynamic_range:.2f} "
              f"Balance:{spectrum_position.spectral_balance:.2f} "
              f"Energy:{spectrum_position.energy:.2f}")

        print(f"[Spectrum Params] Compression:{spectrum_params.compression_ratio:.2f}@{spectrum_params.compression_amount:.2f} "
              f"InputGain:{spectrum_params.input_gain:+.1f}dB "
              f"TargetRMS:{spectrum_params.output_target_rms:.1f}dB")

        # Apply input gain from spectrum calculation
        if abs(spectrum_params.input_gain) > 0.5:
            processed_audio = amplify(processed_audio, spectrum_params.input_gain)
            debug(f"[Spectrum Gain Staging] Applied {spectrum_params.input_gain:+.2f} dB input gain")

        # Track loudness through each processing stage
        before_eq_lufs = calculate_loudness_units(processed_audio, self.config.internal_sample_rate)
        debug(f"[STAGE 1] Before EQ: {before_eq_lufs:.2f} LUFS")

        # Generate adaptive targets
        targets = self.target_generator.generate_targets(content_profile)

        # Apply psychoacoustic EQ adjustments with content awareness
        processed_audio = eq_processor.apply_psychoacoustic_eq(processed_audio, targets, content_profile)

        after_eq_lufs = calculate_loudness_units(processed_audio, self.config.internal_sample_rate)
        peak_after_eq = np.max(np.abs(processed_audio))
        peak_after_eq_db = 20 * np.log10(peak_after_eq) if peak_after_eq > 0 else -np.inf
        print(f"[After EQ] Peak: {peak_after_eq_db:.2f} dB")
        debug(f"[STAGE 2] After EQ: {after_eq_lufs:.2f} LUFS (change: {after_eq_lufs - before_eq_lufs:+.2f} dB)")

        # Apply dynamics processing
        processed_audio = self._apply_dynamics_processing(
            processed_audio, spectrum_params, spectrum_position
        )

        # Apply stereo width adjustment
        processed_audio = self._apply_stereo_width(
            processed_audio, targets, spectrum_position
        )

        # Apply final normalization
        processed_audio = self._apply_final_normalization(
            processed_audio, spectrum_params
        )

        return processed_audio

    def _apply_dynamics_processing(self, audio: np.ndarray,
                                   spectrum_params: Any, spectrum_position: Any) -> np.ndarray:
        """Apply compression and expansion based on spectrum parameters and 2D LWRP"""

        # CRITICAL: 2D Loudness-War Restraint Principle check
        # Determine if we need expansion for compressed loud material
        source_lufs = calculate_loudness_units(audio, self.config.internal_sample_rate)
        current_peak = np.max(np.abs(audio))
        current_peak_db = DBConversion.to_db(current_peak)
        current_rms = rms(audio)
        current_rms_db = DBConversion.to_db(current_rms)
        crest_factor_db = current_peak_db - current_rms_db

        # Check if this is compressed loud material that needs special handling
        is_compressed_loud = (
            source_lufs > AdaptiveLoudnessControl.VERY_LOUD_THRESHOLD and
            crest_factor_db < 13.0
        )

        if is_compressed_loud:
            # Compressed loud material: Apply expansion to restore dynamics
            expansion_factor = max(0.1, (13.0 - crest_factor_db) / 10.0)
            debug(f"[2D LWRP] Compressed loud (LUFS {source_lufs:.1f}, crest {crest_factor_db:.1f}) → expansion {expansion_factor:.2f}")
            print(f"[2D LWRP] Compressed loud material (LUFS {source_lufs:.1f} dB, crest {crest_factor_db:.1f} dB)")
            print(f"[2D LWRP] → Applying expansion factor {expansion_factor:.2f} to restore dynamics")

            # Override spectrum_params expansion with LWRP-driven expansion
            spectrum_params.expansion_amount = expansion_factor
            spectrum_params.compression_amount = 0.0  # Don't compress compressed material further

            # Apply expansion
            audio = self._apply_expansion(audio, spectrum_params)

            # Apply gentle gain reduction to prevent over-loudness after expansion
            gentle_reduction = -0.5
            audio = amplify(audio, gentle_reduction)
            debug(f"[2D LWRP] Applied {gentle_reduction:.1f} dB gentle reduction after expansion")
            print(f"[2D LWRP] → Applied {gentle_reduction:.1f} dB gentle gain reduction")

        elif source_lufs > AdaptiveLoudnessControl.VERY_LOUD_THRESHOLD:
            # Dynamic loud material: Pass-through (LWRP principle)
            debug(f"[2D LWRP] Dynamic loud (LUFS {source_lufs:.1f}, crest {crest_factor_db:.1f}) → pass-through")
            print(f"[2D LWRP] Dynamic loud material (LUFS {source_lufs:.1f} dB, crest {crest_factor_db:.1f} dB)")
            print(f"[2D LWRP] → Respecting original mastering (minimal processing)")
            spectrum_params.compression_amount = 0.0
            spectrum_params.expansion_amount = 0.0

        else:
            # Quiet/moderate material: Use spectrum-based parameters
            # SIMPLE DIY COMPRESSOR - Direct crest factor reduction
            if spectrum_params.compression_amount > 0.1:
                audio = self._apply_compression(audio, spectrum_params)

            # SIMPLE DIY EXPANDER - Direct crest factor expansion (de-mastering)
            if spectrum_params.expansion_amount > 0.1:
                audio = self._apply_expansion(audio, spectrum_params)

        return audio

    def _apply_compression(self, audio: np.ndarray, spectrum_params: Any) -> np.ndarray:
        """Apply DIY compression to reduce crest factor"""
        return CompressionStrategies.apply_soft_knee_compression(
            audio,
            spectrum_params.compression_amount
        )

    def _apply_expansion(self, audio: np.ndarray, spectrum_params: Any) -> np.ndarray:
        """Apply DIY expansion to increase crest factor (de-mastering)"""
        return ExpansionStrategies.apply_peak_enhancement_expansion(
            audio,
            spectrum_params.expansion_amount
        )

    def _apply_stereo_width(self, audio: np.ndarray, targets: dict[str, Any],
                           spectrum_position: Any) -> np.ndarray:
        """Apply stereo width adjustment with safety checks"""

        if not StereoWidthProcessor.validate_stereo(audio):
            return audio

        peak_before_stereo_db = StereoWidthProcessor.get_peak_db(audio)
        current_width = stereo_width_analysis(audio)
        target_width = targets["stereo_width"]

        # CRITICAL: Prevent stereo width expansion from creating excessive peaks
        # Limit expansion for already-loud material
        if spectrum_position.input_level > 0.8 and target_width > current_width:
            max_width_increase = 0.6
            target_width = min(target_width, current_width + max_width_increase)
            print(f"[Stereo Width] Limited expansion for loud material: target reduced to {target_width:.2f}")

        # Apply stereo width with safety checks
        audio = StereoWidthProcessor.apply_stereo_width_safe(
            audio, current_width, target_width, peak_before_stereo_db, safety_mode="adaptive"
        )

        return audio

    def _apply_final_normalization(self, audio: np.ndarray, spectrum_params: Any) -> np.ndarray:
        """Apply final gain boost and peak normalization using LUFS-based adaptive control"""

        # Step 0: Calculate source LUFS and crest factor for adaptive loudness control
        source_lufs = calculate_loudness_units(audio, self.config.internal_sample_rate)

        # Calculate crest factor (peak-to-RMS ratio) for transient preservation
        current_peak = np.max(np.abs(audio))
        current_peak_db = DBConversion.to_db(current_peak)
        current_rms = rms(audio)
        current_rms_db = DBConversion.to_db(current_rms)
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
        bass_pct = self.last_content_profile.get('bass_energy_pct', None) if self.last_content_profile else None
        transient_density = self.last_content_profile.get('transient_density', None) if self.last_content_profile else None

        makeup_gain, gain_reasoning = AdaptiveLoudnessControl.calculate_adaptive_gain(
            source_lufs, intensity, crest_factor_db, bass_pct, transient_density
        )

        if bass_pct is not None:
            debug(f"[Bass-Aware Gain] Bass: {bass_pct:.1%}, Transients: {transient_density:.2f if transient_density else 0} - {gain_reasoning}")

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
        current_peak_db = DBConversion.to_db(current_peak)

        # Only normalize if peak is significantly below adaptive target (> 1.5 dB headroom)
        # This prevents over-boosting material that's already at reasonable levels
        if current_peak_db < (target_peak_db - 1.5):
            preset_name = self.config.mastering_profile
            audio, _ = PeakNormalizer.normalize_to_target(audio, target_peak_db, preset_name)
            debug(f"[Adaptive Loudness] Normalized to adaptive peak: {target_peak * 100:.1f}% ({target_peak_db:.2f} dB)")
        else:
            ProcessingLogger.skipped("Peak Normalization", f"Peak already at {current_peak_db:.2f} dB (adaptive target: {target_peak_db:.2f} dB)")
            debug(f"[Adaptive Loudness] Skipped normalization - peak already appropriate for {source_lufs:.1f} LUFS source")

        # Log final pre-limiter metrics
        final_peak = np.max(np.abs(audio))
        final_peak_db = DBConversion.to_db(final_peak)
        final_rms = rms(audio)
        final_rms_db = DBConversion.to_db(final_rms)
        final_crest = final_peak_db - final_rms_db
        ProcessingLogger.pre_stage("Final", final_peak_db, final_rms_db, final_crest)

        # Step 3: Safety limiter
        audio, _ = SafetyLimiter.apply_if_needed(audio)

        # Final metrics
        final_peak = np.max(np.abs(audio))
        final_peak_db = DBConversion.to_db(final_peak)
        final_rms = rms(audio)
        final_rms_db = DBConversion.to_db(final_rms)
        final_crest = final_peak_db - final_rms_db

        debug(f"[Final Result] Peak: {final_peak_db:.2f} dB, RMS: {final_rms_db:.2f} dB, Crest: {final_crest:.2f} dB")

        return audio

    def get_last_content_profile(self) -> dict[str, Any] | None:
        """Get the last analyzed content profile"""
        return self.last_content_profile
