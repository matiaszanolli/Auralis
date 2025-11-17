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
from ...dsp.dynamics.soft_clipper import soft_clip
from ...utils.logging import debug
from .continuous_space import ProcessingSpaceMapper, PreferenceVector, ProcessingParameters
from .parameter_generator import ContinuousParameterGenerator
from ..recording_type_detector import RecordingTypeDetector


class ContinuousMode:
    """
    Continuous space processing mode - intelligent mastering using fingerprints.

    Instead of discrete presets, this mode maps the audio's 25D fingerprint
    to a continuous 3D processing space and generates optimal parameters
    for that specific position.
    """

    def __init__(self, config, content_analyzer, fingerprint_analyzer):
        """
        Initialize continuous space processor.

        Args:
            config: UnifiedConfig instance
            content_analyzer: ContentAnalyzer for audio analysis
            fingerprint_analyzer: AudioFingerprintAnalyzer for 25D fingerprints
        """
        self.config = config
        self.content_analyzer = content_analyzer
        self.fingerprint_analyzer = fingerprint_analyzer

        # Initialize continuous space components
        self.space_mapper = ProcessingSpaceMapper()
        self.param_generator = ContinuousParameterGenerator()

        # Initialize 25D-guided recording type detector
        self.recording_type_detector = RecordingTypeDetector()

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

    def process(self, target_audio: np.ndarray, eq_processor,
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

    def _apply_eq(self, audio: np.ndarray, eq_processor, params) -> np.ndarray:
        """Apply EQ using generated parameters"""

        eq_curve = params.eq_curve

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
              f"air {eq_curve['high_shelf_gain']:+.1f} dB")

        return audio

    def _apply_dynamics(self, audio: np.ndarray, params) -> np.ndarray:
        """Apply dynamics processing (compression or expansion)"""

        # Compression
        if params.compression_params['amount'] > 0.1:
            audio = self._apply_compression(audio, params.compression_params)

        # Expansion (de-mastering)
        if params.expansion_params['amount'] > 0.1:
            audio = self._apply_expansion(audio, params.expansion_params)

        return audio

    def _apply_compression(self, audio: np.ndarray, comp_params: Dict) -> np.ndarray:
        """Apply simple compression to reduce crest factor"""

        # Validate input - handle empty or very short audio gracefully
        if len(audio) == 0:
            return audio  # Return as-is if empty

        before_rms = rms(audio)
        before_peak = np.max(np.abs(audio))
        before_crest = 20 * np.log10(before_peak / (before_rms + 1e-10))

        ratio = comp_params['ratio']
        amount = comp_params['amount']

        # Simple DIY compression: apply soft clipping at higher levels
        # soft_clip API: (audio, threshold=0.9, ceiling=0.99)
        # Lower threshold = more compression, higher ratio = lower ceiling
        threshold = 0.8 - (ratio - 1.0) * 0.1  # 1.5:1 → 0.75, 2.0:1 → 0.70
        ceiling = 0.95

        compressed = soft_clip(audio, threshold=threshold, ceiling=ceiling)

        # Blend with original based on amount
        audio = audio * (1.0 - amount) + compressed * amount

        after_rms = rms(audio)
        after_peak = np.max(np.abs(audio))
        after_crest = 20 * np.log10(after_peak / (after_rms + 1e-10))

        print(f"[Compression] {ratio:.1f}:1 @ {amount:.0%}: "
              f"Crest {before_crest:.1f} → {after_crest:.1f} dB")

        return audio

    def _apply_expansion(self, audio: np.ndarray, exp_params: Dict) -> np.ndarray:
        """Apply expansion to increase crest factor (de-mastering)"""

        before_rms = rms(audio)
        before_peak = np.max(np.abs(audio))
        before_crest = 20 * np.log10(before_peak / (before_rms + 1e-10))

        target_increase = exp_params['target_crest_increase']
        amount = exp_params['amount']

        # Calculate current crest and target crest
        current_crest = before_crest
        target_crest = current_crest + target_increase

        # Expansion strategy: Reduce RMS while keeping peaks (increases crest)
        # This is the inverse of compression
        rms_reduction_db = target_increase * amount

        # Apply RMS reduction (makes audio quieter, increasing crest)
        audio = amplify(audio, -rms_reduction_db)

        after_rms = rms(audio)
        after_peak = np.max(np.abs(audio))
        after_crest = 20 * np.log10(after_peak / (after_rms + 1e-10))

        print(f"[Expansion] Target +{target_increase:.1f} dB @ {amount:.0%}: "
              f"Crest {before_crest:.1f} → {after_crest:.1f} dB")

        return audio

    def _apply_stereo_width(self, audio: np.ndarray, params) -> np.ndarray:
        """Apply stereo width adjustment"""

        # Only process stereo audio
        if audio.ndim != 2 or audio.shape[0] != 2:
            return audio

        # Get current and target width
        current_width = stereo_width_analysis(audio)
        target_width = params.stereo_width_target

        # Only adjust if significant difference
        if abs(target_width - current_width) > 0.05:
            # Check peak levels before expansion (safety)
            pre_peak = np.max(np.abs(audio))
            pre_peak_db = 20 * np.log10(pre_peak) if pre_peak > 0 else -np.inf

            # Skip expansion if already close to clipping
            if pre_peak_db > -2.0 and target_width > current_width:
                print(f"[Stereo Width] SKIPPED expansion due to high peak ({pre_peak_db:.2f} dB)")
                return audio

            audio = adjust_stereo_width(audio, target_width)

            post_width = stereo_width_analysis(audio)
            print(f"[Stereo Width] {current_width:.2f} → {post_width:.2f} (target: {target_width:.2f})")

        return audio

    def _apply_final_normalization(self, audio: np.ndarray, params) -> np.ndarray:
        """Apply final loudness and peak normalization"""

        # Measure current state
        current_lufs = calculate_loudness_units(audio, self.config.internal_sample_rate)
        current_peak = np.max(np.abs(audio))
        current_peak_db = 20 * np.log10(current_peak) if current_peak > 0 else -np.inf

        print(f"[Pre-Final] Peak: {current_peak_db:.2f} dB, LUFS: {current_lufs:.1f}")

        # Step 1: LUFS normalization (to target loudness)
        target_lufs = params.target_lufs
        lufs_adjustment = target_lufs - current_lufs

        if abs(lufs_adjustment) > 0.5:
            audio = amplify(audio, lufs_adjustment)
            debug(f"[LUFS Normalization] {current_lufs:.1f} → {target_lufs:.1f} LUFS ({lufs_adjustment:+.1f} dB)")

            # Update current measurements
            current_lufs = calculate_loudness_units(audio, self.config.internal_sample_rate)
            current_peak = np.max(np.abs(audio))
            current_peak_db = 20 * np.log10(current_peak) if current_peak > 0 else -np.inf

        # Step 2: Peak normalization (to target peak level)
        target_peak_db = params.peak_target_db

        if current_peak > 0:
            peak_adjustment = target_peak_db - current_peak_db
            audio = amplify(audio, peak_adjustment)
            debug(f"[Peak Normalization] {current_peak_db:.2f} → {target_peak_db:.2f} dB ({peak_adjustment:+.1f} dB)")

        # Final measurements
        final_peak = np.max(np.abs(audio))
        final_peak_db = 20 * np.log10(final_peak) if final_peak > 0 else -np.inf
        final_lufs = calculate_loudness_units(audio, self.config.internal_sample_rate)
        final_rms = rms(audio)
        final_rms_db = 20 * np.log10(final_rms) if final_rms > 0 else -np.inf
        final_crest = final_peak_db - final_rms_db

        print(f"[Final] Peak: {final_peak_db:.2f} dB, RMS: {final_rms_db:.2f} dB, "
              f"Crest: {final_crest:.2f} dB, LUFS: {final_lufs:.1f}")

        return audio
