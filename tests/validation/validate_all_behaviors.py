"""Final comprehensive test - All 4 Matchering behaviors"""
import numpy as np

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.dsp.basic import rms
from auralis.io.unified_loader import load_audio

TEST_CASES = [
    # BEHAVIOR 1: Heavy Compression
    {
        "name": "Slayer - South of Heaven",
        "behavior": "Heavy Compression (extreme dynamics)",
        "orig": "/mnt/Musica/Musica/Slayer/1988 - South Of Heaven/01. South Of Heaven.flac",
        "ref": "/mnt/audio/Audio/Remasters/Slayer - South Of Heaven/01-South Of Heaven.flac",
    },
    # BEHAVIOR 2: Light Compression
    {
        "name": "Testament - The Preacher",
        "behavior": "Light Compression (loud + dynamic)",
        "orig": "/mnt/Musica/Musica/Testament/Live/2005-Live in London/01 The Preacher.mp3",
        "ref": "/mnt/audio/Audio/Remasters/Testament - Live In London/01 The Preacher.flac",
    },
    # BEHAVIOR 3: Preserve Dynamics
    {
        "name": "Seru Giran - Peperina",
        "behavior": "Preserve Dynamics (classic recording)",
        "orig": "/mnt/Musica/Musica/Serú Girán/Seru Giran - Peperina (1981)/(01) [] Peperina.flac",
        "ref": "/mnt/audio/Audio/Remasters/Seru Giran - Peperina/(01) [] Peperina.flac",
    },
    # BEHAVIOR 4: Expand Dynamics (de-mastering)
    {
        "name": "Motörhead - Terminal Show",
        "behavior": "Expand Dynamics (de-mastering)",
        "orig": "/mnt/Musica/Musica/Motörhead/2004  Inferno/(01) [Motorhead] Terminal Show.flac",
        "ref": "/mnt/audio/Audio/Remasters/Motörhead - Inferno/(01) [Motorhead] Terminal Show.flac",
    },
    {
        "name": "Soda Stereo - Signos",
        "behavior": "Expand Dynamics (moderate de-mastering)",
        "orig": "/mnt/Musica/Musica/Soda Stereo/FLAC/Ruido Blanco/01 Signos.flac",
        "ref": "/mnt/audio/Audio/Remasters/Soda Stereo - Ruido Blanco/01 Signos.flac",
    },
    {
        "name": "Pantera - Strength Beyond Strength",
        "behavior": "Expand Dynamics (heavy de-mastering)",
        "orig": "/mnt/Musica/Musica/Pantera/(1994) Pantera - Far Beyond Driven  (20th Anniversary Deluxe Edition) [16Bit-44.1kHz]/Disc 1/01. Strength Beyond Strength.flac",
        "ref": "/mnt/audio/Audio/Remasters/Pantera - Far Beyond Driven/A1. Strength Beyond Strength.flac",
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
print("FINAL COMPREHENSIVE TEST - ALL 4 MATCHERING BEHAVIORS")
print("=" * 80)
print()

config = UnifiedConfig()
config.set_mastering_preset('adaptive')
processor = HybridProcessor(config)

results = []

for test in TEST_CASES:
    print("=" * 80)
    print(f"{test['name']}")
    print(f"Behavior: {test['behavior']}")
    print("=" * 80)
    
    orig_audio, sr = load_audio(test['orig'])
    ref_audio, _ = load_audio(test['ref'])
    
    orig_peak_db, orig_rms_db, orig_crest = analyze_audio(orig_audio)
    ref_peak_db, ref_rms_db, ref_crest = analyze_audio(ref_audio)
    
    expected_rms_delta = ref_rms_db - orig_rms_db
    expected_crest_delta = ref_crest - orig_crest
    
    print(f"Original: Crest {orig_crest:.2f} dB, RMS {orig_rms_db:.2f} dB")
    print(f"Target:   Crest Δ {expected_crest_delta:+.2f} dB, RMS Δ {expected_rms_delta:+.2f} dB")
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
    
    if rms_error < 1.0 and crest_error < 1.0:
        status = "✅ EXCELLENT"
    elif rms_error < 2.0 and crest_error < 2.0:
        status = "✅ GOOD"
    else:
        status = "⚠️  ACCEPTABLE"
    
    print(f"Status: {status}")
    print()
    
    results.append({
        "name": test['name'],
        "behavior": test['behavior'],
        "rms_error": rms_error,
        "crest_error": crest_error,
        "status": status
    })

print("=" * 80)
print("FINAL SUMMARY - ALL BEHAVIORS")
print("=" * 80)
print(f"Overall Average Crest error: {np.mean([r['crest_error'] for r in results]):.2f} dB")
print(f"Overall Average RMS error:   {np.mean([r['rms_error'] for r in results]):.2f} dB")
print()

# Group by behavior
behaviors = {}
for r in results:
    behavior = r['behavior'].split(' (')[0]  # Get behavior type
    if behavior not in behaviors:
        behaviors[behavior] = []
    behaviors[behavior].append(r)

for behavior_name, tracks in behaviors.items():
    print(f"\n{behavior_name}:")
    for r in tracks:
        print(f"  {r['name']:40s} | Crest: {r['crest_error']:4.2f} dB | RMS: {r['rms_error']:4.2f} dB | {r['status']}")

excellent = len([r for r in results if "EXCELLENT" in r['status']])
good = len([r for r in results if "GOOD" in r['status']])
acceptable = len([r for r in results if "ACCEPTABLE" in r['status']])

print(f"\nResults: {excellent} EXCELLENT, {good} GOOD, {acceptable} ACCEPTABLE (out of {len(results)} total)")
