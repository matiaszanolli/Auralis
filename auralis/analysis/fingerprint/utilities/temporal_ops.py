# -*- coding: utf-8 -*-

"""
Temporal Analysis Utilities

Shared temporal/rhythmic feature calculations for batch and streaming analyzers.
Consolidates tempo detection, beat stability, transient density, and silence ratio
calculations to eliminate duplication across temporal_analyzer.py and
streaming_temporal_analyzer.py.

Features:
  - tempo_bpm: Beats per minute (40-200 range)
  - rhythm_stability: How consistent the beat is (0-1)
  - transient_density: Prominence of drums/percussion (0-1)
  - silence_ratio: Proportion of silence/space in music (0-1)
"""

import logging
import warnings
from typing import Tuple

import librosa
import numpy as np

logger = logging.getLogger(__name__)


class TemporalOperations:
    """Centralized temporal/rhythmic feature calculations."""

    @staticmethod
    def detect_tempo(audio: np.ndarray, sr: int) -> float:
        """
        Detect tempo in BPM using librosa's beat tracker (autocorrelation-based).

        Args:
            audio: Audio signal (raw audio, not onset envelope)
            sr: Sample rate

        Returns:
            Tempo in BPM (40-200 range), or 120.0 if detection fails
        """
        try:
            # Import here to avoid circular dependency
            from ..metrics import MetricUtils

            # Use librosa's beat_track which uses autocorrelation
            # This is more robust than spectral flux onset detection
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tempo, _ = librosa.beat.beat_track(y=audio, sr=sr)

            # Handle array output from newer librosa versions
            if hasattr(tempo, '__len__'):
                tempo = float(tempo[0]) if len(tempo) > 0 else 120.0
            else:
                tempo = float(tempo)

            # Clip tempo to reasonable BPM range
            tempo = MetricUtils.clip_to_range(tempo, 40, 200)

            return float(tempo)

        except Exception as e:
            logger.debug(f"Tempo detection failed: {e}")
            return 120.0  # Default to 120 BPM

    @staticmethod
    def calculate_rhythm_stability(onset_env: np.ndarray, sr: int) -> float:
        """
        Calculate rhythm stability (how consistent the beat is).

        Higher value = more stable rhythm (electronic, dance)
        Lower value = less stable rhythm (free jazz, ambient)

        Args:
            onset_env: Onset strength envelope (pre-computed)
            sr: Sample rate

        Returns:
            Rhythm stability (0-1), or 0.5 if calculation fails
        """
        try:
            # Import here to avoid circular dependency
            from ..metrics import StabilityMetrics

            # Detect beat frames using pre-computed onset envelope
            tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)

            if len(beats) < 3:
                return 0.0  # Not enough beats to measure stability

            # Calculate inter-beat intervals
            beat_times = librosa.frames_to_time(beats, sr=sr)
            intervals = np.diff(beat_times)

            # Use unified StabilityMetrics for calculation
            # Default scale=1.0 is appropriate for rhythm (beat intervals)
            return float(StabilityMetrics.from_intervals(intervals, scale=1.0))

        except Exception as e:
            logger.debug(f"Rhythm stability calculation failed: {e}")
            return 0.5  # Default to medium stability

    @staticmethod
    def calculate_transient_density(audio: np.ndarray, sr: int, onset_env: np.ndarray) -> float:
        """
        Calculate transient density (prominence of drums/percussion).

        Higher value = more transients (metal, electronic)
        Lower value = fewer transients (ambient, classical strings)

        Args:
            audio: Audio signal
            sr: Sample rate
            onset_env: Onset strength envelope (pre-computed)

        Returns:
            Transient density (0-1), or 0.5 if calculation fails
        """
        try:
            # Import here to avoid circular dependency
            from ..metrics import MetricUtils

            # Detect onsets from pre-computed envelope
            onset_frames = librosa.onset.onset_detect(
                onset_envelope=onset_env,
                units='frames'
            )

            # Calculate onset density (onsets per second)
            duration = len(audio) / sr
            onset_density = len(onset_frames) / duration

            # Normalize to 0-1 scale using MetricUtils
            # Typical range: 0-10 onsets/second
            # Metal/electronic: 8-10+
            # Rock/pop: 4-8
            # Ambient/classical: 0-4
            normalized_density = MetricUtils.normalize_to_range(onset_density, max_val=10.0, clip=True)

            return float(normalized_density)

        except Exception as e:
            logger.debug(f"Transient density calculation failed: {e}")
            return 0.5  # Default to medium density

    @staticmethod
    def calculate_silence_ratio(rms: np.ndarray, threshold_db: float = -40.0) -> float:
        """
        Calculate silence ratio (proportion of silent/quiet sections).

        Higher value = more space/silence (sparse music, jazz, ambient)
        Lower value = dense/continuous (metal, electronic)

        Args:
            rms: RMS envelope (pre-computed)
            threshold_db: Silence threshold in dB (default: -40)

        Returns:
            Silence ratio (0-1), or 0.1 if calculation fails
        """
        try:
            # Convert RMS to dB
            rms_db = librosa.amplitude_to_db(rms, ref=np.max)

            # Count frames below threshold
            silent_frames = np.sum(rms_db < threshold_db)
            total_frames = len(rms_db)

            silence_ratio = silent_frames / total_frames if total_frames > 0 else 0.1

            return float(np.clip(silence_ratio, 0, 1))

        except Exception as e:
            logger.debug(f"Silence ratio calculation failed: {e}")
            return 0.1  # Default to low silence

    @staticmethod
    def calculate_all(audio: np.ndarray, sr: int) -> Tuple[float, float, float, float]:
        """
        Calculate all four temporal features in one call with pre-computed envelopes.

        This is more efficient than calling individual methods as it computes
        the expensive onset envelope and RMS only once.

        Args:
            audio: Audio signal
            sr: Sample rate

        Returns:
            Tuple of (tempo_bpm, rhythm_stability, transient_density, silence_ratio)
        """
        try:
            # Pre-compute expensive librosa operations once
            onset_env = librosa.onset.onset_strength(y=audio, sr=sr)
            rms = librosa.feature.rms(y=audio)[0]

            # Calculate all metrics
            # Note: detect_tempo now uses Rust backend and requires raw audio
            tempo = TemporalOperations.detect_tempo(audio, sr)
            rhythm_stability = TemporalOperations.calculate_rhythm_stability(onset_env, sr)
            transient_density = TemporalOperations.calculate_transient_density(audio, sr, onset_env)
            silence_ratio = TemporalOperations.calculate_silence_ratio(rms)

            return (tempo, rhythm_stability, transient_density, silence_ratio)

        except Exception as e:
            logger.debug(f"Temporal analysis failed: {e}")
            # Return defaults if anything fails
            return (120.0, 0.5, 0.5, 0.1)
