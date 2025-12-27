# -*- coding: utf-8 -*-

"""
Streaming Harmonic Analyzer - Rust DSP Backend

Real-time harmonic features from audio streams using chunk-based analysis.

Features (3D - Real-time):
  - harmonic_ratio: Ratio of harmonic to percussive content (0-1)
  - pitch_stability: How in-tune/stable the pitch is (0-1)
  - chroma_energy: Tonal complexity/richness (0-1)

Key Algorithms:
  - Chunk-based HPSS (harmonic/percussive separation) via Rust DSP
  - YIN pitch tracking on buffered audio via Rust DSP
  - Chroma energy aggregation via Rust DSP
  - Online statistics for metric aggregation
  - O(chunk_size) update when chunk fills

Dependencies:
  - numpy for numerical operations
  - Rust DSP backend for HPSS, YIN, chroma analysis
  - collections.deque for buffering
"""

import logging
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional, cast

import numpy as np

from ...common_metrics import MetricUtils, SafeOperations, StabilityMetrics
from ...utilities.base_streaming_analyzer import BaseStreamingAnalyzer
from ...utilities.harmonic_ops import HarmonicOperations

logger = logging.getLogger(__name__)


class HarmonicRunningStats:
    """Running statistics for harmonic metrics."""

    def __init__(self) -> None:
        """Initialize harmonic stats."""
        self.count = 0
        self.harmonic_sum = 0.0
        self.pitch_values: deque[np.floating[Any]] = deque(maxlen=1000)  # Keep recent pitch values
        self.chroma_sum = 0.0

    def update_harmonic(self, ratio: float) -> None:
        """Update with harmonic ratio.

        Args:
            ratio: Harmonic ratio (0-1)
        """
        self.count += 1
        self.harmonic_sum += ratio

    def update_pitch(self, f0: np.ndarray) -> None:
        """Update with pitch values.

        Args:
            f0: Pitch values from YIN detection
        """
        # Only store voiced frames (f0 > 0)
        voiced_f0 = f0[f0 > 0]
        if len(voiced_f0) > 0:
            self.pitch_values.extend(voiced_f0)

    def update_chroma(self, energy: float) -> None:
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

    def reset(self) -> None:
        """Reset stats."""
        self.count = 0
        self.harmonic_sum = 0.0
        self.pitch_values.clear()
        self.chroma_sum = 0.0


class StreamingHarmonicAnalyzer(BaseStreamingAnalyzer):
    """Extract harmonic features from audio streams in real-time.

    Provides real-time harmonic metrics using chunk-based analysis:
    - Non-overlapping chunk analysis (0.5 second chunks default)
    - Parallel processing of chunks
    - Online aggregation of results
    - O(chunk_size) update when chunk fills

    Metrics stabilize as chunks accumulate; after 5-10 seconds of audio,
    metrics represent stable estimates.

    Inherits from BaseStreamingAnalyzer to use shared utilities:
    - get_confidence() - Confidence scoring based on analysis runs
    - get_frame_count() - Frame counting
    - get_analysis_count() - Analysis run counting
    """

    def __init__(self, sr: int = 44100, chunk_duration: float = 0.5,
                 interval_duration: float = 0.5):
        """Initialize streaming harmonic analyzer.

        Args:
            sr: Sample rate in Hz
            chunk_duration: Duration of each analyzed chunk in seconds
            interval_duration: Interval between chunk starts in seconds
        """
        super().__init__()  # Initialize mixin
        self.sr = sr
        self.chunk_duration = chunk_duration
        self.interval_duration = interval_duration
        self.chunk_samples = int(sr * chunk_duration)
        self.interval_samples = int(sr * interval_duration)

        # Audio buffer for chunk accumulation
        self.audio_buffer: deque[np.floating[Any]] = deque(maxlen=int(sr * 5))  # 5 second history max

        # Running statistics
        self.stats: HarmonicRunningStats = HarmonicRunningStats()

        # Frame counter (required by BaseStreamingAnalyzer)
        self.frame_count = 0
        self.chunk_count = 0
        self.analysis_runs = 0  # Required by BaseStreamingAnalyzer (used in get_confidence())

    def reset(self) -> None:
        """Reset analyzer state."""
        self.audio_buffer.clear()
        self.stats.reset()
        self.frame_count = 0
        self.chunk_count = 0
        self.analysis_runs = 0

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

    def _analyze_chunk(self, chunk: np.ndarray) -> None:
        """Analyze single chunk using centralized HarmonicOperations.

        Args:
            chunk: Audio chunk to analyze
        """
        try:
            # Use centralized HarmonicOperations for all three metrics
            harmonic_ratio = HarmonicOperations.calculate_harmonic_ratio(chunk)
            self.stats.update_harmonic(harmonic_ratio)

            # For pitch, we need direct access to f0 array (not aggregated)
            # Note: This is still using the internal calculation but via the utility
            from ...utilities.dsp_backend import DSPBackend
            try:
                # Frequency range: C2 (65.41 Hz) to C7 (2093.00 Hz)
                f0 = DSPBackend.yin(
                    chunk,
                    sr=self.sr,
                    fmin=65.41,
                    fmax=2093.00
                )
            except Exception:
                f0 = np.array([0])
            self.stats.update_pitch(f0)

            chroma_energy = HarmonicOperations.calculate_chroma_energy(chunk, self.sr)
            self.stats.update_chroma(chroma_energy)

            # Increment analysis runs for confidence scoring (BaseStreamingAnalyzer)
            self.analysis_runs += 1

        except Exception as e:
            logger.debug(f"Chunk analysis failed: {e}")

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
