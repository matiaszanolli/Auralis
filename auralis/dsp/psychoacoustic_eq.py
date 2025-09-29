# -*- coding: utf-8 -*-

"""
Psychoacoustic EQ System
~~~~~~~~~~~~~~~~~~~~~~~~

Advanced EQ processing based on human auditory perception models

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Psychoacoustic-based adaptive EQ inspired by 2024 research in adaptive mastering
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from scipy import signal
from scipy.fft import fft, ifft

from .unified import smooth_parameter_transition
from ..utils.logging import debug


@dataclass
class CriticalBand:
    """Critical band definition based on Bark scale"""
    index: int
    center_freq: float
    low_freq: float
    high_freq: float
    bandwidth: float
    weight: float  # Perceptual importance weight


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

    Based on 2024 research in adaptive filter topologies and perceptual models
    """

    def __init__(self, settings: EQSettings):
        self.settings = settings
        self.sample_rate = settings.sample_rate
        self.fft_size = settings.fft_size
        self.hop_size = int(self.fft_size * (1 - settings.overlap))

        # Initialize critical bands (26 bands based on Bark scale)
        self.critical_bands = self._create_critical_bands()

        # Initialize psychoacoustic models
        self.masking_calculator = MaskingThresholdCalculator()
        self.perceptual_weighting = self._create_perceptual_weighting()

        # Processing state
        self.current_gains = np.ones(len(self.critical_bands))
        self.target_gains = np.ones(len(self.critical_bands))
        self.processing_history = []

        # Pre-compute frequency mapping
        self.freq_to_band_map = self._create_frequency_mapping()

        debug(f"Psychoacoustic EQ initialized: {len(self.critical_bands)} critical bands")

    def _create_critical_bands(self) -> List[CriticalBand]:
        """Create critical bands based on Bark scale"""
        # Bark scale critical band boundaries (approximate)
        bark_frequencies = [
            0, 100, 200, 300, 400, 510, 630, 770, 920, 1080,
            1270, 1480, 1720, 2000, 2320, 2700, 3150, 3700, 4400,
            5300, 6400, 7700, 9500, 12000, 15500, 20000
        ]

        critical_bands = []

        for i in range(len(bark_frequencies) - 1):
            low_freq = bark_frequencies[i]
            high_freq = bark_frequencies[i + 1]
            center_freq = np.sqrt(low_freq * high_freq)  # Geometric mean
            bandwidth = high_freq - low_freq

            # Perceptual weighting based on equal loudness contours
            if 1000 <= center_freq <= 4000:
                weight = 1.0  # Most important frequency range
            elif 300 <= center_freq <= 8000:
                weight = 0.8  # Important range
            elif 100 <= center_freq <= 300 or 8000 <= center_freq <= 16000:
                weight = 0.6  # Moderately important
            else:
                weight = 0.3  # Less important

            band = CriticalBand(
                index=i,
                center_freq=center_freq,
                low_freq=low_freq,
                high_freq=high_freq,
                bandwidth=bandwidth,
                weight=weight
            )
            critical_bands.append(band)

        return critical_bands

    def _create_perceptual_weighting(self) -> np.ndarray:
        """Create perceptual weighting curve (A-weighting inspired)"""
        freqs = np.linspace(0, self.sample_rate // 2, self.fft_size // 2 + 1)

        # Simplified A-weighting-like curve
        weights = np.ones_like(freqs)

        for i, freq in enumerate(freqs):
            if freq < 20:
                weights[i] = 0.1
            elif freq < 100:
                weights[i] = 0.3
            elif freq < 1000:
                weights[i] = 0.7 + 0.3 * (freq - 100) / 900
            elif freq < 4000:
                weights[i] = 1.0  # Peak sensitivity
            elif freq < 8000:
                weights[i] = 1.0 - 0.2 * (freq - 4000) / 4000
            elif freq < 16000:
                weights[i] = 0.8 - 0.4 * (freq - 8000) / 8000
            else:
                weights[i] = 0.4 - 0.3 * min((freq - 16000) / 4000, 1.0)

        return weights

    def _create_frequency_mapping(self) -> np.ndarray:
        """Map FFT bins to critical bands"""
        freqs = np.linspace(0, self.sample_rate // 2, self.fft_size // 2 + 1)
        band_map = np.zeros(len(freqs), dtype=int)

        for i, freq in enumerate(freqs):
            # Find the critical band for this frequency
            band_idx = 0
            for j, band in enumerate(self.critical_bands):
                if band.low_freq <= freq < band.high_freq:
                    band_idx = j
                    break
                elif freq >= band.high_freq:
                    band_idx = j

            band_map[i] = min(band_idx, len(self.critical_bands) - 1)

        return band_map

    def analyze_spectrum(self, audio_chunk: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Analyze audio spectrum for adaptive EQ

        Args:
            audio_chunk: Audio data for analysis

        Returns:
            Dictionary with spectrum analysis results
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
        spectrum = fft(windowed_audio)
        magnitude = np.abs(spectrum[:self.fft_size // 2 + 1])

        # Convert to dB
        magnitude_db = 20 * np.log10(magnitude + 1e-10)

        # Calculate energy in each critical band
        band_energies = np.zeros(len(self.critical_bands))
        for i, band in enumerate(self.critical_bands):
            band_mask = self.freq_to_band_map == i
            if np.any(band_mask):
                band_energies[i] = np.mean(magnitude_db[band_mask])

        # Calculate masking thresholds
        masking_thresholds = self.masking_calculator.calculate_masking(
            magnitude, self.critical_bands
        )

        return {
            'magnitude_db': magnitude_db,
            'band_energies': band_energies,
            'masking_thresholds': masking_thresholds,
            'spectrum': spectrum
        }

    def calculate_adaptive_gains(self, spectrum_analysis: Dict[str, np.ndarray],
                                target_curve: np.ndarray,
                                content_profile: Optional[Dict] = None) -> np.ndarray:
        """
        Calculate adaptive EQ gains based on spectrum analysis

        Args:
            spectrum_analysis: Results from analyze_spectrum
            target_curve: Target frequency response curve
            content_profile: Optional content analysis for adaptation

        Returns:
            Array of gain values for each critical band
        """
        band_energies = spectrum_analysis['band_energies']
        masking_thresholds = spectrum_analysis['masking_thresholds']

        # Calculate initial gains based on target curve
        target_gains = np.zeros(len(self.critical_bands))

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

        # Content-aware adaptation
        if content_profile:
            target_gains = self._apply_content_adaptation(target_gains, content_profile)

        # Smooth transitions to avoid artifacts
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

    def _apply_content_adaptation(self, gains: np.ndarray,
                                 content_profile: Dict) -> np.ndarray:
        """Apply content-aware adaptations to EQ gains"""
        adapted_gains = gains.copy()

        # Extract content characteristics
        genre = content_profile.get('genre', 'unknown')
        energy_level = content_profile.get('energy_level', 'medium')
        spectral_centroid = content_profile.get('spectral_centroid', 2000)

        # Genre-specific adaptations
        if genre == 'classical':
            # Preserve natural tone - reduce EQ intensity
            adapted_gains *= 0.7
            # Slight treble enhancement for clarity
            for i, band in enumerate(self.critical_bands):
                if 4000 <= band.center_freq <= 8000:
                    adapted_gains[i] += 0.5

        elif genre == 'rock':
            # Enhance punch and clarity
            for i, band in enumerate(self.critical_bands):
                if 100 <= band.center_freq <= 200:  # Bass punch
                    adapted_gains[i] += 1.0
                elif 2000 <= band.center_freq <= 4000:  # Midrange clarity
                    adapted_gains[i] += 0.8

        elif genre == 'electronic':
            # Enhance bass and treble
            for i, band in enumerate(self.critical_bands):
                if 50 <= band.center_freq <= 120:  # Sub-bass
                    adapted_gains[i] += 1.5
                elif 8000 <= band.center_freq <= 16000:  # Treble sparkle
                    adapted_gains[i] += 1.0

        # Energy level adaptations
        if energy_level == 'low':
            # Boost overall presence
            adapted_gains += 0.5
        elif energy_level == 'high':
            # Be more conservative to avoid harshness
            adapted_gains *= 0.8

        # Spectral balance adaptations
        if spectral_centroid < 1500:  # Dark content
            # Boost treble for clarity
            for i, band in enumerate(self.critical_bands):
                if band.center_freq > 2000:
                    adapted_gains[i] += 1.0
        elif spectral_centroid > 4000:  # Bright content
            # Reduce treble to avoid harshness
            for i, band in enumerate(self.critical_bands):
                if band.center_freq > 4000:
                    adapted_gains[i] -= 0.5

        return adapted_gains

    def apply_eq(self, audio_chunk: np.ndarray, gains: np.ndarray) -> np.ndarray:
        """
        Apply EQ gains to audio chunk

        Args:
            audio_chunk: Input audio data
            gains: Gain values for each critical band

        Returns:
            EQ-processed audio
        """
        if len(audio_chunk) < self.fft_size:
            # Pad with zeros for processing
            padded = np.zeros((self.fft_size, audio_chunk.shape[1] if audio_chunk.ndim == 2 else 1))
            if audio_chunk.ndim == 2:
                padded[:len(audio_chunk), :] = audio_chunk
            else:
                padded[:len(audio_chunk), 0] = audio_chunk
            audio_chunk = padded.squeeze()

        # Process each channel
        if audio_chunk.ndim == 1:
            return self._apply_eq_mono(audio_chunk, gains)
        else:
            processed_channels = []
            for channel in range(audio_chunk.shape[1]):
                processed_channel = self._apply_eq_mono(audio_chunk[:, channel], gains)
                processed_channels.append(processed_channel)
            return np.column_stack(processed_channels)

    def _apply_eq_mono(self, audio_mono: np.ndarray, gains: np.ndarray) -> np.ndarray:
        """Apply EQ to mono audio"""
        # Apply window
        window = np.hanning(self.fft_size)
        windowed_audio = audio_mono[:self.fft_size] * window

        # Transform to frequency domain
        spectrum = fft(windowed_audio)

        # Apply gains to each critical band
        for i, gain_db in enumerate(gains):
            gain_linear = 10 ** (gain_db / 20)
            band_mask = self.freq_to_band_map == i

            # Apply gain to positive frequencies
            spectrum[:self.fft_size // 2 + 1][band_mask] *= gain_linear
            # Apply gain to negative frequencies (maintain symmetry)
            if i > 0:  # Skip DC component
                spectrum[self.fft_size // 2 + 1:][band_mask[1:-1][::-1]] *= gain_linear

        # Transform back to time domain
        processed_audio = np.real(ifft(spectrum))

        # Apply window compensation
        processed_audio *= window

        return processed_audio[:len(audio_mono)]

    def process_realtime_chunk(self, audio_chunk: np.ndarray,
                              target_curve: np.ndarray,
                              content_profile: Optional[Dict] = None) -> np.ndarray:
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
        self.processing_history.append({
            'gains': gains.copy(),
            'band_energies': spectrum_analysis['band_energies'].copy(),
            'content_profile': content_profile
        })

        # Limit history size
        if len(self.processing_history) > 100:
            self.processing_history.pop(0)

        return processed_chunk

    def get_current_response(self) -> Dict[str, np.ndarray]:
        """Get current EQ response"""
        freqs = np.array([band.center_freq for band in self.critical_bands])
        gains = self.current_gains

        return {
            'frequencies': freqs,
            'gains_db': gains,
            'bands': [(band.low_freq, band.high_freq) for band in self.critical_bands]
        }

    def reset(self):
        """Reset EQ to flat response"""
        self.current_gains = np.ones(len(self.critical_bands))
        self.target_gains = np.ones(len(self.critical_bands))
        self.processing_history.clear()


class MaskingThresholdCalculator:
    """Calculate psychoacoustic masking thresholds"""

    def calculate_masking(self, magnitude_spectrum: np.ndarray,
                         critical_bands: List[CriticalBand]) -> np.ndarray:
        """
        Calculate masking thresholds for each critical band

        Args:
            magnitude_spectrum: Magnitude spectrum
            critical_bands: List of critical bands

        Returns:
            Masking threshold for each band
        """
        thresholds = np.full(len(critical_bands), -60.0)  # Default threshold

        # Simplified masking calculation
        for i, band in enumerate(critical_bands):
            # Find the peak in this band
            band_start = int(band.low_freq * len(magnitude_spectrum) * 2 / 44100)
            band_end = int(band.high_freq * len(magnitude_spectrum) * 2 / 44100)
            band_start = max(0, band_start)
            band_end = min(len(magnitude_spectrum), band_end)

            if band_end > band_start:
                band_magnitude = magnitude_spectrum[band_start:band_end]
                if len(band_magnitude) > 0:
                    peak_magnitude = np.max(band_magnitude)

                    # Calculate masking threshold (simplified)
                    # In reality, this would involve complex psychoacoustic modeling
                    threshold_db = 20 * np.log10(peak_magnitude + 1e-10) - 20
                    thresholds[i] = max(threshold_db, -80.0)

        return thresholds


# Convenience functions
def create_psychoacoustic_eq(sample_rate: int = 44100,
                           fft_size: int = 4096) -> PsychoacousticEQ:
    """Create psychoacoustic EQ with default settings"""
    settings = EQSettings(
        sample_rate=sample_rate,
        fft_size=fft_size,
        overlap=0.75,
        smoothing_factor=0.1
    )
    return PsychoacousticEQ(settings)


def generate_genre_eq_curve(genre: str, num_bands: int = 25) -> np.ndarray:
    """Generate EQ curve for specific genre"""
    curves = {
        'rock': np.array([2, 1, 0, 0, 1, 2, 1, 0, -1, 0, 1, 2, 1, 0, 0, 1, 2, 1, 0, -1, 0, 0, 0, 0, 0]),
        'pop': np.array([1, 1, 0, 0, 0, 1, 1, 1, 0, 0, 1, 1, 1, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0]),
        'classical': np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0]),
        'electronic': np.array([3, 2, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 2, 2, 2, 1, 1, 1, 0, 0, 0, 0]),
        'jazz': np.array([0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0]),
        'ambient': np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 2, 2, 1, 1, 0, 0, 0, 0])
    }

    if genre.lower() in curves:
        curve = curves[genre.lower()]
        if len(curve) >= num_bands:
            return curve[:num_bands]
        else:
            # Pad with zeros if needed
            padded = np.zeros(num_bands)
            padded[:len(curve)] = curve
            return padded
    else:
        return np.zeros(num_bands)  # Flat response for unknown genres