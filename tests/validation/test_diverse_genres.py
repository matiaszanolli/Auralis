#!/usr/bin/env python3
"""
Test spectrum-based processing with diverse genres
"""

import sys
import numpy as np
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.io.unified_loader import load_audio
from auralis.dsp.basic import rms

# Define test cases: (name, original_path, reference_path, genre_type)
TEST_CASES = [
    # Already tested
    ("Static-X - Fix", 
     "/mnt/Musica/Musica/Static-X/Wisconsin Death Trip/06 Fix.mp3",
     "/mnt/audio/Audio/Remasters/Static-X - Wisconsin Death Trip/06 Fix.flac",
     "under_leveled_metal"),
    
    ("Testament - The Preacher", 
     "/mnt/Musica/Musica/Testament/Live/2005-Live in London/01 The Preacher.mp3",
     "/mnt/audio/Audio/Remasters/Testament - Live In London/01 The Preacher.flac",
     "loud_dynamic_live"),
    
    # Thrash Metal - Well-mastered
    ("Slayer - South of Heaven",
     "/mnt/Musica/Musica/VA - 100 Greatest Thrash Metal Songs (2010)/CD 2/15 Slayer - South Of Heaven.mp3",
     "/mnt/audio/Audio/Remasters/Slayer - South Of Heaven/06 South of Heaven.flac",
     "well_mastered_metal"),
    
    # Classic Rock - Well-mastered
    ("Iron Maiden - Aces High",
     "/mnt/Musica/Musica/Iron Maiden/Powerslave (1984)/01 Aces High.mp3",
     "/mnt/audio/Audio/Remasters/Iron Maiden - Powerslave/01 Aces High.flac",
     "classic_rock"),
    
    # Latin Rock - Well-mastered
    ("Soda Stereo - Persiana Americana",
     "/mnt/Musica/Musica/Soda Stereo/Canción Animal (1990)/01 - (En) El Séptimo Día.mp3",
     "/mnt/audio/Audio/Remasters/Soda Stereo - Cancion Animal/01 (En) El Septimo Dia.flac",
     "latin_rock"),
]

def analyze_track(name, orig_path, ref_path, genre_type):
    """Analyze a single track"""
    print(f"\n{'='*80}")
    print(f"{name} ({genre_type})")
    print('='*80)
    
    try:
        # Load audio
        orig_audio, _ = load_audio(orig_path)
        orig_mono = np.mean(orig_audio, axis=1) if orig_audio.ndim == 2 else orig_audio
        
        ref_audio, _ = load_audio(ref_path)
        ref_mono = np.mean(ref_audio, axis=1) if ref_audio.ndim == 2 else ref_audio
        
        # Analyze original and reference
        orig_peak = np.max(np.abs(orig_mono))
        orig_peak_db = 20 * np.log10(orig_peak)
        orig_rms_val = rms(orig_mono)
        orig_rms_db = 20 * np.log10(orig_rms_val)
        orig_crest = orig_peak_db - orig_rms_db
        
        ref_peak = np.max(np.abs(ref_mono))
        ref_peak_db = 20 * np.log10(ref_peak)
        ref_rms_val = rms(ref_mono)
        ref_rms_db = 20 * np.log10(ref_rms_val)
        ref_crest = ref_peak_db - ref_rms_db
        
        expected_rms_change = ref_rms_db - orig_rms_db
        expected_crest_change = ref_crest - orig_crest
        
        print(f"\nORIGINAL:")
        print(f"  Peak: {orig_peak_db:6.2f} dB, RMS: {orig_rms_db:6.2f} dB, Crest: {orig_crest:6.2f} dB")
        
        print(f"\nMATCHERING EXPECTED:")
        print(f"  RMS Δ: {expected_rms_change:+6.2f} dB, Crest Δ: {expected_crest_change:+6.2f} dB")
        
        # Process with Auralis
        config = UnifiedConfig()
        config.set_mastering_preset('adaptive')
        processor = HybridProcessor(config)
        
        print(f"\nProcessing...")
        processed = processor.process(orig_audio)
        
        proc_mono = np.mean(processed, axis=1) if processed.ndim == 2 else processed
        proc_peak = np.max(np.abs(proc_mono))
        proc_peak_db = 20 * np.log10(proc_peak)
        proc_rms_val = rms(proc_mono)
        proc_rms_db = 20 * np.log10(proc_rms_val)
        proc_crest = proc_peak_db - proc_rms_db
        
        result_rms_change = proc_rms_db - orig_rms_db
        result_crest_change = proc_crest - orig_crest
        
        print(f"\nAURALIS RESULT:")
        print(f"  Peak: {proc_peak_db:6.2f} dB, RMS: {proc_rms_db:6.2f} dB, Crest: {proc_crest:6.2f} dB")
        print(f"  RMS Δ: {result_rms_change:+6.2f} dB, Crest Δ: {result_crest_change:+6.2f} dB")
        
        rms_error = abs(result_rms_change - expected_rms_change)
        crest_error = abs(result_crest_change - expected_crest_change)
        
        print(f"\nACCURACY:")
        print(f"  RMS error: {rms_error:.2f} dB")
        print(f"  Crest error: {crest_error:.2f} dB")
        
        if rms_error < 1.0 and crest_error < 1.5:
            status = "✅ EXCELLENT"
        elif rms_error < 2.0 and crest_error < 2.5:
            status = "✅ GOOD"
        else:
            status = "⚠️  ACCEPTABLE"
        
        print(f"  {status}")
        
        return {
            'name': name,
            'genre': genre_type,
            'rms_error': rms_error,
            'crest_error': crest_error,
            'expected_rms': expected_rms_change,
            'result_rms': result_rms_change,
            'status': status
        }
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    print("="*80)
    print("DIVERSE GENRE TESTING - Spectrum-Based Processing")
    print("="*80)
    
    results = []
    for name, orig_path, ref_path, genre_type in TEST_CASES:
        result = analyze_track(name, orig_path, ref_path, genre_type)
        if result:
            results.append(result)
    
    # Summary
    print(f"\n\n{'='*80}")
    print("SUMMARY")
    print('='*80)
    
    if results:
        excellent = [r for r in results if '✅ EXCELLENT' in r['status']]
        good = [r for r in results if '✅ GOOD' in r['status']]
        acceptable = [r for r in results if '⚠️' in r['status']]
        
        print(f"\nResults breakdown:")
        print(f"  ✅ EXCELLENT: {len(excellent)}/{len(results)}")
        print(f"  ✅ GOOD:      {len(good)}/{len(results)}")
        print(f"  ⚠️  ACCEPTABLE: {len(acceptable)}/{len(results)}")
        
        avg_rms_error = np.mean([r['rms_error'] for r in results])
        avg_crest_error = np.mean([r['crest_error'] for r in results])
        
        print(f"\nAverage errors:")
        print(f"  RMS:   {avg_rms_error:.2f} dB")
        print(f"  Crest: {avg_crest_error:.2f} dB")
        
        print(f"\nBy genre:")
        genres = {}
        for r in results:
            genre = r['genre']
            if genre not in genres:
                genres[genre] = []
            genres[genre].append(r)
        
        for genre, tracks in genres.items():
            avg_error = np.mean([t['rms_error'] for t in tracks])
            print(f"  {genre:25s}: {len(tracks)} tracks, avg {avg_error:.2f} dB error")

if __name__ == "__main__":
    main()
