#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Phase 2.5.2A: Generate A/B Test Audio Files

Processes reference fingerprints with both fingerprint-based parameters and manual
presets, generating WAV files for blind listening tests.

Usage:
    python scripts/generate_ab_test_audio.py

Output:
    - 8 WAV files (4 genres × 2 methods) in tests/audio/ab_test_files/
    - Metadata JSON tracking A/B identities
    - Summary report of generated files

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import json
import os
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import soundfile as sf

from auralis.analysis.fingerprint.parameter_mapper import ParameterMapper
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig


class ManualMasteringPresets:
    """Manual mastering presets for A/B comparison"""

    @staticmethod
    def get_vocal_pop_preset(target_lufs: float = -16.0) -> Dict:
        """Bright, clear vocal preset"""
        return {
            'eq': {
                'gains': {
                    0: -2.0,   # Sub-bass: slight cut
                    1: -1.5,   # Bass
                    2: -1.0,   # Low-mid
                    3: 0.0,    # Low-mid
                    4: 0.5,    # Mid-bass
                    5: 1.5,    # Mid
                    6: 2.0,    # Upper-mid
                    7: 3.5,    # Presence (3kHz)
                    8: 2.5,    # Presence
                    9: 1.5,    # Air start
                    10: 2.0,   # Air
                    11: 1.5,   # Air
                    12: 0.5,   # High air
                    13: -0.5,  # Highest
                    14: -1.0,  # Highest
                    15: -1.5,  # Extreme high
                    16: -1.0,
                    17: -0.5,
                    18: 0.0,
                    19: 0.0,
                    20: 0.0,
                    21: 0.0,
                    22: 0.0,
                    23: -0.5,
                    24: -1.0,
                    25: -1.5,
                    26: -2.0,
                    27: -2.5,
                    28: -3.0,
                    29: -3.5,
                }
            },
            'dynamics': {
                'standard': {
                    'ratio': 2.5,
                    'threshold': -10.0,
                    'attack_ms': 20.0,
                    'release_ms': 100.0,
                }
            },
            'level': {
                'target_lufs': target_lufs,
                'gain_adjustment': 0.0,
            }
        }

    @staticmethod
    def get_bass_heavy_preset(target_lufs: float = -16.0) -> Dict:
        """Deep, punchy bass-focused preset"""
        return {
            'eq': {
                'gains': {
                    0: 4.0,    # Sub-bass boost
                    1: 3.5,    # Bass boost
                    2: 2.0,    # Low-mid
                    3: 1.0,    # Low-mid
                    4: 0.5,    # Mid-bass
                    5: -0.5,   # Mid
                    6: -1.0,   # Upper-mid
                    7: -1.5,   # Presence scoop
                    8: -1.0,   # Presence
                    9: -0.5,   # Air
                    10: 0.0,   # Air
                    11: 0.5,   # Air
                    12: 1.0,   # High air
                    13: 0.5,   # Highest
                    14: 0.0,
                    15: -0.5,
                    16: -1.0,
                    17: -1.5,
                    18: -1.0,
                    19: -0.5,
                    20: 0.0,
                    21: 0.0,
                    22: -0.5,
                    23: -1.0,
                    24: -1.5,
                    25: -2.0,
                    26: -2.5,
                    27: -3.0,
                    28: -3.5,
                    29: -4.0,
                }
            },
            'dynamics': {
                'standard': {
                    'ratio': 3.0,
                    'threshold': -12.0,
                    'attack_ms': 15.0,
                    'release_ms': 80.0,
                }
            },
            'level': {
                'target_lufs': target_lufs,
                'gain_adjustment': 0.0,
            }
        }

    @staticmethod
    def get_bright_acoustic_preset(target_lufs: float = -16.0) -> Dict:
        """Natural, open acoustic preset"""
        return {
            'eq': {
                'gains': {
                    0: -0.5,   # Sub-bass: minimal
                    1: 0.0,    # Bass
                    2: 0.5,    # Low-mid
                    3: 1.0,    # Low-mid
                    4: 0.5,    # Mid-bass
                    5: 0.0,    # Mid
                    6: 0.5,    # Upper-mid
                    7: 1.0,    # Presence
                    8: 1.5,    # Presence
                    9: 2.0,    # Air
                    10: 2.5,   # Air
                    11: 2.0,   # Air
                    12: 1.5,   # High air
                    13: 1.0,   # Highest
                    14: 0.5,
                    15: 0.0,
                    16: -0.5,
                    17: -1.0,
                    18: -1.5,
                    19: -1.0,
                    20: -0.5,
                    21: 0.0,
                    22: 0.0,
                    23: 0.5,
                    24: 0.0,
                    25: -0.5,
                    26: -1.0,
                    27: -1.5,
                    28: -2.0,
                    29: -2.5,
                }
            },
            'dynamics': {
                'standard': {
                    'ratio': 2.0,
                    'threshold': -14.0,
                    'attack_ms': 30.0,
                    'release_ms': 120.0,
                }
            },
            'level': {
                'target_lufs': target_lufs,
                'gain_adjustment': 0.0,
            }
        }

    @staticmethod
    def get_electronic_preset(target_lufs: float = -16.0) -> Dict:
        """Smooth, glued electronic preset"""
        return {
            'eq': {
                'gains': {
                    0: 1.0,    # Sub-bass
                    1: 1.5,    # Bass
                    2: 1.0,    # Low-mid
                    3: 0.5,    # Low-mid
                    4: 0.0,    # Mid-bass
                    5: -0.5,   # Mid
                    6: 0.0,    # Upper-mid
                    7: 0.5,    # Presence
                    8: 0.5,    # Presence
                    9: 0.0,    # Air
                    10: 0.0,   # Air
                    11: 0.0,   # Air
                    12: 0.0,   # High air
                    13: 0.0,   # Highest
                    14: 0.0,
                    15: 0.0,
                    16: 0.0,
                    17: 0.0,
                    18: 0.0,
                    19: 0.0,
                    20: 0.0,
                    21: 0.0,
                    22: 0.0,
                    23: 0.0,
                    24: 0.0,
                    25: 0.0,
                    26: 0.0,
                    27: 0.0,
                    28: 0.0,
                    29: 0.0,
                }
            },
            'dynamics': {
                'standard': {
                    'ratio': 1.8,
                    'threshold': -16.0,
                    'attack_ms': 50.0,
                    'release_ms': 150.0,
                }
            },
            'level': {
                'target_lufs': target_lufs,
                'gain_adjustment': 0.0,
            }
        }

    @staticmethod
    def get_preset(genre: str, target_lufs: float = -16.0) -> Dict:
        """Get preset for specified genre"""
        presets = {
            'vocal_pop': ManualMasteringPresets.get_vocal_pop_preset,
            'bass_heavy': ManualMasteringPresets.get_bass_heavy_preset,
            'bright_acoustic': ManualMasteringPresets.get_bright_acoustic_preset,
            'electronic': ManualMasteringPresets.get_electronic_preset,
        }
        return presets[genre](target_lufs)


def generate_test_audio_profiles() -> Dict[str, Tuple[np.ndarray, int]]:
    """Generate test audio samples matching fingerprint characteristics"""
    sr = 44100
    duration_seconds = 3
    samples = sr * duration_seconds

    profiles = {}

    # Vocal pop: smooth, dynamic vocal with bright presence
    t = np.linspace(0, duration_seconds, samples, False)
    vocal = 0.3 * np.sin(2 * np.pi * 200 * t)  # Fundamental
    vocal += 0.15 * np.sin(2 * np.pi * 400 * t)  # 2nd harmonic
    vocal += 0.1 * np.sin(2 * np.pi * 2500 * t)  # Presence peak
    vocal += 0.05 * np.random.randn(samples)  # Slight noise
    # Add dynamic envelope
    envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 0.5 * t)
    profiles['vocal_pop'] = (vocal * envelope * 0.3).astype(np.float32), sr

    # Bass heavy: heavy low-end with controlled dynamics
    bass = 0.4 * np.sin(2 * np.pi * 60 * t)  # Sub-bass
    bass += 0.25 * np.sin(2 * np.pi * 150 * t)  # Bass
    bass += 0.1 * np.sin(2 * np.pi * 1000 * t)  # Mid for definition
    envelope = 0.7 + 0.3 * np.sin(2 * np.pi * 1.0 * t)
    profiles['bass_heavy'] = (bass * envelope * 0.25).astype(np.float32), sr

    # Bright acoustic: high-frequency rich with varied dynamics
    acoustic = 0.2 * np.sin(2 * np.pi * 300 * t)  # Fundamental
    acoustic += 0.15 * np.sin(2 * np.pi * 800 * t)  # Warmth
    acoustic += 0.2 * np.sin(2 * np.pi * 4000 * t)  # Presence
    acoustic += 0.15 * np.sin(2 * np.pi * 8000 * t)  # Air
    acoustic += 0.08 * np.random.randn(samples)  # String noise
    envelope = 0.4 + 0.6 * np.sin(2 * np.pi * 0.3 * t)
    profiles['bright_acoustic'] = (acoustic * envelope * 0.28).astype(np.float32), sr

    # Electronic: punchy, compressed with minimal dynamics
    electronic = 0.35 * np.sin(2 * np.pi * 80 * t)  # Bass synth
    electronic += 0.2 * np.sin(2 * np.pi * 2000 * t)  # Lead synth
    electronic = np.clip(electronic, -0.4, 0.4)  # Slight saturation
    # Minimal envelope - electronic is typically compressed
    profiles['electronic'] = (electronic * 0.4).astype(np.float32), sr

    return profiles


def get_test_fingerprints() -> Dict[str, Dict]:
    """Reference fingerprints from test framework"""
    return {
        'vocal_pop': {
            'sub_bass_pct': 0.08,
            'bass_pct': 0.18,
            'low_mid_pct': 0.16,
            'mid_pct': 0.22,
            'upper_mid_pct': 0.18,
            'presence_pct': 0.12,
            'air_pct': 0.06,
            'lufs': -12.5,
            'crest_db': 7.5,
            'bass_mid_ratio': 0.9,
            'harmonic_ratio': 0.75,
            'pitch_stability': 0.85,
            'chroma_energy': 0.70,
            'spectral_centroid': 3000.0,
            'spectral_rolloff': 9000.0,
            'spectral_flatness': 0.4,
            'loudness_variation_std': 1.5,
            'dynamic_range_variation': 2.0,
            'peak_consistency': 0.90,
            'tempo_bpm': 100.0,
            'rhythm_stability': 0.88,
            'transient_density': 3.0,
            'silence_ratio': 0.05,
            'stereo_width': 0.65,
            'phase_correlation': 0.85,
        },
        'bass_heavy': {
            'sub_bass_pct': 0.20,
            'bass_pct': 0.28,
            'low_mid_pct': 0.16,
            'mid_pct': 0.18,
            'upper_mid_pct': 0.10,
            'presence_pct': 0.05,
            'air_pct': 0.03,
            'lufs': -11.0,
            'crest_db': 9.0,
            'bass_mid_ratio': 1.6,
            'harmonic_ratio': 0.65,
            'pitch_stability': 0.78,
            'chroma_energy': 0.55,
            'spectral_centroid': 1800.0,
            'spectral_rolloff': 6000.0,
            'spectral_flatness': 0.35,
            'loudness_variation_std': 2.0,
            'dynamic_range_variation': 2.5,
            'peak_consistency': 0.85,
            'tempo_bpm': 90.0,
            'rhythm_stability': 0.82,
            'transient_density': 2.5,
            'silence_ratio': 0.03,
            'stereo_width': 0.50,
            'phase_correlation': 0.92,
        },
        'bright_acoustic': {
            'sub_bass_pct': 0.05,
            'bass_pct': 0.12,
            'low_mid_pct': 0.15,
            'mid_pct': 0.18,
            'upper_mid_pct': 0.18,
            'presence_pct': 0.18,
            'air_pct': 0.14,
            'lufs': -14.0,
            'crest_db': 10.5,
            'bass_mid_ratio': 0.6,
            'harmonic_ratio': 0.80,
            'pitch_stability': 0.90,
            'chroma_energy': 0.75,
            'spectral_centroid': 4200.0,
            'spectral_rolloff': 13000.0,
            'spectral_flatness': 0.45,
            'loudness_variation_std': 2.5,
            'dynamic_range_variation': 3.0,
            'peak_consistency': 0.80,
            'tempo_bpm': 110.0,
            'rhythm_stability': 0.85,
            'transient_density': 4.5,
            'silence_ratio': 0.10,
            'stereo_width': 0.75,
            'phase_correlation': 0.88,
        },
        'electronic': {
            'sub_bass_pct': 0.18,
            'bass_pct': 0.22,
            'low_mid_pct': 0.14,
            'mid_pct': 0.16,
            'upper_mid_pct': 0.12,
            'presence_pct': 0.10,
            'air_pct': 0.08,
            'lufs': -13.0,
            'crest_db': 6.5,
            'bass_mid_ratio': 1.2,
            'harmonic_ratio': 0.50,
            'pitch_stability': 0.65,
            'chroma_energy': 0.40,
            'spectral_centroid': 2500.0,
            'spectral_rolloff': 10000.0,
            'spectral_flatness': 0.50,
            'loudness_variation_std': 1.0,
            'dynamic_range_variation': 1.5,
            'peak_consistency': 0.95,
            'tempo_bpm': 128.0,
            'rhythm_stability': 0.92,
            'transient_density': 2.0,
            'silence_ratio': 0.01,
            'stereo_width': 0.60,
            'phase_correlation': 0.80,
        },
    }


def main():
    """Generate A/B test audio files"""
    print("\n" + "="*70)
    print("Phase 2.5.2A: Generating A/B Test Audio Files")
    print("="*70 + "\n")

    # Setup
    output_dir = Path("tests/audio/ab_test_files")
    output_dir.mkdir(parents=True, exist_ok=True)

    mapper = ParameterMapper()
    config = UnifiedConfig()
    config.set_processing_mode('adaptive')
    processor = HybridProcessor(config)

    # Get fingerprints and audio
    fingerprints = get_test_fingerprints()
    audio_profiles = generate_test_audio_profiles()
    target_lufs = -16.0

    # Track which method is A and which is B (randomized)
    metadata = {
        'test_date': datetime.now().isoformat(),
        'target_lufs': target_lufs,
        'genres': {},
        'randomization_seed': None,  # Will be set
    }

    # Randomize A/B assignment once
    random.seed(42)  # For reproducibility
    metadata['randomization_seed'] = 42

    file_counter = 0
    genre_results = {}

    for genre in ['vocal_pop', 'bass_heavy', 'bright_acoustic', 'electronic']:
        print(f"\n{'='*70}")
        print(f"Processing: {genre.upper()}")
        print(f"{'='*70}")

        fingerprint = fingerprints[genre]
        audio_data, sr = audio_profiles[genre]

        # Generate fingerprint-based parameters
        fp_params = mapper.generate_mastering_parameters(fingerprint, target_lufs=target_lufs)
        print(f"✓ Fingerprint parameters generated")
        print(f"  EQ: {np.mean(list(fp_params['eq']['gains'].values())):.2f} dB avg")
        print(f"  Compression: {fp_params['dynamics']['standard']['ratio']:.1f}:1 @ {fp_params['dynamics']['standard']['threshold']:.1f} dB")

        # Get manual preset parameters
        preset_params = ManualMasteringPresets.get_preset(genre, target_lufs=target_lufs)
        print(f"✓ Manual preset parameters selected")
        print(f"  EQ: {np.mean(list(preset_params['eq']['gains'].values())):.2f} dB avg")
        print(f"  Compression: {preset_params['dynamics']['standard']['ratio']:.1f}:1 @ {preset_params['dynamics']['standard']['threshold']:.1f} dB")

        # Process with both methods
        print(f"\nProcessing audio with both methods...")

        # Process with fingerprint parameters
        fp_processed = processor.process(audio_data.copy(), fp_params)
        fp_processed = np.clip(fp_processed, -1.0, 1.0)  # Prevent clipping

        # Process with preset parameters
        preset_processed = processor.process(audio_data.copy(), preset_params)
        preset_processed = np.clip(preset_processed, -1.0, 1.0)  # Prevent clipping

        print(f"✓ Audio processed with both methods")

        # Randomize A/B assignment for this genre
        # A = Fingerprint, B = Preset (but randomize which file gets which label)
        if random.random() > 0.5:
            a_audio, a_method = fp_processed, 'fingerprint'
            b_audio, b_method = preset_processed, 'preset'
            print(f"  Randomization: A=fingerprint, B=preset")
        else:
            a_audio, a_method = preset_processed, 'preset'
            b_audio, b_method = fp_processed, 'fingerprint'
            print(f"  Randomization: A=preset, B=fingerprint")

        # Save files with anonymized names
        a_filename = f"{file_counter + 1:02d}_test_{genre}_A.wav"
        b_filename = f"{file_counter + 2:02d}_test_{genre}_B.wav"

        sf.write(output_dir / a_filename, a_audio, sr, subtype='PCM_24')
        sf.write(output_dir / b_filename, b_audio, sr, subtype='PCM_24')

        print(f"✓ Files saved:")
        print(f"  {a_filename}")
        print(f"  {b_filename}")

        # Record metadata
        metadata['genres'][genre] = {
            'fingerprint': {
                'spectral_centroid': fingerprint['spectral_centroid'],
                'bass_mid_ratio': fingerprint['bass_mid_ratio'],
                'lufs': fingerprint['lufs'],
            },
            'a_file': a_filename,
            'a_method': a_method,
            'b_file': b_filename,
            'b_method': b_method,
            'parameters_fingerprint': {
                'eq_average_gain': float(np.mean(list(fp_params['eq']['gains'].values()))),
                'compression_ratio': float(fp_params['dynamics']['standard']['ratio']),
                'compression_threshold': float(fp_params['dynamics']['standard']['threshold']),
                'attack_ms': float(fp_params['dynamics']['standard']['attack_ms']),
                'release_ms': float(fp_params['dynamics']['standard']['release_ms']),
            },
            'parameters_preset': {
                'eq_average_gain': float(np.mean(list(preset_params['eq']['gains'].values()))),
                'compression_ratio': float(preset_params['dynamics']['standard']['ratio']),
                'compression_threshold': float(preset_params['dynamics']['standard']['threshold']),
                'attack_ms': float(preset_params['dynamics']['standard']['attack_ms']),
                'release_ms': float(preset_params['dynamics']['standard']['release_ms']),
            },
        }

        genre_results[genre] = {
            'fingerprint_eq_avg': np.mean(list(fp_params['eq']['gains'].values())),
            'preset_eq_avg': np.mean(list(preset_params['eq']['gains'].values())),
        }

        file_counter += 2

    # Save metadata
    metadata_file = output_dir / "ab_test_metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"\n✓ Metadata saved: {metadata_file}")

    # Print summary
    print("\n" + "="*70)
    print("SUMMARY: A/B Test Audio Generation")
    print("="*70)
    print(f"\nGenerated Files: 8 WAV files (4 genres × 2 methods)")
    print(f"Location: {output_dir}")
    print(f"Format: 24-bit PCM, 44.1 kHz, 3 seconds each")
    print(f"\nGenre Comparison (EQ Average Gain):")
    print(f"{'Genre':<20} {'Fingerprint':<15} {'Preset':<15} {'Difference':<15}")
    print(f"{'-'*65}")
    for genre, results in genre_results.items():
        diff = results['fingerprint_eq_avg'] - results['preset_eq_avg']
        print(f"{genre:<20} {results['fingerprint_eq_avg']:>6.2f} dB       "
              f"{results['preset_eq_avg']:>6.2f} dB       {diff:>6.2f} dB")

    print(f"\n✅ Phase 2.5.2A COMPLETE")
    print(f"Next: Recruit 3-5 mastering engineers for listening tests")
    print(f"      Prepare randomized A/B testing instructions")
    print(f"      (See PHASE25_2_LISTENING_TESTS.md for full procedure)\n")


if __name__ == '__main__':
    main()
