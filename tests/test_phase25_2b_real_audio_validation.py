# -*- coding: utf-8 -*-

"""
Phase 2.5.2B: Real Audio Validation - Blind Guardian Study

Compares professional 2018 remasters against original versions using simple metrics.
Analyzes what changes professionals made (RMS, crest factor, spectral) to identify patterns.

Key Research Questions:
1. What RMS/loudness changes do professional remasters apply?
2. How do they handle dynamic range (crest factor)?
3. Are there spectral changes (brighter/darker)?
4. Can we learn the professional mastering strategies?

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import numpy as np
import json
import gc
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, List, Optional
import librosa


class RealAudioMetrics:
    """Calculate metrics from real audio files for comparison"""

    @staticmethod
    def calculate_metrics(audio: np.ndarray, sr: int) -> Dict:
        """Calculate comprehensive metrics from audio - FAST version without expensive librosa operations"""
        # Basic level metrics
        rms = np.sqrt(np.mean(audio**2))
        rms_db = 20 * np.log10(rms) if rms > 0 else -np.inf
        peak = np.max(np.abs(audio))
        peak_db = 20 * np.log10(peak) if peak > 0 else -np.inf

        # Dynamic range metrics
        crest = peak / rms if rms > 0 else 0
        crest_db = 20 * np.log10(crest) if crest > 0 else 0

        # Simple spectral centroid via FFT (fast)
        fft = np.abs(np.fft.rfft(audio))
        freqs = np.fft.rfftfreq(len(audio), 1/sr)
        spectral_centroid = np.sum(freqs * fft) / np.sum(fft) if np.sum(fft) > 0 else 0

        # 95% spectral rolloff (where 95% of energy is below)
        cumsum = np.cumsum(fft)
        rolloff_idx = np.argmax(cumsum >= 0.95 * cumsum[-1])
        spectral_rolloff = freqs[rolloff_idx] if rolloff_idx < len(freqs) else freqs[-1]

        return {
            'rms': float(rms),
            'rms_db': float(rms_db),
            'peak': float(peak),
            'peak_db': float(peak_db),
            'crest_db': float(crest_db),
            'spectral_centroid_hz': float(spectral_centroid),
            'spectral_rolloff_hz': float(spectral_rolloff),
        }

    @staticmethod
    def compare_metrics(original: Dict, remastered: Dict) -> Dict:
        """Compare metrics between original and remastered"""
        return {
            'rms_change_db': remastered['rms_db'] - original['rms_db'],
            'peak_change_db': remastered['peak_db'] - original['peak_db'],
            'crest_change_db': remastered['crest_db'] - original['crest_db'],
            'centroid_change_hz': remastered['spectral_centroid_hz'] - original['spectral_centroid_hz'],
            'rolloff_change_hz': remastered['spectral_rolloff_hz'] - original['spectral_rolloff_hz'],
        }


# Album pairs with original and remastered versions (up to 2002)
ALBUM_PAIRS = [
    ('1988 - Battalions Of Fear', '1988 - Battalions Of Fear (2018)'),
    ('1989 - Follow The Blind', '1989 - Follow The Blind (2018)'),
    ('1990 - Tales From The Twilight World', '1990 - Tales From The Twilight World (2018)'),
    ('1992 - Somewhere Far Beyond', '1992 - Somewhere Far Beyond (2018)'),
    ('1995 - Imaginations From The Other Side', '1995 - Imaginations From The Other Side (2018)'),
    ('1998 - Nightfall In Middle-Earth', '1998 - Nightfall In Middle-Earth (2018)'),
    ('2002 - A Night At The Opera', '2002 - A Night At The Opera (2018)'),
]

BASE_PATH = Path('/mnt/Musica/Musica/Blind Guardian')


def _get_matching_tracks(original_dir: Path, remastered_dir: Path) -> List[Tuple[Path, Path]]:
    """Find matching tracks between original and remastered versions"""
    # Get track basenames without year prefix
    def get_basename(path: Path) -> str:
        """Extract comparable filename"""
        name = path.stem
        # Remove leading numbers and spaces
        parts = name.split()
        if parts and parts[0].isdigit():
            return ' '.join(parts[1:])
        return name

    original_files = {get_basename(f): f for f in original_dir.glob('*.flac')}
    remastered_files = {get_basename(f): f for f in remastered_dir.glob('*.flac')}

    # Find matches
    pairs = []
    for basename in original_files:
        if basename in remastered_files:
            pairs.append((original_files[basename], remastered_files[basename]))

    return sorted(pairs)


def test_blind_guardian_complete_validation():
    """Complete validation across all Blind Guardian albums - FAST version using only simple metrics"""

    print("\n" + "="*80)
    print("PHASE 2.5.2B: REAL AUDIO VALIDATION - BLIND GUARDIAN STUDY (FAST)")
    print("Analyzing professional mastering strategies using simple metrics")
    print("="*80)

    results_by_album = {}
    all_results = []

    for orig_album, remaster_album in ALBUM_PAIRS:
        orig_path = BASE_PATH / orig_album
        remaster_path = BASE_PATH / remaster_album

        if not orig_path.exists() or not remaster_path.exists():
            print(f"\n⏭️  Skipping {orig_album} (files not found)")
            continue

        print(f"\n{'='*80}")
        print(f"Album: {orig_album}")
        print(f"{'='*80}")

        # Find matching tracks
        track_pairs = _get_matching_tracks(orig_path, remaster_path)
        print(f"Found {len(track_pairs)} matching tracks")

        album_results = {
            'original_album': orig_album,
            'remaster_album': remaster_album,
            'tracks': [],
        }

        for orig_file, remaster_file in track_pairs:
            try:
                print(f"\n  Processing: {orig_file.name}")

                # Load audio at 44.1kHz to make FFT computationally feasible
                # This is sufficient for spectral analysis (Nyquist < 22kHz)
                sr_target = 44100
                audio_orig, sr_orig = librosa.load(orig_file, sr=sr_target, mono=True)
                audio_remaster, sr_remaster = librosa.load(remaster_file, sr=sr_target, mono=True)

                # Calculate metrics (FAST - no expensive operations)
                metrics_orig = RealAudioMetrics.calculate_metrics(audio_orig, sr_orig)
                metrics_remaster = RealAudioMetrics.calculate_metrics(audio_remaster, sr_remaster)
                metrics_diff = RealAudioMetrics.compare_metrics(metrics_orig, metrics_remaster)

                # Store results before clearing audio from memory
                track_result = {
                    'track_name': orig_file.name,
                    'metrics': {
                        'original': metrics_orig,
                        'remastered': metrics_remaster,
                        'difference': metrics_diff,
                    }
                }

                album_results['tracks'].append(track_result)
                all_results.append(track_result)

                # Print summary
                print(f"      Original RMS:     {metrics_orig['rms_db']:+.2f} dB")
                print(f"      Remastered RMS:   {metrics_remaster['rms_db']:+.2f} dB")
                print(f"      RMS Change:       {metrics_diff['rms_change_db']:+.2f} dB")
                print(f"      Crest Change:     {metrics_diff['crest_change_db']:+.2f} dB")
                print(f"      Spectral Change:  {metrics_diff['centroid_change_hz']:+.1f} Hz")

                # Explicit cleanup - delete large arrays before next iteration
                del audio_orig, audio_remaster
                gc.collect()

            except Exception as e:
                print(f"    ✗ Error: {e}")
                # Clean up even on error
                gc.collect()
                continue

        # Album summary
        if album_results['tracks']:
            results_by_album[orig_album] = album_results
            avg_rms_change = np.mean([t['metrics']['difference']['rms_change_db']
                                     for t in album_results['tracks']])
            avg_crest_change = np.mean([t['metrics']['difference']['crest_change_db']
                                       for t in album_results['tracks']])
            avg_centroid_change = np.mean([t['metrics']['difference']['centroid_change_hz']
                                          for t in album_results['tracks']])
            print(f"\n  Album Summary:")
            print(f"    Average RMS Change:      {avg_rms_change:+.2f} dB")
            print(f"    Average Crest Change:    {avg_crest_change:+.2f} dB")
            print(f"    Average Centroid Change: {avg_centroid_change:+.1f} Hz")

    # Final summary
    print(f"\n{'='*80}")
    print("VALIDATION COMPLETE")
    print(f"{'='*80}")
    print(f"Total albums analyzed: {len(results_by_album)}")
    print(f"Total tracks analyzed: {len(all_results)}")

    # Overall statistics
    if all_results:
        all_rms_changes = [t['metrics']['difference']['rms_change_db'] for t in all_results]
        all_crest_changes = [t['metrics']['difference']['crest_change_db'] for t in all_results]
        all_centroid_changes = [t['metrics']['difference']['centroid_change_hz'] for t in all_results]

        print(f"\nOverall Statistics:")
        print(f"  RMS Change:      {np.mean(all_rms_changes):+.2f} ± {np.std(all_rms_changes):.2f} dB")
        print(f"  Crest Change:    {np.mean(all_crest_changes):+.2f} ± {np.std(all_crest_changes):.2f} dB")
        print(f"  Centroid Change: {np.mean(all_centroid_changes):+.1f} ± {np.std(all_centroid_changes):.1f} Hz")

    # Save results
    output_dir = Path(__file__).parent.parent / 'docs' / 'reports'
    output_dir.mkdir(parents=True, exist_ok=True)

    results_file = output_dir / 'phase25_2b_blind_guardian_validation.json'
    with open(results_file, 'w') as f:
        json.dump({
            'test_date': datetime.now().isoformat(),
            'albums': results_by_album,
        }, f, indent=2)

    print(f"\n✓ Results saved to {results_file}")

    # Assertions
    assert len(all_results) > 0, "Should have analyzed some tracks"
    assert len(results_by_album) > 0, "Should have completed some albums"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
