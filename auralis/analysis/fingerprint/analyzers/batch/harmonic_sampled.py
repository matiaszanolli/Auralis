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

import logging
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from ...metrics import AggregationUtils
from ...utilities.harmonic_ops import HarmonicOperations
from ..base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)


class SampledHarmonicAnalyzer(BaseAnalyzer):
    """Extract harmonic features using time-domain sampling strategy."""

    DEFAULT_FEATURES: dict[str, float] = {
        'harmonic_ratio': 0.5,
        'pitch_stability': 0.7,
        'chroma_energy': 0.5
    }

    def __init__(self, chunk_duration: float = 5.0, interval_duration: float = 10.0, max_chunks: int = 60) -> None:
        """
        Initialize sampled analyzer.

        Args:
            chunk_duration: Duration of each analyzed chunk in seconds (default: 5s)
            interval_duration: Interval between chunk starts in seconds (default: 10s)
                If equal to chunk_duration, chunks don't overlap.
                If greater, chunks are spaced apart.
            max_chunks: Maximum number of chunks to extract (default: 60 = ~5 min at 5s/chunk, #2451)
        """
        super().__init__()
        self.chunk_duration: float = chunk_duration
        self.interval_duration: float = interval_duration
        self.max_chunks: int = max_chunks

    def _extract_chunks(self, audio: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
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

        # For long tracks, spread max_chunks evenly across the full duration
        # instead of stopping at the cap and silently discarding the remainder (#2517).
        total_samples = len(audio)
        possible_chunks = max(1, (total_samples - chunk_samples) // interval_samples + 1)
        if possible_chunks > self.max_chunks:
            effective_interval = max(chunk_samples, total_samples // self.max_chunks)
            logger.debug(
                f"Track duration {total_duration:.1f}s would yield {possible_chunks} chunks; "
                f"distributing {self.max_chunks} evenly (interval={effective_interval / sr:.1f}s)"
            )
        else:
            effective_interval = interval_samples

        # Extract chunks at regular intervals
        start_sample = 0
        while start_sample + chunk_samples <= len(audio):
            end_sample = start_sample + chunk_samples
            chunk = audio[start_sample:end_sample].copy()
            chunks.append(chunk)

            start_times.append(start_sample / sr)
            start_sample += effective_interval

        if len(chunks) == 0:
            # Track too short, analyze entire audio as one chunk
            logger.debug(
                f"Track duration {total_duration:.1f}s < chunk_duration {self.chunk_duration}s, analyzing full track"
            )
            return np.array([audio.copy()]), np.array([0.0])

        # Keep chunks as list instead of object array to preserve float dtypes
        return chunks, np.array(start_times)

    def _analyze_impl(self, audio: np.ndarray, sr: int) -> dict[str, float]:
        """
        Analyze harmonic features using time-domain sampling with parallel chunk processing.

        Args:
            audio: Audio signal (mono)
            sr: Sample rate

        Returns:
            Dict with 3 harmonic features (aggregated from chunks)
        """
        # Extract chunks
        chunks, start_times = self._extract_chunks(audio, sr)
        n_chunks = len(chunks)

        logger.debug(f"Analyzing {n_chunks} chunks from {len(audio)/sr:.1f}s track")

        # OPTIMIZATION: Analyze chunks in parallel using ThreadPoolExecutor.
        # Use as_completed() so a single failed chunk does not block the rest:
        # the `with` context manager would call shutdown(wait=True) after a
        # list-comprehension exception, stalling until all running threads finish
        # (fixes #2527).
        from concurrent.futures import as_completed as _as_completed
        executor = ThreadPoolExecutor(max_workers=4)
        try:
            future_to_idx = {
                executor.submit(self._analyze_chunk, chunk, sr, i): i
                for i, chunk in enumerate(chunks)
            }
            results_map: dict[int, tuple[float, float, float]] = {}
            for future in _as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results_map[idx] = future.result()
                except Exception as exc:
                    logger.warning(f"Chunk {idx} analysis failed ({exc}); using default features")
                    results_map[idx] = (
                        self.DEFAULT_FEATURES['harmonic_ratio'],
                        self.DEFAULT_FEATURES['pitch_stability'],
                        self.DEFAULT_FEATURES['chroma_energy'],
                    )
            results = [results_map[i] for i in range(len(chunks))]
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        # Aggregate results from chunks using mean aggregation
        if not results:
            return {
                'harmonic_ratio': 0.5,
                'pitch_stability': 0.7,
                'chroma_energy': 0.5
            }

        # Extract chunk-level features and aggregate to track level
        harmonic_ratios = np.array([r[0] for r in results])
        pitch_stabilities = np.array([r[1] for r in results])
        chroma_energies = np.array([r[2] for r in results])

        return {
            'harmonic_ratio': AggregationUtils.aggregate_frames_to_track(harmonic_ratios, method='mean'),
            'pitch_stability': AggregationUtils.aggregate_frames_to_track(pitch_stabilities, method='mean'),
            'chroma_energy': AggregationUtils.aggregate_frames_to_track(chroma_energies, method='mean')
        }

    def _analyze_chunk(self, chunk: np.ndarray, sr: int, chunk_idx: int) -> tuple[float, float, float]:
        """
        Analyze single chunk (called in parallel).

        Args:
            chunk: Audio chunk to analyze
            sr: Sample rate
            chunk_idx: Index of chunk (for logging)

        Returns:
            Tuple of (harmonic_ratio, pitch_stability, chroma_energy)
        """
        try:
            # Use centralized HarmonicOperations
            return HarmonicOperations.calculate_all(chunk, sr)
        except Exception as e:
            logger.debug(f"Chunk {chunk_idx} analysis failed: {e}, using defaults")
            return (0.5, 0.7, 0.5)
