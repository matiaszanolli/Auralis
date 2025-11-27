# -*- coding: utf-8 -*-

"""
Adaptive Mode Processing
~~~~~~~~~~~~~~~~~~~~~~~~~

Spectrum-based adaptive processing without reference tracks

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict, Any, Optional
from ...dsp.basic import rms, amplify
from ...dsp.unified import (
    calculate_loudness_units, stereo_width_analysis, adjust_stereo_width
)
from ...dsp.dynamics.soft_clipper import soft_clip
from ...utils.logging import debug
from .base_processing_mode import (
    MeasurementUtilities, CompressionStrategies, ExpansionStrategies,
    DBConversion, StereoWidthProcessor
)


class AdaptiveMode:
    """
    Adaptive processing mode - intelligent mastering without reference tracks
    Uses spectrum-based analysis to determine optimal processing parameters
    """

    def __init__(self, config, content_analyzer, target_generator, spectrum_mapper):
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

    def process(self, target_audio: np.ndarray, eq_processor) -> np.ndarray:
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
                                   spectrum_params, spectrum_position) -> np.ndarray:
        """Apply compression and expansion based on spectrum parameters"""

        # SIMPLE DIY COMPRESSOR - Direct crest factor reduction
        if spectrum_params.compression_amount > 0.1:
            audio = self._apply_compression(audio, spectrum_params)

        # SIMPLE DIY EXPANDER - Direct crest factor expansion (de-mastering)
        if spectrum_params.expansion_amount > 0.1:
            audio = self._apply_expansion(audio, spectrum_params)

        return audio

    def _apply_compression(self, audio: np.ndarray, spectrum_params) -> np.ndarray:
        """Apply DIY compression to reduce crest factor"""
        return CompressionStrategies.apply_soft_knee_compression(
            audio,
            spectrum_params.compression_amount
        )

    def _apply_expansion(self, audio: np.ndarray, spectrum_params) -> np.ndarray:
        """Apply DIY expansion to increase crest factor (de-mastering)"""
        return ExpansionStrategies.apply_peak_enhancement_expansion(
            audio,
            spectrum_params.expansion_amount
        )

    def _apply_stereo_width(self, audio: np.ndarray, targets: Dict[str, Any],
                           spectrum_position) -> np.ndarray:
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

    def _apply_final_normalization(self, audio: np.ndarray, spectrum_params) -> np.ndarray:
        """Apply final RMS boost and peak normalization"""
        from ..config.preset_profiles import get_preset_profile

        peak = np.max(np.abs(audio))
        peak_db = DBConversion.to_db(peak)
        current_rms = rms(audio)
        current_rms_db = DBConversion.to_db(current_rms)
        current_crest = peak_db - current_rms_db

        print(f"[Pre-Final] Peak: {peak_db:.2f} dB, RMS: {current_rms_db:.2f} dB, Crest: {current_crest:.2f} dB")

        # Calculate target RMS from spectrum
        target_rms_db = spectrum_params.output_target_rms

        # IMPORTANT: Apply RMS gain BEFORE peak normalization to preserve dynamics
        # But ONLY for under-leveled material - NOT for already-loud material
        rms_diff_from_target = target_rms_db - current_rms_db

        # Only boost RMS if material is significantly under-leveled
        # AND we're not in expansion mode (expansion should REDUCE RMS)
        should_boost_rms = (
            rms_diff_from_target > 0.5 and  # Need significant boost
            current_rms_db < -15.0 and  # Material is actually quiet
            spectrum_params.expansion_amount < 0.1  # NOT expanding dynamics
        )

        if should_boost_rms:
            # Apply gain to reach target RMS first
            rms_boost = np.clip(rms_diff_from_target, 0.0, 12.0)  # Cap at +12 dB
            audio = amplify(audio, rms_boost)
            print(f"[RMS Boost] Applied {rms_boost:+.2f} dB (target: {target_rms_db:.1f} dB)")

            # Recalculate after boost
            peak = np.max(np.abs(audio))
            peak_db = DBConversion.to_db(peak)
            current_rms = rms(audio)
            current_rms_db = DBConversion.to_db(current_rms)
        else:
            if rms_diff_from_target > 0.5:
                print(f"[RMS Boost] SKIPPED - Material already loud (RMS: {current_rms_db:.2f} dB, target: {target_rms_db:.2f} dB)")

        # Get preset-specific peak target
        preset_name = self.config.mastering_profile
        preset_profile = get_preset_profile(preset_name)
        target_peak_db = preset_profile.peak_target_db if preset_profile else -1.00
        target_peak = DBConversion.to_linear(target_peak_db)

        print(f"[Peak Normalization] Preset: {preset_name}, Target: {target_peak_db:.2f} dB")

        if peak > 0.001:  # Avoid division by zero
            peak_change_db = target_peak_db - peak_db
            audio = audio * (target_peak / peak)
            print(f"[Peak Normalization] {peak_db:.2f} → {target_peak_db:.2f} dB (change: {peak_change_db:+.2f} dB)")

            # Recalculate final metrics
            current_rms = rms(audio)
            current_rms_db = DBConversion.to_db(current_rms)
            peak = np.max(np.abs(audio))
            peak_db = DBConversion.to_db(peak)
            current_crest = peak_db - current_rms_db

            print(f"[Final] Peak: {peak_db:.2f} dB, RMS: {current_rms_db:.2f} dB, Crest: {current_crest:.2f} dB")

        # Safety limiter (only if exceeds safety threshold)
        safety_threshold = -0.01  # dBFS
        final_peak = np.max(np.abs(audio))
        final_peak_db = DBConversion.to_db(final_peak)

        if final_peak_db > safety_threshold:
            print(f"[Safety Limiter] Peak {final_peak_db:.2f} dB exceeds threshold {safety_threshold:.2f} dB")
            # Apply gentle soft clipping to prevent hard clipping
            audio = soft_clip(audio, threshold=0.99)
            final_peak = np.max(np.abs(audio))
            final_peak_db = DBConversion.to_db(final_peak)
            print(f"[Safety Limiter] Peak reduced to {final_peak_db:.2f} dB")

        # Final metrics
        final_rms = rms(audio)
        final_rms_db = DBConversion.to_db(final_rms)
        final_crest = final_peak_db - final_rms_db

        debug(f"[Final Result] Peak: {final_peak_db:.2f} dB, RMS: {final_rms_db:.2f} dB, Crest: {final_crest:.2f} dB")

        return audio

    def get_last_content_profile(self) -> Optional[Dict[str, Any]]:
        """Get the last analyzed content profile"""
        return self.last_content_profile
