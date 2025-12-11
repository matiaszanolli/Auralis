# Python DSP Legacy Archive

This directory contains deprecated Python DSP code that has been migrated to the Rust fingerprinting server.

**Why archived?**
- All fingerprinting DSP operations have been migrated to Rust for 5-20x performance improvement
- Python code is now pure orchestration/database/HTTP layer
- Rust server handles all signal processing

**When to use fallback (if Rust server unavailable)?**
1. If fingerprint server crashes and needs manual restart
2. For development/testing without running Rust server
3. For running fingerprinting on isolated systems

---

## Fallback Usage

To re-enable Python DSP fallback (temporary troubleshooting only):

```python
# In fingerprint_extractor.py, change:
# if self.use_rust_server and self._is_rust_server_available():
#     ...
# else:
#     # Use Python fallback
#     from archived.python_dsp_legacy.audio_fingerprint_analyzer import AudioFingerprintAnalyzer
#     fingerprint = self.analyzer.analyze(audio, sr)
```

---

## Archived Modules

### Core Fingerprinting DSP
| File | Purpose | Status |
|------|---------|--------|
| `fingerprint/utilities/temporal_ops.py` | Tempo, rhythm, onset, silence detection | Migrated to Rust |
| `fingerprint/utilities/spectral_ops.py` | Spectral features (centroid, rolloff, flatness) | Migrated to Rust |
| `fingerprint/utilities/variation_ops.py` | Dynamic range variation analysis | Migrated to Rust |
| `audio_fingerprint_analyzer.py` | 25D fingerprint orchestration | Simplified to Rust-only |
| `analysis/loudness_meter.py` | LUFS measurement with K-weighting | Migrated to Rust |
| `analysis/dynamic_range.py` | Dynamic range calculation | Migrated to Rust |

### Harmonics (Partially Archived)
| File | Status | Notes |
|------|--------|-------|
| `fingerprint/utilities/harmonic_ops.py` | KEEP | Thin wrapper around Rust via PyO3 (auralis_dsp) |

### Quality Assessment (Deprecated)
| File | Status | Notes |
|------|--------|-------|
| `quality_assessors/*` | PARTIAL | Many quality metrics depend on DSP; no longer maintained |

---

## Migration Summary

### Removed from Main Code Path (~2000 LOC)
- ❌ librosa.beat.tempo() → Rust onset-based tempo detection
- ❌ librosa.beat.beat_track() → Rust beat tracking
- ❌ librosa.onset.onset_strength() → Rust spectral flux
- ❌ librosa.feature.rms() → Rust RMS envelope
- ❌ scipy FFT/STFT → Rust FFT with rustfft
- ❌ ITU-R BS.1770-4 K-weighting → Rust LUFS calculation
- ❌ Custom frequency band analysis → Rust vectorized extraction
- ❌ All NumPy DSP operations → Rust SIMD vectorization

### Performance Impact

| Operation | Python | Rust | Speedup |
|-----------|--------|------|---------|
| Tempo detection | 100-300ms | 20-50ms | 5-10x |
| STFT + spectral | 50-150ms | 15-40ms | 3-5x |
| LUFS measurement | 30-100ms | 10-30ms | 2-4x |
| Full fingerprint | 1-2 sec | 200-400ms | 5-10x |

---

## Reverting Migration (Emergency Only)

If Rust server is permanently unavailable and Python fallback needed:

1. Copy this archive back to main `auralis/analysis/fingerprint/utilities/`
2. Restore old `audio_fingerprint_analyzer.py` from git history
3. Revert `fingerprint_extractor.py` to use fallback
4. Reinstall dependencies: `pip install librosa resampy`

**Warning**: This reduces throughput to 0.2-0.5 tracks/sec and increases memory usage.

---

## Code Evolution

### Original Architecture (Pre-Migration)
```
Python workers (16) + FFT + librosa + LUFS calculation
  → 0.2-0.5 tracks/sec per worker
  → 3-8 tracks/sec total
  → Heavy dependencies (librosa, resampy, scipy)
```

### Current Architecture (Post-Migration)
```
Python workers (16) + async HTTP → Rust server (32 async + 64 blocking threads)
  → 5-10 tracks/sec per worker
  → 80-160 tracks/sec total
  → Zero Python DSP dependencies for fingerprinting
```

### Potential Future: Pure Rust Everything
```
Rust CLI → Direct fingerprinting (no HTTP)
  → 1000+ tracks/sec possible
  → Single binary, zero external dependencies
```

---

## Files in This Archive

```
archived/python_dsp_legacy/
├── fingerprint/
│   └── utilities/
│       ├── temporal_ops.py       (200 LOC)
│       ├── spectral_ops.py       (190 LOC)
│       ├── variation_ops.py      (250 LOC)
│       └── harmonic_ops.py       (150 LOC - KEEP REFERENCE)
├── analysis/
│   ├── loudness_meter.py         (350 LOC)
│   ├── dynamic_range.py          (200 LOC)
│   └── audio_fingerprint_analyzer.py  (original, 400+ LOC)
├── docs/
│   └── ALGORITHM_REFERENCE.md    (DSP algorithm documentation)
└── ARCHIVE_README.md             (this file)
```

---

## References

- Original DSP algorithms: `docs/ALGORITHM_REFERENCE.md`
- Rust implementation: `fingerprint-server/src/analysis/analyzer.rs`
- Migration plan: `DSP_MIGRATION_PLAN.md`
- Phase 11 fingerprint cache: `auralis/analysis/fingerprint/persistent_cache.py`

---

## Questions?

If Python DSP fallback is needed:
1. Check fingerprint server status first
2. Review `DSP_MIGRATION_PLAN.md` for Rust server requirements
3. Only use archived code as last resort (performance will be much slower)
