# Quick Reference: 25D Adaptive Mastering System

**TL;DR**: Use 25D fingerprints to intelligently generate mastering parameters instead of real-time analysis. Eliminates chunk boundary issues, faster processing, deterministic output.

---

## Problem → Solution

```
PROBLEM:
  processing_engine.py:177-187 has TODO comments
  → EQ settings extracted but ignored
  → Dynamics settings extracted but ignored
  → Real-time chunk analysis overhead
  → Non-deterministic chunk boundaries

SOLUTION:
  Generate EQ/Dynamics from 25D fingerprint
  → Pre-compute once, use always
  → All chunks process identically
  → Zero boundary artifacts
```

---

## The 25 Dimensions

```
Frequency (7D)       Dynamics (2D)      Temporal (4D)    Spectral (3D)
─────────────        ─────────────      ────────────     ────────────
Sub-bass             LUFS               Tempo            Centroid
Bass                 Crest factor       Beat stability   Rolloff
Low-mid                                 Transients       Flatness
Mid                                     Silence ratio
Upper-mid
Presence
Air

Harmonic (3D)        Variation (3D)     Stereo (2D)
────────────         ──────────────     ───────────
Ratio                Loudness var       Width
Pitch stability      Peak var           Phase correlation
Chroma               Energy var
```

---

## The Mapping Logic

```
SPECTRAL (7D) ──→ EQ PARAMETERS
├─ Sub-bass low      → Boost sub-bass gain
├─ Bass high         → Reduce bass
├─ Low-mid harsh     → Dip low-mid
├─ Mid flat          → Leave flat
├─ Upper-mid lacking → Boost presence
├─ Air rolled-off    → Boost highs
└─ Result: Balanced spectrum

DYNAMICS (2D) + VARIATION (3D) ──→ COMPRESSOR SETTINGS
├─ High crest factor → Low threshold, high ratio
├─ Low crest factor  → High threshold, low ratio
├─ High variation    → Moderate compression
├─ Low variation     → Minimal compression
├─ Transient-rich    → Fast attack
└─ Result: Controlled dynamics

LUFS + GENRE ──→ LEVEL TARGETS
├─ Streaming         → -14 LUFS
├─ Broadcast         → -16 LUFS
├─ Vinyl             → -10 LUFS
├─ Heavy/Metal       → -8 LUFS
└─ Ambient/Classical → -18 LUFS
```

---

## Implementation Timeline

| Phase | Duration | Target | Current Status |
|-------|----------|--------|-----------------|
| 1: Fingerprint & Background | 3-4 weeks | Auto-extract all tracks | Starting |
| 2: Parameter Mapping | 4-5 weeks | EQ/Dynamics/Level generators | Planning |
| 3: Stable Chunks | 2-3 weeks | Zero boundary artifacts | Planned |
| 4: UI Integration | 2 weeks | Fingerprint-aware settings | Planned |
| 5: Testing & Validation | 3-4 weeks | > 95% tests, A/B approved | Planned |
| 6: Documentation | 1 week | Full architecture docs | Planned |
| **TOTAL** | **~18 weeks** | **Late February 2026** | **Planning** |

---

## Key Files to Create/Modify

### New Files (Phase 2)
```
auralis/processing/fingerprint_eq_generator.py
auralis/processing/fingerprint_dynamics_generator.py
auralis/processing/fingerprint_level_generator.py
auralis/processing/eq_targets.py
auralis/processing/loudness_targets.py
```

### Files to Modify
```
auralis-web/backend/processing_engine.py        (RESOLVE TODOs at lines 177-187)
auralis/library/manager.py                      (add fingerprint queue)
auralis/library/scanner.py                      (trigger fingerprint extraction)
auralis-web/backend/routers/processing.py       (new endpoints)
```

### Existing Files to Leverage
```
auralis/analysis/fingerprint/audio_fingerprint_analyzer.py
auralis/library/fingerprint_extractor.py
auralis/library/sidecar_manager.py
```

---

## Code Location: Where the TODOs Live

**File**: `auralis-web/backend/processing_engine.py`
**Lines**: 177-187
**Method**: `_create_processor_config()`

```python
# Current (TODO):
if "eq" in job.settings and job.settings["eq"].get("enabled"):
    eq_settings = job.settings["eq"]
    # TODO: Map UI EQ settings to processor config

# Future (Solution):
if fingerprint:
    eq_params = FingerprintEQGenerator.generate(fingerprint)
    config.adaptive.eq.apply_params(eq_params)
```

---

## One-Sentence Summary

Use cached 25D fingerprints to generate optimal EQ/Dynamics parameters once, apply identically to all chunks, eliminate real-time analysis and chunk boundary artifacts.

---

## Why This Matters

### Performance
- **Before**: Real-time analysis during playback → CPU spike
- **After**: Pre-computed parameters → Zero overhead

### Quality
- **Before**: Per-chunk analysis → Non-deterministic boundaries
- **After**: Identical parameters → Seamless output

### Predictability
- **Before**: Same song, different processing each time
- **After**: Same song, identical processing always

### Scalability
- **Before**: Large libraries strain real-time analysis
- **After**: Any size library, no performance impact

---

## Next Week (Week 1 Actions)

1. **Audit fingerprint code**
   - Verify all 25 dimensions implemented
   - Profile extraction speed (~1-2s per track)
   - Ensure deterministic output

2. **Design parameter generators**
   - Pseudocode for EQ mapping
   - Pseudocode for dynamics mapping
   - Test data structures

3. **Plan background extraction**
   - Queue architecture
   - Worker thread design
   - Database schema updates

4. **Create test fixtures**
   - Reference tracks with known fingerprints
   - Expected parameter outputs
   - Validation metrics

---

## Success Criteria

✅ Phase complete when:
- All fingerprints extracting correctly (25D)
- Parameters generate from fingerprint data
- All chunks process with same parameters
- No artifacts at chunk boundaries
- Tests > 95% passing
- A/B testing shows fingerprint ≥ manual presets
- Documentation clear for future developers

---

## Questions to Answer During Implementation

1. **Fingerprint completeness**: Are all 25 dimensions working?
2. **Generation accuracy**: Do generated parameters match manual tuning?
3. **Performance**: Is 30x real-time achievable?
4. **User acceptance**: Do users prefer fingerprint-based mastering?
5. **Scalability**: Does it handle 10k+ track libraries?

---

## Related Documentation

- **Full Roadmap**: [docs/roadmaps/25D_ADAPTIVE_MASTERING_ROADMAP.md](docs/roadmaps/25D_ADAPTIVE_MASTERING_ROADMAP.md)
- **Implementation Summary**: [docs/IMPLEMENTATION_SUMMARY_25D_ADAPTIVE_MASTERING.md](docs/IMPLEMENTATION_SUMMARY_25D_ADAPTIVE_MASTERING.md)
- **Fingerprint System**: [docs/guides/FINGERPRINT_SYSTEM_ROADMAP.md](docs/guides/FINGERPRINT_SYSTEM_ROADMAP.md)
- **Current Architecture**: [docs/guides/AUDIO_PLAYBACK_STATUS.md](docs/guides/AUDIO_PLAYBACK_STATUS.md)
- **Master Roadmap**: [docs/MASTER_ROADMAP.md](docs/MASTER_ROADMAP.md) (Track 2)

---

**Created**: November 24, 2025
**Status**: Ready for Phase 1 Implementation
**Priority**: P1 - Core Architecture
**Ownership**: Architecture + Backend Team

