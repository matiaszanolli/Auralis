# -*- coding: utf-8 -*-

"""
Streaming Temporal Analyzer

Real-time temporal and rhythmic features from audio streams.

Features (4D - Real-time):
  - tempo_bpm: Beats per minute (40-200 range)
  - rhythm_stability: How consistent the beat is (0-1)
  - transient_density: Prominence of drums/percussion (0-1)
  - silence_ratio: Proportion of silence/space (0-1)

Key Algorithms:
  - Windowed onset detection with running envelope
  - Periodic beat tracking on buffered audio
  - Online RMS tracking for silence ratio
  - O(buffer_size) update time when buffer fills

Dependencies:
  - numpy for numerical operations
  - librosa for onset/beat detection
  - collections.deque for windowed buffers
"""

import numpy as np
import librosa
import logging
from typing import Dict, Optional
from collections import deque
from .common_metrics import MetricUtils, StabilityMetrics, SafeOperations

logger = logging.getLogger(__name__)


class OnsetBuffer:
    """Running buffer for onset detection across frames."""

    def __init__(self, sr: int = 44100, buffer_duration: float = 2.0):
        """Initialize onset buffer.

        Args:
            sr: Sample rate
            buffer_duration: Duration in seconds to buffer audio
        """
        self.sr = sr
        self.buffer_duration = buffer_duration
        self.buffer_size = int(sr * buffer_duration)
        self.audio_buffer = deque(maxlen=self.buffer_size)
        self.onset_times = deque()  # Times of detected onsets
        self.last_analysis_pos = 0  # Position of last analysis

    def append(self, frame: np.ndarray):
        """Add audio frame to buffer.

        Args:
            frame: Audio samples to add
        """
        self.audio_buffer.extend(frame)

    def detect_onsets(self) -> np.ndarray:
        """Detect onsets in current buffer using onset detection.

        Returns:
            Array of onset times (in seconds) detected since last analysis
        """
        if len(self.audio_buffer) < self.sr // 4:  # Minimum 250ms for onset detection
            return np.array([])

        try:
            audio = np.array(list(self.audio_buffer))

            # Compute onset strength envelope
            onset_env = librosa.onset.onset_strength(y=audio, sr=self.sr)

            # Detect onset frames
            onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, units='frames')

            if len(onset_frames) == 0:
                return np.array([])

            # Convert frames to time
            onset_times = librosa.frames_to_time(onset_frames, sr=self.sr)

            return onset_times

        except Exception as e:
            logger.debug(f"Onset detection failed: {e}")
            return np.array([])

    def get_audio(self) -> Optional[np.ndarray]:
        """Get current buffered audio."""
        if len(self.audio_buffer) > 0:
            return np.array(list(self.audio_buffer))
        return None

    def clear(self):
        """Clear buffer."""
        self.audio_buffer.clear()
        self.onset_times.clear()
        self.last_analysis_pos = 0


class StreamingTemporalAnalyzer:
    """Extract temporal features from audio streams in real-time.

    Provides real-time temporal metrics using windowed analysis:
    - Onset detection for transient density
    - Periodic beat tracking on buffered audio
    - Running RMS for silence ratio
    - O(N) update time when buffer fills (N = buffer size)

    Note: Temporal metrics have higher latency (0.5-2 seconds) due to
    beat tracking and onset detection requirements.

    Metrics stabilize as frames accumulate; after 5-10 seconds of audio,
    metrics represent stable estimates.
    """

    def __init__(self, sr: int = 44100, buffer_duration: float = 2.0, hop_length: float = 0.25):
        """Initialize streaming temporal analyzer.

        Args:
            sr: Sample rate in Hz
            buffer_duration: Duration in seconds to buffer for beat tracking (default: 2s)
            hop_length: Hop length for RMS in seconds (default: 250ms)
        """
        self.sr = sr
        self.buffer_duration = buffer_duration
        self.hop_length = int(sr * hop_length)

        # Onset/beat analysis buffer
        self.onset_buffer = OnsetBuffer(sr, buffer_duration)

        # RMS tracking for silence ratio
        self.rms_buffer = deque()
        self.frame_rms_values = deque(maxlen=int(sr * 10 / self.hop_length))  # 10 second history

        # Metric tracking
        self.tempo_estimate = 120.0
        self.recent_onsets = deque(maxlen=100)  # Track recent onsets
        self.rhythm_stability_estimate = 0.5
        self.transient_density_estimate = 0.5
        self.silence_ratio_estimate = 0.1

        # Frame counter
        self.frame_count = 0
        self.analysis_counter = 0  # Counter for periodic re-analysis

    def reset(self):
        """Reset analyzer state."""
        self.onset_buffer.clear()
        self.rms_buffer.clear()
        self.frame_rms_values.clear()
        self.recent_onsets.clear()
        self.tempo_estimate = 120.0
        self.rhythm_stability_estimate = 0.5
        self.transient_density_estimate = 0.5
        self.silence_ratio_estimate = 0.1
        self.frame_count = 0
        self.analysis_counter = 0

    def update(self, frame: np.ndarray) -> Dict[str, float]:
        """Update analyzer with new audio frame.

        Args:
            frame: Audio frame to process (mono)

        Returns:
            Dictionary with current metrics: tempo_bpm, rhythm_stability,
            transient_density, silence_ratio
        """
        try:
            # Increment frame counter
            self.frame_count += 1
            self.analysis_counter += 1

            # Add to onset buffer
            self.onset_buffer.append(frame)

            # Calculate RMS for silence ratio
            rms_val = np.sqrt(np.mean(frame ** 2))
            rms_db = 20 * np.log10(np.maximum(rms_val, SafeOperations.EPSILON))
            self.frame_rms_values.append(rms_db)

            # Periodic re-analysis when buffer fills (every ~2 seconds at 22050 hop)
            if self.analysis_counter >= int(self.sr * self.buffer_duration / len(frame)):
                self._perform_analysis()
                self.analysis_counter = 0

            return self.get_metrics()

        except Exception as e:
            logger.debug(f"Streaming temporal update failed: {e}")
            return self.get_metrics()

    def _perform_analysis(self):
        """Perform expensive analysis on buffered audio."""
        try:
            audio = self.onset_buffer.get_audio()
            if audio is None or len(audio) < self.sr // 4:
                return

            # Detect onsets
            onsets = self.onset_buffer.detect_onsets()
            if len(onsets) > 0:
                # Update recent onsets
                current_time = len(audio) / self.sr
                for onset_time in onsets:
                    self.recent_onsets.append(onset_time)

            # Detect tempo and beats
            try:
                onset_env = librosa.onset.onset_strength(y=audio, sr=self.sr)

                # Tempo detection
                import warnings
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=FutureWarning, module="librosa")
                    try:
                        tempo_array = librosa.feature.rhythm.tempo(onset_envelope=onset_env, sr=self.sr)
                    except AttributeError:
                        tempo_array = librosa.beat.tempo(onset_envelope=onset_env, sr=self.sr)

                if len(tempo_array) > 0:
                    self.tempo_estimate = float(MetricUtils.clip_to_range(tempo_array[0], 40, 200))

                # Beat tracking for rhythm stability
                try:
                    _, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=self.sr)

                    if len(beats) >= 3:
                        beat_times = librosa.frames_to_time(beats, sr=self.sr)
                        intervals = np.diff(beat_times)

                        # Use unified StabilityMetrics
                        stability = StabilityMetrics.from_intervals(intervals, scale=1.0)
                        self.rhythm_stability_estimate = float(np.clip(stability, 0, 1))
                except Exception as e:
                    logger.debug(f"Beat tracking failed: {e}")

            except Exception as e:
                logger.debug(f"Tempo/beat detection failed: {e}")

            # Calculate transient density
            onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, units='frames')
            duration = len(audio) / self.sr
            onset_density = len(onset_frames) / max(duration, 0.1)
            self.transient_density_estimate = float(np.clip(onset_density / 10.0, 0, 1))

        except Exception as e:
            logger.debug(f"Analysis failed: {e}")

    def get_metrics(self) -> Dict[str, float]:
        """Get current temporal metrics.

        Returns:
            Dictionary with current metric estimates
        """
        # Silence ratio from RMS history
        silence_ratio = self._calculate_silence_ratio()

        return {
            'tempo_bpm': float(self.tempo_estimate),
            'rhythm_stability': float(self.rhythm_stability_estimate),
            'transient_density': float(self.transient_density_estimate),
            'silence_ratio': float(silence_ratio)
        }

    def _calculate_silence_ratio(self) -> float:
        """Calculate silence ratio from RMS history.

        Returns:
            Silence ratio (0-1)
        """
        try:
            if len(self.frame_rms_values) == 0:
                return 0.1

            rms_db_array = np.array(list(self.frame_rms_values))

            # Silence threshold
            threshold_db = -40.0

            # Count silent frames
            silent_frames = np.sum(rms_db_array < threshold_db)
            total_frames = len(rms_db_array)

            silence_ratio = silent_frames / total_frames if total_frames > 0 else 0.1

            return float(np.clip(silence_ratio, 0, 1))

        except Exception as e:
            logger.debug(f"Silence ratio calculation failed: {e}")
            return 0.1

    def get_confidence(self) -> Dict[str, float]:
        """Get confidence scores for current metrics.

        Higher confidence = more data accumulated, more analysis runs.

        Returns:
            Dictionary with confidence scores (0-1) for each metric
        """
        # Stabilization: 5 analyses = high confidence
        stabilization_analyses = 5
        analysis_confidence = float(np.clip(
            self.frame_count / (stabilization_analyses * int(self.sr * self.buffer_duration / 4000)),
            0, 1
        ))

        # Silence ratio has higher confidence immediately (based on RMS history)
        silence_confidence = float(np.clip(len(self.frame_rms_values) / 100, 0, 1))

        return {
            'tempo_bpm': analysis_confidence,
            'rhythm_stability': analysis_confidence,
            'transient_density': analysis_confidence,
            'silence_ratio': silence_confidence
        }

    def get_frame_count(self) -> int:
        """Get number of frames processed so far."""
        return self.frame_count

    def get_analysis_count(self) -> int:
        """Get number of full analyses performed so far."""
        return max(0, self.frame_count // int(self.sr * self.buffer_duration / 4000))
