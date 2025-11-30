# -*- coding: utf-8 -*-

"""
DSP Backend Abstraction Layer

Provides unified interface for Rust DSP library (auralis_dsp) with automatic
fallback to librosa implementations when the Rust library is unavailable.

This eliminates repeated try/except import patterns across harmonic analyzers
and provides a single point of control for swapping DSP implementations.

Supported Operations:
  - HPSS: Harmonic/percussive source separation
  - YIN: Fundamental frequency estimation
  - Chroma CQT: Constant-Q chromagram calculation
"""

import numpy as np
import librosa
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class DSPBackend:
    """Unified interface for DSP operations with automatic backend selection."""

    # Class-level flag, initialized on module load
    AVAILABLE = False
    _module = None

    @classmethod
    def initialize(cls):
        """Initialize DSP backend, attempting to load Rust library."""
        try:
            import auralis_dsp
            cls._module = auralis_dsp
            cls.AVAILABLE = True
            logger.info("Rust DSP library (auralis_dsp) available - using optimized implementations")
        except ImportError:
            cls._module = None
            cls.AVAILABLE = False
            logger.warning("Rust DSP library (auralis_dsp) not available - falling back to librosa")

    @classmethod
    def hpss(cls, audio: np.ndarray, **kwargs) -> Tuple[np.ndarray, np.ndarray]:
        """
        Harmonic/Percussive Source Separation.

        Decomposes audio into harmonic and percussive components.

        Args:
            audio: Audio signal
            **kwargs: Additional arguments (ignored for librosa compatibility)

        Returns:
            Tuple of (harmonic, percussive) components
        """
        try:
            if cls.AVAILABLE:
                return cls._module.hpss(audio)
            else:
                return librosa.effects.hpss(audio)
        except Exception as e:
            logger.debug(f"HPSS failed: {e}, returning original audio as harmonic")
            return audio, np.zeros_like(audio)

    @classmethod
    def yin(cls, audio: np.ndarray, sr: int, fmin: float, fmax: float) -> np.ndarray:
        """
        YIN Fundamental Frequency Estimation.

        Estimates the fundamental frequency (pitch) using the YIN algorithm.

        Args:
            audio: Audio signal
            sr: Sample rate
            fmin: Minimum frequency to consider
            fmax: Maximum frequency to consider

        Returns:
            Array of pitch estimates (f0 in Hz), 0 for unvoiced frames
        """
        try:
            if cls.AVAILABLE:
                return cls._module.yin(audio, sr=sr, fmin=fmin, fmax=fmax)
            else:
                return librosa.yin(audio, fmin=fmin, fmax=fmax, sr=sr)
        except Exception as e:
            logger.debug(f"YIN pitch detection failed: {e}, returning zeros")
            return np.zeros(len(audio) // 512 + 1)  # Approximate frame count

    @classmethod
    def chroma_cqt(cls, audio: np.ndarray, sr: int) -> np.ndarray:
        """
        Constant-Q Chromagram Calculation.

        Computes the 12-dimensional chroma features (pitch class profile).

        Args:
            audio: Audio signal
            sr: Sample rate

        Returns:
            Chromagram array (12 x time_frames)
        """
        try:
            if cls.AVAILABLE:
                return cls._module.chroma_cqt(audio, sr=sr)
            else:
                return librosa.feature.chroma_cqt(y=audio, sr=sr)
        except Exception as e:
            logger.debug(f"Chroma CQT calculation failed: {e}, returning default chroma")
            # Return default uniform chroma
            n_frames = len(audio) // 512 + 1
            return np.ones((12, n_frames)) / 12.0


# Initialize backend on module import
DSPBackend.initialize()
