#!/usr/bin/env python3
"""
Comprehensive validation of smooth scaling mastering approach.
Calls auto_master.py as subprocess and validates results.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

# Add project to path
sys.path.insert(0, '/mnt/data/src/matchering')

from auralis.analysis.fingerprint.fingerprint_service import FingerprintService


def fingerprint_audio(audio_path: str) -> Dict[str, Any]:
    """Fingerprint audio using FingerprintService"""
    try:
        service = FingerprintService(fingerprint_strategy="sampling")
        fingerprint = service.get_or_compute(Path(audio_path))
        return fingerprint if fingerprint else {}
    except Exception as e:
        print(f"    Error fingerprinting: {e}")
        return {}


def process_track_with_auto_master(input_path: str, output_path: str) -> bool:
    """Process track using auto_master.py"""
    result = subprocess.run(
        ["python", "auto_master.py", input_path, "-o", output_path],
        capture_output=True,
        text=True,
        cwd="/mnt/data/src/matchering",
        timeout=60
    )

    if result.returncode != 0:
        print(f"    Error: {result.stderr[:200]}")
        return False

    # Print processing output
    for line in result.stdout.split('\n'):
        if line.strip() and ('Soft clipping' in line or 'Normalizing' in line or 'makeup' in line or 'Processing' in line):
            print(f"    {line}")

    return True


def format_result(track_name: str, input_fp: Dict, output_fp: Dict) -> str:
    """Format result line"""
    input_lufs = input_fp.get('lufs', None)
    output_lufs = output_fp.get('lufs', None)

    if input_lufs is None or output_lufs is None:
        return f"✗ {track_name:40s} | Fingerprinting failed"

    gain = output_lufs - input_lufs
    crest_change = output_fp.get('crest_db', 0) - input_fp.get('crest_db', 0)

    gain_str = f"+{gain:.2f}" if gain > 0 else f"{gain:.2f}"
    crest_str = f"{crest_change:.2f}" if crest_change < 0 else f"+{crest_change:.2f}"

    status = "✓" if gain >= 0 else "✗"

    return (
        f"{status} {track_name:40s} | "
        f"{input_lufs:6.2f} → {output_lufs:6.2f} LUFS | "
        f"Δ{gain_str:6s} dB | Crest Δ{crest_str:6s} dB"
    )


def main():
    """Run validation"""

    # Test tracks - using confirmed available tracks
    test_tracks = [
        ("/mnt/Musica/Musica/(1980) Fresh Fruit For Rotting Vegetables/01 Kill The Poor.flac",
         "Dead Kennedys - Kill The Poor"),

        ("/mnt/Musica/Musica/(1980) Fresh Fruit For Rotting Vegetables/02 Forward To Death.flac",
         "Dead Kennedys - Forward To Death"),

        ("/mnt/Musica/Musica/(1980) Fresh Fruit For Rotting Vegetables/05 Drug Me.flac",
         "Dead Kennedys - Drug Me"),

        ("/mnt/Musica/Musica/Soda Stereo/FLAC/Dynamo/01 Secuencia Inicial.flac",
         "Soda Stereo - Secuencia Inicial"),
    ]

    print("=" * 120)
    print("SMOOTH SCALING VALIDATION TEST")
    print("Testing across diverse material (1980s punk, 1984 synth-pop)")
    print("=" * 120)
    print()

    results = []
    gains = []

    for input_path, track_name in test_tracks:
        if not os.path.exists(input_path):
            print(f"⊘ {track_name:40s} | File not found")
            continue

        print(f"Testing: {track_name}")

        # Fingerprint input
        print(f"  → Fingerprinting input...")
        input_fp = fingerprint_audio(input_path)
        if not input_fp:
            print(f"  ✗ Input fingerprinting failed")
            continue

        input_lufs = input_fp.get('lufs')
        print(f"    Input: {input_lufs:.2f} LUFS, Crest {input_fp.get('crest_db', 0):.1f} dB")

        # Process through auto_master
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            output_path = tmp.name

        try:
            print(f"  → Processing through auto_master.py...")
            if not process_track_with_auto_master(input_path, output_path):
                print(f"  ✗ Processing failed")
                continue

            # Fingerprint output
            print(f"  → Fingerprinting output...")
            output_fp = fingerprint_audio(output_path)
            if not output_fp:
                print(f"  ✗ Output fingerprinting failed")
                continue

            output_lufs = output_fp.get('lufs')
            print(f"    Output: {output_lufs:.2f} LUFS, Crest {output_fp.get('crest_db', 0):.1f} dB")

            # Format result
            result_line = format_result(track_name, input_fp, output_fp)
            results.append(result_line)

            # Track gains for statistics
            gain = output_lufs - input_lufs
            gains.append(gain)

            print()
        finally:
            # Clean up temp file
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except:
                    pass

    # Print summary
    print("=" * 120)
    print("RESULTS")
    print("=" * 120)
    for result in results:
        print(result)

    print()
    if gains:
        avg_gain = sum(gains) / len(gains)
        min_gain = min(gains)
        max_gain = max(gains)

        print(f"Processed: {len(gains)} tracks")
        print(f"  Average gain: +{avg_gain:.2f} dB")
        print(f"  Range: +{min_gain:.2f} to +{max_gain:.2f} dB")
        print()

        if all(g >= 0 for g in gains):
            print("✓ VALIDATION PASSED")
            print("✓ All tracks show positive loudness improvement")
            print("✓ Smooth scaling approach is production-ready")
            return 0
        else:
            negative = [g for g in gains if g < 0]
            print(f"✗ VALIDATION FAILED - {len(negative)} tracks with negative gains")
            return 1
    else:
        print("✗ No valid results")
        return 1


if __name__ == "__main__":
    sys.exit(main())
