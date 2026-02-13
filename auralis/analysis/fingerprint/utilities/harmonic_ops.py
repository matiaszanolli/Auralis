"""
Harmonic Analysis Utilities - Rust DSP Backend

Shared harmonic feature calculations for batch and streaming analyzers.
Consolidates harmonic/percussive separation, pitch detection, and chroma analysis
to eliminate duplication across harmonic_analyzer.py, harmonic_analyzer_sampled.py,
and streaming_harmonic_analyzer.py.

Features:
  - harmonic_ratio: Ratio of harmonic to percussive content (0-1)
  - pitch_stability: How in-tune/stable the pitch is (0-1)
  - chroma_energy: Tonal complexity/richness (0-1)

Note: Uses Rust DSP backend (auralis_dsp) for all operations. Requires Rust library.
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)


class HarmonicOperations:
    """Centralized harmonic feature calculations."""

    @staticmethod
    def calculate_harmonic_ratio(audio: np.ndarray) -> float:
        """
        Calculate ratio of harmonic to percussive content using Rust DSP.

        Higher value = more harmonic (strings, vocals, sustained instruments)
        Lower value = more percussive (drums, attacks, rhythmic)

        Args:
            audio: Audio signal

        Returns:
            Harmonic ratio (0-1), or 0.5 if calculation fails

        Raises:
            RuntimeError: If Rust DSP library not available
        """
        try:
            # Import DSPBackend for Rust HPSS implementation
            from .dsp_backend import DSPBackend

            # Use Rust HPSS implementation (no fallback)
            harmonic, percussive = DSPBackend.hpss(audio)

            # Calculate RMS energy of each
            harmonic_energy = np.sqrt(np.mean(harmonic**2))
            percussive_energy = np.sqrt(np.mean(percussive**2))

            total_energy = harmonic_energy + percussive_energy

            if total_energy > 0:
                harmonic_ratio = harmonic_energy / total_energy
            else:
                harmonic_ratio = 0.5

            return float(np.clip(harmonic_ratio, 0, 1))

        except Exception as e:
            logger.error(f"Harmonic ratio calculation failed: {e}")
            raise

    @staticmethod
    def calculate_pitch_stability(audio: np.ndarray, sr: int) -> float:
        """
        Calculate pitch stability (how in-tune/stable the pitch is) using Rust DSP.

        Higher value = stable pitch (in-tune instruments, vocals)
        Lower value = unstable pitch (out-of-tune, dissonant, noise)

        Args:
            audio: Audio signal
            sr: Sample rate

        Returns:
            Pitch stability (0-1), or default values if calculation fails

        Raises:
            RuntimeError: If Rust DSP library not available
        """
        try:
            # Import here to avoid circular dependency
            from ..metrics import StabilityMetrics
            from .dsp_backend import DSPBackend

            # Calculate pitch (fundamental frequency) using Rust YIN algorithm
            # Frequency range: C2 (65.41 Hz) to C7 (2093.00 Hz)
            f0 = DSPBackend.yin(audio, sr=sr, fmin=65.41, fmax=2093.00)

            # Remove unvoiced frames (no pitch detected)
            voiced_mask = f0 > 0
            voiced_f0 = f0[voiced_mask]

            if len(voiced_f0) < 10:
                return 0.5  # Not enough pitch data

            # Calculate stability using unified StabilityMetrics
            # Higher scale makes pitch stability more sensitive to variation
            return float(StabilityMetrics.from_values(voiced_f0, scale=10.0))

        except Exception as e:
            logger.error(f"Pitch stability calculation failed: {e}")
            raise

    @staticmethod
    def calculate_chroma_energy(audio: np.ndarray, sr: int) -> float:
        """
        Calculate chroma energy (tonal complexity/richness) using Rust DSP.

        Higher value = more tonal complexity (rich harmonies, chords)
        Lower value = simpler tonal content (single notes, sparse)

        Args:
            audio: Audio signal
            sr: Sample rate

        Returns:
            Chroma energy (0-1), or 0.5 if calculation fails

        Raises:
            RuntimeError: If Rust DSP library not available
        """
        try:
            # Import here to avoid circular dependency
            from ..metrics import MetricUtils
            from .dsp_backend import DSPBackend

            # Calculate chromagram (12-dimensional pitch class profile) using Rust
            chroma = DSPBackend.chroma_cqt(audio, sr=sr)

            # Calculate average energy across all pitch classes
            # High energy in multiple classes = rich tonal content
            chroma_mean = np.mean(chroma, axis=1)  # Average across time for each pitch class

            # Calculate how many pitch classes are active
            # (how spread the energy is across pitch classes)
            chroma_energy = np.mean(chroma_mean)

            # Normalize to 0-1 using MetricUtils
            # Typical range: 0.1-0.4
            # Simple tonal: 0.1-0.2
            # Rich tonal: 0.3-0.4
            normalized = MetricUtils.normalize_to_range(float(chroma_energy), max_val=0.4, clip=True)

            return float(normalized)

        except Exception as e:
            logger.error(f"Chroma energy calculation failed: {e}")
            raise

    @staticmethod
    def calculate_all(audio: np.ndarray, sr: int) -> tuple[float, float, float]:
        """
        Calculate all three harmonic features in one call.

        Args:
            audio: Audio signal
            sr: Sample rate

        Returns:
            Tuple of (harmonic_ratio, pitch_stability, chroma_energy)
        """
        return (
            HarmonicOperations.calculate_harmonic_ratio(audio),
            HarmonicOperations.calculate_pitch_stability(audio, sr),
            HarmonicOperations.calculate_chroma_energy(audio, sr)
        )
