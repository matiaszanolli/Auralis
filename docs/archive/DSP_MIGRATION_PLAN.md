# DSP Migration Plan: Python → Rust Server

**Goal**: Migrate all Digital Signal Processing logic from Python to Rust fingerprinting server. Python becomes pure orchestration/database layer.

**Current Status**: ~75+ DSP operations in Python; 3 partially in Rust (HPSS, YIN, Chroma)

**Target**: All 25D fingerprint dimensions computed in Rust server; Python only handles HTTP requests, database storage, caching

---

## Architecture Transition

### Current (Mixed, Inefficient)
```
Python Worker Thread
  ├─ extract_and_store()
  │  ├─ Try Rust server via HTTP (requests lib - SYNCHRONOUS!)
  │  │  ├─ Load audio (Rust)
  │  │  ├─ Compute FFT, STFT, etc (Rust)
  │  │  └─ Return 25D fingerprint
  │  └─ Fall back to Python analyzer if server unavailable
  │     ├─ load_audio() [Python]
  │     ├─ analyze() [Python]
  │     │  ├─ FFT spectrum (Python NumPy)
  │     │  ├─ STFT analysis (Python NumPy)
  │     │  ├─ Tempo detection (librosa)
  │     │  ├─ Onset detection (librosa)
  │     │  ├─ HPSS/YIN/Chroma (Rust module)
  │     │  ├─ LUFS measurement (Python)
  │     │  ├─ Dynamics analysis (Python)
  │     │  └─ Variation analysis (Python)
  │     └─ Store fingerprint
```

**Problems**:
- Synchronous HTTP requests block worker threads (no parallelism)
- FFT, STFT computed twice (Python fallback + Rust)
- Duplicated code across Python DSP modules
- Bottleneck: Librosa operations (tempo, onset) in Python

### Target (Rust-Centric, Efficient)
```
Python Worker Thread
  └─ extract_and_store()
     ├─ Async HTTP POST to Rust server
     │  └─ Complete 25D fingerprint analysis (NO fallback)
     │     ├─ Load audio
     │     ├─ Compute FFT/STFT once
     │     ├─ Extract all 25 dimensions
     │     └─ Return complete fingerprint
     └─ Store in database + sidecar

Python is stateless for DSP:
  - No librosa calls
  - No FFT/STFT
  - No tempo detection
  - No dynamics analysis
  - Only: HTTP client + database + orchestration
```

**Benefits**:
- Async HTTP requests (true parallelism)
- Single FFT per fingerprint (not duplicated)
- No Python DSP code to maintain
- Rust optimizations (vectorization, SIMD)
- 5-20x overall speedup potential

---

## Migration Phases

### Phase 0: Async HTTP Client (IMMEDIATE)
**Task**: Replace synchronous `requests` with async `aiohttp`
- **Files**: `fingerprint_extractor.py`
- **Impact**: Enables concurrent HTTP requests from worker threads
- **Status**: IN PROGRESS (partial implementation)

### Phase 1: Rust Server DSP Extension (CRITICAL)
**Task**: Extend Rust server to compute all 25D fingerprint dimensions

**Rust server must implement**:
1. ✅ Audio loading (Symphonia) - DONE
2. ✅ FFT/STFT - DONE (for Rust server analysis)
3. ❌ Frequency band analysis (7D)
4. ❌ Dynamics analysis (3D) - LUFS, crest, bass/mid
5. ❌ Temporal analysis (4D) - tempo, rhythm, transient, silence
6. ❌ Spectral analysis (3D) - centroid, rolloff, flatness
7. ✅ Harmonic analysis (3D) - HPSS, YIN, Chroma (via PyO3)
8. ❌ Variation analysis (3D)
9. ❌ Stereo analysis (2D)

**Current Rust server analysis**:
- `fingerprint-server/src/analysis/analyzer.rs:10-81`
- Only returns `Fingerprint::default()` with empty fields
- **Needed**: Implement analyze_frequency, analyze_dynamics, analyze_temporal, etc.

**Estimate**: 400-600 LOC additions to `analyzer.rs`

### Phase 2: Python Analyzer Simplification
**Task**: Remove all DSP code from Python analyzers

**Files to Archive**:
```
auralis/analysis/fingerprint/utilities/
  ├─ temporal_ops.py (REMOVE - move to Rust)
  ├─ spectral_ops.py (REMOVE - move to Rust)
  ├─ variation_ops.py (REMOVE - move to Rust)
  ├─ harmonic_ops.py (KEEP - thin wrapper around auralis_dsp)
  └─ dsp_backend.py (KEEP - Rust module dispatcher)

auralis/analysis/loudness_meter.py (REMOVE - move to Rust)
auralis/analysis/dynamic_range.py (REMOVE - move to Rust)

auralis/core/hybrid_processor.py (KEEP - enhancement only, not fingerprinting)
auralis/dsp/ (KEEP - audio enhancement, not fingerprinting)
```

**Files to Refactor**:
```
auralis/analysis/fingerprint/audio_fingerprint_analyzer.py
  - Remove: All analyze_* methods
  - Keep: Caching logic, sampling strategy
  - New: Pure orchestration (call Rust server only)

auralis/library/fingerprint_extractor.py
  - Replace: requests → aiohttp (async)
  - Remove: Python analyzer fallback option
  - New: Async HTTP only, no local DSP
```

**Estimate**: 200-300 LOC removed, 100-150 LOC refactored

### Phase 3: Integration & Testing
**Task**: Test end-to-end fingerprinting with Rust-only backend

**Tests**:
- [ ] Single track fingerprinting via Rust server
- [ ] 50-track batch fingerprinting (concurrency test)
- [ ] Performance comparison (Python DSP vs Rust)
- [ ] Fingerprint stability (same audio = same fingerprint)
- [ ] Cache hit/miss rates

### Phase 4: Cleanup & Documentation
**Task**: Archive old Python DSP code, update docs

**Archive to**:
```
archived/python_dsp_legacy/
  ├─ temporal_ops.py
  ├─ spectral_ops.py
  ├─ variation_ops.py
  ├─ old_audio_fingerprint_analyzer.py
  ├─ loudness_meter.py
  └─ README.md (why archived, when to use)
```

---

## Files Breakdown

### REMOVE (Archive to `archived/`)
| File | Lines | Reason | Archive? |
|------|-------|--------|----------|
| `auralis/analysis/fingerprint/utilities/temporal_ops.py` | ~200 | Tempo, rhythm, onset, silence (moving to Rust) | YES |
| `auralis/analysis/fingerprint/utilities/spectral_ops.py` | ~190 | Spectral features (moving to Rust) | YES |
| `auralis/analysis/fingerprint/utilities/variation_ops.py` | ~250 | Dynamic range variation (moving to Rust) | YES |
| `auralis/analysis/loudness_meter.py` | ~350 | LUFS + K-weighting (moving to Rust) | YES |
| `auralis/analysis/dynamic_range.py` | ~200 | DR calculation (moving to Rust) | YES |
| `auralis/analysis/quality_assessors/` | ~800 | Quality metrics (depend on DSP) | PARTIAL |

**Total**: ~2000 LOC to be removed/archived

### REFACTOR (Simplify)
| File | Current Lines | New Lines | Changes |
|------|--------------|-----------|---------|
| `fingerprint_extractor.py` | ~320 | ~250 | Remove fallback, add async HTTP |
| `audio_fingerprint_analyzer.py` | ~400 | ~200 | Remove all analyze_* methods |
| `harmonic_ops.py` | ~150 | ~100 | Keep as thin wrapper |

**Total**: ~470 LOC reduction

### KEEP (No Changes)
| Module | Purpose |
|--------|---------|
| `auralis/core/hybrid_processor.py` | Audio enhancement (NOT fingerprinting) |
| `auralis/dsp/` | DSP processing for playback enhancement |
| `auralis/io/` | Audio loading, resampling (limited optimization) |
| `auralis/optimization/` | Performance helpers |

---

## Rust Server Extensions Needed

### Current Rust Analyzer Structure
```rust
// fingerprint-server/src/analysis/analyzer.rs
pub fn analyze_fingerprint(samples: &[f64], sample_rate: u32) -> Result<Fingerprint> {
    // Currently returns empty Fingerprint::default()
    // Needs implementation of:
}

// Existing functions:
fn compute_fft_spectrum() ✅
fn compute_stft_spectral_analysis() ✅
```

### Functions to Implement

#### 1. Frequency Analysis (7D)
```rust
fn analyze_frequency(magnitude_spec: &[f64], freqs: &[f64]) -> Result<(f64, f64, f64, f64, f64, f64, f64)>
// Returns: (sub_bass_pct, bass_pct, low_mid_pct, mid_pct, upper_mid_pct, presence_pct, air_pct)
// Logic: Extract energy in 7 frequency bands (20-100Hz, 100-500Hz, etc.)
```

#### 2. Dynamics Analysis (3D)
```rust
fn analyze_dynamics(samples: &[f64], magnitude_spec: &[f64], freqs: &[f64], sample_rate: u32) -> Result<(f64, f64, f64)>
// Returns: (lufs, crest_db, bass_mid_ratio)
// Logic:
//   - LUFS: ITU-R BS.1770-4 K-weighted loudness
//   - Crest: Peak / RMS ratio
//   - Bass/Mid: Energy ratio
```

#### 3. Temporal Analysis (4D)
```rust
fn analyze_temporal(samples: &[f64], sample_rate: u32) -> Result<(f64, f64, f64, f64)>
// Returns: (tempo_bpm, rhythm_stability, transient_density, silence_ratio)
// Logic:
//   - Tempo: Onset autocorrelation (librosa equivalent)
//   - Rhythm: Beat interval stability
//   - Transients: Onset detection (spectral flux)
//   - Silence: RMS threshold ratio
```

#### 4. Spectral Analysis (3D)
```rust
fn analyze_spectral(stft_frames: &[Vec<f64>]) -> Result<(f64, f64, f64)>
// Returns: (spectral_centroid, spectral_rolloff, spectral_flatness)
// Logic: Already in analyzer.rs but marked as dead code
```

#### 5. Harmonic Analysis (3D)
```rust
fn analyze_harmonic(samples: &[f64], sample_rate: u32) -> Result<(f64, f64, f64)>
// Returns: (harmonic_ratio, pitch_stability, chroma_energy)
// Logic: Uses PyO3 bindings to auralis_dsp (HPSS, YIN, Chroma)
// Status: ALREADY IMPLEMENTED via Python FFI
```

#### 6. Variation Analysis (3D)
```rust
fn analyze_variation(samples: &[f64], sample_rate: u32) -> Result<(f64, f64, f64)>
// Returns: (dynamic_range_variation, loudness_variation_std, peak_consistency)
// Logic: Frame-by-frame crest factor variation
```

#### 7. Stereo Analysis (2D)
```rust
fn analyze_stereo(samples: &[f64]) -> Result<(f64, f64)>
// Returns: (stereo_width, phase_correlation)
// Logic: Mid/side energy, L-R correlation (already in code)
```

### Implementation Estimate
- **Frequency**: 80 LOC, 2-3 hours
- **Dynamics**: 120 LOC, 4-5 hours
- **Temporal**: 150 LOC, 6-8 hours (complex onset/tempo algorithms)
- **Spectral**: 40 LOC, 1 hour (mostly done)
- **Harmonic**: 20 LOC, <1 hour (already done)
- **Variation**: 80 LOC, 2-3 hours
- **Stereo**: 30 LOC, 1 hour

**Total**: ~520 LOC, ~18-23 hours development

---

## Dependency Graph

```
fingerprint_extractor.py
  └─ Rust server (HTTP)
     └─ analyze_fingerprint()
        ├─ compute_fft_spectrum()
        ├─ analyze_frequency() [NEW]
        ├─ analyze_dynamics() [NEW]
        │  └─ compute_lufs_k_weighted() [NEW]
        ├─ analyze_temporal() [NEW]
        │  └─ detect_onset_envelope() [NEW]
        │  └─ beat_track() [NEW]
        │  └─ estimate_tempo() [NEW]
        ├─ analyze_spectral()
        ├─ analyze_harmonic() [via PyO3]
        │  └─ hpss() [Rust via auralis_dsp]
        │  └─ yin() [Rust via auralis_dsp]
        │  └─ chroma_cqt() [Rust via auralis_dsp]
        ├─ analyze_variation() [NEW]
        └─ analyze_stereo()

# After migration:
fingerprint_extractor.py (no local DSP!)
  ├─ load_sidecar()
  ├─ call_rust_server_async()
  └─ store_fingerprint()
```

---

## Implementation Order

### Week 1: Foundation
- [ ] Extend Rust server: Frequency analysis (simple band energy extraction)
- [ ] Extend Rust server: Stereo analysis (already coded, just enable)
- [ ] Async HTTP client in fingerprint_extractor.py
- [ ] Test: 10-track batch with async HTTP

### Week 2: Critical Path
- [ ] Extend Rust server: Temporal analysis (onset + tempo detection)
- [ ] Extend Rust server: Dynamics analysis (LUFS calculation)
- [ ] Test: Single track fingerprinting quality
- [ ] Performance comparison: Python DSP vs Rust

### Week 3: Completion
- [ ] Extend Rust server: Spectral analysis (enable existing code)
- [ ] Extend Rust server: Variation analysis
- [ ] Archive Python DSP files
- [ ] Refactor Python analyzers

### Week 4: Polish
- [ ] Full integration testing (all 54K+ tracks)
- [ ] Performance benchmarking
- [ ] Documentation updates
- [ ] Cleanup and review

---

## Performance Targets

### Throughput
| Operation | Current | Target | Speedup |
|-----------|---------|--------|---------|
| Single fingerprint | 1-2 sec | 200-400 ms | 5-10x |
| Concurrent (32 workers) | 0.4-0.6 tracks/sec | 5-10 tracks/sec | 10-20x |
| Full library (54.7K tracks) | ~1.5 hours | ~2-3 hours (cache hits) | 30-50x with cache |

### Breakdown
- Current Rust analyzer: ~25-30ms per track
- Python fallback: ~1500-2000ms per track
- **Target**: Rust-only at ~200-400ms (optimized algorithms)

---

## Rollback Plan

If Rust server unstable:
1. Keep Python DSP code archived (not deleted)
2. Revert fingerprint_extractor.py to use fallback
3. Restore Python analyzer classes
4. Use phase 11 fingerprint cache for existing data

**Estimated recovery time**: <30 minutes

---

## Success Criteria

- [ ] All 25D fingerprint dimensions computed in Rust
- [ ] No Python DSP code in fingerprinting path
- [ ] Async HTTP requests (concurrent processing)
- [ ] 5-10x speedup vs current (accounting for Rust overhead)
- [ ] <1% fingerprint quality regression (per-dimension variance)
- [ ] 100% of 54.7K tracks can be re-fingerprinted
- [ ] Zero external Python DSP dependencies (librosa, resampy, etc.) for fingerprinting

---

## Documentation Changes

Files to update:
- [ ] `DEVELOPMENT_STANDARDS.md` - Remove Python DSP references
- [ ] `CLAUDE.md` - Architecture section (Python is orchestration only)
- [ ] `README.md` - Fingerprinting section (Rust-based)
- [ ] New: `FINGERPRINTING_ARCHITECTURE.md` (Rust server details)

---

## Notes

- **Why not pure Rust for orchestration?**
  - Database access is simpler in Python (SQLite, ORM)
  - Web framework integration easier (FastAPI)
  - Small performance cost for orchestration
  - Can migrate in future if needed

- **Why async HTTP in Python workers?**
  - Each worker thread runs its own event loop
  - Allows up to 16-32 concurrent requests per thread
  - No GIL blocking on I/O
  - ~10-20x improvement in request throughput

- **What about enhancement DSP?**
  - Audio enhancement (`auralis/dsp/`) stays in Python
  - Fingerprinting ≠ Enhancement
  - Enhancement is separate concern (playback optimization)
  - Can be migrated to Rust in future if needed
