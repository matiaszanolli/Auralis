# -*- coding: utf-8 -*-

"""
Streaming Harmonic Analyzer

Real-time harmonic features from audio streams using chunk-based analysis.

Features (3D - Real-time):
  - harmonic_ratio: Ratio of harmonic to percussive content (0-1)
  - pitch_stability: How in-tune/stable the pitch is (0-1)
  - chroma_energy: Tonal complexity/richness (0-1)

Key Algorithms:
  - Chunk-based HPSS (harmonic/percussive separation)
  - YIN pitch tracking on buffered audio
  - Chroma energy aggregation
  - Online statistics for metric aggregation
  - O(chunk_size) update when chunk fills

Dependencies:
  - numpy for numerical operations
  - librosa for HPSS, YIN, chroma analysis
  - collections.deque for buffering
"""

import numpy as np
import librosa
import logging
from typing import Dict, Optional
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from .common_metrics import MetricUtils, StabilityMetrics, SafeOperations

logger = logging.getLogger(__name__)

# Try to use Rust implementations via PyO3
try:
    import auralis_dsp
    RUST_DSP_AVAILABLE = True
    logger.info("Rust DSP library (auralis_dsp) available - using optimized implementations")
except ImportError:
    RUST_DSP_AVAILABLE = False
    logger.warning("Rust DSP library (auralis_dsp) not available - falling back to librosa")


class HarmonicRunningStats:
    """Running statistics for harmonic metrics."""

    def __init__(self):
        """Initialize harmonic stats."""
        self.count = 0
        self.harmonic_sum = 0.0
        self.pitch_values = deque(maxlen=1000)  # Keep recent pitch values
        self.chroma_sum = 0.0

    def update_harmonic(self, ratio: float):
        """Update with harmonic ratio.

        Args:
            ratio: Harmonic ratio (0-1)
        """
        self.count += 1
        self.harmonic_sum += ratio

    def update_pitch(self, f0: np.ndarray):
        """Update with pitch values.

        Args:
            f0: Pitch values from YIN detection
        """
        # Only store voiced frames (f0 > 0)
        voiced_f0 = f0[f0 > 0]
        if len(voiced_f0) > 0:
            self.pitch_values.extend(voiced_f0)

    def update_chroma(self, energy: float):
        """Update with chroma energy.

        Args:
            energy: Chroma energy value
        """
        self.chroma_sum += energy

    def get_harmonic_ratio(self) -> float:
        """Get average harmonic ratio."""
        if self.count > 0:
            return self.harmonic_sum / self.count
        return 0.5

    def get_pitch_stability(self) -> float:
        """Get pitch stability from accumulated values."""
        if len(self.pitch_values) < 10:
            return 0.5

        try:
            voiced_f0 = np.array(list(self.pitch_values))
            # Use unified StabilityMetrics with harmonic-specific scale
            return StabilityMetrics.from_values(voiced_f0, scale=10.0)
        except Exception as e:
            logger.debug(f"Pitch stability calculation failed: {e}")
            return 0.7

    def get_chroma_energy(self) -> float:
        """Get average chroma energy."""
        if self.count > 0:
            energy = self.chroma_sum / self.count
            # Normalize to 0-1 using MetricUtils (typical range: 0.1-0.4)
            normalized = MetricUtils.normalize_to_range(energy, max_val=0.4, clip=True)
            return float(normalized)
        return 0.5

    def reset(self):
        """Reset stats."""
        self.count = 0
        self.harmonic_sum = 0.0
        self.pitch_values.clear()
        self.chroma_sum = 0.0


class StreamingHarmonicAnalyzer:
    """Extract harmonic features from audio streams in real-time.

    Provides real-time harmonic metrics using chunk-based analysis:
    - Non-overlapping chunk analysis (0.5 second chunks default)
    - Parallel processing of chunks
    - Online aggregation of results
    - O(chunk_size) update when chunk fills

    Metrics stabilize as chunks accumulate; after 5-10 seconds of audio,
    metrics represent stable estimates.
    """

    def __init__(self, sr: int = 44100, chunk_duration: float = 0.5,
                 interval_duration: float = 0.5):
        """Initialize streaming harmonic analyzer.

        Args:
            sr: Sample rate in Hz
            chunk_duration: Duration of each analyzed chunk in seconds
            interval_duration: Interval between chunk starts in seconds
        """
        self.sr = sr
        self.chunk_duration = chunk_duration
        self.interval_duration = interval_duration
        self.chunk_samples = int(sr * chunk_duration)
        self.interval_samples = int(sr * interval_duration)

        # Audio buffer for chunk accumulation
        self.audio_buffer = deque(maxlen=int(sr * 5))  # 5 second history max

        # Running statistics
        self.stats = HarmonicRunningStats()

        # Frame counter
        self.frame_count = 0
        self.chunk_count = 0

    def reset(self):
        """Reset analyzer state."""
        self.audio_buffer.clear()
        self.stats.reset()
        self.frame_count = 0
        self.chunk_count = 0

    def update(self, frame: np.ndarray) -> Dict[str, float]:
        """Update analyzer with new audio frame.

        Args:
            frame: Audio frame to process (mono)

        Returns:
            Dictionary with current metrics: harmonic_ratio, pitch_stability,
            chroma_energy
        """
        try:
            # Increment frame counter
            self.frame_count += 1

            # Add to buffer
            self.audio_buffer.extend(frame)

            # When we have enough audio, analyze a chunk
            if len(self.audio_buffer) >= self.chunk_samples:
                # Extract chunk
                audio_chunk = np.array(list(self.audio_buffer))[:self.chunk_samples]

                # Analyze chunk
                self._analyze_chunk(audio_chunk)
                self.chunk_count += 1

            return self.get_metrics()

        except Exception as e:
            logger.debug(f"Streaming harmonic update failed: {e}")
            return self.get_metrics()

    def _analyze_chunk(self, chunk: np.ndarray):
        """Analyze single chunk.

        Args:
            chunk: Audio chunk to analyze
        """
        try:
            # Harmonic/percussive separation
            harmonic_ratio = self._calculate_harmonic_ratio(chunk)
            self.stats.update_harmonic(harmonic_ratio)

            # Pitch tracking
            f0 = self._calculate_pitch(chunk)
            self.stats.update_pitch(f0)

            # Chroma energy
            chroma_energy = self._calculate_chroma_energy(chunk)
            self.stats.update_chroma(chroma_energy)

        except Exception as e:
            logger.debug(f"Chunk analysis failed: {e}")

    def _calculate_harmonic_ratio(self, audio: np.ndarray) -> float:
        """Calculate harmonic/percussive ratio.

        Args:
            audio: Audio chunk

        Returns:
            Harmonic ratio (0-1)
        """
        try:
            # Use Rust implementation if available
            if RUST_DSP_AVAILABLE:
                harmonic, percussive = auralis_dsp.hpss(audio)
            else:
                harmonic, percussive = librosa.effects.hpss(audio)

            # Calculate RMS energy
            harmonic_energy = np.sqrt(np.mean(harmonic ** 2))
            percussive_energy = np.sqrt(np.mean(percussive ** 2))

            total_energy = harmonic_energy + percussive_energy

            if total_energy > SafeOperations.EPSILON:
                ratio = harmonic_energy / total_energy
            else:
                ratio = 0.5

            return float(np.clip(ratio, 0, 1))

        except Exception as e:
            logger.debug(f"Harmonic ratio calculation failed: {e}")
            return 0.5

    def _calculate_pitch(self, audio: np.ndarray) -> np.ndarray:
        """Calculate pitch using YIN algorithm.

        Args:
            audio: Audio chunk

        Returns:
            Pitch values (f0) from YIN detection
        """
        try:
            # Use Rust implementation if available
            if RUST_DSP_AVAILABLE:
                f0 = auralis_dsp.yin(
                    audio,
                    sr=self.sr,
                    fmin=librosa.note_to_hz('C2'),
                    fmax=librosa.note_to_hz('C7')
                )
            else:
                f0 = librosa.yin(
                    audio,
                    fmin=librosa.note_to_hz('C2'),
                    fmax=librosa.note_to_hz('C7'),
                    sr=self.sr
                )

            return f0

        except Exception as e:
            logger.debug(f"Pitch detection failed: {e}")
            return np.array([0])

    def _calculate_chroma_energy(self, audio: np.ndarray) -> float:
        """Calculate chroma energy (tonal complexity).

        Args:
            audio: Audio chunk

        Returns:
            Chroma energy (0-1)
        """
        try:
            # Use Rust implementation if available
            if RUST_DSP_AVAILABLE:
                chroma = auralis_dsp.chroma_cqt(audio, sr=self.sr)
            else:
                chroma = librosa.feature.chroma_cqt(y=audio, sr=self.sr)

            # Average energy across pitch classes and time
            chroma_mean = np.mean(chroma, axis=1)  # Per pitch class
            chroma_energy = np.mean(chroma_mean)  # Average

            return float(chroma_energy)

        except Exception as e:
            logger.debug(f"Chroma energy calculation failed: {e}")
            return 0.5

    def get_metrics(self) -> Dict[str, float]:
        """Get current harmonic metrics.

        Returns:
            Dictionary with current metric estimates
        """
        return {
            'harmonic_ratio': float(np.clip(self.stats.get_harmonic_ratio(), 0, 1)),
            'pitch_stability': float(np.clip(self.stats.get_pitch_stability(), 0, 1)),
            'chroma_energy': float(np.clip(self.stats.get_chroma_energy(), 0, 1))
        }

    def get_confidence(self) -> Dict[str, float]:
        """Get confidence scores for current metrics.

        Higher confidence = more chunks accumulated.

        Returns:
            Dictionary with confidence scores (0-1) for each metric
        """
        # Stabilization: 5 chunks = high confidence
        stabilization_chunks = 5
        confidence = float(np.clip(self.chunk_count / stabilization_chunks, 0, 1))

        return {
            'harmonic_ratio': confidence,
            'pitch_stability': confidence,
            'chroma_energy': confidence
        }

    def get_frame_count(self) -> int:
        """Get number of frames processed so far."""
        return self.frame_count

    def get_chunk_count(self) -> int:
        """Get number of chunks analyzed so far."""
        return self.chunk_count
