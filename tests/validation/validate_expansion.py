"""Test expansion on all de-mastering cases"""
import numpy as np

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.dsp.basic import rms
from auralis.io.unified_loader import load_audio

TEST_CASES = [
    {
        "name": "Pantera - Strength Beyond Strength",
        "type": "Very compressed (DR 0.35, crest 11.30)",
        "orig": "/mnt/Musica/Musica/Pantera/(1994) Pantera - Far Beyond Driven  (20th Anniversary Deluxe Edition) [16Bit-44.1kHz]/Disc 1/01. Strength Beyond Strength.flac",
        "ref": "/mnt/audio/Audio/Remasters/Pantera - Far Beyond Driven/A1. Strength Beyond Strength.flac",
    },
    {
        "name": "Motörhead - Terminal Show",
        "type": "Very compressed (DR 0.37, crest 11.57)",
        "orig": "/mnt/Musica/Musica/Motörhead/2004  Inferno/(01) [Motorhead] Terminal Show.flac",
        "ref": "/mnt/audio/Audio/Remasters/Motörhead - Inferno/(01) [Motorhead] Terminal Show.flac",
    },
    {
        "name": "Soda Stereo - Signos",
        "type": "Moderately compressed (DR 0.73, crest 15.14)",
        "orig": "/mnt/Musica/Musica/Soda Stereo/FLAC/Ruido Blanco/01 Signos.flac",
        "ref": "/mnt/audio/Audio/Remasters/Soda Stereo - Ruido Blanco/01 Signos.flac",
    },
]

def analyze_audio(audio):
    mono = np.mean(audio, axis=1) if audio.ndim == 2 else audio
    peak = np.max(np.abs(mono))
    rms_val = rms(mono)
    peak_db = 20 * np.log10(peak)
    rms_db = 20 * np.log10(rms_val)
    crest = peak_db - rms_db
    return peak_db, rms_db, crest

print("=" * 80)
print("DYNAMICS EXPANSION TEST (De-mastering)")
print("=" * 80)
print()

config = UnifiedConfig()
config.set_mastering_preset('adaptive')
processor = HybridProcessor(config)

results = []

for test in TEST_CASES:
    print("=" * 80)
    print(f"{test['name']}")
    print(f"Type: {test['type']}")
    print("=" * 80)
    
    orig_audio, sr = load_audio(test['orig'])
    ref_audio, _ = load_audio(test['ref'])
    
    orig_peak_db, orig_rms_db, orig_crest = analyze_audio(orig_audio)
    ref_peak_db, ref_rms_db, ref_crest = analyze_audio(ref_audio)
    
    expected_rms_delta = ref_rms_db - orig_rms_db
    expected_crest_delta = ref_crest - orig_crest
    
    print(f"Expected: Crest Δ {expected_crest_delta:+.2f} dB, RMS Δ {expected_rms_delta:+.2f} dB")
    print()
    
    processed = processor.process(orig_audio)
    
    proc_peak_db, proc_rms_db, proc_crest = analyze_audio(processed)
    
    result_rms_delta = proc_rms_db - orig_rms_db
    result_crest_delta = proc_crest - orig_crest
    
    rms_error = abs(result_rms_delta - expected_rms_delta)
    crest_error = abs(result_crest_delta - expected_crest_delta)
    
    print()
    print(f"Result:   Crest Δ {result_crest_delta:+.2f} dB, RMS Δ {result_rms_delta:+.2f} dB")
    print(f"Errors:   Crest: {crest_error:.2f} dB, RMS: {rms_error:.2f} dB")
    
    if rms_error < 2.0 and crest_error < 2.0:
        status = "✅ GOOD"
    else:
        status = "⚠️  ACCEPTABLE"
    
    print(f"Status: {status}")
    print()
    
    results.append({
        "name": test['name'],
        "rms_error": rms_error,
        "crest_error": crest_error,
        "expected_crest_delta": expected_crest_delta,
        "result_crest_delta": result_crest_delta
    })

print("=" * 80)
print("EXPANSION SUMMARY")
print("=" * 80)
print(f"Average Crest error: {np.mean([r['crest_error'] for r in results]):.2f} dB")
print(f"Average RMS error: {np.mean([r['rms_error'] for r in results]):.2f} dB")
print()
for r in results:
    print(f"{r['name']:40s} | Target: {r['expected_crest_delta']:+5.2f} dB | Result: {r['result_crest_delta']:+5.2f} dB | Error: {r['crest_error']:4.2f} dB")
