# -*- coding: utf-8 -*-

"""
Frequency Operations
~~~~~~~~~~~~~~~~~~~~

Common frequency analysis patterns for quality assessments.

Provides shared frequency analysis functions used across all quality assessors
to ensure consistency in frequency balance, weighting, and band analysis.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Optional, Tuple, List, Dict
import numpy as np


class FrequencyOperations:
    """Common frequency analysis patterns for quality assessments"""

    @staticmethod
    def apply_a_weighting(frequencies: np.ndarray,
                         magnitudes: np.ndarray) -> np.ndarray:
        """
        Apply A-weighting curve (ISO 61672-1)

        A-weighting emphasizes frequencies important to human hearing,
        reducing sensitivity to very low and very high frequencies.

        Args:
            frequencies: Frequency array in Hz
            magnitudes: Magnitude spectrum (linear or dB)

        Returns:
            A-weighted magnitude spectrum (in dB)
        """
        # A-weighting coefficients at reference frequencies
        ref_freq = np.array([31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000])
        ref_weights = np.array([-39.4, -26.2, -16.1, -8.6, -3.2, 0.0, 1.2, 1.0, -1.1, -6.6])

        # Interpolate weights for given frequencies
        weights = np.interp(frequencies, ref_freq, ref_weights)

        # Apply weighting
        if magnitudes.ndim == 1:
            # Assume linear magnitude, convert to dB
            mag_db = 20 * np.log10(np.maximum(magnitudes, 1e-10))
        else:
            mag_db = magnitudes

        return mag_db + weights

    @staticmethod
    def apply_c_weighting(frequencies: np.ndarray,
                         magnitudes: np.ndarray) -> np.ndarray:
        """
        Apply C-weighting curve (ISO 61672-1)

        C-weighting is flatter than A-weighting, used for high-level
        sound measurement and industrial noise assessment.

        Args:
            frequencies: Frequency array in Hz
            magnitudes: Magnitude spectrum (linear or dB)

        Returns:
            C-weighted magnitude spectrum (in dB)
        """
        # C-weighting coefficients at reference frequencies
        ref_freq = np.array([31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000])
        ref_weights = np.array([-3.0, -0.8, 0.0, 0.0, 0.0, 0.0, -0.2, -0.8, -3.4, -8.5])

        # Interpolate weights for given frequencies
        weights = np.interp(frequencies, ref_freq, ref_weights)

        # Apply weighting
        if magnitudes.ndim == 1:
            # Assume linear magnitude, convert to dB
            mag_db = 20 * np.log10(np.maximum(magnitudes, 1e-10))
        else:
            mag_db = magnitudes

        return mag_db + weights

    @staticmethod
    def compute_frequency_bands(frequencies: np.ndarray,
                               magnitudes: np.ndarray,
                               num_bands: int = 10) -> Dict[str, np.ndarray]:
        """
        Divide frequency spectrum into logarithmic bands

        Implements equal logarithmic spacing commonly used in audio analysis.

        Args:
            frequencies: Frequency array in Hz
            magnitudes: Magnitude spectrum
            num_bands: Number of bands to create (default 10)

        Returns:
            Dictionary with band data: {
                'frequencies': center frequencies,
                'magnitudes': energy in each band,
                'low_edges': lower edge of each band,
                'high_edges': upper edge of each band
            }
        """
        min_freq = 20  # Hz
        max_freq = 20000  # Hz

        # Logarithmic band edges
        log_edges = np.logspace(np.log10(min_freq), np.log10(max_freq), num_bands + 1)
        band_centers = np.sqrt(log_edges[:-1] * log_edges[1:])

        # Energy in each band
        band_magnitudes = np.zeros(num_bands)
        for i in range(num_bands):
            mask = (frequencies >= log_edges[i]) & (frequencies < log_edges[i + 1])
            if np.any(mask):
                band_magnitudes[i] = np.mean(magnitudes[mask])
            else:
                band_magnitudes[i] = np.min(magnitudes)

        return {
            'frequencies': band_centers,
            'magnitudes': band_magnitudes,
            'low_edges': log_edges[:-1],
            'high_edges': log_edges[1:]
        }

    @staticmethod
    def analyze_frequency_balance(audio: np.ndarray,
                                 sr: int = 44100,
                                 num_bands: int = 3) -> Dict[str, float]:
        """
        Analyze frequency balance (bass, mids, treble)

        Divides spectrum into bass, mid, and treble bands and compares
        energy levels for frequency balance assessment.

        Args:
            audio: Audio data (mono or stereo)
            sr: Sample rate
            num_bands: Number of bands (default 3 for bass/mid/treble)

        Returns:
            Dictionary with band energy ratios and balance metrics
        """
        if audio.ndim == 2:
            audio_mono = np.mean(audio, axis=1)
        else:
            audio_mono = audio

        # Compute FFT
        fft_result = np.fft.rfft(audio_mono)
        magnitude = np.abs(fft_result)
        frequencies = np.fft.rfftfreq(len(audio_mono), 1 / sr)

        # Define frequency bands
        bass_mask = (frequencies >= 20) & (frequencies < 250)
        mids_mask = (frequencies >= 250) & (frequencies < 2000)
        treble_mask = (frequencies >= 2000) & (frequencies < 20000)

        # Compute energy in each band
        bass_energy = np.sqrt(np.mean(magnitude[bass_mask] ** 2)) if np.any(bass_mask) else 0.0
        mids_energy = np.sqrt(np.mean(magnitude[mids_mask] ** 2)) if np.any(mids_mask) else 0.0
        treble_energy = np.sqrt(np.mean(magnitude[treble_mask] ** 2)) if np.any(treble_mask) else 0.0

        total_energy = bass_energy + mids_energy + treble_energy
        if total_energy == 0:
            return {
                'bass_ratio': 0.0,
                'mids_ratio': 0.0,
                'treble_ratio': 0.0,
                'bass_treble_ratio': 0.0,
                'balance_deviation': 0.0
            }

        bass_ratio = bass_energy / total_energy
        mids_ratio = mids_energy / total_energy
        treble_ratio = treble_energy / total_energy

        # Balance metrics
        bass_treble_ratio = bass_energy / (treble_energy + 1e-10)
        ideal_ratio = 1.0
        balance_deviation = abs(bass_treble_ratio - ideal_ratio)

        return {
            'bass_ratio': float(bass_ratio),
            'mids_ratio': float(mids_ratio),
            'treble_ratio': float(treble_ratio),
            'bass_treble_ratio': float(bass_treble_ratio),
            'balance_deviation': float(balance_deviation)
        }

    @staticmethod
    def detect_frequency_peaks(audio: np.ndarray,
                              sr: int = 44100,
                              threshold_db: float = 6.0,
                              min_peak_width: int = 3) -> List[Dict[str, Any]]:
        """
        Detect prominent frequency peaks

        Identifies peaks in the magnitude spectrum that exceed threshold.

        Args:
            audio: Audio data
            sr: Sample rate
            threshold_db: Minimum peak prominence in dB above average
            min_peak_width: Minimum peak width in FFT bins

        Returns:
            List of peak dictionaries: {
                'frequency': peak frequency in Hz,
                'magnitude_db': peak magnitude in dB,
                'prominence': prominence above baseline
            }
        """
        if audio.ndim == 2:
            audio_mono = np.mean(audio, axis=1)
        else:
            audio_mono = audio

        # Compute FFT
        fft_result = np.fft.rfft(audio_mono)
        magnitude_db = 20 * np.log10(np.abs(fft_result) + 1e-10)
        frequencies = np.fft.rfftfreq(len(audio_mono), 1 / sr)

        # Smooth to reduce noise
        from scipy.ndimage import gaussian_filter1d
        smoothed = gaussian_filter1d(magnitude_db, sigma=2.0)

        # Find peaks (local maxima)
        peaks = []
        for i in range(min_peak_width, len(smoothed) - min_peak_width):
            if smoothed[i] > smoothed[i - 1] and smoothed[i] > smoothed[i + 1]:
                prominence = smoothed[i] - np.mean(smoothed[max(0, i - 5):min(len(smoothed), i + 5)])
                if prominence > threshold_db:
                    peaks.append({
                        'frequency': float(frequencies[i]),
                        'magnitude_db': float(magnitude_db[i]),
                        'prominence': float(prominence)
                    })

        # Sort by prominence
        peaks.sort(key=lambda x: x['prominence'], reverse=True)
        return peaks[:10]  # Return top 10 peaks

    @staticmethod
    def estimate_spectral_centroid(audio: np.ndarray,
                                  sr: int = 44100) -> float:
        """
        Estimate spectral centroid

        The "center of mass" of the frequency spectrum. Higher values
        indicate brighter-sounding audio.

        Args:
            audio: Audio data
            sr: Sample rate

        Returns:
            Spectral centroid in Hz
        """
        if audio.ndim == 2:
            audio_mono = np.mean(audio, axis=1)
        else:
            audio_mono = audio

        # Compute FFT
        fft_result = np.fft.rfft(audio_mono)
        magnitude = np.abs(fft_result)
        frequencies = np.fft.rfftfreq(len(audio_mono), 1 / sr)

        # Spectral centroid
        centroid = np.sum(frequencies * magnitude) / (np.sum(magnitude) + 1e-10)

        return float(centroid)

    @staticmethod
    def estimate_spectral_spread(audio: np.ndarray,
                                sr: int = 44100) -> float:
        """
        Estimate spectral spread

        Measures how spread out the frequency content is around the centroid.
        Higher values indicate more distributed frequency content.

        Args:
            audio: Audio data
            sr: Sample rate

        Returns:
            Spectral spread in Hz
        """
        if audio.ndim == 2:
            audio_mono = np.mean(audio, axis=1)
        else:
            audio_mono = audio

        # Compute FFT
        fft_result = np.fft.rfft(audio_mono)
        magnitude = np.abs(fft_result)
        frequencies = np.fft.rfftfreq(len(audio_mono), 1 / sr)

        # Spectral centroid
        centroid = FrequencyOperations.estimate_spectral_centroid(audio, sr)

        # Spectral spread (standard deviation of frequencies)
        spread = np.sqrt(np.sum(magnitude * (frequencies - centroid) ** 2) / (np.sum(magnitude) + 1e-10))

        return float(spread)

    @staticmethod
    def detect_frequency_anomalies(audio: np.ndarray,
                                  sr: int = 44100,
                                 reference_audio: Optional[np.ndarray] = None,
                                  threshold_db: float = 3.0) -> Dict[str, any]:
        """
        Detect frequency anomalies (unexpected peaks or valleys)

        Identifies unusual frequency characteristics by comparing against
        a reference or baseline spectrum.

        Args:
            audio: Audio data to analyze
            sr: Sample rate
            reference_audio: Optional reference for comparison
            threshold_db: Detection threshold in dB

        Returns:
            Dictionary with anomaly detection results
        """
        if audio.ndim == 2:
            audio_mono = np.mean(audio, axis=1)
        else:
            audio_mono = audio

        # Compute FFT
        fft_result = np.fft.rfft(audio_mono)
        magnitude_db = 20 * np.log10(np.abs(fft_result) + 1e-10)

        # Baseline spectrum (smoothed)
        from scipy.ndimage import gaussian_filter1d
        baseline = gaussian_filter1d(magnitude_db, sigma=5.0)

        # Deviations from baseline
        deviations = magnitude_db - baseline
        peaks_anomaly = np.sum(deviations > threshold_db)
        valleys_anomaly = np.sum(deviations < -threshold_db)

        # If reference provided, compare
        if reference_audio is not None:
            if reference_audio.ndim == 2:
                ref_mono = np.mean(reference_audio, axis=1)
            else:
                ref_mono = reference_audio

            ref_fft = np.fft.rfft(ref_mono)
            ref_mag_db = 20 * np.log10(np.abs(ref_fft) + 1e-10)

            # Difference from reference
            diff = magnitude_db - ref_mag_db
            anomaly_score = float(np.sqrt(np.mean(diff ** 2)))
        else:
            anomaly_score = float(np.sqrt(np.mean(deviations ** 2)))

        return {
            'peak_anomalies': int(peaks_anomaly),
            'valley_anomalies': int(valleys_anomaly),
            'anomaly_score': anomaly_score,
            'has_anomalies': (peaks_anomaly + valleys_anomaly) > 0
        }

    @staticmethod
    def compute_crest_factor(audio: np.ndarray,
                           sr: int = 44100,
                           frame_duration: float = 0.05) -> float:
        """
        Compute crest factor (peak-to-average ratio)

        Measures dynamic range within frequency domain. Higher values
        indicate more dynamic content.

        Args:
            audio: Audio data
            sr: Sample rate
            frame_duration: Analysis frame duration

        Returns:
            Crest factor in dB
        """
        if audio.ndim == 2:
            audio_mono = np.mean(audio, axis=1)
        else:
            audio_mono = audio

        # Frame-based analysis
        frame_size = int(sr * frame_duration)
        crest_factors = []

        for i in range(0, len(audio_mono) - frame_size, frame_size):
            frame = audio_mono[i:i + frame_size]

            # Compute FFT for this frame
            fft_result = np.fft.rfft(frame)
            magnitude = np.abs(fft_result)

            peak_mag = np.max(magnitude)
            mean_mag = np.mean(magnitude)

            if mean_mag > 0:
                crest = peak_mag / mean_mag
                crest_factors.append(crest)

        if not crest_factors:
            return 0.0

        avg_crest = np.mean(crest_factors)
        crest_factor_db = 20 * np.log10(avg_crest + 1e-10)

        return float(max(0, crest_factor_db))
