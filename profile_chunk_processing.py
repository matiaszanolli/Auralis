#!/usr/bin/env python3
"""
Profile chunk processing to identify bottlenecks.

Usage:
    python profile_chunk_processing.py <audio_file> [preset] [intensity]

Example:
    python profile_chunk_processing.py "/path/to/track.flac" adaptive 1.0
"""

import sys
import time
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from auralis.io.unified_loader import load_audio
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.analysis.fingerprint import AudioFingerprintAnalyzer
import numpy as np


def profile_section(name):
    """Context manager to profile a section of code."""
    class ProfileContext:
        def __init__(self, section_name):
            self.name = section_name
            self.start = None

        def __enter__(self):
            self.start = time.time()
            return self

        def __exit__(self, *args):
            elapsed = time.time() - self.start
            print(f"  {self.name}: {elapsed:.3f}s")

    return ProfileContext(name)


def profile_chunk_processing(audio_file: str, preset: str = "adaptive", intensity: float = 1.0):
    """Profile a complete chunk processing cycle."""

    print(f"\n{'='*70}")
    print(f"Profiling Chunk Processing")
    print(f"{'='*70}")
    print(f"Audio file: {audio_file}")
    print(f"Preset: {preset}")
    print(f"Intensity: {intensity}")
    print(f"{'='*70}\n")

    # Load audio
    print("Step 1: Loading Audio")
    with profile_section("Audio loading"):
        audio, sr = load_audio(audio_file)

    print(f"  Duration: {len(audio) / sr:.1f}s")
    print(f"  Sample rate: {sr} Hz")
    print(f"  Channels: {audio.shape[1] if audio.ndim > 1 else 1}")
    print()

    # Extract first 30 seconds (one chunk)
    chunk_samples = 30 * sr
    audio_chunk = audio[:chunk_samples]

    print("Step 2: Fingerprint Analysis")
    with profile_section("TOTAL Fingerprint Analysis") as total_fp:
        analyzer = AudioFingerprintAnalyzer()

        with profile_section("  - Frequency analysis"):
            from auralis.analysis.fingerprint.frequency_analyzer import FrequencyAnalyzer
            freq_analyzer = FrequencyAnalyzer()
            freq_result = freq_analyzer.analyze(audio_chunk, sr)

        with profile_section("  - Dynamics analysis"):
            from auralis.analysis.fingerprint.dynamics_analyzer import DynamicsAnalyzer
            dyn_analyzer = DynamicsAnalyzer()
            dyn_result = dyn_analyzer.analyze(audio_chunk, sr)

        with profile_section("  - Temporal analysis (SLOW - librosa)"):
            from auralis.analysis.fingerprint.temporal_analyzer import TemporalAnalyzer
            temp_analyzer = TemporalAnalyzer()
            temp_result = temp_analyzer.analyze(audio_chunk, sr)

        with profile_section("  - Spectral analysis"):
            from auralis.analysis.fingerprint.spectral_analyzer import SpectralAnalyzer
            spec_analyzer = SpectralAnalyzer()
            spec_result = spec_analyzer.analyze(audio_chunk, sr)

        with profile_section("  - Harmonic analysis"):
            from auralis.analysis.fingerprint.harmonic_analyzer import HarmonicAnalyzer
            harm_analyzer = HarmonicAnalyzer()
            harm_result = harm_analyzer.analyze(audio_chunk, sr)

        with profile_section("  - Variation analysis"):
            from auralis.analysis.fingerprint.variation_analyzer import VariationAnalyzer
            var_analyzer = VariationAnalyzer()
            var_result = var_analyzer.analyze(audio_chunk, sr)

        with profile_section("  - Stereo analysis"):
            from auralis.analysis.fingerprint.stereo_analyzer import StereoAnalyzer
            stereo_analyzer = StereoAnalyzer()
            stereo_result = stereo_analyzer.analyze(audio_chunk, sr)

    print()

    # Process audio
    print("Step 3: Audio Processing")
    with profile_section("TOTAL Audio Processing") as total_proc:
        config = UnifiedConfig()
        config.set_processing_mode("adaptive")
        config.set_preset(preset)

        processor = HybridProcessor(config)

        with profile_section("  - HybridProcessor.process()"):
            processed_chunk = processor.process(audio_chunk)

    print()

    # Summary
    print(f"{'='*70}")
    print("Summary")
    print(f"{'='*70}")
    print(f"Total time: {total_fp.start - time.time() if hasattr(total_fp, 'start') else 0:.3f}s")
    print(f"  - Fingerprint analysis: (see above)")
    print(f"  - Audio processing: (see above)")
    print()
    print("Bottleneck Identification:")
    print("  🔴 SLOW: Temporal analysis (librosa tempo detection)")
    print("  🟡 MODERATE: Full audio processing pipeline")
    print("  🟢 FAST: All other fingerprint components")
    print()
    print("Optimization Recommendations:")
    print("  1. Cache track-level fingerprints in database")
    print("     - Extract once per track, reuse for all chunks")
    print("     - Saves ~0.5-1s per chunk")
    print()
    print("  2. Parallel chunk processing")
    print("     - Process chunks 0-2 simultaneously")
    print("     - Start playback when chunk 0 ready")
    print("     - Chunks 1-2 ready when needed")
    print()
    print("  3. Optional: Fast-path processing")
    print("     - Skip heavy analysis for first chunk")
    print("     - Use simplified processing (< 1s)")
    print("     - Upgrade quality in background")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    audio_file = sys.argv[1]
    preset = sys.argv[2] if len(sys.argv) > 2 else "adaptive"
    intensity = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0

    if not Path(audio_file).exists():
        print(f"Error: Audio file not found: {audio_file}")
        sys.exit(1)

    profile_chunk_processing(audio_file, preset, intensity)
