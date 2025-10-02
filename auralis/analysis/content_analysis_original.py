# -*- coding: utf-8 -*-

"""
Content Analysis Framework
~~~~~~~~~~~~~~~~~~~~~~~~~~

Advanced audio content analysis for adaptive mastering

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Comprehensive audio content analysis system for intelligent processing decisions
"""

import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from scipy import signal
from scipy.fft import fft, fftfreq

from .spectrum_analyzer import SpectrumAnalyzer, SpectrumSettings
from .loudness_meter import LoudnessMeter
from .phase_correlation import PhaseCorrelationAnalyzer
from .dynamic_range import DynamicRangeAnalyzer
from .quality_metrics import QualityMetrics
from ..dsp.unified import (
    spectral_centroid, spectral_rolloff, zero_crossing_rate,
    crest_factor, tempo_estimate, rms, energy_profile
)
from ..utils.logging import debug, info


@dataclass
class ContentFeatures:
    """Basic audio content features"""
    # Amplitude characteristics
    rms_energy: float
    peak_energy: float
    crest_factor_db: float
    dynamic_range_db: float

    # Spectral characteristics
    spectral_centroid: float
    spectral_rolloff: float
    spectral_spread: float
    spectral_flux: float

    # Temporal characteristics
    zero_crossing_rate: float
    tempo_estimate: float
    attack_time_ms: float

    # Tonal characteristics
    fundamental_frequency: float
    harmonic_ratio: float
    inharmonicity: float

    # Rhythmic characteristics
    rhythm_strength: float
    beat_consistency: float


@dataclass
class GenreClassification:
    """Genre classification results"""
    primary_genre: str
    confidence: float
    genre_scores: Dict[str, float]
    features_used: List[str]


@dataclass
class MoodAnalysis:
    """Mood and energy analysis"""
    energy_level: str  # "low", "medium", "high"
    valence: float     # 0-1 (sad to happy)
    arousal: float     # 0-1 (calm to energetic)
    danceability: float # 0-1
    acousticness: float # 0-1


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
        self.sample_rate = sample_rate

        # Initialize analysis components
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

        # Genre classification rules
        self.genre_rules = self._create_genre_classification_rules()

        # Mood analysis parameters
        self.mood_parameters = self._create_mood_parameters()

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

        # Extract basic features
        features = self._extract_content_features(mono_audio, stereo_audio)

        # Classify genre
        genre = self._classify_genre(features)

        # Analyze mood and energy
        mood = self._analyze_mood(features, mono_audio)

        # Quality assessment
        quality_assessment = self.quality_metrics.assess_quality(stereo_audio)

        # Stereo analysis
        stereo_analysis = self._analyze_stereo_characteristics(stereo_audio)

        # Generate processing recommendations
        recommendations = self._generate_processing_recommendations(
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
        dynamic_range_db = float(self._calculate_dynamic_range(mono_audio))

        # Spectral characteristics
        spec_centroid = float(spectral_centroid(mono_audio, self.sample_rate))
        spec_rolloff = float(spectral_rolloff(mono_audio, self.sample_rate))
        spec_spread = float(self._calculate_spectral_spread(mono_audio))
        spec_flux = float(self._calculate_spectral_flux(mono_audio))

        # Temporal characteristics
        zcr = float(zero_crossing_rate(mono_audio))
        tempo = float(tempo_estimate(mono_audio, self.sample_rate))
        attack_time = float(self._estimate_attack_time(mono_audio))

        # Tonal characteristics
        fundamental_freq = float(self._estimate_fundamental_frequency(mono_audio))
        harmonic_ratio = float(self._calculate_harmonic_ratio(mono_audio))
        inharmonicity = float(self._calculate_inharmonicity(mono_audio))

        # Rhythmic characteristics
        rhythm_strength = float(self._calculate_rhythm_strength(mono_audio))
        beat_consistency = float(self._calculate_beat_consistency(mono_audio))

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

    def _calculate_dynamic_range(self, audio: np.ndarray) -> float:
        """Calculate dynamic range in dB"""
        window_size = int(0.5 * self.sample_rate)  # 500ms windows
        hop_size = window_size // 2

        rms_values = []
        for i in range(0, len(audio) - window_size, hop_size):
            window = audio[i:i + window_size]
            rms_val = np.sqrt(np.mean(window ** 2))
            if rms_val > 1e-6:  # Avoid silence
                rms_values.append(rms_val)

        if len(rms_values) < 2:
            return 20.0

        rms_values = np.array(rms_values)
        loud_level = np.percentile(rms_values, 95)
        quiet_level = np.percentile(rms_values, 10)

        if quiet_level > 0:
            return 20 * np.log10(loud_level / quiet_level)
        else:
            return 20.0

    def _calculate_spectral_spread(self, audio: np.ndarray) -> float:
        """Calculate spectral spread (bandwidth)"""
        fft_result = fft(audio[:8192])  # Use first 8192 samples
        magnitude = np.abs(fft_result[:4096])
        freqs = fftfreq(8192, 1/self.sample_rate)[:4096]

        # Calculate centroid
        if np.sum(magnitude) > 0:
            centroid = np.sum(freqs * magnitude) / np.sum(magnitude)
            # Calculate spread around centroid
            spread = np.sqrt(np.sum(((freqs - centroid) ** 2) * magnitude) / np.sum(magnitude))
            return spread
        return 1000.0  # Default spread

    def _calculate_spectral_flux(self, audio: np.ndarray) -> float:
        """Calculate spectral flux (rate of spectral change)"""
        window_size = 2048
        hop_size = 1024

        flux_values = []
        prev_spectrum = None

        for i in range(0, len(audio) - window_size, hop_size):
            window = audio[i:i + window_size]
            spectrum = np.abs(fft(window)[:window_size//2])

            if prev_spectrum is not None:
                flux = np.sum(np.maximum(0, spectrum - prev_spectrum))
                flux_values.append(flux)

            prev_spectrum = spectrum

        return np.mean(flux_values) if flux_values else 0.0

    def _estimate_attack_time(self, audio: np.ndarray) -> float:
        """Estimate average attack time in milliseconds"""
        # Simple onset detection and attack time estimation
        energy = energy_profile(audio, window_size=512)

        # Find onsets (energy increases)
        onset_threshold = np.mean(energy) + np.std(energy)
        onsets = []

        for i in range(1, len(energy) - 1):
            if (energy[i] > onset_threshold and
                energy[i] > energy[i-1] and
                energy[i] > energy[i+1]):
                onsets.append(i)

        if len(onsets) < 2:
            return 50.0  # Default attack time

        # Estimate attack times around onsets
        attack_times = []
        hop_size = 256  # For energy profile calculation

        for onset_idx in onsets[:10]:  # Analyze first 10 onsets
            start_sample = onset_idx * hop_size
            if start_sample + 2048 < len(audio):
                segment = audio[start_sample:start_sample + 2048]

                # Find 10% to 90% rise time
                envelope = np.abs(segment)
                max_val = np.max(envelope)

                if max_val > 0:
                    ten_percent = max_val * 0.1
                    ninety_percent = max_val * 0.9

                    ten_idx = np.where(envelope >= ten_percent)[0]
                    ninety_idx = np.where(envelope >= ninety_percent)[0]

                    if len(ten_idx) > 0 and len(ninety_idx) > 0:
                        attack_samples = ninety_idx[0] - ten_idx[0]
                        attack_time_ms = (attack_samples / self.sample_rate) * 1000
                        attack_times.append(attack_time_ms)

        return np.mean(attack_times) if attack_times else 50.0

    def _estimate_fundamental_frequency(self, audio: np.ndarray) -> float:
        """Estimate fundamental frequency using autocorrelation"""
        # Use middle section of audio
        start = len(audio) // 4
        end = 3 * len(audio) // 4
        segment = audio[start:end]

        if len(segment) < 4096:
            return 0.0

        # Autocorrelation
        autocorr = np.correlate(segment, segment, mode='full')
        autocorr = autocorr[len(autocorr)//2:]

        # Find peaks in autocorrelation
        min_period = int(self.sample_rate / 800)  # 800 Hz max
        max_period = int(self.sample_rate / 80)   # 80 Hz min

        if max_period >= len(autocorr):
            return 0.0

        search_range = autocorr[min_period:max_period]
        if len(search_range) == 0:
            return 0.0

        peak_idx = np.argmax(search_range) + min_period
        fundamental = self.sample_rate / peak_idx

        return fundamental if 80 <= fundamental <= 800 else 0.0

    def _calculate_harmonic_ratio(self, audio: np.ndarray) -> float:
        """Calculate harmonic to noise ratio"""
        fft_result = fft(audio[:8192])
        magnitude = np.abs(fft_result[:4096])

        # Find peaks (harmonics)
        from scipy.signal import find_peaks
        peaks, _ = find_peaks(magnitude, height=np.max(magnitude) * 0.1)

        if len(peaks) == 0:
            return 0.0

        # Sum energy at peaks (harmonic) vs total energy
        harmonic_energy = np.sum(magnitude[peaks])
        total_energy = np.sum(magnitude)

        if total_energy > 0:
            return harmonic_energy / total_energy
        else:
            return 0.0

    def _calculate_inharmonicity(self, audio: np.ndarray) -> float:
        """Calculate inharmonicity (deviation from perfect harmonic series)"""
        fundamental = self._estimate_fundamental_frequency(audio)

        if fundamental == 0:
            return 1.0  # Maximum inharmonicity for non-tonal content

        fft_result = fft(audio[:8192])
        magnitude = np.abs(fft_result[:4096])
        freqs = fftfreq(8192, 1/self.sample_rate)[:4096]

        # Expected harmonic frequencies
        harmonics = [fundamental * i for i in range(1, 11)]  # First 10 harmonics

        deviations = []
        for harmonic_freq in harmonics:
            if harmonic_freq < self.sample_rate / 2:
                # Find closest frequency bin
                closest_idx = np.argmin(np.abs(freqs - harmonic_freq))

                # Look for peak near expected harmonic
                search_range = 10  # bins
                start_idx = max(0, closest_idx - search_range)
                end_idx = min(len(magnitude), closest_idx + search_range)

                local_peak_idx = np.argmax(magnitude[start_idx:end_idx]) + start_idx
                actual_freq = freqs[local_peak_idx]

                if magnitude[local_peak_idx] > np.max(magnitude) * 0.05:
                    deviation = abs(actual_freq - harmonic_freq) / harmonic_freq
                    deviations.append(deviation)

        return np.mean(deviations) if deviations else 1.0

    def _calculate_rhythm_strength(self, audio: np.ndarray) -> float:
        """Calculate rhythmic strength"""
        # Calculate onset strength
        onset_envelope = self._calculate_onset_strength(audio)

        # Autocorrelation of onset envelope to find rhythmic patterns
        autocorr = np.correlate(onset_envelope, onset_envelope, mode='full')
        autocorr = autocorr[len(autocorr)//2:]

        # Look for peaks corresponding to beat periods
        hop_size = 512
        fps = self.sample_rate / hop_size

        min_bpm = 60
        max_bpm = 200
        min_period = int(60 * fps / max_bpm)
        max_period = int(60 * fps / min_bpm)

        if max_period >= len(autocorr):
            return 0.0

        rhythm_range = autocorr[min_period:max_period]
        rhythm_strength = np.max(rhythm_range) / (np.mean(autocorr) + 1e-6)

        return min(rhythm_strength / 10.0, 1.0)  # Normalize

    def _calculate_beat_consistency(self, audio: np.ndarray) -> float:
        """Calculate beat consistency (regularity)"""
        onset_times = self._detect_onsets(audio)

        if len(onset_times) < 4:
            return 0.0

        # Calculate inter-onset intervals
        intervals = np.diff(onset_times)

        if len(intervals) < 2:
            return 0.0

        # Measure consistency as inverse of coefficient of variation
        mean_interval = np.mean(intervals)
        std_interval = np.std(intervals)

        if mean_interval > 0:
            consistency = 1.0 / (1.0 + std_interval / mean_interval)
            return consistency
        else:
            return 0.0

    def _calculate_onset_strength(self, audio: np.ndarray) -> np.ndarray:
        """Calculate onset strength envelope"""
        window_size = 1024
        hop_size = 512

        onset_strength = []
        prev_spectrum = None

        for i in range(0, len(audio) - window_size, hop_size):
            window = audio[i:i + window_size]
            spectrum = np.abs(fft(window)[:window_size//2])

            if prev_spectrum is not None:
                # Spectral flux (positive changes only)
                flux = np.sum(np.maximum(0, spectrum - prev_spectrum))
                onset_strength.append(flux)
            else:
                onset_strength.append(0)

            prev_spectrum = spectrum

        return np.array(onset_strength)

    def _detect_onsets(self, audio: np.ndarray) -> np.ndarray:
        """Detect onset times"""
        onset_strength = self._calculate_onset_strength(audio)

        # Peak picking
        threshold = np.mean(onset_strength) + np.std(onset_strength)

        onsets = []
        hop_size = 512

        for i in range(1, len(onset_strength) - 1):
            if (onset_strength[i] > threshold and
                onset_strength[i] > onset_strength[i-1] and
                onset_strength[i] > onset_strength[i+1]):
                onset_time = i * hop_size / self.sample_rate
                onsets.append(onset_time)

        return np.array(onsets)

    def _classify_genre(self, features: ContentFeatures) -> GenreClassification:
        """Classify genre based on extracted features"""
        genre_scores = {}

        for genre, rules in self.genre_rules.items():
            score = 0.0
            features_used = []

            # Apply each rule
            for rule in rules:
                feature_name = rule['feature']
                feature_value = getattr(features, feature_name)

                if 'min' in rule and feature_value >= rule['min']:
                    score += rule['weight']
                    features_used.append(feature_name)
                elif 'max' in rule and feature_value <= rule['max']:
                    score += rule['weight']
                    features_used.append(feature_name)
                elif 'range' in rule:
                    min_val, max_val = rule['range']
                    if min_val <= feature_value <= max_val:
                        score += rule['weight']
                        features_used.append(feature_name)

            genre_scores[genre] = score

        # Find best genre
        primary_genre = max(genre_scores, key=genre_scores.get)
        confidence = genre_scores[primary_genre] / max(sum(genre_scores.values()), 1.0)

        # Use default if confidence too low
        if confidence < 0.3:
            primary_genre = "pop"
            confidence = 0.5

        # Collect features used across all genres
        all_features_used = []
        for genre, rules in self.genre_rules.items():
            for rule in rules:
                all_features_used.append(rule['feature'])

        return GenreClassification(
            primary_genre=primary_genre,
            confidence=confidence,
            genre_scores=genre_scores,
            features_used=list(set(all_features_used))
        )

    def _analyze_mood(self, features: ContentFeatures, audio: np.ndarray) -> MoodAnalysis:
        """Analyze mood and energy characteristics"""

        # Energy level classification
        if features.rms_energy > 0.3:
            energy_level = "high"
        elif features.rms_energy > 0.1:
            energy_level = "medium"
        else:
            energy_level = "low"

        # Valence (happiness/sadness) - based on harmonic content and key
        valence = features.harmonic_ratio * 0.5 + (1.0 - features.inharmonicity) * 0.3
        if features.spectral_centroid > 2000:
            valence += 0.2  # Brighter sounds tend to be happier
        valence = np.clip(valence, 0.0, 1.0)

        # Arousal (energy/calmness) - based on tempo and dynamics
        arousal = min(features.tempo_estimate / 180.0, 1.0) * 0.4
        arousal += min(features.dynamic_range_db / 30.0, 1.0) * 0.3
        arousal += min(features.spectral_flux / 100.0, 1.0) * 0.3
        arousal = np.clip(arousal, 0.0, 1.0)

        # Danceability - based on rhythm and tempo
        danceability = features.rhythm_strength * 0.4
        danceability += features.beat_consistency * 0.3
        if 90 <= features.tempo_estimate <= 140:  # Optimal dance tempo
            danceability += 0.3
        danceability = np.clip(danceability, 0.0, 1.0)

        # Acousticness - based on harmonic content and attack times
        acousticness = features.harmonic_ratio * 0.4
        if features.attack_time_ms > 20:  # Slower attacks suggest acoustic instruments
            acousticness += 0.3
        if features.inharmonicity < 0.1:  # Low inharmonicity suggests acoustic
            acousticness += 0.3
        acousticness = np.clip(acousticness, 0.0, 1.0)

        return MoodAnalysis(
            energy_level=energy_level,
            valence=valence,
            arousal=arousal,
            danceability=danceability,
            acousticness=acousticness
        )

    def _analyze_stereo_characteristics(self, stereo_audio: np.ndarray) -> Dict[str, Any]:
        """Analyze stereo characteristics"""
        if stereo_audio.ndim != 2 or stereo_audio.shape[1] != 2:
            return {"is_stereo": False}

        left = stereo_audio[:, 0]
        right = stereo_audio[:, 1]

        # Correlation
        correlation = np.corrcoef(left, right)[0, 1]

        # Phase analysis
        phase_result = self.phase_analyzer.analyze_correlation(stereo_audio)

        # Width analysis
        from ..dsp.unified import stereo_width_analysis
        width = stereo_width_analysis(stereo_audio)

        return {
            "is_stereo": True,
            "correlation": float(correlation),
            "width": float(width),
            "phase_analysis": phase_result,
            "balance": float(np.mean(np.abs(left)) / (np.mean(np.abs(right)) + 1e-6))
        }

    def _generate_processing_recommendations(self, features: ContentFeatures,
                                           genre: GenreClassification,
                                           mood: MoodAnalysis,
                                           quality: Any) -> Dict[str, Any]:
        """Generate processing recommendations based on analysis"""

        recommendations = {
            "suggested_genre_profile": genre.primary_genre,
            "confidence": genre.confidence,
            "processing_intensity": 0.5,  # Default
            "eq_suggestions": {},
            "dynamics_suggestions": {},
            "stereo_suggestions": {}
        }

        # Adjust processing intensity based on genre and mood
        if genre.primary_genre in ["classical", "jazz"]:
            recommendations["processing_intensity"] = 0.3  # Conservative
        elif genre.primary_genre in ["electronic", "rock"]:
            recommendations["processing_intensity"] = 0.8  # Aggressive

        # EQ suggestions based on spectral characteristics
        if features.spectral_centroid < 1500:
            recommendations["eq_suggestions"]["treble"] = "boost +2dB"
        elif features.spectral_centroid > 3500:
            recommendations["eq_suggestions"]["treble"] = "cut -1dB"

        # Dynamics suggestions based on dynamic range
        if features.dynamic_range_db > 25:
            recommendations["dynamics_suggestions"]["compression"] = "light (2:1)"
        elif features.dynamic_range_db < 10:
            recommendations["dynamics_suggestions"]["compression"] = "minimal (1.2:1)"
        else:
            recommendations["dynamics_suggestions"]["compression"] = "moderate (3:1)"

        # Stereo suggestions based on genre
        if genre.primary_genre == "classical":
            recommendations["stereo_suggestions"]["width"] = "natural (0.8)"
        elif genre.primary_genre == "electronic":
            recommendations["stereo_suggestions"]["width"] = "wide (1.1)"

        return recommendations

    def _create_genre_classification_rules(self) -> Dict[str, List[Dict]]:
        """Create rule-based genre classification system"""
        return {
            "classical": [
                {"feature": "tempo_estimate", "range": (60, 120), "weight": 0.3},
                {"feature": "dynamic_range_db", "min": 20, "weight": 0.4},
                {"feature": "harmonic_ratio", "min": 0.6, "weight": 0.3},
                {"feature": "attack_time_ms", "min": 30, "weight": 0.2}
            ],
            "rock": [
                {"feature": "tempo_estimate", "range": (110, 160), "weight": 0.3},
                {"feature": "rhythm_strength", "min": 0.6, "weight": 0.4},
                {"feature": "spectral_centroid", "range": (1500, 3500), "weight": 0.2},
                {"feature": "dynamic_range_db", "range": (8, 20), "weight": 0.2}
            ],
            "electronic": [
                {"feature": "tempo_estimate", "range": (120, 160), "weight": 0.3},
                {"feature": "rhythm_strength", "min": 0.7, "weight": 0.4},
                {"feature": "spectral_centroid", "min": 2000, "weight": 0.2},
                {"feature": "beat_consistency", "min": 0.7, "weight": 0.3}
            ],
            "jazz": [
                {"feature": "tempo_estimate", "range": (80, 140), "weight": 0.2},
                {"feature": "harmonic_ratio", "min": 0.5, "weight": 0.4},
                {"feature": "dynamic_range_db", "min": 15, "weight": 0.3},
                {"feature": "rhythm_strength", "range": (0.3, 0.7), "weight": 0.2}
            ],
            "pop": [
                {"feature": "tempo_estimate", "range": (100, 140), "weight": 0.3},
                {"feature": "dynamic_range_db", "range": (6, 15), "weight": 0.3},
                {"feature": "beat_consistency", "min": 0.5, "weight": 0.3}
            ],
            "ambient": [
                {"feature": "tempo_estimate", "max": 100, "weight": 0.3},
                {"feature": "dynamic_range_db", "min": 25, "weight": 0.4},
                {"feature": "rhythm_strength", "max": 0.3, "weight": 0.4},
                {"feature": "attack_time_ms", "min": 50, "weight": 0.2}
            ]
        }

    def _create_mood_parameters(self) -> Dict[str, Any]:
        """Create mood analysis parameters"""
        return {
            "valence_weights": {
                "harmonic_ratio": 0.4,
                "spectral_brightness": 0.3,
                "inharmonicity": -0.3
            },
            "arousal_weights": {
                "tempo": 0.4,
                "dynamic_range": 0.3,
                "spectral_flux": 0.3
            }
        }


# Convenience function for quick content analysis
def analyze_audio_content(audio_data: np.ndarray, sample_rate: int = 44100) -> ContentProfile:
    """Quick content analysis function"""
    analyzer = AdvancedContentAnalyzer(sample_rate)
    return analyzer.analyze_content(audio_data)