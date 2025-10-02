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
from .analysis import ContentAnalyzer, AdaptiveTargetGenerator
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
from ..analysis.ml_genre_classifier import MLGenreClassifier, create_ml_genre_classifier
from ..learning.preference_engine import PreferenceLearningEngine, UserAction, create_preference_engine
from ..optimization.performance_optimizer import get_performance_optimizer, optimized, cached
from ..utils.logging import debug, info
from ..io.results import Result


class HybridProcessor:
    """
    Main hybrid processor supporting reference-based and adaptive mastering
    """

    def __init__(self, config: UnifiedConfig):
        self.config = config
        self.content_analyzer = ContentAnalyzer(config.internal_sample_rate)
        self.target_generator = AdaptiveTargetGenerator(config, self)

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

        # Initialize advanced dynamics processor
        self.dynamics_processor = create_dynamics_processor(
            mode=DynamicsMode.ADAPTIVE,
            sample_rate=config.internal_sample_rate,
            target_lufs=-14.0  # Modern mastering standard
        )

        # Initialize preference learning engine
        self.preference_engine = create_preference_engine()
        self.current_user_id = None  # Will be set when user is identified

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
        """Apply adaptive processing based on generated targets"""
        debug("Applying adaptive processing")

        processed_audio = target_audio.copy()

        # Apply loudness adjustment
        current_lufs = calculate_loudness_units(processed_audio, self.config.internal_sample_rate)
        target_lufs = targets["target_lufs"]

        if abs(current_lufs - target_lufs) > 1.0:  # Only adjust if significant difference
            lufs_gain_db = target_lufs - current_lufs
            # Limit gain adjustment
            lufs_gain_db = np.clip(lufs_gain_db, -12, 12)
            processed_audio = amplify(processed_audio, lufs_gain_db)

        # Apply psychoacoustic EQ adjustments with content awareness
        content_profile = self.content_analyzer.analyze_content(processed_audio)

        # Store content profile for potential user learning
        self.last_content_profile = content_profile

        processed_audio = self._apply_psychoacoustic_eq(processed_audio, targets, content_profile)

        # Apply advanced dynamics processing
        processed_audio, dynamics_info = self.dynamics_processor.process(
            processed_audio, content_profile
        )

        # Apply stereo width adjustment
        if processed_audio.ndim == 2 and processed_audio.shape[1] == 2:
            current_width = stereo_width_analysis(processed_audio)
            target_width = targets["stereo_width"]
            if abs(current_width - target_width) > 0.1:
                processed_audio = adjust_stereo_width(processed_audio, target_width)

        # Store dynamics info for monitoring
        if hasattr(self, 'last_dynamics_info'):
            self.last_dynamics_info = dynamics_info

        # Apply gentle normalization (reduced since we have limiting)
        return normalize(processed_audio, 0.99)

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

        return normalize(blended_audio, 0.98)

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

            # Low-midrange (250-500 Hz)
            'low_mid_boost': targets.get("bass_boost_db", 0.0) * 0.5,

            # Midrange (500-2000 Hz)
            'mid_boost': targets.get("midrange_clarity_db", 0.0),

            # High-midrange (2000-4000 Hz)
            'high_mid_boost': targets.get("midrange_clarity_db", 0.0) * 0.7,

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
        eq_curve = self.realtime_eq.get_current_eq_curve()
        performance = self.realtime_eq.get_performance_stats()

        return {
            "eq_curve": eq_curve,
            "performance": performance,
            "buffer_size": self.realtime_eq.settings.buffer_size,
            "target_latency_ms": self.realtime_eq.settings.target_latency_ms,
            "actual_latency_ms": performance.get("total_latency_ms", 0),
            "adaptation_rate": self.realtime_eq.settings.adaptation_rate
        }

    def set_realtime_eq_parameters(self, **kwargs):
        """Update real-time EQ parameters dynamically"""
        self.realtime_eq.set_adaptation_parameters(**kwargs)
        info(f"Updated real-time EQ parameters: {kwargs}")

    def reset_realtime_eq(self):
        """Reset real-time EQ state"""
        self.realtime_eq.reset()
        info("Real-time EQ state reset")

    def get_dynamics_info(self) -> Dict[str, Any]:
        """Get dynamics processing information"""
        dynamics_info = self.dynamics_processor.get_processing_info()

        # Add recent processing info if available
        if hasattr(self, 'last_dynamics_info'):
            dynamics_info['last_processing'] = self.last_dynamics_info

        return dynamics_info

    def set_dynamics_mode(self, mode: str):
        """Set dynamics processing mode"""
        if mode in ['transparent', 'musical', 'broadcast', 'mastering', 'adaptive']:
            dynamics_mode = DynamicsMode(mode)
            self.dynamics_processor.set_mode(dynamics_mode)
            info(f"Dynamics mode set to: {mode}")
        else:
            debug(f"Invalid dynamics mode: {mode}")

    def reset_dynamics(self):
        """Reset dynamics processing state"""
        self.dynamics_processor.reset()
        info("Dynamics processor state reset")

    def set_user(self, user_id: str):
        """Set the current user for preference learning"""
        self.current_user_id = user_id
        # Ensure user profile exists
        self.preference_engine.get_or_create_user(user_id)
        info(f"User set for preference learning: {user_id}")

    def record_user_feedback(self, rating: float,
                           parameters_before: Optional[Dict[str, float]] = None,
                           parameters_after: Optional[Dict[str, float]] = None):
        """Record user feedback for learning"""
        if not self.current_user_id:
            debug("No user set for preference learning")
            return

        if not hasattr(self, 'last_content_profile'):
            debug("No content profile available for learning")
            return

        # Create user action record
        action = UserAction(
            timestamp=datetime.now(),
            action_type='rating',
            audio_features=self.last_content_profile,
            parameters_before=parameters_before or {},
            parameters_after=parameters_after or {},
            user_rating=rating
        )

        self.preference_engine.record_user_action(self.current_user_id, action)
        info(f"Recorded user rating: {rating}/5")

    def record_parameter_adjustment(self, parameter_name: str,
                                  old_value: float, new_value: float):
        """Record user parameter adjustment for learning"""
        if not self.current_user_id or not hasattr(self, 'last_content_profile'):
            return

        action = UserAction(
            timestamp=datetime.now(),
            action_type='adjustment',
            audio_features=self.last_content_profile,
            parameters_before={parameter_name: old_value},
            parameters_after={parameter_name: new_value}
        )

        self.preference_engine.record_user_action(self.current_user_id, action)
        debug(f"Recorded parameter adjustment: {parameter_name} {old_value} -> {new_value}")

    def get_user_insights(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get user preference insights"""
        target_user = user_id or self.current_user_id
        if not target_user:
            return {}

        return self.preference_engine.get_user_insights(target_user)

    def save_user_preferences(self, user_id: Optional[str] = None) -> bool:
        """Save user preferences to storage"""
        target_user = user_id or self.current_user_id
        if not target_user:
            return False

        return self.preference_engine.save_user_profile(target_user)

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