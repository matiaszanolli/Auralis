# -*- coding: utf-8 -*-

"""
Streaming Spectral Analyzer

Real-time spectral features from audio streams using windowed STFT.

Features (3D - Real-time):
  - spectral_centroid: Brightness/center of mass (0-1)
  - spectral_rolloff: High-frequency content (0-1)
  - spectral_flatness: Noise-like vs tonal (0-1)

Key Algorithms:
  - Windowed STFT with overlap (50% default)
  - Running statistics for spectral moments
  - O(1) metric update per new STFT frame

Dependencies:
  - numpy for numerical operations
  - librosa for STFT computation
  - collections.deque for windowed buffers
  - spectral_utilities for centralized spectral calculations
"""

import logging
from collections import deque
from typing import Any, Dict, Optional, Tuple

import librosa
import numpy as np

from ...metrics import MetricUtils, SafeOperations

logger = logging.getLogger(__name__)


class SpectralMoments:
    """Running calculation of spectral moments using online algorithm.

    Maintains cumulative sum of weighted spectrum data for efficient
    centroid and rolloff calculation without storing full history.
    """

    def __init__(self) -> None:
        """Initialize spectral moments."""
        self.count = 0
        self.centroid_sum = 0.0  # Sum of (frequency * magnitude) weighted
        self.magnitude_sum = 0.0  # Sum of magnitudes
        self.flatness_sum = 0.0  # Sum of flatness values

    def update(self, magnitude_spectrum: np.ndarray, sr: int) -> None:
        """Update moments with new STFT frame magnitude.

        Args:
            magnitude_spectrum: Magnitude spectrum from STFT (1D array of frequencies)
            sr: Sample rate
        """
        self.count += 1

        # Calculate frequencies for this FFT size
        freqs = librosa.fft_frequencies(sr=sr, n_fft=2 * (len(magnitude_spectrum) - 1))

        # Centroid update: weighted sum of frequencies
        magnitude_safe = np.maximum(magnitude_spectrum, SafeOperations.EPSILON)
        self.centroid_sum += np.sum(freqs * magnitude_spectrum)
        self.magnitude_sum += np.sum(magnitude_spectrum)

        # Flatness update: geometric mean / arithmetic mean
        geom_mean = np.exp(np.mean(np.log(magnitude_safe)))
        arith_mean = np.mean(magnitude_safe)
        flatness = SafeOperations.safe_divide(geom_mean, arith_mean)
        self.flatness_sum += flatness  # type: ignore[assignment]

    def get_centroid(self) -> float:
        """Get current average spectral centroid in Hz."""
        if self.magnitude_sum > SafeOperations.EPSILON:
            return self.centroid_sum / self.magnitude_sum
        return 0.0

    def get_flatness(self) -> float:
        """Get current average spectral flatness."""
        if self.count > 0:
            return self.flatness_sum / self.count
        return 0.3

    def reset(self) -> None:
        """Reset moments to initial state."""
        self.count = 0
        self.centroid_sum = 0.0
        self.magnitude_sum = 0.0
        self.flatness_sum = 0.0


class StreamingSpectralAnalyzer:
    """Extract spectral features from audio streams in real-time.

    Provides real-time spectral metrics using windowed STFT:
    - Running spectral moments for centroid and flatness
    - Windowed buffer for rolloff calculation (requires cumulative energy)
    - O(1) update time per STFT frame (no full re-computation)

    Metrics stabilize as frames accumulate; after 2-5 seconds of audio,
    metrics represent stable estimates.
    """

    def __init__(self, sr: int = 44100, n_fft: int = 2048, hop_length: Optional[int] = None,
                 window_duration: float = 5.0) -> None:
        """Initialize streaming spectral analyzer.

        Args:
            sr: Sample rate in Hz
            n_fft: FFT size for STFT (default: 2048)
            hop_length: Hop length for STFT (default: n_fft // 4 = 50% overlap)
            window_duration: Window duration for rolloff buffer in seconds
        """
        self.sr = sr
        self.n_fft = n_fft
        self.hop_length = hop_length or (n_fft // 4)  # 50% overlap default

        # Audio buffer for STFT calculation
        # We need to buffer full frames for STFT computation
        self.audio_buffer: deque[Any] = deque(maxlen=self.hop_length * 2)

        # STFT magnitude buffer for rolloff (needs recent history)
        window_frames = max(1, int(sr * window_duration / self.hop_length))
        self.magnitude_buffer: deque[Any] = deque(maxlen=window_frames)

        # Running moments for centroid and flatness
        self.spectral_moments = SpectralMoments()

        # Frame counter
        self.frame_count = 0

    def reset(self) -> None:
        """Reset analyzer state."""
        self.audio_buffer.clear()
        self.magnitude_buffer.clear()
        self.spectral_moments.reset()
        self.frame_count = 0

    def update(self, frame: np.ndarray) -> Dict[str, float]:
        """Update analyzer with new audio frame.

        Args:
            frame: Audio frame to process (mono)

        Returns:
            Dictionary with current metrics: spectral_centroid, spectral_rolloff,
            spectral_flatness
        """
        try:
            # Increment frame counter
            self.frame_count += 1

            # Add to buffer
            self.audio_buffer.extend(frame)

            # When buffer has enough data, compute STFT frame
            if len(self.audio_buffer) >= self.n_fft:
                # Pad to window size with zeros if needed
                audio_chunk = np.array(list(self.audio_buffer))
                if len(audio_chunk) < self.n_fft:
                    audio_chunk = np.pad(audio_chunk, (0, self.n_fft - len(audio_chunk)))

                # Compute STFT for this frame
                S = librosa.stft(audio_chunk[:self.n_fft], n_fft=self.n_fft,
                                hop_length=self.hop_length, center=False)
                magnitude = np.abs(S)

                # Take the most recent frame (last column)
                if magnitude.shape[1] > 0:
                    latest_magnitude = magnitude[:, -1]

                    # Update running moments
                    self.spectral_moments.update(latest_magnitude, self.sr)

                    # Store magnitude for rolloff calculation
                    self.magnitude_buffer.append(latest_magnitude)

            return self.get_metrics()

        except Exception as e:
            logger.debug(f"Streaming spectral update failed: {e}")
            return self.get_metrics()

    def get_metrics(self) -> Dict[str, float]:
        """Get current spectral metrics.

        Returns:
            Dictionary with current metric estimates
        """
        # Spectral centroid from running moments
        centroid_hz = self.spectral_moments.get_centroid()
        spectral_centroid = float(MetricUtils.normalize_to_range(centroid_hz, 8000.0, clip=True))

        # Spectral rolloff from windowed buffer (uses magnitude buffer for rolloff calculation)
        spectral_rolloff = self._calculate_rolling_rolloff()

        # Spectral flatness from running moments
        flatness = self.spectral_moments.get_flatness()
        spectral_flatness = float(np.clip(flatness, 0, 1))

        return {
            'spectral_centroid': spectral_centroid,
            'spectral_rolloff': spectral_rolloff,
            'spectral_flatness': spectral_flatness
        }

    def _calculate_rolling_rolloff(self) -> float:
        """Calculate spectral rolloff from recent magnitude history.

        Rolloff is the frequency below which 85% of energy is contained.
        Requires cumulative energy calculation, so we use windowed buffer.

        Returns:
            Normalized spectral rolloff (0-1)
        """
        try:
            if len(self.magnitude_buffer) == 0:
                return 0.5

            # Convert deque to array for vectorized operations
            magnitude_history = np.array(list(self.magnitude_buffer)).T  # Shape: (freq, frames)

            freqs = librosa.fft_frequencies(sr=self.sr, n_fft=self.n_fft)

            # Normalize each frame by its total energy
            if magnitude_history.shape[1] > 0:
                norm = SafeOperations.safe_divide(
                    np.ones_like(magnitude_history),
                    np.sum(magnitude_history, axis=0, keepdims=True)
                )
                magnitude_norm = magnitude_history * norm

                # Cumulative energy per frame
                cumsum = np.cumsum(magnitude_norm, axis=0)

                # Vectorized: find first frequency where cumsum >= 0.85
                rolloff_indices = np.argmax(cumsum >= 0.85, axis=0)

                # Handle edge case: frames where cumsum never reaches 0.85
                never_reached = np.all(cumsum < 0.85, axis=0)
                rolloff_indices[never_reached] = len(freqs) - 1

                # Map indices to frequencies
                rolloff_freqs = freqs[np.clip(rolloff_indices, 0, len(freqs) - 1)]

                # Average across frames
                rolloff_hz = np.mean(rolloff_freqs)
            else:
                rolloff_hz = 0.0

            # Normalize to 0-1 (typical range: 0-10000 Hz)
            return float(MetricUtils.normalize_to_range(rolloff_hz, 10000.0, clip=True))

        except Exception as e:
            logger.debug(f"Rolling rolloff calculation failed: {e}")
            return 0.5

    def get_confidence(self) -> Dict[str, float]:
        """Get confidence scores for current metrics.

        Higher confidence = more frames accumulated, more stable estimates.

        Returns:
            Dictionary with confidence scores (0-1) for each metric
        """
        # Stabilization: 5 STFT frames = high confidence (at 50% overlap = 5 * hop_length samples)
        stabilization_frames = 5
        confidence = float(np.clip(self.spectral_moments.count / stabilization_frames, 0, 1))

        return {
            'spectral_centroid': confidence,
            'spectral_rolloff': confidence,
            'spectral_flatness': confidence
        }

    def get_frame_count(self) -> int:
        """Get number of frames processed so far (input frames)."""
        return self.frame_count

    def get_stft_frame_count(self) -> int:
        """Get number of STFT frames computed so far."""
        return self.spectral_moments.count
