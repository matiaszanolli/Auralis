# -*- coding: utf-8 -*-

"""
Streaming Variation Analyzer

Real-time dynamic variation features from audio streams using online algorithms.

Features (3D - Real-time):
  - dynamic_range_variation: How much dynamics change over time (0-1)
  - loudness_variation_std: Standard deviation of loudness (0-10 dB)
  - peak_consistency: How consistent peaks are (0-1)

Key Algorithms:
  - Welford's online algorithm for running mean/variance
  - Sliding window for recent-history aggregation
  - O(1) update time per frame (no re-computation)

Dependencies:
  - numpy for numerical operations
  - collections.deque for windowed buffers
"""

import numpy as np
import logging
from typing import Dict, Optional
from collections import deque

logger = logging.getLogger(__name__)


class RunningStatistics:
    """Online mean and variance calculation using Welford's algorithm.

    Computes mean and variance incrementally in O(1) time per update.
    Uses numerically stable algorithm (no catastrophic cancellation).

    Reference: Welford, B. P. (1962). "Note on a method for calculating
    corrected sums of squares and products." Technometrics.
    """

    def __init__(self):
        """Initialize running statistics."""
        self.count = 0
        self.mean = 0.0
        self.m2 = 0.0  # Sum of squared differences from mean

    def update(self, value: float):
        """Update statistics with a single value.

        Args:
            value: New value to incorporate
        """
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2

    def get_mean(self) -> float:
        """Get current mean."""
        return self.mean if self.count > 0 else 0.0

    def get_variance(self) -> float:
        """Get current variance (population variance)."""
        if self.count < 1:
            return 0.0
        return self.m2 / self.count

    def get_std(self) -> float:
        """Get current standard deviation."""
        return np.sqrt(self.get_variance())

    def reset(self):
        """Reset to initial state."""
        self.count = 0
        self.mean = 0.0
        self.m2 = 0.0


class WindowedBuffer:
    """Sliding window buffer with automatic old value removal.

    Maintains a fixed-size buffer that automatically removes oldest values
    when new values are added beyond capacity.
    """

    def __init__(self, window_size: int):
        """Initialize windowed buffer.

        Args:
            window_size: Maximum number of values to maintain
        """
        self.buffer = deque(maxlen=window_size)
        self.window_size = window_size

    def append(self, value: float):
        """Add value to buffer (oldest removed if at capacity).

        Args:
            value: New value to add
        """
        self.buffer.append(value)

    def get_values(self) -> np.ndarray:
        """Get all current values as array."""
        return np.array(list(self.buffer))

    def is_full(self) -> bool:
        """Check if buffer is at capacity."""
        return len(self.buffer) == self.window_size

    def clear(self):
        """Clear buffer."""
        self.buffer.clear()


class StreamingVariationAnalyzer:
    """Extract dynamic variation features from audio streams.

    Provides real-time variation metrics using online algorithms:
    - Running statistics for mean/variance computation
    - Windowed aggregation for recent-history metrics
    - O(1) update time per frame (no full re-computation)

    Metrics stabilize as frames accumulate; after ~5-10 seconds of audio,
    metrics represent stable estimates.
    """

    def __init__(self, sr: int = 44100, hop_length: float = 0.25,
                 frame_length: float = 0.5, window_duration: float = 5.0):
        """Initialize streaming variation analyzer.

        Args:
            sr: Sample rate in Hz
            hop_length: Hop length for RMS in seconds (default: 250ms)
            frame_length: Frame length for RMS in seconds (default: 500ms)
            window_duration: Window duration for windowed metrics in seconds
        """
        self.sr = sr
        self.hop_length = int(sr * hop_length)
        self.frame_length = int(sr * frame_length)
        self.window_duration = window_duration

        # Windowed buffers for recent-history metrics
        window_frames = max(1, int(sr * window_duration / self.hop_length))
        self.rms_window = WindowedBuffer(window_frames)
        self.peak_window = WindowedBuffer(window_frames)

        # Running statistics for global metrics
        self.rms_stats = RunningStatistics()
        self.peak_stats = RunningStatistics()

        # Audio buffer for RMS/peak calculation
        self.audio_buffer = deque(maxlen=self.frame_length)

        # Frame counter tracking input updates (not metric updates)
        self.frame_count = 0

    def reset(self):
        """Reset analyzer state."""
        self.rms_window.clear()
        self.peak_window.clear()
        self.rms_stats.reset()
        self.peak_stats.reset()
        self.audio_buffer.clear()
        self.frame_count = 0

    def update(self, frame: np.ndarray) -> Dict[str, float]:
        """Update analyzer with new audio frame.

        Args:
            frame: Audio frame to process (mono)

        Returns:
            Dictionary with current metrics: dynamic_range_variation,
            loudness_variation_std, peak_consistency
        """
        try:
            # Increment frame counter for input tracking
            self.frame_count += 1

            # Add to buffer
            self.audio_buffer.extend(frame)

            # Calculate metrics for this frame when buffer is full
            if len(self.audio_buffer) >= self.frame_length:
                # RMS calculation
                audio_chunk = np.array(list(self.audio_buffer))
                rms_val = np.sqrt(np.mean(audio_chunk ** 2))
                rms_db = 20 * np.log10(np.maximum(rms_val, 1e-10))

                # Peak calculation
                peak_val = np.max(np.abs(audio_chunk))

                # Update windowed buffers
                self.rms_window.append(rms_db)
                self.peak_window.append(peak_val)

                # Update running statistics
                self.rms_stats.update(rms_db)
                self.peak_stats.update(peak_val)

            return self.get_metrics()

        except Exception as e:
            logger.debug(f"Streaming variation update failed: {e}")
            return self.get_metrics()

    def get_metrics(self) -> Dict[str, float]:
        """Get current variation metrics.

        Returns:
            Dictionary with current metrics estimates
        """
        # Dynamic range variation: from global peak stats
        peak_mean = self.peak_stats.get_mean()
        peak_std = self.peak_stats.get_std()
        if peak_mean > 0:
            # Coefficient of variation normalized
            cv = (peak_std / peak_mean) / 1.0  # scale factor
            dynamic_range_variation = float(np.clip(cv, 0, 1))
        else:
            dynamic_range_variation = 0.5

        # Loudness variation: standard deviation of RMS (in dB)
        loudness_variation = float(np.clip(self.rms_stats.get_std(), 0, 10.0))

        # Peak consistency: use global stats with stability conversion
        if self.peak_stats.count < 2:
            peak_consistency = 0.5
        else:
            peak_mean = self.peak_stats.get_mean()
            peak_std = self.peak_stats.get_std()
            if peak_mean > 0:
                cv = peak_std / peak_mean
                # Convert CV to consistency (lower CV = higher consistency)
                peak_consistency = float(np.clip(1.0 - cv, 0, 1))
            else:
                peak_consistency = 0.5

        return {
            'dynamic_range_variation': dynamic_range_variation,
            'loudness_variation_std': loudness_variation,
            'peak_consistency': peak_consistency
        }

    def get_confidence(self) -> Dict[str, float]:
        """Get confidence scores for current metrics.

        Higher confidence = more data accumulated, more stable estimates.
        Confidence based on number of frames processed.

        Returns:
            Dictionary with confidence scores (0-1) for each metric
        """
        # Stabilization: 5 seconds of data = high confidence
        stabilization_frames = max(1, int(self.sr * 5.0 / self.hop_length))
        confidence = float(np.clip(self.peak_stats.count / stabilization_frames, 0, 1))

        return {
            'dynamic_range_variation': confidence,
            'loudness_variation_std': confidence,
            'peak_consistency': confidence
        }

    def get_frame_count(self) -> int:
        """Get number of frames processed so far (input frames)."""
        return self.frame_count
