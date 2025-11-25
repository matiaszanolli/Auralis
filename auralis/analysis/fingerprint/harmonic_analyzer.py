"""
Harmonic Content Analyzer

Extracts harmonic features from audio for fingerprinting.

Features (3D):
  - harmonic_ratio: Ratio of harmonic to percussive content (0-1)
  - pitch_stability: How in-tune/stable the pitch is (0-1)
  - chroma_energy: Tonal complexity/richness (0-1)

Dependencies:
  - auralis_dsp for Rust-optimized harmonic/percussive separation, pitch detection, chroma analysis
  - librosa for fallback implementations if Rust library unavailable
  - numpy for numerical operations
"""

import numpy as np
import librosa
from typing import Dict
import logging

logger = logging.getLogger(__name__)

# Try to use Rust implementations via PyO3
try:
    import auralis_dsp
    RUST_DSP_AVAILABLE = True
    logger.info("Rust DSP library (auralis_dsp) available - using optimized implementations")
except ImportError:
    RUST_DSP_AVAILABLE = False
    logger.warning("Rust DSP library (auralis_dsp) not available - falling back to librosa")


class HarmonicAnalyzer:
    """Extract harmonic content features from audio."""

    def analyze(self, audio: np.ndarray, sr: int) -> Dict[str, float]:
        """
        Analyze harmonic features.

        Args:
            audio: Audio signal (mono)
            sr: Sample rate

        Returns:
            Dict with 3 harmonic features
        """
        try:
            # Harmonic ratio (harmonic vs percussive)
            harmonic_ratio = self._calculate_harmonic_ratio(audio)

            # Pitch stability
            pitch_stability = self._calculate_pitch_stability(audio, sr)

            # Chroma energy (tonal complexity)
            chroma_energy = self._calculate_chroma_energy(audio, sr)

            return {
                'harmonic_ratio': float(harmonic_ratio),
                'pitch_stability': float(pitch_stability),
                'chroma_energy': float(chroma_energy)
            }

        except Exception as e:
            logger.warning(f"Harmonic analysis failed: {e}")
            return {
                'harmonic_ratio': 0.5,
                'pitch_stability': 0.7,
                'chroma_energy': 0.5
            }

    def _calculate_harmonic_ratio(self, audio: np.ndarray) -> float:
        """
        Calculate ratio of harmonic to percussive content.

        Higher value = more harmonic (strings, vocals, sustained instruments)
        Lower value = more percussive (drums, attacks, rhythmic)

        Args:
            audio: Audio signal

        Returns:
            Harmonic ratio (0-1)
        """
        try:
            # Use Rust implementation if available, fallback to librosa
            if RUST_DSP_AVAILABLE:
                harmonic, percussive = auralis_dsp.hpss(audio)
            else:
                harmonic, percussive = librosa.effects.hpss(audio)

            # Calculate RMS energy of each
            harmonic_energy = np.sqrt(np.mean(harmonic**2))
            percussive_energy = np.sqrt(np.mean(percussive**2))

            total_energy = harmonic_energy + percussive_energy

            if total_energy > 0:
                harmonic_ratio = harmonic_energy / total_energy
            else:
                harmonic_ratio = 0.5

            return np.clip(harmonic_ratio, 0, 1)

        except Exception as e:
            logger.debug(f"Harmonic ratio calculation failed: {e}")
            return 0.5

    def _calculate_pitch_stability(self, audio: np.ndarray, sr: int) -> float:
        """
        Calculate pitch stability (how in-tune/stable the pitch is).

        Higher value = stable pitch (in-tune instruments, vocals)
        Lower value = unstable pitch (out-of-tune, dissonant, noise)

        Args:
            audio: Audio signal
            sr: Sample rate

        Returns:
            Pitch stability (0-1)
        """
        try:
            # Calculate pitch (fundamental frequency) using YIN algorithm
            if RUST_DSP_AVAILABLE:
                f0 = auralis_dsp.yin(
                    audio,
                    sr=sr,
                    fmin=librosa.note_to_hz('C2'),
                    fmax=librosa.note_to_hz('C7')
                )
            else:
                f0 = librosa.yin(
                    audio,
                    fmin=librosa.note_to_hz('C2'),
                    fmax=librosa.note_to_hz('C7'),
                    sr=sr
                )

            # Remove unvoiced frames (no pitch detected)
            voiced_mask = f0 > 0
            voiced_f0 = f0[voiced_mask]

            if len(voiced_f0) < 10:
                return 0.5  # Not enough pitch data

            # Calculate stability as inverse of pitch variation
            pitch_std = np.std(voiced_f0)
            pitch_mean = np.mean(voiced_f0)

            if pitch_mean > 0:
                # Coefficient of variation
                cv = pitch_std / pitch_mean

                # Map to stability (low variation = high stability)
                stability = 1.0 / (1.0 + cv * 10)  # Scale CV to reasonable range
            else:
                stability = 0.5

            return np.clip(stability, 0, 1)

        except Exception as e:
            logger.debug(f"Pitch stability calculation failed: {e}")
            return 0.7  # Default to reasonably stable

    def _calculate_chroma_energy(self, audio: np.ndarray, sr: int) -> float:
        """
        Calculate chroma energy (tonal complexity/richness).

        Higher value = more tonal complexity (rich harmonies, chords)
        Lower value = simpler tonal content (single notes, sparse)

        Args:
            audio: Audio signal
            sr: Sample rate

        Returns:
            Chroma energy (0-1)
        """
        try:
            # Calculate chromagram (12-dimensional pitch class profile)
            if RUST_DSP_AVAILABLE:
                chroma = auralis_dsp.chroma_cqt(audio, sr=sr)
            else:
                chroma = librosa.feature.chroma_cqt(y=audio, sr=sr)

            # Calculate average energy across all pitch classes
            # High energy in multiple classes = rich tonal content
            chroma_mean = np.mean(chroma, axis=1)  # Average across time for each pitch class

            # Calculate how many pitch classes are active
            # (how spread the energy is across pitch classes)
            chroma_energy = np.mean(chroma_mean)

            # Normalize to 0-1
            # Typical range: 0.1-0.4
            # Simple tonal: 0.1-0.2
            # Rich tonal: 0.3-0.4
            normalized = chroma_energy / 0.4
            normalized = np.clip(normalized, 0, 1)

            return normalized

        except Exception as e:
            logger.debug(f"Chroma energy calculation failed: {e}")
            return 0.5
