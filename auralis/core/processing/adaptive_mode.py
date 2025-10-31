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

        # Measure current state
        before_comp_peak = np.max(np.abs(audio))
        before_comp_peak_db = 20 * np.log10(before_comp_peak) if before_comp_peak > 0 else -np.inf
        before_comp_rms = rms(audio)
        before_comp_rms_db = 20 * np.log10(before_comp_rms) if before_comp_rms > 0 else -np.inf
        before_comp_crest = before_comp_peak_db - before_comp_rms_db

        # Calculate target crest reduction based on compression amount
        # compression_amount = 0.85 means reduce crest by ~3 dB (from Matchering data)
        # Use higher multiplier to account for stereo expansion adding peaks back
        target_crest_reduction = spectrum_params.compression_amount * 4.5  # Max ~3.8 dB reduction

        # Simple soft clipping approach: reduce peaks while preserving RMS
        # Calculate soft clip threshold based on desired crest reduction
        target_crest = before_comp_crest - target_crest_reduction
        clip_threshold_db = before_comp_rms_db + target_crest
        clip_threshold_linear = 10 ** (clip_threshold_db / 20)

        # Apply soft clipping
        audio_abs = np.abs(audio)
        over_threshold = audio_abs > clip_threshold_linear

        if np.any(over_threshold):
            # Soft knee compression for samples over threshold
            # Use adaptive ratio based on compression intensity
            compression_ratio = 3.0 + spectrum_params.compression_amount * 4.0  # 3:1 to 7:1
            excess = audio_abs[over_threshold] - clip_threshold_linear
            compressed_excess = excess / compression_ratio
            new_amplitude = clip_threshold_linear + compressed_excess

            # Apply compression while preserving sign
            audio[over_threshold] = np.sign(audio[over_threshold]) * new_amplitude

        # Measure result
        after_comp_peak = np.max(np.abs(audio))
        after_comp_peak_db = 20 * np.log10(after_comp_peak) if after_comp_peak > 0 else -np.inf
        after_comp_rms = rms(audio)
        after_comp_rms_db = 20 * np.log10(after_comp_rms) if after_comp_rms > 0 else -np.inf
        after_comp_crest = after_comp_peak_db - after_comp_rms_db

        print(f"[DIY Compressor] Peak: {before_comp_peak_db:.2f} → {after_comp_peak_db:.2f} dB (Δ {after_comp_peak_db - before_comp_peak_db:+.2f} dB)")
        print(f"[DIY Compressor] RMS: {before_comp_rms_db:.2f} → {after_comp_rms_db:.2f} dB (Δ {after_comp_rms_db - before_comp_rms_db:+.2f} dB)")
        print(f"[DIY Compressor] Crest: {before_comp_crest:.2f} → {after_comp_crest:.2f} dB (Δ {after_comp_crest - before_comp_crest:+.2f} dB, target: {-target_crest_reduction:.2f} dB)")

        return audio

    def _apply_expansion(self, audio: np.ndarray, spectrum_params) -> np.ndarray:
        """Apply DIY expansion to increase crest factor (de-mastering)"""

        # Measure current state
        before_exp_peak = np.max(np.abs(audio))
        before_exp_peak_db = 20 * np.log10(before_exp_peak) if before_exp_peak > 0 else -np.inf
        before_exp_rms = rms(audio)
        before_exp_rms_db = 20 * np.log10(before_exp_rms) if before_exp_rms > 0 else -np.inf
        before_exp_crest = before_exp_peak_db - before_exp_rms_db

        # Calculate target crest expansion based on expansion amount
        # expansion_amount = 0.7 means expand crest by ~4-6 dB (Pantera/Motörhead cases)
        # expansion_amount = 0.4 means expand crest by ~2-3 dB (Soda Stereo case)
        target_crest_expansion = spectrum_params.expansion_amount * 6.0  # Max ~4.2 dB expansion

        # Expansion approach: Enhance peaks while preserving RMS
        # We want to make loud samples louder (above RMS) to increase dynamic contrast
        expansion_threshold_db = before_exp_rms_db + 3.0  # Start expanding 3 dB above RMS
        expansion_threshold_linear = 10 ** (expansion_threshold_db / 20)

        # Apply expansion
        audio_abs = np.abs(audio)
        above_threshold = audio_abs > expansion_threshold_linear

        if np.any(above_threshold):
            # Expansion: boost samples above threshold
            # expansion_ratio: 1:2 means for every 1 dB above threshold, add 2 dB
            expansion_ratio = 1.0 + spectrum_params.expansion_amount  # 1.1 to 1.7
            excess = audio_abs[above_threshold] - expansion_threshold_linear

            # Convert to dB, apply expansion, convert back
            excess_db = 20 * np.log10(excess / expansion_threshold_linear + 1.0)
            expanded_excess_db = excess_db * expansion_ratio
            expanded_excess_linear = (10 ** (expanded_excess_db / 20) - 1.0) * expansion_threshold_linear

            new_amplitude = expansion_threshold_linear + expanded_excess_linear

            # Apply expansion while preserving sign
            audio[above_threshold] = np.sign(audio[above_threshold]) * new_amplitude

        # Measure result
        after_exp_peak = np.max(np.abs(audio))
        after_exp_peak_db = 20 * np.log10(after_exp_peak) if after_exp_peak > 0 else -np.inf
        after_exp_rms = rms(audio)
        after_exp_rms_db = 20 * np.log10(after_exp_rms) if after_exp_rms > 0 else -np.inf
        after_exp_crest = after_exp_peak_db - after_exp_rms_db

        print(f"[DIY Expander] Peak: {before_exp_peak_db:.2f} → {after_exp_peak_db:.2f} dB (Δ {after_exp_peak_db - before_exp_peak_db:+.2f} dB)")
        print(f"[DIY Expander] RMS: {before_exp_rms_db:.2f} → {after_exp_rms_db:.2f} dB (Δ {after_exp_rms_db - before_exp_rms_db:+.2f} dB)")
        print(f"[DIY Expander] Crest: {before_exp_crest:.2f} → {after_exp_crest:.2f} dB (Δ {after_exp_crest - before_exp_crest:+.2f} dB, target: +{target_crest_expansion:.2f} dB)")

        return audio

    def _apply_stereo_width(self, audio: np.ndarray, targets: Dict[str, Any],
                           spectrum_position) -> np.ndarray:
        """Apply stereo width adjustment with safety checks"""

        if audio.ndim != 2 or audio.shape[1] != 2:
            return audio  # Skip if not stereo

        peak_before_stereo = np.max(np.abs(audio))
        peak_before_stereo_db = 20 * np.log10(peak_before_stereo) if peak_before_stereo > 0 else -np.inf

        current_width = stereo_width_analysis(audio)
        target_width = targets["stereo_width"]

        # CRITICAL: Prevent stereo width expansion from creating excessive peaks
        # Strategy 1: Limit expansion for already-loud material
        if spectrum_position.input_level > 0.8 and target_width > current_width:
            max_width_increase = 0.3  # Only allow +0.3 increase
            target_width = min(target_width, current_width + max_width_increase)
            print(f"[Stereo Width] Limited expansion for loud material: target reduced to {target_width:.2f}")

        # Strategy 2: Skip expansion if current peak is already high (> 3 dB)
        if peak_before_stereo_db > 3.0 and target_width > current_width:
            print(f"[Stereo Width] SKIPPED expansion due to high peak ({peak_before_stereo_db:.2f} dB) - preserving dynamics")
            target_width = current_width  # Keep current width

        if abs(current_width - target_width) > 0.1:
            audio = adjust_stereo_width(audio, target_width)

            peak_after_stereo = np.max(np.abs(audio))
            peak_after_stereo_db = 20 * np.log10(peak_after_stereo) if peak_after_stereo > 0 else -np.inf
            print(f"[Stereo Width] Peak: {peak_before_stereo_db:.2f} → {peak_after_stereo_db:.2f} dB (width: {current_width:.2f} → {target_width:.2f})")

        return audio

    def _apply_final_normalization(self, audio: np.ndarray, spectrum_params) -> np.ndarray:
        """Apply final RMS boost and peak normalization"""
        from ..config.preset_profiles import get_preset_profile

        peak = np.max(np.abs(audio))
        peak_db = 20 * np.log10(peak) if peak > 0 else -np.inf
        current_rms = rms(audio)
        current_rms_db = 20 * np.log10(current_rms) if current_rms > 0 else -np.inf
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
            peak_db = 20 * np.log10(peak) if peak > 0 else -np.inf
            current_rms = rms(audio)
            current_rms_db = 20 * np.log10(current_rms) if current_rms > 0 else -np.inf
        else:
            if rms_diff_from_target > 0.5:
                print(f"[RMS Boost] SKIPPED - Material already loud (RMS: {current_rms_db:.2f} dB, target: {target_rms_db:.2f} dB)")

        # Get preset-specific peak target
        preset_name = self.config.mastering_profile
        preset_profile = get_preset_profile(preset_name)
        target_peak_db = preset_profile.peak_target_db if preset_profile else -1.00
        target_peak = 10 ** (target_peak_db / 20)  # Convert dB to linear

        print(f"[Peak Normalization] Preset: {preset_name}, Target: {target_peak_db:.2f} dB")

        if peak > 0.001:  # Avoid division by zero
            peak_change_db = target_peak_db - peak_db
            audio = audio * (target_peak / peak)
            print(f"[Peak Normalization] {peak_db:.2f} → {target_peak_db:.2f} dB (change: {peak_change_db:+.2f} dB)")

            # Recalculate final metrics
            current_rms = rms(audio)
            current_rms_db = 20 * np.log10(current_rms) if current_rms > 0 else -np.inf
            peak = np.max(np.abs(audio))
            peak_db = 20 * np.log10(peak) if peak > 0 else -np.inf
            current_crest = peak_db - current_rms_db

            print(f"[Final] Peak: {peak_db:.2f} dB, RMS: {current_rms_db:.2f} dB, Crest: {current_crest:.2f} dB")

        # Safety limiter (only if exceeds safety threshold)
        safety_threshold = -0.01  # dBFS
        final_peak = np.max(np.abs(audio))
        final_peak_db = 20 * np.log10(final_peak) if final_peak > 0 else -np.inf

        if final_peak_db > safety_threshold:
            print(f"[Safety Limiter] Peak {final_peak_db:.2f} dB exceeds threshold {safety_threshold:.2f} dB")
            # Apply gentle soft clipping to prevent hard clipping
            audio = soft_clip(audio, threshold=0.99)
            final_peak = np.max(np.abs(audio))
            final_peak_db = 20 * np.log10(final_peak) if final_peak > 0 else -np.inf
            print(f"[Safety Limiter] Peak reduced to {final_peak_db:.2f} dB")

        # Final metrics
        final_rms = rms(audio)
        final_rms_db = 20 * np.log10(final_rms) if final_rms > 0 else -np.inf
        final_crest = final_peak_db - final_rms_db

        debug(f"[Final Result] Peak: {final_peak_db:.2f} dB, RMS: {final_rms_db:.2f} dB, Crest: {final_crest:.2f} dB")

        return audio

    def get_last_content_profile(self) -> Optional[Dict[str, Any]]:
        """Get the last analyzed content profile"""
        return self.last_content_profile
