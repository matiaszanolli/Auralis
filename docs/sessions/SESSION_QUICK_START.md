# Mastering Quality Session - Quick Start Guide
**Session Date**: November 17, 2025
**Status**: 🚀 READY TO START
**Duration**: 5 weeks
**Effort**: ~15 hours per week

---

## 📋 Session Overview

This session focuses on **systematically improving mastering quality** from **72% to 85%+** by:
1. Fixing excessive bass boosting (+3.2 dB → +1.5 dB)
2. Improving dynamic range preservation (65% → 85%)
3. Enhancing adaptive algorithm precision
4. Optimizing stereo field handling
5. Validating against world-class reference standards

**Key Documents**:
- 📊 [MASTERING_QUALITY_BASELINE_METRICS.md](MASTERING_QUALITY_BASELINE_METRICS.md) - Current metrics (72%)
- 🎯 [MASTERING_QUALITY_IMPROVEMENT_PLAN.md](MASTERING_QUALITY_IMPROVEMENT_PLAN.md) - Detailed roadmap
- 🔍 [MASTERING_QUALITY_IMPROVEMENT_SESSION.md](MASTERING_QUALITY_IMPROVEMENT_SESSION.md) - Full context

---

## 🎯 The 3 Critical Issues to Fix

### Issue #1: Bass Boost Too Aggressive ❌
- **Current**: Rock track has +3.2 dB bass (unacceptable)
- **Target**: +0-1.5 dB bass (tight, controlled)
- **Impact**: Makes rock sound boomy instead of punchy
- **Fix Time**: 11-15 hours (Phase 1, Weeks 1-2)
- **Files**: `auralis/core/config/preset_profiles.py`

### Issue #2: Dynamic Range Compressed Too Much ❌
- **Current**: Losing 1.8-2.8 dB of DR (compression too aggressive)
- **Target**: Preserve ≥85% of input DR (<1 dB loss)
- **Impact**: Music sounds over-compressed, less "alive"
- **Fix Time**: 12-15 hours (Phase 2, Weeks 2-3)
- **Files**: `auralis/core/hybrid_processor.py`, `auralis/dsp/advanced_dynamics.py`

### Issue #3: Transients Getting Over-Controlled ⚠️
- **Current**: Crest factor 3.8 (too low)
- **Target**: Crest factor 4.5-5.5 (preserves punch)
- **Impact**: Drums/bass lose impact and definition
- **Fix Time**: 2-3 hours (Part of Phase 2)
- **Files**: `auralis/core/hybrid_processor.py` (soft clipper settings)

---

## 📈 Quality Scores by Category

### Current State (Week 1)
```
Overall: 72%  ⚠️ NEEDS IMPROVEMENT

├─ Loudness Accuracy: 88% ✓ (GOOD)
├─ Dynamic Range Preservation: 65% ❌ (CRITICAL)
├─ Frequency Balance: 58% ❌ (CRITICAL)
├─ Spectral Centroid: 92% ✓ (EXCELLENT)
├─ Stereo Field: 96% ✓ (EXCELLENT)
└─ Transient Handling: 72% ⚠️ (MODERATE)
```

### Target State (Week 5)
```
Overall: 85%+ ✅ TARGET

├─ Loudness Accuracy: 95%+ ✓
├─ Dynamic Range Preservation: 85%+ ✓
├─ Frequency Balance: 80%+ ✓
├─ Spectral Centroid: 95%+ ✓
├─ Stereo Field: 95%+ ✓
└─ Transient Handling: 85%+ ✓
```

---

## 📅 Week-by-Week Breakdown

### Week 1-2: Frequency Response Fix
**Goal**: Reduce bass boost, improve frequency balance
- [ ] Analyze current EQ curves (what's being boosted?)
- [ ] Compare to Steven Wilson/Quincy Jones standards
- [ ] Reduce bass boost from +3.2 to +1.5 dB on rock
- [ ] Validate all test tracks
- **Success**: Frequency score 58% → 75-80%

**Key Changes**:
```python
# File: auralis/core/config/preset_profiles.py
# Rock preset:
bass_boost_db = 1.5  # was 3.2

# Adaptive preset:
bass_boost_db = 1.2  # was 2.8
```

### Week 2-3: Dynamic Range Excellence
**Goal**: Preserve 85%+ of input dynamic range
- [ ] Analyze current compression aggressiveness
- [ ] Make threshold and ratio content-aware
- [ ] Fix makeup gain calculation
- [ ] Improve transient handling
- [ ] Validate all test tracks
- **Success**: DR score 65% → 80-85%

**Key Changes**:
```python
# File: auralis/core/hybrid_processor.py
# Make compression content-aware:
if input_dr > 14:  # Dynamic material
    ratio = 2.5  # Light
else:  # Already compressed
    ratio = 3.5  # Medium

# Adjust limiter for better transients:
threshold_db = -0.1  # was -0.3 (looser)
lookahead_ms = 5.0   # was 2.0 (more lookahead)
```

### Week 3-4: Adaptive Algorithm
**Goal**: Better genre detection and parameter selection
- [ ] Validate genre detection (≥85% accuracy)
- [ ] Improve content-aware processing
- [ ] Better adaptive targets
- [ ] Full validation
- **Success**: Content-aware processing improvements

### Week 4: Stereo Optimization
**Goal**: Maintain excellent stereo field quality
- [ ] Width preservation validation
- [ ] Phase coherence checking
- [ ] Minor refinements if needed
- **Success**: Stereo score stays 95%+

### Week 5: Testing & Documentation
**Goal**: Comprehensive validation and documentation
- [ ] Run full test suite (no regressions)
- [ ] A/B compare old vs new code
- [ ] Generate final metrics
- [ ] Complete all documentation
- **Success**: 85%+ overall quality score, ready for release

---

## 🔧 Implementation Priority

### Priority 1 (Must Do)
1. ✅ Fix bass boost issue - Makes biggest immediate improvement
2. ✅ Improve DR preservation - Critical for music quality
3. ✅ Fix transient handling - Important for punch and clarity

### Priority 2 (Should Do)
1. ⚠️ Enhance adaptive algorithm - Better content-awareness
2. ⚠️ Genre-specific optimizations - Per-genre improvements

### Priority 3 (Nice to Have)
1. 💡 Stereo field enhancements - Currently excellent
2. 💡 Performance optimization - If time permits
3. 💡 Advanced features - For future sessions

---

## 🏃 Quick Command Reference

### Running Tests
```bash
# All tests
python -m pytest tests/ -v

# Validation suite only
python -m pytest tests/validation/ -v

# Specific quality test
python -m pytest tests/validation/test_quality_improvements.py -v

# With coverage report
python -m pytest tests/ --cov=auralis --cov-report=html
```

### Processing Test Tracks
```python
from auralis.core import HybridProcessor, UnifiedConfig
from auralis.analysis.quality_metrics import measure_all_metrics
import soundfile as sf

config = UnifiedConfig()
processor = HybridProcessor(config)

audio, sr = sf.read('test.wav')
output = processor.process(audio)

metrics = measure_all_metrics(
    input_audio=audio,
    output_audio=output,
    sr=sr
)
```

### Before/After Comparison
```bash
# Process with old code
python -c "... save as old_output.wav"

# Make changes, process again
python -c "... save as new_output.wav"

# Compare metrics
python -m auralis.analysis.quality_metrics old_output.wav new_output.wav
```

---

## 📊 Success Criteria

### Phase 1 Success (Frequency Response)
- [ ] Frequency balance score: 75%+ (was 58%)
- [ ] Bass boost: ≤1.5 dB on rock track (was +3.2 dB)
- [ ] No regressions in other metrics
- [ ] All 3 test tracks validated

### Phase 2 Success (Dynamic Range)
- [ ] DR preservation: 85%+ (was 65%)
- [ ] Crest factor: 4.5-5.5 range (was 3.8)
- [ ] No pumping/breathing artifacts
- [ ] LUFS stability maintained

### Overall Session Success
- [ ] Overall quality: 85%+ (was 72%)
- [ ] All test suites passing
- [ ] Zero regressions
- [ ] Full documentation complete
- [ ] Ready for release

---

## 📁 Key Files to Modify

### Frequency Response (Week 1-2)
```
auralis/core/config/preset_profiles.py    <- EQ curve adjustments
auralis/dsp/eq/psychoacoustic_eq.py       <- EQ band refinements (if needed)
```

### Dynamic Range (Week 2-3)
```
auralis/core/hybrid_processor.py           <- Compression settings, limiter
auralis/dsp/advanced_dynamics.py          <- Makeup gain formula
auralis/core/processing/adaptive_mode.py  <- Content-aware processing
```

### Adaptive Algorithm (Week 3-4)
```
auralis/analysis/content_analyzer.py      <- Content type detection
auralis/core/processing/parameter_generator.py  <- Target selection
auralis/analysis/ml_genre_classifier.py   <- Genre detection validation
```

### Testing & Validation
```
tests/validation/test_quality_improvements.py  <- New quality tests
docs/sessions/MASTERING_QUALITY_*.md           <- Session documentation
```

---

## ⚠️ Common Pitfalls to Avoid

1. **Don't Over-Optimize for One Track**
   - Validate changes on all 3 test tracks
   - Watch for regressions on other genres

2. **Don't Sacrifice Loudness for Dynamics**
   - Target: Maintain LUFS while improving DR
   - Both metrics matter

3. **Don't Introduce Artifacts**
   - Listen for pumping, breathing, harshness
   - Run full test suite after changes

4. **Don't Rush Documentation**
   - Document what changed and why
   - Include before/after metrics
   - Clear for next developer

5. **Don't Skip Validation**
   - Always compare against references
   - Run A/B tests before committing
   - Check for regressions

---

## 🎓 Learning Resources

### Understanding the System
- Read: [MASTERING_QUALITY_VALIDATION.md](../guides/MASTERING_QUALITY_VALIDATION.md) - Framework
- Read: [TECHNICAL_DEBT_RESOLUTION.md](../completed/TECHNICAL_DEBT_RESOLUTION.md) - Current state
- Code: `auralis/core/hybrid_processor.py` - Main processor

### Reference Standards
- Steven Wilson: Progressive rock, -13.2 LUFS, 13-14 dB DR
- Quincy Jones: Pop, -11.8 LUFS, 11-12 dB DR
- Andy Wallace: Rock, -10.5 LUFS, 10-11 dB DR

### Quality Metrics
- LUFS: Loudness Units (target depends on genre)
- DR: Dynamic Range (measure range from quiet to loud)
- Crest Factor: Peak to RMS ratio (preserve for punch)
- Spectral Centroid: Brightness (measure of tone)
- Stereo Width: 0-1 (0=mono, 1=extreme width)

---

## 💬 Questions to Ask If Stuck

1. **Where is this specific metric computed?**
   - Check `auralis/analysis/quality_metrics.py`

2. **How does the current EQ work?**
   - Look at `auralis/dsp/eq/psychoacoustic_eq.py`

3. **What are the compression settings?**
   - See `auralis/dsp/advanced_dynamics.py`

4. **How is genre detected?**
   - Check `auralis/analysis/ml_genre_classifier.py`

5. **Where are tests for this feature?**
   - Look in `tests/auralis/`, `tests/validation/`, etc.

---

## 📞 Session Management

### Tracking Progress
- Use [MASTERING_QUALITY_IMPROVEMENT_SESSION.md](MASTERING_QUALITY_IMPROVEMENT_SESSION.md) as checklist
- Update [MASTERING_QUALITY_BASELINE_METRICS.md](MASTERING_QUALITY_BASELINE_METRICS.md) with new measurements
- Keep git commits documented with improvements

### Handling Issues
1. **Test fails after change**: Check diff with `git diff`
2. **Regression detected**: Revert with `git checkout main -- file.py`
3. **Stuck on implementation**: Review reference standards docs
4. **Need to verify improvement**: Run `python -m pytest tests/validation/ -v`

### Committing Changes
```bash
# After completing a task:
git add auralis/core/config/preset_profiles.py
git commit -m "fix: reduce bass boost for rock tracks

- Rock: +3.2 dB → +1.5 dB
- Adaptive: +2.8 dB → +1.2 dB
- Frequency balance score: 58% → 75%
- No regressions in other metrics

Fixes: Issue #1 (excessive bass boost)"
```

---

## 🎉 End State

After 5 weeks and ~75 hours of work:

✅ **Overall Quality**: 72% → 85%+
✅ **Frequency Balance**: 58% → 75%+
✅ **Dynamic Range Preservation**: 65% → 85%+
✅ **All Tests Passing**: 100% pass rate
✅ **Full Documentation**: Complete
✅ **Ready for Release**: Yes

**Achievement**: Mastering quality now matches or exceeds world-class standards in multiple genres!

---

**Session Created**: November 17, 2025
**Start Date**: Ready now
**Target Completion**: December 22, 2025
**Current Task**: Phase 1 - Frequency Response Optimization
