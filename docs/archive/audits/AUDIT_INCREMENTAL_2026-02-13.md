# Incremental Audit Report — 2026-02-13
**Scope**: Last 10 commits (ce27e1df → 7c5ade49)
**Auditor**: Claude Sonnet 4.5
**Date**: 2026-02-13
**Focus**: Regression detection, cross-layer impact, fix verification

## Executive Summary

Audited 25 changed files across 10 commits, covering 7 bug fixes and 4 new test suites. Most fixes are correctly implemented with excellent test coverage (1255 lines added). **Critical finding**: Path traversal fix (#2069) was incomplete — the library scan endpoint remains vulnerable.

**Risk Summary**:
- 🔴 **1 HIGH** — Incomplete path traversal fix leaves library scan endpoint vulnerable
- 🟡 **1 MEDIUM** — Duplicate `ScanRequest` models with different schemas cause confusion
- ✅ **7 fixes verified** — All other fixes correctly implemented

---

## Commits Analyzed

```
7c5ade49  fix: Remove double windowing in FFT EQ to eliminate amplitude modulation (#2166)
74471dfd  fix: Remove unbounded _deleted_track_ids set to prevent memory leak (#2081)
6a2c04a6  fix: Pass correct sample rate to AudioContext in usePlayNormal (#2098)
5dc13efc  chore: Add test-results to .gitignore
dccff38c  docs: Add comprehensive audit reports (2026-02-12/13)
0048589e  fix: Add missing SpectrumSettings import to spectrum_analyzer.py
ac96c038  fix: Add .copy() to compression/expansion functions to prevent in-place modification (#2150)
457d9eff  fix: Change library scan format from bare parameters to ScanRequest body (#2101)
7163b530  fix: Add path traversal validation to directory scanning endpoint (#2069)
ce27e1df  fix: Add WebSocket message size validation and rate limiting (#2156)
```

**Files Changed**: 25
**Test Coverage**: +1255 lines (4 new test files)

---

## Findings

### 🔴 HIGH-1: Path Traversal Fix Incomplete — Library Scan Endpoint Still Vulnerable

**File**: `auralis-web/backend/schemas.py:663-675`, `auralis-web/backend/routers/library.py:436`
**Introduced**: Commit 457d9eff (fix #2101)
**Root Cause**: Path validation applied to files router but not library router

The path traversal fix (#2069) added `validate_scan_path()` to the files router's `ScanRequest` model via a `field_validator`. However, the library scan endpoint uses a **different** `ScanRequest` model from `schemas.py` that has **NO path validation**.

**Evidence**:

1. **Files router** (`routers/files.py:41-66`):
   ```python
   class ScanRequest(BaseModel):
       directory: str

       @field_validator('directory')
       @classmethod
       def validate_directory_path(cls, v: str) -> str:
           validated_path = validate_scan_path(v)  # ✅ SECURE
           return str(validated_path)
   ```

2. **Library router** (`schemas.py:663-675`, used by `routers/library.py:31,436`):
   ```python
   class ScanRequest(BaseModel):
       directories: list[str] = Field(...)  # ❌ NO VALIDATION
       recursive: bool = Field(default=True, ...)
       skip_existing: bool = Field(default=True, ...)
   ```

3. **Scanner** (`auralis/library/scanner.py`):
   - No path validation in `scan_directories()` method
   - Accepts arbitrary paths from the endpoint

**Attack Vector**:
```bash
curl -X POST http://localhost:8765/api/library/scan \
  -H "Content-Type: application/json" \
  -d '{"directories": ["/etc", "/root", "../../sensitive"]}'
```

**Impact**:
- ⚠️ **Directory enumeration**: Attacker can scan system directories
- ⚠️ **Information disclosure**: File paths and metadata from restricted areas
- ⚠️ **DoS potential**: Scan large directories like `/` or `/usr`

**Recommendation**:
Add `field_validator` to `schemas.py` `ScanRequest.directories`:
```python
@field_validator('directories')
@classmethod
def validate_directory_paths(cls, v: list[str]) -> list[str]:
    from path_security import validate_scan_path
    return [str(validate_scan_path(path)) for path in v]
```

**Related**: Issue #2069 (original path traversal fix)

---

### 🟡 MEDIUM-1: Duplicate ScanRequest Models with Different Schemas

**Files**: `auralis-web/backend/schemas.py:663`, `auralis-web/backend/routers/files.py:41`
**Impact**: Confusing naming, risk of importing wrong model

Two `ScanRequest` models exist with the same name but different schemas:

| Location | Schema | Validation | Used By |
|----------|--------|------------|---------|
| `schemas.py:663` | `directories: list[str]` | ❌ None | Library router |
| `routers/files.py:41` | `directory: str` | ✅ `validate_scan_path()` | Files router |

**Issues**:
1. **Naming collision**: Both named `ScanRequest`, causing confusion
2. **Import ambiguity**: Easy to import the wrong model
3. **Inconsistent security**: One has validation, one doesn't

**Example Confusion**:
```python
# Which ScanRequest is this?
from schemas import ScanRequest  # Unvalidated version
from routers.files import ScanRequest  # Validated version
```

**Recommendation**:
Rename to be specific:
- `schemas.py`: `LibraryScanRequest` (and add validation per HIGH-1)
- `routers/files.py`: `FileScanRequest` or keep local

**Alternative**: Move both to `schemas.py` with proper validation.

---

## Fixes Verified ✅

All 7 bug fixes were reviewed and verified correct:

### ✅ #2150: Copy-Before-Modify Fix (ac96c038)
**File**: `auralis/core/processing/base/compression_expansion.py`
**Changes**: Added `audio = audio.copy()` at top of both `apply_soft_knee_compression()` and `apply_peak_enhancement_expansion()`
**Verification**: ✅ Correct — preserves critical audio DSP invariant
**Test Coverage**: ✅ 252 lines (`tests/auralis/core/test_compression_expansion_invariants.py`)

### ✅ #2166: Double Windowing Fix (7c5ade49)
**File**: `auralis/dsp/eq/filters.py`
**Changes**: Removed Hanning window application before FFT and after IFFT
**Impact**: Eliminates ~3dB amplitude drop and envelope modulation
**Verification**: ✅ Correct — EQ should not apply windowing (OLA is for STFT, not EQ)
**Test Coverage**: ✅ 204 lines (`tests/test_fix_2166_double_windowing.py`) — amplitude, RMS, envelope, spectral tests

### ✅ #2156: WebSocket Security (ce27e1df)
**Files**: `auralis-web/backend/routers/system.py`, `websocket_security.py` (new), `schemas.py`, `websocket_protocol.py`
**Changes**:
- Added `WebSocketRateLimiter` (10 msg/sec per connection)
- Added `validate_and_parse_message()` with 64KB size limit
- Added `WebSocketMessageType` enum with schema validation
- Integrated into `streaming_control_handler` before message parsing

**Verification**: ✅ Correct
- Rate limiting: ✅ Per-connection, sliding window, cleanup on disconnect
- Size validation: ✅ 64KB limit prevents memory exhaustion
- Schema validation: ✅ Enum covers all 9 handler message types (ping, processing_settings_update, ab_track_loaded, play_enhanced, play_normal, pause, stop, seek, subscribe_job_progress)

**Test Coverage**: ✅ 440 lines (`tests/security/test_websocket_security.py`) — size limits, JSON parsing, schema validation, rate limiting, DoS prevention

### ✅ #2069: Path Validation (files router only) (7163b530)
**Files**: `auralis-web/backend/path_security.py` (new), `routers/files.py`
**Changes**:
- New `path_security.py` module with `validate_scan_path()`, whitelist of allowed dirs (home, ~/Music, ~/Documents, XDG_MUSIC_DIR)
- Added `field_validator` to files router's `ScanRequest.directory`
- Checks for `..` in path parts, resolves symlinks, verifies directory exists and is readable

**Verification**: ✅ Correct for files router, ❌ **INCOMPLETE** for library router (see HIGH-1)
**Test Coverage**: ✅ 359 lines (`tests/security/test_scan_path_validation.py`) — traversal, absolute paths, symlinks, non-existent, unreadable, empty, null

### ✅ #2101: Library Scan Format (457d9eff)
**File**: `auralis-web/backend/routers/library.py`
**Changes**: Changed `scan_library` from bare parameters (`directory: str`, `recursive: bool`, `skip_existing: bool`) to `ScanRequest` body model
**Frontend Alignment**: ✅ `useLibraryData.ts` changed from `{ directory: folderPath }` to `{ directories: [folderPath] }` (commit 6a2c04a6)
**Verification**: ✅ Contract aligned, but model lacks validation (see HIGH-1)

### ✅ #2081: Memory Leak Fix (74471dfd)
**File**: `auralis/library/manager.py`
**Changes**: Removed unbounded `_deleted_track_ids: set[int]` tracking set
**Verification**: ✅ Correct
- Database itself prevents double-deletion (returns False if not exists)
- `_delete_lock` (RLock) still present to serialize delete operations
- Simplification eliminates memory leak from set growing indefinitely

### ✅ #2098: AudioContext Sample Rate (6a2c04a6)
**File**: `auralis-web/frontend/src/hooks/enhancement/usePlayNormal.ts:206-224`
**Changes**:
- Creates AudioContext with `{ sampleRate: sourceSampleRate }` matching streaming audio
- Closes old context if sample rate differs before creating new one
- Prevents ~9% playback speed error (48000Hz context playing 44100Hz audio)

**Verification**: ✅ Correct
- Backend sends `message.data.sample_rate` in streaming init message
- Frontend now matches this rate when creating AudioContext
- Closes old context before creating new one (prevents leak)

**Minor Edge Case**: If `new AudioContextClass()` throws after closing old context, `audioContextRef.current` points to closed context until next init. Unlikely and self-healing.

---

## Cross-Layer Impact Analysis

### Frontend ↔ Backend Contract Changes

| Change | Frontend | Backend | Status |
|--------|----------|---------|--------|
| Library scan format | `useLibraryData.ts`: `directories: [path]` | `library.py`: `ScanRequest.directories` | ✅ Aligned |
| WebSocket message types | Uses 9 message types | Enum covers all 9 types | ✅ Complete |
| AudioContext sample rate | Reads `message.data.sample_rate` | Sends `sample_rate` in init | ✅ Aligned |

### Database Changes
- **Schema**: No migrations in this commit range
- **`_deleted_track_ids` removal**: Internal change only, no schema impact

### Test Coverage
Excellent coverage for all fixes:

| Fix | Test File | Lines | Coverage |
|-----|-----------|-------|----------|
| #2150 (copy-before-modify) | `test_compression_expansion_invariants.py` | 252 | Comprehensive |
| #2166 (double windowing) | `test_fix_2166_double_windowing.py` | 204 | Amplitude, RMS, envelope, spectral |
| #2069 (path validation) | `test_scan_path_validation.py` | 359 | Traversal, symlinks, edge cases |
| #2156 (WebSocket security) | `test_websocket_security.py` | 440 | Size, JSON, schema, rate limit, DoS |

**Total**: 1255 lines of test coverage for 4 security/correctness fixes.

---

## Regression Check

### Audio DSP Invariants
- ✅ **Sample count preservation**: `compression_expansion.py` now uses `.copy()` before modification
- ✅ **Amplitude consistency**: Double windowing removed from `filters.py`
- ✅ **No in-place modification**: Verified in test suite

### Security Posture
- ✅ **WebSocket**: Rate limiting, size validation, schema validation added
- ⚠️ **Path traversal**: Partially fixed (files router ✅, library router ❌)
- ✅ **Input validation**: WebSocket message types now validated

### Memory Leaks
- ✅ **`_deleted_track_ids`**: Removed from manager.py
- ✅ **AudioContext**: Closes old context before creating new one

### Performance
- No performance regressions detected
- Test suites cover edge cases (zero-length, large arrays, deeply nested JSON)

---

## Non-Issues (Disproved Findings)

The following potential issues were investigated and determined to be **not actual bugs**:

1. ✅ **`from __future__ import annotations`**: Added to 4 files (mastering_fingerprint.py, unified_config.py, continuous_space.py, websocket_protocol.py). This is Python 3.14+ typing modernization, not a bug.

2. ✅ **SpectrumSettings import**: Added to `spectrum_analyzer.py` (commit 0048589e). Legitimate import fix, not an issue.

3. ✅ **.gitignore test-results**: Added `test-results/` to `.gitignore` (commit 5dc13efc). Standard test artifact cleanup.

---

## Recommendations

### Immediate (Before Next Release)
1. **🔴 HIGH-1**: Add path validation to `schemas.py` `ScanRequest.directories` field
2. **🟡 MEDIUM-1**: Rename duplicate `ScanRequest` models to avoid confusion

### Next Sprint
1. Add integration tests for library scan endpoint with path traversal attempts
2. Audit all Pydantic models for missing input validation
3. Document which `ScanRequest` is used by which endpoint

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Commits analyzed | 10 |
| Files changed | 25 |
| New findings | 2 (1 HIGH, 1 MEDIUM) |
| Fixes verified | 7 ✅ |
| Test lines added | 1255 |
| Security issues found | 1 (incomplete fix) |
| Regressions detected | 0 |

**Conclusion**: Most fixes are correctly implemented with excellent test coverage. The critical finding is that the path traversal fix (#2069) was incomplete — the library scan endpoint bypasses validation. This should be addressed before the next release.

---

**Report Generated**: 2026-02-13
**Tool**: Claude Sonnet 4.5 (incremental audit mode)
**Commits**: ce27e1df → 7c5ade49 (10 commits)
