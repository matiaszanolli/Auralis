# -*- coding: utf-8 -*-

"""
Hybrid Audio Processor
~~~~~~~~~~~~~~~~~~~~~~

Unified processor supporting both reference-based and adaptive mastering

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Main processing engine that bridges Matchering and Auralis systems
"""

import numpy as np
from typing import Optional, Union, List, Tuple, Dict, Any
from pathlib import Path
from datetime import datetime

from .unified_config import UnifiedConfig, GenreProfile
from .config.preset_profiles import get_preset_profile
from .analysis import ContentAnalyzer, AdaptiveTargetGenerator
from .analysis.spectrum_mapper import SpectrumMapper
from .processors import apply_reference_matching
from ..dsp.unified import (
    rms, normalize, amplify, spectral_centroid, spectral_rolloff,
    zero_crossing_rate, crest_factor, tempo_estimate, adaptive_gain_calculation,
    psychoacoustic_weighting, smooth_parameter_transition,
    calculate_loudness_units, stereo_width_analysis, adjust_stereo_width
)
from ..dsp.psychoacoustic_eq import PsychoacousticEQ, EQSettings
from ..dsp.realtime_adaptive_eq import RealtimeAdaptiveEQ, create_realtime_adaptive_eq
from ..dsp.advanced_dynamics import DynamicsProcessor, DynamicsMode, create_dynamics_processor
from ..dsp.dynamics import create_brick_wall_limiter
from ..dsp.dynamics.soft_clipper import soft_clip
from ..analysis.ml_genre_classifier import MLGenreClassifier, create_ml_genre_classifier
from ..learning.preference_engine import PreferenceLearningEngine, UserAction, create_preference_engine
from ..optimization.performance_optimizer import get_performance_optimizer, optimized, cached
from ..utils.logging import debug, info
from ..io.results import Result
from .hybrid import RealtimeEQManager, DynamicsManager, PreferenceManager


class HybridProcessor:
    """
    Main hybrid processor supporting reference-based and adaptive mastering
    """

    def __init__(self, config: UnifiedConfig):
        self.config = config
        self.content_analyzer = ContentAnalyzer(config.internal_sample_rate)
        self.target_generator = AdaptiveTargetGenerator(config, self)
        self.spectrum_mapper = SpectrumMapper()  # NEW: Spectrum-based parameter calculation

        # Initialize psychoacoustic EQ
        eq_settings = EQSettings(
            sample_rate=config.internal_sample_rate,
            fft_size=config.fft_size,
            adaptation_speed=config.adaptive.adaptation_strength
        )
        self.psychoacoustic_eq = PsychoacousticEQ(eq_settings)

        # Initialize real-time adaptive EQ for streaming applications
        self.realtime_eq = create_realtime_adaptive_eq(
            sample_rate=config.internal_sample_rate,
            buffer_size=min(config.fft_size // 4, 1024),  # Smaller buffer for low latency
            target_latency_ms=20.0,
            adaptation_rate=config.adaptive.adaptation_strength
        )

        # Initialize advanced dynamics processor with automatic makeup gain
        self.dynamics_processor = create_dynamics_processor(
            mode=DynamicsMode.ADAPTIVE,
            sample_rate=config.internal_sample_rate,
            target_lufs=-14.0  # Modern mastering standard
        )
        # Enable only compressor with auto makeup gain, keep gate and limiter disabled for now
        self.dynamics_processor.settings.enable_gate = False
        self.dynamics_processor.settings.enable_compressor = True
        self.dynamics_processor.settings.enable_limiter = False

        # Initialize brick-wall limiter for final peak control
        self.brick_wall_limiter = create_brick_wall_limiter(
            threshold_db=-0.3,      # -0.3 dBFS ceiling (safe for most DACs)
            lookahead_ms=2.0,       # 2ms look-ahead for transparent limiting
            release_ms=50.0,        # 50ms release for natural sound
            sample_rate=config.internal_sample_rate
        )

        # Initialize preference learning engine
        self.preference_engine = create_preference_engine()

        # Initialize component managers
        self.realtime_eq_manager = RealtimeEQManager(self.realtime_eq)
        self.dynamics_manager = DynamicsManager(self.dynamics_processor)
        self.preference_manager = PreferenceManager(self.preference_engine)

        # Shared state (backwards compatibility)
        self.current_user_id = None  # Kept for backwards compatibility

        # Initialize performance optimizer
        self.performance_optimizer = get_performance_optimizer()
        self._optimize_processing_methods()

        # Processing state
        self.current_targets = None
        self.processing_history = []

        debug(f"Hybrid processor initialized in {config.adaptive.mode} mode with psychoacoustic EQ")

    def process(
        self,
        target: Union[str, np.ndarray],
        reference: Optional[Union[str, np.ndarray]] = None,
        results: Union[str, List[str], Result, List[Result]] = None,
        preview_target: Optional[Result] = None,
        preview_result: Optional[Result] = None
    ) -> Optional[np.ndarray]:
        """
        Main processing function supporting both reference and adaptive modes

        Args:
            target: Target audio file path or array
            reference: Reference audio file path or array (optional for adaptive mode)
            results: Output file path(s) or Result object(s)
            preview_target: Preview target result (optional)
            preview_result: Preview result output (optional)

        Returns:
            Processed audio array (if no file output specified)
        """
        info(f"Starting hybrid processing in {self.config.adaptive.mode} mode")

        # Load target audio (simplified for now - will be enhanced with unified I/O)
        if isinstance(target, str):
            target_audio = self._load_audio_placeholder(target)
        else:
            target_audio = target

        # Process based on mode
        if self.config.is_reference_mode() and reference is not None:
            return self._process_reference_mode(target_audio, reference, results)
        elif self.config.is_adaptive_mode():
            return self._process_adaptive_mode(target_audio, results)
        elif self.config.is_hybrid_mode():
            return self._process_hybrid_mode(target_audio, reference, results)
        else:
            raise ValueError(f"Invalid processing mode: {self.config.adaptive.mode}")

    def _process_reference_mode(self, target_audio: np.ndarray,
                               reference: Union[str, np.ndarray],
                               results) -> np.ndarray:
        """Process using traditional reference-based matching"""
        info("Processing in reference mode")

        # Load reference audio
        if isinstance(reference, str):
            reference_audio = self._load_audio_placeholder(reference)
        else:
            reference_audio = reference

        # Traditional Matchering-style processing
        return self._apply_reference_matching(target_audio, reference_audio)

    def _process_adaptive_mode(self, target_audio: np.ndarray, results) -> np.ndarray:
        """Process using adaptive mastering without reference"""
        info("Processing in adaptive mode")

        # Analyze content
        content_profile = self.content_analyzer.analyze_content(target_audio)

        # Generate adaptive targets
        targets = self.target_generator.generate_targets(content_profile)

        # Apply adaptive processing
        return self._apply_adaptive_processing(target_audio, targets)

    def _process_hybrid_mode(self, target_audio: np.ndarray,
                            reference: Optional[Union[str, np.ndarray]],
                            results) -> np.ndarray:
        """Process using hybrid approach combining reference and adaptive"""
        info("Processing in hybrid mode")

        # Always analyze content for hybrid mode
        content_profile = self.content_analyzer.analyze_content(target_audio)

        if reference is not None:
            # Use reference with adaptive enhancement
            if isinstance(reference, str):
                reference_audio = self._load_audio_placeholder(reference)
            else:
                reference_audio = reference

            return self._apply_hybrid_processing(target_audio, reference_audio, content_profile)
        else:
            # Fall back to pure adaptive mode
            targets = self.target_generator.generate_targets(content_profile)
            return self._apply_adaptive_processing(target_audio, targets)

    def _apply_reference_matching(self, target_audio: np.ndarray,
                                 reference_audio: np.ndarray) -> np.ndarray:
        """Apply traditional reference-based matching"""
        return apply_reference_matching(target_audio, reference_audio)

    def _apply_adaptive_processing(self, target_audio: np.ndarray,
                                  targets: Dict[str, Any]) -> np.ndarray:
        """Apply spectrum-based adaptive processing"""
        debug("Applying spectrum-based adaptive processing")

        processed_audio = target_audio.copy()

        # Analyze content first
        content_profile = self.content_analyzer.analyze_content(processed_audio)

        # Store content profile for potential user learning
        self.last_content_profile = content_profile
        self.preference_manager.set_content_profile(content_profile)

        # NEW: Analyze input level and add to content profile
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
            from ..dsp.basic import amplify
            processed_audio = amplify(processed_audio, spectrum_params.input_gain)
            debug(f"[Spectrum Gain Staging] Applied {spectrum_params.input_gain:+.2f} dB input gain")

        # Track loudness through each processing stage
        before_eq_lufs = calculate_loudness_units(processed_audio, self.config.internal_sample_rate)
        debug(f"[STAGE 1] Before EQ: {before_eq_lufs:.2f} LUFS")

        # Apply psychoacoustic EQ adjustments with content awareness
        processed_audio = self._apply_psychoacoustic_eq(processed_audio, targets, content_profile)

        after_eq_lufs = calculate_loudness_units(processed_audio, self.config.internal_sample_rate)
        peak_after_eq = np.max(np.abs(processed_audio))
        peak_after_eq_db = 20 * np.log10(peak_after_eq) if peak_after_eq > 0 else -np.inf
        print(f"[After EQ] Peak: {peak_after_eq_db:.2f} dB")
        debug(f"[STAGE 2] After EQ: {after_eq_lufs:.2f} LUFS (change: {after_eq_lufs - before_eq_lufs:+.2f} dB)")

        # SPECTRUM-AWARE DYNAMICS PROCESSING
        # Apply compression based on spectrum_params.compression_amount
        # Skip if compression_amount is 0.0 (loud+compressed material)

        # TEMPORARY: Disable complex dynamics processor, use simple DIY approach
        if False and spectrum_params.compression_amount > 0.1:
            # Create spectrum-aware dynamics settings
            from ..dsp.dynamics.settings import DynamicsSettings, CompressorSettings, LimiterSettings, DynamicsMode

            # Calculate compression parameters from spectrum
            comp_ratio = spectrum_params.compression_ratio
            comp_threshold = spectrum_params.compression_threshold
            comp_intensity = spectrum_params.compression_amount  # 0.0-1.0

            # Create compressor settings
            # GOAL: Reduce crest factor by compressing peaks
            # Strategy: Set threshold based on current RMS, compress everything above that

            # Measure current RMS to set appropriate threshold
            from ..dsp.basic import rms as calculate_rms
            current_rms = calculate_rms(processed_audio)
            current_rms_db = 20 * np.log10(current_rms) if current_rms > 0 else -np.inf

            # Set threshold slightly above current RMS
            # This way we compress the dynamic peaks while preserving average level
            adjusted_threshold = current_rms_db + 3.0  # 3 dB above RMS

            # Use higher ratio for extreme dynamics
            adjusted_ratio = max(comp_ratio, 4.0) if comp_intensity > 0.75 else comp_ratio

            compressor_settings = CompressorSettings(
                threshold_db=adjusted_threshold,
                ratio=adjusted_ratio,
                attack_ms=2.0,  # Fast attack to catch all peaks
                release_ms=50.0,  # Faster release to preserve transients
                knee_db=2.0,  # Narrow knee for focused peak control
                makeup_gain_db=0.0,  # No makeup gain
                enable_lookahead=True,
                lookahead_ms=5.0
            )

            print(f"[Compressor Setup] RMS: {current_rms_db:.2f} dB, Threshold: {adjusted_threshold:.2f} dB")

            # Create limiter settings (currently disabled)
            limiter_settings = LimiterSettings(
                threshold_db=-0.5,
                release_ms=60.0,
                lookahead_ms=5.0,
                isr_enabled=True,
                oversampling=2
            )

            # Create dynamics settings
            # GOAL: Reduce crest factor (bring peaks closer to RMS)
            # NOT: Increase RMS (that's done in final normalization)
            dynamics_settings = DynamicsSettings(
                mode=DynamicsMode.ADAPTIVE,
                sample_rate=self.config.internal_sample_rate,
                enable_gate=False,  # No gate
                enable_compressor=True,
                compressor=compressor_settings,
                enable_limiter=False,  # Limiter destroys RMS, disable for now
                limiter=limiter_settings
            )

            # Create processor instance
            from ..dsp.advanced_dynamics import DynamicsProcessor
            dynamics_proc = DynamicsProcessor(dynamics_settings)

            print(f"[Dynamics] Compression {adjusted_ratio:.1f}:1 @ {adjusted_threshold:.1f}dB, intensity {comp_intensity:.2f}")

            from ..dsp.basic import rms as calculate_rms

            # Measure before dynamics
            before_dynamics_peak = np.max(np.abs(processed_audio))
            before_dynamics_peak_db = 20 * np.log10(before_dynamics_peak) if before_dynamics_peak > 0 else -np.inf
            before_dynamics_rms = calculate_rms(processed_audio)
            before_dynamics_rms_db = 20 * np.log10(before_dynamics_rms) if before_dynamics_rms > 0 else -np.inf
            before_dynamics_crest = before_dynamics_peak_db - before_dynamics_rms_db

            # Process
            processed_audio, dynamics_info = dynamics_proc.process(processed_audio, content_profile)

            # Measure after dynamics
            after_dynamics_peak = np.max(np.abs(processed_audio))
            after_dynamics_peak_db = 20 * np.log10(after_dynamics_peak) if after_dynamics_peak > 0 else -np.inf
            after_dynamics_rms = calculate_rms(processed_audio)
            after_dynamics_rms_db = 20 * np.log10(after_dynamics_rms) if after_dynamics_rms > 0 else -np.inf
            after_dynamics_crest = after_dynamics_peak_db - after_dynamics_rms_db

            print(f"[Dynamics] Peak: {before_dynamics_peak_db:.2f} → {after_dynamics_peak_db:.2f} dB (Δ {after_dynamics_peak_db - before_dynamics_peak_db:+.2f} dB)")
            print(f"[Dynamics] RMS: {before_dynamics_rms_db:.2f} → {after_dynamics_rms_db:.2f} dB (Δ {after_dynamics_rms_db - before_dynamics_rms_db:+.2f} dB)")
            print(f"[Dynamics] Crest: {before_dynamics_crest:.2f} → {after_dynamics_crest:.2f} dB (Δ {after_dynamics_crest - before_dynamics_crest:+.2f} dB)")
        else:
            dynamics_info = {}
            print(f"[Dynamics] SKIPPED - compression_amount={spectrum_params.compression_amount:.2f} (preserving dynamics)")

        # SIMPLE DIY COMPRESSOR - Direct crest factor reduction
        # Goal: Reduce crest factor by compressing peaks
        if spectrum_params.compression_amount > 0.1:
            from ..dsp.basic import rms as calculate_rms

            # Measure current state
            before_comp_peak = np.max(np.abs(processed_audio))
            before_comp_peak_db = 20 * np.log10(before_comp_peak) if before_comp_peak > 0 else -np.inf
            before_comp_rms = calculate_rms(processed_audio)
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
            # For samples above threshold, apply compression
            audio_abs = np.abs(processed_audio)
            over_threshold = audio_abs > clip_threshold_linear

            if np.any(over_threshold):
                # Soft knee compression for samples over threshold
                # Use adaptive ratio based on compression intensity
                compression_ratio = 3.0 + spectrum_params.compression_amount * 4.0  # 3:1 to 7:1
                excess = audio_abs[over_threshold] - clip_threshold_linear
                compressed_excess = excess / compression_ratio
                new_amplitude = clip_threshold_linear + compressed_excess

                # Apply compression while preserving sign
                processed_audio[over_threshold] = np.sign(processed_audio[over_threshold]) * new_amplitude

            # Measure result
            after_comp_peak = np.max(np.abs(processed_audio))
            after_comp_peak_db = 20 * np.log10(after_comp_peak) if after_comp_peak > 0 else -np.inf
            after_comp_rms = calculate_rms(processed_audio)
            after_comp_rms_db = 20 * np.log10(after_comp_rms) if after_comp_rms > 0 else -np.inf
            after_comp_crest = after_comp_peak_db - after_comp_rms_db

            print(f"[DIY Compressor] Peak: {before_comp_peak_db:.2f} → {after_comp_peak_db:.2f} dB (Δ {after_comp_peak_db - before_comp_peak_db:+.2f} dB)")
            print(f"[DIY Compressor] RMS: {before_comp_rms_db:.2f} → {after_comp_rms_db:.2f} dB (Δ {after_comp_rms_db - before_comp_rms_db:+.2f} dB)")
            print(f"[DIY Compressor] Crest: {before_comp_crest:.2f} → {after_comp_crest:.2f} dB (Δ {after_comp_crest - before_comp_crest:+.2f} dB, target: {-target_crest_reduction:.2f} dB)")

        # SIMPLE DIY EXPANDER - Direct crest factor expansion (de-mastering)
        # Goal: Increase crest factor by expanding peaks relative to RMS
        # This restores dynamics to over-compressed material (loudness war casualties)
        if spectrum_params.expansion_amount > 0.1:
            from ..dsp.basic import rms as calculate_rms

            # Measure current state
            before_exp_peak = np.max(np.abs(processed_audio))
            before_exp_peak_db = 20 * np.log10(before_exp_peak) if before_exp_peak > 0 else -np.inf
            before_exp_rms = calculate_rms(processed_audio)
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
            audio_abs = np.abs(processed_audio)
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
                processed_audio[above_threshold] = np.sign(processed_audio[above_threshold]) * new_amplitude

            # Measure result
            after_exp_peak = np.max(np.abs(processed_audio))
            after_exp_peak_db = 20 * np.log10(after_exp_peak) if after_exp_peak > 0 else -np.inf
            after_exp_rms = calculate_rms(processed_audio)
            after_exp_rms_db = 20 * np.log10(after_exp_rms) if after_exp_rms > 0 else -np.inf
            after_exp_crest = after_exp_peak_db - after_exp_rms_db

            print(f"[DIY Expander] Peak: {before_exp_peak_db:.2f} → {after_exp_peak_db:.2f} dB (Δ {after_exp_peak_db - before_exp_peak_db:+.2f} dB)")
            print(f"[DIY Expander] RMS: {before_exp_rms_db:.2f} → {after_exp_rms_db:.2f} dB (Δ {after_exp_rms_db - before_exp_rms_db:+.2f} dB)")
            print(f"[DIY Expander] Crest: {before_exp_crest:.2f} → {after_exp_crest:.2f} dB (Δ {after_exp_crest - before_exp_crest:+.2f} dB, target: +{target_crest_expansion:.2f} dB)")

        # Apply stereo width adjustment
        if processed_audio.ndim == 2 and processed_audio.shape[1] == 2:
            peak_before_stereo = np.max(np.abs(processed_audio))
            peak_before_stereo_db = 20 * np.log10(peak_before_stereo) if peak_before_stereo > 0 else -np.inf

            current_width = stereo_width_analysis(processed_audio)
            target_width = targets["stereo_width"]

            # CRITICAL: Prevent stereo width expansion from creating excessive peaks
            # Strategy 1: Limit expansion for already-loud material
            if spectrum_position.input_level > 0.8 and target_width > current_width:
                max_width_increase = 0.3  # Only allow +0.3 increase
                target_width = min(target_width, current_width + max_width_increase)
                print(f"[Stereo Width] Limited expansion for loud material: target reduced to {target_width:.2f}")

            # Strategy 2: Skip expansion if current peak is already high (> 3 dB)
            # This prevents stereo expansion from undoing dynamics work
            if peak_before_stereo_db > 3.0 and target_width > current_width:
                print(f"[Stereo Width] SKIPPED expansion due to high peak ({peak_before_stereo_db:.2f} dB) - preserving dynamics")
                target_width = current_width  # Keep current width

            if abs(current_width - target_width) > 0.1:
                processed_audio = adjust_stereo_width(processed_audio, target_width)

                peak_after_stereo = np.max(np.abs(processed_audio))
                peak_after_stereo_db = 20 * np.log10(peak_after_stereo) if peak_after_stereo > 0 else -np.inf
                print(f"[Stereo Width] Peak: {peak_before_stereo_db:.2f} → {peak_after_stereo_db:.2f} dB (width: {current_width:.2f} → {target_width:.2f})")

        # Store dynamics info for monitoring
        if hasattr(self, 'last_dynamics_info'):
            self.last_dynamics_info = dynamics_info

        # SPECTRUM-BASED FINAL NORMALIZATION
        # Strategy: Balance RMS target with peak limit constraint
        # We can't have both high RMS AND low peak - they're linked by crest factor

        from ..dsp.basic import rms as calculate_rms

        peak = np.max(np.abs(processed_audio))
        peak_db = 20 * np.log10(peak) if peak > 0 else -np.inf
        current_rms = calculate_rms(processed_audio)
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

            from ..dsp.basic import amplify
            processed_audio = amplify(processed_audio, rms_boost)
            print(f"[RMS Boost] Applied {rms_boost:+.2f} dB (target: {target_rms_db:.1f} dB)")

            # Recalculate after boost
            peak = np.max(np.abs(processed_audio))
            peak_db = 20 * np.log10(peak) if peak > 0 else -np.inf
            current_rms = calculate_rms(processed_audio)
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
            processed_audio = processed_audio * (target_peak / peak)
            print(f"[Peak Normalization] {peak_db:.2f} → {target_peak_db:.2f} dB (change: {peak_change_db:+.2f} dB)")

            # Recalculate final metrics
            current_rms = calculate_rms(processed_audio)
            current_rms_db = 20 * np.log10(current_rms) if current_rms > 0 else -np.inf
            peak = np.max(np.abs(processed_audio))
            peak_db = 20 * np.log10(peak) if peak > 0 else -np.inf
            current_crest = peak_db - current_rms_db

            print(f"[Final] Peak: {peak_db:.2f} dB, RMS: {current_rms_db:.2f} dB, Crest: {current_crest:.2f} dB")

        # Safety limiter (only if exceeds safety threshold)
        safety_threshold = -0.01  # dBFS
        final_peak = np.max(np.abs(processed_audio))
        final_peak_db = 20 * np.log10(final_peak) if final_peak > 0 else -np.inf

        if final_peak_db > safety_threshold:
            print(f"[Safety Limiter] Peak {final_peak_db:.2f} dB exceeds threshold {safety_threshold:.2f} dB")
            # Apply gentle soft clipping to prevent hard clipping
            processed_audio = soft_clip(processed_audio, threshold=0.99)
            final_peak = np.max(np.abs(processed_audio))
            final_peak_db = 20 * np.log10(final_peak) if final_peak > 0 else -np.inf
            print(f"[Safety Limiter] Peak reduced to {final_peak_db:.2f} dB")

        # Final metrics
        final_rms = calculate_rms(processed_audio)
        final_rms_db = 20 * np.log10(final_rms) if final_rms > 0 else -np.inf
        final_crest = final_peak_db - final_rms_db

        debug(f"[Final Result] Peak: {final_peak_db:.2f} dB, RMS: {final_rms_db:.2f} dB, Crest: {final_crest:.2f} dB")

        return processed_audio

    def _apply_hybrid_processing(self, target_audio: np.ndarray,
                                reference_audio: np.ndarray,
                                content_profile: Dict[str, Any]) -> np.ndarray:
        """Apply hybrid processing combining reference and adaptive approaches"""
        debug("Applying hybrid processing")

        # Start with reference matching
        reference_matched = self._apply_reference_matching(target_audio, reference_audio)

        # Generate adaptive targets
        targets = self.target_generator.generate_targets(content_profile)

        # Apply adaptive enhancements with reduced intensity
        adaptation_strength = self.config.adaptive.adaptation_strength * 0.5  # Reduced for hybrid

        # Blend reference matching with adaptive processing
        adaptive_processed = self._apply_adaptive_processing(target_audio, targets)

        # Blend the two results
        blended_audio = (reference_matched * (1 - adaptation_strength) +
                        adaptive_processed * adaptation_strength)

        # Normalize to -0.1 dB peak (matching Matchering behavior)
        return normalize(blended_audio, 0.9886)

    def _apply_psychoacoustic_eq(self, audio: np.ndarray, targets: Dict[str, Any],
                                content_profile: Optional[Dict[str, Any]] = None) -> np.ndarray:
        """Apply psychoacoustic EQ adjustments based on adaptive targets and content analysis"""
        debug("Applying psychoacoustic EQ processing")

        try:
            # Create EQ curve from targets and content analysis
            eq_curve = self._targets_to_eq_curve(targets, content_profile)

            # Apply psychoacoustic EQ using real-time processing
            processed = self._process_with_psychoacoustic_eq(audio, eq_curve, content_profile)

            debug("Psychoacoustic EQ processing completed successfully")
            return processed

        except Exception as e:
            debug(f"Psychoacoustic EQ failed, falling back to simple EQ: {e}")
            return self._apply_simple_eq_fallback(audio, targets)

    def _targets_to_eq_curve(self, targets: Dict[str, Any],
                            content_profile: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """Convert adaptive targets to EQ curve parameters with content awareness"""
        # Base EQ curve from targets
        eq_curve = {
            # Bass frequencies (20-250 Hz)
            'bass_boost': targets.get("bass_boost_db", 0.0),

            # Low-midrange (250-500 Hz) - Use preset-specific if available
            'low_mid_boost': targets.get("preset_low_mid_gain", targets.get("bass_boost_db", 0.0) * 0.5),

            # Midrange (500-2000 Hz)
            'mid_boost': targets.get("midrange_clarity_db", 0.0),

            # High-midrange (2000-4000 Hz) - Use preset-specific if available
            'high_mid_boost': targets.get("preset_high_mid_gain", targets.get("midrange_clarity_db", 0.0) * 0.7),

            # Treble (4000+ Hz)
            'treble_boost': targets.get("treble_enhancement_db", 0.0),

            # Overall intensity
            'mastering_intensity': targets.get("mastering_intensity", 0.5)
        }

        # Apply content-aware adjustments
        if content_profile:
            # Adjust based on spectral characteristics
            centroid = content_profile.get("spectral_centroid", 2000)
            if centroid > 3500:  # Very bright content
                eq_curve['treble_boost'] *= 0.7  # Reduce treble boost
                eq_curve['high_mid_boost'] *= 0.8
            elif centroid < 1000:  # Very dark content
                eq_curve['treble_boost'] *= 1.3  # Increase treble boost
                eq_curve['mid_boost'] *= 1.2

            # Adjust based on genre
            genre_info = content_profile.get("genre_info", {})
            primary_genre = genre_info.get("primary", "pop")

            if primary_genre == "electronic":
                eq_curve['bass_boost'] *= 1.2
                eq_curve['treble_boost'] *= 1.1
            elif primary_genre == "classical":
                eq_curve['bass_boost'] *= 0.8
                eq_curve['mid_boost'] *= 1.2
            elif primary_genre == "rock":
                eq_curve['mid_boost'] *= 1.3
                eq_curve['high_mid_boost'] *= 1.2

            # Adjust based on dynamic range
            dynamic_range = content_profile.get("dynamic_range", 20)
            if dynamic_range > 25:  # High dynamic range - be gentler
                for key in eq_curve:
                    if key != 'mastering_intensity':
                        eq_curve[key] *= 0.8
            elif dynamic_range < 10:  # Low dynamic range - be more aggressive
                for key in eq_curve:
                    if key != 'mastering_intensity':
                        eq_curve[key] *= 1.2

        return eq_curve

    def _process_with_psychoacoustic_eq(self, audio: np.ndarray, eq_curve: Dict[str, float],
                                       content_profile: Optional[Dict[str, Any]] = None) -> np.ndarray:
        """Process audio using psychoacoustic EQ with content awareness"""

        # Convert EQ curve dict to target curve array
        target_curve = self._eq_curve_to_array(eq_curve)

        # Process audio in chunks for psychoacoustic EQ
        chunk_size = self.psychoacoustic_eq.fft_size
        processed_audio = np.zeros_like(audio)

        for i in range(0, len(audio), chunk_size // 2):  # 50% overlap
            end_idx = min(i + chunk_size, len(audio))
            chunk = audio[i:end_idx]

            # Pad chunk if necessary
            if len(chunk) < chunk_size:
                padded_chunk = np.zeros((chunk_size,) + chunk.shape[1:])
                padded_chunk[:len(chunk)] = chunk
                chunk = padded_chunk

            # Process chunk with psychoacoustic EQ
            processed_chunk = self.psychoacoustic_eq.process_realtime_chunk(
                chunk, target_curve, content_profile
            )

            # Extract only the valid part (remove padding)
            valid_length = end_idx - i
            if audio.ndim == 2:
                processed_audio[i:end_idx] = processed_chunk[:valid_length]
            else:
                processed_audio[i:end_idx] = processed_chunk[:valid_length]

        return processed_audio

    def process_realtime_chunk(self, audio_chunk: np.ndarray,
                              content_info: Optional[Dict[str, Any]] = None) -> np.ndarray:
        """
        Process audio chunk in real-time for streaming applications

        Args:
            audio_chunk: Small audio chunk for real-time processing
            content_info: Optional pre-analyzed content information

        Returns:
            Processed audio chunk with minimal latency
        """
        debug("Processing real-time audio chunk")

        try:
            # If no content info provided, do quick analysis
            if content_info is None:
                # Quick content analysis for real-time (simplified)
                content_info = self._quick_content_analysis(audio_chunk)

            # Use real-time adaptive EQ
            processed_chunk = self.realtime_eq.process_realtime(audio_chunk, content_info)

            # Apply dynamics processing for real-time
            processed_chunk, dynamics_info = self.dynamics_processor.process(
                processed_chunk, content_info
            )

            return processed_chunk

        except Exception as e:
            debug(f"Real-time processing failed: {e}")
            return audio_chunk  # Return unprocessed on error

    def _quick_content_analysis(self, audio_chunk: np.ndarray) -> Dict[str, Any]:
        """Quick content analysis for real-time processing"""

        # Basic analysis with minimal computation
        if audio_chunk.ndim == 2:
            mono_audio = np.mean(audio_chunk, axis=1)
        else:
            mono_audio = audio_chunk

        # Quick feature extraction
        rms_val = np.sqrt(np.mean(mono_audio ** 2))
        peak_val = np.max(np.abs(mono_audio))

        # Simple energy level classification
        if rms_val > 0.3:
            energy_level = "high"
        elif rms_val > 0.1:
            energy_level = "medium"
        else:
            energy_level = "low"

        # Quick spectral centroid (simplified)
        if len(mono_audio) >= 512:
            spectrum = np.fft.fft(mono_audio[:512])
            magnitude = np.abs(spectrum[:257])
            freqs = np.fft.fftfreq(512, 1/self.config.internal_sample_rate)[:257]
            centroid = np.sum(freqs * magnitude) / (np.sum(magnitude) + 1e-10)
        else:
            centroid = 1000  # Default

        # Default genre (would use cached from previous full analysis)
        genre_info = {
            "primary": "pop",  # Safe default
            "confidence": 0.5
        }

        return {
            "rms": float(rms_val),
            "peak": float(peak_val),
            "energy_level": energy_level,
            "spectral_centroid": float(centroid),
            "genre_info": genre_info,
            "dynamic_range": 15.0  # Default estimate
        }

    def _eq_curve_to_array(self, eq_curve: Dict[str, float]) -> np.ndarray:
        """Convert EQ curve dictionary to array format expected by psychoacoustic EQ"""
        # Create target curve for 26 critical bands
        num_bands = len(self.psychoacoustic_eq.critical_bands)
        target_curve = np.zeros(num_bands)

        # Map frequency ranges to bands
        bass_bands = range(0, 4)        # ~20-250 Hz
        low_mid_bands = range(4, 8)     # ~250-500 Hz
        mid_bands = range(8, 16)        # ~500-2000 Hz
        high_mid_bands = range(16, 20)  # ~2000-4000 Hz
        treble_bands = range(20, 26)    # ~4000+ Hz

        # Apply gains to appropriate bands
        for band_idx in bass_bands:
            target_curve[band_idx] = eq_curve.get('bass_boost', 0.0)

        for band_idx in low_mid_bands:
            target_curve[band_idx] = eq_curve.get('low_mid_boost', 0.0)

        for band_idx in mid_bands:
            target_curve[band_idx] = eq_curve.get('mid_boost', 0.0)

        for band_idx in high_mid_bands:
            target_curve[band_idx] = eq_curve.get('high_mid_boost', 0.0)

        for band_idx in treble_bands:
            target_curve[band_idx] = eq_curve.get('treble_boost', 0.0)

        # Apply mastering intensity scaling
        intensity = eq_curve.get('mastering_intensity', 0.5)
        target_curve *= intensity

        return target_curve

    def _apply_simple_eq_fallback(self, audio: np.ndarray, targets: Dict[str, Any]) -> np.ndarray:
        """Fallback simple EQ implementation for safety"""
        processed = audio.copy()

        # Very basic frequency adjustment using simple filtering
        bass_gain_db = targets.get("bass_boost_db", 0.0)
        treble_gain_db = targets.get("treble_enhancement_db", 0.0)

        # Apply very gentle adjustments (limited for safety)
        if abs(bass_gain_db) > 0.5:
            bass_gain_linear = 10 ** (np.clip(bass_gain_db, -6, 6) / 20)
            processed = processed * (1.0 + (bass_gain_linear - 1.0) * 0.1)

        if abs(treble_gain_db) > 0.5:
            treble_gain_linear = 10 ** (np.clip(treble_gain_db, -6, 6) / 20)
            processed = processed * (1.0 + (treble_gain_linear - 1.0) * 0.1)

        return processed

    def _load_audio_placeholder(self, file_path: str) -> np.ndarray:
        """Placeholder for audio loading - will be replaced with unified I/O"""
        # This is a placeholder - will be replaced with proper audio loading
        debug(f"Loading audio file: {file_path}")
        # For now, return dummy audio data
        return np.random.randn(44100 * 5, 2) * 0.1  # 5 seconds of dummy stereo audio

    def get_realtime_eq_info(self) -> Dict[str, Any]:
        """Get real-time EQ status and performance information"""
        return self.realtime_eq_manager.get_info()

    def set_realtime_eq_parameters(self, **kwargs):
        """Update real-time EQ parameters dynamically"""
        self.realtime_eq_manager.set_parameters(**kwargs)

    def reset_realtime_eq(self):
        """Reset real-time EQ state"""
        self.realtime_eq_manager.reset()

    def get_dynamics_info(self) -> Dict[str, Any]:
        """Get dynamics processing information"""
        return self.dynamics_manager.get_info()

    def set_dynamics_mode(self, mode: str):
        """Set dynamics processing mode"""
        self.dynamics_manager.set_mode(mode)

    def reset_dynamics(self):
        """Reset dynamics processing state"""
        self.dynamics_manager.reset()

    def set_user(self, user_id: str):
        """Set the current user for preference learning"""
        self.current_user_id = user_id
        self.preference_manager.set_user(user_id)

    def record_user_feedback(self, rating: float,
                           parameters_before: Optional[Dict[str, float]] = None,
                           parameters_after: Optional[Dict[str, float]] = None):
        """Record user feedback for learning"""
        self.preference_manager.record_feedback(rating, parameters_before, parameters_after)

    def record_parameter_adjustment(self, parameter_name: str,
                                  old_value: float, new_value: float):
        """Record user parameter adjustment for learning"""
        self.preference_manager.record_adjustment(parameter_name, old_value, new_value)

    def get_user_insights(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get user preference insights"""
        return self.preference_manager.get_insights(user_id)

    def save_user_preferences(self, user_id: Optional[str] = None) -> bool:
        """Save user preferences to storage"""
        return self.preference_manager.save_preferences(user_id)

    def _optimize_processing_methods(self):
        """Apply performance optimizations to processing methods"""
        # Optimize critical processing methods
        self._apply_adaptive_processing = self.performance_optimizer.optimize_real_time_processing(
            self._apply_adaptive_processing
        )
        self.process_realtime_chunk = self.performance_optimizer.optimize_real_time_processing(
            self.process_realtime_chunk
        )

        # Add caching to content analysis for similar audio
        self.content_analyzer.analyze_content = self.performance_optimizer.cached_function(
            "content_analysis"
        )(self.content_analyzer.analyze_content)

        info("Performance optimizations applied to processing methods")

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance optimization statistics"""
        return self.performance_optimizer.get_optimization_stats()

    def get_processing_info(self) -> Dict[str, Any]:
        """Get information about current processing configuration"""
        return {
            "mode": self.config.adaptive.mode,
            "sample_rate": self.config.internal_sample_rate,
            "fft_size": self.config.fft_size,
            "adaptation_strength": self.config.adaptive.adaptation_strength,
            "enable_genre_detection": self.config.adaptive.enable_genre_detection,
            "available_genres": list(self.config.genre_profiles.keys()),
            "current_targets": self.current_targets
        }

    def set_processing_mode(self, mode: str):
        """Change processing mode"""
        if mode in ["reference", "adaptive", "hybrid"]:
            self.config.set_processing_mode(mode)
            debug(f"Processing mode changed to: {mode}")
        else:
            raise ValueError(f"Invalid processing mode: {mode}")


# Convenience functions for quick processing
def process_adaptive(target: Union[str, np.ndarray],
                    config: Optional[UnifiedConfig] = None) -> np.ndarray:
    """Quick adaptive processing function"""
    if config is None:
        config = UnifiedConfig()
        config.set_processing_mode("adaptive")

    processor = HybridProcessor(config)
    return processor.process(target)


def process_reference(target: Union[str, np.ndarray],
                     reference: Union[str, np.ndarray],
                     config: Optional[UnifiedConfig] = None) -> np.ndarray:
    """Quick reference-based processing function"""
    if config is None:
        config = UnifiedConfig()
        config.set_processing_mode("reference")

    processor = HybridProcessor(config)
    return processor.process(target, reference)


def process_hybrid(target: Union[str, np.ndarray],
                  reference: Optional[Union[str, np.ndarray]] = None,
                  config: Optional[UnifiedConfig] = None) -> np.ndarray:
    """Quick hybrid processing function"""
    if config is None:
        config = UnifiedConfig()
        config.set_processing_mode("hybrid")

    processor = HybridProcessor(config)
    return processor.process(target, reference)