# -*- coding: utf-8 -*-

"""
Base Streaming Analyzer

Mixin class providing common utilities for streaming feature analyzers.
Eliminates duplicate code for:
- Frame counting and analysis tracking
- Confidence scoring based on analysis runs
- Common interface patterns

Designed to be flexible enough for different buffering strategies
(buffer-based, chunk-based, or other) while providing shared utilities.
"""

import numpy as np
from typing import Dict, cast


class BaseStreamingAnalyzer:
    """Mixin class providing common utilities for streaming analyzers.

    Provides:
    - Frame and analysis counting
    - Confidence scoring calculation
    - Common getter methods

    Subclasses should:
    - Initialize self.sr, self.frame_count, self.analysis_runs
    - Implement their own update(), get_metrics(), reset() logic
    - Call get_confidence() for confidence scoring
    """

    def get_confidence(self) -> Dict[str, float]:
        """Get confidence scores for metrics.

        Confidence increases with more analysis runs. After 5 analyses,
        confidence reaches 1.0 (100%).

        This is a common pattern across streaming analyzers and is provided
        here to avoid duplication.

        Returns:
            Dict with metric names and confidence scores (0-1)
        """
        # Stabilization: 5 analyses = high confidence (100%)
        confidence = float(np.clip(self.analysis_runs / 5.0, 0, 1))

        # Return same confidence for all metrics from subclass
        metrics = self.get_metrics()
        return {metric: confidence for metric in metrics.keys()}

    def get_frame_count(self) -> int:
        """Get total frames processed so far.

        Requires self.frame_count to be initialized and maintained by subclass.

        Returns:
            Number of audio frames processed
        """
        return cast(int, self.frame_count)

    def get_analysis_count(self) -> int:
        """Get total analyses performed so far.

        Requires self.analysis_runs to be initialized and maintained by subclass.

        Returns:
            Number of analyses completed
        """
        return cast(int, self.analysis_runs)

    def get_metrics(self) -> Dict[str, float]:
        """Get current metric estimates.

        Subclasses must implement this to return their specific metrics.

        Returns:
            Dict with metric names as keys and float estimates as values
        """
        raise NotImplementedError("Subclass must implement get_metrics()")
