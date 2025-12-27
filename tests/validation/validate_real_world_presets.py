#!/usr/bin/env python3
"""Test preset integration with real-world music across different genres"""

from pathlib import Path

import numpy as np

from auralis.analysis.dynamic_range import DynamicRangeAnalyzer
from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from auralis.dsp.utils.adaptive import calculate_loudness_units
from auralis.dsp.utils.spectral import spectral_centroid
from auralis.io.unified_loader import load_audio


def analyze_track(audio_path, max_duration=30.0):
    """Analyze a real-world track with all 5 presets"""
    print(f"\n{'='*80}")
    print(f"Track: {Path(audio_path).name}")
    print(f"{'='*80}")
    
    # Load audio (limit to 30 seconds for speed)
    audio, sr = load_audio(audio_path)
    
    # Trim to max_duration
    max_samples = int(max_duration * sr)
    if len(audio) > max_samples:
        audio = audio[:max_samples]
    
    # Analyze input
    input_lufs = calculate_loudness_units(audio, sr)
    input_rms = np.sqrt(np.mean(audio ** 2))
    input_peak = np.max(np.abs(audio))
    
    dr_analyzer = DynamicRangeAnalyzer()
    input_dr_info = dr_analyzer.analyze_dynamic_range(audio, sr)
    input_dr = input_dr_info['dr_value']
    
    input_centroid = spectral_centroid(audio if audio.ndim == 1 else audio[:, 0], sr)
    
    print(f"\nINPUT CHARACTERISTICS:")
    print(f"  Duration: {len(audio)/sr:.1f}s")
    print(f"  LUFS: {input_lufs:.2f}")
    print(f"  RMS: {input_rms:.4f}")
    print(f"  Peak: {input_peak:.4f}")
    print(f"  Dynamic Range: {input_dr:.1f} dB")
    print(f"  Spectral Centroid: {input_centroid:.0f} Hz")
    
    # Process with each preset
    presets = ['adaptive', 'gentle', 'warm', 'bright', 'punchy']
    results = {}
    
    print(f"\n{'Preset':<12} {'Target':<8} {'Output':<8} {'RMS':<10} {'Peak':<10} {'DR':<8} {'Centroid':<10}")
    print(f"{'-'*80}")
    
    for preset_name in presets:
        # Create processor with preset
        config = UnifiedConfig()
        config.mastering_profile = preset_name
        processor = HybridProcessor(config)
        
        # Get target LUFS
        preset_profile = config.get_preset_profile()
        target_lufs = preset_profile.target_lufs if preset_profile else -14.0
        
        # Process
        processed = processor.process(audio.copy())
        
        # Analyze output
        output_lufs = calculate_loudness_units(processed, sr)
        output_rms = np.sqrt(np.mean(processed ** 2))
        output_peak = np.max(np.abs(processed))
        
        output_dr_info = dr_analyzer.analyze_dynamic_range(processed, sr)
        output_dr = output_dr_info['dr_value']
        
        output_centroid = spectral_centroid(processed if processed.ndim == 1 else processed[:, 0], sr)
        
        results[preset_name] = {
            'lufs': output_lufs,
            'rms': output_rms,
            'peak': output_peak,
            'dr': output_dr,
            'centroid': output_centroid
        }
        
        print(f"{preset_name:<12} {target_lufs:<8.1f} {output_lufs:<8.2f} {output_rms:<10.4f} {output_peak:<10.4f} {output_dr:<8.1f} {output_centroid:<10.0f}")
    
    # Analysis
    print(f"\n{'='*80}")
    print("ANALYSIS:")
    
    rms_values = [r['rms'] for r in results.values()]
    lufs_values = [r['lufs'] for r in results.values()]
    dr_values = [r['dr'] for r in results.values()]
    
    rms_range = max(rms_values) - min(rms_values)
    lufs_range = max(lufs_values) - min(lufs_values)
    dr_range = max(dr_values) - min(dr_values)
    
    print(f"  RMS range: {rms_range:.4f} ({min(rms_values):.4f} to {max(rms_values):.4f})")
    print(f"  LUFS range: {lufs_range:.2f} dB ({min(lufs_values):.2f} to {max(lufs_values):.2f})")
    print(f"  DR range: {dr_range:.1f} dB ({min(dr_values):.1f} to {max(dr_values):.1f})")
    
    # Verdict
    if rms_range > 0.05:
        print(f"  ✅ Presets produce DISTINCT outputs (RMS difference: {rms_range:.4f})")
    elif rms_range > 0.01:
        print(f"  ⚠️  Presets produce SUBTLE differences (RMS difference: {rms_range:.4f})")
    else:
        print(f"  ❌ Presets produce IDENTICAL outputs (RMS difference: {rms_range:.4f})")
    
    # Specific checks
    gentle_quieter = results['gentle']['rms'] < results['punchy']['rms']
    gentle_more_dr = results['gentle']['dr'] > results['punchy']['dr']
    
    print(f"\n  Gentle quieter than Punchy: {'✅' if gentle_quieter else '❌'}")
    print(f"  Gentle more dynamic than Punchy: {'✅' if gentle_more_dr else '❌'}")
    
    return results

if __name__ == "__main__":
    # Test tracks from different genres
    test_tracks = [
        # Electronic (modern, compressed)
        "/mnt/Musica/Musica/2005 - Daft Punk - Human After All [24bit 96kHz Vinyl Rip]/A1 - Human After All.flac",
        
        # Jazz (acoustic, dynamic)
        "/mnt/Musica/Musica/Miles Davis/Miles Davis - Blue Moods [FLAC+MP3](Big Papi) Jazz Additional Torrents Inside/01 - Nature Boy.flac",
        
        # Rock (punchy, mid-heavy)
        "/mnt/Musica/Musica/(The) Rolling Stones - Voodoo Lounge (1994)(UK & Europe)[LP][24-96][FLAC]/A1. Love Is Strong.flac",
        
        # Metal (aggressive, distorted)
        "/mnt/Musica/Musica/2015. Blind Guardian - Beyond The Red Mirror (2018) [24-96]/01. The Ninth Wave.flac",
        
        # Hip-hop (bass-heavy, modern loudness)
        "/mnt/Musica/Musica/2Pac/Greatest Hits/01 - Keep Ya Head Up.flac",
    ]
    
    for track in test_tracks:
        if Path(track).exists():
            try:
                analyze_track(track, max_duration=30.0)
            except Exception as e:
                print(f"❌ Error processing {Path(track).name}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"❌ File not found: {track}")
    
    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}")
