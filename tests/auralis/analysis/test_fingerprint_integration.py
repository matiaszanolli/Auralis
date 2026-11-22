#!/usr/bin/env python3
"""
Test script for 25D audio fingerprint integration into processing pipeline.

This validates that:
1. ContentAnalyzer extracts 25D fingerprints
2. AdaptiveTargetGenerator uses fingerprint data for intelligent target generation
3. Processing targets are enhanced by fingerprint analysis
4. The integration works across different audio characteristics

Usage:
    python test_fingerprint_integration.py /path/to/audio.flac
    python test_fingerprint_integration.py  # Uses synthetic test signals
"""

import sys
from pathlib import Path

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from auralis.core.analysis import AdaptiveTargetGenerator, ContentAnalyzer
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.config import UnifiedConfig
from auralis.io.unified_loader import load_audio


def generate_test_signals(sample_rate=44100, duration=10):
    """Generate test audio signals with different characteristics."""

    signals = {}
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples)

    # 1. Bass-heavy electronic (sub-bass + bass dominant)
    bass_heavy = (
        0.5 * np.sin(2 * np.pi * 50 * t) +    # Sub-bass
        0.4 * np.sin(2 * np.pi * 120 * t) +   # Bass
        0.1 * np.sin(2 * np.pi * 2000 * t)    # Mids (minimal)
    )
    # Stereo with wide width
    signals['bass_heavy_electronic'] = np.column_stack([
        bass_heavy + 0.1 * np.random.randn(num_samples),
        bass_heavy * 0.7 + 0.1 * np.random.randn(num_samples)
    ]) * 0.3

    # 2. Bright acoustic (presence + air dominant)
    bright_acoustic = (
        0.1 * np.sin(2 * np.pi * 80 * t) +     # Bass (minimal)
        0.2 * np.sin(2 * np.pi * 800 * t) +    # Mids
        0.4 * np.sin(2 * np.pi * 4000 * t) +   # Presence
        0.3 * np.sin(2 * np.pi * 8000 * t)     # Air
    )
    # Stereo with narrow width (acoustic recording)
    signals['bright_acoustic'] = np.column_stack([
        bright_acoustic + 0.05 * np.random.randn(num_samples),
        bright_acoustic * 0.95 + 0.05 * np.random.randn(num_samples)
    ]) * 0.2

    # 3. Compressed modern mix (low crest factor)
    compressed_modern = 0.3 * np.sin(2 * np.pi * 200 * t) + 0.2 * np.random.randn(num_samples)
    # Hard clip to simulate brick-wall limiting
    compressed_modern = np.clip(compressed_modern, -0.9, 0.9)
    signals['compressed_modern'] = np.column_stack([
        compressed_modern,
        compressed_modern * 0.9
    ])

    # 4. Dynamic classical (high crest factor)
    # Quiet sustained tones with loud peaks
    dynamic_classical = 0.05 * np.sin(2 * np.pi * 440 * t)  # Sustained
    # Add transient peaks
    peak_positions = np.random.randint(0, num_samples, 20)
    for pos in peak_positions:
        if pos + 1000 < num_samples:
            dynamic_classical[pos:pos+1000] += 0.5 * np.exp(-np.linspace(0, 5, 1000))
    signals['dynamic_classical'] = np.column_stack([
        dynamic_classical + 0.01 * np.random.randn(num_samples),
        dynamic_classical * 0.85 + 0.01 * np.random.randn(num_samples)
    ])

    # 5. Percussive rhythm (high transient density)
    percussive = np.zeros(num_samples)
    # Add transients every 0.5 seconds (120 BPM)
    for i in range(0, num_samples, sample_rate // 2):
        if i + 500 < num_samples:
            percussive[i:i+500] = 0.6 * np.exp(-np.linspace(0, 10, 500))
    signals['percussive_rhythm'] = np.column_stack([
        percussive + 0.05 * np.random.randn(num_samples),
        percussive + 0.05 * np.random.randn(num_samples)
    ])

    return signals


def test_fingerprint_extraction():
    """Test that ContentAnalyzer extracts 25D fingerprints."""

    analyzer = ContentAnalyzer(sample_rate=44100, use_fingerprint_analysis=True)
    signals = generate_test_signals()

    for signal_name, audio in signals.items():
        profile = analyzer.analyze_content(audio)

        # Check that fingerprint was extracted
        assert "fingerprint" in profile, f"Fingerprint missing for {signal_name}"
        assert profile["fingerprint"] is not None, f"Fingerprint is None for {signal_name}"

        fingerprint = profile["fingerprint"]

        # Verify all 25 dimensions are present
        expected_keys = [
            # Frequency (7D)
            'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
            'upper_mid_pct', 'presence_pct', 'air_pct',
            # Dynamics (3D)
            'lufs', 'crest_db', 'bass_mid_ratio',
            # Temporal (4D)
            'tempo_bpm', 'rhythm_stability', 'transient_density', 'silence_ratio',
            # Spectral (3D)
            'spectral_centroid', 'spectral_rolloff', 'spectral_flatness',
            # Harmonic (3D)
            'harmonic_ratio', 'pitch_stability', 'chroma_energy',
            # Variation (3D)
            'dynamic_range_variation', 'loudness_variation_std', 'peak_consistency',
            # Stereo (2D)
            'stereo_width', 'phase_correlation'
        ]

        for key in expected_keys:
            assert key in fingerprint, f"Missing dimension: {key}"

        # Print some key fingerprint features


def test_target_generation():
    """Test that AdaptiveTargetGenerator uses fingerprint data."""

    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    analyzer = ContentAnalyzer(sample_rate=44100, use_fingerprint_analysis=True)
    target_gen = AdaptiveTargetGenerator(config)

    signals = generate_test_signals()

    for signal_name, audio in signals.items():

        # Analyze content
        profile = analyzer.analyze_content(audio)

        # Generate targets WITHOUT fingerprint
        profile_no_fp = profile.copy()
        profile_no_fp.pop("fingerprint", None)
        targets_baseline = target_gen.generate_targets(profile_no_fp)

        # Generate targets WITH fingerprint
        targets_enhanced = target_gen.generate_targets(profile)

        # The fingerprint is what makes the targets fingerprint-driven.
        assert targets_enhanced.get("fingerprint_driven") is True, \
            f"Fingerprint-driven flag missing for {signal_name}"
        assert targets_baseline.get("fingerprint_driven") is not True, \
            f"Targets claim to be fingerprint-driven without a fingerprint for {signal_name}"



def test_end_to_end_processing():
    """Test end-to-end processing with fingerprint integration."""

    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)

    signals = generate_test_signals()

    for signal_name, audio in list(signals.items())[:2]:  # Test first 2 to save time

        processed = processor.process(audio)

        assert processed.shape == audio.shape, f"Shape mismatch for {signal_name}"
        assert not np.isnan(processed).any(), f"NaN values in output for {signal_name}"
        assert not np.isinf(processed).any(), f"Inf values in output for {signal_name}"


def test_real_audio(test_audio_files):
    """Test with real audio file."""
    # The fixture synthesises its files, so there is always one (#6660).
    audio_path = next(iter(test_audio_files.values()))

    # Load audio
    audio, sr = load_audio(audio_path)

    # Analyze
    analyzer = ContentAnalyzer(sample_rate=sr, use_fingerprint_analysis=True)
    profile = analyzer.analyze_content(audio)

    # Verify fingerprint
    assert "fingerprint" in profile, "Fingerprint missing"
    assert {"sub_bass_pct", "lufs", "crest_db", "stereo_width"} <= profile["fingerprint"].keys()

    # Generate targets from it
    targets = AdaptiveTargetGenerator(UnifiedConfig()).generate_targets(profile)
    assert targets.get("fingerprint_driven") is True
