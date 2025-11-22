#!/usr/bin/env python3
"""Test script to process an audio track and analyze the results."""

import numpy as np
from auralis.io.unified_loader import load_audio
from auralis.io.saver import save
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.dsp.basic import rms

def analyze_audio(audio, sr, label="Audio"):
    """Analyze audio characteristics"""
    peak = np.max(np.abs(audio))
    rms_value = rms(audio)
    
    # Calculate dB values
    peak_db = 20 * np.log10(peak) if peak > 0 else -np.inf
    rms_db = 20 * np.log10(rms_value) if rms_value > 0 else -np.inf
    crest_factor = peak_db - rms_db
    
    print(f"\n{'='*60}")
    print(f"{label} Analysis:")
    print(f"{'='*60}")
    print(f"Peak Level:      {peak_db:>8.2f} dB  ({peak:.4f} linear)")
    print(f"RMS Level:       {rms_db:>8.2f} dB  ({rms_value:.4f} linear)")
    print(f"Crest Factor:    {crest_factor:>8.2f} dB  (dynamics)")
    
    # Check for clipping
    clipped_samples = np.sum(np.abs(audio) >= 0.99)
    if clipped_samples > 0:
        print(f"⚠️  CLIPPING: {clipped_samples} samples at >= 0.99")
    
    # Check for over-compression
    if crest_factor < 6.0:
        print(f"⚠️  OVER-COMPRESSED: Crest factor {crest_factor:.1f} dB (< 6 dB)")
    
    # Check if peak is too high
    if peak_db > -1.0:
        print(f"⚠️  PEAK TOO HIGH: {peak_db:.1f} dB (> -1 dB)")
    
    return {'peak_db': peak_db, 'rms_db': rms_db, 'crest_factor': crest_factor, 'clipped_samples': clipped_samples}

def main():
    input_file = "/mnt/Musica/Musica/Television/[1977] Marquee Moon (Expanded & Remastered)/01 - See No Evil.mp3"
    output_file = "/tmp/test_mastered_output.wav"
    
    print("\n" + "="*60)
    print("AURALIS PRESET ANALYSIS TEST")
    print("="*60)
    
    # Load and analyze original
    print("\nLoading audio...")
    audio, sr = load_audio(input_file)
    original_stats = analyze_audio(audio, sr, "ORIGINAL")
    
    # Process
    print("\n\nProcessing with 'adaptive' preset...")
    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    config.mastering_profile = "adaptive"
    processor = HybridProcessor(config)
    processed_audio = processor.process(audio)
    
    # Analyze processed
    processed_stats = analyze_audio(processed_audio, sr, "PROCESSED")
    
    # Calculate changes
    print(f"\n{'='*60}")
    print("PROCESSING CHANGES:")
    print(f"{'='*60}")
    print(f"Peak Change:     {processed_stats['peak_db'] - original_stats['peak_db']:>+8.2f} dB")
    print(f"RMS Change:      {processed_stats['rms_db'] - original_stats['rms_db']:>+8.2f} dB")
    print(f"Crest Factor Δ:  {processed_stats['crest_factor'] - original_stats['crest_factor']:>+8.2f} dB")
    
    print(f"\n{'='*60}")
    print("ASSESSMENT:")
    print(f"{'='*60}")
    
    if processed_stats['clipped_samples'] > 0:
        print("❌ CLIPPING DETECTED - Audio is distorted!")
        print("   → Need to reduce limiter threshold")
    
    rms_increase = processed_stats['rms_db'] - original_stats['rms_db']
    if rms_increase > 6.0:
        print(f"❌ TOO LOUD - RMS increased by {rms_increase:.1f} dB (> 6 dB)")
        print("   → Need to reduce target loudness")
    
    if processed_stats['crest_factor'] < 6.0:
        print(f"❌ OVER-COMPRESSED - Crest factor only {processed_stats['crest_factor']:.1f} dB")
        print("   → Need to reduce compression ratio or blend")
    
    # Save
    print(f"\nSaving to: {output_file}")
    save(output_file, processed_audio, sr, subtype='PCM_24')
    print("\n✅ Analysis complete - check /tmp/test_mastered_output.wav\n")

if __name__ == "__main__":
    main()
