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

from auralis.core.simple_mastering import create_simple_mastering_pipeline


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
    # Output quality thresholds
    max_peak_db: float = -0.1  # Should not clip
    min_crest_db: float = 6.0  # Should maintain some dynamics


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

                # Validate processing stage
                stages = output["processing"]["stages"]
                stage_names = [s["stage"] for s in stages]
                result["processing"]["stages"] = stage_names

                if case.expected_stage == "quiet_processing":
                    if "soft_clip" not in stage_names:
                        result["errors"].append("Expected soft_clip stage for quiet material")
                elif case.expected_stage == "compressed_loud":
                    if "expansion" not in stage_names:
                        result["errors"].append("Expected expansion stage for compressed loud material")
                elif case.expected_stage == "dynamic_loud":
                    if "passthrough" not in stage_names:
                        result["errors"].append("Expected passthrough stage for dynamic loud material")

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
                print(f"    Bass: {result['fingerprint'].get('bass_pct', 0):.0%}, "
                      f"LUFS: {result['fingerprint'].get('lufs', 0):.1f}, "
                      f"Crest: {result['fingerprint'].get('crest_db', 0):.1f}")
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
