# -*- coding: utf-8 -*-

"""
Real-time Processor
~~~~~~~~~~~~~~~~~~~

Real-time audio chunk processing for streaming applications

NOTE (Phase 1 refactoring): This processor is now a thin wrapper around
the DSP components. Audio validation is handled by AudioProcessingPipeline
when this processor is used through the pipeline.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict, Any, Optional
from ...dsp.realtime_adaptive_eq import RealtimeAdaptiveEQ
from ...dsp.advanced_dynamics import DynamicsProcessor
from ...utils.logging import debug


class RealtimeProcessor:
    """
    Real-time audio chunk processor for streaming applications
    Processes small audio chunks with minimal latency
    """

    def __init__(self, config: Any, realtime_eq: RealtimeAdaptiveEQ,
                 dynamics_processor: DynamicsProcessor) -> None:
        """
        Initialize real-time processor

        Args:
            config: UnifiedConfig instance
            realtime_eq: RealtimeAdaptiveEQ instance
            dynamics_processor: DynamicsProcessor instance
        """
        self.config = config
        self.realtime_eq = realtime_eq
        self.dynamics_processor = dynamics_processor

    def process_chunk(self, audio_chunk: np.ndarray,
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
        """
        Quick content analysis for real-time processing

        Args:
            audio_chunk: Audio chunk to analyze

        Returns:
            Quick content profile dictionary
        """
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
