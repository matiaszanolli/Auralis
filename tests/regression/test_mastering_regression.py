#!/usr/bin/env python3
"""
Mastering Regression Test Suite

Tests auto_master.py against known tracks to ensure processing consistency.
Each test case defines:
  - Input track path
  - Expected fingerprint ranges
  - Expected processing decisions
  - Output quality thresholds

Usage:
    python -m pytest tests/regression/test_mastering_regression.py -v
    python tests/regression/test_mastering_regression.py  # standalone
"""

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import librosa
import numpy as np
import pytest

from scipy.fft import rfft, rfftfreq

from auralis.core.simple_mastering import create_simple_mastering_pipeline


def measure_spectral_bands(audio: np.ndarray, sr: int) -> Dict[str, float]:
    """
    Measure energy in key spectral bands.

    Args:
        audio: Mono audio array
        sr: Sample rate

    Returns:
        Dict with band energies in dB
    """
    # Use middle 10 seconds for measurement
    mid = len(audio) // 2
    seg_len = min(sr * 10, len(audio) // 2)
    seg = audio[mid - seg_len // 2 : mid + seg_len // 2]

    fft = np.abs(rfft(seg))
    freqs = rfftfreq(len(seg), 1 / sr)

    bands = {
        'sub_bass': (20, 60),
        'bass': (60, 250),
        'low_mid': (250, 500),
        'mid': (500, 2000),
        'upper_mid': (2000, 4000),
        'presence': (4000, 6000),
        'air': (6000, 20000),
    }

    results = {}
    for name, (lo, hi) in bands.items():
        mask = (freqs >= lo) & (freqs < hi)
        energy = np.sum(fft[mask] ** 2)
        results[name] = 10 * np.log10(energy) if energy > 0 else -100

    return results


@dataclass
class TrackTestCase:
    """Definition of a regression test case."""
    name: str
    path: str
    # Expected fingerprint ranges (min, max)
    bass_pct_range: Tuple[float, float]
    lufs_range: Tuple[float, float]
    crest_db_range: Tuple[float, float]
    # Expected processing behavior
    expected_stage: str  # 'quiet_processing', 'compressed_loud', 'dynamic_loud'
    # Stereo width range (optional - for tracks testing stereo expansion)
    stereo_width_range: Optional[Tuple[float, float]] = None
    expects_stereo_expansion: bool = False  # True if track should get stereo_expand stage
    # Output quality thresholds
    max_peak_db: float = -0.1  # Should not clip
    min_crest_db: float = 6.0  # Should maintain some dynamics
    # Spectral preservation thresholds (max allowed loss in dB)
    max_air_loss_db: float = 6.0  # Air band (6-20kHz) - critical for brightness
    max_presence_loss_db: float = 4.0  # Presence band (2-6kHz) - critical for clarity


# Define test cases based on tracks we've tested
TEST_CASES = [
    TrackTestCase(
        name="Iron Maiden - Holy Smoke (moderate bass, loud)",
        path="/mnt/Musica/Musica/Iron Maiden/1990 - No Prayer For The Dying [FLAC 24-bit 44kHz]/02. Holy Smoke.flac",
        bass_pct_range=(0.30, 0.45),
        lufs_range=(-13.0, -10.0),
        crest_db_range=(9.0, 13.0),
        expected_stage="compressed_loud",
    ),
    TrackTestCase(
        name="Porcupine Tree - Phase I (extreme bass, quiet)",
        path="/mnt/Musica/Musica/Porcupine Tree/Voyage 34_ The Complete Trip [2000]/01. Phase I.flac",
        bass_pct_range=(0.50, 0.65),
        lufs_range=(-18.0, -14.0),
        crest_db_range=(15.0, 20.0),
        expected_stage="quiet_processing",
    ),
    TrackTestCase(
        name="Blind Guardian - Valhalla (moderate bass, dynamic)",
        path="/mnt/Musica/Musica/Blind Guardian/1989 - Follow The Blind/08 Valhalla.flac",
        bass_pct_range=(0.35, 0.55),
        lufs_range=(-21.0, -17.0),
        crest_db_range=(16.0, 20.0),
        expected_stage="quiet_processing",
    ),
    TrackTestCase(
        name="Blind Guardian - Somewhere Far Beyond (moderate bass, dynamic)",
        path="/mnt/Musica/Musica/Blind Guardian/1992 - Somewhere Far Beyond/10 Somewhere Far Beyond.flac",
        bass_pct_range=(0.35, 0.55),
        lufs_range=(-18.0, -14.0),
        crest_db_range=(13.0, 18.0),
        expected_stage="quiet_processing",
    ),
    # Stereo expansion test cases
    TrackTestCase(
        name="Rolling Stones - Rock and a Hard Place (narrow stereo, quiet)",
        path="/mnt/Musica/Musica/The Rolling Stones/1989b - Steel Wheels/07 - Rock and a Hard Place.mp3",
        bass_pct_range=(0.30, 0.45),
        lufs_range=(-19.0, -16.0),
        crest_db_range=(16.0, 20.0),
        expected_stage="quiet_processing",
        stereo_width_range=(0.10, 0.30),  # Narrow mix from 1989
        expects_stereo_expansion=True,
    ),
    TrackTestCase(
        name="Stratovarius - Eagleheart (narrow stereo, compressed loud, heavy bass)",
        path="/mnt/Musica/Musica/Stratovarius/Stratovarius - 2003 - Elements Pt. 1 (Limited - Remastered)/01 Eagleheart.flac",
        bass_pct_range=(0.40, 0.55),
        lufs_range=(-12.0, -9.0),
        crest_db_range=(10.0, 13.0),
        expected_stage="compressed_loud",
        stereo_width_range=(0.10, 0.25),  # Narrow metal mix
        expects_stereo_expansion=True,
        min_crest_db=8.0,  # Allow lower crest for already-compressed material
    ),
]


class MasteringRegressionTests:
    """Regression test runner for mastering pipeline."""

    def __init__(self):
        self.pipeline = create_simple_mastering_pipeline()
        self.results: Dict[str, dict] = {}

    def run_test(self, case: TrackTestCase) -> dict:
        """Run a single test case and return results."""
        result = {
            "name": case.name,
            "passed": True,
            "errors": [],
            "fingerprint": {},
            "processing": {},
        }

        # Check if file exists
        if not Path(case.path).exists():
            result["passed"] = False
            result["errors"].append(f"File not found: {case.path}")
            return result

        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                # Run mastering
                output = self.pipeline.master_file(
                    input_path=case.path,
                    output_path=tmp.name,
                    intensity=1.0,
                    verbose=False,
                )

                fp = output["fingerprint"]
                result["fingerprint"] = {
                    "bass_pct": fp.get("bass_pct", 0),
                    "lufs": fp.get("lufs", 0),
                    "crest_db": fp.get("crest_db", 0),
                    "stereo_width": fp.get("stereo_width", 0.5),
                    "tempo_bpm": fp.get("tempo_bpm", 0),
                }

                # Validate fingerprint ranges
                if not (case.bass_pct_range[0] <= fp["bass_pct"] <= case.bass_pct_range[1]):
                    result["errors"].append(
                        f"bass_pct {fp['bass_pct']:.2%} outside range "
                        f"[{case.bass_pct_range[0]:.0%}, {case.bass_pct_range[1]:.0%}]"
                    )

                if not (case.lufs_range[0] <= fp["lufs"] <= case.lufs_range[1]):
                    result["errors"].append(
                        f"LUFS {fp['lufs']:.1f} outside range "
                        f"[{case.lufs_range[0]:.1f}, {case.lufs_range[1]:.1f}]"
                    )

                if not (case.crest_db_range[0] <= fp["crest_db"] <= case.crest_db_range[1]):
                    result["errors"].append(
                        f"crest_db {fp['crest_db']:.1f} outside range "
                        f"[{case.crest_db_range[0]:.1f}, {case.crest_db_range[1]:.1f}]"
                    )

                # Validate stereo width range if specified
                if case.stereo_width_range is not None:
                    width = fp.get("stereo_width", 0.5)
                    if not (case.stereo_width_range[0] <= width <= case.stereo_width_range[1]):
                        result["errors"].append(
                            f"stereo_width {width:.0%} outside range "
                            f"[{case.stereo_width_range[0]:.0%}, {case.stereo_width_range[1]:.0%}]"
                        )

                # Validate processing stage
                stages = output["processing"]["stages"]
                stage_names = [s["stage"] for s in stages]
                result["processing"]["stages"] = stage_names

                if case.expected_stage == "quiet_processing":
                    if "soft_clip" not in stage_names:
                        result["errors"].append("Expected soft_clip stage for quiet material")
                elif case.expected_stage == "compressed_loud":
                    # Accept rms_expansion, skip_expansion, or legacy expansion stage
                    has_expansion_stage = any(s in stage_names for s in ["expansion", "rms_expansion", "skip_expansion"])
                    if not has_expansion_stage:
                        result["errors"].append("Expected expansion stage for compressed loud material")
                elif case.expected_stage == "dynamic_loud":
                    if "passthrough" not in stage_names:
                        result["errors"].append("Expected passthrough stage for dynamic loud material")

                # Validate stereo expansion if expected
                if case.expects_stereo_expansion:
                    if "stereo_expand" not in stage_names:
                        result["errors"].append("Expected stereo_expand stage for narrow mix")
                    else:
                        # Verify multiband expansion was used (check for width_factor in stage info)
                        stereo_stage = next((s for s in stages if s["stage"] == "stereo_expand"), None)
                        if stereo_stage:
                            result["processing"]["stereo_expansion"] = {
                                "original_width": stereo_stage.get("original_width"),
                                "width_factor": stereo_stage.get("width_factor"),
                            }

                # Validate output quality
                audio_out, sr = librosa.load(tmp.name, sr=None, mono=True)
                peak_db = 20 * np.log10(np.max(np.abs(audio_out)) + 1e-10)
                rms = np.sqrt(np.mean(audio_out ** 2))
                crest_out = 20 * np.log10(np.max(np.abs(audio_out)) / (rms + 1e-10))

                result["processing"]["output_peak_db"] = peak_db
                result["processing"]["output_crest_db"] = crest_out

                if peak_db > case.max_peak_db:
                    result["errors"].append(f"Output peak {peak_db:.1f} dB exceeds max {case.max_peak_db:.1f} dB")

                if crest_out < case.min_crest_db:
                    result["errors"].append(f"Output crest {crest_out:.1f} dB below min {case.min_crest_db:.1f} dB")

                # Spectral preservation validation
                # Load input for comparison (mono, same sample rate)
                audio_in, _ = librosa.load(case.path, sr=sr, mono=True)

                input_spectrum = measure_spectral_bands(audio_in, sr)
                output_spectrum = measure_spectral_bands(audio_out, sr)

                # Calculate and store spectral changes
                spectral_changes = {}
                for band in input_spectrum:
                    spectral_changes[band] = output_spectrum[band] - input_spectrum[band]

                result["processing"]["spectral_changes"] = spectral_changes

                # Validate air band preservation
                air_loss = -spectral_changes['air']  # Positive means loss
                if air_loss > case.max_air_loss_db:
                    result["errors"].append(
                        f"Air band loss {air_loss:.1f} dB exceeds max {case.max_air_loss_db:.1f} dB"
                    )

                # Validate presence band preservation
                presence_loss = -spectral_changes['presence']
                if presence_loss > case.max_presence_loss_db:
                    result["errors"].append(
                        f"Presence band loss {presence_loss:.1f} dB exceeds max {case.max_presence_loss_db:.1f} dB"
                    )

        except Exception as e:
            result["passed"] = False
            result["errors"].append(f"Exception: {str(e)}")

        result["passed"] = len(result["errors"]) == 0
        return result

    def run_all(self) -> Dict[str, dict]:
        """Run all test cases and return results."""
        print("\n" + "=" * 70)
        print("MASTERING REGRESSION TEST SUITE")
        print("=" * 70 + "\n")

        for case in TEST_CASES:
            print(f"Testing: {case.name}...")
            result = self.run_test(case)
            self.results[case.name] = result

            if result["passed"]:
                print(f"  ✓ PASSED")
                fp_info = (f"    Bass: {result['fingerprint'].get('bass_pct', 0):.0%}, "
                           f"LUFS: {result['fingerprint'].get('lufs', 0):.1f}, "
                           f"Crest: {result['fingerprint'].get('crest_db', 0):.1f}, "
                           f"Width: {result['fingerprint'].get('stereo_width', 0.5):.0%}")
                print(fp_info)
                # Show stereo expansion details if applied
                if "stereo_expansion" in result.get("processing", {}):
                    se = result["processing"]["stereo_expansion"]
                    expansion_pct = (se["width_factor"] - 0.5) * 200
                    print(f"    Stereo: {se['original_width']:.0%} → +{expansion_pct:.0f}% (multiband)")
                # Show spectral preservation
                if "spectral_changes" in result.get("processing", {}):
                    sc = result["processing"]["spectral_changes"]
                    print(f"    Spectral: Air {sc['air']:+.1f}dB, Presence {sc['presence']:+.1f}dB")
            else:
                print(f"  ✗ FAILED")
                for err in result["errors"]:
                    print(f"    - {err}")
            print()

        # Summary
        passed = sum(1 for r in self.results.values() if r["passed"])
        total = len(self.results)
        print("=" * 70)
        print(f"SUMMARY: {passed}/{total} tests passed")
        print("=" * 70)

        return self.results


# Pytest integration
@pytest.fixture
def regression_runner():
    return MasteringRegressionTests()


@pytest.mark.parametrize("case", TEST_CASES, ids=[c.name for c in TEST_CASES])
def test_mastering_regression(case: TrackTestCase, regression_runner):
    """Pytest-compatible regression test."""
    if not Path(case.path).exists():
        pytest.skip(f"Test file not found: {case.path}")

    result = regression_runner.run_test(case)
    assert result["passed"], f"Regression test failed: {result['errors']}"


if __name__ == "__main__":
    runner = MasteringRegressionTests()
    results = runner.run_all()
    
    # Exit with error code if any test failed
    failed = sum(1 for r in results.values() if not r["passed"])
    exit(failed)
