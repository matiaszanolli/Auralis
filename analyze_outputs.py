#!/usr/bin/env python3
"""Analyze processed audio output quality"""

from auralis.io.unified_loader import load_audio
import numpy as np

files = [
    'examples/demo_acoustic.wav',
    'test_output_adaptive.wav',
    'test_output_gentle.wav',
    'test_output_bright.wav',
    'test_output_punchy.wav',
    'test_output_warm.wav'
]

print('\n📊 Audio Analysis Comparison')
print('=' * 80)
print(f"{'File':<30} {'Peak dB':>12} {'RMS dB':>12} {'Dynamic Range':>15}")
print('-' * 80)

for f in files:
    audio, sr = load_audio(f)
    peak = 20 * np.log10(np.abs(audio).max() + 1e-10)
    rms = 20 * np.log10(np.sqrt(np.mean(audio**2)) + 1e-10)
    dr = peak - rms
    name = f.split('/')[-1].replace('test_output_', '').replace('.wav', '')
    print(f'{name:<30} {peak:>10.2f} dB {rms:>10.2f} dB {dr:>13.2f} dB')

print('=' * 80)
print('\n✅ Analysis complete!')