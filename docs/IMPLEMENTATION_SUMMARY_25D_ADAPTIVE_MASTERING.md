# 25D Adaptive Mastering System: Implementation Summary

**Date**: November 24, 2025
**Status**: Planning Complete → Ready for Phase 1 Implementation
**Key Insight**: Transform the current "TODO" comments in `processing_engine.py:177-187` into a fully intelligent adaptive mastering system

---

## The Problem We're Solving

Currently in [auralis-web/backend/processing_engine.py:177-187](auralis-web/backend/processing_engine.py#L177-L187):

```python
# Apply EQ settings
if "eq" in job.settings and job.settings["eq"].get("enabled"):
    eq_settings = job.settings["eq"]
    # Apply EQ settings to config (simplified for now)
    # TODO: Map UI EQ settings to processor config

# Apply dynamics settings
if "dynamics" in job.settings and job.settings["dynamics"].get("enabled"):
    dynamics_settings = job.settings["dynamics"]
    # TODO: Map UI dynamics settings to processor config
```

**What's happening**: Settings are extracted but never actually applied. The system doesn't use the 25D fingerprint to intelligently generate parameters.

---

## The Solution: 25D-Driven Adaptive Mastering

### Core Concept

Instead of static preset mappings or ignored UI settings, use **25D fingerprints to generate optimal mastering parameters automatically**:

1. **Audio is analyzed once** → 25D fingerprint extracted
2. **Fingerprint cached** → .25d sidecar file + database
3. **Parameters generated intelligently** → EQ, Dynamics, Level based on actual audio characteristics
4. **Processing applies cached parameters** → Stable, deterministic, seamless

### What This Enables

```
BEFORE (Current):
  UI sends settings → Settings ignored → Real-time chunk analysis → Non-deterministic parameters → Artifacts

AFTER (New):
  Audio analyzed → 25D fingerprint → Smart parameter generation → Identical for all chunks → Seamless output
                  (one-time)                (deterministic)        (reproducible)
```

### Key Benefits

1. **No Real-Time Analysis Overhead**
   - Fingerprint computed once at library scan
   - Parameters pre-computed before processing
   - Processing uses cached data only

2. **Seamless Chunk Processing**
   - All chunks processed with identical parameters
   - No boundary artifacts
   - Deterministic output (same input = same output)

3. **Intelligent Mastering**
   - Spectral analysis informs EQ curve
   - Dynamic range analysis informs compression
   - Genre detection informs level targets
   - Humans don't need to tune this—fingerprint does

4. **Faster Performance**
   - 30-50% faster processing (no analysis during playback)
   - Responsive UI (minimal CPU usage)
   - Scalable to large libraries

---

## How 25D Dimensions Map to Mastering Parameters

### Spectral Features (7D) → EQ Parameters

```
Frequency Distribution    Mastering Action
─────────────────────    ────────────────
Sub-bass too low    →    Boost sub-bass gain
Bass too high       →    Reduce bass, preserve sub-bass
Low-mid harsh       →    Gentle dip in low-mid
Midrange present    →    Leave flat (good balance)
Upper-mid lacking   →    Gentle boost for presence
Presence good       →    Maintain
Air rolled off       →    Boost high shelf

Output: EQ curve that balances spectrum toward target
```

### Dynamics Features (2D + 3D Variation) → Compressor Settings

```
Dynamic Profile              Compression Action
───────────────────         ─────────────────
High crest factor (peaks stand out)    →  Low threshold, high ratio (squash peaks)
Low crest factor (already limited)     →  High threshold, low ratio (barely touch)
High loudness variation               →  Moderate compression (follow peaks)
Low variation (very consistent)       →  Minimal compression (already good)
Transient-rich (drums/percussion)    →  Fast attack (catch peaks quickly)
Smooth (ambient/strings)             →  Slow attack (preserve sustain)

Output: Compressor settings that control dynamics intelligently
```

### LUFS + Genre → Level Matching

```
Genre Detection         Target LUFS
───────────────        ───────────
Streaming standard      → -14 LUFS
Broadcast standard      → -16 LUFS
Vinyl mastering         → -10 LUFS
Heavy/Metal genre       → -8 LUFS  (more aggressive)
Ambient/Classical       → -18 LUFS (more dynamic range)

Output: Makeup gain to achieve target loudness
```

---

## The Implementation Roadmap (18 weeks, 6 phases)

### Phase 1: Fingerprint Enhancement (3-4 weeks)
- ✅ Verify all 25D dimensions work
- ✅ Background extraction pipeline with worker threads
- ✅ .25d sidecar file caching
- ✅ Integrate with library scanner
- **Target**: All tracks auto-fingerprinted during library scan

### Phase 2: Parameter Generation (4-5 weeks)
- Build `FingerprintEQGenerator` class
- Build `FingerprintDynamicsGenerator` class
- Build `FingerprintLevelGenerator` class
- **Replace TODO comments** with intelligent mapping
- **Target**: Parameters generated from 25D data, not ignored settings

### Phase 3: Stable Chunk Processing (2-3 weeks)
- Ensure all chunks use same parameters
- Seamless chunk boundaries
- Chunk cache coherency
- **Target**: Zero boundary artifacts

### Phase 4: UI Integration (2 weeks)
- Update settings to show "Intensity" sliders instead of presets
- Show fingerprint status in library
- Parameter preview visualization
- **Target**: Users understand fingerprint-based system

### Phase 5: Testing & Validation (3-4 weeks)
- Unit tests for each generator
- A/B testing vs manual presets
- Performance benchmarking
- **Target**: > 95% tests passing, fingerprint ≥ manual

### Phase 6: Documentation (1 week)
- Architecture guide
- Developer documentation
- Knowledge transfer
- **Target**: Clear understanding for future maintenance

---

## Why This Matters

### Current System (Before)
```
process_audio.py
  → Load audio
  → Real-time chunk analysis (expensive!)
  → Per-chunk parameters (non-deterministic!)
  → Process each chunk (artifacts at boundaries!)
  → Output (inconsistent)
```

Problems:
- High CPU during playback
- Different results each time
- Chunk boundaries might have artifacts
- Scaling issues with large libraries

### New System (After)
```
1. library_scan.py
   → Fingerprint extraction (background, one-time)
   → Cache .25d file
   → Store in database

2. process_audio.py
   → Load fingerprint (cached, instant)
   → Generate parameters (deterministic)
   → Apply to ALL chunks identically
   → Output (consistent, seamless)
```

Benefits:
- Low CPU during playback
- Same result every time
- No chunk boundary artifacts
- Scales to unlimited libraries

---

## Where to Start (Week 1 Actions)

### 1. Audit Fingerprint Extraction
```bash
# Check which dimensions are implemented
grep -r "class.*Analyzer" auralis/analysis/fingerprint/
# Profile extraction speed
python -m cProfile scripts/fingerprint_proof_of_concept.py
```

### 2. Review Current TODOs
```python
# In processing_engine.py:177-187
# These become the integration point for Phase 2
```

### 3. Create Test Fixtures
```python
# Test audio library for parameter generation
# Reference tracks with known fingerprints
# Expected parameter outputs
```

### 4. Design Parameter Generators
```
Design document (pseudocode):
- FingerprintEQGenerator: 7D spectral → EQ gains
- FingerprintDynamicsGenerator: 2D + 3D variation → compressor settings
- FingerprintLevelGenerator: LUFS + genre → makeup gain
```

---

## Key Files

**Where the TODO comments live**:
- [auralis-web/backend/processing_engine.py:177-187](auralis-web/backend/processing_engine.py#L177-L187)

**Where parameter generators will go**:
- `auralis/processing/fingerprint_eq_generator.py` (new)
- `auralis/processing/fingerprint_dynamics_generator.py` (new)
- `auralis/processing/fingerprint_level_generator.py` (new)

**Fingerprint system (already exists)**:
- `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py`
- `auralis/library/fingerprint_extractor.py`
- `auralis/library/sidecar_manager.py`

**Full roadmap**:
- [docs/roadmaps/25D_ADAPTIVE_MASTERING_ROADMAP.md](docs/roadmaps/25D_ADAPTIVE_MASTERING_ROADMAP.md)

---

## Success Metrics

| Metric | Target | How We Measure |
|--------|--------|----------------|
| **Parameter Generation Accuracy** | > 85% | A/B testing vs manual tuning |
| **Processing Speed** | 30x real-time | Benchmarking, comparing to real-time factor |
| **Determinism** | 100% | Process same audio 10x → identical output |
| **Chunk Boundaries** | Zero artifacts | Spectral/phase continuity tests |
| **Test Coverage** | > 95% pass | Unit + integration + A/B tests |
| **User Acceptance** | > 60% prefer fingerprint | Blind listening tests |

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Fingerprint extraction slow | Medium | High | Profile early, optimize bottlenecks |
| Parameter mapping inaccurate | Medium | High | A/B testing validates before release |
| Chunk boundary artifacts | Low | High | Rigorous boundary testing |
| Cache invalidation bugs | Medium | Medium | Comprehensive test suite |

---

## Why This Matters to Auralis

This is the **bridge between audio analysis and intelligent mastering**:

- **Analysis** (25D fingerprints) already works beautifully
- **Mastering** (processing_engine.py) currently ignores that analysis
- **Gap**: The TODO comments represent lost potential

By implementing this roadmap:
- ✅ We use our best technology (25D fingerprints)
- ✅ We eliminate redundant real-time analysis
- ✅ We produce predictable, seamless results
- ✅ We scale efficiently to any library size
- ✅ We solve the "stable chunks" problem permanently

---

## Next Steps

1. **This week**: Review full roadmap ([25D_ADAPTIVE_MASTERING_ROADMAP.md](docs/roadmaps/25D_ADAPTIVE_MASTERING_ROADMAP.md))
2. **Week 2**: Kick off Phase 1 (Fingerprint audit + background processing design)
3. **Week 3-4**: Begin Phase 2 (Parameter generator prototypes)
4. **Ongoing**: Keep tests passing, maintain quality bar

---

**Status**: Ready to implement
**Priority**: P1 (Core architecture improvement)
**Timeline**: ~18 weeks to complete
**Owned by**: Architecture team + Backend team
**Reviewed by**: [Your team lead]

