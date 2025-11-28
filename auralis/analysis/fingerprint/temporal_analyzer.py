"""
Temporal/Rhythmic Feature Analyzer

Extracts temporal and rhythmic features from audio for fingerprinting.

Features (4D):
  - tempo_bpm: Beats per minute (tempo detection)
  - rhythm_stability: How consistent the rhythm is (0-1)
  - transient_density: Prominence of drums/percussion (0-1)
  - silence_ratio: Proportion of silence/space in music (0-1)

Dependencies:
  - librosa for tempo/beat tracking
  - numpy for numerical operations
"""

import numpy as np
import librosa
from typing import Dict
import logging
from .base_analyzer import BaseAnalyzer
from .common_metrics import MetricUtils, StabilityMetrics

logger = logging.getLogger(__name__)


class TemporalAnalyzer(BaseAnalyzer):
    """Extract temporal and rhythmic features from audio."""

    DEFAULT_FEATURES = {
        'tempo_bpm': 120.0,
        'rhythm_stability': 0.5,
        'transient_density': 0.5,
        'silence_ratio': 0.1
    }

    def _analyze_impl(self, audio: np.ndarray, sr: int) -> Dict[str, float]:
        """
        Analyze temporal/rhythmic features.

        Args:
            audio: Audio signal (mono)
            sr: Sample rate

        Returns:
            Dict with 4 temporal features
        """
        # Cache expensive librosa operations - compute onset envelope once
        onset_env = librosa.onset.onset_strength(y=audio, sr=sr)
        rms = librosa.feature.rms(y=audio)[0]

        # Tempo detection
        tempo_bpm = self._detect_tempo(onset_env, sr)

        # Rhythm stability
        rhythm_stability = self._calculate_rhythm_stability(onset_env, sr)

        # Transient density (drum/percussion prominence)
        transient_density = self._calculate_transient_density(audio, sr, onset_env)

        # Silence ratio
        silence_ratio = self._calculate_silence_ratio(rms)

        return {
            'tempo_bpm': float(tempo_bpm),
            'rhythm_stability': float(rhythm_stability),
            'transient_density': float(transient_density),
            'silence_ratio': float(silence_ratio)
        }

    def _detect_tempo(self, onset_env: np.ndarray, sr: int) -> float:
        """
        Detect tempo in BPM using librosa.

        Args:
            onset_env: Onset strength envelope (pre-computed)
            sr: Sample rate

        Returns:
            Tempo in BPM (40-200 range)
        """
        try:
            # Use librosa's tempo detection with pre-computed onset envelope
            # Note: API migration to librosa.feature.rhythm.tempo planned but not yet in 0.11.0

            # Suppress FutureWarning about API migration (we're ready when it happens)
            import warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=FutureWarning, module="librosa")

                try:
                    # Try new location first (librosa >= 1.0.0 when released)
                    tempo_array = librosa.feature.rhythm.tempo(onset_envelope=onset_env, sr=sr)
                except AttributeError:
                    # Current location (librosa < 1.0.0, including 0.11.0)
                    tempo_array = librosa.beat.tempo(onset_envelope=onset_env, sr=sr)

            # Handle empty array (no tempo detected)
            if len(tempo_array) == 0:
                logger.debug("Tempo detection returned empty array, using default")
                return 120.0

            tempo = tempo_array[0]

            # Clip tempo to reasonable BPM range using MetricUtils
            tempo = MetricUtils.clip_to_range(tempo, 40, 200)

            return tempo

        except Exception as e:
            logger.debug(f"Tempo detection failed: {e}")
            return 120.0  # Default to 120 BPM

    def _calculate_rhythm_stability(self, onset_env: np.ndarray, sr: int) -> float:
        """
        Calculate rhythm stability (how consistent the beat is).

        Higher value = more stable rhythm (electronic, dance)
        Lower value = less stable rhythm (free jazz, ambient)

        Args:
            onset_env: Onset strength envelope (pre-computed)
            sr: Sample rate

        Returns:
            Rhythm stability (0-1)
        """
        try:
            # Detect beat frames using pre-computed onset envelope
            tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)

            if len(beats) < 3:
                return 0.0  # Not enough beats to measure stability

            # Calculate inter-beat intervals
            beat_times = librosa.frames_to_time(beats, sr=sr)
            intervals = np.diff(beat_times)

            # Use unified StabilityMetrics for calculation
            # Default scale=1.0 is appropriate for rhythm (beat intervals)
            return StabilityMetrics.from_intervals(intervals, scale=1.0)

        except Exception as e:
            logger.debug(f"Rhythm stability calculation failed: {e}")
            return 0.5  # Default to medium stability

    def _calculate_transient_density(self, audio: np.ndarray, sr: int, onset_env: np.ndarray) -> float:
        """
        Calculate transient density (prominence of drums/percussion).

        Higher value = more transients (metal, electronic)
        Lower value = fewer transients (ambient, classical strings)

        Args:
            audio: Audio signal
            sr: Sample rate
            onset_env: Onset strength envelope (pre-computed)

        Returns:
            Transient density (0-1)
        """
        try:
            # Detect onsets from pre-computed envelope
            onset_frames = librosa.onset.onset_detect(
                onset_envelope=onset_env,
                units='frames'
            )

            # Calculate onset density (onsets per second)
            duration = len(audio) / sr
            onset_density = len(onset_frames) / duration

            # Normalize to 0-1 scale
            # Typical range: 0-10 onsets/second
            # Metal/electronic: 8-10+
            # Rock/pop: 4-8
            # Ambient/classical: 0-4
            normalized_density = onset_density / 10.0
            normalized_density = np.clip(normalized_density, 0, 1)

            return normalized_density

        except Exception as e:
            logger.debug(f"Transient density calculation failed: {e}")
            return 0.5  # Default to medium density

    def _calculate_silence_ratio(self, rms: np.ndarray, threshold_db: float = -40) -> float:
        """
        Calculate silence ratio (proportion of silent/quiet sections).

        Higher value = more space/silence (sparse music, jazz, ambient)
        Lower value = dense/continuous (metal, electronic)

        Args:
            rms: RMS envelope (pre-computed)
            threshold_db: Silence threshold in dB

        Returns:
            Silence ratio (0-1)
        """
        try:
            # Convert RMS to dB
            rms_db = librosa.amplitude_to_db(rms, ref=np.max)

            # Count frames below threshold
            silent_frames = np.sum(rms_db < threshold_db)
            total_frames = len(rms_db)

            silence_ratio = silent_frames / total_frames

            return np.clip(silence_ratio, 0, 1)

        except Exception as e:
            logger.debug(f"Silence ratio calculation failed: {e}")
            return 0.1  # Default to low silence
