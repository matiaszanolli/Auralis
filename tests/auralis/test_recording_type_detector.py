# -*- coding: utf-8 -*-

"""
Tests for RecordingTypeDetector

Tests the 25D-guided recording type detection system and adaptive parameter generation.
Based on reference material analysis:
  - Deep Purple (Steven Wilson) - Studio approach
  - Porcupine Tree (Matchering) - Bootleg approach
  - Iron Maiden (Matchering) - Metal approach
"""

import numpy as np
import pytest

from auralis.core.recording_type_detector import (
    AdaptiveParameters,
    RecordingType,
    RecordingTypeDetector,
)


class TestRecordingTypeDetector:
    """Test suite for recording type detection."""

    @pytest.fixture
    def detector(self):
        """Initialize detector for each test."""
        return RecordingTypeDetector()

    # ========== Classification Tests ==========

    def test_detector_initialization(self, detector):
        """Detector should initialize without errors."""
        assert detector is not None
        assert detector.confidence_threshold == 0.65

    def test_returns_tuple_with_type_and_params(self, detector):
        """Detector should return (RecordingType, AdaptiveParameters) tuple."""
        # Create simple audio
        audio = np.random.randn(44100)
        sr = 44100

        recording_type, params = detector.detect(audio, sr)

        assert isinstance(recording_type, RecordingType)
        assert isinstance(params, AdaptiveParameters)

    def test_studio_detection_scores(self, detector):
        """Studio detection should score based on characteristic metrics."""
        # Studio characteristics: spectral ~664 Hz, bass-to-mid ~1.15 dB, stereo ~0.39
        studio_score = detector._score_studio(
            spectral_hz=664,
            bass_to_mid=1.15,
            stereo_width=0.39
        )
        # Should be moderately high
        assert 0.4 < studio_score <= 1.0

    def test_bootleg_detection_scores(self, detector):
        """Bootleg detection should score based on dark, bass-heavy characteristics."""
        # Bootleg characteristics: spectral <500 Hz, bass-to-mid >12 dB, stereo <0.3
        bootleg_score = detector._score_bootleg(
            spectral_hz=450,
            bass_to_mid=14.0,
            stereo_width=0.20
        )
        # Should be high for clear bootleg
        assert bootleg_score > 0.6

    def test_metal_detection_scores(self, detector):
        """Metal detection should score based on bright, compressed characteristics."""
        # Metal characteristics: spectral >1000 Hz, bass-to-mid ~9.58 dB, crest <4.5, stereo >0.35
        metal_score = detector._score_metal(
            spectral_hz=1344,
            bass_to_mid=9.58,
            stereo_width=0.418,
            crest_db=3.54
        )
        # Should be high for clear metal
        assert metal_score > 0.6

    def test_classification_confidence(self, detector):
        """Classification should include confidence metric."""
        recording_type, confidence = detector._classify({
            'spectral_centroid': 0.033,  # ~664 Hz (0.033 * 20000)
            'bass_mid_ratio': 1.15,
            'stereo_width': 0.39,
            'crest_db': 6.53,
        })

        assert 0 <= confidence <= 1

    def test_low_confidence_returns_unknown(self, detector):
        """If confidence below threshold, should return UNKNOWN."""
        # Mixed characteristics that don't match any clearly
        recording_type, confidence = detector._classify({
            'spectral_centroid': 0.05,   # ~1000 Hz (unclear)
            'bass_mid_ratio': 5.0,        # (unclear)
            'stereo_width': 0.32,         # (unclear)
            'crest_db': 5.0,
        })

        if confidence < detector.confidence_threshold:
            assert recording_type == RecordingType.UNKNOWN

    # ========== Parameter Generation Tests ==========

    def test_studio_parameters_generation(self, detector):
        """Studio recording should generate appropriate parameters."""
        params = detector._parameters_studio({}, confidence=0.85)

        assert params.mastering_philosophy == "enhance"
        assert params.bass_adjustment_db == pytest.approx(1.5, abs=0.1)
        assert params.mid_adjustment_db == pytest.approx(-1.0, abs=0.1)
        assert params.treble_adjustment_db == pytest.approx(2.0, abs=0.1)
        assert params.stereo_strategy == "maintain"
        assert params.confidence == 0.85

    def test_bootleg_parameters_generation(self, detector):
        """Bootleg recording should generate correction parameters."""
        params = detector._parameters_bootleg({}, confidence=0.85)

        assert params.mastering_philosophy == "correct"
        assert params.bass_adjustment_db == pytest.approx(-4.0, abs=0.1)
        assert params.treble_adjustment_db == pytest.approx(4.0, abs=0.1)
        assert params.stereo_strategy == "expand"
        assert params.stereo_width_target == pytest.approx(0.40, abs=0.05)
        assert params.dr_expansion_db == pytest.approx(23.5, abs=1.0)
        assert params.confidence == 0.85

    def test_metal_parameters_generation(self, detector):
        """Metal recording should generate punch parameters."""
        params = detector._parameters_metal({}, confidence=0.85)

        assert params.mastering_philosophy == "punch"
        assert params.bass_adjustment_db == pytest.approx(3.85, abs=0.1)
        assert params.mid_adjustment_db == pytest.approx(-5.70, abs=0.1)
        # UNIQUE: Treble reduction, not boost
        assert params.treble_adjustment_db == pytest.approx(-1.22, abs=0.1)
        assert params.treble_adjustment_db < 0  # Reduction
        assert params.stereo_strategy == "narrow"
        assert params.stereo_width_target < 0.35
        assert params.rms_adjustment_db < 0  # Reduction
        assert params.confidence == 0.85

    def test_default_parameters_fallback(self, detector):
        """Unknown type should generate conservative default parameters."""
        params = detector._parameters_default(confidence=0.40)

        assert params.mastering_philosophy == "enhance"
        assert params.confidence == 0.40
        # Should be conservative (moderate adjustments)
        assert abs(params.bass_adjustment_db) < 2.0
        assert abs(params.treble_adjustment_db) < 2.0

    # ========== Fine-tuning Tests ==========

    def test_studio_fine_tuning_darker_input(self, detector):
        """Studio fine-tuning should reduce bass boost for darker input."""
        # Input darker than studio reference (664 Hz)
        dark_fingerprint = {'spectral_centroid': 0.025}  # ~500 Hz
        params_dark = detector._parameters_studio(dark_fingerprint, confidence=0.85)

        # Should have reduced bass boost
        assert params_dark.bass_adjustment_db < 1.5

    def test_studio_fine_tuning_brighter_input(self, detector):
        """Studio fine-tuning should reduce treble boost for brighter input."""
        # Input brighter than studio reference (664 Hz)
        bright_fingerprint = {'spectral_centroid': 0.055}  # ~1100 Hz
        params_bright = detector._parameters_studio(bright_fingerprint, confidence=0.85)

        # Should have reduced treble boost
        assert params_bright.treble_adjustment_db < 2.0

    def test_bootleg_fine_tuning_darker_input(self, detector):
        """Bootleg fine-tuning should increase treble for darker bootleg."""
        # Input darker than bootleg reference
        very_dark_fingerprint = {
            'spectral_centroid': 0.015,  # ~300 Hz (very dark)
            'bass_mid_ratio': 16.0,      # Higher than reference
            'stereo_width': 0.18
        }
        params_dark = detector._parameters_bootleg(very_dark_fingerprint, confidence=0.85)

        # Should have more aggressive treble boost
        assert params_dark.treble_adjustment_db > 4.0

    def test_bootleg_fine_tuning_heavier_bass(self, detector):
        """Bootleg fine-tuning should increase bass reduction for heavier bass."""
        # Input with heavier bass than reference
        heavy_bass_fingerprint = {
            'spectral_centroid': 0.035,
            'bass_mid_ratio': 16.5,  # > reference 13.6-16.8
            'stereo_width': 0.20
        }
        params_heavy = detector._parameters_bootleg(heavy_bass_fingerprint, confidence=0.85)

        # Should have more aggressive bass reduction
        assert params_heavy.bass_adjustment_db < -4.0

    def test_metal_fine_tuning_brightness_variation(self, detector):
        """Metal fine-tuning should adjust treble reduction based on brightness."""
        # Very bright metal (brighter than reference 1340 Hz)
        very_bright_fingerprint = {'spectral_centroid': 0.0685}  # ~1370 Hz (> 1340)
        params_bright = detector._parameters_metal(very_bright_fingerprint, confidence=0.85)

        # Should have more treble reduction
        assert params_bright.treble_adjustment_db < -1.22
        assert params_bright.treble_adjustment_db == pytest.approx(-1.5, abs=0.01)

        # Less bright metal
        less_bright_fingerprint = {'spectral_centroid': 0.059}  # ~1180 Hz (< 1200)
        params_less = detector._parameters_metal(less_bright_fingerprint, confidence=0.85)

        # Should have less treble reduction (closer to 0)
        assert params_less.treble_adjustment_db > -1.22
        assert params_less.treble_adjustment_db == pytest.approx(-0.95, abs=0.01)

    def test_metal_fine_tuning_compression(self, detector):
        """Metal fine-tuning should adjust mid reduction based on compression."""
        # Very compressed metal
        compressed_fingerprint = {'crest_db': 3.4}  # < 3.5
        params_compressed = detector._parameters_metal(compressed_fingerprint, confidence=0.85)

        # Should have less aggressive mid reduction
        assert params_compressed.mid_adjustment_db > -5.70

    # ========== Reference Matching Tests ==========

    def test_deep_purple_studio_reference_match(self, detector):
        """Studio parameters should match Deep Purple reference."""
        # Deep Purple characteristics (normalized to 0-1 range where applicable)
        params = detector._parameters_studio({
            'spectral_centroid': 0.0332,  # 664 Hz
        }, confidence=0.85)

        # Should closely match Steven Wilson reference
        assert params.bass_adjustment_db == pytest.approx(1.5, abs=0.2)
        assert params.treble_adjustment_db == pytest.approx(2.0, abs=0.2)
        assert params.target_spectral_centroid_hz == pytest.approx(675, abs=20)

    def test_porcupine_tree_bootleg_reference_match(self, detector):
        """Bootleg parameters should match Porcupine Tree reference."""
        # Porcupine Tree characteristics
        params = detector._parameters_bootleg({
            'spectral_centroid': 0.0225,  # ~450 Hz (middle of bootleg range)
        }, confidence=0.85)

        # Should closely match Matchering remaster
        assert params.bass_adjustment_db == pytest.approx(-4.0, abs=0.2)
        assert params.treble_adjustment_db == pytest.approx(4.0, abs=0.3)
        assert params.dr_expansion_db == pytest.approx(23.5, abs=1.0)

    def test_iron_maiden_metal_reference_match(self, detector):
        """Metal parameters should match Iron Maiden reference."""
        # Iron Maiden characteristics
        params = detector._parameters_metal({
            'spectral_centroid': 0.067,  # ~1344 Hz
        }, confidence=0.85)

        # Should closely match Matchering remaster
        assert params.bass_adjustment_db == pytest.approx(3.85, abs=0.2)
        assert params.treble_adjustment_db == pytest.approx(-1.22, abs=0.1)
        assert params.mid_adjustment_db == pytest.approx(-5.70, abs=0.2)

    # ========== Edge Cases ==========

    def test_mono_audio_detection(self, detector):
        """Detector should handle mono audio."""
        audio_mono = np.random.randn(44100)  # Mono
        sr = 44100

        recording_type, params = detector.detect(audio_mono, sr)

        assert recording_type in [RecordingType.STUDIO, RecordingType.BOOTLEG, RecordingType.METAL, RecordingType.UNKNOWN]
        assert params is not None

    def test_stereo_audio_detection(self, detector):
        """Detector should handle stereo audio."""
        audio_stereo = np.random.randn(2, 44100)  # Stereo
        sr = 44100

        recording_type, params = detector.detect(audio_stereo, sr)

        assert recording_type in [RecordingType.STUDIO, RecordingType.BOOTLEG, RecordingType.METAL, RecordingType.UNKNOWN]
        assert params is not None

    def test_short_audio_detection(self, detector):
        """Detector should handle short audio clips."""
        audio_short = np.random.randn(4410)  # ~0.1 seconds at 44.1kHz
        sr = 44100

        # Should not crash
        recording_type, params = detector.detect(audio_short, sr)

        assert isinstance(recording_type, RecordingType)
        assert isinstance(params, AdaptiveParameters)

    def test_long_audio_detection(self, detector):
        """Detector should handle long audio files."""
        audio_long = np.random.randn(44100 * 60)  # 60 seconds
        sr = 44100

        # Should not crash
        recording_type, params = detector.detect(audio_long, sr)

        assert isinstance(recording_type, RecordingType)
        assert isinstance(params, AdaptiveParameters)

    # ========== AdaptiveParameters Tests ==========

    def test_adaptive_parameters_dataclass(self):
        """AdaptiveParameters should be a valid dataclass."""
        params = AdaptiveParameters(
            bass_adjustment_db=1.5,
            mid_adjustment_db=-1.0,
            treble_adjustment_db=2.0,
            target_spectral_centroid_hz=675,
            spectral_adjustment_guidance="maintain",
            stereo_width_target=0.39,
            stereo_strategy="maintain",
            crest_factor_target_min=6.0,
            crest_factor_target_max=6.5,
            dr_expansion_db=0,
            rms_adjustment_db=-0.51,
            peak_headroom_db=-0.24,
            mastering_philosophy="enhance",
            confidence=0.85
        )

        assert params.bass_adjustment_db == 1.5
        assert params.confidence == 0.85
        assert params.mastering_philosophy == "enhance"

    def test_adaptive_parameters_repr(self):
        """AdaptiveParameters should have readable repr."""
        params = AdaptiveParameters(
            bass_adjustment_db=1.5,
            mid_adjustment_db=-1.0,
            treble_adjustment_db=2.0,
            target_spectral_centroid_hz=675,
            spectral_adjustment_guidance="maintain",
            stereo_width_target=0.39,
            stereo_strategy="maintain",
            crest_factor_target_min=6.0,
            crest_factor_target_max=6.5,
            dr_expansion_db=0,
            rms_adjustment_db=-0.51,
            peak_headroom_db=-0.24,
            mastering_philosophy="enhance",
            confidence=0.85
        )

        repr_str = repr(params)
        assert "enhance" in repr_str
        assert "+1.50dB" in repr_str or "1.50dB" in repr_str

    # ========== Philosophy Consistency Tests ==========

    def test_studio_philosophy_consistency(self, detector):
        """Studio philosophy should be consistent with parameters."""
        params = detector._parameters_studio({}, confidence=0.85)

        # Enhance philosophy means modest adjustments
        assert params.mastering_philosophy == "enhance"
        assert -2 < params.bass_adjustment_db < 2
        assert -2 < params.treble_adjustment_db < 3
        assert params.dr_expansion_db == 0  # Already mastered

    def test_bootleg_philosophy_consistency(self, detector):
        """Bootleg philosophy should be consistent with parameters."""
        params = detector._parameters_bootleg({}, confidence=0.85)

        # Correct philosophy means aggressive adjustments
        assert params.mastering_philosophy == "correct"
        assert params.bass_adjustment_db < -3  # Aggressive reduction
        assert params.treble_adjustment_db > 3  # Aggressive boost
        assert params.dr_expansion_db > 20  # Significant expansion

    def test_metal_philosophy_consistency(self, detector):
        """Metal philosophy should be consistent with parameters."""
        params = detector._parameters_metal({}, confidence=0.85)

        # Punch philosophy means bass boost + treble reduction
        assert params.mastering_philosophy == "punch"
        assert params.bass_adjustment_db > 3  # Bass boost for punch
        assert params.treble_adjustment_db < 0  # Reduction for warmth
        assert params.rms_adjustment_db < -3  # Aggressive headroom creation

    # ========== Scoring Algorithm Tests ==========

    def test_bootleg_scores_dark_dark_dark(self, detector):
        """Very dark bootleg should score highest for bootleg."""
        # All three bootleg indicators present
        scores = {
            'bootleg': detector._score_bootleg(400, 15.0, 0.20),
            'studio': detector._score_studio(400, 15.0, 0.20),
            'metal': detector._score_metal(400, 15.0, 0.20, 6.0),
        }

        # Bootleg should be clearly highest
        assert scores['bootleg'] > scores['studio']
        assert scores['bootleg'] > scores['metal']

    def test_metal_scores_bright_bright_bright(self, detector):
        """Very bright metal should score highest for metal."""
        # All three metal indicators present
        scores = {
            'bootleg': detector._score_bootleg(1400, 9.5, 0.40),
            'studio': detector._score_studio(1400, 9.5, 0.40),
            'metal': detector._score_metal(1400, 9.5, 0.40, 3.5),
        }

        # Metal should be clearly highest
        assert scores['metal'] > scores['bootleg']
        assert scores['metal'] > scores['studio']

    def test_studio_scores_normal_normal_normal(self, detector):
        """Normal balanced recording should score highest for studio."""
        # All three studio indicators present
        scores = {
            'bootleg': detector._score_bootleg(700, 1.5, 0.40),
            'studio': detector._score_studio(700, 1.5, 0.40),
            'metal': detector._score_metal(700, 1.5, 0.40, 6.5),
        }

        # Studio should be clearly highest
        assert scores['studio'] > scores['bootleg']
        assert scores['studio'] > scores['metal']


class TestAdaptiveParametersIntegration:
    """Integration tests for adaptive parameters in processing context."""

    @pytest.fixture
    def detector(self):
        """Initialize detector."""
        return RecordingTypeDetector()

    def test_parameters_guide_not_command(self, detector):
        """Parameters should be guidance, adjustable by fingerprint."""
        params = detector._parameters_studio({}, confidence=0.85)

        # Parameters are guidance, not absolute commands
        # They can be adjusted further based on 25D fingerprint
        assert params.bass_adjustment_db is not None  # Guidance provided
        assert isinstance(params.bass_adjustment_db, (int, float))  # Numerical guidance

    def test_confidence_affects_parameter_selection(self, detector):
        """Higher confidence should justify more aggressive parameters."""
        # Same type, different confidences
        params_high = detector._parameters_bootleg({}, confidence=0.95)
        params_low = detector._parameters_bootleg({}, confidence=0.55)

        # Confidence is stored (could be used for weighting later)
        assert params_high.confidence == 0.95
        assert params_low.confidence == 0.55
        # But base parameters same (confidence doesn't change base)
        assert params_high.bass_adjustment_db == params_low.bass_adjustment_db

    def test_philosophy_field_enables_strategy_selection(self, detector):
        """Philosophy field should enable strategic decision-making."""
        studio_params = detector._parameters_studio({}, confidence=0.85)
        bootleg_params = detector._parameters_bootleg({}, confidence=0.85)
        metal_params = detector._parameters_metal({}, confidence=0.85)

        # Different philosophies should enable different processing strategies
        philosophies = {studio_params.mastering_philosophy, bootleg_params.mastering_philosophy, metal_params.mastering_philosophy}
        assert len(philosophies) == 3  # All different
        assert "enhance" in philosophies
        assert "correct" in philosophies
        assert "punch" in philosophies
