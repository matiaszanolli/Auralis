# -*- coding: utf-8 -*-

"""
Base Analyzer Class for Fingerprint Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Abstract base class consolidating common error handling and interface
for all fingerprint analyzers (spectral, temporal, harmonic, variation, stereo).

Eliminates duplicate try/except blocks and default value handling across analyzers.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import numpy as np
from ...utils.logging import debug


class BaseAnalyzer(ABC):
    """
    Abstract base class for all fingerprint feature analyzers.

    Consolidates:
    - Common error handling (try/except blocks)
    - Default feature initialization
    - Analysis interface standardization
    - Logging and debugging

    All concrete analyzers (Spectral, Temporal, Harmonic, Variation, Stereo)
    inherit from this class and implement _analyze_impl().
    """

    # Override in subclasses with default values for each feature
    DEFAULT_FEATURES: Dict[str, float] = {}

    def __init__(self, name: str = None):
        """
        Initialize analyzer.

        Args:
            name: Display name for this analyzer (used in logging)
        """
        self.name = name or self.__class__.__name__

    def analyze(self, audio: np.ndarray, sr: int) -> Dict[str, float]:
        """
        Analyze audio and extract features.

        This is the public interface. Handles all error handling and provides
        sensible defaults if analysis fails.

        Args:
            audio: Audio signal
            sr: Sample rate in Hz

        Returns:
            Dictionary with feature names as keys and values in [0, 1] typically

        Note:
            If analysis fails, returns DEFAULT_FEATURES unchanged.
            This ensures downstream processing doesn't break on bad audio.
        """
        try:
            return self._analyze_impl(audio, sr)
        except Exception as e:
            debug(f"{self.name} analysis failed: {e}")
            return self.DEFAULT_FEATURES.copy()

    @abstractmethod
    def _analyze_impl(self, audio: np.ndarray, sr: int) -> Dict[str, float]:
        """
        Implement actual analysis logic.

        Override this method in subclasses.

        Args:
            audio: Audio signal
            sr: Sample rate in Hz

        Returns:
            Dictionary with features

        Raises:
            Any exception is caught by analyze() and triggers default return
        """
        raise NotImplementedError

    def validate_input(self, audio: np.ndarray, sr: int) -> bool:
        """
        Validate audio input before analysis.

        Args:
            audio: Audio signal
            sr: Sample rate

        Returns:
            True if input is valid

        Raises:
            ValueError: If input is invalid
        """
        if not isinstance(audio, np.ndarray):
            raise ValueError(f"Audio must be numpy array, got {type(audio)}")

        if audio.size == 0:
            raise ValueError("Audio array is empty")

        if not np.isfinite(audio).all():
            raise ValueError("Audio contains non-finite values (nan/inf)")

        if sr <= 0:
            raise ValueError(f"Sample rate must be positive, got {sr}")

        return True

    def __repr__(self) -> str:
        """String representation of analyzer."""
        return f"{self.name}(features={len(self.DEFAULT_FEATURES)})"
