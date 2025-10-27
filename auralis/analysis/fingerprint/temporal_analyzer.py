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

logger = logging.getLogger(__name__)


class TemporalAnalyzer:
    """Extract temporal and rhythmic features from audio."""

    def analyze(self, audio: np.ndarray, sr: int) -> Dict[str, float]:
        """
        Analyze temporal/rhythmic features.

        Args:
            audio: Audio signal (mono)
            sr: Sample rate

        Returns:
            Dict with 4 temporal features
        """
        try:
            # Tempo detection
            tempo_bpm = self._detect_tempo(audio, sr)

            # Rhythm stability
            rhythm_stability = self._calculate_rhythm_stability(audio, sr)

            # Transient density (drum/percussion prominence)
            transient_density = self._calculate_transient_density(audio, sr)

            # Silence ratio
            silence_ratio = self._calculate_silence_ratio(audio)

            return {
                'tempo_bpm': float(tempo_bpm),
                'rhythm_stability': float(rhythm_stability),
                'transient_density': float(transient_density),
                'silence_ratio': float(silence_ratio)
            }

        except Exception as e:
            logger.warning(f"Temporal analysis failed: {e}")
            # Return default values on error
            return {
                'tempo_bpm': 120.0,
                'rhythm_stability': 0.5,
                'transient_density': 0.5,
                'silence_ratio': 0.1
            }

    def _detect_tempo(self, audio: np.ndarray, sr: int) -> float:
        """
        Detect tempo in BPM using librosa.

        Args:
            audio: Audio signal
            sr: Sample rate

        Returns:
            Tempo in BPM (40-200 range)
        """
        try:
            # Use librosa's tempo detection
            onset_env = librosa.onset.onset_strength(y=audio, sr=sr)
            tempo = librosa.beat.tempo(onset_envelope=onset_env, sr=sr)[0]

            # Clip to reasonable range
            tempo = np.clip(tempo, 40, 200)

            return tempo

        except Exception as e:
            logger.debug(f"Tempo detection failed: {e}")
            return 120.0  # Default to 120 BPM

    def _calculate_rhythm_stability(self, audio: np.ndarray, sr: int) -> float:
        """
        Calculate rhythm stability (how consistent the beat is).

        Higher value = more stable rhythm (electronic, dance)
        Lower value = less stable rhythm (free jazz, ambient)

        Args:
            audio: Audio signal
            sr: Sample rate

        Returns:
            Rhythm stability (0-1)
        """
        try:
            # Detect beat frames
            onset_env = librosa.onset.onset_strength(y=audio, sr=sr)
            tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)

            if len(beats) < 3:
                return 0.0  # Not enough beats to measure stability

            # Calculate inter-beat intervals
            beat_times = librosa.frames_to_time(beats, sr=sr)
            intervals = np.diff(beat_times)

            # Stability = inverse of interval variation
            # Consistent rhythm = low std dev of intervals
            if len(intervals) > 0 and np.mean(intervals) > 0:
                cv = np.std(intervals) / np.mean(intervals)  # Coefficient of variation
                stability = 1.0 / (1.0 + cv)  # Map to 0-1 (high CV = low stability)
            else:
                stability = 0.5

            return np.clip(stability, 0, 1)

        except Exception as e:
            logger.debug(f"Rhythm stability calculation failed: {e}")
            return 0.5  # Default to medium stability

    def _calculate_transient_density(self, audio: np.ndarray, sr: int) -> float:
        """
        Calculate transient density (prominence of drums/percussion).

        Higher value = more transients (metal, electronic)
        Lower value = fewer transients (ambient, classical strings)

        Args:
            audio: Audio signal
            sr: Sample rate

        Returns:
            Transient density (0-1)
        """
        try:
            # Detect onsets (transients)
            onset_frames = librosa.onset.onset_detect(
                y=audio,
                sr=sr,
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

    def _calculate_silence_ratio(self, audio: np.ndarray, threshold_db: float = -40) -> float:
        """
        Calculate silence ratio (proportion of silent/quiet sections).

        Higher value = more space/silence (sparse music, jazz, ambient)
        Lower value = dense/continuous (metal, electronic)

        Args:
            audio: Audio signal
            threshold_db: Silence threshold in dB

        Returns:
            Silence ratio (0-1)
        """
        try:
            # Convert to dB
            rms = librosa.feature.rms(y=audio)[0]
            rms_db = librosa.amplitude_to_db(rms, ref=np.max)

            # Count frames below threshold
            silent_frames = np.sum(rms_db < threshold_db)
            total_frames = len(rms_db)

            silence_ratio = silent_frames / total_frames

            return np.clip(silence_ratio, 0, 1)

        except Exception as e:
            logger.debug(f"Silence ratio calculation failed: {e}")
            return 0.1  # Default to low silence
