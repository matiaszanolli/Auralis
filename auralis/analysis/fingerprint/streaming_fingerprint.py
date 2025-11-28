# -*- coding: utf-8 -*-

"""
Streaming Fingerprint Orchestrator

Real-time 25-dimensional audio fingerprint calculation using online algorithms.

Combines all streaming analyzers for complete fingerprint extraction:
- Variation metrics (3D): dynamic_range_variation, loudness_variation_std, peak_consistency
- Spectral metrics (3D): spectral_centroid, spectral_rolloff, spectral_flatness
- Temporal metrics (4D): tempo_bpm, rhythm_stability, transient_density, silence_ratio
- Harmonic metrics (3D): harmonic_ratio, pitch_stability, chroma_energy

Total: 13D metrics implemented, with 12D additional metrics available in extended fingerprint.

Performance:
- O(1) per-frame cost for variation metrics (Welford's algorithm)
- O(1) per-frame cost for spectral metrics (windowed moments)
- O(buffer_size) per-buffer cost for temporal metrics (periodic beat tracking)
- O(1) per-frame cost for harmonic metrics (chunk aggregation)
- Expected latency: 50-500ms depending on buffer size
- Memory: ~5-10MB for default buffer sizes

Dependencies:
  - numpy for numerical operations
  - Stream analyzer implementations
"""

import numpy as np
import logging
from typing import Dict, Optional

from .streaming_variation_analyzer import StreamingVariationAnalyzer
from .streaming_spectral_analyzer import StreamingSpectralAnalyzer
from .streaming_temporal_analyzer import StreamingTemporalAnalyzer
from .streaming_harmonic_analyzer import StreamingHarmonicAnalyzer

logger = logging.getLogger(__name__)


class StreamingFingerprint:
    """Real-time 25D audio fingerprint calculation.

    Orchestrates multiple streaming analyzers to provide complete fingerprint
    extraction without full re-computation per frame. Suitable for real-time,
    streaming, and incremental audio analysis.
    """

    def __init__(self, sr: int = 44100, enable_harmonic: bool = True):
        """Initialize streaming fingerprint analyzer.

        Args:
            sr: Sample rate in Hz (default: 44100)
            enable_harmonic: Whether to enable harmonic metrics (default: True)
        """
        self.sr = sr
        self.enable_harmonic = enable_harmonic

        # Initialize component analyzers
        self.variation = StreamingVariationAnalyzer(sr=sr)
        self.spectral = StreamingSpectralAnalyzer(sr=sr)
        self.temporal = StreamingTemporalAnalyzer(sr=sr)

        # Harmonic analyzer (Phase 7.4d)
        self.harmonic = StreamingHarmonicAnalyzer(sr=sr) if enable_harmonic else None

        # Frame counter
        self.frame_count = 0

    def reset(self):
        """Reset all analyzer states."""
        self.variation.reset()
        self.spectral.reset()
        self.temporal.reset()
        if self.harmonic is not None:
            self.harmonic.reset()
        self.frame_count = 0

    def update(self, frame: np.ndarray) -> Dict[str, float]:
        """Update fingerprint with new audio frame.

        Args:
            frame: Audio frame to process (mono)

        Returns:
            Dictionary with current 13D fingerprint (or extended with harmonic)
        """
        try:
            self.frame_count += 1

            # Update all component analyzers
            variation_metrics = self.variation.update(frame)
            spectral_metrics = self.spectral.update(frame)
            temporal_metrics = self.temporal.update(frame)

            # Combine into fingerprint
            fingerprint = {}

            # Variation metrics (3D)
            fingerprint.update(variation_metrics)

            # Spectral metrics (3D)
            fingerprint.update(spectral_metrics)

            # Temporal metrics (4D)
            fingerprint.update(temporal_metrics)

            # Harmonic metrics (3D) - Phase 7.4d
            if self.enable_harmonic and self.harmonic is not None:
                harmonic_metrics = self.harmonic.update(frame)
                fingerprint.update(harmonic_metrics)

            return fingerprint

        except Exception as e:
            logger.debug(f"Streaming fingerprint update failed: {e}")
            return self.get_fingerprint()

    def get_fingerprint(self) -> Dict[str, float]:
        """Get current fingerprint without processing new frame.

        Returns:
            Dictionary with current 13D fingerprint (or 16D with harmonic)
        """
        fingerprint = {}

        # Variation metrics (3D)
        fingerprint.update(self.variation.get_metrics())

        # Spectral metrics (3D)
        fingerprint.update(self.spectral.get_metrics())

        # Temporal metrics (4D)
        fingerprint.update(self.temporal.get_metrics())

        # Harmonic metrics (3D)
        if self.enable_harmonic and self.harmonic is not None:
            fingerprint.update(self.harmonic.get_metrics())

        return fingerprint

    def get_confidence(self) -> Dict[str, float]:
        """Get confidence scores for all metrics.

        Returns:
            Dictionary with confidence (0-1) for each metric
        """
        confidence = {}

        # Variation confidence
        confidence.update(self.variation.get_confidence())

        # Spectral confidence
        confidence.update(self.spectral.get_confidence())

        # Temporal confidence
        confidence.update(self.temporal.get_confidence())

        # Harmonic confidence
        if self.enable_harmonic and self.harmonic is not None:
            confidence.update(self.harmonic.get_confidence())

        return confidence

    def get_frame_count(self) -> int:
        """Get number of frames processed."""
        return self.frame_count

    def get_component_status(self) -> Dict[str, Dict[str, int]]:
        """Get status of component analyzers.

        Returns:
            Dictionary with frame counts for each component
        """
        status = {
            'variation': {
                'frames': self.variation.get_frame_count(),
                'stats_updates': self.variation.peak_stats.count
            },
            'spectral': {
                'frames': self.spectral.get_frame_count(),
                'stft_frames': self.spectral.get_stft_frame_count()
            },
            'temporal': {
                'frames': self.temporal.get_frame_count(),
                'analyses': self.temporal.get_analysis_count()
            }
        }

        if self.enable_harmonic and self.harmonic is not None:
            status['harmonic'] = {
                'frames': self.harmonic.get_frame_count(),
                'chunks': self.harmonic.get_chunk_count()
            }

        return status

    def get_fingerprint_size(self) -> int:
        """Get current fingerprint dimensionality.

        Returns:
            Number of dimensions in current fingerprint (13D or 16D)
        """
        # Base: Variation (3D) + Spectral (3D) + Temporal (4D) = 10D
        base_size = 3 + 3 + 4

        # Harmonic (3D) if enabled
        if self.enable_harmonic and self.harmonic is not None:
            base_size += 3

        return base_size

    def get_latency_estimate_ms(self) -> float:
        """Estimate current processing latency in milliseconds.

        Returns:
            Approximate latency from update() call
        """
        # Latency is determined by the slowest component
        # Temporal has highest latency (beat tracking every ~2 seconds)

        # Nominal latencies:
        # - Variation: ~1ms (O(1) Welford)
        # - Spectral: ~2ms (windowed moments)
        # - Temporal: ~50ms-500ms (periodic beat analysis)

        return 50.0  # Conservative estimate for periodic analysis
