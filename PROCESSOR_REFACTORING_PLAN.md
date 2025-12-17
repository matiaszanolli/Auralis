# Backend Processor Refactoring Plan
**Date**: 2025-12-16
**Goal**: Eliminate duplicate logic across 6 processor files while preserving best implementation patterns
**Principle**: DRY (Don't Repeat Yourself) - Extract to utilities, refactor modules to thin wrappers

---

## 📊 Current State Analysis

### Files Analyzed
1. `auralis-web/backend/chunked_processor.py` (1,300 lines)
2. `auralis-web/backend/routers/webm_streaming.py` (431 lines)
3. `auralis-web/backend/core/processor_manager.py` (182 lines)
4. `auralis/optimization/parallel_processor.py` (468 lines)
5. `auralis/core/hybrid_processor.py` (509 lines)
6. `auralis/core/processing/realtime_processor.py` (124 lines)

**Total**: ~3,014 lines
**Estimated Duplication**: 30-40% (~900-1,200 lines)

---

## 🔍 Identified Duplications

### 1. **Audio Processing Orchestration** (CRITICAL - 400+ lines duplicate)

**Locations**:
- `chunked_processor.py:_process_chunk_core()` (lines 616-693)
- `chunked_processor.py:_process_chunk_with_hybrid_processor()` (lines 556-614)
- `hybrid_processor.py:process()` (lines 164-227)
- `hybrid_processor.py:_process_adaptive_mode()` (lines 244-283)
- `realtime_processor.py:process_chunk()` (lines 40-71)

**Duplicate Logic**:
```python
# Repeated in 5 places with variations:
- Audio validation (empty, silence, mono->stereo, min samples)
- Processor initialization/selection
- Target/fingerprint application
- Processing delegation
- Post-processing (limiter, level smoothing)
- Error handling
```

**Best Practices Found**:
- ✅ `hybrid_processor.py`: Comprehensive validation (empty, silence, min samples, NaN check)
- ✅ `chunked_processor.py`: Fingerprint caching (database → .25d → extract)
- ✅ `chunked_processor.py`: Thread-safe processor locking (`_processor_lock`)

---

### 2. **Processor Instance Management** (MODERATE - 150+ lines duplicate)

**Locations**:
- `processor_manager.py:ProcessorManager` (full file - 182 lines)
- `hybrid_processor.py:_processor_cache` (lines 438-464)
- `chunked_processor.py` uses ProcessorManager but also has own caching

**Duplicate Logic**:
```python
# Two different caching mechanisms:
1. ProcessorManager: (track_id, preset, intensity) → HybridProcessor
2. _processor_cache: f"{id(config)}_{mode}" → HybridProcessor
```

**Best Practices Found**:
- ✅ `processor_manager.py`: Explicit lifecycle management (get_or_create, release, cleanup)
- ✅ `processor_manager.py`: Statistics/monitoring (`get_statistics()`)
- ❌ `hybrid_processor.py`: Module-level cache lacks cleanup methods

**Problem**: Two separate caching strategies for same purpose

---

### 3. **Chunk Extraction & Boundary Management** (CRITICAL - 300+ lines duplicate)

**Locations**:
- `chunked_processor.py:load_chunk()` (lines 381-446)
- `chunked_processor.py:_extract_chunk_segment()` (lines 1095-1162)
- `webm_streaming.py:_get_original_wav_chunk()` (lines 362-428)
- Uses `ChunkBoundaryManager` but still has duplication

**Duplicate Logic**:
```python
# Repeated chunk extraction pattern:
1. Calculate boundaries (start_sample, end_sample)
2. Load audio segment (soundfile vs. load_audio fallback)
3. Handle overlap for crossfade
4. Validate chunk not empty
5. Pad/trim edge cases
```

**Best Practices Found**:
- ✅ `chunked_processor.py`: Delegates boundary calc to `ChunkBoundaryManager`
- ✅ `chunked_processor.py`: Soundfile with fallback to load_audio
- ❌ `webm_streaming.py`: Reimplements chunk extraction from scratch

---

### 4. **Fingerprint & Target Management** (SIGNIFICANT - 200+ lines duplicate)

**Locations**:
- `chunked_processor.py:_load_fingerprint_from_database()` (lines 239-298)
- `chunked_processor.py:_generate_targets_from_fingerprint()` (lines 953-996)
- `chunked_processor.py` fingerprint extraction in `process_chunk()` (lines 724-772)
- `hybrid_processor.py:set_fixed_mastering_targets()` (lines 133-162)

**Duplicate Logic**:
```python
# Fingerprint loading hierarchy:
1. Try database first (LibraryManager)
2. Fall back to .25d file (FingerprintStorage)
3. Extract from audio if missing
4. Generate mastering targets from fingerprint
5. Cache for reuse
```

**Best Practices Found**:
- ✅ `chunked_processor.py`: 3-tier fallback (DB → .25d → extract)
- ✅ `chunked_processor.py`: Saves extracted fingerprint to .25d file
- ❌ No centralized FingerprintService - logic scattered

---

### 5. **Content Analysis** (SIGNIFICANT - 150+ lines duplicate)

**Locations**:
- `hybrid_processor.py`: Uses `ContentAnalyzer`, `AdaptiveTargetGenerator`, `SpectrumMapper`
- `chunked_processor.py`: Uses `AdaptiveMasteringEngine` with same analyzers
- `realtime_processor.py:_quick_content_analysis()` (lines 73-123)

**Duplicate Logic**:
```python
# Two levels of analysis:
1. Full analysis: ContentAnalyzer (frequency, dynamics, genre, spectrum)
2. Quick analysis: Basic RMS, peak, spectral centroid
```

**Best Practices Found**:
- ✅ `realtime_processor.py`: Fast path for streaming (simplified analysis)
- ✅ `hybrid_processor.py`: Comprehensive analyzer initialization
- ❌ No facade to route between full/quick analysis based on context

---

### 6. **Parallel Processing** (ISOLATED - 468 lines)

**Location**: `auralis/optimization/parallel_processor.py` (entire file)

**Observations**:
- Self-contained, no direct duplication
- **Unused**: Not imported by any of the other 5 files
- Provides: ParallelFFTProcessor, ParallelBandProcessor, ParallelFeatureExtractor
- **Potential**: Could optimize chunked_processor batch operations

**Recommendation**: Keep as-is (utility module), consider integration in Phase 6 optimization

---

## 🎯 Refactoring Strategy

### Phase 1: Audio Processing Pipeline Unification
**Goal**: Eliminate 400+ lines of duplicate processing orchestration

**Create**: `auralis-web/backend/core/audio_processing_pipeline.py`

```python
class AudioProcessingPipeline:
    """
    Unified audio processing pipeline consolidating best practices
    from chunked_processor, hybrid_processor, and realtime_processor.
    """

    @staticmethod
    def validate_audio(audio: np.ndarray) -> np.ndarray:
        """
        Validate and normalize audio (mono→stereo, silence check, min samples).
        Consolidates validation from hybrid_processor.process().
        """
        pass

    @staticmethod
    def select_processor(
        preset: Optional[str],
        intensity: float,
        processor_manager: ProcessorManager,
        **context
    ) -> Optional[HybridProcessor]:
        """
        Select appropriate processor based on preset/intensity.
        Consolidates processor selection logic.
        """
        pass

    @staticmethod
    def apply_enhancement(
        audio: np.ndarray,
        processor: Optional[HybridProcessor],
        targets: Optional[Dict[str, Any]],
        **kwargs
    ) -> np.ndarray:
        """
        Apply enhancement with processor.
        Consolidates processing delegation logic.
        """
        pass

    @classmethod
    def process_audio(
        cls,
        audio: np.ndarray,
        preset: Optional[str] = None,
        intensity: float = 1.0,
        targets: Optional[Dict[str, Any]] = None,
        processor_manager: Optional[ProcessorManager] = None,
        **kwargs
    ) -> np.ndarray:
        """
        Main unified processing entry point.
        Replaces _process_chunk_core(), process(), process_chunk().
        """
        # 1. Validate
        audio = cls.validate_audio(audio)

        # 2. Select processor
        processor = cls.select_processor(preset, intensity, processor_manager, **kwargs)

        # 3. Apply enhancement
        processed = cls.apply_enhancement(audio, processor, targets, **kwargs)

        # 4. Return
        return processed
```

**Refactor Impact**:
- ✅ `chunked_processor._process_chunk_core()` → calls `AudioProcessingPipeline.process_audio()`
- ✅ `hybrid_processor.process()` → calls `AudioProcessingPipeline.process_audio()`
- ✅ `realtime_processor.process_chunk()` → calls `AudioProcessingPipeline.process_audio()`
- **Lines Saved**: ~400 lines

---

### Phase 2: Processor Factory & Registry
**Goal**: Consolidate processor caching into single unified system

**Create**: `auralis-web/backend/core/processor_factory.py`

```python
class ProcessorFactory:
    """
    Unified processor factory consolidating ProcessorManager and
    hybrid_processor's _processor_cache.
    """

    def __init__(self):
        # Unified cache: (track_id, preset, intensity, config_hash) → HybridProcessor
        self._processor_cache: Dict[Tuple, HybridProcessor] = {}
        self._active_processors: Dict[int, HybridProcessor] = {}
        self._lock = threading.RLock()

    def get_or_create(
        self,
        track_id: Optional[int] = None,
        preset: str = "adaptive",
        intensity: float = 1.0,
        config: Optional[UnifiedConfig] = None,
        mastering_targets: Optional[Dict[str, Any]] = None
    ) -> HybridProcessor:
        """
        Get cached processor or create new one.
        Merges logic from ProcessorManager and _get_or_create_processor().
        """
        pass

    def release(self, track_id: int) -> None:
        """Release processor for track (from ProcessorManager)."""
        pass

    def cleanup_track(self, track_id: int) -> None:
        """Cleanup all processors for track (from ProcessorManager)."""
        pass

    def clear_cache(self) -> None:
        """Clear all cached processors."""
        pass

    def get_statistics(self) -> Dict[str, Any]:
        """Get cache statistics."""
        pass
```

**Refactor Impact**:
- ❌ **Deprecate**: `processor_manager.py:ProcessorManager`
- ❌ **Remove**: `hybrid_processor.py:_processor_cache` and `_get_or_create_processor()`
- ✅ **Update**: All files use `ProcessorFactory` instead
- **Lines Saved**: ~150 lines

---

### Phase 3: Chunk Operations Utility
**Goal**: Consolidate chunk extraction into single utility

**Create**: `auralis-web/backend/core/chunk_operations.py`

```python
class ChunkOperations:
    """
    Unified chunk extraction and boundary operations.
    Consolidates load_chunk(), _extract_chunk_segment(), _get_original_wav_chunk().
    """

    def __init__(
        self,
        boundary_manager: ChunkBoundaryManager,
        chunk_duration: int = 15,
        chunk_interval: int = 10,
        overlap_duration: int = 5
    ):
        self.boundary_manager = boundary_manager
        self.chunk_duration = chunk_duration
        self.chunk_interval = chunk_interval
        self.overlap_duration = overlap_duration

    def load_chunk_from_file(
        self,
        filepath: str,
        chunk_index: int,
        sample_rate: int,
        with_context: bool = True
    ) -> Tuple[np.ndarray, float, float]:
        """
        Load chunk from audio file with optional context.
        Consolidates chunked_processor.load_chunk() and
        webm_streaming._get_original_wav_chunk().
        """
        pass

    def extract_segment(
        self,
        processed_chunk: np.ndarray,
        chunk_index: int,
        total_chunks: int,
        total_duration: float,
        sample_rate: int
    ) -> np.ndarray:
        """
        Extract correct segment from processed chunk.
        Consolidates _extract_chunk_segment() logic.
        """
        pass

    @staticmethod
    def apply_crossfade(
        chunk1: np.ndarray,
        chunk2: np.ndarray,
        overlap_samples: int
    ) -> np.ndarray:
        """
        Apply crossfade between chunks.
        Moved from chunked_processor.apply_crossfade_between_chunks().
        """
        pass
```

**Refactor Impact**:
- ✅ `chunked_processor.load_chunk()` → calls `ChunkOperations.load_chunk_from_file()`
- ✅ `chunked_processor._extract_chunk_segment()` → calls `ChunkOperations.extract_segment()`
- ✅ `webm_streaming._get_original_wav_chunk()` → calls `ChunkOperations.load_chunk_from_file()`
- ✅ Move `apply_crossfade_between_chunks()` to `ChunkOperations.apply_crossfade()`
- **Lines Saved**: ~300 lines

---

### Phase 4: Mastering Target Service
**Goal**: Centralize fingerprint and target management

**Create**: `auralis-web/backend/core/mastering_target_service.py`

```python
class MasteringTargetService:
    """
    Centralized fingerprint loading and mastering target generation.
    Consolidates fingerprint/target logic from chunked_processor.
    """

    def __init__(self, cache: Optional[Dict[str, Any]] = None):
        self.cache = cache or {}
        self._lock = threading.RLock()

    def load_fingerprint(
        self,
        track_id: int,
        filepath: str,
        extract_if_missing: bool = True
    ) -> Optional[MasteringFingerprint]:
        """
        Load fingerprint using 3-tier hierarchy:
        1. Database (fastest)
        2. .25d file
        3. Extract from audio (if extract_if_missing=True)

        Consolidates _load_fingerprint_from_database() and
        fingerprint extraction from process_chunk().
        """
        pass

    def generate_targets(
        self,
        fingerprint: MasteringFingerprint
    ) -> Dict[str, Any]:
        """
        Generate mastering targets from fingerprint.
        Consolidates _generate_targets_from_fingerprint().
        """
        pass

    def get_or_extract_targets(
        self,
        track_id: int,
        filepath: str,
        preset: str
    ) -> Tuple[Optional[MasteringFingerprint], Optional[Dict[str, Any]]]:
        """
        One-stop method for getting fingerprint + targets.
        """
        fingerprint = self.load_fingerprint(track_id, filepath)
        if fingerprint:
            targets = self.generate_targets(fingerprint)
            return fingerprint, targets
        return None, None
```

**Refactor Impact**:
- ✅ `chunked_processor._load_fingerprint_from_database()` → `MasteringTargetService.load_fingerprint()`
- ✅ `chunked_processor._generate_targets_from_fingerprint()` → `MasteringTargetService.generate_targets()`
- ✅ Fingerprint extraction in `process_chunk()` → `MasteringTargetService.load_fingerprint()`
- **Lines Saved**: ~200 lines

---

### Phase 5: Content Analysis Facade
**Goal**: Unified interface for full vs. quick analysis

**Create**: `auralis/core/analysis/content_analysis_facade.py`

```python
class ContentAnalysisFacade:
    """
    Unified content analysis facade providing both full and quick analysis.
    Consolidates ContentAnalyzer initialization and realtime quick analysis.
    """

    def __init__(self, sample_rate: int, config: Optional[UnifiedConfig] = None):
        self.sample_rate = sample_rate
        self.config = config or UnifiedConfig()

        # Initialize full analyzers (lazy)
        self._content_analyzer: Optional[ContentAnalyzer] = None
        self._target_generator: Optional[AdaptiveTargetGenerator] = None
        self._spectrum_mapper: Optional[SpectrumMapper] = None

    def analyze_full(
        self,
        audio: np.ndarray,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Full content analysis with all features.
        Used by hybrid_processor and adaptive_mode.
        """
        if self._content_analyzer is None:
            self._content_analyzer = ContentAnalyzer(self.sample_rate)
        return self._content_analyzer.analyze_content(audio, **kwargs)

    def analyze_quick(
        self,
        audio: np.ndarray
    ) -> Dict[str, Any]:
        """
        Quick analysis for real-time streaming.
        Consolidates realtime_processor._quick_content_analysis().
        """
        # Basic RMS, peak, spectral centroid (minimal computation)
        pass

    def analyze_adaptive(
        self,
        audio: np.ndarray,
        realtime: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Adaptive analysis: quick if realtime=True, full otherwise.
        """
        if realtime:
            return self.analyze_quick(audio)
        else:
            return self.analyze_full(audio, **kwargs)
```

**Refactor Impact**:
- ✅ `hybrid_processor` uses `ContentAnalysisFacade.analyze_full()`
- ✅ `realtime_processor._quick_content_analysis()` → `ContentAnalysisFacade.analyze_quick()`
- ✅ Single initialization point for all analyzers
- **Lines Saved**: ~150 lines

---

## 📐 Architecture After Refactoring

### New Module Structure
```
auralis-web/backend/core/
├── audio_processing_pipeline.py    # NEW - Phase 1 (unified processing)
├── processor_factory.py             # NEW - Phase 2 (replaces processor_manager)
├── chunk_operations.py              # NEW - Phase 3 (chunk utilities)
├── mastering_target_service.py      # NEW - Phase 4 (fingerprint/targets)
├── chunk_boundaries.py              # EXISTING - keep as-is
├── level_manager.py                 # EXISTING - keep as-is
├── encoding.py                      # EXISTING - keep as-is

auralis/core/analysis/
├── content_analysis_facade.py       # NEW - Phase 5 (unified analysis)
├── content_analyzer.py              # EXISTING - refactor to facade
├── adaptive_target_generator.py     # EXISTING - refactor to facade
├── spectrum_mapper.py               # EXISTING - refactor to facade

# Refactored Files (become thin wrappers):
auralis-web/backend/chunked_processor.py      # 1,300 → ~700 lines (46% reduction)
auralis-web/backend/routers/webm_streaming.py # 431 → ~300 lines (30% reduction)
auralis/core/hybrid_processor.py              # 509 → ~350 lines (31% reduction)
auralis/core/processing/realtime_processor.py # 124 → ~80 lines (35% reduction)

# Deprecated:
auralis-web/backend/core/processor_manager.py # REMOVE - replaced by processor_factory
```

### Dependency Flow After Refactoring
```
┌─────────────────────────────────────────────────────────────────┐
│                   Application Layer                              │
│  chunked_processor.py, webm_streaming.py, hybrid_processor.py   │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Core Services Layer                         │
│  ┌──────────────────────┐  ┌──────────────────────┐             │
│  │ AudioProcessing      │  │ ProcessorFactory     │             │
│  │ Pipeline             │  │                      │             │
│  └──────────────────────┘  └──────────────────────┘             │
│  ┌──────────────────────┐  ┌──────────────────────┐             │
│  │ ChunkOperations      │  │ MasteringTarget      │             │
│  │                      │  │ Service              │             │
│  └──────────────────────┘  └──────────────────────┘             │
│  ┌──────────────────────┐                                       │
│  │ ContentAnalysis      │                                       │
│  │ Facade               │                                       │
│  └──────────────────────┘                                       │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Existing Utility Layer                        │
│  ChunkBoundaryManager, LevelManager, WAVEncoder, HybridProcessor│
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Expected Impact

### Code Reduction
| File | Before | After | Reduction |
|------|--------|-------|-----------|
| chunked_processor.py | 1,300 | ~700 | 46% (600 lines) |
| webm_streaming.py | 431 | ~300 | 30% (131 lines) |
| processor_manager.py | 182 | 0 | 100% (removed) |
| hybrid_processor.py | 509 | ~350 | 31% (159 lines) |
| realtime_processor.py | 124 | ~80 | 35% (44 lines) |
| **Total** | **2,546** | **1,430** | **44% (1,116 lines)** |

### New Utility Modules (added)
| Module | Lines | Purpose |
|--------|-------|---------|
| audio_processing_pipeline.py | ~150 | Unified processing |
| processor_factory.py | ~120 | Processor caching |
| chunk_operations.py | ~180 | Chunk utilities |
| mastering_target_service.py | ~150 | Fingerprint/targets |
| content_analysis_facade.py | ~100 | Analysis routing |
| **Total Added** | **~700** | **New utilities** |

### Net Impact
- **Before**: 2,546 lines (application code)
- **After**: 1,430 lines (thin wrappers) + 700 lines (utilities) = 2,130 lines
- **Net Reduction**: 416 lines (16% overall)
- **Maintainability**: ⬆️⬆️⬆️ (utilities = single source of truth)
- **Testability**: ⬆️⬆️⬆️ (utilities can be unit tested in isolation)

---

## 🚀 Implementation Plan

### Phase 1: Audio Processing Pipeline (Week 1)
- [ ] Create `audio_processing_pipeline.py`
- [ ] Implement `validate_audio()`, `select_processor()`, `apply_enhancement()`
- [ ] Refactor `chunked_processor._process_chunk_core()` to use pipeline
- [ ] Unit tests for AudioProcessingPipeline
- [ ] Verify chunked_processor works with new pipeline

### Phase 2: Processor Factory (Week 1)
- [ ] Create `processor_factory.py`
- [ ] Merge logic from ProcessorManager and _processor_cache
- [ ] Update all files to use ProcessorFactory
- [ ] Remove processor_manager.py
- [ ] Update hybrid_processor to remove _processor_cache
- [ ] Unit tests for ProcessorFactory

### Phase 3: Chunk Operations (Week 2)
- [ ] Create `chunk_operations.py`
- [ ] Implement `load_chunk_from_file()`, `extract_segment()`, `apply_crossfade()`
- [ ] Refactor chunked_processor to use ChunkOperations
- [ ] Refactor webm_streaming to use ChunkOperations
- [ ] Unit tests for ChunkOperations
- [ ] Integration tests for chunked processing

### Phase 4: Mastering Target Service (Week 2)
- [ ] Create `mastering_target_service.py`
- [ ] Implement 3-tier fingerprint loading
- [ ] Implement target generation
- [ ] Refactor chunked_processor fingerprint logic
- [ ] Unit tests for MasteringTargetService
- [ ] Integration tests with database

### Phase 5: Content Analysis Facade (Week 3)
- [ ] Create `content_analysis_facade.py`
- [ ] Implement full analysis routing
- [ ] Implement quick analysis (from realtime_processor)
- [ ] Refactor hybrid_processor to use facade
- [ ] Refactor realtime_processor to use facade
- [ ] Unit tests for ContentAnalysisFacade

### Phase 6: Cleanup & Documentation (Week 3)
- [ ] Remove deprecated code
- [ ] Update CLAUDE.md with new architecture
- [ ] Add architecture diagram to docs
- [ ] Create migration guide for future developers
- [ ] Run full test suite (850+ tests)
- [ ] Performance regression testing

---

## ⚠️ Risks & Mitigation

### Risk 1: Breaking Existing Functionality
**Mitigation**:
- Implement phases incrementally with feature flags
- Run full test suite after each phase
- Keep old code commented out until new code proven
- Use git branches for each phase

### Risk 2: Performance Regression
**Mitigation**:
- Benchmark before/after each phase
- Monitor processing time per chunk (target: < 500ms)
- Profile memory usage (target: no increase)
- Use caching aggressively in utilities

### Risk 3: Integration Issues
**Mitigation**:
- Update all import statements in one commit per phase
- Use IDE refactoring tools for import updates
- Grep for old function/class names to find missed references
- Integration tests cover cross-module boundaries

---

## ✅ Success Criteria

1. **Code Reduction**: At least 40% reduction in duplicate logic (✅ 44% projected)
2. **Test Coverage**: All 850+ tests pass with new architecture
3. **Performance**: No regression in chunk processing time
4. **Maintainability**: Single source of truth for each logical component
5. **Documentation**: Updated CLAUDE.md with new patterns

---

## 📚 References

- [CLAUDE.md - Utilities Pattern](CLAUDE.md#utilities-pattern-phase-72---code-deduplication)
- [Phase 7.2 Consolidation](CLAUDE.md#completed-phases) - Eliminated 900 lines via SpectrumOperations
- [DRY Principle](CLAUDE.md#core-principles)
