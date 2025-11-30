# Phase 7 Planning: Advanced Normalization & Optimization Framework

**Status**: Planning Phase
**Date**: November 28, 2025
**Target**: Next release after v1.1.0-beta.3

---

## 📋 Overview

Phase 7 continues code quality improvements initiated in Phase 6, focusing on:

1. **Advanced Normalization Strategies** - Z-score, robust scaling, quantile normalization
2. **Linear Interpolation Framework** - Unified triangular envelope and vectorization
3. **Metric Transformation Pipeline** - Extract and unify complex calculation chains
4. **Performance Optimization** - Vectorization of bottleneck operations

**Phase 6 Foundation**: 22 modules touched, 50+ patterns consolidated, 250+ LOC removed
**Phase 7 Build**: Advanced strategies on top of MetricUtils, improved vectorization, 30-50% speedup targets

---

## 🎯 Phase 7 Subphases (7.0-7.4)

### Phase 7.0: Advanced Normalization Strategies

**Goal**: Extend MetricUtils with z-score, robust scaling, and quantile normalization

#### 7.0.1 - Z-Score Normalization Implementation

**File**: `auralis/analysis/fingerprint/common_metrics.py`

**New Method**:
```python
@staticmethod
def normalize_with_zscore(values: np.ndarray, mean: Optional[float] = None,
                         std: Optional[float] = None, epsilon: float = 1e-10) -> np.ndarray:
    """
    Z-score normalization: (x - mean) / std

    Returns: Array centered at 0 with std deviation of 1
    Use Case: Distribution-aware normalization, better for outlier handling than min-max
    """
```

**Locations Using Z-Score**:
- `normalizer.py` lines 153-154 (already calculates mean/std, reuse them)
- `harmonic_analyzer.py` lines 147-152 (pitch stability calculation)
- `variation_analyzer.py` lines 129-130 (crest variation)

**Impact**: 3 modules, better handling of outliers

#### 7.0.2 - Robust Scaling (IQR-Based)

**File**: `auralis/analysis/fingerprint/common_metrics.py`

**New Method**:
```python
@staticmethod
def robust_scale(values: np.ndarray, q1: Optional[float] = None,
                 q3: Optional[float] = None, epsilon: float = 1e-10) -> np.ndarray:
    """
    Robust scaling: (x - Q2) / (Q3 - Q1)

    Returns: Array scaled by interquartile range (less affected by outliers)
    Use Case: Data with extreme outliers, preferred over z-score for robustness
    """
```

**Implementation**:
- Uses `np.percentile(values, [25, 50, 75])` for Q1, Q2, Q3
- Fallback to z-score if IQR is zero
- Epsilon guard against division by zero

**Impact**: Robust normalization alternative for fingerprinting

#### 7.0.3 - Quantile Normalization

**File**: `auralis/analysis/fingerprint/common_metrics.py`

**New Method**:
```python
@staticmethod
def quantile_normalize(values: np.ndarray, reference: Optional[np.ndarray] = None,
                      quantiles: Optional[np.ndarray] = None) -> np.ndarray:
    """
    Quantile normalization: Normalize to reference distribution

    Returns: Array with values replaced by quantile averages
    Use Case: Distribution matching, fingerprint batch normalization
    """
```

**Implementation**:
- Transform values to match reference distribution (or uniform if no reference)
- Use `np.interp()` for efficient quantile mapping
- Reference can be from training set or previous batch

**Impact**: Better batch normalization for fingerprints

---

### Phase 7.1: Linear Interpolation Framework

**Goal**: Extract and unify triangular envelope creation, vectorize perceptual weighting

#### 7.1.1 - Triangular Envelope Helper

**New Module**: `auralis/dsp/utils/interpolation_helpers.py`

**New Function**:
```python
def create_triangular_envelope(start: float, center: float, end: float,
                              length: int, strategy: str = 'linear') -> np.ndarray:
    """
    Create triangular (tent) filter response.

    Strategies:
    - 'linear': Simple linear slopes (current)
    - 'hann': Hann window variant (smoother)
    - 'hamming': Hamming window variant (less overshoot)

    Returns: Filter response array

    Performance: Fully vectorized with numpy, handles all envelope types
    """
```

**Used In**:
- `feature_extractor.py` lines 317-323 (mel filterbank) - Replace loop with function call
- `filters.py` lines 124-132 (filter bank) - Replace loop with function call
- `critical_bands.py` lines 100-119 (perceptual weighting) - Can use for window creation

**Impact**: 3 modules, unified envelope creation, ~20% vectorization speedup

#### 7.1.2 - Vectorized Perceptual Weighting

**File**: `auralis/dsp/eq/critical_bands.py`

**Current Implementation** (lines 103-117): Loop-based conditional assignments
```python
for i, freq in enumerate(frequencies):
    if freq < 100:
        weights[i] = 0.1
    elif freq < 1000:
        weights[i] = 0.7 + 0.3 * (freq - 100) / 900  # Linear interpolation
    # ... more conditions
```

**Vectorized Alternative**:
```python
# Use np.piecewise() or np.select() for vectorized conditional application
weights = np.select(
    [frequencies < 100, (frequencies >= 100) & (frequencies < 1000), ...],
    [0.1, 0.7 + 0.3 * (frequencies - 100) / 900, ...]
)
```

**Performance Target**: 5-10x speedup on large frequency arrays

**Impact**: Spectrum analysis, ~5% overall application speedup

#### 7.1.3 - Frequency-to-Band Mapping Vectorization

**File**: `auralis/dsp/eq/critical_bands.py`

**Current Implementation** (lines 139-149): O(n*m) nested loop

**Vectorized Alternative**:
```python
# Use np.searchsorted() for O(n log m) mapping
band_indices = np.searchsorted(band_edges, frequencies, side='right') - 1
```

**Performance Target**: 100-500x speedup for large frequency sets

**Impact**: Critical bands analysis

---

### Phase 7.2: Metric Transformation Pipeline

**Goal**: Extract complex calculation chains as reusable, composable patterns

#### 7.2.1 - Variation Metrics Unification

**File**: `auralis/analysis/fingerprint/variation_analyzer.py`

**Current Patterns** (3 separate implementations):
1. `_calculate_dynamic_range_variation()` - RMS → dB → Std → Normalize
2. `_calculate_loudness_variation()` - RMS → dB → Std → Clip
3. `_calculate_peak_consistency()` - Peak detection → Std → CV → Stability

**Unified Implementation**:
```python
class VariationMetrics:
    """Unified variation calculation pipeline."""

    @staticmethod
    def calculate_from_rms(rms_db: np.ndarray) -> tuple[float, float]:
        """Calculate dynamic range and loudness variation from RMS."""
        return (np.std(rms_db), MetricUtils.clip_to_range(np.std(rms_db), 0, 10))

    @staticmethod
    def calculate_from_peaks(peaks: np.ndarray) -> tuple[float, float]:
        """Calculate peak consistency from peak values."""
        peak_std = np.std(peaks)
        peak_mean = np.mean(peaks)
        if peak_mean > 0:
            cv = peak_std / peak_mean
            consistency = MetricUtils.stability_from_cv(cv)
            return (peak_std, np.clip(consistency, 0, 1))
        return (peak_std, 0.5)
```

**Modules Affected**:
- `variation_analyzer.py` - Use unified implementation
- `temporal_analyzer.py` - Align rhythm_stability pattern
- `harmonic_analyzer.py` - Align pitch_stability pattern

**Impact**: 50 LOC eliminated, clearer semantics

#### 7.2.2 - Stability Calculation Pattern

**File**: `auralis/analysis/fingerprint/temporal_analyzer.py`

**Pattern**:
```
Extract metric → Calculate CV → Convert to stability score (0-1)
```

**Current Implementations** (should be unified):
1. Rhythm stability (temporal_analyzer.py lines 136-142)
2. Pitch stability (harmonic_analyzer.py lines 147-152)
3. Peak consistency (variation_analyzer.py lines 211-215)

**Unified Helper**:
```python
@staticmethod
def calculate_stability_from_metric(values: np.ndarray,
                                   scale: float = 1.0,
                                   cv_threshold: float = 0.01) -> float:
    """
    Universal stability calculation: metric → CV → stability score.

    Parameters:
    - scale: CV scaling factor (default 1.0, harmonic_analyzer uses 10.0)
    - cv_threshold: Minimum CV before considering as stable

    Returns: Stability score 0-1
    """
```

**Impact**: 30 LOC eliminated, parameterized reusability

#### 7.2.3 - EQ Parameter Mapping Vectorization

**File**: `auralis/analysis/fingerprint/parameter_mapper.py`

**Current Implementation** (lines 59-98):
```python
# 8 separate normalization calls for 8 frequency bands
for band in bands:
    self._normalize_to_db(band.frequency, target_loudness)  # Called 8 times
```

**Vectorized Alternative**:
```python
# Calculate all band gains at once
gains = self._normalize_batch_to_db(frequencies, target_loudness)
```

**Implementation**:
```python
def _normalize_batch_to_db(self, frequencies: np.ndarray,
                          target: float) -> np.ndarray:
    """Vectorized dB normalization for multiple frequencies."""
    return np.interp(frequencies, self.calibration_freqs,
                     self.calibration_response) * (target / self.reference_level)
```

**Performance Target**: 8x speedup on EQ mapping

---

### Phase 7.3: Fingerprint Optimization

**Goal**: Apply advanced normalization strategies to fingerprint system

#### 7.3.1 - Fingerprint Normalizer Enhancement

**File**: `auralis/analysis/fingerprint/normalizer.py`

**Current**: Only percentile-based (5-95th percentile)

**Enhancement**:
```python
def normalize(self, fingerprint: np.ndarray, strategy: str = 'percentile') -> np.ndarray:
    """
    Normalize fingerprint using specified strategy.

    Strategies:
    - 'percentile': Current (5-95th percentile bounds)
    - 'zscore': Z-score normalization (mean 0, std 1)
    - 'robust': Robust scaling (IQR-based)
    - 'quantile': Quantile normalization
    """

    if strategy == 'percentile':
        return self._normalize_percentile(fingerprint)
    elif strategy == 'zscore':
        return self._normalize_zscore(fingerprint)
    elif strategy == 'robust':
        return self._normalize_robust(fingerprint)
    elif strategy == 'quantile':
        return self._normalize_quantile(fingerprint)
```

**Batch Optimization**:
```python
def normalize_batch(self, fingerprints: np.ndarray, strategy: str = 'percentile') -> np.ndarray:
    """
    Vectorized batch normalization (replace loop with matrix operations).

    Before: [self.normalize(fp, strategy) for fp in fingerprints]  # Loop
    After: Vectorized matrix operations for all fingerprints at once
    """
```

**Impact**: Better fingerprint matching, 3-5x speedup on batch operations

#### 7.3.2 - Similarity Calculation Optimization

**File**: `auralis/analysis/fingerprint/similarity.py`

**Current Implementation** (lines 140-151):
```python
# Normalize query, then normalize batch
query_normalized = self.normalizer.normalize(query)
candidates = self.database.get_candidates(limit=100)
candidates_normalized = self.normalizer.normalize_batch(candidates)
```

**Optimization**:
```python
# Pre-normalize entire database on load (one-time cost)
# Query uses same normalization
# Similarity calculation uses consistent normalization
```

**Impact**: ~2x speedup on similarity search if database is pre-normalized

---

### Phase 7.4: Performance Benchmarking & Validation

**Goal**: Measure improvements, validate backward compatibility, ensure no regressions

#### 7.4.1 - Benchmark Suite

**New File**: `tests/performance/phase_7_optimizations.py`

**Tests**:
```python
# Z-score normalization performance
def test_zscore_vs_percentile_normalization()

# Robust scaling performance
def test_robust_scaling_performance()

# Triangular envelope vectorization
def test_triangular_envelope_vectorization()

# Perceptual weighting vectorization
def test_perceptual_weighting_vectorization()

# Frequency mapping vectorization
def test_frequency_mapping_vectorization()

# Batch normalization vectorization
def test_batch_normalization_vectorization()

# Full pipeline optimization
def test_end_to_end_optimization()
```

**Targets**:
- Z-score: < 5% slower than percentile (for accuracy trade-off)
- Robust scaling: ~30% slower than percentile (but more robust)
- Triangular envelope: **20x faster** (vectorized)
- Perceptual weighting: **5-10x faster** (vectorized)
- Frequency mapping: **100-500x faster** (searchsorted)
- Batch normalization: **3-5x faster** (vectorized)

#### 7.4.2 - Regression Testing

**Ensure**:
- Zero regression in fingerprint accuracy
- Zero regression in audio quality metrics
- All 82 analysis tests still pass
- New tests for each optimization reach 100% coverage

#### 7.4.3 - Backward Compatibility

**Guarantee**:
- `MetricUtils` default behavior unchanged
- Fingerprint normalizer default strategy remains 'percentile'
- All existing APIs remain unchanged (add new ones only)

---

## 📊 Implementation Roadmap

### Week 1: Phase 7.0 (Advanced Normalization)

**Days 1-2**: Z-score implementation
- Add `normalize_with_zscore()` to MetricUtils
- Refactor harmonic_analyzer.py, variation_analyzer.py
- Tests: 5 new tests, 82/82 existing pass

**Days 3-4**: Robust scaling
- Add `robust_scale()` to MetricUtils
- Add benchmarking utilities
- Tests: 5 new tests

**Day 5**: Quantile normalization
- Add `quantile_normalize()` to MetricUtils
- Integration tests: 5 new tests

### Week 2: Phase 7.1 (Linear Interpolation)

**Days 1-2**: Triangular envelope extraction
- Create `interpolation_helpers.py` module
- Refactor feature_extractor.py, filters.py
- Tests: 10 new tests

**Days 3-5**: Vectorization
- Perceptual weighting vectorization
- Frequency mapping vectorization
- Performance benchmarks: 5 new tests

### Week 3: Phase 7.2-7.3 (Pipelines & Fingerprints)

**Days 1-2**: Variation metrics unification
- Extract VariationMetrics class
- Refactor variation_analyzer.py, temporal_analyzer.py
- Tests: 10 new tests

**Days 3-4**: EQ parameter mapping vectorization
- Vectorize parameter_mapper.py
- Tests: 5 new tests

**Day 5**: Fingerprint optimizer enhancement
- Add strategy parameter to normalizer
- Batch vectorization
- Tests: 10 new tests

### Week 4: Phase 7.4 (Benchmarking & Validation)

**Days 1-3**: Comprehensive benchmarking
- Performance suite setup
- Measure all optimizations
- Document improvements

**Days 4-5**: Regression testing & release prep
- Run full test suite (850+)
- Validate zero regressions
- Create Phase 7 completion report

---

## 📋 Success Criteria

### Code Quality
- [ ] All 82 analysis tests pass (zero regressions)
- [ ] New tests reach 100% coverage of optimizations
- [ ] All MetricUtils methods have docstrings with examples
- [ ] All new modules follow project style guidelines

### Performance
- [ ] Triangular envelope: **20x faster** (vectorized)
- [ ] Perceptual weighting: **5-10x faster** (vectorized)
- [ ] Frequency mapping: **100-500x faster** (searchsorted)
- [ ] Batch normalization: **3-5x faster** (vectorized)
- [ ] Z-score: <5% slower than percentile
- [ ] Robust scaling: Measurable accuracy improvement on outlier data

### Backward Compatibility
- [ ] 100% backward compatible
- [ ] Default behavior unchanged
- [ ] All existing APIs work as-is

### Documentation
- [ ] Phase 7 completion report
- [ ] Updated CLAUDE.md with new utilities
- [ ] Benchmark results documented
- [ ] Migration guide (optional methods)

---

## 🔗 Related Documentation

- **[Phase 6 Final Report](PHASE_6_COMPLETION.md)** - Foundation for Phase 7
- **[CLAUDE.md](CLAUDE.md)** - Architecture and development guidelines
- **[DEVELOPMENT_ROADMAP_1_1_0.md](DEVELOPMENT_ROADMAP_1_1_0.md)** - Strategic direction

---

## 📝 Notes

### Why These Optimizations?

1. **Advanced Normalization**: Different distributions require different strategies
   - Z-score: Good for normally distributed data
   - Robust scaling: Good with outliers
   - Quantile: Good for arbitrary distributions

2. **Vectorization**: Current bottlenecks identified:
   - Per-frequency weighting applied in loops
   - Per-band assignments in loops
   - Batch normalization with list comprehension

3. **Pipelines**: Complex calculations are easier to understand and maintain when extracted

### Risk Assessment

- **Low Risk**: All optimizations preserve numerical behavior
- **Validation**: 850+ existing tests catch any regression
- **Rollback**: Easy to revert to percentile normalization if issues arise

---

**Phase 7 Planning Complete**
**Next Step**: Implement Phase 7.0 (Advanced Normalization Strategies)
**Timeline**: Ready to begin implementation
