# -*- coding: utf-8 -*-

"""
Continuous Space Processing Mode
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Processing mode using continuous parameter space instead of discrete presets.
Generates optimal parameters from audio fingerprints.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict, Any, Optional
from ...dsp.basic import rms, amplify
from ...dsp.unified import (
    calculate_loudness_units, stereo_width_analysis, adjust_stereo_width
)
from ...utils.logging import debug
from .continuous_space import ProcessingSpaceMapper, PreferenceVector, ProcessingParameters
from .parameter_generator import ContinuousParameterGenerator
from .base_processing_mode import (
    CompressionStrategies, ExpansionStrategies,
    DBConversion, StereoWidthProcessor, ProcessingLogger,
    SafetyLimiter, NormalizationStep
)
from ..recording_type_detector import RecordingTypeDetector


class ContinuousMode:
    """
    Continuous space processing mode - intelligent mastering using fingerprints.

    Instead of discrete presets, this mode maps the audio's 25D fingerprint
    to a continuous 3D processing space and generates optimal parameters
    for that specific position.
    """

    def __init__(self, config: Any, content_analyzer: Any, fingerprint_analyzer: Any, recording_type_detector: Optional[Any] = None) -> None:
        """
        Initialize continuous space processor.

        Args:
            config: UnifiedConfig instance
            content_analyzer: ContentAnalyzer for audio analysis
            fingerprint_analyzer: AudioFingerprintAnalyzer for 25D fingerprints
            recording_type_detector: Optional RecordingTypeDetector instance (shared from parent)
        """
        self.config = config
        self.content_analyzer = content_analyzer
        self.fingerprint_analyzer = fingerprint_analyzer

        # Initialize continuous space components
        self.space_mapper = ProcessingSpaceMapper()
        self.param_generator = ContinuousParameterGenerator()

        # Use provided detector or create a new one (for backwards compatibility)
        if recording_type_detector is not None:
            self.recording_type_detector = recording_type_detector
        else:
            # Fallback for backwards compatibility (when called without detector)
            self.recording_type_detector = RecordingTypeDetector()  # type: ignore[no-untyped-call]

        # Store last fingerprint and parameters for debugging/learning
        self.last_fingerprint = None
        self.last_coordinates = None
        self.last_parameters = None
        self.last_recording_type = None
        self.last_adaptive_params = None

    def _convert_targets_to_parameters(self, targets: Dict[str, Any]) -> ProcessingParameters:
        """
        Convert dict-based mastering targets to ProcessingParameters object.

        This bridges the gap between chunked processor's dict format and
        continuous mode's ProcessingParameters dataclass.

        Args:
            targets: Dict with keys: target_lufs, target_crest_db, eq_adjustments_db, compression

        Returns:
            ProcessingParameters object
        """
        # Build EQ curve from adjustments
        eq_adjustments = targets.get('eq_adjustments_db', {})
        eq_curve = {
            'low_shelf_gain': eq_adjustments.get('sub_bass', 0.0) + eq_adjustments.get('bass', 0.0),
            'low_mid_gain': eq_adjustments.get('low_mid', 0.0),
            'mid_gain': eq_adjustments.get('mid', 0.0),
            'high_mid_gain': eq_adjustments.get('upper_mid', 0.0),
            'high_shelf_gain': eq_adjustments.get('presence', 0.0) + eq_adjustments.get('air', 0.0),
        }

        # Build compression parameters
        compression = targets.get('compression', {})
        compression_params = {
            'threshold_db': -20.0,  # Default
            'ratio': compression.get('ratio', 2.5),
            'attack_ms': 10.0,
            'release_ms': 100.0,
            'knee_db': 6.0,
            'makeup_db': 0.0,
            'amount': compression.get('amount', 0.6)  # Compression amount/strength
        }

        # Build expansion parameters (de-mastering)
        expansion_params = {
            'threshold_db': -30.0,
            'ratio': 1.5,
            'attack_ms': 5.0,
            'release_ms': 50.0,
            'amount': 0.0  # Disabled by default
        }

        # Build limiter parameters
        limiter_params = {
            'threshold_db': -1.0,
            'attack_ms': 1.0,
            'release_ms': 100.0
        }

        return ProcessingParameters(
            target_lufs=targets.get('target_lufs', -14.0),
            peak_target_db=-1.0,  # Standard peak target
            eq_curve=eq_curve,
            eq_blend=0.7,  # Default blend
            compression_params=compression_params,
            expansion_params=expansion_params,
            dynamics_blend=compression.get('amount', 0.6),
            limiter_params=limiter_params,
            stereo_width_target=1.0  # Default: preserve width
        )

    def process(self, target_audio: np.ndarray, eq_processor: Any,
                fixed_params: Optional[Dict[str, Any]] = None) -> np.ndarray:
        """
        Process audio using continuous parameter space.

        Args:
            target_audio: Input audio array
            eq_processor: EQ processor instance for psychoacoustic EQ
            fixed_params: (Beta.9) Pre-computed parameters from .25d file.
                         If provided, skips fingerprint extraction (8x faster).

        Returns:
            Processed audio array
        """
        debug("Applying continuous space processing")

        processed_audio = target_audio.copy()

        # NEW (Beta.9): Use fixed parameters if provided (from .25d file)
        if fixed_params is not None:
            debug("⚡ Using fixed parameters from .25d file (fast path)")
            # Convert dict targets to ProcessingParameters object
            params = self._convert_targets_to_parameters(fixed_params)
            self.last_parameters = params
            # Note: last_fingerprint and last_coordinates remain from first extraction
        else:
            # Step 1: Extract 25D fingerprint
            fingerprint = self.fingerprint_analyzer.analyze(
                processed_audio,
                self.config.internal_sample_rate
            )
            self.last_fingerprint = fingerprint

            print(f"[Continuous Space] Fingerprint extracted:")
            print(f"  Bass: {fingerprint['bass_pct']:.1f}%, Crest: {fingerprint['crest_db']:.1f} dB, LUFS: {fingerprint['lufs']:.1f}")

            # Step 1b: Detect recording type from fingerprint (NEW - Phase 5)
            recording_type, adaptive_params = self.recording_type_detector.detect(
                processed_audio,
                self.config.internal_sample_rate
            )
            self.last_recording_type = recording_type
            self.last_adaptive_params = adaptive_params

            print(f"[Recording Type Detector] Detected: {recording_type.value} (confidence: {adaptive_params.confidence:.1%})")
            print(f"[Recording Type Detector] Philosophy: {adaptive_params.mastering_philosophy}")
            print(f"[Recording Type Detector] Bass: {adaptive_params.bass_adjustment_db:+.2f} dB, Treble: {adaptive_params.treble_adjustment_db:+.2f} dB")

            # Step 2: Map to 3D processing space
            coords = self.space_mapper.map_fingerprint_to_space(fingerprint)
            self.last_coordinates = coords

            print(f"[Continuous Space] Coordinates: {coords}")

            # Step 3: Get user preference (from preset if using legacy mode)
            preset_name = self.config.mastering_profile or 'adaptive'
            preference = PreferenceVector.from_preset_name(preset_name)

            print(f"[Continuous Space] Preference: {preference}")

            # Step 4: Generate processing parameters
            params = self.param_generator.generate_parameters(coords, preference)
            self.last_parameters = params

            print(f"[Continuous Space] Parameters: {params}")

        # Step 5: Apply processing stages with generated parameters

        # 5a. Apply input gain if needed
        if hasattr(params, 'input_gain') and abs(params.input_gain or 0) > 0.5:
            processed_audio = amplify(processed_audio, params.input_gain)
            debug(f"[Continuous Space] Applied input gain: {params.input_gain:+.2f} dB")

        # 5b. Apply psychoacoustic EQ with generated curve
        processed_audio = self._apply_eq(processed_audio, eq_processor, params)

        # 5c. Apply dynamics processing (compression or expansion)
        processed_audio = self._apply_dynamics(processed_audio, params)

        # 5d. Apply stereo width adjustment
        processed_audio = self._apply_stereo_width(processed_audio, params)

        # 5e. Apply final normalization to target LUFS and peak
        processed_audio = self._apply_final_normalization(processed_audio, params)

        return processed_audio

    def _apply_eq(self, audio: np.ndarray, eq_processor: Any, params: Any) -> np.ndarray:
        """Apply EQ using generated parameters with adaptive guidance"""

        eq_curve = params.eq_curve

        # Apply adaptive guidance if recording type was detected
        if self.last_adaptive_params is not None:
            adaptive_params = self.last_adaptive_params

            # Blend adaptive guidance with continuous space curve
            # Higher confidence = more aggressive adaptive guidance
            adaptive_blend = min(adaptive_params.confidence, 0.7)  # Cap at 70% influence

            # Apply adaptive bass adjustment
            eq_curve['low_shelf_gain'] = (
                eq_curve['low_shelf_gain'] * (1 - adaptive_blend) +
                adaptive_params.bass_adjustment_db * adaptive_blend
            )

            # Apply adaptive mid adjustment
            eq_curve['low_mid_gain'] = (
                eq_curve['low_mid_gain'] * (1 - adaptive_blend) +
                adaptive_params.mid_adjustment_db * adaptive_blend
            )

            # Apply adaptive treble adjustment
            eq_curve['high_shelf_gain'] = (
                eq_curve['high_shelf_gain'] * (1 - adaptive_blend) +
                adaptive_params.treble_adjustment_db * adaptive_blend
            )

            debug(f"[EQ] Applied adaptive guidance (blend={adaptive_blend:.1%}): "
                  f"Bass {adaptive_params.bass_adjustment_db:+.2f} dB, "
                  f"Mid {adaptive_params.mid_adjustment_db:+.2f} dB, "
                  f"Treble {adaptive_params.treble_adjustment_db:+.2f} dB")

        # Create targets dict for EQ processor (compatible with existing API)
        targets = {
            'low_shelf_gain_db': eq_curve['low_shelf_gain'],
            'low_mid_gain_db': eq_curve['low_mid_gain'],
            'mid_gain_db': eq_curve['mid_gain'],
            'high_mid_gain_db': eq_curve['high_mid_gain'],
            'high_shelf_gain_db': eq_curve['high_shelf_gain'],
            'eq_blend': params.eq_blend,
        }

        # Create content profile with fingerprint
        content_profile = {'fingerprint': self.last_fingerprint}

        # Apply EQ
        audio = eq_processor.apply_psychoacoustic_eq(audio, targets, content_profile)

        print(f"[EQ] Applied curve with blend {params.eq_blend:.2f}: "
              f"bass {eq_curve['low_shelf_gain']:+.1f} dB, "
              f"mid {eq_curve['low_mid_gain']:+.1f} dB, "
              f"air {eq_curve['high_shelf_gain']:+.1f} dB")

        return audio

    def _apply_dynamics(self, audio: np.ndarray, params: Any) -> np.ndarray:
        """Apply dynamics processing with adaptive guidance"""

        # Adjust compression parameters based on adaptive guidance
        compression_params = params.compression_params.copy()
        expansion_params = params.expansion_params.copy()

        if self.last_adaptive_params is not None:
            adaptive_params = self.last_adaptive_params

            # Use adaptive confidence to scale compression amount
            # Higher confidence in recording type = more aggressive compression tuning
            adaptive_strength = adaptive_params.confidence

            # Adjust compression ratio and amount based on recording type philosophy
            if adaptive_params.mastering_philosophy == "correct":
                # Bootleg: More aggressive compression to tame dynamics
                compression_params['ratio'] = min(
                    compression_params['ratio'] * (1 + adaptive_strength * 0.3),
                    4.0  # Cap at 4:1
                )
                compression_params['amount'] = min(
                    compression_params['amount'] * (1 + adaptive_strength * 0.2),
                    0.9  # Cap at 90%
                )
                debug(f"[Dynamics] Bootleg correction: ratio {compression_params['ratio']:.2f}:1, "
                      f"amount {compression_params['amount']:.0%}")

            elif adaptive_params.mastering_philosophy == "punch":
                # Metal: Controlled compression for punch (not over-compressed)
                compression_params['ratio'] = max(
                    compression_params['ratio'] * (1 - adaptive_strength * 0.1),
                    1.5  # Minimum 1.5:1
                )
                # Keep amount moderate for metal
                debug(f"[Dynamics] Metal punch: ratio {compression_params['ratio']:.2f}:1, "
                      f"amount {compression_params['amount']:.0%}")

            elif adaptive_params.mastering_philosophy == "enhance":
                # Studio: Subtle compression, preserve dynamics
                compression_params['ratio'] = max(
                    compression_params['ratio'] * (1 - adaptive_strength * 0.2),
                    1.2  # Minimum 1.2:1
                )
                compression_params['amount'] = max(
                    compression_params['amount'] * (1 - adaptive_strength * 0.3),
                    0.1  # Minimum 10%
                )
                debug(f"[Dynamics] Studio enhancement: ratio {compression_params['ratio']:.2f}:1, "
                      f"amount {compression_params['amount']:.0%}")

        # Apply Compression
        if compression_params['amount'] > 0.1:
            audio = self._apply_compression(audio, compression_params)

        # Apply Expansion (de-mastering) if needed
        if expansion_params['amount'] > 0.1:
            audio = self._apply_expansion(audio, expansion_params)

        return audio

    def _apply_compression(self, audio: np.ndarray, comp_params: Dict[str, Any]) -> np.ndarray:
        """Apply simple compression to reduce crest factor"""

        # Validate input - handle empty or very short audio gracefully
        if len(audio) == 0:
            return audio  # Return as-is if empty

        return CompressionStrategies.apply_clip_blend_compression(audio, comp_params)

    def _apply_expansion(self, audio: np.ndarray, exp_params: Dict[str, Any]) -> np.ndarray:
        """Apply expansion to increase crest factor (de-mastering)"""
        return ExpansionStrategies.apply_rms_reduction_expansion(audio, exp_params)

    def _apply_stereo_width(self, audio: np.ndarray, params: Any) -> np.ndarray:
        """Apply stereo width adjustment with adaptive guidance"""

        # Only process stereo audio
        if not StereoWidthProcessor.validate_stereo(audio):
            return audio

        # Get current and target width
        current_width = stereo_width_analysis(audio)
        target_width = params.stereo_width_target

        # Apply adaptive guidance if recording type was detected
        if self.last_adaptive_params is not None:
            adaptive_params = self.last_adaptive_params

            # Use adaptive stereo strategy to modulate target
            # Each philosophy has different stereo treatment approach
            if adaptive_params.stereo_strategy == "narrow":
                # Narrow: Reduce stereo width (metal recordings, mono sources)
                target_width = current_width * (
                    1 - adaptive_params.confidence * (1 - adaptive_params.stereo_width_target)
                )
                debug(f"[Stereo Width] Narrowing strategy: {current_width:.2f} → "
                      f"{target_width:.2f} (confidence {adaptive_params.confidence:.0%})")

            elif adaptive_params.stereo_strategy == "expand":
                # Expand: Increase stereo width (bootleg concert recordings)
                target_width = current_width + (
                    (adaptive_params.stereo_width_target - current_width) *
                    adaptive_params.confidence
                )
                debug(f"[Stereo Width] Expansion strategy: {current_width:.2f} → "
                      f"{target_width:.2f} (confidence {adaptive_params.confidence:.0%})")

            elif adaptive_params.stereo_strategy == "maintain":
                # Maintain: Keep current width close to reference
                target_width = adaptive_params.stereo_width_target

        # Only adjust if significant difference
        if abs(target_width - current_width) > 0.05:
            # Check peak levels before expansion (safety)
            pre_peak_db = StereoWidthProcessor.get_peak_db(audio)

            # Skip expansion if already close to clipping
            if pre_peak_db > -2.0 and target_width > current_width:
                print(f"[Stereo Width] SKIPPED expansion due to high peak ({pre_peak_db:.2f} dB)")
                return audio

            audio = adjust_stereo_width(audio, target_width)
            post_width = stereo_width_analysis(audio)
            print(f"[Stereo Width] {current_width:.2f} → {post_width:.2f} (target: {target_width:.2f})")

        return audio

    def _apply_final_normalization(self, audio: np.ndarray, params: Any) -> np.ndarray:
        """Apply final loudness and peak normalization using unified pipeline"""

        # Step 1: RMS-based normalization (to target loudness)
        # Use RMS instead of LUFS because LUFS measurement can be unreliable after EQ processing
        from ...dsp.basic import rms as calculate_rms

        current_rms = calculate_rms(np.mean(audio, axis=1) if audio.ndim == 2 else audio)
        current_rms_db = DBConversion.to_db(current_rms)

        # Use LUFS target directly as RMS target
        # Both measure loudness but with different frequency weighting
        # The key is to respect the target and not apply excessive gain
        target_rms_db = params.target_lufs
        rms_adjustment = target_rms_db - current_rms_db

        if abs(rms_adjustment) > 0.5:
            audio = amplify(audio, rms_adjustment)
            new_rms = calculate_rms(np.mean(audio, axis=1) if audio.ndim == 2 else audio)
            new_rms_db = DBConversion.to_db(new_rms)
            debug(f"[RMS Normalization] {current_rms_db:.1f} → {new_rms_db:.1f} dB ({rms_adjustment:+.1f} dB)")

        # Step 2: Peak normalization (DISABLED - use LUFS normalization instead)
        # Peak normalization can cause excessive gain when EQ processing has
        # changed the peak-to-RMS relationship. LUFS normalization is more
        # perceptually meaningful and is already applied in step 1.
        # Only apply peak limiting if absolutely necessary to prevent clipping.
        target_peak_db = params.peak_target_db
        current_peak_db = DBConversion.to_db(np.max(np.abs(audio)))

        if current_peak_db > 0.0:
            # Audio is clipping - apply peak limiting only
            peak_adjustment = min(0.0 - current_peak_db, 0.0)  # At most bring to 0 dB
            audio = amplify(audio, peak_adjustment)
            debug(f"[Peak Limiting] {current_peak_db:.2f} → {0.0:.2f} dB (emergency limiting)")
        else:
            debug(f"[Peak Normalization] SKIPPED - audio peak at {current_peak_db:.2f} dB is safe")

        # Step 3: Safety limiter (CRITICAL FIX - was missing in previous version)
        audio, limiter_applied = SafetyLimiter.apply_if_needed(audio)

        # Final measurements
        final_peak = np.max(np.abs(audio))
        final_peak_db = DBConversion.to_db(final_peak)
        final_lufs = calculate_loudness_units(audio, self.config.internal_sample_rate)
        final_rms = rms(audio)
        final_rms_db = DBConversion.to_db(final_rms)
        final_crest = final_peak_db - final_rms_db

        print(f"[Final] Peak: {final_peak_db:.2f} dB, RMS: {final_rms_db:.2f} dB, "
              f"Crest: {final_crest:.2f} dB, LUFS: {final_lufs:.1f}")

        return audio
