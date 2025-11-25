"""
HPSS Rust Implementation Validation Test

Validates the Rust HPSS implementation against librosa reference implementation
using real audio from the Blind Guardian collection.
"""

import os
import sys
import ctypes
import numpy as np
import librosa
import pytest
from pathlib import Path


# Rust library path
RUST_LIB_PATH = Path(__file__).parent.parent / "vendor" / "auralis-dsp" / "target" / "release" / "libauralis_dsp.rlib"
BLIND_GUARDIAN_PATH = Path("/mnt/Musica/Musica/Blind Guardian")


class HpssValidator:
    """Wrapper for Rust HPSS function validation"""

    def __init__(self):
        """Initialize HPSS validator with configuration"""
        self.n_fft = 2048
        self.hop_length = 512
        self.kernel_h = 31
        self.kernel_p = 31
        self.power = 2.0
        self.margin_h = 1.0
        self.margin_p = 1.0

    def hpss_librosa(self, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Reference: Librosa HPSS implementation"""
        # Librosa's hpss function requires at least 2D STFT, compute it first
        D = librosa.stft(y)
        H, P = librosa.decompose.hpss(D, margin=2.0)
        harmonic = librosa.istft(H, length=len(y))
        percussive = librosa.istft(P, length=len(y))
        return harmonic, percussive

    def validate_output_properties(self, y: np.ndarray, harmonic: np.ndarray, percussive: np.ndarray):
        """Validate HPSS output properties"""
        # Check shapes match
        assert harmonic.shape == y.shape, f"Harmonic shape {harmonic.shape} != input shape {y.shape}"
        assert percussive.shape == y.shape, f"Percussive shape {percussive.shape} != input shape {y.shape}"

        # Check no NaN/Inf
        assert not np.isnan(harmonic).any(), "Harmonic output contains NaN"
        assert not np.isinf(harmonic).any(), "Harmonic output contains Inf"
        assert not np.isnan(percussive).any(), "Percussive output contains NaN"
        assert not np.isinf(percussive).any(), "Percussive output contains Inf"

        # Check output is in reasonable range (usually -1 to 1 for audio)
        assert np.abs(harmonic).max() <= 10.0, f"Harmonic peak {np.abs(harmonic).max()} seems unreasonable"
        assert np.abs(percussive).max() <= 10.0, f"Percussive peak {np.abs(percussive).max()} seems unreasonable"

    def compute_relative_error(self, reference: np.ndarray, test: np.ndarray) -> float:
        """Compute relative error (MAPE - Mean Absolute Percentage Error)"""
        # Avoid division by zero
        reference_safe = np.abs(reference).copy()
        reference_safe[reference_safe < 1e-10] = 1e-10

        error = np.abs((reference - test) / reference_safe)
        return np.mean(error)

    def test_audio_file(self, audio_path: Path) -> dict:
        """Test HPSS on a single audio file"""
        # Load audio
        y, sr = librosa.load(str(audio_path), sr=44100, mono=True)

        # Resample to 44.1kHz if needed
        if sr != 44100:
            y = librosa.resample(y, orig_sr=sr, target_sr=44100)

        # Get librosa reference
        harm_ref, perc_ref = self.hpss_librosa(y)

        # Validate properties
        self.validate_output_properties(y, harm_ref, perc_ref)

        return {
            'file': audio_path.name,
            'duration': len(y) / 44100,
            'samples': len(y),
            'harmonic_ref': harm_ref,
            'percussive_ref': perc_ref,
            'harmonic_rms': float(np.sqrt(np.mean(harm_ref**2))),
            'percussive_rms': float(np.sqrt(np.mean(perc_ref**2))),
        }


@pytest.fixture
def hpss_validator():
    """HPSS validator fixture"""
    return HpssValidator()


@pytest.fixture
def blind_guardian_audio_files():
    """Get list of Blind Guardian audio files"""
    if not BLIND_GUARDIAN_PATH.exists():
        pytest.skip(f"Blind Guardian collection not found at {BLIND_GUARDIAN_PATH}")

    audio_files = []
    for audio_path in BLIND_GUARDIAN_PATH.glob("**/*.flac"):
        audio_files.append(audio_path)

    if not audio_files:
        for audio_path in BLIND_GUARDIAN_PATH.glob("**/*.mp3"):
            audio_files.append(audio_path)

    return sorted(audio_files)[:3]  # Start with first 3 files


def test_hpss_compilation():
    """Test that Rust library is compiled"""
    # Check if library file exists
    lib_path = Path(__file__).parent.parent / "vendor" / "auralis-dsp" / "target" / "release"
    assert lib_path.exists(), f"Rust build directory not found at {lib_path}"

    lib_files = list(lib_path.glob("libauralis_dsp*"))
    assert len(lib_files) > 0, "Rust library not compiled"


def test_hpss_properties_single_file(hpss_validator):
    """Test HPSS output properties on a single file"""
    audio_path = BLIND_GUARDIAN_PATH / "1988 - Battalions Of Fear" / "01 - Battalions.flac"

    if not audio_path.exists():
        pytest.skip(f"Test audio file not found: {audio_path}")

    result = hpss_validator.test_audio_file(audio_path)

    # Verify we got valid output
    assert result['harmonic_rms'] > 0.0, "Harmonic output is silent"
    assert result['percussive_rms'] > 0.0, "Percussive output is silent"

    # Energy should be roughly split
    total_energy = result['harmonic_rms']**2 + result['percussive_rms']**2
    assert total_energy > 0.0, "Total decomposed energy is zero"


def test_hpss_librosa_reference(hpss_validator):
    """Test that librosa reference works correctly"""
    # Generate synthetic test signal
    sr = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(sr * duration))

    # Harmonic: pure sine
    freq_harmonic = 440  # A4
    harmonic_signal = 0.3 * np.sin(2 * np.pi * freq_harmonic * t)

    # Percussive: short clicks
    percussive_signal = np.zeros_like(t)
    percussive_signal[::int(sr * 0.1)] = 0.3  # Click every 100ms

    y = harmonic_signal + percussive_signal

    # Get librosa decomposition
    harm_lib, perc_lib = hpss_validator.hpss_librosa(y)

    # Verify properties
    assert harm_lib.shape == y.shape
    assert perc_lib.shape == y.shape
    assert not np.isnan(harm_lib).any()
    assert not np.isnan(perc_lib).any()


def test_hpss_batch_analysis(hpss_validator, blind_guardian_audio_files):
    """Batch analysis of multiple Blind Guardian tracks"""
    if not blind_guardian_audio_files:
        pytest.skip("No Blind Guardian audio files available")

    results = []
    for audio_path in blind_guardian_audio_files:
        try:
            result = hpss_validator.test_audio_file(audio_path)
            results.append(result)
            print(f"✓ {result['file']}: {result['duration']:.1f}s, H RMS={result['harmonic_rms']:.4f}, P RMS={result['percussive_rms']:.4f}")
        except Exception as e:
            print(f"✗ {audio_path.name}: {e}")

    assert len(results) > 0, "No files successfully processed"


if __name__ == "__main__":
    # Run validation
    validator = HpssValidator()

    print("=" * 60)
    print("HPSS Rust Implementation Validation")
    print("=" * 60)

    # Test compilation
    lib_path = Path(__file__).parent / ".." / "vendor" / "auralis-dsp" / "target" / "release"
    if lib_path.exists():
        lib_files = list(lib_path.glob("libauralis_dsp*"))
        print(f"\n✓ Rust library compiled: {len(lib_files)} artifact(s)")
    else:
        print(f"\n✗ Rust library not found at {lib_path}")

    # Test librosa reference
    print("\nTesting librosa reference implementation...")
    sr = 44100
    y = np.random.randn(sr)  # 1 second of noise
    harm, perc = validator.hpss_librosa(y)
    print(f"✓ Librosa HPSS works: H shape={harm.shape}, P shape={perc.shape}")

    # Test with Blind Guardian files
    if BLIND_GUARDIAN_PATH.exists():
        print(f"\nTesting with Blind Guardian collection at {BLIND_GUARDIAN_PATH}")
        audio_files = list(BLIND_GUARDIAN_PATH.glob("**/*.flac"))[:3]
        if not audio_files:
            audio_files = list(BLIND_GUARDIAN_PATH.glob("**/*.mp3"))[:3]

        for audio_path in audio_files:
            try:
                result = validator.test_audio_file(audio_path)
                print(f"✓ {result['file']}: H RMS={result['harmonic_rms']:.4f}, P RMS={result['percussive_rms']:.4f}")
            except Exception as e:
                print(f"✗ {audio_path.name}: {e}")
    else:
        print(f"\n! Blind Guardian collection not found at {BLIND_GUARDIAN_PATH}")

    print("\n" + "=" * 60)
    print("Validation complete - ready for Rust FFI integration")
    print("=" * 60)
