# -*- coding: utf-8 -*-

"""
Audio Feature Extraction
~~~~~~~~~~~~~~~~~~~~~~~~

Extract comprehensive audio features for ML genre classification

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import List, Tuple

from .features import AudioFeatures
from ...dsp.unified import (
    spectral_centroid, spectral_rolloff, zero_crossing_rate,
    crest_factor, tempo_estimate
)
from ...dsp.utils import create_mel_triangular_filters
from ...utils.logging import debug
from ..fingerprint.common_metrics import SafeOperations


class FeatureExtractor:
    """Extract comprehensive audio features for ML classification"""

    def __init__(self, sample_rate: int = 44100):
        """
        Initialize feature extractor

        Args:
            sample_rate: Audio sample rate in Hz
        """
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

        # Use SafeOperations for safe division
        magnitude_sum = np.sum(magnitude)
        centroid = SafeOperations.safe_divide(np.sum(freqs * magnitude), magnitude_sum, fallback=0.0)
        bandwidth = np.sqrt(SafeOperations.safe_divide(
            np.sum(((freqs - centroid) ** 2) * magnitude),
            magnitude_sum,
            fallback=0.0
        ))

        return float(bandwidth)

    def _spectral_contrast(self, audio: np.ndarray, n_bands: int = 6) -> List[float]:
        """Calculate spectral contrast across frequency bands"""
        spectrum = np.fft.fft(audio[:4096])
        magnitude = np.abs(spectrum[:2049])

        band_edges = np.logspace(np.log10(80), np.log10(self.sample_rate/2), n_bands + 1)
        contrasts = []

        for i in range(n_bands):
            low_idx = int(band_edges[i] * 4096 / self.sample_rate)
            high_idx = int(band_edges[i+1] * 4096 / self.sample_rate)

            band_mag = magnitude[low_idx:high_idx]
            if len(band_mag) > 0:
                peak = np.percentile(band_mag, 85)
                valley = np.percentile(band_mag, 15)
                contrasts.append(float(peak - valley))
            else:
                contrasts.append(0.0)

        return contrasts

    def _spectral_flatness(self, audio: np.ndarray) -> float:
        """Calculate spectral flatness"""
        spectrum = np.fft.fft(audio[:4096])
        magnitude = np.abs(spectrum[:2049]) + 1e-10

        geometric_mean = np.exp(np.mean(np.log(magnitude)))
        arithmetic_mean = np.mean(magnitude)

        return float(geometric_mean / arithmetic_mean)

    def _tempo_stability(self, audio: np.ndarray) -> float:
        """Estimate tempo stability"""
        chunk_size = self.sample_rate * 2
        tempos = []

        for i in range(0, len(audio) - chunk_size, chunk_size):
            chunk = audio[i:i + chunk_size]
            tempo = tempo_estimate(chunk, self.sample_rate)
            if 60 <= tempo <= 200:
                tempos.append(tempo)

        if len(tempos) < 2:
            return 0.5

        tempo_std = float(np.std(tempos))
        tempo_mean = float(np.mean(tempos))
        return 1.0 - min(tempo_std / (tempo_mean + 1e-10), 1.0)

    def _onset_rate(self, audio: np.ndarray) -> float:
        """Estimate onset rate"""
        hop_size = 512
        onsets = 0
        prev_spectrum = None

        for i in range(0, len(audio) - 1024, hop_size):
            chunk = audio[i:i + 1024]
            spectrum = np.abs(np.fft.fft(chunk))

            if prev_spectrum is not None:
                flux = np.sum(np.maximum(spectrum - prev_spectrum, 0))
                if flux > np.mean(spectrum) * 0.1:
                    onsets += 1

            prev_spectrum = spectrum

        return onsets / (len(audio) / self.sample_rate)

    def _harmonic_ratio(self, audio: np.ndarray) -> float:
        """Estimate harmonic to non-harmonic ratio"""
        autocorr = np.correlate(audio[:8192], audio[:8192], mode='full')
        autocorr = autocorr[len(autocorr)//2:]

        peak_threshold = np.max(autocorr) * 0.3
        peaks = autocorr > peak_threshold

        peak_energy = np.sum(autocorr[peaks])
        total_energy = np.sum(autocorr)

        return float(peak_energy / (total_energy + 1e-10))

    def _fundamental_frequency(self, audio: np.ndarray) -> float:
        """Estimate fundamental frequency"""
        autocorr = np.correlate(audio[:8192], audio[:8192], mode='full')
        autocorr = autocorr[len(autocorr)//2:]

        min_lag = int(self.sample_rate / 800)
        max_lag = int(self.sample_rate / 80)

        if max_lag < len(autocorr):
            autocorr_segment = autocorr[min_lag:max_lag]
            if len(autocorr_segment) > 0:
                peak_lag = np.argmax(autocorr_segment) + min_lag
                return self.sample_rate / peak_lag

        return 0.0

    def _energy_distribution(self, audio: np.ndarray) -> Tuple[float, float, float]:
        """Calculate energy distribution across frequency bands"""
        spectrum = np.fft.fft(audio[:4096])
        magnitude = np.abs(spectrum[:2049]) ** 2
        freqs = np.fft.fftfreq(4096, 1/self.sample_rate)[:2049]

        low_mask = freqs <= 250
        mid_mask = (freqs > 250) & (freqs <= 4000)
        high_mask = freqs > 4000

        total_energy = np.sum(magnitude)
        energy_low = np.sum(magnitude[low_mask]) / (total_energy + 1e-10)
        energy_mid = np.sum(magnitude[mid_mask]) / (total_energy + 1e-10)
        energy_high = np.sum(magnitude[high_mask]) / (total_energy + 1e-10)

        return energy_low, energy_mid, energy_high

    def _extract_mfcc(self, audio: np.ndarray) -> List[float]:
        """Extract MFCC features (simplified)"""
        spectrum = np.fft.fft(audio[:4096])
        magnitude = np.abs(spectrum[:2049])

        mel_filters = self._create_mel_filterbank(self.n_mfcc, 2049)

        mel_energies = []
        for filt in mel_filters:
            energy = np.sum(magnitude * filt)
            mel_energies.append(max(energy, 1e-10))

        log_energies = np.log(mel_energies)

        mfcc = []
        for i in range(self.n_mfcc):
            component = 0.0
            for j, log_energy in enumerate(log_energies):
                component += log_energy * np.cos(np.pi * i * (j + 0.5) / len(log_energies))
            mfcc.append(float(component))

        return mfcc

    def _extract_chroma(self, audio: np.ndarray) -> List[float]:
        """Extract chroma features"""
        spectrum = np.fft.fft(audio[:4096])
        magnitude = np.abs(spectrum[:2049])
        freqs = np.fft.fftfreq(4096, 1/self.sample_rate)[:2049]

        chroma = np.zeros(12)

        for i, freq in enumerate(freqs):
            if freq > 80:
                midi_note = 12 * np.log2(freq / 440.0) + 69
                chroma_bin = int(midi_note) % 12
                chroma[chroma_bin] += magnitude[i]

        total_energy = np.sum(chroma)
        if total_energy > 0:
            chroma = chroma / total_energy

        return chroma.tolist()

    def _extract_tonnetz(self, audio: np.ndarray) -> List[float]:
        """Extract tonnetz features"""
        chroma = np.array(self._extract_chroma(audio))
        tonnetz = np.zeros(6)

        tonnetz[0] = np.sum(chroma * np.cos(np.arange(12) * 7 * np.pi / 6))
        tonnetz[1] = np.sum(chroma * np.sin(np.arange(12) * 7 * np.pi / 6))
        tonnetz[2] = np.sum(chroma * np.cos(np.arange(12) * 3 * np.pi / 2))
        tonnetz[3] = np.sum(chroma * np.sin(np.arange(12) * 3 * np.pi / 2))
        tonnetz[4] = np.sum(chroma * np.cos(np.arange(12) * 2 * np.pi / 3))
        tonnetz[5] = np.sum(chroma * np.sin(np.arange(12) * 2 * np.pi / 3))

        return tonnetz.tolist()

    def _create_mel_filterbank(self, n_filters: int, n_fft: int) -> List[np.ndarray]:
        """Create mel-scale filter bank using vectorized helper"""
        return create_mel_triangular_filters(n_filters, n_fft, self.sample_rate)
