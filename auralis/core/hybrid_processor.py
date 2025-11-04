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
from typing import Optional, Union, List, Dict, Any
from pathlib import Path

from .unified_config import UnifiedConfig
from .analysis import ContentAnalyzer, AdaptiveTargetGenerator
from .analysis.spectrum_mapper import SpectrumMapper
from ..analysis.fingerprint import AudioFingerprintAnalyzer
from .processors import apply_reference_matching
from .processing import AdaptiveMode, HybridMode, EQProcessor, RealtimeProcessor, ContinuousMode
from ..dsp.psychoacoustic_eq import PsychoacousticEQ, EQSettings
from ..dsp.realtime_adaptive_eq import create_realtime_adaptive_eq
from ..dsp.advanced_dynamics import create_dynamics_processor, DynamicsMode
from ..dsp.dynamics import create_brick_wall_limiter
from ..optimization.performance_optimizer import get_performance_optimizer
from ..utils.logging import debug, info
from ..io.results import Result
from .hybrid import RealtimeEQManager, DynamicsManager, PreferenceManager
from ..learning.preference_engine import create_preference_engine


class HybridProcessor:
    """
    Main hybrid processor supporting reference-based and adaptive mastering

    This is a thin orchestrator that delegates to specialized mode processors:
    - AdaptiveMode: Spectrum-based adaptive processing
    - HybridMode: Combines reference matching with adaptive intelligence
    - RealtimeProcessor: Low-latency chunk processing for streaming
    """

    def __init__(self, config: UnifiedConfig):
        self.config = config

        # Initialize analyzers
        self.content_analyzer = ContentAnalyzer(config.internal_sample_rate)
        self.target_generator = AdaptiveTargetGenerator(config, self)
        self.spectrum_mapper = SpectrumMapper()
        self.fingerprint_analyzer = AudioFingerprintAnalyzer()

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
            buffer_size=min(config.fft_size // 4, 1024),
            target_latency_ms=20.0,
            adaptation_rate=config.adaptive.adaptation_strength
        )

        # Initialize advanced dynamics processor
        self.dynamics_processor = create_dynamics_processor(
            mode=DynamicsMode.ADAPTIVE,
            sample_rate=config.internal_sample_rate,
            target_lufs=-14.0
        )
        self.dynamics_processor.settings.enable_gate = False
        self.dynamics_processor.settings.enable_compressor = True
        self.dynamics_processor.settings.enable_limiter = False

        # Initialize brick-wall limiter for final peak control
        self.brick_wall_limiter = create_brick_wall_limiter(
            threshold_db=-0.3,
            lookahead_ms=2.0,
            release_ms=50.0,
            sample_rate=config.internal_sample_rate
        )

        # Initialize preference learning engine
        self.preference_engine = create_preference_engine()

        # Initialize component managers
        self.realtime_eq_manager = RealtimeEQManager(self.realtime_eq)
        self.dynamics_manager = DynamicsManager(self.dynamics_processor)
        self.preference_manager = PreferenceManager(self.preference_engine)

        # Initialize mode processors
        self.eq_processor = EQProcessor(self.psychoacoustic_eq)
        self.adaptive_mode = AdaptiveMode(
            config, self.content_analyzer, self.target_generator,
            self.spectrum_mapper
        )
        self.continuous_mode = ContinuousMode(
            config, self.content_analyzer, self.fingerprint_analyzer
        )
        self.hybrid_mode = HybridMode(
            config, self.content_analyzer, self.target_generator,
            self.adaptive_mode
        )
        self.realtime_processor = RealtimeProcessor(
            config, self.realtime_eq, self.dynamics_processor
        )

        # Shared state (backwards compatibility)
        self.current_user_id = None

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

        # Delegate to reference matching
        return apply_reference_matching(target_audio, reference_audio)

    def _process_adaptive_mode(self, target_audio: np.ndarray, results) -> np.ndarray:
        """Process using adaptive mastering without reference"""
        info("Processing in adaptive mode")

        # Choose processing mode based on config
        if self.config.use_continuous_space:
            info("Using continuous parameter space (fingerprint-based)")
            # Delegate to continuous mode processor
            processed = self.continuous_mode.process(target_audio, self.eq_processor)

            # Store fingerprint and parameters for learning/debugging
            self.last_content_profile = {
                'fingerprint': self.continuous_mode.last_fingerprint,
                'coordinates': self.continuous_mode.last_coordinates,
                'parameters': self.continuous_mode.last_parameters,
            }
        else:
            info("Using legacy preset-based processing")
            # Delegate to legacy adaptive mode processor
            processed = self.adaptive_mode.process(target_audio, self.eq_processor)

            # Store content profile for user learning
            self.last_content_profile = self.adaptive_mode.get_last_content_profile()

        self.preference_manager.set_content_profile(self.last_content_profile)

        return processed

    def _process_hybrid_mode(self, target_audio: np.ndarray,
                            reference: Optional[Union[str, np.ndarray]],
                            results) -> np.ndarray:
        """Process using hybrid approach combining reference and adaptive"""
        info("Processing in hybrid mode")

        # Load reference if provided
        reference_audio = None
        if reference is not None:
            if isinstance(reference, str):
                reference_audio = self._load_audio_placeholder(reference)
            else:
                reference_audio = reference

        # Delegate to hybrid mode processor
        return self.hybrid_mode.process(target_audio, reference_audio, self.eq_processor)

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
        return self.realtime_processor.process_chunk(audio_chunk, content_info)

    def _load_audio_placeholder(self, file_path: str) -> np.ndarray:
        """Placeholder for audio loading - will be replaced with unified I/O"""
        debug(f"Loading audio file: {file_path}")
        # For now, return dummy audio data
        return np.random.randn(44100 * 5, 2) * 0.1  # 5 seconds of dummy stereo audio

    # Delegation methods for component managers

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
        self.adaptive_mode.process = self.performance_optimizer.optimize_real_time_processing(
            self.adaptive_mode.process
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
