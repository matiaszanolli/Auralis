# Mastering Quality - Detailed Improvement Plan
**Date**: November 17, 2025
**Status**: 🎯 READY FOR IMPLEMENTATION
**Goal**: Execute systematic improvements to reach 85%+ quality score

---

## Quick Summary

**Current State**: 72% overall quality score
**Target**: 85%+ quality score
**Timeline**: 5 weeks
**Effort**: ~80-100 hours

**Critical Issues to Fix**:
1. ❌ Excessive bass boost on rock tracks (+3.2 dB, target 0 dB)
2. ❌ Dynamic range compression too aggressive (11.2 dB vs target 13-14 dB)
3. ⚠️ Transient handling insufficient (crest factor 3.8 vs target 4.5-5.5)
4. ⚠️ Progressive rock loudness range too narrow (6.2 LU vs target 7-9 LU)

---

## Phase 1: Frequency Response Optimization (Week 1-2)

### Problem Statement
Rock tracks show +3.2 dB bass boost (unacceptable), other tracks show less but still elevated. This creates a boomy, unbalanced sound rather than tight, controlled bass.

### Root Cause Analysis
The adaptive algorithm is over-correcting perceived bass thinness by:
1. Analyzing input as "dark" (spectral centroid 2.0-2.1 kHz)
2. Automatically boosting bass to match brighter reference
3. Using fixed boost curves that don't account for actual bass energy

### Solution Approach

#### Step 1a: Analyze Current EQ Curves (4 hours)

**Tasks**:
1. Extract current EQ curves from `preset_profiles.py` for each preset
2. Compare curves against reference standards:
   - Steven Wilson: Tight, balanced, transparent
   - Quincy Jones: Presence-focused, vocal-forward
   - Andy Wallace: Punchy bass, aggressive mids, clear highs
3. Identify over-boosted bands per genre

**Deliverable**: `FREQUENCY_RESPONSE_ANALYSIS.md` with graphs

```python
# File to analyze: auralis/core/config/preset_profiles.py
# Extract curves like this:
from auralis.dsp.eq import generate_genre_eq_curve
curve_adaptive = generate_genre_eq_curve('adaptive', 44100)
curve_bright = generate_genre_eq_curve('bright', 44100)
# Compare band by band (each of 26 bands)
```

#### Step 1b: Identify Over-boosting (2-3 hours)

**Tasks**:
1. Run test tracks through current system
2. Measure output frequency response
3. Compare to input frequency response
4. Calculate boost per band
5. Compare to reference standards

**Acceptance Criteria**:
- Bass boost ≤1.5 dB (vs current +3.2 dB) ✓
- Mid boost ≤1.0 dB (vs current +1.8 dB) ✓
- High boost ≤0.5 dB (vs current +0.2 dB) ✓

#### Step 1c: Refine EQ Curves (3-4 hours)

**Tasks**:
1. Adjust band gains in `preset_profiles.py`
   - Rock preset: Reduce bass boost from +3 to +1.5 dB
   - Pop preset: Keep close to current (+0.8 dB acceptable)
   - Adaptive preset: Reduce from +2.8 to +1.2 dB
2. Test each adjustment
3. Validate against rock track specifically

**Implementation Strategy**:
- Start with most aggressive preset (Rock) - needs biggest adjustment
- Use A/B comparison to validate changes
- Measure improvement metrics after each change
- Stop when bass is tight but not thin

```python
# File to modify: auralis/core/config/preset_profiles.py
# Example change:
class PresetProfile:
    # OLD: bass_boost_db = 3.2
    # NEW: bass_boost_db = 1.5
```

#### Step 1d: Validate Frequency Response (2-3 hours)

**Tasks**:
1. Process all 3 test tracks (Progressive Rock, Pop, Rock)
2. Measure frequency response after changes
3. Compare to baselines
4. Validate against reference standards
5. Document improvements

**Success Criteria**:
```
Rock Track:
├─ Bass (20-250Hz): 0 ± 1.5 dB (was +3.2) ✓
├─ Mid (250-4kHz): -0.5 ± 1.0 dB (was +1.8) ✓
└─ High (4-20kHz): +0.1 ± 0.5 dB (was +0.1) ✓

Spectral Similarity to Wallace: 75%+ (was ~60%)
```

**Estimated Time**: 11-15 hours
**Expected Improvement**: Frequency balance 58% → 75-80%

---

## Phase 2: Dynamic Range Preservation (Week 2-3)

### Problem Statement
All tracks lose 1.8-2.8 dB of dynamic range vs references. This results in less "alive" sound and over-compressed feel.

**Target**: Preserve ≥85% of input dynamic range (loss <1 dB)

### Root Cause Analysis
Compression settings are too aggressive:
1. Threshold too high (signals above -18 dB being compressed)
2. Ratio too steep (4:1 or higher)
3. Attack time too fast (catching transients)
4. Makeup gain sometimes excessive

### Solution Approach

#### Step 2a: Analyze Compression Behavior (3-4 hours)

**Tasks**:
1. Test current compression on each track
2. Measure:
   - How much signal is being compressed
   - Average gain reduction
   - Maximum gain reduction
   - Threshold being triggered percentage of time
3. Compare to reference compression behavior

**Test Setup**:
```python
from auralis.dsp.advanced_dynamics import AdaptiveCompressor
from auralis.analysis.quality_metrics import measure_dynamic_range

# Measure compression impact
input_dr = measure_dynamic_range(input_audio)
# Process through compressor
output_dr = measure_dynamic_range(output_audio)
dr_loss_percent = (input_dr - output_dr) / input_dr * 100
# Target: dr_loss_percent < 15% (lose <1dB from typical 13-14 dB DR)
```

**Deliverable**: Compression behavior report

#### Step 2b: Refine Compression Parameters (3-4 hours)

**Approach 1: Content-Aware Threshold**
- Detect if track is naturally compressed (low DR) vs dynamic (high DR)
- Dynamic track: Use gentle compression (threshold -12 dB, ratio 2:1)
- Compressed track: Use tighter compression (threshold -15 dB, ratio 3:1)

**Approach 2: Genre-Aware Settings**
- Rock: Aggressive transient handling, moderate compression
- Pop: Light compression, preserve vocal dynamics
- Progressive Rock: Very light compression, preserve all dynamics

**Implementation**:
```python
# File to modify: auralis/core/hybrid_processor.py
# Current (lines 72-80):
self.dynamics_processor = create_dynamics_processor(...)
self.dynamics_processor.settings.enable_compressor = True
# NEW: Make these content-aware:
# If input_dr > 14 dB:
#   settings.compression_ratio = 2.5  # Light
# Else:
#   settings.compression_ratio = 3.5  # Medium
```

**Testing**:
```python
# Test on all 3 tracks
from tests.validation.test_quality_improvements import validate_dr_preservation
results = validate_dr_preservation(processor, test_tracks)
# Target: All results show dr_loss < 1 dB
```

#### Step 2c: Improve Makeup Gain Calculation (2-3 hours)

**Current Formula**:
```
makeup_gain = |threshold| * (1 - 1/ratio)
```

**Issue**: Sometimes results in excessive makeup gain (+15 dB in extreme cases)

**Improved Formula**:
```
# Estimate average input level
average_input_level = calculate_rms_level(input_audio)
# Calculate makeup gain more conservatively
if average_input_level > threshold:
    gain_reduction_avg = (threshold - average_input_level) * (1 - 1/ratio)
    makeup_gain = max(0, -gain_reduction_avg * 0.8)  # 80% compensation
else:
    makeup_gain = 0
```

**Implementation**:
```python
# File: auralis/dsp/advanced_dynamics.py (lines 233-239)
# Update makeup gain calculation with new formula
```

#### Step 2d: Transient Preservation (2-3 hours)

**Goal**: Improve crest factor (peak-to-RMS ratio) preservation

**Current Issue**: Soft clipper and limiter catching too many transients

**Solution**:
1. Increase attack time to let transients through
2. Reduce soft clipper aggressiveness
3. Make limiter threshold looser for low-ratio compression

```python
# File: auralis/core/hybrid_processor.py (lines 82-87)
# Adjust soft clipper and limiter:
self.soft_clipper = SoftClipper(threshold_db=-1.5)  # was -1.0
self.brick_wall_limiter = create_brick_wall_limiter(
    threshold_db=-0.1,  # was -0.3 (looser)
    lookahead_ms=5.0,   # was 2.0 (more lookahead)
    release_ms=75.0     # was 50.0 (slower release)
)
```

#### Step 2e: Validate Dynamic Range Preservation (2-3 hours)

**Validation Procedure**:
1. Process all test tracks
2. Measure input and output DR
3. Calculate preservation percentage
4. Compare to references
5. Document improvements

**Success Criteria**:
```
Progressive Rock:
├─ Input DR: 16-18 dB
├─ Output DR: 14-16 dB (85% preservation, was 77%)
└─ Loss: <1.5 dB (was 2.8 dB) ✓

Pop:
├─ Input DR: 14-16 dB
├─ Output DR: 12-14 dB (87% preservation, was 84%)
└─ Loss: <1 dB ✓

Rock:
├─ Input DR: 17-19 dB
├─ Output DR: 16-17 dB (95% preservation, was 91%)
└─ Loss: <1 dB ✓
```

**Estimated Time**: 12-15 hours
**Expected Improvement**: DR score 65% → 80-85%

---

## Phase 3: Adaptive Algorithm Enhancement (Week 3-4)

### Problem Statement
Algorithm doesn't always select optimal parameters for different content types. Need better content analysis and parameter selection.

### Goals
1. Improve genre detection accuracy to ≥85%
2. Better vocal vs instrumental detection
3. Better transient vs smooth content detection
4. More accurate adaptive target prediction

### Solution Approach

#### Step 3a: Genre Detection Analysis (2-3 hours)

**Current System**: ML classifier in `ml_genre_classifier.py`

**Validation**:
1. Test on diverse music library
2. Measure accuracy per genre
3. Identify failure cases
4. Improve if <85% accuracy

```python
from auralis.analysis.ml_genre_classifier import GenreClassifier
from tests.validation import measure_genre_accuracy

classifier = GenreClassifier()
accuracy = measure_genre_accuracy(classifier, test_set)
# Target: accuracy >= 0.85
```

#### Step 3b: Content Type Detection (2-3 hours)

**Add Detection For**:
- Vocal vs instrumental (% vocals in mix)
- Transient vs smooth (attack rate analysis)
- Compressed vs dynamic (input DR and RMS stability)
- Stereo vs mono (stereo width analysis)

**Implementation**:
```python
# File: auralis/core/analysis/content_analyzer.py
def analyze_content_type(audio):
    """Analyze content characteristics for adaptive processing"""
    return {
        'has_vocals': True/False,
        'vocal_percentage': 0-100,
        'is_transient_heavy': True/False,
        'input_is_compressed': True/False,
        'compression_ratio': estimated_ratio,
        'stereo_type': 'mono'/'stereo'/'wide',
    }
```

#### Step 3c: Adaptive Target Refinement (3-4 hours)

**Goal**: Better prediction of processing targets based on content

**Current System**: SpectrumMapper determines processing targets

**Improvement**:
1. Better threshold prediction for compression
2. Genre-aware target generation
3. Content-aware parameter adjustment
4. Validation against references

```python
# File: auralis/core/processing/parameter_generator.py
# Improve target prediction with content analysis
def generate_targets(content_profile, genre):
    # OLD: Fixed targets
    # NEW: Content-aware targets
    if content_profile.is_transient_heavy:
        return targets_for_transients
    elif content_profile.has_vocals:
        return targets_for_vocals
    else:
        return targets_for_instruments
```

#### Step 3d: Validation & Testing (2-3 hours)

**Validation**:
1. Test on all genres with diverse material
2. Measure parameter accuracy
3. Validate output quality
4. Check for improvements

**Success Criteria**:
- Genre detection ≥85% accuracy
- Parameter selection optimal for content type
- Overall quality improvements visible
- No regressions

**Estimated Time**: 9-13 hours
**Expected Improvement**: Adaptive algorithm quality +10-15%

---

## Phase 4: Stereo Field Optimization (Week 4)

### Goal
Maintain or enhance stereo imaging while preventing artifacts

### Tasks

#### Step 4a: Stereo Width Analysis (1-2 hours)
- Measure input stereo width for all test tracks
- Analyze reference stereo widths
- Identify optimal width per genre

#### Step 4b: Width Preservation (1-2 hours)
- Implement genre-aware width targeting
- Avoid excessive widening that causes phase issues
- Preserve mono compatibility

#### Step 4c: Phase Coherence Validation (1-2 hours)
- Monitor phase throughout pipeline
- Ensure no processing introduces phase shifts
- Validate mono compatibility

**Estimated Time**: 3-6 hours
**Expected Improvement**: Minor, mostly maintaining excellence

---

## Phase 5: Comprehensive Testing & Documentation (Week 5)

### Testing Phase

#### Step 5a: Full Validation Suite (4-6 hours)
```bash
# Run all tests
python -m pytest tests/validation/ -v
python -m pytest tests/auralis/ -v
python -m pytest tests/boundaries/ -v

# Specific quality tests
python -m pytest tests/validation/test_quality_improvements.py -v
```

#### Step 5b: A/B Comparison (2-3 hours)
- Process test tracks with old and new code
- Compare all metrics
- Document improvements
- Check for any regressions

#### Step 5c: Final Metrics (2-3 hours)
- Measure final quality scores
- Compare to baselines
- Validate against references
- Calculate improvement percentage

### Documentation Phase

#### Step 5d: Create Final Reports (4-6 hours)

**Documents to Create**:
1. **FREQUENCY_RESPONSE_IMPROVEMENTS.md**
   - What changed
   - Before/after comparisons
   - Metrics improvements

2. **DYNAMICS_EXCELLENCE_REPORT.md**
   - Compression optimization details
   - DR preservation improvements
   - Transient handling enhancements

3. **ADAPTIVE_ALGORITHM_ENHANCEMENTS.md**
   - Genre detection accuracy
   - Content-aware improvements
   - Parameter selection refinements

4. **STEREO_FIELD_VALIDATION.md**
   - Width preservation validation
   - Phase coherence verification
   - Quality metrics

5. **SESSION_FINAL_SUMMARY.md**
   - All improvements summary
   - Before/after quality scores
   - Test coverage
   - Next steps

**Estimated Time**: 6-10 hours

---

## Overall Timeline & Effort

### Week-by-Week Schedule

**Week 1 (Days 1-5): Frequency Response**
- Day 1-2: Analyze curves and baseline (4 hours)
- Day 3: Refine EQ curves (4 hours)
- Day 4-5: Validate and test (4-5 hours)
- **Total**: ~12 hours
- **Deliverable**: Frequency balance improved 58% → 75-80%

**Week 2 (Days 6-10): Dynamic Range**
- Day 6-7: Analyze compression (6-8 hours)
- Day 8: Refine parameters (3-4 hours)
- Day 9-10: Validate and test (4-5 hours)
- **Total**: ~13-17 hours
- **Deliverable**: DR preservation improved 65% → 80-85%

**Week 3-4 (Days 11-20): Adaptive Algorithm**
- Day 11-13: Genre detection and content analysis (8-10 hours)
- Day 14-16: Adaptive target refinement (8-10 hours)
- Day 17-20: Testing and validation (6-8 hours)
- **Total**: ~22-28 hours
- **Deliverable**: Better content-aware processing

**Week 4 (Days 16-20): Stereo Optimization**
- Parallel with adaptive algorithm
- **Total**: ~3-6 hours
- **Deliverable**: Stereo validation maintained

**Week 5 (Days 21-25): Testing & Documentation**
- Day 21-22: Full validation (8-12 hours)
- Day 23-25: Final reports and documentation (10-15 hours)
- **Total**: ~18-27 hours
- **Deliverable**: Complete documentation, 85%+ quality score

### Total Effort Summary

| Phase | Hours | Status |
|-------|-------|--------|
| Frequency Response | 12-15 | Week 1-2 |
| Dynamic Range | 12-15 | Week 2-3 |
| Adaptive Algorithm | 9-13 | Week 3-4 |
| Stereo Optimization | 3-6 | Week 4 |
| Testing & Docs | 18-27 | Week 5 |
| **TOTAL** | **54-76 hours** | ~15 hours/week |

**Parallel Work Possible**: Yes, can do stereo work during other phases
**Expected Duration**: 5 weeks at ~15 hours/week

---

## Success Metrics & Checkpoints

### Checkpoint 1 (End of Week 1-2)
- [ ] Frequency balance score 75%+ (was 58%)
- [ ] No regressions in other metrics
- [ ] Bass boost ≤1.5 dB across all tracks
- [ ] Documentation completed

### Checkpoint 2 (End of Week 3)
- [ ] DR preservation ≥85% (was 65%)
- [ ] Crest factor within target range (4.5-5.5, was 3.8-5.8)
- [ ] No pumping or artifacts
- [ ] All test tracks validate

### Checkpoint 3 (End of Week 4)
- [ ] Adaptive algorithm improvements validated
- [ ] Genre detection ≥85% accurate
- [ ] Stereo field maintained or improved
- [ ] Overall quality score 80%+

### Final Checkpoint (End of Week 5)
- [ ] Overall quality score ≥85% (was 72%)
- [ ] All test suites passing
- [ ] No regressions
- [ ] Full documentation complete
- [ ] Ready for release

---

## Risk Mitigation

### Risk 1: Changes Introduce Regressions
**Probability**: Medium
**Impact**: High (need to revert)
**Mitigation**:
- Run full test suite after each change
- Keep old code in version control
- Use feature flags for large changes
- A/B test before/after

### Risk 2: Reference Standards Overly Strict
**Probability**: Low
**Impact**: Medium (can't reach targets)
**Mitigation**:
- Reference standards are from publicly available masters
- Adjust targets if evidence shows different approach is better
- Focus on perceptual quality, not just metrics

### Risk 3: Time Overruns on Implementation
**Probability**: Medium
**Impact**: Medium (miss deadline)
**Mitigation**:
- Prioritize critical issues first
- Can defer "nice to have" features
- Parallel work on multiple phases

### Risk 4: Performance Degradation
**Probability**: Low
**Impact**: High (slow processing)
**Mitigation**:
- Profile code before/after
- Use Numba JIT where applicable
- Test on large files for latency

---

## Tools & Commands

### Running Tests
```bash
# All tests
python -m pytest tests/ -v

# Validation suite
python -m pytest tests/validation/ -v

# Specific test file
python -m pytest tests/validation/test_quality_improvements.py -v

# With coverage
python -m pytest tests/ --cov=auralis --cov-report=html

# Performance benchmark
python benchmark_performance.py
```

### Processing Test Tracks
```python
from auralis.core import HybridProcessor, UnifiedConfig
from auralis.analysis.quality_metrics import measure_all_metrics
import soundfile as sf

config = UnifiedConfig()
processor = HybridProcessor(config)

# Process a track
audio, sr = sf.read('test_track.wav')
output = processor.process(audio)

# Measure all metrics
metrics = measure_all_metrics(input_audio=audio, output_audio=output, sr=sr)
print(metrics)
```

### Comparing Before/After
```bash
# Create output files for comparison
python scripts/compare_processing.py test_track.wav

# Run analysis
python -m auralis.analysis.quality_metrics test_track.wav output.wav
```

---

## Review Checkpoints

After each major phase, review:

1. **Quality Metrics**
   - All KPIs tracked and documented
   - Improvements measured
   - No regressions

2. **Code Quality**
   - No duplication introduced
   - Modules still <300 lines
   - Proper documentation

3. **Test Coverage**
   - All tests passing
   - New tests added where applicable
   - No flaky tests

4. **Performance**
   - Processing speed maintained
   - Memory usage acceptable
   - No new bottlenecks

---

## Rollback Procedure (If Needed)

If changes cause regressions:

```bash
# See what changed
git diff main

# Revert specific file
git checkout main -- auralis/core/hybrid_processor.py

# Or revert entire branch
git reset --hard main

# Re-run tests to confirm
python -m pytest tests/ -v
```

---

**Plan Created**: November 17, 2025
**Ready for Implementation**: ✅ YES
**Next Action**: Begin Phase 1 frequency response optimization
**Estimated Completion**: December 22, 2025 (5 weeks)
