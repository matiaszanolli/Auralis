#!/usr/bin/env python3
"""
Continuous Parameter Space Demonstration

Shows how the continuous approach generates unique targets for each audio
based on its position in 5D parameter space, without any profile matching.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
from auralis.analysis.content_aware_analyzer import ContentAwareAnalyzer
from auralis.analysis.continuous_target_generator import ContinuousTargetGenerator
import soundfile as sf


def load_audio(filepath, max_duration=30):
    """Load audio file (first N seconds)."""
    audio, sr = sf.read(filepath)
    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)

    max_samples = sr * max_duration
    if len(audio) > max_samples:
        audio = audio[:max_samples]

    return audio, sr


def demonstrate_continuous_approach():
    """Demonstrate continuous parameter space approach."""

    print("=" * 80)
    print("CONTINUOUS PARAMETER SPACE DEMONSTRATION")
    print("=" * 80)
    print("\nThis shows how EVERY audio gets a UNIQUE target computed from")
    print("continuous mathematical relationships - NO profile matching!\n")

    # Test cases from our reference library
    test_cases = [
        {
            'name': 'AC/DC - Highway To Hell (Classic Rock)',
            'path': '/mnt/audio/Audio/Remasters/AC-DC - Highway To Hell/01 - Highway To Hell.flac',
            'expected': 'Mid-dominant (rare), excellent dynamics - preserve both'
        },
        {
            'name': 'Bob Marley - Get Up Stand Up (Reggae)',
            'path': '/mnt/audio/Audio/Remasters/Bob Marley - Legend/01 - Get Up, Stand Up.flac',
            'expected': 'Bass-heavy, loudness war era - restore some dynamics'
        },
        {
            'name': 'Dio - Holy Diver (Heavy Metal)',
            'path': '/mnt/audio/Audio/Remasters/Dio - Holy Diver/02-Holy Diver.flac',
            'expected': 'Very loud, low dynamics - significant restoration possible'
        }
    ]

    analyzer = ContentAwareAnalyzer()
    generator = ContinuousTargetGenerator()

    print(f"{'─' * 80}\n")

    for i, test_case in enumerate(test_cases, 1):
        filepath = Path(test_case['path'])

        if not filepath.exists():
            print(f"⚠️  Skipping {test_case['name']} (file not found)\n")
            continue

        print(f"Test {i}: {test_case['name']}")
        print(f"Expected: {test_case['expected']}")
        print()

        # Load and analyze
        try:
            audio, sr = load_audio(filepath)
            analysis = analyzer.analyze(audio, sr)

            # Show source position in parameter space
            spectral = analysis['spectral']
            dynamic = analysis['dynamic']

            print("📍 SOURCE POSITION IN 5D PARAMETER SPACE:")
            print(f"   Dimension 1 (LUFS):          {dynamic['estimated_lufs']:>7.1f} dB")
            print(f"   Dimension 2 (Crest Factor):  {dynamic['crest_factor_db']:>7.1f} dB")
            print(f"   Dimension 3 (Bass/Mid Ratio):{spectral['bass_to_mid_db']:>+7.1f} dB")
            print(f"   Dimension 4 (Bass %):        {spectral['bass_pct']:>7.1f} %")
            print(f"   Dimension 5 (Mid %):         {spectral['mid_pct']:>7.1f} %")

            # Generate target via continuous functions (no profile matching!)
            print("\n🎯 TARGET COMPUTED VIA CONTINUOUS FUNCTIONS:")

            # Test different preservation levels
            for preserve in [0.9, 0.7, 0.5]:
                target = generator.generate_target(
                    analysis,
                    preserve_character=preserve
                )

                print(f"\n   Preserve={preserve} (mix: {preserve*100:.0f}% source + {(1-preserve)*100:.0f}% target):")
                print(f"      LUFS:   {dynamic['estimated_lufs']:>6.1f} → {target['target_lufs']:>6.1f} dB  (Δ {target['deltas']['lufs_change']:>+5.1f})")
                print(f"      Crest:  {dynamic['crest_factor_db']:>6.1f} → {target['target_crest_factor']:>6.1f} dB  (Δ {target['deltas']['crest_change']:>+5.1f})")
                print(f"      B/M:    {spectral['bass_to_mid_db']:>+6.1f} → {target['target_bass_mid_ratio']:>+6.1f} dB  (Δ {target['deltas']['bass_mid_change']:>+5.1f})")
                print(f"      Intensity: {target['processing_intensity']:.2f}")

            # Test different user intents
            print("\n🎨 USER INTENT MODIFIERS (preserve=0.7):")

            intents = ['audiophile', 'punchy', 'preserve']
            for intent in intents:
                target = generator.generate_target(
                    analysis,
                    user_intent=intent,
                    preserve_character=0.7
                )

                print(f"\n   Intent='{intent}':")
                print(f"      Target LUFS:  {target['target_lufs']:>6.1f} dB")
                print(f"      Target Crest: {target['target_crest_factor']:>6.1f} dB")
                print(f"      Intensity:    {target['processing_intensity']:.2f}")

            print(f"\n{'─' * 80}\n")

        except Exception as e:
            print(f"❌ Error processing {test_case['name']}: {e}")
            import traceback
            traceback.print_exc()
            print(f"\n{'─' * 80}\n")

    # Show parameter space info
    print("\n" + "=" * 80)
    print("PARAMETER SPACE INFORMATION")
    print("=" * 80)

    space_info = generator.get_parameter_space_info()

    print(f"\nDimensions: {space_info['dimensions']}")
    print("\nDimension Bounds (from 7 reference analysis):")
    for dim_name, bounds in zip(space_info['dimension_names'], space_info['bounds'].values()):
        print(f"  {dim_name:20s}: [{bounds['min']:>7.1f}, {bounds['max']:>7.1f}]  neutral={bounds['neutral']:>6.1f}")

    print(f"\nKey Relationship Discovered:")
    print(f"  LUFS ↔ Crest Factor correlation: {space_info['relationships']['lufs_crest_correlation']}")
    print(f"  ({space_info['relationships']['description']})")

    print(f"\nReference Points: {space_info['reference_points']}")
    print(f"Approach: {space_info['approach']}")

    print("\n" + "=" * 80)
    print("KEY INSIGHT")
    print("=" * 80)
    print("""
Every audio file is analyzed as a unique point in 5D parameter space.
Targets are computed via mathematical relationships - NO profile matching.
Different preserve_character values yield smooth transitions.
User intents shift positions in parameter space via vector operations.

This is TRUE content-aware adaptive processing.
No assumptions. No categories. No presets. Just mathematics.
""")


if __name__ == '__main__':
    demonstrate_continuous_approach()
