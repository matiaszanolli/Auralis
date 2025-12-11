# Python DSP Migration Manifest

**Status**: Planning Phase (Ready to Execute)
**Target Completion**: 3-4 weeks
**Rust Server Status**: Started (needs completion of analyze_* functions)

---

## Files to Archive/Move

### Phase 1: Core Fingerprinting Utilities (HIGH PRIORITY)

#### `auralis/analysis/fingerprint/utilities/temporal_ops.py` → Archive
**Lines**: ~200 | **Dependency**: librosa.beat, librosa.onset, librosa.feature.rms
**Functions**:
- `detect_tempo()` - Tempo detection via librosa beat.tempo
- `calculate_rhythm_stability()` - Beat interval variance
- `calculate_transient_density()` - Onset detection + density
- `calculate_silence_ratio()` - RMS-based silence ratio
- `calculate_all()` - Pre-compute onset envelope, RMS, tempo

**Rust Equivalent**: `fingerprint-server/src/analysis/analyzer.rs:analyze_temporal()`
**Status**: Not yet implemented in Rust

---

#### `auralis/analysis/fingerprint/utilities/spectral_ops.py` → Archive
**Lines**: ~190 | **Dependency**: scipy.fft, NumPy
**Functions**:
- `calculate_spectral_centroid()` - Center of mass of spectrum
- `calculate_spectral_rolloff()` - 85% cumulative energy frequency
- `calculate_spectral_flatness()` - Geometric/arithmetic mean ratio
- `calculate_all()` - Pre-computed STFT analysis

**Rust Equivalent**: `fingerprint-server/src/analysis/analyzer.rs:analyze_spectral()`
**Status**: Partially implemented (dead code, line 424)

---

#### `auralis/analysis/fingerprint/utilities/variation_ops.py` → Archive
**Lines**: ~250 | **Dependency**: NumPy vectorization
**Functions**:
- `get_frame_peaks()` - Frame-by-frame peak detection
- `calculate_dynamic_range_variation()` - Crest factor variance
- `calculate_loudness_variation()` - RMS variation std dev
- `calculate_peak_consistency()` - Peak normalization consistency
- `calculate_all()` - Aggregate frame statistics

**Rust Equivalent**: `fingerprint-server/src/analysis/analyzer.rs:analyze_variation()`
**Status**: Not yet implemented in Rust

---

#### `auralis/analysis/fingerprint/utilities/harmonic_ops.py` → KEEP (thin wrapper)
**Lines**: ~150 | **Dependency**: auralis_dsp PyO3, librosa
**Functions**:
- `calculate_harmonic_ratio()` - HPSS separation
- `calculate_pitch_stability()` - YIN pitch detection
- `calculate_chroma_energy()` - Chroma CQT analysis

**Rust Equivalent**: Via PyO3 bindings (auralis_dsp Rust module)
**Status**: Already in Rust, keep as Python wrapper

---

### Phase 2: Analysis & Loudness Modules

#### `auralis/analysis/loudness_meter.py` → Archive
**Lines**: ~350 | **Dependency**: Custom IIR filters, NumPy
**Functions**:
- `apply_k_weighting()` - ITU-R BS.1770-4 K-weighting filter
- `calculate_block_loudness()` - LUFS for 400ms block
- `measure_chunk()` - Full LUFS measurement pipeline
- `finalize_measurement()` - Integrated loudness with gating

**Rust Equivalent**: `fingerprint-server/src/analysis/analyzer.rs:analyze_dynamics()` (LUFS part)
**Status**: Not yet implemented in Rust

---

#### `auralis/analysis/dynamic_range.py` → Archive
**Lines**: ~200 | **Dependency**: NumPy peak/RMS analysis
**Functions**:
- `analyze_dynamic_range()` - DR value calculation
- Dynamic range assessment

**Rust Equivalent**: `fingerprint-server/src/analysis/analyzer.rs:analyze_variation()`
**Status**: Partial (related to variation analysis)

---

#### `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py` → REFACTOR
**Lines**: ~400 | **Current Purpose**: 25D fingerprint orchestration
**Changes**:
- Remove all `analyze_*` methods (call Rust server instead)
- Keep: Sampling strategy, caching logic, sidecar management
- New: Pure HTTP orchestration

**Rust Equivalent**: `fingerprint-server/src/analysis/analyzer.rs` (complete)
**Status**: Needs refactoring to Rust-only

---

### Phase 3: Quality Assessment (Deprecated)

#### `auralis/analysis/quality_assessors/*` → PARTIAL (Low Priority)
**Lines**: ~800+ | **Status**: Many metrics depend on archived DSP
**Action**: Mark as deprecated, no longer maintain

**Modules affected**:
- `loudness_assessment.py` - Depends on loudness_meter (archived)
- `frequency_assessment.py` - Depends on spectral_ops (archived)
- `distortion_assessment.py` - Depends on FFT analysis (archived)
- `dynamic_assessment.py` - Depends on dynamic_range (archived)

---

## Files to KEEP (No Changes)

### Core Audio Enhancement (Not Fingerprinting)
- `auralis/core/hybrid_processor.py` - Audio enhancement pipeline
- `auralis/dsp/` - DSP processing for playback (EQ, dynamics, etc.)
- `auralis/io/` - Audio loading/resampling
- `auralis/optimization/` - Performance helpers

**Reason**: These are for ENHANCEMENT, not fingerprinting. Separate concern.

---

## Migration Checklist

### Step 0: Preparation (Today)
- [x] Create archive directory structure
- [x] Create archive README
- [x] Create migration manifest (this file)
- [ ] Create archive copies of all files

### Step 1: Archive Creation (~2 hours)
Commands to execute:
```bash
# Copy files to archive (before deleting from main code)
cp auralis/analysis/fingerprint/utilities/temporal_ops.py archived/python_dsp_legacy/fingerprint/utilities/
cp auralis/analysis/fingerprint/utilities/spectral_ops.py archived/python_dsp_legacy/fingerprint/utilities/
cp auralis/analysis/fingerprint/utilities/variation_ops.py archived/python_dsp_legacy/fingerprint/utilities/
cp auralis/analysis/loudness_meter.py archived/python_dsp_legacy/analysis/
cp auralis/analysis/dynamic_range.py archived/python_dsp_legacy/analysis/
cp auralis/analysis/fingerprint/audio_fingerprint_analyzer.py archived/python_dsp_legacy/fingerprint/
```

### Step 2: Rust Server Extension (18-23 hours)
- [ ] Analyze frequency bands (simple extraction)
- [ ] Analyze dynamics (LUFS + K-weighting)
- [ ] Analyze temporal (tempo + onset + beat tracking)
- [ ] Analyze spectral (enable existing code)
- [ ] Analyze variation (frame-wise metrics)
- [ ] Analyze stereo (already implemented, enable)

### Step 3: Python Refactoring (3-5 hours)
- [ ] Refactor fingerprint_extractor.py (remove fallback, async HTTP)
- [ ] Simplify audio_fingerprint_analyzer.py (orchestration only)
- [ ] Remove import references to archived modules
- [ ] Update harmonic_ops.py comments

### Step 4: Integration Testing (5-8 hours)
- [ ] Single track fingerprinting (Rust-only)
- [ ] Batch processing (50 tracks, concurrent)
- [ ] Performance benchmarking
- [ ] Fingerprint quality check
- [ ] Memory usage validation

### Step 5: Cleanup & Documentation (3-4 hours)
- [ ] Delete Python DSP files (if not needed for fallback)
- [ ] Or keep archived copies for emergency fallback
- [ ] Update documentation
- [ ] Add Rust server deployment guide

---

## Estimated Timeline

| Phase | Task | Duration | Start | End |
|-------|------|----------|-------|-----|
| 1 | Archive preparation | 2 hours | Day 1 | Day 1 |
| 2 | Rust server extension | 20 hours | Day 2-3 | Day 4 |
| 3 | Python refactoring | 4 hours | Day 5 | Day 5 |
| 4 | Integration testing | 6 hours | Day 5-6 | Day 6 |
| 5 | Cleanup & docs | 3 hours | Day 6 | Day 7 |
| **Total** | | **35 hours** | | |

**Calendar**: ~1 week full-time, or 3-4 weeks part-time

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Rust server incomplete | MEDIUM | HIGH | Keep Python fallback in archive |
| Fingerprint mismatch | LOW | MEDIUM | Per-dimension variance testing |
| Performance not achieved | LOW | LOW | Optimize Rust algorithms |
| Async HTTP bugs | LOW | MEDIUM | Thorough concurrent testing |

---

## Rollback Procedure

If Rust server fails:
1. Copy archived files back to main source
2. Revert fingerprint_extractor.py commits
3. Reinstall Python DSP dependencies: `pip install librosa resampy scipy`
4. Restore Python analyzer fallback in fingerprint_extractor.py
5. Continue fingerprinting with Python DSP (slower, but functional)

**Time to rollback**: ~10 minutes
**Performance impact**: 5-10x slower (back to 0.2-0.5 tracks/sec)

---

## Success Criteria

- [ ] All 25 fingerprint dimensions computed in Rust
- [ ] Python code: 0 DSP operations (pure orchestration)
- [ ] Async HTTP working (concurrent requests)
- [ ] Throughput: 5-10x improvement
- [ ] Fingerprints: <1% dimension variance vs Python
- [ ] 54.7K track library can be re-fingerprinted
- [ ] Zero DSP dependencies in fingerprinting path (no librosa, scipy, resampy)

---

## Next Steps

1. **Finalize Rust server** - Implement remaining analyze_* functions
2. **Create archive copies** - Copy files before deletion
3. **Refactor Python code** - Remove DSP, use HTTP-only
4. **Integration testing** - Validate end-to-end
5. **Documentation** - Update all relevant docs

See `DSP_MIGRATION_PLAN.md` for detailed technical specification.
