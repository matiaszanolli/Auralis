# ChunkedAudioProcessor Refactoring Plan

## Problem Statement
- **Current size**: 1142 lines (3.8x the 300-line guideline)
- **Issues**: God object, code duplication, mixed responsibilities, dead code
- **Impact**: Hard to test, maintain, extend
- **Tests affected**: 2433 lines across 4 test files that must continue passing

## Refactoring Goals
1. **Reduce main class** to < 300 lines
2. **Eliminate 53-line duplication** between `process_chunk()` and `get_wav_chunk_path()`
3. **Extract utilities** into focused, single-responsibility modules
4. **Remove dead code** (WebM encoder, no-op functions)
5. **Maintain 100% backward compatibility** for all public APIs
6. **All tests must pass** without modification

## Public API to Maintain
```python
from chunked_processor import (
    ChunkedAudioProcessor,        # Main class
    CHUNK_DURATION,               # Constant = 15
    OVERLAP_DURATION,             # Constant = 5
    CONTEXT_DURATION,             # Constant = 5
    apply_crossfade_between_chunks # Function (module-level)
)
```

---

## Phase 1: Remove Dead Code (Days 1-2)
**Effort: 2 days | Payoff: Clear codebase**

### Task 1.1: Remove unused WebM encoder
- **File**: `auralis-web/backend/chunked_processor.py`
- **Lines to remove**: 1053-1077 (`_convert_to_webm_opus()` method)
- **Impact**: -25 lines, clear deprecated comment
- **Test impact**: NONE (no tests call this method)
- **Verification**: Search for `_convert_to_webm_opus` - should have 0 results

### Task 1.2: Remove no-op apply_crossfade()
- **File**: `auralis-web/backend/chunked_processor.py`
- **Lines to remove**: 432-454 (method that just returns chunk unchanged)
- **Impact**: -22 lines, clarity
- **Test impact**: LOW (1 test may mock it, verify in test_chunked_processor.py)
- **Keep**: `apply_crossfade_between_chunks()` at module level (different function, used by tests)

### Task 1.3: Remove deprecated comments
- **Remove**: Lines 40-49 (comments about "Beta 12.1", WebM/Opus mentions)
- **Impact**: -10 lines, freshness
- **Test impact**: NONE

**New file size after Phase 1: ~1085 lines** (-57 lines)

---

## Phase 2: Extract Core Duplication (Days 3-5)
**Effort: 3 days | Payoff: 53 lines eliminated, single code path**

### Root Cause
Lines 934-977 in `get_wav_chunk_path()` are identical to lines 525-585 in `process_chunk()`:
- Load chunk with context
- Disable fingerprint (fast-start optimization)
- Apply intensity blending
- Trim context
- Apply level smoothing

### Solution: Create `_process_chunk_core()` method
```python
def _process_chunk_core(self, chunk_index: int) -> np.ndarray:
    """
    Core chunk processing (shared by process_chunk and get_wav_chunk_path).

    Returns:
        np.ndarray: Processed audio chunk (with context trimmed)
    """
    # Load chunk with context
    audio_chunk_with_context, _, _ = self.load_chunk(
        chunk_index,
        with_context=True
    )

    # Fast-start optimization: disable fingerprint for speed
    original_setting = self.processor.content_analyzer.use_fingerprint_analysis
    try:
        self.processor.content_analyzer.use_fingerprint_analysis = False
        processed_chunk = self.processor.process(audio_chunk_with_context)
    finally:
        self.processor.content_analyzer.use_fingerprint_analysis = original_setting

    # Trim context
    processed_chunk = self._trim_context(processed_chunk, chunk_index)

    # Apply intensity blending if needed
    if self.intensity < 1.0:
        original_chunk, _, _ = self.load_chunk(chunk_index, with_context=False)
        min_len = min(len(original_chunk), len(processed_chunk))
        processed_chunk = (
            original_chunk[:min_len] * (1.0 - self.intensity) +
            processed_chunk[:min_len] * self.intensity
        )

    # Smooth level transition
    processed_chunk = self._smooth_level_transition(processed_chunk, chunk_index)

    return processed_chunk
```

### Refactor `process_chunk()`
```python
def process_chunk(self, chunk_index: int) -> str:
    """Process and save chunk to WAV file (cached)."""
    processed_chunk = self._process_chunk_core(chunk_index)

    # Save to cache
    chunk_path = self.chunk_dir / f"chunk_{chunk_index}_{self.file_signature}.wav"
    from encoding.wav_encoder import encode_to_wav
    wav_bytes = encode_to_wav(processed_chunk, self.sample_rate)
    chunk_path.write_bytes(wav_bytes)

    self.chunk_cache[self._get_cache_key(chunk_index)] = str(chunk_path)
    return str(chunk_path)
```

### Refactor `get_wav_chunk_path()`
```python
def get_wav_chunk_path(self, chunk_index: int) -> str:
    """Process and extract chunk segment to WAV bytes."""
    processed_chunk = self._process_chunk_core(chunk_index)

    # Extract appropriate segment based on position
    extracted = self._extract_chunk_segment(processed_chunk, chunk_index)

    # Encode and return as WAV
    from encoding.wav_encoder import encode_to_wav
    wav_bytes = encode_to_wav(extracted, self.sample_rate)

    # Save to temp WAV file for serving
    wav_path = Path(tempfile.gettempdir()) / f"chunk_{chunk_index}_{self.file_signature}.wav"
    wav_path.write_bytes(wav_bytes)

    return str(wav_path)
```

### Extract `_extract_chunk_segment()` (new helper)
```python
def _extract_chunk_segment(self, processed_chunk: np.ndarray, chunk_index: int) -> np.ndarray:
    """Extract appropriate segment from processed chunk based on position."""
    overlap_samples = int(OVERLAP_DURATION * self.sample_rate)
    expected_samples = int(CHUNK_INTERVAL * self.sample_rate)
    is_last_chunk = chunk_index >= (self.total_chunks - 1)

    if chunk_index == 0:
        # First chunk: use full duration without trimming overlap
        return processed_chunk[:int(CHUNK_DURATION * self.sample_rate)]
    elif is_last_chunk:
        # Last chunk: might be shorter
        return processed_chunk[overlap_samples:overlap_samples + expected_samples]
    else:
        # Middle chunks: skip overlap, take interval duration
        return processed_chunk[overlap_samples:overlap_samples + expected_samples]
```

**New file size after Phase 2: ~1015 lines** (-70 lines cumulative)

---

## Phase 3: Extract Utilities to Modules (Days 6-12)
**Effort: 7 days | Payoff: Modular structure, reusable code, <300 line main class**

### 3.1 Create `chunking/__init__.py`
**Purpose**: Package for chunking utilities

```python
# Re-export public API
from chunked_processor import (
    ChunkedAudioProcessor,
    CHUNK_DURATION,
    CHUNK_INTERVAL,
    OVERLAP_DURATION,
    CONTEXT_DURATION,
    apply_crossfade_between_chunks
)

__all__ = [
    'ChunkedAudioProcessor',
    'CHUNK_DURATION',
    'CHUNK_INTERVAL',
    'OVERLAP_DURATION',
    'CONTEXT_DURATION',
    'apply_crossfade_between_chunks',
]
```

### 3.2 Create `chunking/audio_metadata.py` (120 lines)
**Purpose**: Handle audio file metadata, loading, caching

**Extract from ChunkedAudioProcessor:**
- `_generate_file_signature()` → `AudioMetadataLoader.generate_file_signature()`
- `_load_metadata()` → `AudioMetadataLoader.load_metadata()`
- `_get_cache_key()` → `AudioMetadataLoader.get_cache_key()`
- `_get_chunk_path()` → `AudioMetadataLoader.get_chunk_path()`
- `_get_wav_chunk_path()` → (consolidate, no longer needed)

**Class design:**
```python
class AudioMetadataLoader:
    def __init__(self, filepath: str, sample_rate_override: Optional[int] = None):
        self.filepath = Path(filepath)
        self._metadata = None
        self._signature = None

    def load_metadata(self) -> Tuple[int, float, int]:
        """Load audio metadata (sample_rate, duration, channels)"""
        # Actual implementation with try/except

    def generate_file_signature(self) -> str:
        """Generate MD5 signature of first 10 seconds"""
        # Actual implementation

    def get_cache_key(self, chunk_index: int, suffix: str = '') -> str:
        """Generate cache key for chunk"""

    def get_chunk_path(self, track_id: int, chunk_index: int,
                      preset: str, intensity: float) -> Path:
        """Generate path for cached chunk"""
```

**Test compatibility:**
- Still import from `chunked_processor` in tests ✓
- All paths managed by main class ✓

### 3.3 Create `chunking/audio_processing.py` (160 lines)
**Purpose**: Audio signal processing utilities

**Extract from ChunkedAudioProcessor:**
- `_calculate_rms()` → `AudioProcessing.calculate_rms()`
- `_smooth_level_transition()` → `AudioProcessing.smooth_level_transitions()`
- `_trim_context()` → `AudioProcessing.trim_context()`
- `_calculate_eq_adjustment()` → `AudioProcessing.calculate_eq_adjustment()`
- `_apply_intensity_blending()` → `AudioProcessing.apply_intensity_blending()` (extract from inline)

**Class design:**
```python
class AudioProcessing:
    @staticmethod
    def calculate_rms(audio: np.ndarray) -> float:
        """Calculate RMS level"""

    @staticmethod
    def trim_context(audio: np.ndarray, chunk_index: int,
                    total_chunks: int) -> np.ndarray:
        """Trim context from chunk based on position"""

    @staticmethod
    def apply_intensity_blending(original: np.ndarray,
                                processed: np.ndarray,
                                intensity: float) -> np.ndarray:
        """Blend original and processed audio by intensity"""

    @staticmethod
    def smooth_level_transition(chunk_history: Dict, current_chunk: np.ndarray,
                               chunk_index: int, sample_rate: int) -> np.ndarray:
        """Apply level smoothing between chunks"""

    @staticmethod
    def calculate_eq_adjustment(spectrum: np.ndarray,
                               reference_spectrum: np.ndarray) -> np.ndarray:
        """Calculate EQ adjustment from spectral comparison"""
```

### 3.4 Create `chunking/fingerprint.py` (130 lines)
**Purpose**: Mastering fingerprint and recommendation caching

**Extract from ChunkedAudioProcessor:**
- `_get_track_fingerprint_cache_key()` → `FingerprintManager.get_cache_key()`
- `get_cached_fingerprint()` → `FingerprintManager.get_cached()`
- `cache_fingerprint()` → `FingerprintManager.cache()`
- `_generate_targets_from_fingerprint()` → `FingerprintManager.generate_targets()`
- Fingerprint initialization logic

**Class design:**
```python
class FingerprintManager:
    def __init__(self, preset: Optional[str] = None):
        self.preset = preset
        self.cached_fingerprint = None
        self.cached_targets = None
        self.cached_recommendation = None

    def get_cached(self, filepath: str) -> Optional[MasteringFingerprint]:
        """Load cached fingerprint from disk"""

    def cache(self, fingerprint: MasteringFingerprint, filepath: str) -> None:
        """Save fingerprint to cache"""

    def generate_targets(self, fingerprint: MasteringFingerprint) -> Dict:
        """Generate mastering targets from fingerprint"""

    def get_recommendation(self, fingerprint: MasteringFingerprint,
                          confidence_threshold: float = 0.4):
        """Get mastering recommendation (lazy-init adaptive engine)"""
```

### 3.5 Create `chunking/chunk_cache.py` (100 lines)
**Purpose**: In-memory chunk cache management

**Extract from ChunkedAudioProcessor:**
- `self.chunk_cache` dict → `ChunkCache` class
- Cache key generation consolidated

**Class design:**
```python
class ChunkCache:
    def __init__(self, max_size: int = 100):
        self._cache: Dict[str, str] = {}  # key -> filepath
        self._max_size = max_size

    def get(self, key: str) -> Optional[str]:
        """Get cached chunk filepath"""

    def put(self, key: str, filepath: str) -> None:
        """Cache chunk filepath (with LRU eviction)"""

    def exists(self, key: str) -> bool:
        """Check if chunk is cached"""

    def clear(self) -> None:
        """Clear all cached chunks"""

    @property
    def size(self) -> int:
        """Current cache size"""
```

### 3.6 Move `apply_crossfade_between_chunks()` to module level
- Already at module level (lines 1080-1127)
- No changes needed ✓
- Keep in `chunked_processor.py` for backward compatibility

**New file size after Phase 3:**
- `chunked_processor.py`: ~300-350 lines (main class simplified)
- Plus 5 new modules: 600+ lines total (but properly organized)
- **Result**: Goal achieved - main class < 300 lines ✓

---

## Phase 4: Simplify Constructor (Days 13-14)
**Effort: 2 days | Payoff: Constructor < 30 lines, easy to understand**

### Current constructor: 91 lines (lines 64-155)
### New constructor design:
```python
def __init__(self, track_id: int, filepath: str, preset: str = None,
             intensity: float = 1.0, chunk_cache: Dict = None):
    self.track_id = track_id
    self.filepath = Path(filepath)
    self.preset = preset or 'adaptive'
    self.intensity = intensity
    self.lock = asyncio.Lock()

    # Load metadata
    self.metadata = AudioMetadataLoader(str(self.filepath))
    self.sample_rate, self.total_duration, self.channels = self.metadata.load_metadata()
    self.file_signature = self.metadata.generate_file_signature()
    self.total_chunks = int(np.ceil(self.total_duration / CHUNK_INTERVAL))

    # Set up directories
    self.chunk_dir = Path(tempfile.gettempdir()) / f"auralis_chunks"
    self.chunk_dir.mkdir(exist_ok=True)

    # Initialize caches
    self.chunk_cache = ChunkCache() if chunk_cache is None else chunk_cache
    self.fingerprint_manager = FingerprintManager(preset)

    # Initialize processor (lazy)
    self.processor = None
```

**Result**: Constructor reduced from 91 to ~25 lines

---

## Phase 5: Update Imports and Exports (Days 15-16)
**Effort: 2 days | Payoff: Consistent API, backward compatibility**

### In `chunked_processor.py`:
```python
# Top of file - import utilities
from chunking.audio_metadata import AudioMetadataLoader
from chunking.audio_processing import AudioProcessing
from chunking.fingerprint import FingerprintManager
from chunking.chunk_cache import ChunkCache
from chunking.crossfade import apply_crossfade_between_chunks

# At bottom - maintain backward compatibility
__all__ = [
    'ChunkedAudioProcessor',
    'CHUNK_DURATION',
    'CHUNK_INTERVAL',
    'OVERLAP_DURATION',
    'CONTEXT_DURATION',
    'apply_crossfade_between_chunks',
]
```

### Update `chunking/__init__.py`:
```python
from chunking.audio_metadata import AudioMetadataLoader
from chunking.audio_processing import AudioProcessing
from chunking.fingerprint import FingerprintManager
from chunking.chunk_cache import ChunkCache
from chunked_processor import (
    ChunkedAudioProcessor,
    CHUNK_DURATION,
    CHUNK_INTERVAL,
    OVERLAP_DURATION,
    CONTEXT_DURATION,
    apply_crossfade_between_chunks,
)

__all__ = [
    'ChunkedAudioProcessor',
    'AudioMetadataLoader',
    'AudioProcessing',
    'FingerprintManager',
    'ChunkCache',
    'CHUNK_DURATION',
    'CHUNK_INTERVAL',
    'OVERLAP_DURATION',
    'CONTEXT_DURATION',
    'apply_crossfade_between_chunks',
]
```

---

## Testing Strategy
**ALL EXISTING TESTS MUST PASS WITHOUT MODIFICATION**

### Run tests after each phase:
```bash
# After Phase 1 (dead code removal)
python -m pytest tests/backend/test_chunked_processor*.py -v

# After Phase 2 (duplication extraction)
python -m pytest tests/backend/test_chunked_processor*.py -v

# After Phase 3 (utility extraction)
python -m pytest tests/backend/test_chunked_processor*.py -v
python -m pytest tests/boundaries/test_chunked_processing_boundaries.py -v

# Final check
python -m pytest tests/ -k chunked -v --tb=short
```

### Specific test verification:
- ✓ `test_chunked_processor.py` - imports from chunked_processor (no change needed)
- ✓ `test_chunked_processor_invariants.py` - tests invariants (should still pass)
- ✓ `test_chunked_processor_boundaries.py` - boundary tests (should still pass)
- ✓ `test_chunked_processing_boundaries.py` - integration boundaries (should still pass)

---

## File Structure After Refactoring

```
auralis-web/backend/
├── chunked_processor.py (REFACTORED - 300-350 lines)
│   ├── ChunkedAudioProcessor class (main orchestrator)
│   ├── CHUNK_DURATION, CHUNK_INTERVAL, OVERLAP_DURATION, CONTEXT_DURATION
│   ├── apply_crossfade_between_chunks() function
│   └── __all__ exports (maintains backward compatibility)
│
├── chunking/ (NEW PACKAGE)
│   ├── __init__.py (public API re-exports)
│   ├── audio_metadata.py (120 lines)
│   │   └── AudioMetadataLoader class
│   ├── audio_processing.py (160 lines)
│   │   └── AudioProcessing utility class
│   ├── fingerprint.py (130 lines)
│   │   └── FingerprintManager class
│   ├── chunk_cache.py (100 lines)
│   │   └── ChunkCache class
│   └── crossfade.py (90 lines - MOVE from chunked_processor.py)
│       └── apply_crossfade_between_chunks() function
│
└── (All tests remain unchanged and in original locations)
```

---

## Impact Analysis

### Code Reduction
| Item | Before | After | Change |
|------|--------|-------|--------|
| chunked_processor.py | 1142 | 300-350 | -792 lines (-69%) |
| Total backend code | - | ~900 (split across 6 files) | More maintainable |
| Constructor | 91 | 25 | -66 lines |
| process_chunk + get_wav_chunk_path overlap | 53 dup | 0 dup | Eliminated |
| Dead code removed | - | 0 lines | -57 lines |

### Modularity Gains
✓ Each module < 200 lines (well below 300-line limit)
✓ Single responsibility per module
✓ Testable independently
✓ Reusable utilities for other features
✓ Backward compatible (all tests pass unmodified)

### Maintenance Improvements
✓ Easier to understand code flow
✓ Easier to find where specific functionality is
✓ Easier to test in isolation
✓ Easier to extend with new features
✓ Clear separation of concerns

---

## Risk Mitigation

**Risk**: Tests fail after refactoring
- **Mitigation**: Run full test suite after each phase
- **Backup**: Keep original code accessible via git history

**Risk**: Import cycles between modules
- **Mitigation**: Keep ChunkedAudioProcessor as main import, utilities in separate package
- **Verification**: `python -c "from chunked_processor import *"`

**Risk**: Behavioral change during refactoring
- **Mitigation**: Use `_process_chunk_core()` to ensure identical logic path
- **Verification**: Binary-level comparison of processed chunks

**Risk**: API compatibility issues
- **Mitigation**: All public exports maintained in chunked_processor.py
- **Verification**: All tests import from original location and still pass

---

## Implementation Order

### Week 1 (Days 1-5)
1. Phase 1: Remove dead code
2. Phase 2: Extract duplication into `_process_chunk_core()`
3. Run tests

### Week 2 (Days 6-10)
4. Phase 3: Extract utilities to modules
5. Verify imports, run tests
6. Fix any import issues

### Week 3 (Days 11-16)
7. Phase 4: Simplify constructor
8. Phase 5: Update imports and exports
9. Final testing pass
10. Update CLAUDE.md documentation

---

## Success Criteria

- [ ] Main `ChunkedAudioProcessor` class < 300 lines
- [ ] All 4 test files pass (2433 lines of tests)
- [ ] No code duplication between process_chunk and get_wav_chunk_path
- [ ] All dead code removed (WebM encoder, no-op apply_crossfade)
- [ ] Each utility module < 200 lines
- [ ] All imports from `chunked_processor` work unchanged
- [ ] No circular imports
- [ ] Backward compatibility maintained (100%)

---

## Quick Reference Commands

```bash
# Check current structure
wc -l auralis-web/backend/chunked_processor.py

# Run relevant tests
python -m pytest tests/backend/test_chunked_processor*.py -v
python -m pytest tests/boundaries/test_chunked_processing_boundaries.py -v

# Check for remaining dead code
grep -n "def _convert_to_webm_opus\|apply_crossfade()" auralis-web/backend/chunked_processor.py

# Check imports work
python -c "from chunked_processor import ChunkedAudioProcessor, CHUNK_DURATION, apply_crossfade_between_chunks; print('✓ Imports OK')"

# Verify no circular imports
python -c "import chunking; print('✓ No circular imports')"
```
