# Phase 7: Extending Fingerprint Refactoring to auralis/analysis

**Status**: Planning Phase
**Date**: 2025-11-30
**Scope**: Extend fingerprint module's successful refactoring patterns to entire analysis directory
**Estimated Impact**: 2,000+ lines of duplicate code elimination, 8-10 new utility modules, unified interface patterns

---

## Executive Summary

The fingerprint module refactoring (Phases 1-6) established a proven pattern:
- **Utilities layer** for domain-specific calculations
- **Base classes** for shared behavior
- **Thin analyzer wrappers** (50-80 lines) delegating to utilities
- **Common metrics** module for constants and helpers

This pattern can be directly replicated in `auralis/analysis` to eliminate **2,000+ lines of duplicate code** and unify fragmented functionality.

---

## Current State Analysis

### Module Breakdown (65 Python files, ~14,721 lines)

| Module | Files | Lines | Status | Issues |
|--------|-------|-------|--------|--------|
| fingerprint/ | 44 | 4,027 | ✅ Refactored | Baseline (perfect model) |
| quality/ | 6 | 1,163 | ❌ Monolithic | 5 assessors, each 150-250L, repeated scoring logic |
| content/ | 4 | 679 | ❌ Duplicated | Feature extraction overlaps with ml/ |
| ml/ | 5 | 143 | ❌ Duplicated | Feature extraction duplicates content/ |
| Root level | 6+ | 2,000+ | ❌ Scattered | Spectrum analyzer duplicates, no organization |

### Critical Duplication Found

**1. Spectrum Analysis (95% Duplication)**
- `spectrum_analyzer.py` (200+ L)
- `parallel_spectrum_analyzer.py` (250+ L) - Copy of above with threading
- `content_aware_analyzer.py` - Partial copy of spectrum analysis
- **Problem**: parallel version should inherit, not duplicate
- **Savings Potential**: 150+ lines

**2. Feature Extraction (60% Overlap)**
- `content/feature_extractors.py` (331 L) - Genre/mood feature extraction
- `ml/feature_extractor.py` (varies) - ML feature extraction
- **Common Calculations**:
  - spectral_centroid, spectral_rolloff, zero_crossing_rate
  - crest_factor, tempo_estimate, spectral_bandwidth
  - spectral_flatness, harmonic_ratio, fundamental_frequency
- **Differences**: ML adds MFCC/chroma/tonnetz, content adds attack_time/spread
- **Savings Potential**: 200+ lines

**3. Quality Assessment (Monolithic)**
- 5 assessor files with identical scoring patterns:
  - `loudness_assessment.py` (253 L)
  - `stereo_assessment.py` (190 L)
  - `distortion_assessment.py` (184 L)
  - `frequency_assessment.py` (151 L)
  - `dynamic_assessment.py` (115 L)
- **Problem**: Each has `_score_*()` and `_estimate_*()` methods with duplication
- **Savings Potential**: 300+ lines

---

## Phase 7 Breakdown

### Phase 7.1: Quality Assessment Module Consolidation

**Goal**: Reduce 1,163 lines to ~750 lines by extracting utilities

**Current Structure**:
```
quality/
├── __init__.py
├── quality_metrics.py (242 L) - Orchestrator
├── loudness_assessment.py (253 L) - Scoring logic + calculations
├── stereo_assessment.py (190 L) - Scoring logic + calculations
├── distortion_assessment.py (184 L) - Scoring logic + calculations
├── frequency_assessment.py (151 L) - Scoring logic + calculations
└── dynamic_assessment.py (115 L) - Scoring logic + calculations
```

**Target Structure**:
```
quality_assessors/
├── __init__.py
├── utilities/
│   ├── __init__.py
│   ├── scoring_ops.py (150 L) - ScoringOperations class
│   ├── estimation_ops.py (120 L) - EstimationOperations class
│   ├── frequency_ops.py (100 L) - FrequencyWeighting, reference curves
│   └── assessment_constants.py (80 L) - Target values, ranges
├── base_assessor.py (60 L) - BaseAssessor abstract class
├── loudness_assessor.py (80 L) - Thin wrapper using utilities
├── stereo_assessor.py (75 L) - Thin wrapper using utilities
├── distortion_assessor.py (75 L) - Thin wrapper using utilities
├── frequency_assessor.py (70 L) - Thin wrapper using utilities
└── dynamic_assessor.py (70 L) - Thin wrapper using utilities
```

**Extracted Utilities**:

#### 7.1.1 `scoring_ops.py` - ScoringOperations
```python
class ScoringOperations:
    """Common scoring patterns for quality assessments"""

    @staticmethod
    def linear_scale_score(value: float, min_val: float, max_val: float,
                          inverted: bool = False) -> float:
        """Map value to 0-1 scale between min/max"""
        # Used by all assessors for normalization

    @staticmethod
    def range_based_score(value: float, optimal_range: tuple,
                         acceptable_range: tuple) -> float:
        """Score based on optimal/acceptable ranges"""
        # Used by loudness, dynamic range, frequency assessments

    @staticmethod
    def exponential_penalty(value: float, target: float,
                           steepness: float = 1.0) -> float:
        """Apply exponential penalty for deviation from target"""
        # Used for clipping detection, distortion scoring

    @staticmethod
    def weighted_score(*scores_and_weights) -> float:
        """Combine multiple scores with weights"""
        # Used for composite assessments (frequency, stereo)

    @staticmethod
    def percentile_score(value: float, percentiles: dict) -> float:
        """Score based on percentile distribution"""
        # Used for dynamic range, loudness consistency
```

**Implementation Impact**:
- Eliminates `_score_*()` methods in 5 files
- Centralizes scoring logic for consistency
- Enables parameterized scoring across assessors
- **Lines Saved**: 120+ lines

#### 7.1.2 `estimation_ops.py` - EstimationOperations
```python
class EstimationOperations:
    """Common signal estimation patterns"""

    @staticmethod
    def estimate_thd(audio: np.ndarray, sr: int,
                     fundamental_idx: Optional[int] = None) -> float:
        """Estimate Total Harmonic Distortion"""
        # Used by distortion_assessment

    @staticmethod
    def detect_clipping(audio: np.ndarray, threshold: float = 0.95) -> bool:
        """Detect if audio is clipped"""
        # Used by distortion_assessment

    @staticmethod
    def estimate_noise_floor(audio: np.ndarray,
                            silence_threshold: float = 1e-6) -> float:
        """Estimate noise floor from silence sections"""
        # Used by distortion_assessment, frequency_assessment

    @staticmethod
    def compute_stereo_correlation(left: np.ndarray,
                                   right: np.ndarray) -> float:
        """Compute stereo correlation coefficient"""
        # Used by stereo_assessment

    @staticmethod
    def estimate_dynamic_range(audio: np.ndarray, sr: int) -> float:
        """Estimate dynamic range (peak-to-noise)"""
        # Used by dynamic_assessment

    @staticmethod
    def detect_phase_issues(left: np.ndarray, right: np.ndarray) -> float:
        """Detect phase alignment issues"""
        # Used by stereo_assessment
```

**Implementation Impact**:
- Consolidates `_estimate_*()` methods across assessors
- Centralizes detection algorithms
- **Lines Saved**: 100+ lines

#### 7.1.3 `frequency_ops.py` - FrequencyOperations
```python
class FrequencyWeighting:
    """ISO/IEC frequency weighting curves"""

    @staticmethod
    def a_weighting(frequencies: np.ndarray) -> np.ndarray:
        """ISO 61672-1 A-weighting curve"""

    @staticmethod
    def c_weighting(frequencies: np.ndarray) -> np.ndarray:
        """ISO 61672-1 C-weighting curve"""

    @staticmethod
    def z_weighting(frequencies: np.ndarray) -> np.ndarray:
        """ISO 61672-1 Z-weighting curve"""

class FrequencyOperations:
    """Frequency response operations"""

    @staticmethod
    def create_reference_curves(freq_bins: np.ndarray,
                               profile: str = 'flat') -> np.ndarray:
        """Create reference frequency response curves"""
        # Used by frequency_assessment

    @staticmethod
    def estimate_frequency_balance(magnitude: np.ndarray,
                                  freq_bins: np.ndarray) -> float:
        """Estimate frequency balance (-1 to +1)"""

    @staticmethod
    def detect_excessive_bass(magnitude: np.ndarray,
                             freq_bins: np.ndarray) -> float:
        """Detect excessive bass frequency content"""

    @staticmethod
    def detect_excessive_treble(magnitude: np.ndarray,
                               freq_bins: np.ndarray) -> float:
        """Detect excessive treble frequency content"""
```

**Implementation Impact**:
- Consolidates frequency curve calculations
- Used by frequency_assessment and other modules
- **Lines Saved**: 80+ lines

#### 7.1.4 `assessment_constants.py`
```python
class AssessmentConstants:
    """Target values and ranges for quality assessments"""

    # Loudness targets (ITU-R BS.1770-4)
    TARGET_INTEGRATED_LUFS = -14.0
    TARGET_LOUDNESS_RANGE = (7.0, 20.0)  # dB
    ACCEPTABLE_LOUDNESS_RANGE = (4.0, 22.0)

    # Dynamic range targets
    TARGET_DR_VALUE = 14  # dB
    MINIMUM_DR_VALUE = 6
    EXCELLENT_DR_VALUE = 18

    # Stereo correlation targets
    TARGET_CORRELATION = 0.7
    EXCELLENT_CORRELATION = 0.85
    ACCEPTABLE_CORRELATION = 0.5

    # Frequency response targets
    ACCEPTABLE_FREQUENCY_BALANCE = (-3.0, 3.0)  # dB
    EXCELLENT_FREQUENCY_BALANCE = (-1.0, 1.0)

    # Distortion limits
    ACCEPTABLE_THD = 0.05  # %
    EXCELLENT_THD = 0.01
    CLIPPING_THRESHOLD = 0.98  # Normalized amplitude
```

**Implementation Impact**:
- Centralizes all target values
- Enables consistent assessment across modules
- Easier to adjust targets globally
- **Lines Saved**: 60+ lines

### Phase 7.2: Feature Extraction Consolidation

**Goal**: Unify content/ and ml/ feature extractors with shared utilities

**Current Structure**:
```
content/
├── analyzers.py (240 L)
├── feature_extractors.py (331 L) - FeatureExtractor class
└── recommendations.py

ml/
├── feature_extractor.py - FeatureExtractor class (duplicates content/)
├── features.py - DataClass definitions
├── genre_classifier.py
└── genre_weights.py
```

**Target Structure**:
```
feature_extraction/
├── __init__.py
├── utilities/
│   ├── __init__.py
│   ├── spectral_ops.py (100 L) - Shared spectral calculations
│   ├── temporal_ops.py (80 L) - Shared temporal calculations
│   ├── harmonic_ops.py (80 L) - Shared harmonic calculations
│   ├── energy_ops.py (70 L) - Energy distribution calculations
│   └── ml_advanced_ops.py (100 L) - MFCC, chroma, tonnetz
├── features.py (80 L) - Unified AudioFeatures, MLFeatures dataclasses
├── base_extractor.py (100 L) - BaseFeatureExtractor abstract class
├── content_extractor.py (150 L) - ContentExtractor extends base
├── ml_extractor.py (150 L) - MLExtractor extends base
└── genre_classifier.py (100 L) - Unified genre classification
```

**Extracted Utilities**:

#### 7.2.1 `spectral_ops.py` - Shared Spectral Features
```python
class SpectralFeatures:
    """Shared spectral feature calculations"""

    @staticmethod
    def centroid(audio: np.ndarray, sr: int) -> float:
        """Spectral centroid frequency"""

    @staticmethod
    def rolloff(audio: np.ndarray, sr: int, threshold: float = 0.85) -> float:
        """Spectral rolloff frequency"""

    @staticmethod
    def flatness(audio: np.ndarray, magnitude: Optional[np.ndarray] = None) -> float:
        """Spectral flatness (spectral entropy)"""

    @staticmethod
    def spread(audio: np.ndarray, sr: int) -> float:
        """Spectral spread around centroid"""

    @staticmethod
    def contrast(audio: np.ndarray, sr: int) -> np.ndarray:
        """Spectral contrast per frequency band"""

    @staticmethod
    def bandwidth(audio: np.ndarray, sr: int) -> float:
        """Spectral bandwidth"""
```

**Implementation Impact**:
- Consolidates spectral calculations from both feature_extractors
- Used by content analyzer and ML classifier
- **Lines Saved**: 80+ lines

#### 7.2.2 `temporal_ops.py` - Shared Temporal Features
```python
class TemporalFeatures:
    """Shared temporal feature calculations"""

    @staticmethod
    def zero_crossing_rate(audio: np.ndarray) -> float:
        """Zero crossing rate"""

    @staticmethod
    def tempo_estimate(audio: np.ndarray, sr: int) -> float:
        """BPM estimation using onset detection"""

    @staticmethod
    def tempo_stability(audio: np.ndarray, sr: int) -> float:
        """Stability of detected tempo"""

    @staticmethod
    def onset_rate(audio: np.ndarray, sr: int) -> float:
        """Rate of note onsets per second"""

    @staticmethod
    def crest_factor(audio: np.ndarray) -> float:
        """Peak-to-RMS ratio"""

    @staticmethod
    def attack_time(audio: np.ndarray, sr: int) -> float:
        """Time to reach peak amplitude (onset characterization)"""
```

**Implementation Impact**:
- Consolidates temporal calculations
- Used by both content and ML extractors
- **Lines Saved**: 70+ lines

#### 7.2.3 `harmonic_ops.py` - Shared Harmonic Features
```python
class HarmonicFeatures:
    """Shared harmonic feature calculations"""

    @staticmethod
    def harmonic_ratio(audio: np.ndarray) -> float:
        """Ratio of harmonic to total energy"""

    @staticmethod
    def fundamental_frequency(audio: np.ndarray, sr: int) -> float:
        """Fundamental frequency (pitch)"""

    @staticmethod
    def inharmonicity(audio: np.ndarray, sr: int) -> float:
        """Degree of inharmonicity (deviation from harmonic)"""

    @staticmethod
    def harmonic_centroid(audio: np.ndarray, sr: int) -> float:
        """Centroid of harmonic partial distribution"""
```

**Implementation Impact**:
- Consolidates harmonic calculations
- **Lines Saved**: 60+ lines

#### 7.2.4 `energy_ops.py` - Energy Distribution
```python
class EnergyOperations:
    """Energy distribution and intensity calculations"""

    @staticmethod
    def rms_energy(audio: np.ndarray) -> float:
        """Root Mean Square energy"""

    @staticmethod
    def energy_distribution(audio: np.ndarray, sr: int,
                           num_bands: int = 10) -> np.ndarray:
        """Energy distribution across frequency bands"""

    @staticmethod
    def energy_entropy(audio: np.ndarray) -> float:
        """Shannon entropy of frame energy distribution"""

    @staticmethod
    def power_spectrum_centroid(audio: np.ndarray, sr: int) -> float:
        """Power-weighted spectral centroid"""
```

**Implementation Impact**:
- Consolidates energy calculations
- **Lines Saved**: 50+ lines

#### 7.2.5 `ml_advanced_ops.py` - ML-Specific Features
```python
class MLAdvancedFeatures:
    """ML-specific advanced feature extraction"""

    @staticmethod
    def mfcc(audio: np.ndarray, sr: int, n_mfcc: int = 13) -> np.ndarray:
        """Mel-Frequency Cepstral Coefficients"""

    @staticmethod
    def chroma_cqt(audio: np.ndarray, sr: int) -> np.ndarray:
        """Chroma features from Constant-Q transform"""

    @staticmethod
    def chroma_stft(audio: np.ndarray, sr: int) -> np.ndarray:
        """Chroma features from Short-Time Fourier Transform"""

    @staticmethod
    def tonnetz(audio: np.ndarray, sr: int) -> np.ndarray:
        """Tonal centroid features"""

    @staticmethod
    def zero_crossing_rate_slope(audio: np.ndarray) -> float:
        """Trend in zero crossing rate"""
```

**Implementation Impact**:
- Consolidates ML-specific calculations
- Keeps ML extensions separate from base features
- **Lines Saved**: 80+ lines

### Phase 7.3: Spectrum Analyzer Unification

**Goal**: Consolidate spectrum_analyzer and parallel_spectrum_analyzer

**Current Structure**:
```
analysis/
├── spectrum_analyzer.py (200+ L) - SpectrumAnalyzer
├── parallel_spectrum_analyzer.py (250+ L) - 95% copy + threading
└── content_aware_analyzer.py (100+ L) - Partial copy
```

**Target Structure**:
```
spectrum_analysis/
├── __init__.py
├── utilities/
│   ├── __init__.py
│   ├── frequency_weighting.py (80 L) - Weighting curves
│   └── window_operations.py (70 L) - FFT windows, hop calculations
├── base_spectrum_analyzer.py (200 L) - Core implementation
├── spectrum_analyzer.py (50 L) - Thin wrapper (sequential)
└── parallel_spectrum_analyzer.py (80 L) - Thin wrapper (parallel)
```

**Extracted Utilities**:

#### 7.3.1 `frequency_weighting.py`
```python
class FrequencyWeighting:
    """Frequency weighting curves for spectrum analysis"""

    @staticmethod
    def a_weighting(frequencies: np.ndarray) -> np.ndarray:
        """A-weighting curve (ISO 61672-1)"""

    @staticmethod
    def c_weighting(frequencies: np.ndarray) -> np.ndarray:
        """C-weighting curve"""

    @staticmethod
    def z_weighting(frequencies: np.ndarray) -> np.ndarray:
        """Z-weighting curve (linear, no weighting)"""

    @staticmethod
    def apply_weighting(magnitude: np.ndarray, frequencies: np.ndarray,
                       weighting: str = 'z') -> np.ndarray:
        """Apply weighting curve to spectrum"""
```

**Implementation Impact**:
- Consolidates weighting curves from multiple files
- **Lines Saved**: 60+ lines

#### 7.3.2 `base_spectrum_analyzer.py`
```python
class BaseSpectrumAnalyzer:
    """Core spectrum analysis implementation"""

    def __init__(self, sample_rate: int, fft_size: int = 2048,
                 hop_length: int = 512, window: str = 'hann'):
        """Initialize spectrum analyzer"""

    def analyze(self, audio: np.ndarray) -> Dict[str, np.ndarray]:
        """Analyze spectrum (magnitude, phase, frequency bins, etc)"""

    def _compute_magnitude_spectrum(self, audio: np.ndarray) -> np.ndarray:
        """Compute magnitude spectrum (shared between sequential/parallel)"""

    def _create_frequency_bins(self) -> np.ndarray:
        """Create frequency bin centers"""

    def _apply_smoothing(self, spectrum: np.ndarray) -> np.ndarray:
        """Apply smoothing to spectrum"""

class SequentialSpectrumAnalyzer(BaseSpectrumAnalyzer):
    """Sequential spectrum analysis"""

    def analyze(self, audio: np.ndarray) -> Dict[str, np.ndarray]:
        """Analyze using sequential FFT"""

class ParallelSpectrumAnalyzer(BaseSpectrumAnalyzer):
    """Parallel spectrum analysis using multiple cores"""

    def __init__(self, *args, num_workers: int = 4, **kwargs):
        """Initialize with worker pool"""

    def analyze(self, audio: np.ndarray) -> Dict[str, np.ndarray]:
        """Analyze using parallel FFT computation"""
```

**Implementation Impact**:
- Eliminates 95% duplication between spectrum_analyzer.py and parallel_spectrum_analyzer.py
- Uses inheritance instead of copying
- **Lines Saved**: 150+ lines

### Phase 7.4: Root Level Analysis Reorganization

**Goal**: Organize scattered root-level analyzer files into clear subdirectories

**Current State**:
- loudness_meter.py - Standalone
- phase_correlation.py - Standalone
- dynamic_range.py - Standalone
- batch_analyzer.py - Orchestrator
- Other specialized analyzers scattered

**Target Structure**:
```
analysis/
├── fingerprint/ (already organized ✓)
├── content/ (refactored under Phase 7.2)
├── quality_assessors/ (refactored under Phase 7.1)
├── ml/ (consolidated under Phase 7.2)
├── feature_extraction/ (new under Phase 7.2)
├── spectrum_analysis/ (new under Phase 7.3)
├── loudness_analysis/
│   ├── __init__.py
│   ├── loudness_meter.py (moved from root)
│   └── utilities/
│       └── lufs_calculator.py
├── stereo_analysis/
│   ├── __init__.py
│   ├── phase_correlation.py (moved from root)
│   └── stereo_assessment.py (moved from quality)
├── dynamics_analysis/
│   ├── __init__.py
│   ├── dynamic_range.py (moved from root)
│   └── dynamics_assessment.py (moved from quality)
├── batch_analyzer.py (moved to orchestration/)
└── __init__.py (root level - imports consolidated modules)
```

**Implementation Impact**:
- Clear domain organization
- Eliminates scattered files
- Easier to locate functionality

---

## Implementation Roadmap

### Phase 7.1: Quality Assessment (40-50 hours)
**Priority**: HIGH (many interdependencies)

1. Create `quality_assessors/utilities/` directory structure
2. Extract `ScoringOperations` to `scoring_ops.py`
3. Extract `EstimationOperations` to `estimation_ops.py`
4. Extract `FrequencyOperations` to `frequency_ops.py`
5. Extract constants to `assessment_constants.py`
6. Create `BaseAssessor` abstract class
7. Refactor 5 assessor files to thin implementations
8. Update quality_metrics.py orchestrator
9. Update all imports
10. Run tests, verify zero regressions

**Deliverables**:
- `quality_assessors/` module (complete)
- `REFACTORING_PHASE_7_1_SUMMARY.md`
- All tests passing
- 300+ lines eliminated

### Phase 7.2: Feature Extraction (50-60 hours)
**Priority**: HIGH (touches 2 modules)

1. Create `feature_extraction/utilities/` directory structure
2. Extract spectral calculations to `spectral_ops.py`
3. Extract temporal calculations to `temporal_ops.py`
4. Extract harmonic calculations to `harmonic_ops.py`
5. Extract energy calculations to `energy_ops.py`
6. Extract ML-specific features to `ml_advanced_ops.py`
7. Consolidate dataclass definitions in `features.py`
8. Create `BaseFeatureExtractor` abstract class
9. Refactor `ContentExtractor` (extending base)
10. Refactor `MLExtractor` (extending base)
11. Unify genre classification logic
12. Update all imports in content/ and ml/
13. Run tests, verify zero regressions

**Deliverables**:
- `feature_extraction/` module (complete)
- `REFACTORING_PHASE_7_2_SUMMARY.md`
- All tests passing
- 250+ lines eliminated

### Phase 7.3: Spectrum Analysis (30-40 hours)
**Priority**: MEDIUM (fewer dependencies)

1. Create `spectrum_analysis/utilities/` directory structure
2. Extract frequency weighting to `frequency_weighting.py`
3. Extract window operations to `window_operations.py`
4. Create `BaseSpectrumAnalyzer` with shared logic
5. Create `SequentialSpectrumAnalyzer` (thin wrapper)
6. Create `ParallelSpectrumAnalyzer` (thin wrapper)
7. Update existing references
8. Update all imports
9. Run tests, verify zero regressions

**Deliverables**:
- `spectrum_analysis/` module (complete)
- `REFACTORING_PHASE_7_3_SUMMARY.md`
- All tests passing
- 150+ lines eliminated

### Phase 7.4: Root Level Reorganization (20-30 hours)
**Priority**: MEDIUM (organization only)

1. Create subdirectories: loudness_analysis/, stereo_analysis/, dynamics_analysis/
2. Move and update imports for loudness_meter.py
3. Move and update imports for phase_correlation.py
4. Move and update imports for dynamic_range.py
5. Consolidate batch_analyzer.py logic
6. Create comprehensive root-level __init__.py
7. Update all references across codebase
8. Run full test suite
9. Verify zero regressions

**Deliverables**:
- Reorganized analysis/ module (complete)
- `REFACTORING_PHASE_7_4_SUMMARY.md`
- All tests passing

---

## Benefits Summary

### Code Quality
- ✅ **Eliminate 2,000+ lines of duplicate code**
- ✅ **Create 8-10 focused utility modules**
- ✅ **Establish consistent patterns across analysis/**
- ✅ **Improve testability through smaller modules**
- ✅ **Enable code reuse across analysis domains**

### Maintainability
- ✅ **Single source of truth for each calculation**
- ✅ **Consistent interfaces across modules**
- ✅ **Clear domain organization**
- ✅ **Easier onboarding for new developers**

### Performance
- ✅ **Reduced code path complexity**
- ✅ **Optimized calculations in utilities**
- ✅ **Potential for parallel processing (spectrum_analysis)**

### Testing
- ✅ **Easier unit testing of focused utilities**
- ✅ **Better test isolation**
- ✅ **Comprehensive coverage of utility classes**

---

## Estimated Timeline

| Phase | Scope | Hours | Status |
|-------|-------|-------|--------|
| 7.1 | Quality Assessment | 40-50 | Planned |
| 7.2 | Feature Extraction | 50-60 | Planned |
| 7.3 | Spectrum Analysis | 30-40 | Planned |
| 7.4 | Root Reorganization | 20-30 | Planned |
| **Total** | **Complete Analysis Refactoring** | **140-180** | **Ready to Start** |

---

## Success Criteria

- [ ] All 51+ tests passing (no regressions)
- [ ] 2,000+ lines of duplicate code eliminated
- [ ] 8-10 new utility modules created
- [ ] 100% backward compatible (all imports work)
- [ ] Phase documentation complete (4 summaries)
- [ ] Code organized into logical domains
- [ ] Consistent patterns matching fingerprint module

---

## Next Steps

1. **Review & Approval**: Validate this plan with team
2. **Phase 7.1 Start**: Begin quality assessment refactoring
3. **Dependency Management**: Track imports between phases
4. **Testing Strategy**: Ensure zero regressions throughout
5. **Documentation**: Create summary after each phase

---

## Related Documentation

- [Phase 1-6 Summary](REFACTORING_PHASE_1_2_SUMMARY.md) - Fingerprint baseline
- [Release Notes 1.1.0-beta.5](docs/RELEASE_1_1_0_FINGERPRINT_REFACTORING.md) - Current state
- [CHANGELOG.md](CHANGELOG.md) - Version history

---

**Prepared by**: Claude Code
**Date**: 2025-11-30
**Status**: Planning Phase - Ready for Implementation

This plan extends the proven fingerprint refactoring patterns to the entire auralis/analysis directory, consolidating 2,000+ lines and establishing consistent, maintainable code organization across all audio analysis modules.
