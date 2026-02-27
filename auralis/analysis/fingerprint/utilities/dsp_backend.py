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

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class DSPBackend:
    """Rust-only DSP operations interface (no Python fallback)."""

    # Class-level flag, initialized on module load
    AVAILABLE: bool = False
    _module: Any | None = None

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

    @staticmethod
    def _validate_ffi_inputs(audio: np.ndarray, sr: int, op: str) -> np.ndarray:
        """
        Validate and coerce inputs at the Rust FFI boundary (fixes #2521).

        The Rust DSP module requires float64. An empty array or sr=0 causes a
        Rust panic that crashes the interpreter instead of raising a Python exception.
        """
        if sr <= 0:
            raise ValueError(f"{op}: sample rate must be > 0, got sr={sr}")
        if audio.size == 0:
            raise ValueError(f"{op}: audio array is empty")
        if audio.dtype != np.float64:
            audio = audio.astype(np.float64)
        return audio

    @classmethod
    def hpss(cls, audio: np.ndarray, sr: int = 22050, **kwargs: Any) -> tuple[np.ndarray, np.ndarray]:
        """
        Harmonic/Percussive Source Separation (Rust implementation).

        Decomposes audio into harmonic and percussive components using optimized Rust code.

        Args:
            audio: Audio signal
            sr: Sample rate (used for validation; HPSS itself is sample-rate agnostic)
            **kwargs: Additional arguments (reserved for future use)

        Returns:
            Tuple of (harmonic, percussive) components

        Raises:
            RuntimeError: If Rust library is not available
        """
        if not cls.AVAILABLE or cls._module is None:
            raise RuntimeError("Rust DSP library not initialized. Cannot perform HPSS.")

        audio = cls._validate_ffi_inputs(audio, sr, "HPSS")
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

        audio = cls._validate_ffi_inputs(audio, sr, "YIN")
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

        audio = cls._validate_ffi_inputs(audio, sr, "Chroma CQT")
        try:
            return cls._module.chroma_cqt(audio, sr=sr)  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"Chroma CQT calculation failed: {e}")
            raise

    @classmethod
    def detect_tempo(cls, audio: np.ndarray, sr: int) -> float:
        """
        Tempo Detection via Spectral Flux Onset Detection (Rust implementation).

        Estimates tempo in BPM using FFT-based spectral flux onset detection.
        Automatically scales parameters for different sample rates.

        Args:
            audio: Audio signal (mono)
            sr: Sample rate

        Returns:
            Tempo in BPM (40-200 range)

        Raises:
            RuntimeError: If Rust library is not available
        """
        if not cls.AVAILABLE or cls._module is None:
            raise RuntimeError("Rust DSP library not initialized. Cannot perform tempo detection.")

        try:
            # Use larger FFT and hop for tempo detection to capture beat-level events
            # not individual transients. ~93ms window at 44.1kHz catches beat patterns.
            base_sr = 44100
            scale_factor = max(1, sr // base_sr)
            n_fft = 4096 * scale_factor  # Larger window for beat-level detection
            hop_length = 2048 * scale_factor  # Larger hop to smooth out subdivisions

            # Higher threshold to only detect strong beat onsets
            threshold = 3.0 + 0.1 * (scale_factor - 1)

            return cls._module.detect_tempo(
                audio,
                sr=sr,
                n_fft=n_fft,
                hop_length=hop_length,
                threshold_multiplier=threshold
            )  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"Tempo detection failed: {e}")
            raise


# Initialize backend on module import
DSPBackend.initialize()
