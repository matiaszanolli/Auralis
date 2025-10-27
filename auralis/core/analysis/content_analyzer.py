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
from ...analysis.fingerprint import AudioFingerprintAnalyzer
from ...utils.logging import debug


class ContentAnalyzer:
    """Enhanced content analysis for adaptive processing with ML genre classification"""

    def __init__(self, sample_rate: int = 44100, use_ml_classification: bool = True,
                 use_fingerprint_analysis: bool = True):
        """
        Initialize content analyzer

        Args:
            sample_rate: Audio sample rate
            use_ml_classification: Whether to use ML-based genre classification
            use_fingerprint_analysis: Whether to extract 25D audio fingerprints
        """
        self.sample_rate = sample_rate
        self.genre_confidence_threshold = 0.6
        self.use_ml_classification = use_ml_classification
        self.use_fingerprint_analysis = use_fingerprint_analysis

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

        # Initialize 25D audio fingerprint analyzer
        if use_fingerprint_analysis:
            try:
                self.fingerprint_analyzer = AudioFingerprintAnalyzer()
                debug("Audio fingerprint analyzer (25D) initialized successfully")
            except Exception as e:
                debug(f"Failed to initialize fingerprint analyzer: {e}")
                self.fingerprint_analyzer = None
                self.use_fingerprint_analysis = False
        else:
            self.fingerprint_analyzer = None

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

        # Extract 25D audio fingerprint if enabled
        if self.use_fingerprint_analysis and self.fingerprint_analyzer is not None:
            try:
                fingerprint = self.fingerprint_analyzer.analyze(audio, self.sample_rate)
                content_profile["fingerprint"] = fingerprint

                # Promote key fingerprint features to top level for backward compatibility
                # This allows existing code to work while new code can use full fingerprint
                content_profile["spectral_centroid_normalized"] = fingerprint.get("spectral_centroid", 0.5)
                content_profile["crest_factor_db"] = fingerprint.get("crest_db", crest_factor_db)
                content_profile["lufs_fingerprint"] = fingerprint.get("lufs", content_profile["estimated_lufs"])

                debug(f"25D fingerprint extracted: LUFS={fingerprint.get('lufs', 0):.1f}, "
                      f"Crest={fingerprint.get('crest_db', 0):.1f}dB, "
                      f"Tempo={fingerprint.get('tempo_bpm', 0):.0f}BPM")
            except Exception as e:
                debug(f"Fingerprint extraction failed (non-critical): {e}")
                content_profile["fingerprint"] = None

        debug(f"Content analysis complete: genre={genre_info['primary']}, "
              f"energy={content_profile['energy_level']}, "
              f"tempo={estimated_tempo:.1f} BPM")

        return content_profile

    def analyze_input_level(self, audio: np.ndarray) -> Dict[str, Any]:
        """
        Analyze input level characteristics to determine processing strategy.
        Based on Matchering analysis showing adaptive behavior:
        - Under-leveled (quiet) material: Apply significant gain (+3 to +7 dB)
        - Well-leveled material: Conservative enhancement
        - Over-leveled (hot) material: Apply control/limiting

        Args:
            audio: Audio signal to analyze

        Returns:
            Dictionary with level category and processing recommendations
        """
        # Calculate basic level metrics
        peak = np.max(np.abs(audio))
        peak_db = 20 * np.log10(peak) if peak > 0 else -np.inf

        rms_value = rms(audio)
        rms_db = 20 * np.log10(rms_value) if rms_value > 0 else -np.inf

        crest_db = peak_db - rms_db

        # Determine level category based on Matchering analysis
        # KEY INSIGHT: Crest factor is crucial - high crest indicates dynamic material needing compression
        level_category = "well_leveled"  # Default
        processing_strategy = "conservative"
        target_gain_db = 0.0

        # Under-leveled: RMS < -18 dB or Peak < -3 dB
        # Example: Static-X Wisconsin Death Trip (RMS -21.92 dB, Peak -8.65 dB)
        if rms_db < -18.0 or peak_db < -3.0:
            level_category = "under_leveled"
            processing_strategy = "loudness_boost"

            # Calculate gain needed to bring to target range
            target_rms = -15.0  # Target RMS for under-leveled material
            target_gain_db = target_rms - rms_db
            # Cap gain at reasonable maximum
            target_gain_db = min(target_gain_db, 12.0)

            debug(f"[Input Level] Under-leveled: RMS {rms_db:.1f} dB, Peak {peak_db:.1f} dB, "
                  f"Suggested gain: +{target_gain_db:.1f} dB")

        # Live/Dynamic material: High crest factor (>12 dB) with moderate RMS indicates dynamic range
        # Example: Testament Live (Peak 0.0 dB, RMS -12.7 dB, Crest 12.7 dB)
        # Matchering applies +2 to +4 dB RMS increase despite hot peaks
        elif crest_db > 12.0 and rms_db < -12.0:
            level_category = "live_dynamic"
            processing_strategy = "dynamic_control"
            target_gain_db = 0.0  # No pregain - let dynamics processor increase loudness

            debug(f"[Input Level] Live/Dynamic: RMS {rms_db:.1f} dB, Peak {peak_db:.1f} dB, Crest {crest_db:.1f} dB")

        # Over-leveled with low crest: Peak > -0.3 dB AND Crest < 12 dB (compressed mix with clipping risk)
        # Example: Over-compressed modern mixes
        elif peak_db > -0.3 and crest_db < 12.0:
            level_category = "over_leveled"
            processing_strategy = "peak_control"
            target_gain_db = -0.5 - peak_db  # Reduce to -0.5 dB

            debug(f"[Input Level] Over-leveled: Peak {peak_db:.1f} dB, Crest {crest_db:.1f} dB, "
                  f"Suggested reduction: {target_gain_db:.1f} dB")

        # Hot RMS but acceptable peak: RMS > -12 dB, Peak < -0.5 dB
        # Example: Loud modern mixes
        elif rms_db > -12.0 and peak_db < -0.5:
            level_category = "hot_mix"
            processing_strategy = "gentle_control"
            target_gain_db = 0.0  # No pregain needed

            debug(f"[Input Level] Hot mix: RMS {rms_db:.1f} dB, Peak {peak_db:.1f} dB")

        # Well-leveled: -18 dB < RMS < -12 dB, Peak reasonable
        # Example: Iron Maiden Powerslave, Soda Stereo
        else:
            level_category = "well_leveled"
            processing_strategy = "conservative"
            target_gain_db = 0.0

            debug(f"[Input Level] Well-leveled: RMS {rms_db:.1f} dB, Peak {peak_db:.1f} dB")

        return {
            'category': level_category,
            'strategy': processing_strategy,
            'peak_db': peak_db,
            'rms_db': rms_db,
            'crest_db': crest_db,
            'suggested_pregain_db': target_gain_db,
            'metrics': {
                'peak': float(peak),
                'rms': float(rms_value),
            }
        }

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
