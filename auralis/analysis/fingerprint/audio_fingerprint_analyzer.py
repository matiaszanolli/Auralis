"""
Audio Fingerprint Analyzer

Unified analyzer that extracts a complete 25D fingerprint from audio.

Combines:
  - Frequency analysis (7D): sub-bass, bass, low-mid, mid, upper-mid, presence, air
  - Dynamics analysis (3D): LUFS, crest factor, bass/mid ratio
  - Temporal analysis (4D): tempo, rhythm stability, transient density, silence ratio
  - Spectral analysis (3D): spectral centroid, rolloff, flatness
  - Harmonic analysis (3D): harmonic ratio, pitch stability, chroma energy
  - Variation analysis (3D): dynamic range variation, loudness variation, peak consistency
  - Stereo analysis (2D): stereo width, phase correlation

Total: 25 dimensions capturing frequency, dynamics, temporal, spectral, harmonic, variation, and stereo characteristics.

Dependencies:
  - numpy for numerical operations
  - librosa for advanced audio analysis
  - All individual analyzer modules
"""

import numpy as np
import logging
from typing import Dict

from auralis.analysis.fingerprint.temporal_analyzer import TemporalAnalyzer
from auralis.analysis.fingerprint.spectral_analyzer import SpectralAnalyzer
from auralis.analysis.fingerprint.harmonic_analyzer import HarmonicAnalyzer
from auralis.analysis.fingerprint.variation_analyzer import VariationAnalyzer
from auralis.analysis.fingerprint.stereo_analyzer import StereoAnalyzer

logger = logging.getLogger(__name__)


class AudioFingerprintAnalyzer:
    """Extract complete 25D audio fingerprint."""

    def __init__(self):
        """Initialize all sub-analyzers."""
        self.temporal_analyzer = TemporalAnalyzer()
        self.spectral_analyzer = SpectralAnalyzer()
        self.harmonic_analyzer = HarmonicAnalyzer()
        self.variation_analyzer = VariationAnalyzer()
        self.stereo_analyzer = StereoAnalyzer()

    def analyze(self, audio: np.ndarray, sr: int) -> Dict[str, float]:
        """
        Extract complete 25D audio fingerprint.

        Args:
            audio: Audio signal (stereo or mono)
            sr: Sample rate

        Returns:
            Dict with 25 fingerprint features:

            Frequency (7D):
              - sub_bass_pct: 20-60 Hz energy percentage
              - bass_pct: 60-250 Hz energy percentage
              - low_mid_pct: 250-500 Hz energy percentage
              - mid_pct: 500-2000 Hz energy percentage
              - upper_mid_pct: 2000-4000 Hz energy percentage
              - presence_pct: 4000-6000 Hz energy percentage
              - air_pct: 6000-20000 Hz energy percentage

            Dynamics (3D):
              - lufs: Integrated loudness (ITU-R BS.1770-4)
              - crest_db: Peak-to-RMS ratio in dB
              - bass_mid_ratio: Bass/Mid energy ratio in dB

            Temporal (4D):
              - tempo_bpm: Detected tempo
              - rhythm_stability: Beat consistency (0-1)
              - transient_density: Drum/percussion prominence (0-1)
              - silence_ratio: Silence/space proportion (0-1)

            Spectral (3D):
              - spectral_centroid: Brightness (0-1)
              - spectral_rolloff: High-frequency content (0-1)
              - spectral_flatness: Noise-like vs tonal (0-1)

            Harmonic (3D):
              - harmonic_ratio: Harmonic vs percussive (0-1)
              - pitch_stability: Pitch consistency (0-1)
              - chroma_energy: Tonal complexity (0-1)

            Variation (3D):
              - dynamic_range_variation: Crest factor std dev over time (0-1)
              - loudness_variation_std: Loudness consistency (0-1)
              - peak_consistency: Peak level consistency (0-1)

            Stereo (2D):
              - stereo_width: Mono (0) to wide stereo (1)
              - phase_correlation: -1 (out of phase) to +1 (in phase)
        """
        try:
            # Convert to mono for most analysis (except stereo analyzer)
            if len(audio.shape) > 1:
                audio_mono = np.mean(audio, axis=0) if audio.shape[0] == 2 else np.mean(audio, axis=1)
            else:
                audio_mono = audio

            # Initialize fingerprint dict
            fingerprint = {}

            # 1. Frequency analysis (7D)
            frequency_features = self._analyze_frequency(audio_mono, sr)
            fingerprint.update(frequency_features)

            # 2. Dynamics analysis (3D)
            dynamics_features = self._analyze_dynamics(audio_mono, sr)
            fingerprint.update(dynamics_features)

            # 3. Temporal analysis (4D)
            temporal_features = self.temporal_analyzer.analyze(audio_mono, sr)
            fingerprint.update(temporal_features)

            # 4. Spectral analysis (3D)
            spectral_features = self.spectral_analyzer.analyze(audio_mono, sr)
            fingerprint.update(spectral_features)

            # 5. Harmonic analysis (3D)
            harmonic_features = self.harmonic_analyzer.analyze(audio_mono, sr)
            fingerprint.update(harmonic_features)

            # 6. Variation analysis (3D)
            variation_features = self.variation_analyzer.analyze(audio_mono, sr)
            fingerprint.update(variation_features)

            # 7. Stereo analysis (2D) - uses original stereo audio
            stereo_features = self.stereo_analyzer.analyze(audio, sr)
            fingerprint.update(stereo_features)

            return fingerprint

        except Exception as e:
            logger.error(f"Audio fingerprint analysis failed: {e}")
            return self._get_default_fingerprint()

    def _analyze_frequency(self, audio: np.ndarray, sr: int) -> Dict[str, float]:
        """
        Analyze frequency distribution (7-band).

        Args:
            audio: Audio signal (mono)
            sr: Sample rate

        Returns:
            Dict with 7 frequency band percentages
        """
        try:
            # Compute FFT
            fft = np.fft.rfft(audio)
            magnitude = np.abs(fft)
            freqs = np.fft.rfftfreq(len(audio), 1/sr)

            # Define 7 frequency bands
            bands = {
                'sub_bass_pct': (20, 60),
                'bass_pct': (60, 250),
                'low_mid_pct': (250, 500),
                'mid_pct': (500, 2000),
                'upper_mid_pct': (2000, 4000),
                'presence_pct': (4000, 6000),
                'air_pct': (6000, 20000)
            }

            # Calculate energy per band
            band_energies = {}
            total_energy = 0

            for band_name, (low, high) in bands.items():
                mask = (freqs >= low) & (freqs < high)
                energy = np.sum(magnitude[mask] ** 2)
                band_energies[band_name] = energy
                total_energy += energy

            # Convert to percentages
            if total_energy > 0:
                for band_name in bands.keys():
                    band_energies[band_name] = (band_energies[band_name] / total_energy) * 100
            else:
                for band_name in bands.keys():
                    band_energies[band_name] = 0.0

            return band_energies

        except Exception as e:
            logger.debug(f"Frequency analysis failed: {e}")
            return {
                'sub_bass_pct': 5.0,
                'bass_pct': 15.0,
                'low_mid_pct': 15.0,
                'mid_pct': 30.0,
                'upper_mid_pct': 20.0,
                'presence_pct': 10.0,
                'air_pct': 5.0
            }

    def _analyze_dynamics(self, audio: np.ndarray, sr: int) -> Dict[str, float]:
        """
        Analyze dynamics (LUFS, crest factor, bass/mid ratio).

        Args:
            audio: Audio signal (mono)
            sr: Sample rate

        Returns:
            Dict with 3 dynamics features
        """
        try:
            # 1. LUFS (approximate using RMS)
            rms = np.sqrt(np.mean(audio ** 2))
            lufs = 20 * np.log10(rms + 1e-10) + 0.691  # Approximate conversion

            # 2. Crest factor
            peak = np.max(np.abs(audio))
            crest_db = 20 * np.log10(peak / (rms + 1e-10))

            # 3. Bass/Mid ratio
            fft = np.fft.rfft(audio)
            magnitude = np.abs(fft)
            freqs = np.fft.rfftfreq(len(audio), 1/sr)

            bass_mask = (freqs >= 60) & (freqs < 250)
            mid_mask = (freqs >= 250) & (freqs < 2000)

            bass_energy = np.sum(magnitude[bass_mask] ** 2)
            mid_energy = np.sum(magnitude[mid_mask] ** 2)

            if mid_energy > 0:
                bass_mid_ratio = 10 * np.log10(bass_energy / mid_energy)
            else:
                bass_mid_ratio = 0.0

            return {
                'lufs': float(lufs),
                'crest_db': float(crest_db),
                'bass_mid_ratio': float(bass_mid_ratio)
            }

        except Exception as e:
            logger.debug(f"Dynamics analysis failed: {e}")
            return {
                'lufs': -20.0,
                'crest_db': 15.0,
                'bass_mid_ratio': 0.0
            }

    def _get_default_fingerprint(self) -> Dict[str, float]:
        """
        Get default fingerprint on analysis failure.

        Returns:
            Dict with 25 default values
        """
        return {
            # Frequency (7D)
            'sub_bass_pct': 5.0,
            'bass_pct': 15.0,
            'low_mid_pct': 15.0,
            'mid_pct': 30.0,
            'upper_mid_pct': 20.0,
            'presence_pct': 10.0,
            'air_pct': 5.0,
            # Dynamics (3D)
            'lufs': -20.0,
            'crest_db': 15.0,
            'bass_mid_ratio': 0.0,
            # Temporal (4D)
            'tempo_bpm': 120.0,
            'rhythm_stability': 0.5,
            'transient_density': 0.5,
            'silence_ratio': 0.1,
            # Spectral (3D)
            'spectral_centroid': 0.5,
            'spectral_rolloff': 0.5,
            'spectral_flatness': 0.3,
            # Harmonic (3D)
            'harmonic_ratio': 0.5,
            'pitch_stability': 0.7,
            'chroma_energy': 0.5,
            # Variation (3D)
            'dynamic_range_variation': 0.5,
            'loudness_variation_std': 0.5,
            'peak_consistency': 0.5,
            # Stereo (2D)
            'stereo_width': 0.5,
            'phase_correlation': 1.0
        }
