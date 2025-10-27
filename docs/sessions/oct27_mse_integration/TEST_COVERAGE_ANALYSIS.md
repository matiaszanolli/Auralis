# MSE Integration - Test Coverage Analysis & Improvement Plan

**Date**: October 27, 2025
**Focus**: Backend unified streaming components
**Status**: Phase 4 - Comprehensive Testing

---

## Executive Summary

Initial test coverage run reveals **75% coverage on unified_streaming.py** and **38% on webm_encoder.py**. Created comprehensive test suites (30+ tests) that identified import/mocking issues. This document provides detailed coverage analysis and improvement plans for both backend and frontend.

---

## Backend Coverage Analysis

### Test Run Results

```
Command: pytest tests/backend/test_webm_encoder.py tests/backend/test_unified_streaming.py
         --cov=auralis-web/backend --cov-report=term-missing

Results:
- 15 failed (import/mocking issues)
- 3 passed
- 3 skipped
- 11 errors (fixture/import errors)
```

### Coverage by Module

| Module | Statements | Missed | Coverage | Missing Lines |
|--------|-----------|--------|----------|---------------|
| `unified_streaming.py` | 96 | 24 | **75%** | 69, 72-74, 86, 129-131, 136-150, 172-174, 190, 218-224, 231 |
| `webm_encoder.py` | 74 | 46 | **38%** | 57-123, 145-152, 161-167, 200-208 |
| **Overall Backend** | 4,237 | 4,061 | **4%** | (entire codebase) |

---

## unified_streaming.py Coverage Analysis

### Covered (75%)

✅ **Well-tested**:
- Metadata endpoint logic (lines 44-68)
- Basic routing logic
- Router factory pattern
- Cache statistics endpoint

### Not Covered (25%)

❌ **Missing Coverage**:

**Lines 69, 72-74** - File path validation:
```python
if not os.path.exists(track.filepath):
    raise HTTPException(404, f"Audio file not found: {track.filepath}")
```
**Impact**: P1 - File not found handling
**Test Needed**: `test_metadata_missing_file()`

**Lines 86** - Error handling:
```python
except HTTPException:
    raise
except Exception as e:
    logger.error(f"Metadata error: {e}")
```
**Impact**: P2 - General error handling
**Test Needed**: `test_metadata_unexpected_error()`

**Lines 129-131, 136-150** - WebM chunk encoding:
```python
# Load and encode
logger.info(f"WebM cache MISS: encoding chunk {chunk_idx}")
start_time = chunk_idx * chunk_duration
audio, sr = librosa.load(track.filepath, sr=None, mono=False,
                         offset=start_time, duration=chunk_duration)
# Transpose logic
if audio.ndim == 2:
    audio = audio.T
# Encode to WebM
webm_path = await encode_audio_to_webm(audio, sr, cache_key)
```
**Impact**: P0 - Core functionality
**Test Needed**: Integration test with real audio

**Lines 172-174** - Enhanced chunk placeholder:
```python
# TODO: Integrate with multi-tier buffer
raise HTTPException(501, "Enhanced streaming not yet integrated")
```
**Impact**: P1 - MTB integration
**Test Needed**: Integration test when MTB connected

**Lines 190, 218-224, 231** - Error handling paths:
```python
except HTTPException:
    raise
except Exception as e:
    logger.error(f"WebM chunk error: {e}")
    raise HTTPException(500, str(e))
```
**Impact**: P2 - Error handling
**Test Needed**: Error injection tests

---

## webm_encoder.py Coverage Analysis

### Covered (38%)

✅ **Tested**:
- Module initialization
- Basic class structure
- get_encoder singleton

### Not Covered (62%)

❌ **Critical Missing Coverage**:

**Lines 57-123** - Core encode_chunk method:
```python
async def encode_chunk(self, audio, sample_rate, cache_key, bitrate="128k"):
    # Write temp WAV
    sf.write(str(temp_wav), audio, sample_rate)

    # ffmpeg command
    cmd = ['ffmpeg', '-i', str(temp_wav), '-c:a', 'libopus', ...]

    # Run async
    proc = await asyncio.create_subprocess_exec(*cmd, ...)
    stdout, stderr = await proc.communicate()

    # Error handling
    if proc.returncode != 0:
        raise RuntimeError(f"WebM encoding failed: {error_msg}")

    # Statistics and cleanup
    ...
```
**Impact**: P0 - Absolute core functionality
**Why Not Covered**: Async test execution issues
**Test Needed**: Fix async fixtures and test encoding

**Lines 145-152** - get_cached_path:
```python
def get_cached_path(self, cache_key):
    webm_path = self.temp_dir / f"{cache_key}.webm"
    if webm_path.exists():
        return webm_path
    return None
```
**Impact**: P0 - Caching mechanism
**Test Needed**: `test_get_cached_path()`

**Lines 161-167** - clear_cache:
```python
def clear_cache(self):
    for webm_file in self.temp_dir.glob("*.webm"):
        webm_file.unlink()
```
**Impact**: P1 - Cache management
**Test Needed**: `test_clear_cache()`

**Lines 200-208** - get_cache_size:
```python
def get_cache_size(self):
    files = list(self.temp_dir.glob("*.webm"))
    total_size = sum(f.stat().st_size for f in files)
    return len(files), total_size / (1024 * 1024)
```
**Impact**: P2 - Monitoring
**Test Needed**: `test_get_cache_size()`

---

## Test Issues Identified

### 1. Import Path Problems

**Problem**: Tests can't import modules from `auralis-web/backend/`

**Current Approach**:
```python
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'))
from webm_encoder import WebMEncoder
```

**Fix Needed**:
- Option A: Make `auralis-web/backend` a proper Python package with `__init__.py`
- Option B: Use relative imports with proper package structure
- Option C: Install backend as editable package: `pip install -e auralis-web/backend`

**Recommendation**: Option C (cleanest)

### 2. Async Test Execution

**Problem**: pytest-asyncio not properly configured

**Fix**:
```python
# In tests/conftest.py
import pytest

@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
```

**Also Need**:
```python
# Mark all async tests
@pytest.mark.asyncio
async def test_encode_chunk():
    ...
```

### 3. Mocking External Dependencies

**Problem**: Need to mock ffmpeg, librosa, file I/O

**Better Mocking Pattern**:
```python
@pytest.mark.asyncio
@patch('webm_encoder.asyncio.create_subprocess_exec')
async def test_encode_with_mock_ffmpeg(mock_subprocess):
    mock_proc = Mock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))
    mock_subprocess.return_value = mock_proc

    # Test encoding
    ...
```

### 4. TestClient Issues

**Problem**: FastAPI TestClient doesn't work well with router factories

**Fix**: Create proper app fixture:
```python
@pytest.fixture
def app(mock_library_manager):
    from fastapi import FastAPI
    app = FastAPI()

    router = create_unified_streaming_router(
        get_library_manager=lambda: mock_library_manager,
        ...
    )
    app.include_router(router)
    return app

@pytest.fixture
def client(app):
    return TestClient(app)
```

---

## Backend Test Improvement Plan

### Priority 0 (Critical - Must Fix)

**1. Fix Import Structure** (1 hour)
- Make `auralis-web/backend` a proper package
- Add `__init__.py` files
- Create `pyproject.toml` or `setup.py`
- Install as editable: `pip install -e ./auralis-web/backend`

**2. Fix Async Test Execution** (30 min)
- Add proper `conftest.py` with event loop fixture
- Ensure all async tests use `@pytest.mark.asyncio`
- Test with simple async test first

**3. Test webm_encoder Core Functions** (1 hour)
- `test_encode_chunk_success()` - Basic encoding
- `test_get_cached_path()` - Cache retrieval
- `test_clear_cache()` - Cache management
- Mock ffmpeg subprocess properly

**4. Test unified_streaming Integration** (1 hour)
- `test_metadata_missing_file()` - File not found
- `test_chunk_encoding_flow()` - End-to-end chunk delivery
- `test_cache_hit_miss()` - Cache behavior

### Priority 1 (High - Should Fix)

**5. Error Handling Tests** (1 hour)
- WebM encoding failures
- librosa load failures
- Invalid chunk indices
- Network/timeout errors

**6. Edge Case Tests** (1 hour)
- Zero-duration tracks
- Very large files (10+ hours)
- Corrupt audio files
- Missing audio codecs

**7. Concurrent Access Tests** (1 hour)
- Multiple simultaneous chunk requests
- Cache race conditions
- Thread safety verification

### Priority 2 (Medium - Nice to Have)

**8. Performance Tests** (30 min)
- Encoding speed benchmarks
- Cache performance
- Memory usage under load

**9. Integration Tests** (2 hours)
- Full flow with real audio files
- Mode switching verification
- Multi-tier buffer integration (when ready)

---

## Frontend Test Strategy

### Current Frontend Structure

**Existing Frontend Tests**:
- Location: `auralis-web/frontend/src/`
- Framework: Vitest
- Current: 245 tests (234 passing, 11 failing - 95.5%)

**New Components to Test**:
1. `UnifiedPlayerManager.ts` (640 lines)
2. `useUnifiedPlayer.ts` (180 lines)
3. `UnifiedPlayerExample.tsx` (200 lines)
4. `BottomPlayerBarUnified.tsx` (320 lines)

### Frontend Coverage Goals

**Target**: 80%+ coverage on new components

### Frontend Test Plan

#### Priority 0 (Critical)

**1. UnifiedPlayerManager Unit Tests** (2 hours)

File: `auralis-web/frontend/src/services/__tests__/UnifiedPlayerManager.test.ts`

```typescript
describe('UnifiedPlayerManager', () => {
  describe('MSEPlayerInternal', () => {
    it('initializes MediaSource correctly')
    it('loads WebM chunks progressively')
    it('handles seeking')
    it('cleans up resources')
  })

  describe('HTML5AudioPlayerInternal', () => {
    it('loads enhanced audio')
    it('handles seeking')
    it('cleans up resources')
  })

  describe('Mode Switching', () => {
    it('switches from MSE to HTML5')
    it('switches from HTML5 to MSE')
    it('preserves playback position')
    it('resumes playback after switch')
  })

  describe('Event System', () => {
    it('emits statechange events')
    it('emits timeupdate events')
    it('emits modeswitched events')
    it('emits presetswitched events')
    it('handles errors')
  })
})
```

**Coverage Target**: 85%

**2. useUnifiedPlayer Hook Tests** (1 hour)

File: `auralis-web/frontend/src/hooks/__tests__/useUnifiedPlayer.test.ts`

```typescript
describe('useUnifiedPlayer', () => {
  it('initializes manager on mount')
  it('cleans up on unmount')
  it('loads tracks')
  it('handles playback controls')
  it('switches modes')
  it('updates state reactively')
  it('handles errors')
})
```

**Coverage Target**: 90%

**3. BottomPlayerBarUnified Component Tests** (1 hour)

File: `auralis-web/frontend/src/components/__tests__/BottomPlayerBarUnified.test.tsx`

```typescript
describe('BottomPlayerBarUnified', () => {
  it('renders player controls')
  it('displays track information')
  it('handles play/pause')
  it('handles seeking')
  it('handles volume changes')
  it('handles enhancement toggle')
  it('handles preset selection')
  it('shows loading states')
  it('shows mode indicator')
})
```

**Coverage Target**: 80%

#### Priority 1 (High)

**4. Integration Tests** (2 hours)

Test full flow with mocked backend:
- Track loading → playback → mode switching → preset changes

**5. Mock Service Worker (MSW)** (1 hour)

Set up MSW to mock backend API:
```typescript
// Setup mock handlers for:
// - GET /api/audio/stream/{id}/metadata
// - GET /api/audio/stream/{id}/chunk/{idx}
// - GET /api/audio/stream/cache/stats
```

---

## Vitest Configuration

**Location**: `auralis-web/frontend/vitest.config.ts`

**Recommended Config**:
```typescript
export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/tests/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: [
        'src/services/**/*.ts',
        'src/hooks/**/*.ts',
        'src/components/**/*.tsx'
      ],
      exclude: [
        '**/__tests__/**',
        '**/*.test.ts',
        '**/*.test.tsx'
      ],
      thresholds: {
        branches: 70,
        functions: 70,
        lines: 70,
        statements: 70
      }
    }
  }
})
```

---

## Test Execution Commands

### Backend

```bash
# Run all backend tests with coverage
pytest tests/backend/ -v --cov=auralis-web/backend --cov-report=html

# Run only MSE integration tests
pytest tests/backend/test_webm_encoder.py tests/backend/test_unified_streaming.py -v

# Run with specific markers
pytest tests/backend/ -v -m "not integration"  # Skip integration tests
pytest tests/backend/ -v -m "integration"      # Only integration tests
```

### Frontend

```bash
cd auralis-web/frontend

# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Run specific test file
npm test -- UnifiedPlayerManager.test.ts

# Watch mode
npm test -- --watch
```

---

## Success Metrics

### Backend

- [ ] unified_streaming.py: 90%+ coverage
- [ ] webm_encoder.py: 85%+ coverage
- [ ] All P0 tests passing
- [ ] All P1 tests passing
- [ ] Zero import/fixture errors

### Frontend

- [ ] UnifiedPlayerManager.ts: 85%+ coverage
- [ ] useUnifiedPlayer.ts: 90%+ coverage
- [ ] BottomPlayerBarUnified.tsx: 80%+ coverage
- [ ] All new tests passing
- [ ] No new failures in existing tests

### Overall

- [ ] Backend MSE components: 85%+ coverage
- [ ] Frontend MSE components: 80%+ coverage
- [ ] < 5% regression in existing tests
- [ ] All critical paths tested
- [ ] All error paths tested

---

## Timeline

**Total Estimated Time**: 12-15 hours

**Phase 1: Backend Fixes** (4-5 hours)
- P0 import fixes: 1 hour
- P0 async fixes: 30 min
- P0 core tests: 2 hours
- P1 error/edge cases: 2 hours

**Phase 2: Frontend Tests** (6-7 hours)
- P0 UnifiedPlayerManager: 2 hours
- P0 useUnifiedPlayer: 1 hour
- P0 BottomPlayerBarUnified: 1 hour
- P1 Integration tests: 2 hours
- P1 MSW setup: 1 hour

**Phase 3: Validation** (2-3 hours)
- Run full test suites
- Fix any failures
- Verify coverage thresholds
- Document results

---

## Next Steps

**Immediate (Next Session)**:
1. Fix backend import structure
2. Fix async test configuration
3. Get 5-10 core tests passing
4. Verify coverage improves

**Short Term (This Week)**:
1. Complete P0 backend tests
2. Complete P0 frontend tests
3. Achieve 80%+ coverage on new code

**Medium Term (Next Week)**:
1. Complete P1 tests
2. Add integration tests
3. Performance testing

---

## Appendix: Test File Structure

```
tests/
├── backend/
│   ├── conftest.py (fixtures, event loop)
│   ├── test_webm_encoder.py (30+ tests)
│   ├── test_unified_streaming.py (20+ tests)
│   └── integration/
│       └── test_mse_flow.py
└── frontend/ (Vitest)
    └── src/
        ├── services/__tests__/
        │   └── UnifiedPlayerManager.test.ts
        ├── hooks/__tests__/
        │   └── useUnifiedPlayer.test.ts
        └── components/__tests__/
            └── BottomPlayerBarUnified.test.tsx
```

---

## Conclusion

Created comprehensive test suites (50+ tests total) for MSE integration. Initial run revealed:
- **75% coverage** on unified_streaming.py (good baseline)
- **38% coverage** on webm_encoder.py (needs work)
- Import/async issues preventing full execution

**Priority**: Fix P0 infrastructure issues (imports, async), then execute tests to achieve 85%+ coverage on new code.

**Confidence**: With proper fixtures, expect 85-90% coverage achievable in 4-5 hours of focused work.
