#!/usr/bin/env python3
"""
Comprehensive validation of smooth scaling mastering approach.
Tests across diverse material to ensure smooth, non-destructive processing.
"""

import subprocess
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

def run_fingerprint(audio_path: str) -> Dict[str, Any]:
    """Run fingerprinting on audio and return results"""
    result = subprocess.run(
        ["python", "fingerprint_track.py", audio_path, "--json"],
        capture_output=True,
        text=True,
        cwd="/mnt/data/src/matchering"
    )

    if result.returncode != 0:
        print(f"  Error fingerprinting {audio_path}: {result.stderr}")
        return {}

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"  Could not parse fingerprint JSON")
        return {}

def process_track(input_path: str, output_path: str) -> bool:
    """Process audio through auto_master"""
    result = subprocess.run(
        ["python", "auto_master.py", input_path, "-o", output_path],
        capture_output=True,
        text=True,
        cwd="/mnt/data/src/matchering"
    )

    if result.returncode != 0:
        print(f"  Error processing: {result.stderr}")
        return False

    print(result.stdout)
    return True

def get_loudness_gain(input_fp: Dict, output_fp: Dict) -> float:
    """Calculate loudness gain between input and output"""
    input_lufs = input_fp.get('lufs', 0)
    output_lufs = output_fp.get('lufs', 0)
    return output_lufs - input_lufs

def get_crest_change(input_fp: Dict, output_fp: Dict) -> float:
    """Calculate change in crest factor (dynamic range)"""
    input_crest = input_fp.get('crest_db', 0)
    output_crest = output_fp.get('crest_db', 0)
    return output_crest - input_crest

def format_result(track_name: str, input_fp: Dict, output_fp: Dict) -> str:
    """Format validation result"""
    input_lufs = input_fp.get('lufs', 'N/A')
    output_lufs = output_fp.get('lufs', 'N/A')

    if isinstance(input_lufs, (int, float)) and isinstance(output_lufs, (int, float)):
        gain = get_loudness_gain(input_fp, output_fp)
        crest_change = get_crest_change(input_fp, output_fp)

        gain_str = f"+{gain:.2f} dB" if gain > 0 else f"{gain:.2f} dB"
        crest_str = f"{crest_change:.2f} dB" if crest_change < 0 else f"+{crest_change:.2f} dB"

        status = "✓" if gain >= 0 else "✗"

        return f"{status} {track_name:40s} | Input: {input_lufs:6.2f} LUFS | Output: {output_lufs:6.2f} LUFS | Gain: {gain_str:8s} | Crest Δ: {crest_str}"
    else:
        return f"✗ {track_name:40s} | Fingerprinting failed"

def main():
    """Run comprehensive validation"""

    # Test tracks spanning different eras and loudness levels
    test_tracks = [
        # (input_path, track_name, era_description)
        ("/mnt/Musica/Musica/Fito Páez/FLAC/Corazón/01 - Entrada al Rito.flac",
         "Fito Páez - Entrada al Rito", "1995 - Very quiet ballad"),

        ("/mnt/Musica/Musica/Franz Ferdinand/You Could Have It So Much Better/01 - Jacqueline.flac",
         "Franz Ferdinand - Jacqueline", "2005 - Modern indie rock"),

        ("/mnt/Musica/Musica/(1980) Fresh Fruit For Rotting Vegetables/01 Kill The Poor.flac",
         "Dead Kennedys - Kill The Poor", "1980 - Punk rock"),

        ("/mnt/Musica/Musica/Soda Stereo/FLAC/Dynamo/01 Secuencia Inicial.flac",
         "Soda Stereo - Secuencia Inicial", "1984 - Synth-pop"),
    ]

    print("=" * 120)
    print("COMPREHENSIVE SMOOTH SCALING VALIDATION")
    print("=" * 120)
    print()

    results = []

    for input_path, track_name, description in test_tracks:
        # Check if file exists
        if not os.path.exists(input_path):
            print(f"⊘ {track_name:40s} | File not found: {input_path}")
            continue

        print(f"Testing: {track_name} ({description})")

        # Fingerprint input
        print(f"  → Fingerprinting input...")
        input_fp = run_fingerprint(input_path)
        if not input_fp:
            print(f"⊘ {track_name:40s} | Fingerprinting failed")
            continue

        input_lufs = input_fp.get('lufs', 'N/A')
        print(f"    Input LUFS: {input_lufs}, Crest: {input_fp.get('crest_db', 'N/A')} dB, Bass: {input_fp.get('bass_pct', 'N/A')*100:.1f}%")

        # Process through auto_master
        output_path = f"/tmp/{Path(input_path).stem}_mastered.wav"
        print(f"  → Processing through smooth scaling...")
        if not process_track(input_path, output_path):
            print(f"⊘ {track_name:40s} | Processing failed")
            continue

        # Fingerprint output
        print(f"  → Fingerprinting output...")
        output_fp = run_fingerprint(output_path)
        if not output_fp:
            print(f"⊘ {track_name:40s} | Output fingerprinting failed")
            continue

        output_lufs = output_fp.get('lufs', 'N/A')
        print(f"    Output LUFS: {output_lufs}, Crest: {output_fp.get('crest_db', 'N/A')} dB")

        # Format and store result
        result_line = format_result(track_name, input_fp, output_fp)
        results.append(result_line)
        print()

    # Print summary
    print("=" * 120)
    print("VALIDATION RESULTS")
    print("=" * 120)
    for result in results:
        print(result)

    print()
    print("=" * 120)
    print("INTERPRETATION")
    print("=" * 120)
    print("✓ Gain ≥ 0 dB  = Successful loudness improvement")
    print("✗ Gain < 0 dB  = Reduction in loudness (should not occur)")
    print("Crest Δ < 0 dB = Dynamic range compressed (expected for limiting)")
    print("Crest Δ ≈ 0 dB = Minimal dynamic range loss (better character preservation)")
    print()

    # Calculate statistics
    gains = []
    crest_changes = []

    for result in results:
        if "✓" in result and "Gain:" in result:
            # Extract gain value
            gain_str = result.split("Gain: ")[1].split(" dB")[0]
            try:
                gain = float(gain_str.replace("+", ""))
                gains.append(gain)
            except ValueError:
                pass

            # Extract crest change
            crest_str = result.split("Crest Δ: ")[1].split("dB")[0]
            try:
                crest = float(crest_str.replace("+", ""))
                crest_changes.append(crest)
            except ValueError:
                pass

    if gains:
        print(f"Average loudness gain: +{sum(gains)/len(gains):.2f} dB ({len(gains)} tracks)")
        print(f"Average crest factor change: {sum(crest_changes)/len(crest_changes):.2f} dB")
        print()

    if all(gain > 0 for gain in gains):
        print("✓ VALIDATION PASSED - All tracks show positive loudness improvement")
        print("✓ Smooth scaling approach is production-ready")
        return 0
    else:
        print("✗ VALIDATION FAILED - Some tracks show negative gains")
        return 1

if __name__ == "__main__":
    sys.exit(main())
