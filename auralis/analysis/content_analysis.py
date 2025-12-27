# -*- coding: utf-8 -*-

"""
Content Analysis Framework
~~~~~~~~~~~~~~~~~~~~~~~~~~

Advanced audio content analysis for adaptive mastering

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Comprehensive audio content analysis system for intelligent processing decisions
"""

from dataclasses import dataclass
from typing import Any, Dict

import numpy as np

from ..dsp.unified import (
    crest_factor,
    rms,
    spectral_centroid,
    spectral_rolloff,
    tempo_estimate,
    zero_crossing_rate,
)
from ..utils.logging import debug, info
from .content import (
    ContentFeatures,
    FeatureExtractor,
    GenreAnalyzer,
    GenreClassification,
    MoodAnalysis,
    MoodAnalyzer,
    RecommendationEngine,
    create_feature_extractor,
    create_genre_analyzer,
    create_mood_analyzer,
    create_recommendation_engine,
)
from .dynamic_range import DynamicRangeAnalyzer
from .loudness_meter import LoudnessMeter
from .phase_correlation import PhaseCorrelationAnalyzer
from .quality_metrics import QualityMetrics
from .spectrum_analyzer import (  # type: ignore[attr-defined]
    SpectrumAnalyzer,
    SpectrumSettings,
)


@dataclass
class ContentProfile:
    """Comprehensive content analysis profile"""
    features: ContentFeatures
    genre: GenreClassification
    mood: MoodAnalysis
    quality_assessment: Dict[str, Any]
    stereo_analysis: Dict[str, Any]
    processing_recommendations: Dict[str, Any]


class AdvancedContentAnalyzer:
    """Advanced content analysis for adaptive mastering"""

    def __init__(self, sample_rate: int = 44100):
        """
        Initialize advanced content analyzer

        Args:
            sample_rate: Audio sample rate
        """
        self.sample_rate = sample_rate

        # Initialize modular analysis components
        self.feature_extractor = create_feature_extractor(sample_rate)
        self.genre_analyzer = create_genre_analyzer()
        self.mood_analyzer = create_mood_analyzer()
        self.recommendation_engine = create_recommendation_engine()

        # Initialize existing analysis components
        self.spectrum_analyzer = SpectrumAnalyzer(
            SpectrumSettings(
                fft_size=8192,
                frequency_bands=128,
                sample_rate=sample_rate
            )
        )
        self.loudness_meter = LoudnessMeter(sample_rate)
        self.phase_analyzer = PhaseCorrelationAnalyzer(sample_rate)
        self.dynamic_range_analyzer = DynamicRangeAnalyzer(sample_rate)
        self.quality_metrics = QualityMetrics(sample_rate)

    def analyze_content(self, audio_data: np.ndarray) -> ContentProfile:
        """
        Perform comprehensive content analysis

        Args:
            audio_data: Audio signal to analyze

        Returns:
            ContentProfile with complete analysis results
        """
        debug("Starting comprehensive content analysis")

        # Ensure stereo for complete analysis
        if audio_data.ndim == 1:
            stereo_audio = np.column_stack([audio_data, audio_data])
            mono_audio = audio_data
        else:
            stereo_audio = audio_data
            mono_audio = np.mean(audio_data, axis=1)

        # Extract basic features using modular extractor
        features = self._extract_content_features(mono_audio, stereo_audio)

        # Classify genre using modular analyzer
        genre = self.genre_analyzer.classify_genre(features)

        # Analyze mood and energy using modular analyzer
        mood = self.mood_analyzer.analyze_mood(features, mono_audio)

        # Quality assessment
        quality_assessment = self.quality_metrics.assess_quality(stereo_audio)

        # Stereo analysis
        stereo_analysis = self._analyze_stereo_characteristics(stereo_audio)

        # Generate processing recommendations using modular engine
        recommendations = self.recommendation_engine.generate_recommendations(
            features, genre, mood, quality_assessment
        )

        content_profile = ContentProfile(
            features=features,
            genre=genre,
            mood=mood,
            quality_assessment=quality_assessment.__dict__,
            stereo_analysis=stereo_analysis,
            processing_recommendations=recommendations
        )

        info(f"Content analysis complete: {genre.primary_genre} "
             f"({genre.confidence:.2f}), {mood.energy_level} energy")

        return content_profile

    def _extract_content_features(self, mono_audio: np.ndarray,
                                 stereo_audio: np.ndarray) -> ContentFeatures:
        """Extract comprehensive audio features"""

        # Amplitude characteristics
        rms_energy = float(rms(mono_audio))
        peak_energy = float(np.max(np.abs(mono_audio)))
        crest_factor_db = float(crest_factor(mono_audio))
        dynamic_range_db = float(self.feature_extractor.calculate_dynamic_range(mono_audio))

        # Spectral characteristics
        spec_centroid = float(spectral_centroid(mono_audio, self.sample_rate))
        spec_rolloff = float(spectral_rolloff(mono_audio, self.sample_rate))
        spec_spread = float(self.feature_extractor.calculate_spectral_spread(mono_audio))
        spec_flux = float(self.feature_extractor.calculate_spectral_flux(mono_audio))

        # Temporal characteristics
        zcr = float(zero_crossing_rate(mono_audio))
        tempo = float(tempo_estimate(mono_audio, self.sample_rate))
        attack_time = float(self.feature_extractor.estimate_attack_time(mono_audio))

        # Tonal characteristics
        fundamental_freq = float(self.feature_extractor.estimate_fundamental_frequency(mono_audio))
        harmonic_ratio = float(self.feature_extractor.calculate_harmonic_ratio(mono_audio))
        inharmonicity = float(self.feature_extractor.calculate_inharmonicity(mono_audio))

        # Rhythmic characteristics
        rhythm_strength = float(self.feature_extractor.calculate_rhythm_strength(mono_audio))
        beat_consistency = float(self.feature_extractor.calculate_beat_consistency(mono_audio))

        return ContentFeatures(
            rms_energy=rms_energy,
            peak_energy=peak_energy,
            crest_factor_db=crest_factor_db,
            dynamic_range_db=dynamic_range_db,
            spectral_centroid=spec_centroid,
            spectral_rolloff=spec_rolloff,
            spectral_spread=spec_spread,
            spectral_flux=spec_flux,
            zero_crossing_rate=zcr,
            tempo_estimate=tempo,
            attack_time_ms=attack_time,
            fundamental_frequency=fundamental_freq,
            harmonic_ratio=harmonic_ratio,
            inharmonicity=inharmonicity,
            rhythm_strength=rhythm_strength,
            beat_consistency=beat_consistency
        )

    def _analyze_mood(self, features: ContentFeatures, audio: np.ndarray) -> MoodAnalysis:
        """Backward compatibility wrapper for mood analysis"""
        return self.mood_analyzer.analyze_mood(features, audio)

    def _classify_genre(self, features: ContentFeatures) -> GenreClassification:
        """Backward compatibility wrapper for genre classification"""
        return self.genre_analyzer.classify_genre(features)

    def _generate_processing_recommendations(self, features: ContentFeatures,
                                            genre: GenreClassification,
                                            mood: MoodAnalysis,
                                            quality: Any) -> Dict[str, Any]:
        """Backward compatibility wrapper for recommendations"""
        return self.recommendation_engine.generate_recommendations(features, genre, mood, quality)

    def _analyze_stereo_characteristics(self, stereo_audio: np.ndarray) -> Dict[str, Any]:
        """Analyze stereo characteristics"""
        # Correlation analysis
        correlation = self.phase_analyzer.analyze_correlation(stereo_audio)

        # Calculate stereo width
        left = stereo_audio[:, 0]
        right = stereo_audio[:, 1]
        mid = (left + right) / 2
        side = (left - right) / 2

        mid_energy = float(np.sqrt(np.mean(mid ** 2)))
        side_energy = float(np.sqrt(np.mean(side ** 2)))

        if mid_energy > 1e-6:
            stereo_width = side_energy / mid_energy
        else:
            stereo_width = 0.0

        return {
            "correlation": correlation.__dict__ if hasattr(correlation, '__dict__') else correlation,
            "stereo_width": stereo_width,
            "mid_energy": mid_energy,
            "side_energy": side_energy
        }


# Convenience function for quick content analysis
def analyze_audio_content(audio_data: np.ndarray, sample_rate: int = 44100) -> ContentProfile:
    """Quick content analysis function"""
    analyzer = AdvancedContentAnalyzer(sample_rate)
    return analyzer.analyze_content(audio_data)
