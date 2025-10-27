#!/usr/bin/env python3
"""
End-to-end test of Auralis audio processing
"""

import sys
from pathlib import Path

# Add auralis to path
sys.path.insert(0, str(Path(__file__).parent))

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.io.unified_loader import load_audio
from auralis.io.saver import save

def test_adaptive_processing():
    """Test adaptive processing (no reference)"""
    print("\n🎵 Testing Adaptive Processing")
    print("=" * 50)

    # Input file
    input_file = "./examples/demo_acoustic.wav"
    output_file = "./test_output_adaptive.wav"

    print(f"📁 Input: {input_file}")
    print(f"📁 Output: {output_file}")

    # Load audio
    print("\n1️⃣  Loading audio...")
    audio, sr = load_audio(input_file)
    print(f"   ✅ Loaded: {len(audio)/sr:.2f}s @ {sr}Hz")

    # Create processor
    print("\n2️⃣  Creating processor...")
    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)
    print(f"   ✅ Processor ready")

    # Process
    print("\n3️⃣  Processing audio...")
    processed_audio = processor.process(audio)
    print(f"   ✅ Processing complete!")

    # Save
    print("\n4️⃣  Saving output...")
    save(output_file, processed_audio, sr, subtype='PCM_16')
    output_path = Path(output_file)
    size_kb = output_path.stat().st_size / 1024
    print(f"   ✅ Saved: {output_file} ({size_kb:.1f} KB)")

    print("\n✨ Adaptive processing test PASSED!")
    return True

def test_all_presets():
    """Test all 5 presets"""
    print("\n\n🎨 Testing All Presets")
    print("=" * 50)

    input_file = "./examples/demo_acoustic.wav"
    audio, sr = load_audio(input_file)

    presets = ["adaptive", "gentle", "warm", "bright", "punchy"]

    for preset in presets:
        print(f"\n🎛️  Testing preset: {preset.upper()}")

        config = UnifiedConfig()
        config.set_processing_mode("adaptive")

        # Apply preset settings
        if preset == "gentle":
            config.target_loudness = -16.0
            config.enable_dynamics = True
            config.enable_eq = True
        elif preset == "warm":
            config.target_loudness = -14.0
        elif preset == "bright":
            config.target_loudness = -12.0
        elif preset == "punchy":
            config.target_loudness = -11.0
            config.enable_dynamics = True

        processor = HybridProcessor(config)
        processed_audio = processor.process(audio)

        output_file = f"./test_output_{preset}.wav"
        save(output_file, processed_audio, sr, subtype='PCM_16')

        size_kb = Path(output_file).stat().st_size / 1024
        print(f"   ✅ {preset}: {output_file} ({size_kb:.1f} KB)")

    print("\n✨ All presets test PASSED!")
    return True

def main():
    """Run all tests"""
    print("\n" + "="*50)
    print("  🚀 AURALIS END-TO-END PROCESSING TEST")
    print("="*50)

    try:
        # Test 1: Basic adaptive processing
        test_adaptive_processing()

        # Test 2: All presets
        test_all_presets()

        print("\n\n" + "="*50)
        print("  ✅ ALL TESTS PASSED!")
        print("="*50)
        print("\n📁 Output files created:")
        for f in Path(".").glob("test_output_*.wav"):
            size_kb = f.stat().st_size / 1024
            print(f"   - {f.name} ({size_kb:.1f} KB)")

        return 0

    except Exception as e:
        print(f"\n\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())