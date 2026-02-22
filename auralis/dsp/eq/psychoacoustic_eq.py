"""
Psychoacoustic EQ Main Class
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Main orchestrator for psychoacoustic EQ processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass
from typing import Any, cast

import numpy as np

from ...utils.logging import debug
from ..unified import smooth_parameter_transition
from .critical_bands import (
    create_critical_bands,
    create_frequency_mapping,
    create_perceptual_weighting,
)
from .curves import apply_content_adaptation
from .filters import apply_eq_gains
from .masking import MaskingThresholdCalculator

# Use vectorized EQ processor for 1.7x speedup
try:
    from .parallel_eq_processor import VectorizedEQProcessor
    VECTORIZED_EQ_AVAILABLE = True
except ImportError:
    VECTORIZED_EQ_AVAILABLE = False
    debug("Vectorized EQ not available, using standard version")


@dataclass
class EQSettings:
    """Psychoacoustic EQ settings"""
    sample_rate: int = 44100
    fft_size: int = 4096
    overlap: float = 0.75
    smoothing_factor: float = 0.1
    masking_threshold_db: float = -60.0
    adaptation_speed: float = 0.2


class PsychoacousticEQ:
    """
    Advanced EQ system using psychoacoustic principles

    Based on 2024 research in adaptive filter topologies and perceptual models.
    Provides content-aware equalization using critical band analysis and
    psychoacoustic masking models.
    """

    def __init__(self, settings: EQSettings):
        """
        Initialize psychoacoustic EQ

        Args:
            settings: EQ configuration settings
        """
        self.settings = settings
        self.sample_rate = settings.sample_rate
        self.fft_size = settings.fft_size
        self.hop_size = int(self.fft_size * (1 - settings.overlap))

        # Initialize critical bands (26 bands based on Bark scale)
        self.critical_bands = create_critical_bands()

        # Initialize psychoacoustic models
        self.masking_calculator = MaskingThresholdCalculator()
        self.perceptual_weighting = create_perceptual_weighting(
            self.sample_rate,
            self.fft_size
        )

        # Processing state (0.0 dB = flat/unity gain)
        self.current_gains = np.zeros(len(self.critical_bands))
        self.target_gains = np.zeros(len(self.critical_bands))
        self.processing_history: list[dict[str, Any]] = []

        # Pre-compute frequency mapping
        self.freq_to_band_map = create_frequency_mapping(
            self.critical_bands,
            self.sample_rate,
            self.fft_size
        )

        # Initialize vectorized EQ processor (1.7x speedup)
        if VECTORIZED_EQ_AVAILABLE:
            self.vectorized_processor: Any | None = VectorizedEQProcessor()
            debug(f"Psychoacoustic EQ initialized: {len(self.critical_bands)} critical bands (vectorized)")
        else:
            self.vectorized_processor = None
            debug(f"Psychoacoustic EQ initialized: {len(self.critical_bands)} critical bands (standard)")

    def analyze_spectrum(self, audio_chunk: np.ndarray) -> dict[str, np.ndarray]:
        """
        Analyze audio spectrum for adaptive EQ

        Args:
            audio_chunk: Audio data for analysis

        Returns:
            Dictionary with spectrum analysis results containing:
                - magnitude_db: Magnitude spectrum in dB
                - band_energies: Energy per critical band
                - masking_thresholds: Masking thresholds per band
                - spectrum: Complex spectrum
        """
        if audio_chunk.ndim == 2:
            # Convert stereo to mono for analysis
            audio_mono = np.mean(audio_chunk, axis=1)
        else:
            audio_mono = audio_chunk

        # Ensure we have enough samples
        if len(audio_mono) < self.fft_size:
            # Pad with zeros
            padded = np.zeros(self.fft_size)
            padded[:len(audio_mono)] = audio_mono
            audio_mono = padded

        # Apply window to reduce spectral leakage
        window = np.hanning(self.fft_size)
        windowed_audio = audio_mono[:self.fft_size] * window

        # Compute spectrum
        from scipy.fft import fft
        spectrum = fft(windowed_audio)
        magnitude = np.abs(spectrum[:self.fft_size // 2 + 1])

        # Convert to dB and compensate for Hanning window coherent amplitude gain.
        # The Hanning window has a coherent gain of 0.5 (−6.02 dB), so windowed
        # magnitudes read ~6 dB lower than the unwindowed synthesis path.  Adding
        # 6.02 dB here aligns analysis magnitudes with the EQ synthesis scale,
        # preventing adaptive gain curves from over-boosting by that margin (fixes #2518).
        magnitude_db = 20 * np.log10(magnitude + 1e-10) + 6.02

        # Calculate energy in each critical band
        band_energies = self._calculate_band_energies(magnitude_db)

        # Calculate masking thresholds
        masking_thresholds = self.masking_calculator.calculate_masking(
            magnitude, self.critical_bands, self.sample_rate
        )

        return {
            'magnitude_db': magnitude_db,
            'band_energies': band_energies,
            'masking_thresholds': masking_thresholds,
            'spectrum': spectrum
        }

    def _calculate_band_energies(self, magnitude_db: np.ndarray) -> np.ndarray:
        """Calculate energy in each critical band"""
        band_energies = np.zeros(len(self.critical_bands))
        for i, band in enumerate(self.critical_bands):
            band_mask = self.freq_to_band_map == i
            if np.any(band_mask):
                band_energies[i] = np.mean(magnitude_db[band_mask])
        return band_energies

    def calculate_adaptive_gains(self,
                                spectrum_analysis: dict[str, Any],
                                target_curve: np.ndarray,
                                content_profile: dict[str, Any] | None = None) -> np.ndarray:
        """
        Calculate adaptive EQ gains based on spectrum analysis

        Args:
            spectrum_analysis: Results from analyze_spectrum
            target_curve: Target frequency response curve
            content_profile: Optional content analysis for adaptation

        Returns:
            Array of gain values in dB for each critical band
        """
        band_energies = spectrum_analysis['band_energies']
        masking_thresholds = spectrum_analysis['masking_thresholds']

        # Calculate initial gains based on target curve
        target_gains = self._calculate_target_gains(
            band_energies,
            masking_thresholds,
            target_curve
        )

        # Content-aware adaptation
        if content_profile:
            target_gains = apply_content_adaptation(
                target_gains,
                content_profile,
                self.critical_bands
            )

        # Smooth transitions to avoid artifacts
        adaptive_gains = self._smooth_gains(target_gains)

        return adaptive_gains

    def _calculate_target_gains(self,
                               band_energies: np.ndarray,
                               masking_thresholds: np.ndarray,
                               target_curve: np.ndarray) -> np.ndarray:
        """Calculate target gains for each band"""
        target_gains = np.zeros(len(self.critical_bands))

        # Guard against NaN/Inf from silent audio or log10(0) (fixes #2513)
        band_energies = np.where(np.isfinite(band_energies), band_energies, 0.0)
        masking_thresholds = np.where(np.isfinite(masking_thresholds), masking_thresholds, 0.0)

        for i, band in enumerate(self.critical_bands):
            # Find target level for this band
            if i < len(target_curve):
                target_level = target_curve[i]
            else:
                target_level = 0.0  # Default to no change

            # Calculate required gain
            current_level = band_energies[i]
            required_gain = target_level - current_level

            # Apply masking-aware adjustment
            masking_threshold = masking_thresholds[i]
            if current_level < masking_threshold:
                # Below masking threshold - reduce gain to avoid artifacts
                required_gain *= 0.5

            # Apply perceptual weighting
            weighted_gain = required_gain * band.weight

            target_gains[i] = np.clip(weighted_gain, -12.0, 12.0)  # Limit gain range

        return target_gains

    def _smooth_gains(self, target_gains: np.ndarray) -> np.ndarray:
        """Smooth gain transitions to avoid artifacts"""
        adaptive_gains = np.zeros_like(target_gains)
        for i in range(len(target_gains)):
            adaptive_gains[i] = smooth_parameter_transition(
                self.current_gains[i],
                target_gains[i],
                self.settings.adaptation_speed
            )

        # Update current gains
        self.current_gains = adaptive_gains.copy()

        return adaptive_gains

    def apply_eq(self, audio_chunk: np.ndarray, gains: np.ndarray) -> np.ndarray:
        """
        Apply EQ gains to audio chunk

        Args:
            audio_chunk: Input audio data
            gains: Gain values for each critical band

        Returns:
            EQ-processed audio
        """
        # Use vectorized processor if available (1.7x faster)
        if self.vectorized_processor is not None:
            return cast(np.ndarray, self.vectorized_processor.apply_eq_gains_vectorized(
                audio_chunk,
                gains,
                self.freq_to_band_map,
                self.fft_size
            ))
        else:
            # Fall back to standard implementation
            return apply_eq_gains(audio_chunk, gains, self.freq_to_band_map, self.fft_size)

    def process_realtime_chunk(self,
                              audio_chunk: np.ndarray,
                              target_curve: np.ndarray,
                              content_profile: dict[str, Any] | None = None) -> np.ndarray:
        """
        Process audio chunk with real-time adaptive EQ

        Args:
            audio_chunk: Input audio chunk
            target_curve: Target EQ curve
            content_profile: Optional content analysis

        Returns:
            Processed audio chunk
        """
        # Analyze spectrum
        spectrum_analysis = self.analyze_spectrum(audio_chunk)

        # Calculate adaptive gains
        gains = self.calculate_adaptive_gains(
            spectrum_analysis, target_curve, content_profile
        )

        # Apply EQ
        processed_chunk = self.apply_eq(audio_chunk, gains)

        # Store processing history for learning
        self._update_history(gains, spectrum_analysis, content_profile)

        return processed_chunk

    def _update_history(self,
                       gains: np.ndarray,
                       spectrum_analysis: dict[str, Any],
                       content_profile: dict[str, Any] | None) -> None:
        """Update processing history for learning"""
        self.processing_history.append({
            'gains': gains.copy(),
            'band_energies': spectrum_analysis['band_energies'].copy(),
            'content_profile': content_profile
        })

        # Limit history size
        if len(self.processing_history) > 100:
            self.processing_history.pop(0)

    def get_current_response(self) -> dict[str, Any]:
        """
        Get current EQ response

        Returns:
            Dictionary containing frequencies, gains, and band ranges
        """
        freqs = np.array([band.center_freq for band in self.critical_bands])
        gains = self.current_gains

        return {
            'frequencies': freqs,
            'gains_db': gains,
            'bands': [(band.low_freq, band.high_freq) for band in self.critical_bands]
        }

    def reset(self) -> None:
        """Reset EQ to flat response"""
        self.current_gains = np.zeros(len(self.critical_bands))
        self.target_gains = np.zeros(len(self.critical_bands))
        self.processing_history.clear()
