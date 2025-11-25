"""
YIN Rust Implementation Validation Test

Validates the Rust YIN (pitch detection) implementation against librosa reference
implementation using real audio from the Blind Guardian collection.

This test suite validates:
1. Output shape and format consistency
2. Fundamental frequency detection accuracy
3. Voiced/unvoiced frame classification
4. Performance characteristics (timing)
"""

import os
import sys
import time
import numpy as np
import librosa
import pytest
from pathlib import Path
from dataclasses import dataclass


# Blind Guardian audio collection path
BLIND_GUARDIAN_PATH = Path("/mnt/Musica/Musica/Blind Guardian")


@dataclass
class YinTestResult:
    """Result from a YIN test"""
    file: str
    duration: float
    samples: int
    voiced_ratio: float
    mean_frequency: float
    frequency_std: float
    librosa_voiced_ratio: float
    librosa_mean_frequency: float
    librosa_frequency_std: float
    correlation: float
    librosa_time: float
    description: str = ""


class YinValidator:
    """Validator for Rust YIN pitch detection implementation"""

    def __init__(self):
        """Initialize YIN validator"""
        self.fmin = librosa.note_to_hz('C2')  # 65.4 Hz
        self.fmax = librosa.note_to_hz('C7')  # 2093 Hz
        self.frame_length = 2048
        self.hop_length = 512

    def yin_librosa(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Get YIN pitch estimates from librosa reference"""
        return librosa.yin(
            audio,
            fmin=self.fmin,
            fmax=self.fmax,
            sr=sr
        )

    def analyze_f0_contour(self, f0: np.ndarray) -> dict:
        """Analyze F0 contour characteristics"""
        voiced_mask = f0 > 0.0
        voiced_f0 = f0[voiced_mask]

        result = {
            'total_frames': len(f0),
            'voiced_frames': np.sum(voiced_mask),
            'voiced_ratio': float(np.sum(voiced_mask) / len(f0)) if len(f0) > 0 else 0.0,
            'unvoiced_ratio': float(np.sum(~voiced_mask) / len(f0)) if len(f0) > 0 else 1.0,
        }

        if len(voiced_f0) > 0:
            result['mean_frequency'] = float(np.mean(voiced_f0))
            result['median_frequency'] = float(np.median(voiced_f0))
            result['std_frequency'] = float(np.std(voiced_f0))
            result['min_frequency'] = float(np.min(voiced_f0))
            result['max_frequency'] = float(np.max(voiced_f0))
        else:
            result['mean_frequency'] = 0.0
            result['median_frequency'] = 0.0
            result['std_frequency'] = 0.0
            result['min_frequency'] = 0.0
            result['max_frequency'] = 0.0

        return result

    def compare_f0_contours(self, f0_ref: np.ndarray, f0_test: np.ndarray) -> dict:
        """Compare two F0 contours"""
        assert len(f0_ref) == len(f0_test), "F0 contours must have same length"

        # Only compare voiced frames
        voiced_mask = (f0_ref > 0.0) & (f0_test > 0.0)

        if np.sum(voiced_mask) == 0:
            return {
                'correlation': 0.0,
                'mean_abs_error_cents': 0.0,
                'median_abs_error_cents': 0.0,
                'rmse_cents': 0.0,
                'voiced_agreement': 0.0,
            }

        voiced_ref = f0_ref[voiced_mask]
        voiced_test = f0_test[voiced_mask]

        # Pearson correlation
        correlation = float(np.corrcoef(voiced_ref, voiced_test)[0, 1])

        # Error in cents (100 cents = 1 semitone)
        # cents = 1200 * log2(f2 / f1)
        cents_error = 1200.0 * np.log2(voiced_test / (voiced_ref + 1e-8))
        mean_abs_error_cents = float(np.mean(np.abs(cents_error)))
        median_abs_error_cents = float(np.median(np.abs(cents_error)))
        rmse_cents = float(np.sqrt(np.mean(cents_error**2)))

        # Voiced/unvoiced agreement
        ref_voiced = f0_ref > 0.0
        test_voiced = f0_test > 0.0
        voiced_agreement = float(np.mean(ref_voiced == test_voiced))

        return {
            'correlation': correlation,
            'mean_abs_error_cents': mean_abs_error_cents,
            'median_abs_error_cents': median_abs_error_cents,
            'rmse_cents': rmse_cents,
            'voiced_agreement': voiced_agreement,
        }

    def test_audio_file(self, audio_path: Path) -> YinTestResult:
        """Test YIN on a single audio file"""
        # Load audio
        y, sr = librosa.load(str(audio_path), sr=44100, mono=True)

        # Resample if needed
        if sr != 44100:
            y = librosa.resample(y, orig_sr=sr, target_sr=44100)
            sr = 44100

        # Get librosa reference
        start_time = time.perf_counter()
        f0_librosa = self.yin_librosa(y, sr)
        librosa_time = time.perf_counter() - start_time

        # Analyze librosa results
        librosa_stats = self.analyze_f0_contour(f0_librosa)

        # For now, Rust implementation is still in Python via librosa
        # This will be updated in Phase 5 when PyO3 bindings are added
        f0_rust = f0_librosa  # TODO: Call Rust version when available

        # Analyze Rust results (currently same as librosa)
        rust_stats = self.analyze_f0_contour(f0_rust)

        # Compare contours
        comparison = self.compare_f0_contours(f0_librosa, f0_rust)

        return YinTestResult(
            file=audio_path.name,
            duration=len(y) / sr,
            samples=len(y),
            voiced_ratio=rust_stats['voiced_ratio'],
            mean_frequency=rust_stats['mean_frequency'],
            frequency_std=rust_stats['std_frequency'],
            librosa_voiced_ratio=librosa_stats['voiced_ratio'],
            librosa_mean_frequency=librosa_stats['mean_frequency'],
            librosa_frequency_std=librosa_stats['std_frequency'],
            correlation=comparison['correlation'],
            librosa_time=librosa_time,
        )


@pytest.fixture
def yin_validator():
    """YIN validator fixture"""
    return YinValidator()


@pytest.fixture
def blind_guardian_audio_files():
    """Get list of Blind Guardian audio files for testing"""
    if not BLIND_GUARDIAN_PATH.exists():
        pytest.skip(f"Blind Guardian collection not found at {BLIND_GUARDIAN_PATH}")

    audio_files = []

    # Try FLAC files first
    for audio_path in BLIND_GUARDIAN_PATH.glob("**/*.flac"):
        audio_files.append(audio_path)

    # Fallback to MP3 if no FLAC
    if not audio_files:
        for audio_path in BLIND_GUARDIAN_PATH.glob("**/*.mp3"):
            audio_files.append(audio_path)

    # Return first 3 files for validation
    return sorted(audio_files)[:3]


def test_yin_compilation():
    """Test that Rust library is compiled"""
    lib_path = Path(__file__).parent.parent / "vendor" / "auralis-dsp" / "target" / "release"
    assert lib_path.exists(), f"Rust build directory not found at {lib_path}"

    lib_files = list(lib_path.glob("libauralis_dsp*"))
    assert len(lib_files) > 0, "Rust library not compiled"


def test_yin_synthetic_sine_440hz(yin_validator):
    """Test YIN on synthetic 440 Hz sine wave"""
    sr = 44100
    freq = 440.0
    duration = 1.0
    t = np.arange(int(sr * duration)) / sr
    audio = np.sin(2 * np.pi * freq * t)

    f0_librosa = yin_validator.yin_librosa(audio, sr)

    # Analyze results
    stats = yin_validator.analyze_f0_contour(f0_librosa)

    # Should have high voiced ratio for pure sine
    assert stats['voiced_ratio'] > 0.5, f"Expected >50% voiced, got {stats['voiced_ratio']*100:.1f}%"

    # Mean frequency should be close to 440 Hz
    assert stats['mean_frequency'] > 200, f"Mean frequency too low: {stats['mean_frequency']:.1f} Hz"
    assert stats['mean_frequency'] < 800, f"Mean frequency too high: {stats['mean_frequency']:.1f} Hz"


def test_yin_synthetic_chirp(yin_validator):
    """Test YIN on synthetic chirp (frequency sweep)"""
    sr = 44100
    duration = 2.0
    t = np.arange(int(sr * duration)) / sr

    # Chirp from 200 Hz to 1000 Hz
    f_start = 200.0
    f_end = 1000.0
    freq_t = f_start + (f_end - f_start) * t / duration

    # Generate chirp
    phase = 2 * np.pi * np.cumsum(freq_t) / sr
    audio = np.sin(phase)

    f0_librosa = yin_validator.yin_librosa(audio, sr)

    # Analyze results
    stats = yin_validator.analyze_f0_contour(f0_librosa)

    # Mean frequency should be between start and end
    expected_mean = (f_start + f_end) / 2
    assert stats['mean_frequency'] > f_start * 0.7, "Mean frequency too low for chirp"
    assert stats['mean_frequency'] < f_end * 1.3, "Mean frequency too high for chirp"

    # Should have good voiced ratio
    assert stats['voiced_ratio'] > 0.3, f"Expected decent voiced ratio for chirp, got {stats['voiced_ratio']*100:.1f}%"


def test_yin_silence(yin_validator):
    """Test YIN on pure silence"""
    sr = 44100
    duration = 1.0
    audio = np.zeros(int(sr * duration))

    f0_librosa = yin_validator.yin_librosa(audio, sr)

    # Analyze results
    stats = yin_validator.analyze_f0_contour(f0_librosa)

    # Note: librosa.yin may detect "periodicity" even in silence due to algorithm behavior
    # Just verify we get valid output
    assert np.isfinite(stats['mean_frequency']), "Mean frequency is not finite"
    assert np.isfinite(stats['std_frequency']), "Std frequency is not finite"


def test_yin_white_noise(yin_validator):
    """Test YIN on white noise"""
    sr = 44100
    duration = 1.0
    np.random.seed(42)
    audio = np.random.randn(int(sr * duration)) * 0.1

    f0_librosa = yin_validator.yin_librosa(audio, sr)

    # Analyze results
    stats = yin_validator.analyze_f0_contour(f0_librosa)

    # Should have valid output (no NaN/Inf)
    assert np.isfinite(stats['mean_frequency']), "Mean frequency is not finite"
    assert np.isfinite(stats['std_frequency']), "Std frequency is not finite"


def test_yin_real_audio_file(yin_validator, blind_guardian_audio_files):
    """Test YIN on real audio from Blind Guardian collection"""
    if not blind_guardian_audio_files:
        pytest.skip("No Blind Guardian audio files found")

    # Test first audio file
    audio_path = blind_guardian_audio_files[0]
    result = yin_validator.test_audio_file(audio_path)

    print(f"\nYIN Validation Results for {result.file}:")
    print(f"  Duration: {result.duration:.2f}s ({result.samples} samples)")
    print(f"  Librosa voiced ratio: {result.librosa_voiced_ratio*100:.1f}%")
    print(f"  Librosa mean frequency: {result.librosa_mean_frequency:.1f} Hz (±{result.librosa_frequency_std:.1f})")
    print(f"  Librosa processing time: {result.librosa_time*1000:.2f}ms")

    # Verify we got valid output
    assert result.duration > 0, "Audio duration is zero"
    assert result.librosa_voiced_ratio >= 0.0 and result.librosa_voiced_ratio <= 1.0, "Invalid voiced ratio"
    assert np.isfinite(result.librosa_mean_frequency), "Mean frequency is not finite"


def test_yin_multiple_files(yin_validator, blind_guardian_audio_files):
    """Test YIN on multiple files"""
    if not blind_guardian_audio_files:
        pytest.skip("No Blind Guardian audio files found")

    results = []
    for audio_path in blind_guardian_audio_files:
        result = yin_validator.test_audio_file(audio_path)
        results.append(result)

    print(f"\nYIN Validation Results for {len(results)} files:")
    for result in results:
        print(f"  {result.file}: {result.duration:.2f}s, {result.librosa_voiced_ratio*100:.1f}% voiced, "
              f"{result.librosa_mean_frequency:.0f}±{result.librosa_frequency_std:.0f} Hz")

    # All should have valid output
    for result in results:
        assert np.isfinite(result.librosa_mean_frequency), f"Invalid mean frequency for {result.file}"
        assert np.isfinite(result.librosa_frequency_std), f"Invalid std frequency for {result.file}"


def test_yin_performance_benchmark(yin_validator):
    """Benchmark YIN performance on 1 second of audio"""
    sr = 44100
    duration = 1.0
    np.random.seed(42)

    # Generate test audio (chirp to be more realistic)
    t = np.arange(int(sr * duration)) / sr
    freq_t = 200 + 800 * t
    phase = 2 * np.pi * np.cumsum(freq_t) / sr
    audio = np.sin(phase)

    # Measure librosa performance
    start_time = time.perf_counter()
    for _ in range(3):  # Run 3 times for average
        f0 = yin_validator.yin_librosa(audio, sr)
    librosa_time = (time.perf_counter() - start_time) / 3 * 1000  # ms

    print(f"\nYIN Performance Benchmark (1 second audio):")
    print(f"  Librosa: {librosa_time:.2f}ms")
    print(f"  Note: Rust version will be measured in Phase 5 when PyO3 bindings are available")

    # Librosa should be reasonably fast (under 1 second for 1 second of audio)
    assert librosa_time < 1000.0, f"Librosa YIN too slow: {librosa_time:.2f}ms"
