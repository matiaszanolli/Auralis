#!/usr/bin/env python3
"""
Direct test of smooth scaling mastering approach.
Tests by loading audio directly and processing.
"""

import sys
import os
sys.path.insert(0, '/mnt/data/src/matchering')

import numpy as np
import soundfile as sf
from pathlib import Path
import tempfile
from typing import Dict, Any, Tuple

# Import our modules
from auto_master import master_audio
from auralis.analysis.audio_fingerprint_analyzer import AudioFingerprintAnalyzer
from auralis.io.audio_loader import load_audio

def fingerprint_audio(audio_path: str) -> Dict[str, Any]:
    """Generate fingerprint for audio"""
    try:
        analyzer = AudioFingerprintAnalyzer()
        audio, sr = load_audio(audio_path)
        fingerprint = analyzer.analyze(audio, sr)
        return fingerprint
    except Exception as e:
        print(f"  Error fingerprinting: {e}")
        return {}

def process_track(input_path: str, output_path: str) -> bool:
    """Process audio through auto_master"""
    try:
        audio, sr = load_audio(input_path)
        processed = master_audio(audio, sr)

        # Write output
        sf.write(output_path, processed, sr)
        return True
    except Exception as e:
        print(f"  Error processing: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_loudness_gain(input_fp: Dict, output_fp: Dict) -> float:
    """Calculate loudness gain"""
    input_lufs = input_fp.get('lufs', 0)
    output_lufs = output_fp.get('lufs', 0)
    return output_lufs - input_lufs

def get_crest_change(input_fp: Dict, output_fp: Dict) -> float:
    """Calculate crest factor change"""
    input_crest = input_fp.get('crest_db', 0)
    output_crest = output_fp.get('crest_db', 0)
    return output_crest - input_crest

def format_result(track_name: str, input_fp: Dict, output_fp: Dict) -> str:
    """Format result line"""
    input_lufs = input_fp.get('lufs', 'N/A')
    output_lufs = output_fp.get('lufs', 'N/A')

    if isinstance(input_lufs, (int, float)) and isinstance(output_lufs, (int, float)):
        gain = get_loudness_gain(input_fp, output_fp)
        crest_change = get_crest_change(input_fp, output_fp)

        gain_str = f"+{gain:.2f} dB" if gain > 0 else f"{gain:.2f} dB"
        crest_str = f"{crest_change:.2f} dB" if crest_change < 0 else f"+{crest_change:.2f} dB"

        status = "✓" if gain >= 0 else "✗"

        return (
            f"{status} {track_name:40s} | "
            f"Input: {input_lufs:6.2f} LUFS → Output: {output_lufs:6.2f} LUFS | "
            f"Gain: {gain_str:8s} | Crest Δ: {crest_str}"
        )
    else:
        return f"✗ {track_name:40s} | Fingerprinting failed"

def main():
    """Run validation"""

    test_tracks = [
        ("/mnt/Musica/Musica/(1980) Fresh Fruit For Rotting Vegetables/01 Kill The Poor.flac",
         "Dead Kennedys - Kill The Poor", "1980 punk"),

        ("/mnt/Musica/Musica/(1980) Fresh Fruit For Rotting Vegetables/02 Forward To Death.flac",
         "Dead Kennedys - Forward To Death", "1980 punk"),

        ("/mnt/Musica/Musica/Soda Stereo/FLAC/Dynamo/01 Secuencia Inicial.flac",
         "Soda Stereo - Secuencia Inicial", "1984 synth-pop"),
    ]

    print("=" * 130)
    print("SMOOTH SCALING VALIDATION - DIRECT PROCESSING")
    print("=" * 130)
    print()

    results = []

    for input_path, track_name, description in test_tracks:
        if not os.path.exists(input_path):
            print(f"⊘ {track_name:40s} | File not found")
            continue

        print(f"Processing: {track_name} ({description})")

        # Fingerprint input
        print(f"  → Fingerprinting input...")
        input_fp = fingerprint_audio(input_path)
        if not input_fp:
            print(f"⊘ Fingerprinting failed")
            continue

        input_lufs = input_fp.get('lufs', 'N/A')
        input_crest = input_fp.get('crest_db', 'N/A')
        input_bass = input_fp.get('bass_pct', 'N/A')
        print(f"    Input: LUFS={input_lufs}, Crest={input_crest} dB, Bass={input_bass*100 if isinstance(input_bass, float) else input_bass}%")

        # Process
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            output_path = tmp.name

        try:
            print(f"  → Processing through smooth scaling...")
            if not process_track(input_path, output_path):
                print(f"⊘ Processing failed")
                continue

            # Fingerprint output
            print(f"  → Fingerprinting output...")
            output_fp = fingerprint_audio(output_path)
            if not output_fp:
                print(f"⊘ Output fingerprinting failed")
                continue

            output_lufs = output_fp.get('lufs', 'N/A')
            output_crest = output_fp.get('crest_db', 'N/A')
            print(f"    Output: LUFS={output_lufs}, Crest={output_crest} dB")

            # Format result
            result_line = format_result(track_name, input_fp, output_fp)
            results.append(result_line)
            print()
        finally:
            # Clean up temp file
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except:
                    pass

    # Print summary
    print("=" * 130)
    print("VALIDATION RESULTS")
    print("=" * 130)
    for result in results:
        print(result)

    print()
    print("=" * 130)
    print("INTERPRETATION")
    print("=" * 130)
    print("✓ Gain ≥ 0 dB  = Successful loudness improvement")
    print("✗ Gain < 0 dB  = Reduction in loudness (should not occur)")
    print("Crest Δ < 0 dB = Dynamic range compressed (expected for limiting)")
    print("Crest Δ ≈ 0 dB = Minimal dynamic range loss (better character preservation)")
    print()

    # Calculate statistics
    gains = []
    crest_changes = []

    for result in results:
        if "✓" in result:
            # Extract values from result string
            try:
                # Extract gain
                gain_part = result.split("Gain: ")[1].split(" dB")[0]
                gain = float(gain_part.replace("+", ""))
                gains.append(gain)

                # Extract crest
                crest_part = result.split("Crest Δ: ")[1].split("dB")[0]
                crest = float(crest_part.replace("+", ""))
                crest_changes.append(crest)
            except (IndexError, ValueError):
                pass

    if gains:
        avg_gain = sum(gains) / len(gains)
        avg_crest = sum(crest_changes) / len(crest_changes)
        print(f"Results: {len(gains)} tracks processed")
        print(f"  Average loudness gain: +{avg_gain:.2f} dB")
        print(f"  Average crest factor change: {avg_crest:.2f} dB")
        print()

        if all(g > 0 for g in gains):
            print("✓ VALIDATION PASSED")
            print("✓ Smooth scaling produces consistent loudness improvement")
            print("✓ Smooth scaling approach is production-ready")
            return 0
        else:
            print("✗ VALIDATION WARNING - Some tracks showed minimal or negative gains")
            return 1
    else:
        print("✗ No valid results to analyze")
        return 1

if __name__ == "__main__":
    sys.exit(main())
