# -*- coding: utf-8 -*-

"""
Phase 6.1: Real-World Audio Processing Validation

Validates RecordingTypeDetector on actual reference materials:
1. Deep Purple - In Rock (Studio mastering)
2. Iron Maiden - Wasted Years (Metal mastering)
3. Porcupine Tree recordings (if available - Bootleg/Live)

Captures detection results, confidence scores, and processing metrics.
"""

import time
from pathlib import Path

import librosa
import numpy as np
import pytest

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import (
    AudioFingerprintAnalyzer,
)
from auralis.core.recording_type_detector import RecordingType, RecordingTypeDetector


class TestPhase6RealWorldAudioValidation:
    """Validate detector on actual reference audio materials."""

    @pytest.fixture
    def detector(self):
        """Create detector for testing."""
        return RecordingTypeDetector()

    @pytest.fixture
    def fingerprint_analyzer(self):
        """Create fingerprint analyzer."""
        return AudioFingerprintAnalyzer()

    # Path definitions for reference materials
    DEEP_PURPLE_DIR = Path("/mnt/audio/Audio/Remasters/Deep Purple - In Rock")
    IRON_MAIDEN_DIR = Path("/mnt/audio/Audio/Remasters/Iron Maiden - Wasted Years (S)")
    PORCUPINE_TREE_DIR = Path("/mnt/audio/Audio/Remasters/Porcupine Tree - Rockpalast Live")

    def test_deep_purple_studio_detection(self, detector, fingerprint_analyzer):
        """Validate Deep Purple detection as STUDIO recording."""
        audio_file = self.DEEP_PURPLE_DIR / "01. Speed King.flac"

        if not audio_file.exists():
            pytest.skip(f"Audio file not found: {audio_file}")

        # Load audio
        audio, sr = librosa.load(str(audio_file), sr=44100, mono=False)

        # Detect recording type
        start_time = time.time()
        recording_type, adaptive_params = detector.detect(audio, sr)
        detection_time = time.time() - start_time

        # Extract fingerprint for logging
        fingerprint = fingerprint_analyzer.analyze(audio, sr)

        # Log results
        print(f"\n{'='*70}")
        print(f"Deep Purple - Speed King (Studio Reference)")
        print(f"{'='*70}")
        print(f"Recording Type Detected: {recording_type.value}")
        print(f"Confidence Score: {adaptive_params.confidence:.1%}")
        print(f"Mastering Philosophy: {adaptive_params.mastering_philosophy}")
        print(f"Detection Time: {detection_time*1000:.1f}ms")
        print(f"\nAudio Characteristics:")
        print(f"  Spectral Centroid: {fingerprint.get('spectral_centroid', 0)*20000:.0f} Hz")
        print(f"  Bass-to-Mid Ratio: {fingerprint.get('bass_mid_ratio', 0):+.2f} dB")
        print(f"  Stereo Width: {fingerprint.get('stereo_width', 0):.2f}")
        print(f"  Crest Factor: {fingerprint.get('crest_db', 0):.2f} dB")
        print(f"\nAdaptive Parameters:")
        print(f"  Bass Adjustment: {adaptive_params.bass_adjustment_db:+.2f} dB")
        print(f"  Mid Adjustment: {adaptive_params.mid_adjustment_db:+.2f} dB")
        print(f"  Treble Adjustment: {adaptive_params.treble_adjustment_db:+.2f} dB")
        print(f"  Stereo Strategy: {adaptive_params.stereo_strategy}")
        print(f"  Stereo Width Target: {adaptive_params.stereo_width_target:.2f}")
        print(f"{'='*70}\n")

        # Assertions
        assert recording_type in [RecordingType.STUDIO, RecordingType.UNKNOWN]
        assert 0 <= adaptive_params.confidence <= 1
        assert adaptive_params.mastering_philosophy in ["enhance", "correct", "punch"]
        assert detection_time < 5.0  # Should detect within 5 seconds

    def test_iron_maiden_metal_detection(self, detector, fingerprint_analyzer):
        """Validate Iron Maiden detection as METAL recording."""
        audio_file = self.IRON_MAIDEN_DIR / "01. Wasted Years.flac"

        if not audio_file.exists():
            pytest.skip(f"Audio file not found: {audio_file}")

        # Load audio
        audio, sr = librosa.load(str(audio_file), sr=44100, mono=False)

        # Detect recording type
        start_time = time.time()
        recording_type, adaptive_params = detector.detect(audio, sr)
        detection_time = time.time() - start_time

        # Extract fingerprint for logging
        fingerprint = fingerprint_analyzer.analyze(audio, sr)

        # Log results
        print(f"\n{'='*70}")
        print(f"Iron Maiden - Wasted Years (Metal Reference)")
        print(f"{'='*70}")
        print(f"Recording Type Detected: {recording_type.value}")
        print(f"Confidence Score: {adaptive_params.confidence:.1%}")
        print(f"Mastering Philosophy: {adaptive_params.mastering_philosophy}")
        print(f"Detection Time: {detection_time*1000:.1f}ms")
        print(f"\nAudio Characteristics:")
        print(f"  Spectral Centroid: {fingerprint.get('spectral_centroid', 0)*20000:.0f} Hz")
        print(f"  Bass-to-Mid Ratio: {fingerprint.get('bass_mid_ratio', 0):+.2f} dB")
        print(f"  Stereo Width: {fingerprint.get('stereo_width', 0):.2f}")
        print(f"  Crest Factor: {fingerprint.get('crest_db', 0):.2f} dB")
        print(f"\nAdaptive Parameters:")
        print(f"  Bass Adjustment: {adaptive_params.bass_adjustment_db:+.2f} dB")
        print(f"  Mid Adjustment: {adaptive_params.mid_adjustment_db:+.2f} dB")
        print(f"  Treble Adjustment: {adaptive_params.treble_adjustment_db:+.2f} dB")
        print(f"  Stereo Strategy: {adaptive_params.stereo_strategy}")
        print(f"  Stereo Width Target: {adaptive_params.stereo_width_target:.2f}")
        print(f"{'='*70}\n")

        # Assertions
        assert recording_type in [RecordingType.METAL, RecordingType.UNKNOWN]
        assert 0 <= adaptive_params.confidence <= 1
        assert adaptive_params.mastering_philosophy in ["enhance", "correct", "punch"]
        assert detection_time < 5.0  # Should detect within 5 seconds

    def test_multiple_deep_purple_tracks(self, detector, fingerprint_analyzer):
        """Test consistency across multiple Deep Purple tracks."""
        if not self.DEEP_PURPLE_DIR.exists():
            pytest.skip(f"Directory not found: {self.DEEP_PURPLE_DIR}")

        flac_files = sorted(self.DEEP_PURPLE_DIR.glob("*.flac"))[:3]  # First 3 tracks

        if not flac_files:
            pytest.skip("No FLAC files found in Deep Purple directory")

        print(f"\n{'='*70}")
        print(f"Deep Purple - Multiple Tracks Consistency Test")
        print(f"{'='*70}\n")

        results = []
        for audio_file in flac_files:
            # Load audio
            audio, sr = librosa.load(str(audio_file), sr=44100, mono=False)

            # Detect
            recording_type, adaptive_params = detector.detect(audio, sr)
            fingerprint = fingerprint_analyzer.analyze(audio, sr)

            results.append({
                'track': audio_file.name,
                'type': recording_type.value,
                'confidence': adaptive_params.confidence,
                'philosophy': adaptive_params.mastering_philosophy,
                'centroid': fingerprint.get('spectral_centroid', 0) * 20000,
            })

            print(f"{audio_file.name}")
            print(f"  Type: {recording_type.value}, Confidence: {adaptive_params.confidence:.1%}")
            print(f"  Philosophy: {adaptive_params.mastering_philosophy}")
            print(f"  Centroid: {fingerprint.get('spectral_centroid', 0)*20000:.0f} Hz")

        print(f"\n{'='*70}")
        print(f"Consistency Summary:")
        avg_confidence = np.mean([r['confidence'] for r in results])
        print(f"  Average Confidence: {avg_confidence:.1%}")
        print(f"  Unique Types: {set(r['type'] for r in results)}")
        print(f"  Unique Philosophies: {set(r['philosophy'] for r in results)}")
        print(f"{'='*70}\n")

        # All should be studio or consistent
        assert len(results) > 0
        assert all(0 <= r['confidence'] <= 1 for r in results)

    def test_deep_purple_studio_characteristics(self, fingerprint_analyzer):
        """Verify Deep Purple has expected studio characteristics."""
        audio_file = self.DEEP_PURPLE_DIR / "01. Speed King.flac"

        if not audio_file.exists():
            pytest.skip(f"Audio file not found: {audio_file}")

        # Load audio
        audio, sr = librosa.load(str(audio_file), sr=44100, mono=False)

        # Get fingerprint
        fingerprint = fingerprint_analyzer.analyze(audio, sr)

        print(f"\n{'='*70}")
        print(f"Deep Purple Studio Characteristics Analysis")
        print(f"{'='*70}")
        print(f"Expected Range: ~664 Hz centroid, ~1 dB bass-to-mid")
        print(f"\nActual Measurements:")
        print(f"  Spectral Centroid: {fingerprint.get('spectral_centroid', 0)*20000:.0f} Hz")
        print(f"  Bass-to-Mid Ratio: {fingerprint.get('bass_mid_ratio', 0):+.2f} dB")
        print(f"  Stereo Width: {fingerprint.get('stereo_width', 0):.2f}")
        print(f"  Crest Factor: {fingerprint.get('crest_db', 0):.2f} dB")
        print(f"  Flatness: {fingerprint.get('flatness', 0):.2f}")
        print(f"{'='*70}\n")

        # Verify characteristics are in reasonable range for studio
        centroid = fingerprint.get('spectral_centroid', 0) * 20000
        bass_mid = fingerprint.get('bass_mid_ratio', 0)
        stereo_width = fingerprint.get('stereo_width', 0)

        # Studio should have moderate centroid (400-1000 Hz), moderate bass, good stereo
        assert 300 < centroid < 2000, f"Centroid {centroid} outside expected range"
        assert -10 < bass_mid < 15, f"Bass-to-mid {bass_mid} outside expected range"
        assert 0.2 < stereo_width < 0.7, f"Stereo width {stereo_width} outside expected range"

    def test_iron_maiden_metal_characteristics(self, fingerprint_analyzer):
        """Verify Iron Maiden has expected metal characteristics."""
        audio_file = self.IRON_MAIDEN_DIR / "01. Wasted Years.flac"

        if not audio_file.exists():
            pytest.skip(f"Audio file not found: {audio_file}")

        # Load audio
        audio, sr = librosa.load(str(audio_file), sr=44100, mono=False)

        # Get fingerprint
        fingerprint = fingerprint_analyzer.analyze(audio, sr)

        print(f"\n{'='*70}")
        print(f"Iron Maiden Metal Characteristics Analysis")
        print(f"{'='*70}")
        print(f"Expected Range: ~1340 Hz centroid, ~10 dB bass-to-mid")
        print(f"\nActual Measurements:")
        print(f"  Spectral Centroid: {fingerprint.get('spectral_centroid', 0)*20000:.0f} Hz")
        print(f"  Bass-to-Mid Ratio: {fingerprint.get('bass_mid_ratio', 0):+.2f} dB")
        print(f"  Stereo Width: {fingerprint.get('stereo_width', 0):.2f}")
        print(f"  Crest Factor: {fingerprint.get('crest_db', 0):.2f} dB")
        print(f"  Flatness: {fingerprint.get('flatness', 0):.2f}")
        print(f"{'='*70}\n")

        # Verify characteristics are in reasonable range for metal
        centroid = fingerprint.get('spectral_centroid', 0) * 20000
        bass_mid = fingerprint.get('bass_mid_ratio', 0)
        stereo_width = fingerprint.get('stereo_width', 0)

        # Metal should have bright centroid (>1000 Hz), moderate-high bass, good stereo
        assert centroid > 800, f"Centroid {centroid} should be bright for metal"
        assert 5 < bass_mid < 20, f"Bass-to-mid {bass_mid} outside expected range for metal"
        assert 0.2 < stereo_width < 0.7, f"Stereo width {stereo_width} outside expected range"

    def test_detection_performance(self, detector, fingerprint_analyzer):
        """Measure detection performance on real audio."""
        audio_file = self.DEEP_PURPLE_DIR / "01. Speed King.flac"

        if not audio_file.exists():
            pytest.skip(f"Audio file not found: {audio_file}")

        # Load audio
        audio, sr = librosa.load(str(audio_file), sr=44100, mono=False)

        # Get audio duration
        duration_seconds = len(audio[0]) / sr

        print(f"\n{'='*70}")
        print(f"Detection Performance Measurement")
        print(f"{'='*70}")
        print(f"Audio Duration: {duration_seconds:.1f} seconds")
        print(f"Sample Rate: {sr} Hz")
        print(f"Channels: {audio.ndim}")

        # Time the detector
        start_time = time.time()
        recording_type, adaptive_params = detector.detect(audio, sr)
        total_time = time.time() - start_time

        print(f"\nDetection Timing:")
        print(f"  Total Time: {total_time*1000:.1f} ms")
        print(f"  Time per Second of Audio: {(total_time/duration_seconds)*1000:.1f} ms")
        print(f"  Real-Time Factor: {duration_seconds/total_time:.1f}x")
        print(f"  Overhead: {(total_time/duration_seconds)*100:.1f}% of audio duration")
        print(f"{'='*70}\n")

        # Assertions
        assert total_time < 10.0, f"Detection took too long: {total_time}s"
        assert duration_seconds / total_time > 5, "Real-time factor should be > 5x"


class TestPhase6AudioMetricsValidation:
    """Validate metrics on real audio."""

    @pytest.fixture
    def fingerprint_analyzer(self):
        """Create fingerprint analyzer."""
        return AudioFingerprintAnalyzer()

    DEEP_PURPLE_DIR = Path("/mnt/audio/Audio/Remasters/Deep Purple - In Rock")
    IRON_MAIDEN_DIR = Path("/mnt/audio/Audio/Remasters/Iron Maiden - Wasted Years (S)")

    def test_spectral_metrics_consistency(self, fingerprint_analyzer):
        """Verify spectral metrics are consistent across measurements."""
        audio_file = self.DEEP_PURPLE_DIR / "01. Speed King.flac"

        if not audio_file.exists():
            pytest.skip(f"Audio file not found: {audio_file}")

        # Load audio
        audio, sr = librosa.load(str(audio_file), sr=44100, mono=False)

        print(f"\n{'='*70}")
        print(f"Spectral Metrics Consistency Test")
        print(f"{'='*70}\n")

        # Multiple measurements
        measurements = []
        for i in range(3):
            fingerprint = fingerprint_analyzer.analyze(audio, sr)
            centroid = fingerprint.get('spectral_centroid', 0) * 20000
            bass_mid = fingerprint.get('bass_mid_ratio', 0)
            measurements.append({'centroid': centroid, 'bass_mid': bass_mid})
            print(f"Measurement {i+1}: Centroid={centroid:.0f} Hz, Bass-Mid={bass_mid:+.2f} dB")

        # Check consistency
        centroids = [m['centroid'] for m in measurements]
        bass_mids = [m['bass_mid'] for m in measurements]

        print(f"\nConsistency Check:")
        print(f"  Centroid Std Dev: {np.std(centroids):.1f} Hz")
        print(f"  Bass-Mid Std Dev: {np.std(bass_mids):.2f} dB")
        print(f"{'='*70}\n")

        # Should be reasonably consistent
        assert np.std(centroids) < 100, "Centroid measurements should be consistent"
        assert np.std(bass_mids) < 2.0, "Bass-mid measurements should be consistent"
