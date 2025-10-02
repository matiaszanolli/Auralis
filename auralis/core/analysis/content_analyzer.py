# -*- coding: utf-8 -*-

"""
Content Analyzer
~~~~~~~~~~~~~~~~

Enhanced content analysis for adaptive audio processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict, Any

from ...dsp.unified import (
    rms, spectral_centroid, spectral_rolloff, zero_crossing_rate,
    crest_factor, tempo_estimate, calculate_loudness_units, stereo_width_analysis
)
from ...analysis.ml_genre_classifier import create_ml_genre_classifier
from ...utils.logging import debug


class ContentAnalyzer:
    """Enhanced content analysis for adaptive processing with ML genre classification"""

    def __init__(self, sample_rate: int = 44100, use_ml_classification: bool = True):
        """
        Initialize content analyzer

        Args:
            sample_rate: Audio sample rate
            use_ml_classification: Whether to use ML-based genre classification
        """
        self.sample_rate = sample_rate
        self.genre_confidence_threshold = 0.6
        self.use_ml_classification = use_ml_classification

        # Initialize ML genre classifier
        if use_ml_classification:
            try:
                self.ml_classifier = create_ml_genre_classifier()
                debug("ML genre classifier initialized successfully")
            except Exception as e:
                debug(f"Failed to initialize ML classifier, falling back to rule-based: {e}")
                self.ml_classifier = None
                self.use_ml_classification = False
        else:
            self.ml_classifier = None

    def analyze_content(self, audio: np.ndarray) -> Dict[str, Any]:
        """
        Analyze audio content for adaptive processing

        Args:
            audio: Audio signal to analyze

        Returns:
            Dictionary containing content analysis results
        """
        debug("Analyzing audio content for adaptive processing")

        if audio.ndim == 2:
            # Convert stereo to mono for analysis
            mono_audio = np.mean(audio, axis=1)
        else:
            mono_audio = audio

        # Basic audio features
        rms_value = rms(audio)
        peak_value = np.max(np.abs(audio))
        crest_factor_db = crest_factor(audio)

        # Spectral features
        centroid = spectral_centroid(mono_audio, self.sample_rate)
        rolloff = spectral_rolloff(mono_audio, self.sample_rate)
        zcr = zero_crossing_rate(mono_audio)

        # Temporal features
        estimated_tempo = tempo_estimate(mono_audio, self.sample_rate)

        # Stereo analysis (if applicable)
        stereo_info = {}
        if audio.ndim == 2 and audio.shape[1] == 2:
            stereo_info = {
                "width": stereo_width_analysis(audio),
                "is_stereo": True
            }
        else:
            stereo_info = {
                "width": 0.5,
                "is_stereo": False
            }

        # Advanced genre classification (ML or rule-based)
        genre_info = self._classify_genre_advanced(audio)

        content_profile = {
            # Basic properties
            "rms": float(rms_value),
            "peak": float(peak_value),
            "crest_factor_db": float(crest_factor_db),
            "estimated_lufs": float(calculate_loudness_units(audio, self.sample_rate)),

            # Spectral properties
            "spectral_centroid": float(centroid),
            "spectral_rolloff": float(rolloff),
            "zero_crossing_rate": float(zcr),

            # Temporal properties
            "estimated_tempo": float(estimated_tempo),

            # Stereo properties
            "stereo_info": stereo_info,

            # Genre classification
            "genre_info": genre_info,

            # Energy characteristics
            "energy_level": self._categorize_energy_level(rms_value),
            "dynamic_range": self._estimate_dynamic_range(audio)
        }

        debug(f"Content analysis complete: genre={genre_info['primary']}, "
              f"energy={content_profile['energy_level']}, "
              f"tempo={estimated_tempo:.1f} BPM")

        return content_profile

    def _classify_genre_advanced(self, audio: np.ndarray) -> Dict[str, Any]:
        """Advanced genre classification using ML or rule-based fallback"""

        if self.use_ml_classification and self.ml_classifier is not None:
            try:
                # Use ML classifier
                ml_result = self.ml_classifier.classify(audio)
                debug(f"ML classification: {ml_result['primary']} (confidence: {ml_result['confidence']:.3f})")
                return ml_result
            except Exception as e:
                debug(f"ML classification failed, falling back to rule-based: {e}")

        # Fall back to rule-based classification
        return self._classify_genre_rule_based(audio)

    def _classify_genre_rule_based(self, audio: np.ndarray) -> Dict[str, Any]:
        """Rule-based genre classification (fallback method)"""

        # Convert to mono for analysis
        if audio.ndim == 2:
            mono_audio = np.mean(audio, axis=1)
        else:
            mono_audio = audio

        # Extract basic features
        centroid = spectral_centroid(mono_audio, self.sample_rate)
        rolloff = spectral_rolloff(mono_audio, self.sample_rate)
        zcr = zero_crossing_rate(mono_audio)
        tempo = tempo_estimate(mono_audio, self.sample_rate)
        crest_factor_db = crest_factor(audio)

        return self._classify_genre(centroid, rolloff, zcr, tempo, crest_factor_db)

    def _classify_genre(self, centroid: float, rolloff: float, zcr: float,
                       tempo: float, crest_factor_db: float) -> Dict[str, Any]:
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
        primary_genre = max(genre_scores, key=genre_scores.get)
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

    def _estimate_dynamic_range(self, audio: np.ndarray) -> float:
        """Estimate dynamic range in dB"""
        if len(audio) == 0:
            return 0.0

        # Calculate RMS in 1-second windows
        window_size = 44100  # 1 second at 44.1 kHz
        rms_values = []

        for i in range(0, len(audio) - window_size, window_size // 2):
            window = audio[i:i + window_size]
            if audio.ndim == 2:
                window_rms = np.sqrt(np.mean(np.mean(window, axis=1) ** 2))
            else:
                window_rms = np.sqrt(np.mean(window ** 2))
            rms_values.append(window_rms)

        if len(rms_values) < 2:
            return 20.0  # Default dynamic range

        rms_values = np.array(rms_values)
        rms_values = rms_values[rms_values > 1e-6]  # Remove silence

        if len(rms_values) == 0:
            return 20.0

        # Calculate dynamic range as difference between 95th and 10th percentile
        loud_level = np.percentile(rms_values, 95)
        quiet_level = np.percentile(rms_values, 10)

        if quiet_level > 0:
            dynamic_range = 20 * np.log10(loud_level / quiet_level)
            return float(np.clip(dynamic_range, 0, 60))
        else:
            return 20.0


def create_content_analyzer(sample_rate: int = 44100,
                           use_ml_classification: bool = True) -> ContentAnalyzer:
    """
    Factory function to create content analyzer

    Args:
        sample_rate: Audio sample rate
        use_ml_classification: Whether to use ML-based genre classification

    Returns:
        Configured ContentAnalyzer instance
    """
    return ContentAnalyzer(sample_rate, use_ml_classification)
