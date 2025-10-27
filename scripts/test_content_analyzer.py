#!/usr/bin/env python3
"""
Test Content-Aware Analyzer

Validates that the content analyzer correctly identifies the 7 reference profiles
by analyzing the original audio files.

This is a critical validation: the analyzer should identify each profile
from audio content alone, without any metadata hints.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import soundfile as sf
from auralis.analysis.content_aware_analyzer import ContentAwareAnalyzer
from auralis.analysis.profile_matcher import ProfileMatcher


def load_audio(filepath):
    """Load audio file."""
    audio, sr = sf.read(filepath)
    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)
    return audio, sr


def test_profile_detection():
    """Test that analyzer correctly identifies each profile."""

    print("=" * 80)
    print("CONTENT-AWARE ANALYZER VALIDATION TEST")
    print("=" * 80)
    print("\nTesting profile detection on 7 reference tracks...")
    print("Expected: Analyzer should identify each track's profile from audio alone\n")

    # Define test cases (track path → expected profile)
    test_cases = [
        {
            'name': 'Steven Wilson 2024 (Ultra-Audiophile)',
            'path': '/mnt/Musica/Musica/Porcupine Tree/(2024) Closure - Continuation [24Bit-96kHz]/05 - Normal.flac',
            'expected': 'steven_wilson_2024',
            'key_features': 'Extreme dynamics (21 dB crest), bass-heavy (74.6%)'
        },
        {
            'name': 'Steven Wilson 2021 (Balanced Audiophile)',
            'path': '/mnt/Musica/Musica/Porcupine Tree/(2024) Closure - Continuation [24Bit-96kHz]/09 - Prodigal.flac',
            'expected': 'steven_wilson_2021',
            'key_features': 'Excellent dynamics (18.5 dB), balanced (52% bass, 42% mid)'
        },
        {
            'name': 'AC/DC (Classic Hard Rock)',
            'path': '/mnt/audio/Audio/Remasters/AC-DC - Highway To Hell/01 - Highway To Hell.flac',
            'expected': 'acdc_highway_to_hell',
            'key_features': 'Mid-dominant (67% mid), negative B/M ratio (-3.4 dB)'
        },
        {
            'name': 'Bob Marley (Reggae)',
            'path': '/mnt/audio/Audio/Remasters/Bob Marley - Legend/01 - Get Up, Stand Up.flac',
            'expected': 'bob_marley_legend',
            'key_features': 'Moderate bass (59%), loudness war era (12.3 dB crest)'
        },
        {
            'name': 'Dio (Traditional Heavy Metal - Max Loudness)',
            'path': '/mnt/audio/Audio/Remasters/Dio - Holy Diver/02-Holy Diver.flac',
            'expected': 'dio_holy_diver',
            'key_features': 'Very loud (-8.6 LUFS), low dynamics (11.6 dB crest)'
        }
    ]

    # Note: Blind Guardian and Joe Satriani files not included in initial test

    analyzer = ContentAwareAnalyzer()
    matcher = ProfileMatcher()

    results = []
    correct = 0
    total = 0

    for test_case in test_cases:
        print(f"\n{'─' * 80}")
        print(f"Testing: {test_case['name']}")
        print(f"File: {test_case['path']}")
        print(f"Expected: {test_case['expected']}")
        print(f"Key Features: {test_case['key_features']}")
        print()

        filepath = Path(test_case['path'])
        if not filepath.exists():
            print(f"❌ SKIP: File not found")
            continue

        total += 1

        try:
            # Load audio (use first 30 seconds for speed)
            audio, sr = load_audio(filepath)
            max_samples = sr * 30
            if len(audio) > max_samples:
                audio = audio[:max_samples]
                print(f"   (Using first 30 seconds for speed)")

            # Analyze content
            analysis = analyzer.analyze(audio, sr)

            # Results
            detected = analysis['profile_match']
            confidence = analysis['confidence']
            characteristics = analysis['characteristics']

            print(f"\n📊 ANALYSIS RESULTS:")
            print(f"   Detected Profile: {detected}")
            print(f"   Confidence: {confidence:.2f}")
            print(f"\n   Spectral:")
            print(f"      Bass: {analysis['spectral']['bass_pct']:.1f}%")
            print(f"      Mid:  {analysis['spectral']['mid_pct']:.1f}%")
            print(f"      High: {analysis['spectral']['high_pct']:.1f}%")
            print(f"      B/M Ratio: {analysis['spectral']['bass_to_mid_db']:+.1f} dB")
            print(f"\n   Dynamic:")
            print(f"      LUFS: {analysis['dynamic']['estimated_lufs']:.1f} dB")
            print(f"      Crest: {analysis['dynamic']['crest_factor_db']:.1f} dB")
            print(f"\n   Characteristics:")
            print(f"      Frequency: {characteristics['frequency_balance']}")
            print(f"      Dynamics: {characteristics['dynamic_range']}")
            print(f"      Era: {characteristics['era_estimation']}")

            # Check if correct
            if detected == test_case['expected']:
                print(f"\n✅ PASS: Correctly identified as {detected}")
                correct += 1
                results.append({'name': test_case['name'], 'result': 'PASS', 'detected': detected, 'confidence': confidence})
            else:
                print(f"\n⚠️  FAIL: Expected {test_case['expected']}, got {detected}")
                results.append({'name': test_case['name'], 'result': 'FAIL', 'expected': test_case['expected'], 'detected': detected, 'confidence': confidence})

            # Generate target
            print(f"\n🎯 TARGET GENERATION:")
            target = matcher.generate_target(analysis, preserve_character=True)
            print(f"   Target LUFS: {target['target_lufs']:.1f} dB")
            print(f"   Min Crest: {target['min_crest_factor']:.1f} dB")
            print(f"   Processing Intensity: {target['processing_intensity']:.2f}")
            print(f"   Adjustments: {target['adjustments_made']}")

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append({'name': test_case['name'], 'result': 'ERROR', 'error': str(e)})

    # Summary
    print(f"\n{'═' * 80}")
    print("TEST SUMMARY")
    print(f"{'═' * 80}\n")

    for result in results:
        status_emoji = {'PASS': '✅', 'FAIL': '⚠️', 'ERROR': '❌'}[result['result']]
        print(f"{status_emoji} {result['name']}: {result['result']}")
        if result['result'] == 'PASS':
            print(f"   → Detected: {result['detected']} (confidence: {result['confidence']:.2f})")
        elif result['result'] == 'FAIL':
            print(f"   → Expected: {result['expected']}, Got: {result['detected']} (confidence: {result['confidence']:.2f})")
        elif result['result'] == 'ERROR':
            print(f"   → Error: {result['error']}")
        print()

    if total > 0:
        accuracy = (correct / total) * 100
        print(f"{'═' * 80}")
        print(f"ACCURACY: {correct}/{total} = {accuracy:.1f}%")
        print(f"{'═' * 80}\n")

        if accuracy >= 80:
            print("✅ EXCELLENT: Content analyzer is working correctly!")
        elif accuracy >= 60:
            print("⚠️  ACCEPTABLE: Content analyzer needs fine-tuning")
        else:
            print("❌ POOR: Content analyzer needs significant improvement")
    else:
        print("⚠️  No tests could be run (files not found)")


if __name__ == '__main__':
    test_profile_detection()
