"""
Validation Tests: Auralis vs World-Class Masters

Test Auralis's adaptive processing against professionally mastered references
from legendary engineers (Steven Wilson, Quincy Jones, etc.).

Goal: Ensure Auralis meets or exceeds industry standards.
"""

from pathlib import Path
from typing import Dict, List

import numpy as np
import pytest

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.io.unified_loader import load_audio
from auralis.learning.reference_analyzer import MasteringProfile, ReferenceAnalyzer
from auralis.learning.reference_library import (
    Genre,
    MasteringEngineer,
    ReferenceTrack,
    get_quality_benchmark,
    get_references_for_genre,
)


class QualityValidator:
    """
    Validates Auralis output against professional mastering standards.
    """

    def __init__(self):
        self.analyzer = ReferenceAnalyzer()

    def validate_against_reference(
        self,
        auralis_audio: np.ndarray,
        reference_audio: np.ndarray,
        sr: int,
        genre: Genre,
    ) -> Dict[str, any]:
        """
        Compare Auralis output against a professional reference.

        Args:
            auralis_audio: Audio processed by Auralis
            reference_audio: Professional master reference
            sr: Sample rate
            genre: Music genre

        Returns:
            Validation results with metrics and pass/fail status
        """
        # Get quality benchmarks for this genre
        benchmarks = get_quality_benchmark(genre)

        # Analyze both tracks
        print("Analyzing Auralis output...")
        auralis_profile = self._quick_profile(auralis_audio, sr)

        print("Analyzing reference...")
        ref_profile = self._quick_profile(reference_audio, sr)

        # Compare metrics
        results = {
            'genre': genre.value,
            'auralis': auralis_profile,
            'reference': ref_profile,
            'comparisons': {},
            'benchmarks': benchmarks,
            'tests_passed': {},
            'overall_pass': True,
        }

        # === LUFS Comparison ===
        lufs_diff = abs(auralis_profile['lufs'] - ref_profile['lufs'])
        lufs_pass = lufs_diff <= 2.0  # Within 2 LUFS is acceptable
        results['comparisons']['lufs_difference'] = lufs_diff
        results['tests_passed']['lufs'] = lufs_pass

        # === Dynamic Range Comparison ===
        dr_diff = abs(auralis_profile['dr'] - ref_profile['dr'])
        dr_ratio = auralis_profile['dr'] / (ref_profile['dr'] + 0.1)
        dr_pass = dr_ratio >= 0.85  # Preserve at least 85% of DR
        results['comparisons']['dr_difference'] = dr_diff
        results['comparisons']['dr_ratio'] = dr_ratio
        results['tests_passed']['dynamic_range'] = dr_pass

        # Check against genre minimum
        if benchmarks.get('min_dynamic_range'):
            min_dr_pass = auralis_profile['dr'] >= benchmarks['min_dynamic_range']
            results['tests_passed']['min_dr_benchmark'] = min_dr_pass
        else:
            min_dr_pass = True

        # === Frequency Balance Comparison ===
        bass_diff = abs(
            auralis_profile['bass_to_mid'] - ref_profile['bass_to_mid']
        )
        high_diff = abs(
            auralis_profile['high_to_mid'] - ref_profile['high_to_mid']
        )

        freq_balance_pass = bass_diff <= 3.0 and high_diff <= 3.0  # Within 3dB
        results['comparisons']['bass_to_mid_diff'] = bass_diff
        results['comparisons']['high_to_mid_diff'] = high_diff
        results['tests_passed']['frequency_balance'] = freq_balance_pass

        # === Stereo Width Comparison ===
        stereo_diff = abs(auralis_profile['stereo_width'] - ref_profile['stereo_width'])
        stereo_pass = stereo_diff <= 0.15  # Within 0.15 (on 0-1 scale)
        results['comparisons']['stereo_width_diff'] = stereo_diff
        results['tests_passed']['stereo_width'] = stereo_pass

        # === Spectral Similarity ===
        spectral_sim = self._calculate_spectral_similarity(
            auralis_audio, reference_audio, sr
        )
        spectral_pass = spectral_sim >= 0.75  # At least 75% similar
        results['comparisons']['spectral_similarity'] = spectral_sim
        results['tests_passed']['spectral_similarity'] = spectral_pass

        # === Overall Pass/Fail ===
        all_tests = [
            lufs_pass,
            dr_pass,
            min_dr_pass,
            freq_balance_pass,
            stereo_pass,
            spectral_pass,
        ]
        results['overall_pass'] = all(all_tests)
        results['pass_rate'] = sum(all_tests) / len(all_tests)

        return results

    def _quick_profile(self, audio: np.ndarray, sr: int) -> Dict:
        """Quick analysis profile for comparison."""
        # Ensure stereo
        if audio.ndim == 1:
            audio = np.stack([audio, audio])

        # Loudness
        from auralis.analysis.loudness_meter import LoudnessMeter
        loudness_meter = LoudnessMeter()
        loudness = loudness_meter.measure(audio, sr)

        # Dynamic range
        from auralis.analysis.dynamic_range import calculate_dynamic_range
        dr = calculate_dynamic_range(audio, sr)

        # RMS
        rms = np.sqrt(np.mean(audio ** 2))
        rms_db = 20 * np.log10(rms + 1e-10)

        # Frequency balance
        mono = np.mean(audio, axis=0)
        n_fft = 4096
        spectrum = np.abs(np.fft.rfft(mono, n=n_fft))
        freqs = np.fft.rfftfreq(n_fft, 1/sr)

        bass_mask = (freqs >= 20) & (freqs <= 250)
        mid_mask = (freqs >= 250) & (freqs <= 4000)
        high_mask = (freqs >= 4000) & (freqs <= 20000)

        bass_energy = 20 * np.log10(np.mean(spectrum[bass_mask]) + 1e-10)
        mid_energy = 20 * np.log10(np.mean(spectrum[mid_mask]) + 1e-10)
        high_energy = 20 * np.log10(np.mean(spectrum[high_mask]) + 1e-10)

        # Stereo width
        if audio.ndim == 2:
            left, right = audio[0], audio[1]
            correlation = np.corrcoef(left, right)[0, 1]
            stereo_width = 1.0 - abs(correlation)
        else:
            stereo_width = 0.0

        return {
            'lufs': loudness['integrated_lufs'],
            'lu_range': loudness['loudness_range'],
            'dr': dr,
            'rms_db': rms_db,
            'bass_to_mid': bass_energy - mid_energy,
            'high_to_mid': high_energy - mid_energy,
            'stereo_width': stereo_width,
        }

    def _calculate_spectral_similarity(
        self, audio1: np.ndarray, audio2: np.ndarray, sr: int
    ) -> float:
        """
        Calculate spectral similarity between two audio tracks.

        Returns value from 0 (completely different) to 1 (identical).
        """
        # Convert to mono
        if audio1.ndim == 2:
            mono1 = np.mean(audio1, axis=0)
        else:
            mono1 = audio1

        if audio2.ndim == 2:
            mono2 = np.mean(audio2, axis=0)
        else:
            mono2 = audio2

        # Ensure same length (truncate to shorter)
        min_len = min(len(mono1), len(mono2))
        mono1 = mono1[:min_len]
        mono2 = mono2[:min_len]

        # FFT
        n_fft = 4096
        spectrum1 = np.abs(np.fft.rfft(mono1, n=n_fft))
        spectrum2 = np.abs(np.fft.rfft(mono2, n=n_fft))

        # Normalize
        spectrum1 = spectrum1 / (np.sum(spectrum1) + 1e-10)
        spectrum2 = spectrum2 / (np.sum(spectrum2) + 1e-10)

        # Cosine similarity
        dot_product = np.sum(spectrum1 * spectrum2)
        norm1 = np.sqrt(np.sum(spectrum1 ** 2))
        norm2 = np.sqrt(np.sum(spectrum2 ** 2))

        similarity = dot_product / (norm1 * norm2 + 1e-10)

        return float(similarity)


# =============================================================================
# Pytest Test Cases
# =============================================================================

@pytest.fixture
def validator():
    """Create QualityValidator instance."""
    return QualityValidator()


@pytest.fixture
def auralis_processor():
    """Create HybridProcessor instance."""
    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    return HybridProcessor(config)


@pytest.mark.skipif(
    not Path("/path/to/references").exists(),
    reason="Reference library not available"
)
class TestAgainstStevenWilson:
    """Test Auralis against Steven Wilson's mastering standards."""

    def test_porcupine_tree_prodigal(self, validator, auralis_processor):
        """
        Test against Porcupine Tree - Prodigal (2021 remaster).

        This is the gold standard for progressive rock mastering.
        """
        # Load reference
        ref_path = Path("/path/to/references/Porcupine Tree - Prodigal.flac")
        ref_audio, sr = load_audio(str(ref_path))

        # Create unmastered version (simulate raw mix)
        # In practice, you'd use the original 1992 version
        unmastered = ref_audio * 0.5  # Simple simulation

        # Process with Auralis
        auralis_audio = auralis_processor.process(unmastered)

        # Validate
        results = validator.validate_against_reference(
            auralis_audio, ref_audio, sr, Genre.PROGRESSIVE_ROCK
        )

        # Print results
        print("\n=== STEVEN WILSON VALIDATION ===")
        print(f"Track: Porcupine Tree - Prodigal")
        print(f"\nComparisons:")
        for key, value in results['comparisons'].items():
            print(f"  {key}: {value:.3f}")

        print(f"\nTests:")
        for test, passed in results['tests_passed'].items():
            status = "✓" if passed else "✗"
            print(f"  {status} {test}")

        print(f"\nOverall: {'PASS' if results['overall_pass'] else 'FAIL'}")
        print(f"Pass rate: {results['pass_rate']:.1%}")

        # Assertions
        assert results['pass_rate'] >= 0.75, "Should pass at least 75% of tests"
        assert results['tests_passed']['dynamic_range'], "Must preserve dynamic range"


@pytest.mark.skipif(
    not Path("/path/to/references").exists(),
    reason="Reference library not available"
)
class TestAgainstQuincyJones:
    """Test Auralis against Quincy Jones production standards."""

    def test_billie_jean(self, validator, auralis_processor):
        """
        Test against Michael Jackson - Billie Jean.

        The gold standard for pop production.
        """
        # Load reference
        ref_path = Path("/path/to/references/Michael Jackson - Billie Jean.flac")
        ref_audio, sr = load_audio(str(ref_path))

        # Create unmastered version
        unmastered = ref_audio * 0.6

        # Process with Auralis
        auralis_audio = auralis_processor.process(unmastered)

        # Validate
        results = validator.validate_against_reference(
            auralis_audio, ref_audio, sr, Genre.POP
        )

        # Print results
        print("\n=== QUINCY JONES VALIDATION ===")
        print(f"Track: Michael Jackson - Billie Jean")
        print(f"\nComparisons:")
        for key, value in results['comparisons'].items():
            print(f"  {key}: {value:.3f}")

        print(f"\nOverall: {'PASS' if results['overall_pass'] else 'FAIL'}")

        # Assertions
        assert results['pass_rate'] >= 0.75, "Should match Quincy Jones standards"


def test_the_cure_wish_album_matchering_comparison():
    """
    Test Auralis on The Cure - Wish album against Matchering results.

    This validates that Auralis can match Matchering quality when the
    goal is to match a modern reference (Porcupine Tree).
    """
    # This test requires:
    # 1. Original Cure - Wish tracks (1992)
    # 2. Porcupine Tree - Prodigal reference
    # 3. Matchering processed results (for comparison)

    pytest.skip("Requires audio files - see implementation notes")

    # Implementation:
    # 1. Process Cure tracks with Auralis adaptive mode
    # 2. Compare against Matchering results
    # 3. Validate both meet Steven Wilson quality standards


# =============================================================================
# Utility Functions for Manual Testing
# =============================================================================

def compare_auralis_vs_matchering(
    original_path: Path,
    matchering_path: Path,
    output_path: Path,
) -> Dict:
    """
    Process a track with Auralis and compare against Matchering result.

    Args:
        original_path: Original unmastered track
        matchering_path: Matchering processed version
        output_path: Where to save Auralis result

    Returns:
        Comparison metrics
    """
    # Load audio
    original, sr = load_audio(str(original_path))
    matchering, _ = load_audio(str(matchering_path))

    # Process with Auralis
    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)
    auralis = processor.process(original)

    # Save Auralis result
    from auralis.io.saver import save
    save(str(output_path), auralis, sr, subtype='PCM_24')

    # Compare
    validator = QualityValidator()
    results = validator.validate_against_reference(
        auralis, matchering, sr, Genre.PROGRESSIVE_ROCK
    )

    return results


if __name__ == "__main__":
    print("=== AURALIS VALIDATION AGAINST WORLD-CLASS MASTERS ===\n")
    print("Run with pytest to execute test suite")
    print("Example: pytest test_against_masters.py -v")
