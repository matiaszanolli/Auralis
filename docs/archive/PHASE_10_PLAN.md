# Phase 10: Further Audio Tuning Plan

**Phase:** 10 (Empirical Validation Continuation)
**Status:** Planning
**Target:** January 2025
**Goal:** Achieve 8/10+ track pass rate on South Of Heaven album

---

## 📊 Current State (Phase 9D Post-Hotfix)

### Validation Results
- **Test Album:** Slayer - South Of Heaven (10 tracks @ 48 kHz)
- **Pass Rate:** 5-6/10 tracks expected (after dynamics adjustment fix)
- **Passing Tracks (2.5-5.5 dB boost):**
  - ✓ 01. South Of Heaven: +2.87 dB
  - ✓ 02. Silent Scream: +2.76 dB
  - ✓ 06. Ghosts of War: +2.74 dB
  - ✓ 07. Read Between the Lies: +2.61 dB
  - ✓ 10. Spill the Blood: 2.54+ dB (expected)

- **Below Threshold (1.3-2.49 dB boost):**
  - ⚠ 03. Live Undead: +1.41 dB (gap: -1.09 dB)
  - ⚠ 04. Behind the Crooked Cross: +1.60 dB (gap: -0.90 dB)
  - ⚠ 05. Mandatory Suicide: +2.19-2.40 dB (gap: -0.10-0.31 dB)
  - ⚠ 08. Cleanse the Soul: +2.23-2.49 dB (gap: 0.01-0.99 dB depending on formula)
  - ⚠ 09. Dissident Aggressor: +1.77-1.99 dB (gap: -0.50-0.73 dB)

### Key Metrics
- **Processing Speed:** 66.5 seconds/track average @ 48 kHz
- **Memory Usage:** ~700 MB per 10-minute track
- **Zero Crashes:** All 10 tracks complete without errors
- **Energy Range:** 0.46-0.55 (all tracks within narrow band)

---

## 🎯 Phase 10 Objectives

### Primary Goal
Improve from 5-6/10 PASS to **8/10+ PASS** by fine-tuning audio processing parameters.

### Secondary Goals
1. Expand validation to additional albums (classical, hip-hop, electronic)
2. Establish confidence that algorithm works across genres
3. Document tuning results and rationale
4. Profile code for potential optimizations

---

## 🔧 Tuning Strategies

### Strategy A: Energy-LUFS Formula Refinement
**Hypothesis:** Current formula needs adjustment for energy range 0.46-0.55

**Current Formula:**
```python
base_lufs = -2.0 - 22.0 * (1.0 - energy)
```

**Observations:**
- energy=0.46 → -12.1 dB target → +2.87 dB boost ✓
- energy=0.48 → -13.4 dB target → +1.41 dB boost ⚠
- energy=0.55 → -15.1 dB target → +2.61 dB boost ✓

**Issue:** Energy 0.48 underperforming despite being between successful 0.46 and 0.55

**Possible Root Causes:**
1. Other fingerprint coordinates (spectral, dynamic) affecting outcome
2. SafetyLimiter soft clipping threshold (0.945) limiting boost
3. EQ blend values varying per track
4. Dynamics blend capping RMS gain

**Action Items:**
- [ ] Analyze fingerprint coordinates for all 10 tracks
- [ ] Correlate energy + spectral + dynamic with final boost
- [ ] Test adjusted LUFS slopes (23.0, 24.0, 25.0)
- [ ] Evaluate SafetyLimiter threshold adjustment (0.92-0.95)
- [ ] Isolate which factor(s) cause mid-energy underperformance

### Strategy B: SafetyLimiter Parameter Tuning
**Current Parameters:**
- SAFETY_THRESHOLD_DB = 0.5 dB
- SOFT_CLIP_THRESHOLD = 0.945 (~-0.54 dB)

**Testing Plan:**
- [ ] Lower soft clip threshold to 0.92-0.93 (more aggressive clipping)
- [ ] Measure RMS boost improvement per 0.01 threshold reduction
- [ ] Balance between safety and loudness target
- [ ] Verify no distortion introduction

### Strategy C: Spectral/Dynamic Coordinate Analysis
**Data Needed:**
- Extract all 3 coordinates (spectral, dynamic, energy) for each track
- Correlate with final boost results
- Identify patterns in high-performing vs. low-performing tracks

**Expected Insights:**
- Which coordinate combinations lead to 2.5+ dB boosts
- Whether spectral or dynamic matters more than energy
- Possible 2D or 3D response surface to optimize

### Strategy D: Extended Album Validation
**Albums to Test:**
1. **Classical:** Debussy Clair de Lune recordings (2-3 versions)
   - Expected: Low energy, dynamic range varies
   - Goal: Verify quiet material handling
2. **Hip-Hop:** Sample album (modern trap/lo-fi)
   - Expected: Medium-high energy, compressed
   - Goal: Verify compressed material handling
3. **Electronic:** Ambient/Synth album
   - Expected: Consistent energy, synthetic timbres
   - Goal: Verify non-live material handling

**Success Criteria:**
- 8/10 PASS on each album (60% pass rate or higher)
- Consistent boost across genres
- No genre-specific tuning needed

---

## 📋 Implementation Roadmap

### Phase 10a: Parameter Analysis (Week 1)
**Goal:** Understand why mid-energy tracks underperform

**Tasks:**
1. Create analysis script to extract all coordinates + final boost for each track
2. Generate heatmaps/scatter plots (energy vs boost, spectral vs boost, etc.)
3. Identify patterns and anomalies
4. Document findings in PHASE_10A_ANALYSIS.md

**Deliverables:**
- `research/phase_10_coordinate_analysis.py`
- `research/PHASE_10A_ANALYSIS.md` (with visualizations)

### Phase 10b: Formula Tuning (Week 1-2)
**Goal:** Adjust energy-LUFS formula for 8/10 pass rate

**Tasks:**
1. Test formula variations (slope 23.0-25.0)
2. Test SafetyLimiter threshold adjustments (0.92-0.95)
3. Run 3-track quick validation for each variation
4. Select best-performing combination
5. Full 10-track validation of final formula

**Deliverables:**
- Updated `parameter_generator.py`
- `research/PHASE_10B_TUNING_RESULTS.md`
- Commit: `fix: Phase 10 - Tune energy-LUFS formula and SafetyLimiter for 8/10 pass rate`

### Phase 10c: Extended Album Testing (Week 2-3)
**Goal:** Validate algorithm across genres

**Tasks:**
1. Acquire/obtain classical, hip-hop, electronic test albums
2. Run full validation pipeline on each
3. Document results and any genre-specific observations
4. Adjust parameters if needed for cross-genre consistency

**Deliverables:**
- `research/PHASE_10C_EXTENDED_VALIDATION.md`
- Test results for 3+ albums

### Phase 10d: Final Release & Documentation (Week 3-4)
**Goal:** Prepare Phase 10 completion and 1.1.0-beta.6 release

**Tasks:**
1. Update README with Phase 10 results
2. Create `RELEASE_NOTES_1_1_0_BETA6.md`
3. Document all tuning decisions and rationale
4. Performance profiling if needed
5. Final commit and GitHub release

**Deliverables:**
- Version bump to 1.1.0-beta.6
- Comprehensive release notes
- Tag: `v1.1.0-beta.6`

---

## 📈 Success Metrics

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| South Of Heaven Pass Rate | 5-6/10 | 8/10 | TBD |
| Processing Speed | 66.5s/track | ≥66.5s | TBD |
| Memory Usage | ~700 MB | ≤700 MB | TBD |
| Crash Rate | 0% | 0% | TBD |
| Albums Validated | 1 | 3+ | TBD |

---

## 🚧 Potential Challenges

### Challenge 1: Mid-Energy Underperformance
**Issue:** Tracks with energy 0.48-0.50 consistently below threshold
**Solution Strategy:**
- Piecewise formula (separate logic for energy < 0.50)
- Different SafetyLimiter thresholds per energy band
- Coordinate-aware tuning (use spectral/dynamic too)

### Challenge 2: Genre Variation
**Issue:** Algorithm may work well for metal but not classical
**Solution Strategy:**
- Per-genre tuning (separate formulas)
- Genre detection via fingerprint coordinates
- Cross-genre validation before release

### Challenge 3: Diminishing Returns
**Issue:** May hit asymptotic limit (e.g., can't get above 7/10 without distortion)
**Solution Strategy:**
- Accept 7/10 as "good enough" (70% pass rate)
- Focus on consistency over perfection
- Document limitations clearly

---

## 📝 Notes & Assumptions

1. **Assumption:** SafetyLimiter is the bottleneck, not EQ or dynamics processing
   - If false, will need to adjust other parameters
2. **Assumption:** Energy-based scaling is sufficient (don't need full 3D tuning)
   - May need to revisit if extended albums show genre-dependent behavior
3. **Assumption:** No distortion artifacts at aggressive SafetyLimiter thresholds
   - Verify with listening tests once threshold < 0.92

---

## 🔗 Related Phases

- **Phase 9D:** Completed SafetyLimiter fixes and energy-adaptive LUFS
- **Phase 9C:** Fixed RMS compensation feedback loop
- **Phase 11 (Future):** Desktop/web interface improvements, binary releases

---

## ✅ Checklist

- [ ] Phase 10a: Coordinate analysis complete
- [ ] Phase 10b: Formula tuning complete
- [ ] Phase 10c: Extended album validation complete
- [ ] Phase 10d: Release notes and 1.1.0-beta.6 ready
- [ ] All commits pushed to GitHub
- [ ] GitHub release v1.1.0-beta.6 published

---

**Owner:** Matías Zanolli
**Created:** November 30, 2024
**Last Updated:** November 30, 2024
**Next Review:** December 7, 2024
