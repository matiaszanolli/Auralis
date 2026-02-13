"""
Real-time DSP Pipeline
~~~~~~~~~~~~~~~~~~~~~~~

Real-time audio DSP pipeline for streaming applications.
Coordinates EQ and dynamics processing for low-latency chunk processing.

NOTE (Phase 1 refactoring): This processor is now a thin wrapper around
the DSP components. Audio validation is handled by AudioProcessingPipeline
when this processor is used through the pipeline.

NOTE (Phase 5 refactoring): Quick content analysis now delegated to
ContentAnalysisFacade for reusability across processors.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any

import numpy as np

from ...dsp.advanced_dynamics import DynamicsProcessor
from ...dsp.realtime_adaptive_eq import RealtimeAdaptiveEQ
from ...utils.logging import debug
from ..analysis.content_analysis_facade import (
    ContentAnalysisFacade,  # Phase 5: Unified analysis
)


class RealtimeDSPPipeline:
    """
    Real-time DSP pipeline for chunk-by-chunk audio processing.
    Coordinates adaptive EQ and dynamics processing with minimal latency.
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

        # Phase 5: Initialize content analysis facade for quick analysis
        self._analysis_facade = ContentAnalysisFacade(
            sample_rate=config.internal_sample_rate,
            realtime_mode=True  # Optimize for quick analysis
        )

    def process_chunk(self, audio_chunk: np.ndarray,
                     content_info: dict[str, Any] | None = None) -> np.ndarray:
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
            # If no content info provided, delegate to facade for quick analysis (Phase 5)
            if content_info is None:
                content_info = self._analysis_facade.analyze_quick(audio_chunk)

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

    # REMOVED (Phase 5 refactoring): _quick_content_analysis()
    # Now handled by ContentAnalysisFacade.analyze_quick()
