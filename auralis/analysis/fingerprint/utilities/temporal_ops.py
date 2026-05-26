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
from typing import Any

import librosa
import numpy as np

logger = logging.getLogger(__name__)


class TemporalOperations:
    """Centralized temporal/rhythmic feature calculations."""

    @staticmethod
    def _clip_tempo(tempo_raw: Any) -> float:
        """Coerce librosa tempo output (scalar or 1-d array) into a clipped BPM scalar."""
        from ..metrics import MetricUtils

        arr = np.asarray(tempo_raw, dtype=float).reshape(-1)
        tempo = float(arr[0]) if arr.size > 0 else 120.0
        return float(MetricUtils.clip_to_range(tempo, 40, 200))

    @staticmethod
    def detect_tempo(
        audio: np.ndarray,
        sr: int,
        precomputed_tempo: Any = None,
    ) -> float:
        """
        Detect tempo in BPM using librosa's beat tracker (autocorrelation-based).

        Args:
            audio: Audio signal (raw audio, not onset envelope)
            sr: Sample rate
            precomputed_tempo: If provided, skip the beat_track call and only
                clip the value. Used by ``calculate_all`` to avoid running
                ``beat_track`` twice (#3704).

        Returns:
            Tempo in BPM (40-200 range), or 120.0 if detection fails
        """
        try:
            if precomputed_tempo is not None:
                return TemporalOperations._clip_tempo(precomputed_tempo)

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tempo, _ = librosa.beat.beat_track(y=audio, sr=sr)

            return TemporalOperations._clip_tempo(tempo)

        except Exception as e:
            logger.debug(f"Tempo detection failed: {e}")
            return 120.0  # Default to 120 BPM

    @staticmethod
    def calculate_rhythm_stability(
        onset_env: np.ndarray,
        sr: int,
        precomputed_beats: np.ndarray | None = None,
    ) -> float:
        """
        Calculate rhythm stability (how consistent the beat is).

        Higher value = more stable rhythm (electronic, dance)
        Lower value = less stable rhythm (free jazz, ambient)

        Args:
            onset_env: Onset strength envelope (pre-computed)
            sr: Sample rate
            precomputed_beats: If provided, skip the beat_track call. Used by
                ``calculate_all`` so tempo and rhythm_stability derive from
                the same tracking pass (#3704).

        Returns:
            Rhythm stability (0-1), or 0.5 if calculation fails
        """
        try:
            # Import here to avoid circular dependency
            from ..metrics import StabilityMetrics

            if precomputed_beats is not None:
                beats = precomputed_beats
            else:
                _, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)

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
    def calculate_all(audio: np.ndarray, sr: int) -> tuple[float, float, float, float]:
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

            # #3704: single beat_track pass — share tempo and beats so the two
            # downstream metrics derive from the same tracking result instead
            # of running the (50-200 ms) tracker twice with subtly different
            # inputs.
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    tempo_raw, beats = librosa.beat.beat_track(
                        onset_envelope=onset_env, sr=sr
                    )
            except Exception as e:
                logger.debug(f"Shared beat_track failed: {e}")
                tempo_raw, beats = None, None

            tempo = TemporalOperations.detect_tempo(
                audio, sr, precomputed_tempo=tempo_raw
            )
            rhythm_stability = TemporalOperations.calculate_rhythm_stability(
                onset_env, sr, precomputed_beats=beats
            )
            transient_density = TemporalOperations.calculate_transient_density(audio, sr, onset_env)
            silence_ratio = TemporalOperations.calculate_silence_ratio(rms)

            return (tempo, rhythm_stability, transient_density, silence_ratio)

        except Exception as e:
            logger.debug(f"Temporal analysis failed: {e}")
            # Return defaults if anything fails
            return (120.0, 0.5, 0.5, 0.1)
