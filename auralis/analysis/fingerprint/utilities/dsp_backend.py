# -*- coding: utf-8 -*-

"""
DSP Backend - Rust-Only Implementation

Provides unified interface for Rust DSP library (auralis_dsp).
Requires the Rust library to be compiled and available.

Supported Operations:
  - HPSS: Harmonic/percussive source separation
  - YIN: Fundamental frequency estimation
  - Chroma CQT: Constant-Q chromagram calculation

Note: This module no longer falls back to librosa. The Rust library is required
for optimal performance and is bundled in all distribution packages.
"""

import numpy as np
import logging
from typing import Tuple, Optional, Any

logger = logging.getLogger(__name__)


class DSPBackend:
    """Rust-only DSP operations interface (no Python fallback)."""

    # Class-level flag, initialized on module load
    AVAILABLE: bool = False
    _module: Optional[Any] = None

    @classmethod
    def initialize(cls) -> None:
        """Initialize DSP backend by loading Rust library (required)."""
        try:
            import auralis_dsp
            cls._module = auralis_dsp
            cls.AVAILABLE = True
            logger.info("Rust DSP library (auralis_dsp) loaded successfully")
        except ImportError as e:
            cls._module = None
            cls.AVAILABLE = False
            error_msg = (
                "CRITICAL: Rust DSP library (auralis_dsp) not available. "
                "Audio processing requires the Rust library for optimal performance. "
                "Please ensure auralis_dsp is compiled (run 'maturin develop' in vendor/auralis-dsp/)"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    @classmethod
    def hpss(cls, audio: np.ndarray, **kwargs: Any) -> Tuple[np.ndarray, np.ndarray]:
        """
        Harmonic/Percussive Source Separation (Rust implementation).

        Decomposes audio into harmonic and percussive components using optimized Rust code.

        Args:
            audio: Audio signal
            **kwargs: Additional arguments (reserved for future use)

        Returns:
            Tuple of (harmonic, percussive) components

        Raises:
            RuntimeError: If Rust library is not available
        """
        if not cls.AVAILABLE or cls._module is None:
            raise RuntimeError("Rust DSP library not initialized. Cannot perform HPSS.")

        try:
            return cls._module.hpss(audio)  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"HPSS processing failed: {e}")
            raise

    @classmethod
    def yin(cls, audio: np.ndarray, sr: int, fmin: float, fmax: float) -> np.ndarray:
        """
        YIN Fundamental Frequency Estimation (Rust implementation).

        Estimates the fundamental frequency (pitch) using the optimized YIN algorithm.

        Args:
            audio: Audio signal
            sr: Sample rate
            fmin: Minimum frequency to consider
            fmax: Maximum frequency to consider

        Returns:
            Array of pitch estimates (f0 in Hz), 0 for unvoiced frames

        Raises:
            RuntimeError: If Rust library is not available
        """
        if not cls.AVAILABLE or cls._module is None:
            raise RuntimeError("Rust DSP library not initialized. Cannot perform YIN pitch detection.")

        try:
            return cls._module.yin(audio, sr=sr, fmin=fmin, fmax=fmax)  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"YIN pitch detection failed: {e}")
            raise

    @classmethod
    def chroma_cqt(cls, audio: np.ndarray, sr: int) -> np.ndarray:
        """
        Constant-Q Chromagram Calculation (Rust implementation).

        Computes the 12-dimensional chroma features (pitch class profile) using optimized Rust code.

        Args:
            audio: Audio signal
            sr: Sample rate

        Returns:
            Chromagram array (12 x time_frames)

        Raises:
            RuntimeError: If Rust library is not available
        """
        if not cls.AVAILABLE or cls._module is None:
            raise RuntimeError("Rust DSP library not initialized. Cannot perform Chroma CQT.")

        try:
            return cls._module.chroma_cqt(audio, sr=sr)  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"Chroma CQT calculation failed: {e}")
            raise


# Initialize backend on module import
DSPBackend.initialize()
