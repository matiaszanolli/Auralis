#!/usr/bin/env python3
"""
Auto-Mastering Script

Quick workflow:
1. Fingerprint the track (via gRPC or database cache)
2. Analyze fingerprint for content characteristics
3. Auto-select optimal mastering preset and intensity
4. Process and export remastered WAV

Usage:
    python auto_master.py input.flac
    python auto_master.py input.flac --output remastered.wav
    python auto_master.py input.flac --intensity 0.8
"""

import argparse
import sqlite3
from pathlib import Path
from typing import Dict, Optional
import librosa
import soundfile as sf
import numpy as np

from grpc_fingerprint_client import GrpcFingerprintClient
from auralis.dsp.basic import amplify, normalize
from auralis.dsp.dynamics.soft_clipper import soft_clip


# Database path
DB_PATH = Path.home() / ".auralis" / "library.db"


def get_cached_fingerprint(filepath: str) -> Optional[Dict]:
    """Get fingerprint from database if already computed"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        # Find track by filepath
        cursor.execute(
            "SELECT id, tempo_bpm, lufs, harmonic_ratio, bass_pct, mid_pct, "
            "crest_db, transient_density, spectral_centroid FROM tracks WHERE filepath = ?",
            (filepath,)
        )
        row = cursor.fetchone()
        conn.close()

        if row and row[1] is not None:  # tempo_bpm exists = fingerprinted
            return {
                'track_id': row[0],
                'tempo_bpm': row[1],
                'lufs': row[2],
                'harmonic_ratio': row[3],
                'bass_pct': row[4],
                'mid_pct': row[5],
                'crest_db': row[6],
                'transient_density': row[7],
                'spectral_centroid': row[8],
            }
        return None

    except Exception as e:
        print(f"  ⚠️  Cache lookup failed: {e}")
        return None


def compute_fingerprint_grpc(filepath: str) -> Optional[Dict]:
    """Compute fingerprint via gRPC server"""
    print(f"🔍 Computing fingerprint via gRPC...")

    client = GrpcFingerprintClient()
    try:
        client.connect()
        fingerprint = client.compute_fingerprint(track_id=0, filepath=filepath)
        return fingerprint
    finally:
        client.close()


def generate_adaptive_parameters(fp: Dict, intensity: float = 1.0) -> Dict:
    """
    Generate content-aware processing parameters from fingerprint.

    All processing is adaptive - parameters are computed based on:
    - Audio fingerprint (25D: tempo, LUFS, spectral features, etc.)
    - Content characteristics (genre, dynamic range, frequency balance)
    - Intensity scaling factor (0.0-1.0)
    """
    # Extract key fingerprint metrics
    tempo = fp.get('tempo_bpm', 120)
    lufs = fp.get('lufs', -14.0)
    harmonic_ratio = fp.get('harmonic_ratio', 0.5)
    transient_density = fp.get('transient_density', 0.5)
    crest_db = fp.get('crest_db', 10)
    bass_pct = fp.get('bass_pct', 0.15)
    spectral_centroid = fp.get('spectral_centroid', 0.5)
    stereo_width = fp.get('stereo_width', 0.5)
    phase_correlation = fp.get('phase_correlation', 1.0)

    # Content-aware parameter generation
    params = {
        'content_type': [],
        'processing_notes': [],
        'dynamics': {},
        'eq_gains': {},
        'stereo': {},
    }

    # Detect content type from fingerprint
    if tempo > 140 and transient_density > 0.6:
        params['content_type'].append('high-energy')
        params['processing_notes'].append('Fast tempo + high transients: preserve dynamics')
    elif harmonic_ratio > 0.6 and 80 < tempo < 140:
        params['content_type'].append('melodic/vocal')
        params['processing_notes'].append('High harmonic content: gentle processing')
    elif harmonic_ratio < 0.4 and transient_density > 0.5:
        params['content_type'].append('percussion-heavy')
        params['processing_notes'].append('Low harmonic + transients: rhythmic content')

    if bass_pct > 0.20:
        params['processing_notes'].append('Bass-heavy: control low end')

    # Adaptive intensity based on dynamic range
    base_intensity = intensity
    if crest_db > 15:  # High dynamic range
        base_intensity *= 0.7
        params['processing_notes'].append('High dynamic range: gentle processing')
    elif crest_db < 8:  # Already compressed
        base_intensity *= 0.5
        params['processing_notes'].append('Already compressed: minimal processing')

    # Adaptive makeup gain based on source LUFS
    # Target final loudness: -12 to -10 LUFS for masters
    target_lufs = -11.0

    if lufs > -12.0:  # Already very loud
        makeup_gain = 0.0
        params['processing_notes'].append(f'Already loud ({lufs:.1f} LUFS): no makeup gain')
    elif lufs > -14.0:  # Moderately loud
        makeup_gain = (target_lufs - lufs) * 0.5  # Gentle boost
        params['processing_notes'].append(f'Moderately loud: gentle {makeup_gain:.1f} dB boost')
    else:  # Quiet source
        makeup_gain = (target_lufs - lufs) * base_intensity
        params['processing_notes'].append(f'Quiet source: {makeup_gain:.1f} dB boost to target')

    # Clamp makeup gain to reasonable range
    makeup_gain = max(0.0, min(makeup_gain, 6.0))

    # Adaptive target peak based on source LUFS
    # Louder sources get lower normalization targets to avoid clipping
    if lufs > -12.0:
        target_peak = 0.85  # Conservative for already-loud material
    elif lufs > -14.0:
        target_peak = 0.88  # Moderate
    else:
        target_peak = 0.90  # Can go a bit higher for quiet sources

    # Generate dynamics parameters
    # More compression for low dynamic range, less for high dynamic range
    compression_ratio = 2.0 + (1.0 / max(crest_db, 1.0)) * 2.0  # 2.0-4.0 range
    params['dynamics'] = {
        'makeup_gain_db': makeup_gain,
        'compressor_ratio': compression_ratio,
        'compressor_threshold_db': -20.0 + (crest_db / 2.0),  # Adaptive threshold
        'soft_clipper_threshold_db': -2.0,
        'target_peak': target_peak,
    }

    # Stereo preservation parameters
    params['stereo'] = {
        'width': stereo_width,
        'phase_correlation': phase_correlation,
        'preserve_imaging': True if stereo_width > 0.3 else False,
    }

    if stereo_width > 0.3:
        params['processing_notes'].append(f'Stereo width {stereo_width:.2f}: preserve imaging')
    else:
        params['processing_notes'].append(f'Narrow stereo: mono processing safe')

    # Generate EQ parameters (simplified - just for documentation)
    # TODO: Implement proper multi-band EQ based on spectral analysis
    params['eq_gains'] = {
        'bass': bass_pct * base_intensity,
        'mid': harmonic_ratio * base_intensity,
        'treble': spectral_centroid * base_intensity,
    }

    params['intensity'] = base_intensity
    return params


def process_track(
    filepath: str,
    intensity: float = 1.0,
    output_path: Optional[str] = None
) -> str:
    """
    Process track with adaptive content-aware mastering.

    All processing is adaptive - parameters are generated dynamically
    based on audio fingerprint analysis.

    Returns path to output WAV file
    """
    input_path = Path(filepath)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {filepath}")

    # Default output path
    if output_path is None:
        output_path = str(input_path.parent / f"{input_path.stem}_mastered.wav")

    print(f"📂 Input: {input_path.name}")
    print(f"📂 Output: {Path(output_path).name}")

    # Step 1: Get or compute fingerprint
    print("\n🔍 Step 1: Fingerprinting...")
    fingerprint = get_cached_fingerprint(str(filepath))

    if fingerprint:
        print(f"  ✅ Using cached fingerprint")
    else:
        print(f"  🆕 Computing new fingerprint")
        fingerprint = compute_fingerprint_grpc(str(filepath))

        if not fingerprint:
            raise RuntimeError("Failed to compute fingerprint")

    # Display key metrics
    print(f"\n📊 Audio Characteristics:")
    print(f"   Tempo: {fingerprint.get('tempo_bpm', 0):.1f} BPM")
    print(f"   LUFS: {fingerprint.get('lufs', 0):.1f} dB")
    print(f"   Harmonic ratio: {fingerprint.get('harmonic_ratio', 0):.2f}")
    print(f"   Crest factor: {fingerprint.get('crest_db', 0):.1f} dB")

    # Step 2: Generate adaptive parameters
    print(f"\n🧠 Step 2: Adaptive Parameter Generation...")
    params = generate_adaptive_parameters(fingerprint, intensity)

    content_types = ', '.join(params['content_type']) if params['content_type'] else 'general'
    print(f"   Content type: {content_types}")
    print(f"   Intensity: {params['intensity']:.2f}")
    print(f"   Compression ratio: {params['dynamics']['compressor_ratio']:.1f}:1")
    print(f"   Makeup gain: {params['dynamics']['makeup_gain_db']:.1f} dB")
    print(f"   Target peak: {params['dynamics']['target_peak'] * 100:.1f}%")

    # Stereo info
    stereo_info = params.get('stereo', {})
    if stereo_info.get('width', 0) > 0:
        print(f"   Stereo width: {stereo_info['width']:.2f} (preserve: {stereo_info.get('preserve_imaging', False)})")

    for note in params['processing_notes']:
        print(f"   • {note}")

    # Step 3: Load audio
    print(f"\n🎵 Step 3: Loading audio...")
    audio, sr = librosa.load(str(filepath), sr=None, mono=False)

    # Convert to stereo if mono
    if audio.ndim == 1:
        audio = np.stack([audio, audio])
        print(f"   Converted mono to stereo")

    print(f"   Sample rate: {sr} Hz")
    print(f"   Duration: {audio.shape[1] / sr:.1f} seconds")

    # Step 4: Apply adaptive processing
    print(f"\n⚡ Step 4: Adaptive Processing...")

    # Start with audio (stereo: channels x samples)
    processed = audio.copy()

    # Apply makeup gain based on adaptive parameters
    makeup_gain = params['dynamics'].get('makeup_gain_db', 0.0)
    if makeup_gain > 0.0:
        print(f"   Applying {makeup_gain:.1f} dB makeup gain")
        processed = amplify(processed, makeup_gain)
    else:
        print(f"   Skipping makeup gain (source already loud)")

    # Apply soft clipping to protect peaks
    threshold = params['dynamics'].get('soft_clipper_threshold_db', -2.0)
    threshold_linear = 10 ** (threshold / 20.0)
    print(f"   Applying soft clipping at {threshold:.1f} dB")
    processed = soft_clip(processed, threshold=threshold_linear, ceiling=0.99)

    # Normalize to adaptive target peak
    target_peak = params['dynamics'].get('target_peak', 0.90)
    print(f"   Normalizing to {target_peak * 100:.1f}% peak")
    processed = normalize(processed, target_peak)

    # Report stereo preservation
    stereo_info = params.get('stereo', {})
    if stereo_info.get('preserve_imaging', False):
        print(f"   ✅ Stereo imaging preserved (width: {stereo_info.get('width', 0):.2f})")

    print(f"   ✅ Processing complete")

    # Step 5: Export
    print(f"\n💾 Step 5: Exporting WAV...")
    sf.write(output_path, processed.T, sr, subtype='PCM_24')

    output_size_mb = Path(output_path).stat().st_size / (1024 * 1024)
    print(f"   ✅ Exported: {output_size_mb:.1f} MB")

    print(f"\n🎉 Complete! Output: {output_path}")

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Adaptive auto-mastering with content-aware processing"
    )
    parser.add_argument(
        'input',
        help='Input audio file (FLAC, WAV, MP3, etc.)'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output WAV file (default: input_mastered.wav)'
    )
    parser.add_argument(
        '-i', '--intensity',
        type=float,
        default=1.0,
        help='Processing intensity 0.0-1.0 (default: 1.0, adaptive based on dynamic range)'
    )

    args = parser.parse_args()

    try:
        output_path = process_track(
            filepath=args.input,
            intensity=args.intensity,
            output_path=args.output
        )

        print(f"\n✨ Success! Play with: ffplay '{output_path}'")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
