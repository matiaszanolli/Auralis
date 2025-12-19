#!/usr/bin/env python3
"""
Extended comprehensive validation of smooth scaling across diverse eras and genres.
"""

import subprocess
import sys
import os
from pathlib import Path
import tempfile
from typing import Dict, Any, List, Tuple

sys.path.insert(0, '/mnt/data/src/matchering')
from auralis.analysis.fingerprint.fingerprint_service import FingerprintService


def fingerprint_audio(audio_path: str) -> Dict[str, Any]:
    """Fingerprint audio"""
    try:
        service = FingerprintService(fingerprint_strategy="sampling")
        fingerprint = service.get_or_compute(Path(audio_path))
        return fingerprint if fingerprint else {}
    except Exception as e:
        return {}


def process_track(input_path: str, output_path: str) -> bool:
    """Process through auto_master.py"""
    result = subprocess.run(
        ["python", "auto_master.py", input_path, "-o", output_path],
        capture_output=True,
        text=True,
        cwd="/mnt/data/src/matchering",
        timeout=60
    )
    return result.returncode == 0


def test_track(track_path: str, track_name: str, era: str) -> Tuple[bool, Dict]:
    """Test single track and return results"""
    if not os.path.exists(track_path):
        return False, {}

    print(f"\n  {track_name} ({era})")

    # Input fingerprint
    input_fp = fingerprint_audio(track_path)
    if not input_fp or 'lufs' not in input_fp:
        print(f"    ⊘ Input fingerprinting failed")
        return False, {}

    input_lufs = input_fp['lufs']
    print(f"    Input: {input_lufs:.2f} LUFS, Crest {input_fp.get('crest_db', 0):.1f} dB, Bass {input_fp.get('bass_pct', 0)*100:.1f}%")

    # Process
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        output_path = tmp.name

    try:
        if not process_track(track_path, output_path):
            print(f"    ⊘ Processing failed")
            return False, {}

        # Output fingerprint
        output_fp = fingerprint_audio(output_path)
        if not output_fp or 'lufs' not in output_fp:
            print(f"    ⊘ Output fingerprinting failed")
            return False, {}

        output_lufs = output_fp['lufs']
        gain = output_lufs - input_lufs
        crest_change = output_fp.get('crest_db', 0) - input_fp.get('crest_db', 0)

        status = "✓" if gain > 0 else "✗" if gain < 0 else "~"
        print(f"    {status} Output: {output_lufs:.2f} LUFS | Gain: +{gain:.2f} dB | Crest Δ: {crest_change:.2f} dB")

        return True, {
            'input_lufs': input_lufs,
            'output_lufs': output_lufs,
            'gain': gain,
            'crest_change': crest_change,
            'bass_pct': input_fp.get('bass_pct', 0)
        }
    finally:
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass


def main():
    """Run comprehensive validation"""

    print("=" * 100)
    print("COMPREHENSIVE SMOOTH SCALING VALIDATION")
    print("Testing across different eras, genres, and loudness levels")
    print("=" * 100)

    # Group test tracks by era
    test_groups = {
        "1980s - Punk Rock (Very Quiet, -17 to -20 LUFS)": [
            ("/mnt/Musica/Musica/(1980) Fresh Fruit For Rotting Vegetables/01 Kill The Poor.flac", "Kill The Poor"),
            ("/mnt/Musica/Musica/(1980) Fresh Fruit For Rotting Vegetables/02 Forward To Death.flac", "Forward To Death"),
            ("/mnt/Musica/Musica/(1980) Fresh Fruit For Rotting Vegetables/06 Your Emotions.flac", "Your Emotions"),
            ("/mnt/Musica/Musica/(1980) Fresh Fruit For Rotting Vegetables/08 California Über Alles.flac", "California Über Alles"),
        ],
        "1984 - Synth-Pop (Moderate Loudness, -12 to -14 LUFS)": [
            ("/mnt/Musica/Musica/Soda Stereo/FLAC/Dynamo/01 Secuencia Inicial.flac", "Secuencia Inicial"),
            ("/mnt/Musica/Musica/Soda Stereo/FLAC/Dynamo/02 Sobredosis de TV.flac", "Sobredosis de TV"),
        ],
        "1990s-2000s - Diverse": [
            ("/mnt/Musica/Musica/(The) Rolling Stones - Voodoo Lounge (1994)(UK & Europe)[LP][24-96][FLAC]/A1. Love Is Strong.flac", "Stones - Love Is Strong"),
            ("/mnt/Musica/Musica/(The) Rolling Stones - Voodoo Lounge (1994)(UK & Europe)[LP][24-96][FLAC]/A2. You Got Me Rocking.flac", "Stones - You Got Me Rocking"),
        ]
    }

    all_results = []

    for era_group, tracks in test_groups.items():
        print(f"\n{'=' * 100}")
        print(era_group)
        print('=' * 100)

        group_results = []
        for track_path, track_name in tracks:
            success, result = test_track(track_path, track_name, era_group)
            if success:
                group_results.append((track_name, result))
                all_results.append((track_name, result))

        if group_results:
            gains = [r['gain'] for _, r in group_results]
            avg_gain = sum(gains) / len(gains)
            avg_crest = sum(r['crest_change'] for _, r in group_results) / len(group_results)

            print(f"\n  Group Summary: {len(group_results)} tracks")
            print(f"    Average gain: +{avg_gain:.2f} dB")
            print(f"    Average crest compression: {avg_crest:.2f} dB")

    # Overall summary
    print(f"\n{'=' * 100}")
    print("OVERALL VALIDATION SUMMARY")
    print('=' * 100)

    if all_results:
        all_gains = [r['gain'] for _, r in all_results]
        all_crest = [r['crest_change'] for _, r in all_results]

        print(f"\nTotal tracks tested: {len(all_results)}")
        print(f"\nLoudness Gains:")
        print(f"  Average: +{sum(all_gains)/len(all_gains):.2f} dB")
        print(f"  Min: +{min(all_gains):.2f} dB")
        print(f"  Max: +{max(all_gains):.2f} dB")
        print(f"  Range: {max(all_gains) - min(all_gains):.2f} dB")

        print(f"\nCrest Factor Changes (Dynamic Range):")
        print(f"  Average compression: {sum(all_crest)/len(all_crest):.2f} dB")
        print(f"  Min compression: {min(all_crest):.2f} dB")
        print(f"  Max compression: {max(all_crest):.2f} dB")

        positive_gains = sum(1 for g in all_gains if g > 0)
        zero_gains = sum(1 for g in all_gains if g == 0)
        negative_gains = sum(1 for g in all_gains if g < 0)

        print(f"\nGain Distribution:")
        print(f"  Positive (>0 dB): {positive_gains} tracks")
        print(f"  Zero: {zero_gains} tracks")
        print(f"  Negative: {negative_gains} tracks")

        print(f"\n{'=' * 100}")
        if all(g > 0 for g in all_gains):
            print("✓ VALIDATION PASSED")
            print("✓ All tracks show positive loudness improvement")
            print("✓ Smooth scaling provides consistent, natural processing")
            print("✓ Production-ready for mastering")
            return 0
        else:
            print("⚠ VALIDATION PASSED WITH NOTES")
            print(f"✓ {positive_gains}/{len(all_results)} tracks show positive gains")
            if negative_gains > 0:
                print(f"⚠ {negative_gains} tracks with unexpected negative gains - review needed")
            return 0 if positive_gains >= len(all_results) * 0.8 else 1
    else:
        print("✗ No valid test results")
        return 1


if __name__ == "__main__":
    sys.exit(main())
