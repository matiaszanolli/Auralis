"""
Base Assessor
~~~~~~~~~~~~~

Abstract base class for all quality assessors.

Defines the common interface and shared functionality for all quality
assessment implementations across loudness, stereo, distortion, frequency,
and dynamic range metrics.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

class BaseAssessor(ABC):
    """Abstract base class for quality assessors"""

    def __init__(self) -> None:
        """Initialize base assessor"""
        self._cached_analysis: dict[str, Any] | None = None

    @abstractmethod
    def assess(self, audio_data: np.ndarray, **kwargs: Any) -> float:
        """
        Assess audio quality on a 0-100 scale

        Args:
            audio_data: Audio data to analyze
            **kwargs: Additional assessor-specific parameters

        Returns:
            Quality score (0-100, higher is better)
        """

    @abstractmethod
    def detailed_analysis(self, audio_data: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        """
        Perform detailed quality analysis

        Args:
            audio_data: Audio data to analyze
            **kwargs: Additional assessor-specific parameters

        Returns:
            Dictionary with detailed metrics and sub-scores
        """

    def clear_cache(self) -> None:
        """Clear any cached analysis results"""
        self._cached_analysis = None
