"""
Genre classification for ContentAnalyzer (split from content_analyzer.py,
#5838): the ML-first / rule-based-fallback dispatch, the rule table, and the
energy-level bucketing.
"""

from typing import Any

import numpy as np

from ...dsp.utils.audio_info import to_mono
from ...dsp.utils.spectral import crest_factor, spectral_centroid, spectral_rolloff, tempo_estimate, zero_crossing_rate
from ...utils.logging import debug


class GenreClassificationMixin:
    """Reads the ML/tempo settings ContentAnalyzer.__init__ sets."""

    sample_rate: int
    use_ml_classification: bool
    ml_classifier: Any
    use_tempo_detection: bool
    genre_confidence_threshold: float

    def _classify_genre_advanced(self, audio: np.ndarray) -> dict[str, Any]:
        """Advanced genre classification using ML or rule-based fallback"""

        if self.use_ml_classification and self.ml_classifier is not None:
            try:
                # Use ML classifier
                ml_result: dict[str, Any] = self.ml_classifier.classify(audio)
                debug(f"ML classification: {ml_result['primary']} (confidence: {ml_result['confidence']:.3f})")
                return ml_result
            except Exception as e:
                debug(f"ML classification failed, falling back to rule-based: {e}")

        # Fall back to rule-based classification
        return self._classify_genre_rule_based(audio)

    def _classify_genre_rule_based(self, audio: np.ndarray) -> dict[str, Any]:
        """Rule-based genre classification (fallback method)"""

        # Convert to mono for analysis
        mono_audio = to_mono(audio)

        # Extract basic features
        centroid = spectral_centroid(mono_audio, self.sample_rate)
        zcr = zero_crossing_rate(mono_audio)
        tempo = tempo_estimate(mono_audio, self.sample_rate) if self.use_tempo_detection else 120.0
        crest_factor_db = crest_factor(audio)

        return self._classify_genre(centroid, zcr, tempo, crest_factor_db)

    def _classify_genre(self, centroid: float, zcr: float,
                       tempo: float, crest_factor_db: float) -> dict[str, Any]:
        """Simple genre classification based on audio features"""

        # Genre classification rules (simplified)
        genre_scores = {
            "classical": 0.0,
            "rock": 0.0,
            "electronic": 0.0,
            "jazz": 0.0,
            "pop": 0.0,
            "hip_hop": 0.0,
            "acoustic": 0.0,
            "ambient": 0.0
        }

        # Tempo-based classification
        if tempo < 80:
            genre_scores["ambient"] += 0.3
            genre_scores["classical"] += 0.2
        elif tempo > 140:
            genre_scores["electronic"] += 0.3
            genre_scores["rock"] += 0.2

        # Spectral centroid-based classification
        if centroid > 3000:
            genre_scores["electronic"] += 0.2
            genre_scores["rock"] += 0.2
        elif centroid < 1500:
            genre_scores["classical"] += 0.2
            genre_scores["ambient"] += 0.2

        # Zero crossing rate-based classification
        if zcr > 0.1:
            genre_scores["rock"] += 0.2
            genre_scores["electronic"] += 0.1
        elif zcr < 0.05:
            genre_scores["classical"] += 0.2

        # Crest factor-based classification
        if crest_factor_db > 15:
            genre_scores["classical"] += 0.3
            genre_scores["jazz"] += 0.2
        elif crest_factor_db < 8:
            genre_scores["electronic"] += 0.2
            genre_scores["pop"] += 0.2

        # Find the genre with highest score
        primary_genre = max(genre_scores, key=lambda x: genre_scores[x])
        confidence = genre_scores[primary_genre]

        # If confidence is too low, use "pop" as safe default
        if confidence < self.genre_confidence_threshold:
            primary_genre = "pop"
            confidence = 0.5

        return {
            "primary": primary_genre,
            "confidence": confidence,
            "scores": genre_scores
        }

    def _categorize_energy_level(self, rms_value: float) -> str:
        """Categorize energy level of audio"""
        if rms_value > 0.3:
            return "high"
        elif rms_value > 0.1:
            return "medium"
        else:
            return "low"
