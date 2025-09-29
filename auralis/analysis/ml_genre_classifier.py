# -*- coding: utf-8 -*-

"""
ML-Based Genre Classification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Machine learning-based genre classification for adaptive audio mastering

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Advanced genre classification using machine learning techniques
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import json
from pathlib import Path

from ..dsp.unified import (
    spectral_centroid, spectral_rolloff, zero_crossing_rate,
    crest_factor, tempo_estimate
)
from ..utils.logging import debug, info


@dataclass
class AudioFeatures:
    """Comprehensive audio features for ML classification"""
    # Basic acoustic features
    rms: float
    peak: float
    crest_factor_db: float
    zero_crossing_rate: float

    # Spectral features
    spectral_centroid: float
    spectral_rolloff: float
    spectral_bandwidth: float
    spectral_contrast: List[float]
    spectral_flatness: float

    # Temporal features
    tempo: float
    tempo_stability: float
    onset_rate: float

    # Harmonic features
    harmonic_ratio: float
    fundamental_frequency: float

    # Energy distribution
    energy_low: float      # 0-250 Hz
    energy_mid: float      # 250-4000 Hz
    energy_high: float     # 4000+ Hz

    # Advanced features
    mfcc: List[float]      # Mel-frequency cepstral coefficients
    chroma: List[float]    # Chromagram features
    tonnetz: List[float]   # Tonal centroid features


class FeatureExtractor:
    """Extract comprehensive audio features for ML classification"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.n_mfcc = 13
        self.n_chroma = 12
        self.n_tonnetz = 6

    def extract_features(self, audio: np.ndarray) -> AudioFeatures:
        """
        Extract comprehensive features from audio

        Args:
            audio: Audio signal (mono or stereo)

        Returns:
            AudioFeatures object with all extracted features
        """
        debug("Extracting ML features for genre classification")

        # Convert to mono if stereo
        if audio.ndim == 2:
            mono_audio = np.mean(audio, axis=1)
        else:
            mono_audio = audio

        # Ensure minimum length
        if len(mono_audio) < self.sample_rate:
            # Pad with zeros if too short
            padded = np.zeros(self.sample_rate)
            padded[:len(mono_audio)] = mono_audio
            mono_audio = padded

        # Basic acoustic features
        rms_val = np.sqrt(np.mean(mono_audio ** 2))
        peak_val = np.max(np.abs(mono_audio))
        crest_factor_db = crest_factor(audio)
        zcr = zero_crossing_rate(mono_audio)

        # Spectral features
        centroid = spectral_centroid(mono_audio, self.sample_rate)
        rolloff = spectral_rolloff(mono_audio, self.sample_rate)
        bandwidth = self._spectral_bandwidth(mono_audio)
        contrast = self._spectral_contrast(mono_audio)
        flatness = self._spectral_flatness(mono_audio)

        # Temporal features
        tempo_val = tempo_estimate(mono_audio, self.sample_rate)
        tempo_stability = self._tempo_stability(mono_audio)
        onset_rate = self._onset_rate(mono_audio)

        # Harmonic features
        harmonic_ratio = self._harmonic_ratio(mono_audio)
        fundamental_freq = self._fundamental_frequency(mono_audio)

        # Energy distribution
        energy_low, energy_mid, energy_high = self._energy_distribution(mono_audio)

        # Advanced features
        mfcc_features = self._extract_mfcc(mono_audio)
        chroma_features = self._extract_chroma(mono_audio)
        tonnetz_features = self._extract_tonnetz(mono_audio)

        return AudioFeatures(
            rms=float(rms_val),
            peak=float(peak_val),
            crest_factor_db=float(crest_factor_db),
            zero_crossing_rate=float(zcr),
            spectral_centroid=float(centroid),
            spectral_rolloff=float(rolloff),
            spectral_bandwidth=float(bandwidth),
            spectral_contrast=contrast,
            spectral_flatness=float(flatness),
            tempo=float(tempo_val),
            tempo_stability=float(tempo_stability),
            onset_rate=float(onset_rate),
            harmonic_ratio=float(harmonic_ratio),
            fundamental_frequency=float(fundamental_freq),
            energy_low=float(energy_low),
            energy_mid=float(energy_mid),
            energy_high=float(energy_high),
            mfcc=mfcc_features,
            chroma=chroma_features,
            tonnetz=tonnetz_features
        )

    def _spectral_bandwidth(self, audio: np.ndarray) -> float:
        """Calculate spectral bandwidth"""
        spectrum = np.fft.fft(audio[:4096])
        magnitude = np.abs(spectrum[:2049])
        freqs = np.fft.fftfreq(4096, 1/self.sample_rate)[:2049]

        # Calculate centroid
        centroid = np.sum(freqs * magnitude) / (np.sum(magnitude) + 1e-10)

        # Calculate bandwidth as weighted standard deviation
        bandwidth = np.sqrt(np.sum(((freqs - centroid) ** 2) * magnitude) /
                           (np.sum(magnitude) + 1e-10))

        return bandwidth

    def _spectral_contrast(self, audio: np.ndarray, n_bands: int = 6) -> List[float]:
        """Calculate spectral contrast across frequency bands"""
        spectrum = np.fft.fft(audio[:4096])
        magnitude = np.abs(spectrum[:2049])

        # Define frequency bands (logarithmic spacing)
        band_edges = np.logspace(np.log10(80), np.log10(self.sample_rate/2), n_bands + 1)
        contrasts = []

        for i in range(n_bands):
            low_idx = int(band_edges[i] * 4096 / self.sample_rate)
            high_idx = int(band_edges[i+1] * 4096 / self.sample_rate)

            band_mag = magnitude[low_idx:high_idx]
            if len(band_mag) > 0:
                peak = np.percentile(band_mag, 85)
                valley = np.percentile(band_mag, 15)
                contrast = peak - valley
                contrasts.append(float(contrast))
            else:
                contrasts.append(0.0)

        return contrasts

    def _spectral_flatness(self, audio: np.ndarray) -> float:
        """Calculate spectral flatness (measure of noise-like vs tonal content)"""
        spectrum = np.fft.fft(audio[:4096])
        magnitude = np.abs(spectrum[:2049])
        magnitude = magnitude + 1e-10  # Avoid log(0)

        # Geometric mean / Arithmetic mean
        geometric_mean = np.exp(np.mean(np.log(magnitude)))
        arithmetic_mean = np.mean(magnitude)

        flatness = geometric_mean / arithmetic_mean
        return flatness

    def _tempo_stability(self, audio: np.ndarray) -> float:
        """Estimate tempo stability (consistency of beat)"""
        # Simple estimation based on autocorrelation analysis
        # This is a simplified implementation
        chunk_size = self.sample_rate * 2  # 2-second chunks
        tempos = []

        for i in range(0, len(audio) - chunk_size, chunk_size):
            chunk = audio[i:i + chunk_size]
            tempo = tempo_estimate(chunk, self.sample_rate)
            if 60 <= tempo <= 200:  # Reasonable tempo range
                tempos.append(tempo)

        if len(tempos) < 2:
            return 0.5  # Default stability

        # Calculate coefficient of variation (lower = more stable)
        tempo_std = np.std(tempos)
        tempo_mean = np.mean(tempos)
        stability = 1.0 - min(tempo_std / (tempo_mean + 1e-10), 1.0)

        return stability

    def _onset_rate(self, audio: np.ndarray) -> float:
        """Estimate onset rate (number of note onsets per second)"""
        # Simplified onset detection using spectral flux
        hop_size = 512
        onsets = 0
        prev_spectrum = None

        for i in range(0, len(audio) - 1024, hop_size):
            chunk = audio[i:i + 1024]
            spectrum = np.abs(np.fft.fft(chunk))

            if prev_spectrum is not None:
                # Spectral flux (positive changes in spectrum)
                flux = np.sum(np.maximum(spectrum - prev_spectrum, 0))
                if flux > np.mean(spectrum) * 0.1:  # Threshold for onset
                    onsets += 1

            prev_spectrum = spectrum

        duration_seconds = len(audio) / self.sample_rate
        onset_rate = onsets / duration_seconds

        return onset_rate

    def _harmonic_ratio(self, audio: np.ndarray) -> float:
        """Estimate ratio of harmonic to non-harmonic content"""
        # Simplified harmonic analysis using autocorrelation
        autocorr = np.correlate(audio[:8192], audio[:8192], mode='full')
        autocorr = autocorr[len(autocorr)//2:]

        # Find peaks that might indicate periodicity
        peak_threshold = np.max(autocorr) * 0.3
        peaks = autocorr > peak_threshold

        # Ratio of energy in peaks vs total
        peak_energy = np.sum(autocorr[peaks])
        total_energy = np.sum(autocorr)

        harmonic_ratio = peak_energy / (total_energy + 1e-10)
        return harmonic_ratio

    def _fundamental_frequency(self, audio: np.ndarray) -> float:
        """Estimate fundamental frequency using autocorrelation"""
        # Simplified F0 estimation
        autocorr = np.correlate(audio[:8192], audio[:8192], mode='full')
        autocorr = autocorr[len(autocorr)//2:]

        # Find the first significant peak after lag 0
        min_lag = int(self.sample_rate / 800)  # Minimum F0 of ~800 Hz
        max_lag = int(self.sample_rate / 80)   # Maximum F0 of ~80 Hz

        if max_lag < len(autocorr):
            autocorr_segment = autocorr[min_lag:max_lag]
            if len(autocorr_segment) > 0:
                peak_lag = np.argmax(autocorr_segment) + min_lag
                f0 = self.sample_rate / peak_lag
                return f0

        return 0.0  # No clear fundamental found

    def _energy_distribution(self, audio: np.ndarray) -> Tuple[float, float, float]:
        """Calculate energy distribution across frequency bands"""
        spectrum = np.fft.fft(audio[:4096])
        magnitude = np.abs(spectrum[:2049]) ** 2  # Power spectrum
        freqs = np.fft.fftfreq(4096, 1/self.sample_rate)[:2049]

        # Define frequency band boundaries
        low_mask = freqs <= 250
        mid_mask = (freqs > 250) & (freqs <= 4000)
        high_mask = freqs > 4000

        # Calculate energy in each band
        total_energy = np.sum(magnitude)
        energy_low = np.sum(magnitude[low_mask]) / (total_energy + 1e-10)
        energy_mid = np.sum(magnitude[mid_mask]) / (total_energy + 1e-10)
        energy_high = np.sum(magnitude[high_mask]) / (total_energy + 1e-10)

        return energy_low, energy_mid, energy_high

    def _extract_mfcc(self, audio: np.ndarray) -> List[float]:
        """Extract MFCC features (simplified implementation)"""
        # This is a simplified MFCC implementation
        # For production, would use librosa or similar library

        spectrum = np.fft.fft(audio[:4096])
        magnitude = np.abs(spectrum[:2049])

        # Mel filter bank (simplified)
        n_filters = self.n_mfcc
        mel_filters = self._create_mel_filterbank(n_filters, 2049)

        # Apply filters
        mel_energies = []
        for filt in mel_filters:
            energy = np.sum(magnitude * filt)
            mel_energies.append(max(energy, 1e-10))

        # Take log and DCT
        log_energies = np.log(mel_energies)

        # Simplified DCT (just take first few components)
        mfcc = []
        for i in range(self.n_mfcc):
            component = 0.0
            for j, log_energy in enumerate(log_energies):
                component += log_energy * np.cos(np.pi * i * (j + 0.5) / len(log_energies))
            mfcc.append(float(component))

        return mfcc

    def _extract_chroma(self, audio: np.ndarray) -> List[float]:
        """Extract chroma features (pitch class profile)"""
        spectrum = np.fft.fft(audio[:4096])
        magnitude = np.abs(spectrum[:2049])
        freqs = np.fft.fftfreq(4096, 1/self.sample_rate)[:2049]

        # Initialize chroma bins (12 semitones)
        chroma = np.zeros(12)

        for i, freq in enumerate(freqs):
            if freq > 80:  # Ignore very low frequencies
                # Convert frequency to MIDI note number
                midi_note = 12 * np.log2(freq / 440.0) + 69
                # Map to chroma bin (0-11)
                chroma_bin = int(midi_note) % 12
                chroma[chroma_bin] += magnitude[i]

        # Normalize
        total_energy = np.sum(chroma)
        if total_energy > 0:
            chroma = chroma / total_energy

        return chroma.tolist()

    def _extract_tonnetz(self, audio: np.ndarray) -> List[float]:
        """Extract tonnetz (tonal centroid) features"""
        # Simplified tonnetz implementation
        chroma = np.array(self._extract_chroma(audio))

        # Tonnetz coordinates based on chroma
        tonnetz = np.zeros(6)

        # Circle of fifths coordinates
        tonnetz[0] = np.sum(chroma * np.cos(np.arange(12) * 7 * np.pi / 6))
        tonnetz[1] = np.sum(chroma * np.sin(np.arange(12) * 7 * np.pi / 6))

        # Minor third coordinates
        tonnetz[2] = np.sum(chroma * np.cos(np.arange(12) * 3 * np.pi / 2))
        tonnetz[3] = np.sum(chroma * np.sin(np.arange(12) * 3 * np.pi / 2))

        # Major third coordinates
        tonnetz[4] = np.sum(chroma * np.cos(np.arange(12) * 2 * np.pi / 3))
        tonnetz[5] = np.sum(chroma * np.sin(np.arange(12) * 2 * np.pi / 3))

        return tonnetz.tolist()

    def _create_mel_filterbank(self, n_filters: int, n_fft: int) -> List[np.ndarray]:
        """Create mel-scale filter bank"""
        # Simplified mel filterbank
        filters = []
        mel_points = np.linspace(0, 2595 * np.log10(1 + (self.sample_rate/2) / 700), n_filters + 2)
        hz_points = 700 * (10**(mel_points / 2595) - 1)
        bin_points = np.floor((n_fft * 2) * hz_points / self.sample_rate).astype(int)

        for i in range(n_filters):
            filt = np.zeros(n_fft)
            start, center, end = bin_points[i:i+3]

            # Rising edge
            for j in range(start, center):
                if j < len(filt):
                    filt[j] = (j - start) / (center - start)

            # Falling edge
            for j in range(center, end):
                if j < len(filt):
                    filt[j] = (end - j) / (end - center)

            filters.append(filt)

        return filters


class MLGenreClassifier:
    """
    Machine Learning-based genre classifier

    Uses extracted audio features to classify music genres
    """

    def __init__(self, model_path: Optional[str] = None):
        self.feature_extractor = FeatureExtractor()
        self.genres = [
            "classical", "rock", "electronic", "jazz", "pop",
            "hip_hop", "acoustic", "ambient", "metal", "country"
        ]

        # Model weights (this would normally be loaded from a trained model)
        self.weights = self._initialize_weights()
        self.confidence_threshold = 0.6

        debug(f"ML Genre Classifier initialized with {len(self.genres)} genres")

    def _initialize_weights(self) -> Dict[str, Dict[str, float]]:
        """Initialize model weights (placeholder for trained model)"""
        # This is a simplified linear model representation
        # In production, this would be replaced with actual trained model weights

        weights = {}
        for genre in self.genres:
            weights[genre] = {
                # Basic acoustic features
                'rms': np.random.normal(0, 0.1),
                'crest_factor_db': np.random.normal(0, 0.1),
                'zero_crossing_rate': np.random.normal(0, 0.1),

                # Spectral features
                'spectral_centroid': np.random.normal(0, 0.1),
                'spectral_rolloff': np.random.normal(0, 0.1),
                'spectral_bandwidth': np.random.normal(0, 0.1),
                'spectral_flatness': np.random.normal(0, 0.1),

                # Temporal features
                'tempo': np.random.normal(0, 0.1),
                'tempo_stability': np.random.normal(0, 0.1),
                'onset_rate': np.random.normal(0, 0.1),

                # Harmonic features
                'harmonic_ratio': np.random.normal(0, 0.1),

                # Energy distribution
                'energy_low': np.random.normal(0, 0.1),
                'energy_mid': np.random.normal(0, 0.1),
                'energy_high': np.random.normal(0, 0.1),

                # Bias term
                'bias': np.random.normal(0, 0.1)
            }

        # Add some genre-specific biases to make the classifier more realistic
        self._apply_genre_specific_weights(weights)

        return weights

    def _apply_genre_specific_weights(self, weights: Dict[str, Dict[str, float]]):
        """Apply genre-specific weight adjustments"""

        # Electronic music characteristics
        weights['electronic']['spectral_centroid'] = 0.3  # Brighter
        weights['electronic']['energy_high'] = 0.4        # More high-frequency energy
        weights['electronic']['tempo'] = 0.2              # Often faster

        # Classical music characteristics
        weights['classical']['crest_factor_db'] = 0.5     # Higher dynamic range
        weights['classical']['harmonic_ratio'] = 0.4      # More harmonic content
        weights['classical']['spectral_flatness'] = -0.3  # Less noise-like

        # Rock music characteristics
        weights['rock']['energy_mid'] = 0.4               # Strong midrange
        weights['rock']['onset_rate'] = 0.3               # More attacks
        weights['rock']['rms'] = 0.2                      # Generally louder

        # Jazz characteristics
        weights['jazz']['harmonic_ratio'] = 0.3           # Complex harmonies
        weights['jazz']['tempo_stability'] = -0.2         # More tempo variation
        weights['jazz']['crest_factor_db'] = 0.3          # Dynamic playing

        # Hip-hop characteristics
        weights['hip_hop']['energy_low'] = 0.5            # Strong bass
        weights['hip_hop']['onset_rate'] = 0.4            # Rhythmic attacks
        weights['hip_hop']['tempo'] = 0.1                 # Moderate tempo

        # Ambient characteristics
        weights['ambient']['tempo'] = -0.4                # Slower
        weights['ambient']['onset_rate'] = -0.5           # Fewer attacks
        weights['ambient']['spectral_flatness'] = 0.2    # More atmospheric

    def classify(self, audio: np.ndarray) -> Dict[str, Any]:
        """
        Classify audio genre using ML model

        Args:
            audio: Audio signal to classify

        Returns:
            Dictionary with classification results
        """
        debug("Running ML genre classification")

        # Extract features
        features = self.feature_extractor.extract_features(audio)

        # Calculate scores for each genre
        scores = {}
        for genre in self.genres:
            score = self._calculate_genre_score(features, genre)
            scores[genre] = score

        # Apply softmax for probability distribution
        probabilities = self._softmax(list(scores.values()))
        genre_probs = dict(zip(self.genres, probabilities))

        # Find the most likely genre
        primary_genre = max(genre_probs, key=genre_probs.get)
        confidence = genre_probs[primary_genre]

        # If confidence is too low, fall back to "pop" as safe default
        if confidence < self.confidence_threshold:
            primary_genre = "pop"
            confidence = 0.5

        debug(f"ML Classification result: {primary_genre} (confidence: {confidence:.3f})")

        return {
            "primary": primary_genre,
            "confidence": float(confidence),
            "probabilities": {k: float(v) for k, v in genre_probs.items()},
            "features_used": self._get_feature_importance(features, primary_genre)
        }

    def _calculate_genre_score(self, features: AudioFeatures, genre: str) -> float:
        """Calculate classification score for a specific genre"""
        weights = self.weights[genre]
        score = weights['bias']

        # Add weighted feature contributions
        score += features.rms * weights['rms']
        score += features.crest_factor_db * weights['crest_factor_db']
        score += features.zero_crossing_rate * weights['zero_crossing_rate']
        score += features.spectral_centroid * weights['spectral_centroid'] / 1000  # Normalize
        score += features.spectral_rolloff * weights['spectral_rolloff'] / 1000
        score += features.spectral_bandwidth * weights['spectral_bandwidth'] / 1000
        score += features.spectral_flatness * weights['spectral_flatness']
        score += features.tempo * weights['tempo'] / 100  # Normalize
        score += features.tempo_stability * weights['tempo_stability']
        score += features.onset_rate * weights['onset_rate']
        score += features.harmonic_ratio * weights['harmonic_ratio']
        score += features.energy_low * weights['energy_low']
        score += features.energy_mid * weights['energy_mid']
        score += features.energy_high * weights['energy_high']

        return score

    def _softmax(self, scores: List[float]) -> List[float]:
        """Apply softmax to convert scores to probabilities"""
        scores_array = np.array(scores)
        exp_scores = np.exp(scores_array - np.max(scores_array))  # Numerical stability
        probabilities = exp_scores / np.sum(exp_scores)
        return probabilities.tolist()

    def _get_feature_importance(self, features: AudioFeatures, genre: str) -> Dict[str, float]:
        """Get feature importance for the classified genre"""
        weights = self.weights[genre]

        # Calculate absolute importance of each feature
        importance = {
            'spectral': abs(weights['spectral_centroid']) + abs(weights['spectral_rolloff']),
            'temporal': abs(weights['tempo']) + abs(weights['onset_rate']),
            'energy': abs(weights['energy_low']) + abs(weights['energy_mid']) + abs(weights['energy_high']),
            'harmonic': abs(weights['harmonic_ratio']),
            'dynamics': abs(weights['crest_factor_db']) + abs(weights['rms'])
        }

        # Normalize
        total_importance = sum(importance.values())
        if total_importance > 0:
            importance = {k: v / total_importance for k, v in importance.items()}

        return importance

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the classifier model"""
        return {
            "model_type": "Linear Feature-based Classifier",
            "num_genres": len(self.genres),
            "genres": self.genres,
            "confidence_threshold": self.confidence_threshold,
            "feature_count": {
                "basic": 4,
                "spectral": 7,
                "temporal": 3,
                "harmonic": 2,
                "energy": 3,
                "advanced": 31  # MFCC + Chroma + Tonnetz
            }
        }


def create_ml_genre_classifier(model_path: Optional[str] = None) -> MLGenreClassifier:
    """
    Factory function to create ML genre classifier

    Args:
        model_path: Optional path to saved model weights

    Returns:
        Configured MLGenreClassifier instance
    """
    return MLGenreClassifier(model_path)