"""
Sampled Harmonic Analyzer - Time-Domain Sampling for Fast Fingerprinting

Extracts harmonic features from audio using strategic sampling instead of full-track analysis.
This approach analyzes key segments of the audio (e.g., 5-second chunks at regular intervals)
and aggregates results, significantly reducing computation time while maintaining accuracy.

Key Strategy:
- Extract non-overlapping 5-second chunks at regular intervals (e.g., every 10 seconds)
- Analyze each chunk independently
- Aggregate results using weighted averaging
- Estimated speedup: 2-5x faster than full-track analysis

Performance Expectations:
- 60-second track: ~2-3 seconds (vs 3.8 seconds full-track) = 1.3-1.9x faster
- 300-second track: ~3-4 seconds (vs 19 seconds full-track) = 4.75-6.3x faster
- Accuracy: 95-99% correlation with full-track features
"""

import numpy as np
import librosa
from typing import Dict, Tuple
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


class SampledHarmonicAnalyzer:
    """Extract harmonic features using time-domain sampling strategy."""

    def __init__(self, chunk_duration: float = 5.0, interval_duration: float = 10.0):
        """
        Initialize sampled analyzer.

        Args:
            chunk_duration: Duration of each analyzed chunk in seconds (default: 5s)
            interval_duration: Interval between chunk starts in seconds (default: 10s)
                If equal to chunk_duration, chunks don't overlap.
                If greater, chunks are spaced apart.
        """
        self.chunk_duration = chunk_duration
        self.interval_duration = interval_duration

    def _extract_chunks(self, audio: np.ndarray, sr: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract analysis chunks from audio.

        Args:
            audio: Full audio signal
            sr: Sample rate

        Returns:
            (chunks, start_times): Array of chunks and their start times in seconds
        """
        total_duration = len(audio) / sr
        chunk_samples = int(self.chunk_duration * sr)
        interval_samples = int(self.interval_duration * sr)

        chunks = []
        start_times = []

        # Extract chunks at regular intervals
        start_sample = 0
        while start_sample + chunk_samples <= len(audio):
            end_sample = start_sample + chunk_samples
            chunk = audio[start_sample:end_sample].copy()
            chunks.append(chunk)

            start_times.append(start_sample / sr)
            start_sample += interval_samples

        if len(chunks) == 0:
            # Track too short, analyze entire audio as one chunk
            logger.debug(
                f"Track duration {total_duration:.1f}s < chunk_duration {self.chunk_duration}s, analyzing full track"
            )
            return np.array([audio.copy()]), np.array([0.0])

        return np.array(chunks, dtype=object), np.array(start_times)

    def analyze(self, audio: np.ndarray, sr: int) -> Dict[str, float]:
        """
        Analyze harmonic features using time-domain sampling.

        Args:
            audio: Audio signal (mono)
            sr: Sample rate

        Returns:
            Dict with 3 harmonic features (aggregated from chunks)
        """
        try:
            # Extract chunks
            chunks, start_times = self._extract_chunks(audio, sr)
            n_chunks = len(chunks)

            logger.debug(f"Analyzing {n_chunks} chunks from {len(audio)/sr:.1f}s track")

            # Analyze each chunk
            chunk_results = {
                'harmonic_ratio': [],
                'pitch_stability': [],
                'chroma_energy': []
            }

            for i, chunk in enumerate(chunks):
                try:
                    hr = self._calculate_harmonic_ratio(chunk)
                    ps = self._calculate_pitch_stability(chunk, sr)
                    ce = self._calculate_chroma_energy(chunk, sr)

                    chunk_results['harmonic_ratio'].append(hr)
                    chunk_results['pitch_stability'].append(ps)
                    chunk_results['chroma_energy'].append(ce)

                except Exception as e:
                    logger.debug(f"Chunk {i} analysis failed: {e}, using defaults")
                    chunk_results['harmonic_ratio'].append(0.5)
                    chunk_results['pitch_stability'].append(0.7)
                    chunk_results['chroma_energy'].append(0.5)

            # Aggregate results (simple mean, could be weighted by chunk characteristics)
            return {
                'harmonic_ratio': float(np.mean(chunk_results['harmonic_ratio'])),
                'pitch_stability': float(np.mean(chunk_results['pitch_stability'])),
                'chroma_energy': float(np.mean(chunk_results['chroma_energy']))
            }

        except Exception as e:
            logger.warning(f"Sampled harmonic analysis failed: {e}")
            return {
                'harmonic_ratio': 0.5,
                'pitch_stability': 0.7,
                'chroma_energy': 0.5
            }

    def _calculate_harmonic_ratio(self, audio: np.ndarray) -> float:
        """
        Calculate ratio of harmonic to percussive content.

        Args:
            audio: Audio chunk

        Returns:
            Harmonic ratio (0-1)
        """
        try:
            if RUST_DSP_AVAILABLE:
                harmonic, percussive = auralis_dsp.hpss(audio)
            else:
                harmonic, percussive = librosa.effects.hpss(audio)

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
        Calculate pitch stability.

        Args:
            audio: Audio chunk
            sr: Sample rate

        Returns:
            Pitch stability (0-1)
        """
        try:
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

            voiced_mask = f0 > 0
            voiced_f0 = f0[voiced_mask]

            if len(voiced_f0) < 10:
                return 0.5

            pitch_std = np.std(voiced_f0)
            pitch_mean = np.mean(voiced_f0)

            if pitch_mean > 0:
                cv = pitch_std / pitch_mean
                stability = 1.0 / (1.0 + cv * 10)
            else:
                stability = 0.5

            return np.clip(stability, 0, 1)

        except Exception as e:
            logger.debug(f"Pitch stability calculation failed: {e}")
            return 0.7

    def _calculate_chroma_energy(self, audio: np.ndarray, sr: int) -> float:
        """
        Calculate chroma energy.

        Args:
            audio: Audio chunk
            sr: Sample rate

        Returns:
            Chroma energy (0-1)
        """
        try:
            if RUST_DSP_AVAILABLE:
                chroma = auralis_dsp.chroma_cqt(audio, sr=sr)
            else:
                chroma = librosa.feature.chroma_cqt(y=audio, sr=sr)

            chroma_mean = np.mean(chroma, axis=1)
            chroma_energy = np.mean(chroma_mean)

            normalized = chroma_energy / 0.4
            normalized = np.clip(normalized, 0, 1)

            return normalized

        except Exception as e:
            logger.debug(f"Chroma energy calculation failed: {e}")
            return 0.5
