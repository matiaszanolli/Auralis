"""
Content Analyzer
~~~~~~~~~~~~~~~~

Enhanced content analysis for adaptive audio processing

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

import numpy as np

from ...analysis.fingerprint import AudioFingerprintAnalyzer
from ...analysis.ml import create_ml_genre_classifier
from ...dsp.basic import rms
from ...dsp.utils.adaptive import calculate_loudness_units
from ...dsp.utils.spectral import crest_factor, spectral_centroid, spectral_rolloff, tempo_estimate, zero_crossing_rate
from ...dsp.utils.stereo import stereo_width_analysis
from ...utils.logging import debug
from .genre_classification import GenreClassificationMixin
from ...dsp.utils.audio_info import to_mono
from ...dsp.utils.conversion import amplitude_to_db


class ContentAnalyzer(GenreClassificationMixin):
    """Enhanced content analysis for adaptive processing with ML genre classification"""

    def __init__(self, sample_rate: int = 44100, use_ml_classification: bool = True,
                 use_fingerprint_analysis: bool = True, use_tempo_detection: bool = True):
        """
        Initialize content analyzer

        Args:
            sample_rate: Audio sample rate
            use_ml_classification: Whether to use ML-based genre classification
            use_fingerprint_analysis: Whether to extract 25D audio fingerprints
            use_tempo_detection: Whether to perform tempo detection (can be disabled for speed)
        """
        self.sample_rate = sample_rate
        self.genre_confidence_threshold = 0.6
        self.use_ml_classification = use_ml_classification
        self.use_fingerprint_analysis = use_fingerprint_analysis
        self.use_tempo_detection = use_tempo_detection

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
                self.fingerprint_analyzer = None  # type: ignore[assignment]
                self.use_fingerprint_analysis = False
        else:
            self.fingerprint_analyzer = None  # type: ignore[assignment]

    def analyze_content(self, audio: np.ndarray) -> dict[str, Any]:
        """
        Analyze audio content for adaptive processing

        Args:
            audio: Audio signal to analyze

        Returns:
            Dictionary containing content analysis results
        """
        debug("Analyzing audio content for adaptive processing")

        mono_audio = to_mono(audio)

        # Basic audio features
        rms_value = rms(audio)
        peak_value = np.max(np.abs(audio))
        crest_factor_db = crest_factor(audio)

        # Spectral features
        centroid = spectral_centroid(mono_audio, self.sample_rate)
        rolloff = spectral_rolloff(mono_audio, self.sample_rate)
        zcr = zero_crossing_rate(mono_audio)

        # Temporal features (tempo detection can be disabled for speed)
        if self.use_tempo_detection:
            estimated_tempo = tempo_estimate(mono_audio, self.sample_rate)
        else:
            estimated_tempo = 120.0  # Default tempo when detection disabled
            debug("Tempo detection disabled, using default 120 BPM")

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

    def analyze_input_level(self, audio: np.ndarray) -> dict[str, Any]:
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
        peak_db = amplitude_to_db(peak)

        rms_value = rms(audio)
        rms_db = amplitude_to_db(rms_value)

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

    def _estimate_dynamic_range(self, audio: np.ndarray) -> float:
        """Estimate dynamic range in dB"""
        if len(audio) == 0:
            return 0.0

        # Calculate RMS in 1-second windows
        # 1-second window at the actual sample rate (#4029) — hardcoding 44100
        # gave a 0.92s window at 48 kHz / 0.46s at 96 kHz, biasing the estimate.
        window_size = int(self.sample_rate)
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

        rms_values_array = np.array(rms_values)
        rms_values_array = rms_values_array[rms_values_array > 1e-6]  # Remove silence

        if len(rms_values_array) == 0:
            return 20.0

        # Calculate dynamic range as difference between 95th and 10th percentile
        loud_level = np.percentile(rms_values_array, 95)
        quiet_level = np.percentile(rms_values_array, 10)

        if quiet_level > 0:
            dynamic_range = 20 * np.log10(loud_level / quiet_level)
            return float(np.clip(dynamic_range, 0, 60))
        else:
            return 20.0
