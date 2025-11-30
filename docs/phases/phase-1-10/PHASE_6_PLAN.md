# Phase 6: Extending DRY Principles to Additional Modules - Implementation Plan

## Overview

Phase 6 extends the successful DRY patterns from Phase 5 (BaseAnalyzer, common_metrics utilities) to additional modules in the `auralis/analysis/` directory. This phase targets 1,800-2,200 LOC of consolidation opportunity across 25+ modules.

## Executive Summary

**Opportunity Identified:**
- 12,262 total LOC in auralis/analysis/ directory
- 1,900-2,400 LOC of consolidation potential (15-19% of codebase)
- 610+ LOC immediately actionable with existing Phase 5 utilities

**Key Patterns to Extend:**
1. BaseAnalyzer inheritance (6 more modules)
2. SafeOperations for epsilon guards (15+ locations)
3. AggregationUtils for frame aggregation (8 modules)
4. MetricUtils for normalization (12 modules)
5. New: BaseQualityAssessor for scoring templates (5 quality modules)

---

## Phase 6 Breakdown

### Phase 6.1: Extend BaseAnalyzer to Remaining Fingerprint Analyzers (2-3 hours)

**Target Modules:**
1. `harmonic_analyzer.py` (203 LOC)
2. `stereo_analyzer.py` (155 LOC)
3. `harmonic_analyzer_sampled.py` (252 LOC)

**Changes per module:**
- Change class inheritance to `BaseAnalyzer`
- Add `DEFAULT_FEATURES` class constant
- Rename `analyze()` → `_analyze_impl()`
- Rename internal try/except blocks to let BaseAnalyzer handle them

**Expected Savings:** -40 to -50 LOC per module (-130 total)

**Implementation Order:**
1. stereo_analyzer.py (simplest, good baseline)
2. harmonic_analyzer.py (consolidate CV logic already unified)
3. harmonic_analyzer_sampled.py (test override behavior)

**Test Strategy:**
- Verify DEFAULT_FEATURES work correctly
- Ensure error handling still works
- Check fingerprint consistency (same values)

---

### Phase 6.2: Create BaseQualityAssessor for Unified Scoring (3-4 hours)

**Target Modules:**
1. `quality/distortion_assessment.py` (185 LOC)
2. `quality/dynamic_assessment.py` (116 LOC)
3. `quality/loudness_assessment.py` (253 LOC)
4. `quality/frequency_assessment.py` (152 LOC)
5. `quality/stereo_assessment.py` (191 LOC)

**Pattern Identified:** All 5 modules implement tiered scoring:
```python
if value >= threshold1:
    return 100.0
elif value >= threshold2:
    return 80 + (value - threshold2) * scale
elif value >= threshold3:
    return 60 + (value - threshold3) * scale
else:
    return max(0, default)
```

**Solution: BaseQualityAssessor Template**

```python
# quality/base_assessor.py (NEW - 80 LOC)
class BaseQualityAssessor(ABC):
    """Template for tiered scoring systems"""

    SCORING_TIERS = []  # Override in subclasses
    # Example: [
    #     (100, 85.0),      # tier, threshold
    #     (80, 70.0, 0.5),  # tier, threshold, scale
    #     (60, 50.0, 0.3),
    #     (0, 0.0, 0.0)
    # ]

    def score(self, value):
        """Apply tiered scoring"""
        for tier_info in self.SCORING_TIERS:
            threshold = tier_info[1]
            if value >= threshold:
                base_score = tier_info[0]
                if len(tier_info) > 2:
                    scale = tier_info[2]
                    return base_score + (value - threshold) * scale
                return base_score
        return 0.0

    @abstractmethod
    def get_issues(self, value):
        """Return list of issues for this value"""
        pass
```

**Apply to each module:**
- Move scoring logic to SCORING_TIERS constant
- Implement get_issues() method
- Replace _score_* methods with generic score()

**Expected Savings:** -200 to -250 LOC total across 5 modules

**Implementation Order:**
1. dynamic_assessment.py (simplest, 2 scoring methods)
2. stereo_assessment.py (2 scoring methods)
3. loudness_assessment.py (3 scoring methods, test multiple)
4. distortion_assessment.py (complex, has multiple features)
5. frequency_assessment.py (frequency-specific, may need customization)

---

### Phase 6.3: Audit and Consolidate SafeOperations Usage (2-3 hours)

**Target Modules:** 15+ modules with manual epsilon guards

**Current Scattered Pattern:**
```python
if denominator > 0:
    result = numerator / denominator
else:
    result = fallback

if value > 1e-10:
    result = np.log10(value)
else:
    result = 0
```

**Consolidated Using Existing SafeOperations:**
```python
result = SafeOperations.safe_divide(numerator, denominator, fallback)
result = SafeOperations.safe_log(value, fallback=0)
result = SafeOperations.safe_power(value, exponent, fallback=1.0)
```

**Affected Modules (Tier 1):**
1. `loudness_meter.py` (4 epsilon guards) - 12 LOC savings
2. `ml/feature_extractor.py` (6 epsilon guards) - 12 LOC savings
3. `dynamic_range.py` (scattered guards) - 20 LOC savings
4. `spectrum_analyzer.py` (5 epsilon guards) - 15 LOC savings
5. `phase_correlation.py` (3 division guards) - 8 LOC savings
6. `content/feature_extractors.py` (5 guards) - 10 LOC savings
7. `parallel_spectrum_analyzer.py` (3 guards) - 8 LOC savings

**Expected Savings:** -90 to -120 LOC

**Implementation:**
1. Create audit script to find all epsilon usage
2. Convert systematically by module
3. Verify numerical equivalence in tests
4. Update documentation

---

### Phase 6.4: Standardize Frame Aggregation with AggregationUtils (2-3 hours)

**Target Modules:** 8 modules using manual aggregation

**Current Pattern (scattered):**
```python
# Multiple different ways in different modules
centroid_median = np.median(centroid_values)
centroid_normalized = centroid_median / 8000.0

rms_mean = np.mean(rms_values)

onset_std = np.std(onset_values)
```

**Consolidated Pattern:**
```python
# All use AggregationUtils
centroid_median = AggregationUtils.aggregate_frames_to_track(
    centroid_values, method='median'
)
normalized = MetricUtils.normalize_to_range(centroid_median, 8000.0)

rms_mean = AggregationUtils.aggregate_frames_to_track(rms_values, method='mean')

onset_std = AggregationUtils.aggregate_frames_to_track(onset_values, method='std')

# Or for multiple at once:
results = AggregationUtils.aggregate_multiple(
    values, methods=['median', 'mean', 'std']
)
```

**Affected Modules:**
1. `temporal_analyzer.py` (beat intervals mean) - 5 LOC
2. `harmonic_analyzer.py` (f0 values mean) - 4 LOC
3. `harmonic_analyzer_sampled.py` (chunk aggregation) - 6 LOC
4. `content/feature_extractors.py` (multi-method aggregation) - 15 LOC
5. `ml/feature_extractor.py` (MFCC/Chroma aggregation) - 10 LOC
6. `dynamic_range.py` (RMS variation) - 8 LOC
7. `continuous_target_generator.py` (frame-level) - 12 LOC
8. `spectrum_analyzer.py` (already using AggregationUtils ✓) - 0 LOC

**Expected Savings:** -60 to -90 LOC

**Implementation:**
1. Review each module's aggregation approach
2. Replace with corresponding AggregationUtils call
3. Test for numerical equivalence
4. Update documentation with pattern

---

### Phase 6.5: Consolidate Normalization Logic with MetricUtils (2-3 hours)

**Target Modules:** 12 modules with duplicate normalization

**Current Pattern (scattered min-max):**
```python
# In module A
if max_val > 0:
    normalized = value / max_val
else:
    normalized = 0.5
result = np.clip(normalized, 0, 1)

# In module B (identical)
if max_val > 0:
    normalized = value / max_val
else:
    normalized = 0.5
result = np.clip(normalized, 0, 1)

# In module C (variation)
norm_val = (val - min_val) / (max_val - min_val)
return np.clip(norm_val, 0, 1)
```

**Consolidated Using MetricUtils:**
```python
# All use consistent approach
normalized = MetricUtils.normalize_to_range(value, max_val, clip=True)

# Min-max normalization
normalized = MetricUtils.normalize_to_range(
    value, max_val, min_val=min_val, clip=True
)

# Percentile-based normalization
normalized = MetricUtils.percentile_based_normalization(
    values, percentile=90, clip=True
)
```

**Affected Modules:**
1. `dynamic_range.py` (min-max normalization, 2 instances) - 8 LOC
2. `spectrum_analyzer.py` (magnitude normalization, 2 instances) - 6 LOC
3. `loudness_meter.py` (peak level norm, 1 instance) - 4 LOC
4. `content/feature_extractors.py` (percentile norm, 1 instance) - 5 LOC
5. `phase_correlation.py` (correlation scaling, 1 instance) - 3 LOC
6. `parallel_spectrum_analyzer.py` (bin normalization, 3 instances) - 10 LOC
7. `fingerprint/normalizer.py` (already optimized ✓) - 0 LOC

**Expected Savings:** -40 to -70 LOC

**Implementation:**
1. Audit all normalization patterns
2. Choose appropriate MetricUtils method for each
3. Replace scattered implementations
4. Verify numerical equivalence

---

## Phase 6 Estimated Totals

| Sub-Phase | Focus | Modules | LOC Savings | Duration |
|-----------|-------|---------|------------|----------|
| 6.1 | BaseAnalyzer extension | 3 | -130 | 2-3 hrs |
| 6.2 | BaseQualityAssessor creation | 5 | -250 | 3-4 hrs |
| 6.3 | SafeOperations audit | 7 | -120 | 2-3 hrs |
| 6.4 | AggregationUtils standardization | 8 | -90 | 2-3 hrs |
| 6.5 | MetricUtils normalization | 7 | -70 | 2-3 hrs |
| **Total** | **Extend Phase 5 patterns** | **25+** | **-660** | **11-16 hrs** |

---

## Implementation Strategy

### Priority Order (Recommended Sequence)

1. **Week 1, Day 1-2: Phase 6.1 (BaseAnalyzer Extension)**
   - Quick wins, high confidence
   - Builds on proven pattern
   - Enables Phase 6.2 testing

2. **Week 1, Day 2-3: Phase 6.3 (SafeOperations Audit)**
   - Parallel work possible
   - Quick replacements
   - Numerical validation needed

3. **Week 1, Day 3-4: Phase 6.2 (BaseQualityAssessor)**
   - More complex creation
   - Requires new abstract class
   - Bigger refactoring impact

4. **Week 2, Day 1-2: Phase 6.4 (AggregationUtils Standardization)**
   - Systematic replacement
   - Good for parallel work
   - Validation straightforward

5. **Week 2, Day 2-3: Phase 6.5 (MetricUtils Normalization)**
   - Final consolidation
   - Ties everything together
   - Complete coverage

### Testing Requirements

**Per Sub-Phase:**
- Unit tests for new utility methods
- Integration tests for refactored modules
- Numerical equivalence verification for math operations
- Regression tests to ensure no behavior changes

**Overall:**
- Full test suite pass (no regressions)
- Performance benchmarking (no slowdowns)
- Code coverage maintenance (≥95%)

---

## Success Criteria

✅ **Phase 6 Complete when:**
- All 3 fingerprint analyzers inherit from BaseAnalyzer
- BaseQualityAssessor implemented and applied to all 5 quality modules
- SafeOperations used consistently (15+ locations updated)
- AggregationUtils used in all aggregation scenarios (8 modules)
- MetricUtils used for all normalization (12 modules)
- 660+ LOC consolidated
- All 200+ tests passing
- Zero regressions in fingerprint or quality assessment

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Numerical differences in refactored code | Low | Comprehensive numerical validation tests |
| Quality assessment scoring changes | Low | Preserve thresholds in SCORING_TIERS |
| Performance regression | Low | Benchmark before/after |
| Integration issues | Low | Existing test suite validates interfaces |

---

## Documentation Requirements

1. **ANALYSIS_REFACTORING_GUIDE.md** - Document Phase 6 patterns
2. **Update CLAUDE.md** - Add Phase 6 patterns to project guidelines
3. **Update common_metrics.py docstrings** - Document all utility usage
4. **Create BaseQualityAssessor docstring** - Clear template usage guide

---

## Next Steps

1. Review this plan with development team
2. Schedule Phase 6.1 (BaseAnalyzer) as quick-win proof of concept
3. Run validation tests after each sub-phase
4. Document learnings for future refactoring initiatives

---

**Document Version:** 1.0
**Status:** Ready for Phase 6 Implementation
**Estimated Total Duration:** 11-16 hours (2-3 days of focused work)
**Consolidation Potential:** 660+ LOC (-6.0% of analysis/ directory)

