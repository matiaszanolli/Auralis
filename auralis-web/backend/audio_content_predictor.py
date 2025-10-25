"""
Audio-Content-Aware Prediction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Analyzes upcoming audio chunks to predict preset switches based on
audio characteristics (energy, brightness, dynamics, vocals).

Enhances the BranchPredictor with audio-informed predictions:
- High energy sections → "punchy" prediction
- Quiet/ambient sections → "gentle" or "warm" prediction
- Vocal-heavy sections → "bright" prediction
- Dynamic sections → "adaptive" prediction

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
import numpy as np
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AudioFeatures:
    """Audio features extracted from a chunk."""
    energy: float  # 0.0-1.0, overall loudness/energy
    brightness: float  # 0.0-1.0, high-frequency content
    dynamics: float  # 0.0-1.0, dynamic range (crest factor)
    vocal_presence: float  # 0.0-1.0, estimated vocal content
    tempo_energy: float  # 0.0-1.0, rhythmic/percussive energy


@dataclass
class PresetAffinityScores:
    """Affinity scores for each preset based on audio content."""
    adaptive: float = 0.5  # Default neutral
    gentle: float = 0.0
    warm: float = 0.0
    bright: float = 0.0
    punchy: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            'adaptive': self.adaptive,
            'gentle': self.gentle,
            'warm': self.warm,
            'bright': self.bright,
            'punchy': self.punchy
        }

    def get_top_preset(self) -> Tuple[str, float]:
        """Get preset with highest affinity."""
        scores = self.to_dict()
        top = max(scores.items(), key=lambda x: x[1])
        return top


class AudioContentAnalyzer:
    """
    Fast audio analysis for preset prediction.

    Uses lightweight analysis (no full processing) to extract features
    that correlate with preset preferences.
    """

    def __init__(self):
        """Initialize analyzer."""
        self.analysis_cache: Dict[str, AudioFeatures] = {}  # Cache results
        self._cache_max_size = 100

    async def analyze_chunk_fast(
        self,
        audio_data: Optional[np.ndarray] = None,
        filepath: Optional[str] = None,
        chunk_idx: int = 0
    ) -> AudioFeatures:
        """
        Fast analysis of audio chunk for prediction.

        Args:
            audio_data: Audio data array (if already loaded)
            filepath: Path to audio file (if not loaded)
            chunk_idx: Chunk index (for caching)

        Returns:
            AudioFeatures with 0.0-1.0 normalized values
        """
        # Check cache first
        cache_key = f"{filepath}_{chunk_idx}" if filepath else f"mem_{id(audio_data)}"
        if cache_key in self.analysis_cache:
            logger.debug(f"Audio analysis cache hit: {cache_key}")
            return self.analysis_cache[cache_key]

        # Load audio if needed
        if audio_data is None and filepath:
            audio_data = await self._load_chunk_fast(filepath, chunk_idx)

        if audio_data is None:
            logger.warning("No audio data provided for analysis")
            return AudioFeatures(0.5, 0.5, 0.5, 0.5, 0.5)  # Neutral

        # Extract features
        features = await self._extract_features(audio_data)

        # Cache result
        if len(self.analysis_cache) < self._cache_max_size:
            self.analysis_cache[cache_key] = features

        return features

    async def _load_chunk_fast(self, filepath: str, chunk_idx: int) -> Optional[np.ndarray]:
        """
        Fast load of audio chunk (lightweight, no full processing).

        Uses minimal dependencies for speed.
        """
        try:
            # Try soundfile first (fastest)
            import soundfile as sf

            # Calculate chunk position (30 seconds per chunk)
            chunk_duration = 30.0
            start_sec = chunk_idx * chunk_duration

            # Read just this chunk
            with sf.SoundFile(filepath) as f:
                sample_rate = f.samplerate
                start_frame = int(start_sec * sample_rate)
                num_frames = int(chunk_duration * sample_rate)

                f.seek(start_frame)
                audio = f.read(num_frames)

                # Convert to mono if stereo
                if len(audio.shape) > 1:
                    audio = np.mean(audio, axis=1)

                return audio

        except Exception as e:
            logger.warning(f"Fast chunk load failed: {e}")
            return None

    async def _extract_features(self, audio: np.ndarray) -> AudioFeatures:
        """
        Extract audio features for prediction.

        Fast analysis using basic signal processing.
        """
        # Ensure mono
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)

        # 1. Energy (RMS normalized)
        rms = np.sqrt(np.mean(audio ** 2))
        energy = min(1.0, rms * 10)  # Scale to 0-1

        # 2. Brightness (high-frequency energy)
        # Simple approximation: high-pass filter via diff
        high_freq = np.abs(np.diff(audio))
        brightness = min(1.0, np.mean(high_freq) * 100)

        # 3. Dynamics (crest factor normalized)
        peak = np.max(np.abs(audio))
        if rms > 0:
            crest_db = 20 * np.log10(peak / rms)
            dynamics = min(1.0, crest_db / 20)  # Normalize to 0-1
        else:
            dynamics = 0.5

        # 4. Vocal presence (estimate from spectral centroid)
        # Vocals typically 300-3000 Hz, we approximate with spectral shape
        if len(audio) > 2048:
            # Simple FFT-based estimate
            fft = np.abs(np.fft.rfft(audio[:2048]))
            spectral_centroid = np.sum(fft * np.arange(len(fft))) / (np.sum(fft) + 1e-10)
            # Normalize: higher centroid (0.2-0.4 of spectrum) = more vocals
            vocal_presence = min(1.0, max(0.0, (spectral_centroid / len(fft) - 0.1) * 5))
        else:
            vocal_presence = 0.5

        # 5. Tempo energy (percussive/rhythmic content)
        # Estimate from envelope fluctuations
        envelope = np.abs(audio)
        envelope_smooth = np.convolve(envelope, np.ones(441) / 441, mode='same')  # 10ms smooth
        fluctuations = np.abs(np.diff(envelope_smooth))
        tempo_energy = min(1.0, np.mean(fluctuations) * 200)

        return AudioFeatures(
            energy=float(energy),
            brightness=float(brightness),
            dynamics=float(dynamics),
            vocal_presence=float(vocal_presence),
            tempo_energy=float(tempo_energy)
        )


class AudioContentPredictor:
    """
    Combines audio analysis with user behavior to predict presets.

    Enhances BranchPredictor with audio-content-aware predictions.
    """

    def __init__(self, analyzer: Optional[AudioContentAnalyzer] = None):
        """
        Initialize audio-content predictor.

        Args:
            analyzer: AudioContentAnalyzer instance (creates new if None)
        """
        self.analyzer = analyzer or AudioContentAnalyzer()

        # Preset affinity rules based on audio characteristics
        # These are learned/tuned based on user behavior patterns
        self.affinity_rules = {
            'high_energy': {'punchy': 0.8, 'bright': 0.6, 'adaptive': 0.4},
            'low_energy': {'gentle': 0.7, 'warm': 0.6, 'adaptive': 0.3},
            'high_brightness': {'bright': 0.8, 'punchy': 0.5, 'adaptive': 0.3},
            'high_vocals': {'bright': 0.7, 'adaptive': 0.5, 'warm': 0.3},
            'high_dynamics': {'adaptive': 0.8, 'punchy': 0.5, 'gentle': 0.2},
            'low_dynamics': {'gentle': 0.6, 'warm': 0.7, 'adaptive': 0.3},
            'high_tempo': {'punchy': 0.8, 'bright': 0.6, 'adaptive': 0.4}
        }

    async def predict_preset_for_chunk(
        self,
        audio_data: Optional[np.ndarray] = None,
        filepath: Optional[str] = None,
        chunk_idx: int = 0
    ) -> PresetAffinityScores:
        """
        Predict preset affinity based on audio content.

        Args:
            audio_data: Audio data (if already loaded)
            filepath: Path to audio file
            chunk_idx: Chunk index

        Returns:
            PresetAffinityScores with 0.0-1.0 values per preset
        """
        # Analyze audio
        features = await self.analyzer.analyze_chunk_fast(audio_data, filepath, chunk_idx)

        # Calculate affinity scores based on features
        scores = PresetAffinityScores()

        # High energy → punchy/bright
        if features.energy > 0.7:
            for preset, score in self.affinity_rules['high_energy'].items():
                setattr(scores, preset, getattr(scores, preset) + score * 0.5)

        # Low energy → gentle/warm
        if features.energy < 0.3:
            for preset, score in self.affinity_rules['low_energy'].items():
                setattr(scores, preset, getattr(scores, preset) + score * 0.5)

        # High brightness → bright
        if features.brightness > 0.6:
            for preset, score in self.affinity_rules['high_brightness'].items():
                setattr(scores, preset, getattr(scores, preset) + score * 0.4)

        # Vocal presence → bright
        if features.vocal_presence > 0.6:
            for preset, score in self.affinity_rules['high_vocals'].items():
                setattr(scores, preset, getattr(scores, preset) + score * 0.3)

        # High dynamics → adaptive (needs processing)
        if features.dynamics > 0.7:
            for preset, score in self.affinity_rules['high_dynamics'].items():
                setattr(scores, preset, getattr(scores, preset) + score * 0.4)

        # Low dynamics (compressed) → gentle/warm
        if features.dynamics < 0.3:
            for preset, score in self.affinity_rules['low_dynamics'].items():
                setattr(scores, preset, getattr(scores, preset) + score * 0.3)

        # High tempo/rhythm → punchy
        if features.tempo_energy > 0.6:
            for preset, score in self.affinity_rules['high_tempo'].items():
                setattr(scores, preset, getattr(scores, preset) + score * 0.4)

        # Normalize scores to 0-1 range
        scores_dict = scores.to_dict()
        max_score = max(scores_dict.values())
        if max_score > 1.0:
            for key in scores_dict:
                setattr(scores, key, scores_dict[key] / max_score)

        logger.debug(
            f"Audio prediction for chunk {chunk_idx}: "
            f"energy={features.energy:.2f}, brightness={features.brightness:.2f}, "
            f"top_preset={scores.get_top_preset()}"
        )

        return scores

    async def predict_upcoming_chunks(
        self,
        filepath: str,
        current_chunk: int,
        num_chunks: int = 3
    ) -> Dict[int, PresetAffinityScores]:
        """
        Predict preset affinities for upcoming chunks.

        Args:
            filepath: Path to audio file
            current_chunk: Current playback chunk
            num_chunks: Number of upcoming chunks to analyze

        Returns:
            Dictionary mapping chunk_idx to PresetAffinityScores
        """
        predictions = {}

        for offset in range(1, num_chunks + 1):
            chunk_idx = current_chunk + offset

            try:
                scores = await self.predict_preset_for_chunk(
                    filepath=filepath,
                    chunk_idx=chunk_idx
                )
                predictions[chunk_idx] = scores

            except Exception as e:
                logger.warning(f"Failed to predict chunk {chunk_idx}: {e}")
                # Use neutral scores as fallback
                predictions[chunk_idx] = PresetAffinityScores()

        return predictions

    def combine_with_user_prediction(
        self,
        user_predictions: List[Tuple[str, float]],
        audio_scores: PresetAffinityScores,
        user_weight: float = 0.7,
        audio_weight: float = 0.3
    ) -> List[Tuple[str, float]]:
        """
        Combine user behavior predictions with audio content predictions.

        Args:
            user_predictions: Predictions from BranchPredictor (user behavior)
            audio_scores: Predictions from audio analysis
            user_weight: Weight for user behavior (0-1)
            audio_weight: Weight for audio content (0-1)

        Returns:
            Combined predictions sorted by probability
        """
        # Normalize weights
        total_weight = user_weight + audio_weight
        user_weight /= total_weight
        audio_weight /= total_weight

        # Combine scores
        combined = {}
        audio_dict = audio_scores.to_dict()

        # Start with user predictions
        for preset, prob in user_predictions:
            combined[preset] = prob * user_weight

        # Add audio scores
        for preset, score in audio_dict.items():
            if preset in combined:
                combined[preset] += score * audio_weight
            else:
                combined[preset] = score * audio_weight

        # Sort by combined score
        sorted_predictions = sorted(
            combined.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return sorted_predictions


# Global instance
audio_content_predictor: Optional[AudioContentPredictor] = None


def get_audio_content_predictor() -> AudioContentPredictor:
    """Get or create global audio content predictor instance."""
    global audio_content_predictor
    if audio_content_predictor is None:
        audio_content_predictor = AudioContentPredictor()
    return audio_content_predictor
