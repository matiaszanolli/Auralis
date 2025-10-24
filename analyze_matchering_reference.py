#!/usr/bin/env python3
"""
Analyze original vs Matchering remastered tracks to understand target characteristics.
"""

import numpy as np
from pathlib import Path
from auralis.io.unified_loader import load_audio
from auralis.dsp.basic import rms

def analyze_file(filepath):
    """Analyze a single audio file"""
    try:
        audio, sr = load_audio(str(filepath))
        peak = np.max(np.abs(audio))
        rms_value = rms(audio)
        
        peak_db = 20 * np.log10(peak) if peak > 0 else -np.inf
        rms_db = 20 * np.log10(rms_value) if rms_value > 0 else -np.inf
        crest_factor = peak_db - rms_db
        
        clipped_samples = np.sum(np.abs(audio) >= 0.99)
        
        return {
            'peak_db': peak_db,
            'rms_db': rms_db,
            'crest_factor': crest_factor,
            'clipped': clipped_samples,
            'success': True
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def compare_pair(original_path, remastered_path, track_name):
    """Compare original vs remastered track"""
    print(f"\n{'='*70}")
    print(f"Track: {track_name}")
    print(f"{'='*70}")
    
    orig = analyze_file(original_path)
    rema = analyze_file(remastered_path)
    
    if not orig['success']:
        print(f"❌ Failed to load original: {orig['error']}")
        return None
    if not rema['success']:
        print(f"❌ Failed to load remastered: {rema['error']}")
        return None
    
    print(f"\nORIGINAL:")
    print(f"  Peak:         {orig['peak_db']:>7.2f} dB")
    print(f"  RMS:          {orig['rms_db']:>7.2f} dB")
    print(f"  Crest Factor: {orig['crest_factor']:>7.2f} dB")
    if orig['clipped'] > 0:
        print(f"  ⚠️  Clipping:   {orig['clipped']} samples")
    
    print(f"\nMATCHERING REMASTERED:")
    print(f"  Peak:         {rema['peak_db']:>7.2f} dB")
    print(f"  RMS:          {rema['rms_db']:>7.2f} dB")
    print(f"  Crest Factor: {rema['crest_factor']:>7.2f} dB")
    if rema['clipped'] > 0:
        print(f"  ⚠️  Clipping:   {rema['clipped']} samples")
    
    delta_peak = rema['peak_db'] - orig['peak_db']
    delta_rms = rema['rms_db'] - orig['rms_db']
    delta_crest = rema['crest_factor'] - orig['crest_factor']
    
    print(f"\nCHANGES (Remastered - Original):")
    print(f"  Peak Δ:       {delta_peak:>+7.2f} dB")
    print(f"  RMS Δ:        {delta_rms:>+7.2f} dB")
    print(f"  Crest Δ:      {delta_crest:>+7.2f} dB")
    
    return {
        'track': track_name,
        'delta_peak': delta_peak,
        'delta_rms': delta_rms,
        'delta_crest': delta_crest,
        'orig_peak': orig['peak_db'],
        'orig_rms': orig['rms_db'],
        'rema_peak': rema['peak_db'],
        'rema_rms': rema['rms_db'],
        'rema_crest': rema['crest_factor']
    }

def main():
    print("\n" + "="*70)
    print("MATCHERING REFERENCE ANALYSIS")
    print("Comparing original tracks vs Matchering remastered outputs")
    print("="*70)
    
    # Iron Maiden - Powerslave (1984)
    comparisons = []
    
    # Find tracks in Powerslave
    orig_album = Path("/mnt/Musica/Musica/Iron Maiden")
    rema_album = Path("/mnt/audio/Audio/Remasters/Iron Maiden - Powerslave")
    
    if rema_album.exists():
        rema_tracks = sorted(rema_album.glob("*.flac"))[:3]  # First 3 tracks
        
        for rema_track in rema_tracks:
            # Try to find matching original
            track_name = rema_track.stem
            print(f"\nSearching for original of: {track_name}")
            
            # Search recursively in Iron Maiden folder
            orig_tracks = list(orig_album.rglob(f"*{track_name}*"))
            if not orig_tracks:
                # Try simpler search
                orig_tracks = list(orig_album.rglob("*.flac"))
            
            if orig_tracks:
                orig_track = orig_tracks[0]
                print(f"Found: {orig_track}")
                result = compare_pair(orig_track, rema_track, track_name)
                if result:
                    comparisons.append(result)
    
    # Soda Stereo - Doble Vida
    soda_orig = Path("/mnt/Musica/Musica/Soda Stereo/1988 - Doble Vida (Lossless)")
    soda_rema = Path("/mnt/audio/Audio/Remasters")
    
    # Find Soda Stereo remasters
    soda_rema_dirs = list(soda_rema.glob("Soda Stereo*"))
    if soda_rema_dirs and soda_orig.exists():
        orig_tracks = sorted(soda_orig.glob("*.m4a"))[:2]  # First 2 tracks
        
        for orig_track in orig_tracks:
            track_name = orig_track.stem
            # Try to find remastered version
            for rema_dir in soda_rema_dirs:
                rema_tracks = list(rema_dir.glob(f"*{track_name.split('-')[1].strip()}*"))
                if rema_tracks:
                    result = compare_pair(orig_track, rema_tracks[0], track_name)
                    if result:
                        comparisons.append(result)
                    break
    
    # Summary statistics
    if comparisons:
        print(f"\n\n{'='*70}")
        print("SUMMARY - Matchering Typical Behavior:")
        print(f"{'='*70}")
        
        avg_peak_change = np.mean([c['delta_peak'] for c in comparisons])
        avg_rms_change = np.mean([c['delta_rms'] for c in comparisons])
        avg_crest_change = np.mean([c['delta_crest'] for c in comparisons])
        
        avg_final_peak = np.mean([c['rema_peak'] for c in comparisons])
        avg_final_rms = np.mean([c['rema_rms'] for c in comparisons])
        avg_final_crest = np.mean([c['rema_crest'] for c in comparisons])
        
        print(f"\nAverage Changes ({len(comparisons)} tracks analyzed):")
        print(f"  Peak Change:       {avg_peak_change:>+7.2f} dB")
        print(f"  RMS Change:        {avg_rms_change:>+7.2f} dB")
        print(f"  Crest Factor Δ:    {avg_crest_change:>+7.2f} dB")
        
        print(f"\nTypical Final Values:")
        print(f"  Final Peak:        {avg_final_peak:>7.2f} dB")
        print(f"  Final RMS:         {avg_final_rms:>7.2f} dB")
        print(f"  Final Crest:       {avg_final_crest:>7.2f} dB")
        
        print(f"\n{'='*70}")
        print("RECOMMENDATIONS FOR AURALIS PRESETS:")
        print(f"{'='*70}")
        print(f"✓ Target RMS increase: ~{avg_rms_change:.1f} dB (not +12 dB!)")
        print(f"✓ Preserve crest factor: Change by {avg_crest_change:.1f} dB (not -12 dB!)")
        print(f"✓ Target peak level: ~{avg_final_peak:.1f} dB (leave headroom)")
        print(f"✓ Final crest factor: ~{avg_final_crest:.1f} dB (preserve dynamics)")
        
    print("\n")

if __name__ == "__main__":
    main()
