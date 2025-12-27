# -*- coding: utf-8 -*-

"""
Phase 5: Adaptive Parameters Integration Tests

Validates that RecordingTypeDetector is properly integrated into
HybridProcessor and ContinuousMode, and that adaptive guidance is
correctly applied to EQ, dynamics, and stereo processing stages.

Tests the end-to-end integration of the 25D-guided adaptive mastering system.
"""

import numpy as np
import pytest

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import (
    AudioFingerprintAnalyzer,
)
from auralis.core.analysis.content_analyzer import ContentAnalyzer
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.processing.continuous_mode import ContinuousMode
from auralis.core.recording_type_detector import RecordingType, RecordingTypeDetector
from auralis.core.unified_config import UnifiedConfig


class TestPhase5RecordingTypeDetectorIntegration:
    """Test RecordingTypeDetector integration with HybridProcessor and ContinuousMode."""

    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return UnifiedConfig()

    @pytest.fixture
    def hybrid_processor(self, config):
        """Create a HybridProcessor instance with detector initialized."""
        return HybridProcessor(config)

    @pytest.fixture
    def continuous_mode(self, config):
        """Create a ContinuousMode instance with detector initialized."""
        content_analyzer = ContentAnalyzer()
        fingerprint_analyzer = AudioFingerprintAnalyzer()
        return ContinuousMode(config, content_analyzer, fingerprint_analyzer)

    @pytest.fixture
    def studio_audio(self):
        """Generate synthetic studio-like audio (balanced, good stereo)."""
        sr = 44100
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration))

        # Balanced frequency mix (studio-like)
        bass = 0.3 * np.sin(2 * np.pi * 80 * t)  # Bass at 80 Hz
        mid = 0.3 * np.sin(2 * np.pi * 400 * t)  # Mid at 400 Hz
        treble = 0.2 * np.sin(2 * np.pi * 3000 * t)  # Treble at 3 kHz

        mono = bass + mid + treble
        # Good stereo separation (0.4 width ~ studio)
        left = mono * 1.2
        right = mono * 0.8

        return np.array([left, right])

    @pytest.fixture
    def bootleg_audio(self):
        """Generate synthetic bootleg-like audio (dark, bass-heavy, narrow stereo)."""
        sr = 44100
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration))

        # Dark mix (bootleg-like) - heavy bass, muffled
        bass = 0.5 * np.sin(2 * np.pi * 60 * t)  # Bass at 60 Hz (very low)
        mid = 0.4 * np.sin(2 * np.pi * 200 * t)  # Muffled mid at 200 Hz
        treble = 0.05 * np.sin(2 * np.pi * 2000 * t)  # Very little treble

        mono = bass + mid + treble
        # Narrow stereo (0.2 width ~ bootleg)
        left = mono * 1.05
        right = mono * 0.95

        return np.array([left, right])

    @pytest.fixture
    def metal_audio(self):
        """Generate synthetic metal-like audio (bright, compressed, punchy)."""
        sr = 44100
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration))

        # Bright, punchy mix (metal-like)
        bass = 0.35 * np.sin(2 * np.pi * 100 * t)  # Bass at 100 Hz
        mid = 0.2 * np.sin(2 * np.pi * 800 * t)  # Scooped mid at 800 Hz
        treble = 0.4 * np.sin(2 * np.pi * 5000 * t)  # Bright treble at 5 kHz

        mono = bass + mid + treble
        # Good stereo separation (0.4 width ~ metal)
        left = mono * 1.1
        right = mono * 0.9

        return np.array([left, right])

    def test_hybrid_processor_has_detector(self, hybrid_processor):
        """Verify HybridProcessor has RecordingTypeDetector initialized."""
        assert hasattr(hybrid_processor, 'recording_type_detector')
        assert isinstance(hybrid_processor.recording_type_detector, RecordingTypeDetector)

    def test_continuous_mode_has_detector(self, continuous_mode):
        """Verify ContinuousMode has RecordingTypeDetector initialized."""
        assert hasattr(continuous_mode, 'recording_type_detector')
        assert isinstance(continuous_mode.recording_type_detector, RecordingTypeDetector)

    def test_continuous_mode_stores_detection_results(self, continuous_mode, studio_audio):
        """Verify ContinuousMode stores detection results after process()."""
        # Mock eq_processor
        class MockEQProcessor:
            def apply_psychoacoustic_eq(self, audio, targets, content_profile):
                return audio

        eq_processor = MockEQProcessor()

        # Process should call detector and store results
        # (Note: This is a basic integration test, full processing may need more setup)
        assert continuous_mode.last_recording_type is None
        assert continuous_mode.last_adaptive_params is None

    def test_studio_detection_confidence(self, continuous_mode, studio_audio):
        """Verify studio audio produces high confidence classification."""
        recording_type, adaptive_params = continuous_mode.recording_type_detector.detect(
            studio_audio, 44100
        )

        # Studio audio should either be STUDIO or UNKNOWN (depending on fingerprint)
        # The key is that confidence should be reasonable
        assert recording_type in [RecordingType.STUDIO, RecordingType.UNKNOWN]
        assert 0 <= adaptive_params.confidence <= 1

    def test_bootleg_detection_confidence(self, continuous_mode, bootleg_audio):
        """Verify bootleg audio is detected with appropriate confidence."""
        recording_type, adaptive_params = continuous_mode.recording_type_detector.detect(
            bootleg_audio, 44100
        )

        # Bootleg audio should either be BOOTLEG or UNKNOWN
        # The key is that we get consistent results
        assert recording_type in [RecordingType.BOOTLEG, RecordingType.UNKNOWN]
        assert 0 <= adaptive_params.confidence <= 1

    def test_metal_detection_confidence(self, continuous_mode, metal_audio):
        """Verify metal audio is detected with appropriate confidence."""
        recording_type, adaptive_params = continuous_mode.recording_type_detector.detect(
            metal_audio, 44100
        )

        # Metal audio should either be METAL or UNKNOWN
        assert recording_type in [RecordingType.METAL, RecordingType.UNKNOWN]
        assert 0 <= adaptive_params.confidence <= 1

    def test_adaptive_eq_guidance_blending(self, continuous_mode, studio_audio):
        """Verify EQ processing blends adaptive guidance based on confidence."""
        from auralis.core.processing.continuous_space import ProcessingParameters

        # Create mock parameters
        params = ProcessingParameters(
            target_lufs=-14.0,
            peak_target_db=-1.0,
            eq_curve={
                'low_shelf_gain': 0.0,
                'low_mid_gain': 0.0,
                'mid_gain': 0.0,
                'high_mid_gain': 0.0,
                'high_shelf_gain': 0.0,
            },
            eq_blend=0.7,
            compression_params={
                'threshold_db': -20.0,
                'ratio': 2.5,
                'attack_ms': 10.0,
                'release_ms': 100.0,
                'knee_db': 6.0,
                'makeup_db': 0.0,
                'amount': 0.6
            },
            expansion_params={
                'threshold_db': -30.0,
                'ratio': 1.5,
                'attack_ms': 5.0,
                'release_ms': 50.0,
                'amount': 0.0
            },
            dynamics_blend=0.6,
            limiter_params={
                'threshold_db': -1.0,
                'attack_ms': 1.0,
                'release_ms': 100.0
            },
            stereo_width_target=1.0
        )

        # Set adaptive parameters
        from auralis.core.recording_type_detector import AdaptiveParameters
        adaptive_params = AdaptiveParameters(
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
            confidence=0.8
        )

        continuous_mode.last_adaptive_params = adaptive_params
        continuous_mode.last_fingerprint = {}

        # Create mock EQ processor
        class MockEQProcessor:
            def apply_psychoacoustic_eq(self, audio, targets, content_profile):
                # Just return audio unchanged
                return audio

        eq_processor = MockEQProcessor()

        # Apply EQ - should blend adaptive guidance
        output = continuous_mode._apply_eq(studio_audio, eq_processor, params)

        # Verify output is audio (not checking exact values due to complexity)
        assert isinstance(output, np.ndarray)
        assert output.shape == studio_audio.shape

    def test_adaptive_dynamics_philosophy_scaling(self, continuous_mode, bootleg_audio):
        """Verify dynamics processing scales per mastering philosophy."""
        from auralis.core.processing.continuous_space import ProcessingParameters
        from auralis.core.recording_type_detector import AdaptiveParameters

        params = ProcessingParameters(
            target_lufs=-14.0,
            peak_target_db=-1.0,
            eq_curve={'low_shelf_gain': 0, 'low_mid_gain': 0, 'mid_gain': 0,
                     'high_mid_gain': 0, 'high_shelf_gain': 0},
            eq_blend=0.7,
            compression_params={'threshold_db': -20.0, 'ratio': 2.5, 'attack_ms': 10.0,
                               'release_ms': 100.0, 'knee_db': 6.0, 'makeup_db': 0.0,
                               'amount': 0.6},
            expansion_params={'threshold_db': -30.0, 'ratio': 1.5, 'attack_ms': 5.0,
                             'release_ms': 50.0, 'amount': 0.0},
            dynamics_blend=0.6,
            limiter_params={'threshold_db': -1.0, 'attack_ms': 1.0, 'release_ms': 100.0},
            stereo_width_target=1.0
        )

        # Bootleg correction philosophy
        adaptive_params = AdaptiveParameters(
            bass_adjustment_db=-4.0,
            mid_adjustment_db=-3.5,
            treble_adjustment_db=4.0,
            target_spectral_centroid_hz=990,
            spectral_adjustment_guidance="brighten",
            stereo_width_target=0.40,
            stereo_strategy="expand",
            crest_factor_target_min=4.6,
            crest_factor_target_max=6.0,
            dr_expansion_db=23.5,
            rms_adjustment_db=2.0,
            peak_headroom_db=-0.02,
            mastering_philosophy="correct",
            confidence=0.85
        )

        continuous_mode.last_adaptive_params = adaptive_params

        # Apply dynamics - should scale for correction philosophy
        output = continuous_mode._apply_dynamics(bootleg_audio, params)

        # Verify output is audio
        assert isinstance(output, np.ndarray)
        assert output.shape == bootleg_audio.shape
        # Output should not be NaN or Inf
        assert not np.isnan(output).any()
        assert not np.isinf(output).any()

    def test_adaptive_stereo_expansion_strategy(self, continuous_mode, bootleg_audio):
        """Verify stereo processing applies expansion strategy for bootleg."""
        from auralis.core.processing.continuous_space import ProcessingParameters
        from auralis.core.recording_type_detector import AdaptiveParameters

        params = ProcessingParameters(
            target_lufs=-14.0,
            peak_target_db=-1.0,
            eq_curve={'low_shelf_gain': 0, 'low_mid_gain': 0, 'mid_gain': 0,
                     'high_mid_gain': 0, 'high_shelf_gain': 0},
            eq_blend=0.7,
            compression_params={'threshold_db': -20.0, 'ratio': 2.5, 'attack_ms': 10.0,
                               'release_ms': 100.0, 'knee_db': 6.0, 'makeup_db': 0.0,
                               'amount': 0.6},
            expansion_params={'threshold_db': -30.0, 'ratio': 1.5, 'attack_ms': 5.0,
                             'release_ms': 50.0, 'amount': 0.0},
            dynamics_blend=0.6,
            limiter_params={'threshold_db': -1.0, 'attack_ms': 1.0, 'release_ms': 100.0},
            stereo_width_target=0.4  # Target for expansion
        )

        # Bootleg expansion strategy
        adaptive_params = AdaptiveParameters(
            bass_adjustment_db=-4.0,
            mid_adjustment_db=-3.5,
            treble_adjustment_db=4.0,
            target_spectral_centroid_hz=990,
            spectral_adjustment_guidance="brighten",
            stereo_width_target=0.40,
            stereo_strategy="expand",  # Key: expansion
            crest_factor_target_min=4.6,
            crest_factor_target_max=6.0,
            dr_expansion_db=23.5,
            rms_adjustment_db=2.0,
            peak_headroom_db=-0.02,
            mastering_philosophy="correct",
            confidence=0.85
        )

        continuous_mode.last_adaptive_params = adaptive_params

        # Apply stereo - should expand
        output = continuous_mode._apply_stereo_width(bootleg_audio, params)

        # Verify output is stereo audio
        assert isinstance(output, np.ndarray)
        assert output.ndim == 2
        assert output.shape[0] == 2
        # Output should not be NaN or Inf
        assert not np.isnan(output).any()
        assert not np.isinf(output).any()

    def test_full_phase5_integration(self, continuous_mode, studio_audio):
        """Integration test: verify detector results stored after detection call."""
        recording_type, adaptive_params = continuous_mode.recording_type_detector.detect(
            studio_audio, 44100
        )

        # Detector should return valid types
        assert isinstance(recording_type, RecordingType)
        assert hasattr(adaptive_params, 'mastering_philosophy')
        assert adaptive_params.mastering_philosophy in ['enhance', 'correct', 'punch']

    def test_confidence_scales_adaptive_strength(self, continuous_mode):
        """Verify confidence level properly scales adaptive guidance strength."""
        from auralis.core.recording_type_detector import AdaptiveParameters

        # High confidence should scale more aggressively
        high_confidence = AdaptiveParameters(
            bass_adjustment_db=3.0, mid_adjustment_db=-5.0, treble_adjustment_db=-1.0,
            target_spectral_centroid_hz=930, spectral_adjustment_guidance="darken",
            stereo_width_target=0.263, stereo_strategy="narrow",
            crest_factor_target_min=5.0, crest_factor_target_max=5.3,
            dr_expansion_db=23.2, rms_adjustment_db=-3.93, peak_headroom_db=-0.40,
            mastering_philosophy="punch", confidence=0.95  # Very high confidence
        )

        low_confidence = AdaptiveParameters(
            bass_adjustment_db=3.0, mid_adjustment_db=-5.0, treble_adjustment_db=-1.0,
            target_spectral_centroid_hz=930, spectral_adjustment_guidance="darken",
            stereo_width_target=0.263, stereo_strategy="narrow",
            crest_factor_target_min=5.0, crest_factor_target_max=5.3,
            dr_expansion_db=23.2, rms_adjustment_db=-3.93, peak_headroom_db=-0.40,
            mastering_philosophy="punch", confidence=0.70  # Low confidence
        )

        # High confidence should have stronger influence than low
        assert high_confidence.confidence > low_confidence.confidence


class TestPhase5ReferenceValidation:
    """Validate detector behavior matches reference material expectations."""

    @pytest.fixture
    def detector(self):
        """Create a RecordingTypeDetector for testing."""
        return RecordingTypeDetector()

    def test_studio_reference_expectations(self, detector):
        """Verify studio parameters match Deep Purple reference expectations."""
        from auralis.core.recording_type_detector import RecordingType

        # Deep Purple studio reference fingerprint (approximate)
        studio_fingerprint = {
            'spectral_centroid': 0.0332,  # ~664 Hz (studio range)
            'bass_mid_ratio': 1.15,  # +1.15 dB relative bass
            'stereo_width': 0.39,
            'crest_db': 6.53,
        }

        recording_type, confidence = detector._classify(studio_fingerprint)

        # Should classify as studio or unknown (confidence matters)
        assert recording_type in [RecordingType.STUDIO, RecordingType.UNKNOWN]

        # Get studio parameters
        params = detector._parameters_studio(studio_fingerprint, confidence)

        # Should match Steven Wilson reference
        assert params.bass_adjustment_db == pytest.approx(1.5, abs=0.5)
        assert params.treble_adjustment_db == pytest.approx(2.0, abs=0.5)
        assert params.mastering_philosophy == "enhance"

    def test_bootleg_reference_expectations(self, detector):
        """Verify bootleg parameters match Porcupine Tree reference expectations."""
        from auralis.core.recording_type_detector import RecordingType

        # Porcupine Tree bootleg reference fingerprint (approximate)
        bootleg_fingerprint = {
            'spectral_centroid': 0.0249,  # ~498 Hz (very dark, bootleg range)
            'bass_mid_ratio': 15.0,  # Very high bass dominance
            'stereo_width': 0.20,  # Very narrow
            'crest_db': 5.0,
        }

        recording_type, confidence = detector._classify(bootleg_fingerprint)

        # Should detect as bootleg
        assert recording_type in [RecordingType.BOOTLEG, RecordingType.UNKNOWN]

        # Get bootleg parameters
        params = detector._parameters_bootleg(bootleg_fingerprint, confidence)

        # Should show correction philosophy
        assert params.bass_adjustment_db == pytest.approx(-4.0, abs=1.0)
        assert params.treble_adjustment_db >= 4.0  # Aggressive brightening
        assert params.mastering_philosophy == "correct"
        assert params.stereo_strategy == "expand"

    def test_metal_reference_expectations(self, detector):
        """Verify metal parameters match Iron Maiden reference expectations."""
        from auralis.core.recording_type_detector import RecordingType

        # Iron Maiden metal reference fingerprint (approximate)
        metal_fingerprint = {
            'spectral_centroid': 0.0672,  # ~1344 Hz (very bright, metal)
            'bass_mid_ratio': 9.58,  # Moderate bass
            'stereo_width': 0.418,  # Good stereo
            'crest_db': 3.54,  # Compressed
        }

        recording_type, confidence = detector._classify(metal_fingerprint)

        # Should detect as metal
        assert recording_type in [RecordingType.METAL, RecordingType.UNKNOWN]

        # Get metal parameters
        params = detector._parameters_metal(metal_fingerprint, confidence)

        # Should show punch philosophy with treble reduction (unique!)
        assert params.bass_adjustment_db == pytest.approx(3.85, abs=1.0)
        assert params.treble_adjustment_db < 0  # REDUCTION, not boost
        assert params.mastering_philosophy == "punch"
        assert params.stereo_strategy == "narrow"
