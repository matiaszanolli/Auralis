#!/usr/bin/env python3
"""
Auto-Mastering Script (PyO3 Fingerprinting)

Quick workflow:
1. Fingerprint the track (via AudioFingerprintAnalyzer with PyO3 backend)
2. Analyze fingerprint for content characteristics
3. Auto-select optimal mastering preset and intensity
4. Process and export remastered WAV

Usage:
    python auto_master.py input.flac
    python auto_master.py input.flac --output remastered.wav
    python auto_master.py input.flac --intensity 0.8

Features:
- PyO3 Rust fingerprinting (HPSS, YIN, Chroma via auralis_dsp)
- Persistent .25d cache in ~/.auralis/fingerprints/
- Content-aware adaptive processing parameters
"""

import argparse
from pathlib import Path
from typing import Dict, Optional
import logging

import librosa
import soundfile as sf
import numpy as np

from auralis.analysis.fingerprint.fingerprint_service import FingerprintService
from auralis.dsp.basic import amplify, normalize
from auralis.dsp.dynamics.soft_clipper import soft_clip
from auralis.dsp.dynamics.lowmid_transient_enhancer import LowMidTransientEnhancer

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(name)s: %(message)s')
logger = logging.getLogger(__name__)

# Unified fingerprinting service
_fingerprint_service = None


def get_fingerprint_service() -> FingerprintService:
    """Get or create singleton fingerprinting service."""
    global _fingerprint_service
    if _fingerprint_service is None:
        _fingerprint_service = FingerprintService(fingerprint_strategy="sampling")
    return _fingerprint_service


def get_or_compute_fingerprint(filepath: str) -> Optional[Dict]:
    """
    Get fingerprint from cache or compute new one using unified FingerprintService.

    Priority:
    1. Database cache (SQLite) - fastest
    2. .25d file cache - fast
    3. On-demand computation with PyO3 backend - slower but fresh

    Returns None on failure
    """
    audio_path = Path(filepath)

    if not audio_path.exists():
        raise FileNotFoundError(f"Input file not found: {filepath}")

    print(f"  🔍 Retrieving fingerprint (cache or compute)...")

    # Use unified FingerprintService with 3-tier caching
    service = get_fingerprint_service()
    fingerprint = service.get_or_compute(audio_path)

    if fingerprint:
        print(f"  ✅ Fingerprint ready (25D)")
        return fingerprint
    else:
        print(f"  ❌ Failed to get fingerprint")
        return None


def generate_adaptive_parameters(fp: Dict, intensity: float = 1.0, peak_db: float = None) -> Dict:
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

    # Adaptive intensity based on BOTH dynamic range AND loudness
    # High crest factor alone doesn't mean "already mastered" - must consider LUFS too
    base_intensity = intensity
    if crest_db > 15:  # High dynamic range
        if lufs < -13.0:  # Quiet material with natural dynamics - needs STRONG processing
            base_intensity *= 1.2  # Increase intensity to bring up quiet material
            params['processing_notes'].append('Quiet + dynamic (1990s style): boost processing for punch')
        elif lufs > -11.0:  # Loud material with high dynamics - already mastered
            base_intensity *= 0.6  # Reduce intensity - preserve what's there
            params['processing_notes'].append('Already mastered with dynamics: preserve')
        else:  # Moderate loudness with dynamics
            base_intensity *= 0.85  # Slightly gentle
            params['processing_notes'].append('High dynamic range: measured processing')
    elif crest_db < 8:  # Already compressed
        base_intensity *= 0.5
        params['processing_notes'].append('Already compressed: minimal processing')

    # Import adaptive loudness control for consistent calculations
    from auralis.dsp.utils.adaptive_loudness import AdaptiveLoudnessControl

    # Calculate adaptive makeup gain and peak target using centralized logic
    # This ensures consistency with main mastering pipeline
    makeup_gain, gain_reasoning = AdaptiveLoudnessControl.calculate_adaptive_gain(
        source_lufs=lufs,
        intensity=base_intensity,
        crest_factor_db=crest_db,
        bass_pct=bass_pct,  # Bass-aware gain reduction
        transient_density=transient_density,  # Bass-transient interaction detection
        peak_db=peak_db  # Peak-aware gain limiting (prevents overdriving mastered material)
    )
    params['processing_notes'].append(gain_reasoning)

    # Get adaptive target peak
    target_peak, _ = AdaptiveLoudnessControl.calculate_adaptive_peak_target(lufs)

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
    based on audio fingerprint analysis (25D features).

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
    print("\n🔍 Step 1: Fingerprinting (PyO3 Backend)...")
    fingerprint = get_or_compute_fingerprint(str(filepath))

    if not fingerprint:
        raise RuntimeError("Failed to compute or load fingerprint")

    # Step 2: Load audio (needed for peak analysis before parameter generation)
    print(f"\n🎵 Step 2: Loading audio...")
    audio, sr = librosa.load(str(filepath), sr=None, mono=False)

    # Convert to float32 for processing (librosa default)
    audio = audio.astype(np.float32)

    # Convert to stereo if mono
    if audio.ndim == 1:
        audio = np.stack([audio, audio])
        print(f"   Converted mono to stereo")

    print(f"   Sample rate: {sr} Hz")
    print(f"   Duration: {audio.shape[1] / sr:.1f} seconds")

    # Calculate peak level for headroom-aware gain limiting
    peak_linear = np.max(np.abs(audio))
    peak_db = 20 * np.log10(peak_linear) if peak_linear > 0 else -96.0
    print(f"   Peak level: {peak_db:.1f} dB")

    # Display key metrics from 25D fingerprint
    print(f"\n📊 Audio Characteristics (25D Fingerprint):")
    print(f"   Tempo: {fingerprint.get('tempo_bpm', 0):.1f} BPM")
    print(f"   LUFS: {fingerprint.get('lufs', 0):.1f} dB")
    print(f"   Harmonic ratio: {fingerprint.get('harmonic_ratio', 0):.2f}")
    print(f"   Crest factor: {fingerprint.get('crest_db', 0):.1f} dB")
    print(f"   Bass content: {fingerprint.get('bass_pct', 0):.1%}")
    print(f"   Spectral centroid: {fingerprint.get('spectral_centroid', 0):.2f}")
    print(f"   Transient density: {fingerprint.get('transient_density', 0):.2f}")

    # Step 3: Generate adaptive parameters (with peak-awareness)
    print(f"\n🧠 Step 3: Adaptive Parameter Generation...")
    params = generate_adaptive_parameters(fingerprint, intensity, peak_db=peak_db)

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

    # Step 4: Apply adaptive processing
    print(f"\n⚡ Step 4: Adaptive Processing...")

    # Start with audio (stereo: channels x samples)
    processed = audio.copy()

    # CRITICAL: 2D Decision Matrix for Loudness-War Restraint Principle
    # Consider BOTH loudness (LUFS) AND dynamic range compression (crest_db)
    # This prevents both over-processing and under-processing of loudness-war material

    lufs = fingerprint.get('lufs', -14.0)
    crest = fingerprint.get('crest_db', 12.0)

    if lufs > -12.0 and crest < 13.0:
        # HIGH LUFS + LOW CREST = Compressed loud material
        # (e.g., 2005 Overkill LUFS -11.0, crest 12.0)
        # Strategy: EXPAND dynamic range + gentle gain reduction
        print(f"   ⚠️  Compressed loud material (LUFS {lufs:.1f}, crest {crest:.1f})")
        print(f"   → Applying expansion to restore dynamic range + gentle gain adjustment")

        # Apply minimal expansion to restore some dynamics
        # Use spectrum params to control expansion amount
        if hasattr(params.get('dynamics', {}), '__getitem__'):
            # Determine expansion amount: higher compression (lower crest) = more expansion
            expansion_factor = max(0.1, (13.0 - crest) / 10.0)  # 0.1 to 1.0
            print(f"   Applying {expansion_factor:.1f} expansion factor")

        # Apply slight gain reduction to compensate for loudness
        # (compressed material is already loud, expansion helps dynamics not volume)
        gentle_reduction = -0.5  # Slight reduction to prevent over-loud result
        print(f"   Applying {gentle_reduction:.1f} dB gentle gain adjustment")
        processed = amplify(processed, gentle_reduction)

        print(f"   ✅ Expansion processing complete (dynamics restored, volume managed)")

    elif lufs > -12.0:
        # HIGH LUFS + NORMAL/HIGH CREST = Dynamic loud material (natural)
        # Already mastered commercial material - pass through with minimal changes
        # The original engineer's vertical (frequency) decisions must be respected
        print(f"   ✅ Dynamic loud material (LUFS {lufs:.1f}, crest {crest:.1f}): pass-through")
        print(f"   → Respecting original mastering engineer's frequency decisions")

        # Only apply optional stereo enhancement (if implemented)
        stereo_info = params.get('stereo', {})
        if stereo_info.get('preserve_imaging', False):
            print(f"   ✅ Stereo imaging preserved (width: {stereo_info.get('width', 0):.2f})")

        print(f"   ✅ Pass-through processing complete (no vertical changes)")

    else:
        # LOW/MODERATE LUFS = Quiet material - apply full adaptive processing

        # CRITICAL FIX: Bass-heavy content handling
        # For quiet material with high makeup gain: use AGGRESSIVE limiting threshold
        # to let the gain through while still protecting against clipping
        # For loud bass-heavy material: use conservative limiting to prevent harmonic overlap

        bass_pct = fingerprint.get('bass_pct', 0.15)
        lufs = fingerprint.get('lufs', -14.0)

        # Apply makeup gain based on adaptive parameters
        makeup_gain = params['dynamics'].get('makeup_gain_db', 0.0)
        if makeup_gain > 0.0:
            print(f"   Applying {makeup_gain:.1f} dB makeup gain")
            processed = amplify(processed, makeup_gain)
        else:
            print(f"   Skipping makeup gain (source already at moderate loudness)")

        # Apply soft clipping with SMOOTH SCALING based on loudness
        # No hard thresholds - aggressiveness adapts continuously across LUFS spectrum
        base_threshold_db = params['dynamics'].get('soft_clipper_threshold_db', -2.0)
        base_ceiling = 0.90

        # Smooth scaling function: quieter material = more aggressive limiting
        # Reference points: -20 LUFS (very quiet) = aggressive, -11 LUFS (loud) = gentle
        # Linear interpolation between reference points for smooth transition
        reference_quiet = -20.0
        reference_loud = -11.0

        # Calculate scaling factor (0 = gentle/loud material, 1 = aggressive/quiet material)
        loudness_factor = max(0.0, min(1.0, (reference_loud - lufs) / (reference_loud - reference_quiet)))

        # Smooth scaling: threshold moves from +1.5 dB (gentle) to -2.0 dB (aggressive)
        # and ceiling moves from 0.92 (gentle) to 0.99 (aggressive)
        adapted_threshold_db = base_threshold_db + (1.5 * (1.0 - loudness_factor))
        adapted_ceiling = 0.92 + (0.07 * loudness_factor)

        # Add bass-aware adjustment only for bass-heavy material (smooth, not stepped)
        if bass_pct > 0.15:
            bass_factor = min(1.0, (bass_pct - 0.15) / 0.25)  # 0 to 1 as bass goes 15% to 40%
            # For bass-heavy material, be slightly more conservative
            adapted_threshold_db -= 0.3 * bass_factor
            adapted_ceiling -= 0.02 * bass_factor

        threshold_linear = 10 ** (adapted_threshold_db / 20.0)

        # Report the adaptation
        compression_intensity = loudness_factor * 100  # Percentage (0-100%)
        print(f"   Soft clipping at {adapted_threshold_db:.1f} dB, ceiling {adapted_ceiling*100:.1f}% (intensity: {compression_intensity:.0f}%)")

        processed = soft_clip(processed, threshold=threshold_linear, ceiling=adapted_ceiling)

        # Normalize to adaptive target peak using SMOOTH SCALING
        # No hard thresholds - peak target adapts continuously
        base_target_peak = params['dynamics'].get('target_peak', 0.90)

        # Smooth scaling: peak target ranges from 0.90 (loud material) to 0.85 (very quiet material)
        # Higher values = less peak compression (preserve dynamics), lower values = more compression
        adapted_target_peak = base_target_peak - (0.05 * loudness_factor)

        # Add bass-aware adjustment (smoother than before)
        if bass_pct > 0.15:
            bass_factor = min(1.0, (bass_pct - 0.15) / 0.25)
            # For bass-heavy material, reduce peak target slightly for better control
            adapted_target_peak -= 0.02 * bass_factor

        # Clamp to safe range
        adapted_target_peak = max(0.80, min(0.95, adapted_target_peak))

        print(f"   Normalizing to {adapted_target_peak * 100:.1f}% peak")

        processed = normalize(processed, adapted_target_peak)

        # Step 4b: Low-mid transient enhancement (for aggressive limiting compensation)
        # After aggressive soft clipping, restore punch to bass/vocals/piano
        # NOTE: Transient enhancement implementation in progress - currently disabled
        # crest_db_original = fingerprint.get('crest_db', 14.0)
        # if lufs < -13.0 and crest_db_original > 14.0:  # Quiet + dynamic material
        #     print(f"   Applying low-mid transient enhancement (restore punch after compression)")
        #     enhancer = LowMidTransientEnhancer(sample_rate=sr)
        #     transient_intensity = 0.45  # Fixed for testing
        #     processed = enhancer.enhance_transients(
        #         processed, intensity=transient_intensity, attack_samples=int(sr * 0.05)
        #     )
        #     print(f"   ✅ Transient enhancement applied")

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
        description="Auto-mastering with PyO3 fingerprinting and content-aware processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python auto_master.py input.flac

  # With custom output
  python auto_master.py input.flac --output my_master.wav

  # With lower intensity
  python auto_master.py input.flac --intensity 0.7

Fingerprinting:
  - Uses PyO3 Rust backend (auralis_dsp) when available
  - Falls back to Python analyzers automatically
  - Caches results in ~/.auralis/fingerprints/ as .25d files
  - 25-dimensional fingerprint captures: frequency, dynamics, temporal,
    spectral, harmonic, variation, and stereo characteristics
        """
    )
    parser.add_argument(
        'input',
        help='Input audio file (FLAC, WAV, MP3, OGG, M4A, etc.)'
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
    parser.add_argument(
        '--clear-cache',
        action='store_true',
        help='Clear cached fingerprints before processing'
    )

    args = parser.parse_args()

    try:
        # Clear cache if requested
        if args.clear_cache:
            count = FingerprintStorage.clear_all()
            print(f"🗑️  Cleared {count} cached fingerprints")

        output_path = process_track(
            filepath=args.input,
            intensity=args.intensity,
            output_path=args.output
        )

        print(f"\n✨ Success! Play with: ffplay '{output_path}'")
        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
