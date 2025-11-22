#!/usr/bin/env python3
"""Quick test of Slayer and Iron Maiden"""

import sys
import numpy as np
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.io.unified_loader import load_audio
from auralis.dsp.basic import rms

# Test cases with verified paths
tests = [
    ('Slayer - South of Heaven',
     '/mnt/Musica/Musica/Slayer/1988 - South Of Heaven/01. South Of Heaven.flac',
     '/mnt/audio/Audio/Remasters/Slayer - South Of Heaven/01-South Of Heaven.flac'),

    ('Iron Maiden - Aces High',
     '/mnt/Musica/Musica/Iron Maiden/1984 - Powerslave [FLAC 24-bit 96kHz]/01. Aces High.flac',
     '/mnt/audio/Audio/Remasters/Iron Maiden - Powerslave/01. Aces High.flac'),
]

results = []

for name, orig_path, ref_path in tests:
    print()
    print('='*70)
    print(name)
    print('='*70)

    try:
        # Load
        orig_audio, _ = load_audio(orig_path)
        orig_mono = np.mean(orig_audio, axis=1) if orig_audio.ndim == 2 else orig_audio

        ref_audio, _ = load_audio(ref_path)
        ref_mono = np.mean(ref_audio, axis=1) if ref_audio.ndim == 2 else ref_audio

        # Analyze
        orig_rms_db = 20 * np.log10(rms(orig_mono))
        ref_rms_db = 20 * np.log10(rms(ref_mono))
        expected = ref_rms_db - orig_rms_db

        print(f'Expected: RMS Δ {expected:+.2f} dB')

        # Process
        config = UnifiedConfig()
        config.set_mastering_preset('adaptive')
        processor = HybridProcessor(config)
        processed = processor.process(orig_audio)

        proc_mono = np.mean(processed, axis=1) if processed.ndim == 2 else processed
        proc_rms_db = 20 * np.log10(rms(proc_mono))
        result = proc_rms_db - orig_rms_db

        error = abs(result - expected)

        print(f'Result:   RMS Δ {result:+.2f} dB')
        print(f'Error:    {error:.2f} dB')

        if error < 1.0:
            status = '✅ EXCELLENT'
        elif error < 2.0:
            status = '✅ GOOD'
        else:
            status = '⚠️  ACCEPTABLE'

        print(status)
        results.append((name, error))

    except Exception as e:
        print(f'❌ ERROR: {e}')
        import traceback
        traceback.print_exc()

print()
print('='*70)
print('SUMMARY')
print('='*70)
if results:
    avg = np.mean([r[1] for r in results])
    print(f'Average error: {avg:.2f} dB')
    for name, error in results:
        print(f'  {name:40s}: {error:.2f} dB')
