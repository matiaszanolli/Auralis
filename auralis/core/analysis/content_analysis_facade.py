# -*- coding: utf-8 -*-

"""
Content Analysis Facade
~~~~~~~~~~~~~~~~~~~~~~~~

Unified interface for content analysis providing both full and quick analysis modes.
Consolidates analyzer initialization and quick analysis logic.

This facade eliminates duplicate analyzer initialization across processors
and provides a single entry point for all content analysis operations.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AnalysisConfig:
    """Configuration for content analysis facade."""
    sample_rate: int = 44100
    use_ml_classification: bool = True
    use_tempo_detection: bool = True
    realtime_mode: bool = False


class ContentAnalysisFacade:
    """
    Unified content analysis facade providing both full and quick analysis.
    
    Consolidates ContentAnalyzer initialization and realtime quick analysis.
    
    Usage Patterns:
    
    1. Full Analysis (hybrid_processor, chunked_processor):
       ```python
       facade = ContentAnalysisFacade(sample_rate=44100)
       result = facade.analyze_full(audio)
       ```
    
    2. Quick Analysis (realtime_processor):
       ```python
       facade = ContentAnalysisFacade(sample_rate=44100, realtime_mode=True)
       result = facade.analyze_quick(audio)
       ```
    
    3. Adaptive Analysis (routes based on context):
       ```python
       facade = ContentAnalysisFacade(sample_rate=44100)
       result = facade.analyze_adaptive(audio, realtime=True)  # Uses quick
       result = facade.analyze_adaptive(audio, realtime=False) # Uses full
       ```
    """

    def __init__(
        self,
        sample_rate: int = 44100,
        config: Optional[Any] = None,
        use_ml_classification: bool = True,
        use_tempo_detection: bool = True,
        realtime_mode: bool = False
    ):
        """
        Initialize content analysis facade.
        
        Args:
            sample_rate: Audio sample rate
            config: Optional UnifiedConfig instance (for compatibility)
            use_ml_classification: Enable ML-based genre classification
            use_tempo_detection: Enable tempo detection
            realtime_mode: If True, optimizes for quick analysis
        """
        self.sample_rate = sample_rate
        self.config = config
        self.use_ml_classification = use_ml_classification
        self.use_tempo_detection = use_tempo_detection
        self.realtime_mode = realtime_mode
        
        # Lazy initialization (only create when needed)
        self._content_analyzer: Optional[Any] = None
        self._target_generator: Optional[Any] = None
        self._spectrum_mapper: Optional[Any] = None
        
        logger.debug(
            f"ContentAnalysisFacade initialized: "
            f"sample_rate={sample_rate}, realtime={realtime_mode}"
        )

    @property
    def content_analyzer(self) -> Any:
        """Lazy-load ContentAnalyzer (full analysis)."""
        if self._content_analyzer is None:
            from .content_analyzer import ContentAnalyzer
            self._content_analyzer = ContentAnalyzer(
                sample_rate=self.sample_rate,
                use_ml_classification=self.use_ml_classification,
                use_tempo_detection=self.use_tempo_detection
            )
            logger.debug("ContentAnalyzer initialized (lazy)")
        return self._content_analyzer

    @property
    def target_generator(self) -> Any:
        """Lazy-load AdaptiveTargetGenerator."""
        if self._target_generator is None:
            from ..analysis.target_generator import AdaptiveTargetGenerator

            # Create config if not provided
            if self.config is None:
                from ..unified_config import UnifiedConfig
                config = UnifiedConfig(internal_sample_rate=self.sample_rate)
            else:
                config = self.config
            
            self._target_generator = AdaptiveTargetGenerator(config, processor=None)
            logger.debug("AdaptiveTargetGenerator initialized (lazy)")
        return self._target_generator

    @property
    def spectrum_mapper(self) -> Any:
        """Lazy-load SpectrumMapper."""
        if self._spectrum_mapper is None:
            from ..analysis.spectrum_mapper import SpectrumMapper

            # Create config if not provided
            if self.config is None:
                from ..unified_config import UnifiedConfig
                config = UnifiedConfig(internal_sample_rate=self.sample_rate)
            else:
                config = self.config
            
            self._spectrum_mapper = SpectrumMapper(config)
            logger.debug("SpectrumMapper initialized (lazy)")
        return self._spectrum_mapper

    def analyze_full(
        self,
        audio: np.ndarray,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Full content analysis with all features.
        
        Consolidates logic from:
        - hybrid_processor: ContentAnalyzer usage
        - chunked_processor: AdaptiveMasteringEngine analysis
        
        Args:
            audio: Audio array to analyze
            **kwargs: Additional arguments passed to analyzer
        
        Returns:
            Complete content analysis result with all features
        """
        logger.debug("Running full content analysis")
        
        # Use ContentAnalyzer for comprehensive analysis
        result = self.content_analyzer.analyze_content(audio, **kwargs)
        
        return result

    def analyze_quick(
        self,
        audio: np.ndarray
    ) -> Dict[str, Any]:
        """
        Quick analysis for real-time streaming.
        
        Consolidates realtime_processor._quick_content_analysis() logic.
        Performs minimal computation for low-latency processing.
        
        Args:
            audio: Audio chunk to analyze
        
        Returns:
            Quick content profile with basic features:
            - rms: RMS level
            - peak: Peak level
            - energy_level: "low"/"medium"/"high"
            - spectral_centroid: Center frequency
            - genre_info: Default genre (would use cached from full analysis)
            - dynamic_range: Estimated dynamic range
        """
        logger.debug("Running quick content analysis")
        
        # Convert to mono if stereo
        if audio.ndim == 2:
            mono_audio = np.mean(audio, axis=1)
        else:
            mono_audio = audio
        
        # Quick feature extraction (minimal computation)
        rms_val = np.sqrt(np.mean(mono_audio ** 2))
        peak_val = np.max(np.abs(mono_audio))
        
        # Simple energy level classification
        if rms_val > 0.3:
            energy_level = "high"
        elif rms_val > 0.1:
            energy_level = "medium"
        else:
            energy_level = "low"
        
        # Quick spectral centroid (simplified FFT)
        if len(mono_audio) >= 512:
            spectrum = np.fft.fft(mono_audio[:512])
            magnitude = np.abs(spectrum[:257])
            freqs = np.fft.fftfreq(512, 1/self.sample_rate)[:257]
            centroid = np.sum(freqs * magnitude) / (np.sum(magnitude) + 1e-10)
        else:
            centroid = 1000.0  # Default
        
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

    def analyze_adaptive(
        self,
        audio: np.ndarray,
        realtime: bool = False,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Adaptive analysis: quick if realtime=True, full otherwise.
        
        This method routes to the appropriate analysis mode based on context.
        
        Args:
            audio: Audio to analyze
            realtime: If True, use quick analysis; if False, use full analysis
            **kwargs: Additional arguments for full analysis
        
        Returns:
            Analysis result (quick or full depending on mode)
        """
        if realtime or self.realtime_mode:
            return self.analyze_quick(audio)
        else:
            return self.analyze_full(audio, **kwargs)

    def reset(self) -> None:
        """Reset all analyzers (clear cached state)."""
        self._content_analyzer = None
        self._target_generator = None
        self._spectrum_mapper = None
        logger.debug("ContentAnalysisFacade reset (analyzers cleared)")


# Global facade instance (singleton pattern)
_global_content_analysis_facade: Optional[ContentAnalysisFacade] = None


def get_content_analysis_facade(
    sample_rate: int = 44100,
    realtime_mode: bool = False
) -> ContentAnalysisFacade:
    """
    Get global content analysis facade instance (singleton).
    
    Args:
        sample_rate: Audio sample rate
        realtime_mode: If True, optimize for quick analysis
    
    Returns:
        Global ContentAnalysisFacade instance
    """
    global _global_content_analysis_facade
    
    if _global_content_analysis_facade is None:
        _global_content_analysis_facade = ContentAnalysisFacade(
            sample_rate=sample_rate,
            realtime_mode=realtime_mode
        )
        logger.info("Global ContentAnalysisFacade instance created")
    
    return _global_content_analysis_facade


def create_content_analysis_facade(
    sample_rate: int = 44100,
    **kwargs: Any
) -> ContentAnalysisFacade:
    """
    Create new content analysis facade instance (for testing or isolation).
    
    Args:
        sample_rate: Audio sample rate
        **kwargs: Additional arguments passed to ContentAnalysisFacade
    
    Returns:
        New ContentAnalysisFacade instance
    """
    return ContentAnalysisFacade(sample_rate=sample_rate, **kwargs)
