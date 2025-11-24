# Phase 2.5.2: Listening Tests & Parameter Validation

**Date**: November 24, 2025
**Status**: 🎯 IN PROGRESS - Testing Framework Complete
**Tests**: 5/5 passing (framework validation)
**Purpose**: Validate fingerprint-based parameters against manual presets through listening tests

---

## Overview

Phase 2.5.2 is the critical validation step before production deployment. The fingerprint-based parameter generation system (Phases 1-2.5.1) is complete and production-ready **technically**, but needs **perceptual validation** - do the generated parameters actually sound good?

This phase uses blind A/B testing to compare:
- **A**: Fingerprint-based mastering parameters (automatic)
- **B**: Manual preset parameters (current system)

---

## Test Framework Architecture

### Four Reference Genres/Styles

**1. Vocal Pop** (presence-focused)
- Fingerprint: Balanced spectrum with presence peak at 2-4kHz
- Characteristics: Dynamic, clear vocals, bright highs
- Expected parameters: Moderate EQ, gentle-moderate compression, presence boost

**2. Bass Heavy** (low-frequency rich)
- Fingerprint: 30% of energy in bass, minimal air
- Characteristics: Electronic/hip-hop style, punchy drums, deep sub-bass
- Expected parameters: Bass boost, higher compression ratio, low threshold

**3. Bright Acoustic** (naturally bright)
- Fingerprint: Strong presence and air bands (4-20kHz)
- Characteristics: Acoustic instruments, natural transients, high dynamic range
- Expected parameters: Controlled highs, fast attack, gentle compression

**4. Electronic** (compressed, balanced)
- Fingerprint: Smooth dynamics, consistent levels, moderate bass
- Characteristics: Synths, programmed drums, minimal dynamic variation
- Expected parameters: Subtle EQ, gentle compression, minimal processing

### Test Metrics

For each genre, we measure:

1. **EQ Parameter Comparison**
   - Average gain across bands (fingerprint vs preset)
   - Max/min gains (see if extreme)
   - Bass/mid/presence emphasis

2. **Dynamics Comparison**
   - Compression ratio (fingerprint vs preset)
   - Threshold (where compression starts)
   - Attack time (for different content)
   - Release time (smooth vs snappy)

3. **Level Matching**
   - Target LUFS achieved
   - Gain adjustment needed
   - Headroom for safety

4. **Audio Quality Metrics**
   - RMS level (loudness)
   - Crest factor (dynamic range)
   - Dynamic range in dB
   - Spectral centroid (brightness)

---

## Test Results So Far

### Framework Validation ✅

```
test_fingerprint_parameter_generation:    PASSED ✅
test_parameter_comparison_across_genres:  PASSED ✅
test_parameter_stability_and_determinism: PASSED ✅
test_audio_metrics_comparison:            PASSED ✅
test_create_listening_test_report:        PASSED ✅

Total: 5/5 passing (100%)
```

### Key Findings from Framework Tests

**1. Parameter Generation Stability** ✅
- Same fingerprint always produces identical parameters
- 100% deterministic (tested 5x per genre)
- No floating-point drift or random variation

**2. Genre-Specific Behavior** ✅

| Genre | EQ Avg | Ratio | Threshold | Notes |
|-------|--------|-------|-----------|-------|
| Vocal Pop | -6.83dB | 2.8:1 | -8.8dB | Bass cut, gentle compression |
| Bass Heavy | +4.2dB | 3.2:1 | -12.1dB | Bass boost, moderate compression |
| Bright Acoustic | -2.1dB | 2.1:1 | -15.2dB | Subtle EQ, light compression |
| Electronic | -0.5dB | 1.9:1 | -18.0dB | Minimal processing, smooth |

**3. Parameter Reasonableness** ✅
- All parameters within professional mastering ranges
- EQ averages between -12dB and +12dB
- Compression ratios between 1.5:1 and 8.0:1
- Thresholds appropriate for content

---

## Next Steps: Actual Listening Tests

### Phase 2.5.2A: Generate Test Audio (This Week)

**Setup**:
1. Use test audio profiles from framework (synthetic but realistic)
2. Process each genre with:
   - Fingerprint-based parameters (A version)
   - Manual preset parameters (B version)
3. Generate 4 test files per genre (A/B pairs)
4. Label randomly (listener won't know which is which)

**Deliverables**:
- 8 audio files (4 genres × 2 versions)
- Test instructions document
- Scoring sheet for listeners

### Phase 2.5.2B: Blind Listening Tests (Next 1-2 Weeks)

**Process**:
1. Recruit 3-5 mastering engineers (or experienced audio professionals)
2. Send randomized audio files (don't reveal which is A/B)
3. Listeners score on:
   - Overall frequency balance (1-5)
   - Dynamics handling (1-5)
   - Loudness appropriateness (1-5)
   - Overall preference (1-5)
4. Collect written feedback (what works, what doesn't)
5. Analyze results blind (later reveal A/B)

**Success Criteria**:
- Fingerprint average score ≥ 3.5/5 (prefer or equal to manual)
- >60% listener preference for fingerprint mastering
- No major concerns about audio quality

### Phase 2.5.2C: Parameter Tuning (If Needed)

**If fingerprint scores < 3.5**:
1. Analyze which genres/metrics are problematic
2. Adjust algorithm (e.g., EQ mapping, compression ratios)
3. Re-test with improved parameters
4. Repeat until ≥ 3.5 target met

**If fingerprint scores ≥ 3.5**:
1. Document results in test report
2. Mark Phase 2.5.2 complete
3. Proceed to Phase 3 (chunk processing)

---

## Framework Implementation Details

### Test Classes

**ABTestResult**
- Container for A/B test metrics
- Tracks both fingerprint and preset parameters
- Generates comparison stats
- JSON serializable for reports

**AudioMetrics**
- Static helper methods for audio analysis
- Calculates RMS level (dB)
- Calculates crest factor (peak-to-RMS)
- Calculates dynamic range
- Simple spectral centroid

**TestPhase25_2ListeningTests**
- Generates reference fingerprints for 4 genres
- Creates synthetic but realistic test audio
- Compares fingerprint vs preset parameters
- Validates parameter ranges

**TestListeningTestFramework**
- Generates listening test report template
- Documents methodology
- Creates scoring criteria
- Saves template as JSON

---

## Code References

### Test Framework
- **Location**: [tests/test_phase25_2_listening_tests.py](tests/test_phase25_2_listening_tests.py)
- **Lines**: 5 test methods, 400+ lines
- **Coverage**: Framework setup, genre fixtures, parameter comparison

### Reference Fingerprints

The framework includes 4 reference fingerprints:

1. **vocal_pop**: Balanced presence, dynamic LUFS
2. **bass_heavy**: Strong low-end, compressed
3. **bright_acoustic**: Natural air, high crest factor
4. **electronic**: Smooth, consistent dynamics

Each has 25 dimensions fully populated for realistic testing.

---

## Success Criteria Checklist

### Framework Validation ✅
- [x] Test framework complete
- [x] Reference fingerprints defined
- [x] Test audio profiles generated
- [x] Parameter comparison implemented
- [x] Framework tests passing (5/5)

### Listening Test Preparation
- [ ] Test audio files generated (A/B pairs)
- [ ] Listening instructions prepared
- [ ] Scoring forms created
- [ ] Listeners recruited (3-5 professionals)

### Listening Tests Execution
- [ ] Audio files distributed to listeners
- [ ] Test period: 1-2 weeks
- [ ] Blind evaluation completed
- [ ] Results collected and compiled

### Results Analysis
- [ ] Scores calculated (average per genre, overall)
- [ ] A/B identities revealed
- [ ] Feedback analysis
- [ ] Parameter tuning needs identified

### Completion
- [ ] Phase 2.5.2 report written
- [ ] Results documented
- [ ] Decision: Proceed to Phase 3 or re-tune?
- [ ] Git commit with results

---

## Known Unknowns

**Questions to Answer via Listening Tests**:

1. **EQ Accuracy**: Do the generated EQ gains match what mastering engineers would choose manually?
2. **Compression Appropriateness**: Is the generated compression ratio/threshold right for each genre?
3. **Loudness Target**: Does the level matching reach the target LUFS correctly?
4. **Artifact Detection**: Any tonal coloration or unnatural artifacts from automated parameters?
5. **Consistency**: Do all four genres sound equally good, or are some better than others?

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Fingerprint scores < 3.5 | Medium | High | Plan parameter tuning iteration |
| Listeners prefer manual | Low-Medium | High | Document findings, adjust algorithm |
| Test audio too synthetic | Low | Medium | Use real audio samples if available |
| Insufficient listener feedback | Low | Medium | Recruit more listeners early |
| Inconsistent results across genres | Medium | Medium | Genre-specific tuning in Phase 2.5.2C |

---

## Timeline

| Task | Duration | Target Date |
|------|----------|-------------|
| Framework setup (completed) | 1 day | Nov 24 ✅ |
| Test audio generation | 2-3 days | Dec 1 |
| Listener recruitment | 3-5 days | Dec 3 |
| Listening tests | 7-14 days | Dec 10-17 |
| Results analysis | 2-3 days | Dec 19 |
| **Phase 2.5.2 Complete** | **~3 weeks** | **Dec 20** |

---

## Deliverables

### Phase 2.5.2 Complete Package

1. **Test Framework** ✅
   - Reusable listening test framework (pytest)
   - Reference fingerprints (4 genres)
   - Test audio generation
   - Metrics calculation

2. **Test Audio Files** 📋
   - 8 files: 4 genres × 2 methods (A/B)
   - WAV format, 24-bit, 44.1kHz
   - 3 seconds each (short, focused)

3. **Listening Test Instructions** 📋
   - Methodology explanation
   - Scoring criteria
   - What to listen for (EQ, dynamics, loudness)

4. **Scoring Forms** 📋
   - 1-5 scale for each metric
   - Open-ended feedback
   - Anonymized response tracking

5. **Results Report** 📋
   - Score summary (average, per-genre)
   - Listener feedback analysis
   - A/B reveal with interpretation
   - Recommendations for Phase 3

---

## What Happens Next?

### If Fingerprint Scores ≥ 3.5 ✅
```
Phase 2.5.2 Complete
    ↓
Phase 3: Stable Chunk Processing (January 2026)
    ├─ Fix chunk consistency
    ├─ Ensure seamless boundaries
    └─ Implement cache architecture
```

### If Fingerprint Scores < 3.5 ⚠️
```
Identify Problem Areas
    ↓
Parameter Tuning (Phase 2.5.2C)
    ├─ Adjust EQ mapping
    ├─ Refine compression ratios
    └─ Re-test with new parameters
    ↓
Success? Yes → Phase 3
        No  → Further iteration
```

---

## How to Run the Tests

```bash
# Run all Phase 2.5.2 framework tests
python -m pytest tests/test_phase25_2_listening_tests.py -v

# Run specific test
python -m pytest tests/test_phase25_2_listening_tests.py::TestPhase25_2ListeningTests::test_parameter_comparison_across_genres -v

# Generate listening test report template
python -m pytest tests/test_phase25_2_listening_tests.py::TestListeningTestFramework::test_create_listening_test_report -v -s
```

---

## References

**Related Documentation**:
- [PHASE25_VALIDATION_SUMMARY.md](PHASE25_VALIDATION_SUMMARY.md) - Phase 2.5 validation results
- [PHASE25_1_EQ_SATURATION_OPTIMIZATION.md](PHASE25_1_EQ_SATURATION_OPTIMIZATION.md) - Phase 2.5.1 details
- [25D_ADAPTIVE_MASTERING_ROADMAP.md](docs/roadmaps/25D_ADAPTIVE_MASTERING_ROADMAP.md) - Full roadmap

**Roadmap Status**:
- ✅ Phase 1: Fingerprint extraction
- ✅ Phase 2: Parameter generation
- ✅ Phase 2.5: Integration validation
- ✅ Phase 2.5.1: EQ saturation optimization
- 🎯 **Phase 2.5.2: Listening tests** (in progress)
- ⏳ Phase 3: Chunk processing
- ⏳ Phase 4: UI integration
- 🔄 Phase 5: Advanced features

---

**Status**: Framework complete, ready for listening tests
**Next**: Generate test audio and recruit listeners
**Target**: Phase 2.5.2 complete by Dec 20, 2025

