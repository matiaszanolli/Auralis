"""Comprehensive test of DIY compressor across material types"""
import numpy as np
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.io.unified_loader import load_audio
from auralis.dsp.basic import rms

TEST_CASES = [
    {
        "name": "Slayer - South of Heaven",
        "type": "Extreme dynamics (18.98 dB crest)",
        "orig": "/mnt/Musica/Musica/Slayer/1988 - South Of Heaven/01. South Of Heaven.flac",
        "ref": "/mnt/audio/Audio/Remasters/Slayer - South Of Heaven/01-South Of Heaven.flac",
    },
    {
        "name": "Testament - The Preacher",
        "type": "Loud + dynamic live (12.55 dB crest)",
        "orig": "/mnt/Musica/Musica/Testament/Live/2005-Live in London/01 The Preacher.mp3",
        "ref": "/mnt/audio/Audio/Remasters/Testament - Live In London/01 The Preacher.flac",
    },
    {
        "name": "Static-X - Fix",
        "type": "Under-leveled with good dynamics (12.49 dB crest)",
        "orig": "/mnt/Musica/Musica/Static-X/Wisconsin Death Trip/Fix.mp3",
        "ref": "/mnt/audio/Audio/Remasters/Static-X - Wisconsin Death Trip/Fix.flac",
    },
    {
        "name": "Iron Maiden - Aces High",
        "type": "Over-compressed modern remaster (11.86 dB crest)",
        "orig": "/mnt/Musica/Musica/Iron Maiden/2008 - Somewhere Back In Time - The Best Of 1980-1989/04 - Aces High.mp3",
        "ref": "/mnt/audio/Audio/Remasters/Iron Maiden - Somewhere Back In Time/04. Aces High.flac",
    },
]

def analyze_audio(audio):
    """Analyze audio and return metrics"""
    mono = np.mean(audio, axis=1) if audio.ndim == 2 else audio
    peak = np.max(np.abs(mono))
    rms_val = rms(mono)
    peak_db = 20 * np.log10(peak)
    rms_db = 20 * np.log10(rms_val)
    crest = peak_db - rms_db
    return peak_db, rms_db, crest

print("=" * 80)
print("COMPREHENSIVE DIY COMPRESSOR TEST")
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
    
    # Load audio
    orig_audio, sr = load_audio(test['orig'])
    ref_audio, _ = load_audio(test['ref'])
    
    # Analyze
    orig_peak_db, orig_rms_db, orig_crest = analyze_audio(orig_audio)
    ref_peak_db, ref_rms_db, ref_crest = analyze_audio(ref_audio)
    
    expected_rms_delta = ref_rms_db - orig_rms_db
    expected_crest_delta = ref_crest - orig_crest
    
    print(f"ORIGINAL: Peak: {orig_peak_db:.2f} dB, RMS: {orig_rms_db:.2f} dB, Crest: {orig_crest:.2f} dB")
    print(f"TARGET:   Peak: {ref_peak_db:.2f} dB, RMS: {ref_rms_db:.2f} dB, Crest: {ref_crest:.2f} dB")
    print(f"Expected: RMS Δ {expected_rms_delta:+.2f} dB, Crest Δ {expected_crest_delta:+.2f} dB")
    print()
    
    # Process
    processed = processor.process(orig_audio)
    
    # Analyze result
    proc_peak_db, proc_rms_db, proc_crest = analyze_audio(processed)
    
    result_rms_delta = proc_rms_db - orig_rms_db
    result_crest_delta = proc_crest - orig_crest
    
    rms_error = abs(result_rms_delta - expected_rms_delta)
    crest_error = abs(result_crest_delta - expected_crest_delta)
    
    print()
    print(f"RESULT:   Peak: {proc_peak_db:.2f} dB, RMS: {proc_rms_db:.2f} dB, Crest: {proc_crest:.2f} dB")
    print(f"Result:   RMS Δ {result_rms_delta:+.2f} dB, Crest Δ {result_crest_delta:+.2f} dB")
    print(f"RMS error: {rms_error:.2f} dB, Crest error: {crest_error:.2f} dB")
    
    if rms_error < 1.0:
        status = "✅ EXCELLENT"
    elif rms_error < 2.0:
        status = "✅ GOOD"
    else:
        status = "⚠️  ACCEPTABLE"
    
    print(f"Status: {status}")
    print()
    
    results.append({
        "name": test['name'],
        "type": test['type'],
        "rms_error": rms_error,
        "crest_error": crest_error,
        "status": status
    })

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Average RMS error: {np.mean([r['rms_error'] for r in results]):.2f} dB")
print(f"Average Crest error: {np.mean([r['crest_error'] for r in results]):.2f} dB")
print()
for r in results:
    print(f"{r['name']:40s} RMS: {r['rms_error']:.2f} dB, Crest: {r['crest_error']:.2f} dB - {r['status']}")
