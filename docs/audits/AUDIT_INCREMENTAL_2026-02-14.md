# Incremental / Delta Audit — 2026-02-14

**Commit Range**: `59dabc94..d6bdd7ef` (10 commits)
**Auditor**: Claude Opus 4.6 (automated)
**Focus**: Code changed in last 10 commits only

## Change Summary

| Metric | Value |
|--------|-------|
| Commits | 10 |
| Files changed | 31 |
| Lines added | 4,811 |
| Lines removed | 1,433 |
| Net change | +3,378 |

### Commit Themes

| Hash | Type | Summary |
|------|------|---------|
| `d6bdd7ef` | refactor | Extract processing branches — strategy pattern (Phase 3) |
| `48b3faa7` | refactor | Complete S-curve consolidation (Phase 2.3 final) |
| `aadcc5f1` | refactor | Complete enhancement method refactoring (Phase 2.2 & 2.3) |
| `f47d0596` | refactor | Create ParallelEQUtilities for DSP consolidation (Phase 2.1) |
| `9f460102` | refactor | Extract config and utilities from simple_mastering.py (Phase 1) |
| `6cf3f0aa` | refactor | Simplify base_processing_mode to re-export wrapper |
| `27320ace` | feat | Server-side crossfade in WebSocket streaming |
| `edac7f60` | refactor | Extract services from chunked_processor (Phase 5.1) |
| `bbea0b18` | feat | Add incremental audit report for 2026-02-13 |
| `59dabc94` | fix | Move library auto-scan to background task |

### Changed File Categories

| Domain | Risk | Files |
|--------|------|-------|
| Audio Core | HIGH | `auralis/core/simple_mastering.py`, `auralis/core/mastering_branches.py` (new), `auralis/core/mastering_config.py` (new), `auralis/core/dsp/parallel_eq.py` (new), `auralis/core/utils/smooth_curves.py` (new), `auralis/core/utils/fingerprint_unpacker.py` (new), `auralis/core/utils/stage_recorder.py` (new), `auralis/core/processing/base_processing_mode.py` |
| Backend Streaming | HIGH | `auralis-web/backend/audio_stream_controller.py`, `auralis-web/backend/chunked_processor.py` |
| Backend Services | MEDIUM | `auralis-web/backend/config/startup.py`, `auralis-web/backend/core/chunk_boundaries.py` (new), `auralis-web/backend/core/chunk_cache_manager.py` (new), `auralis-web/backend/core/file_signature.py` (new), `auralis-web/backend/core/processing_lock_manager.py` (new) |
| Analysis | LOW | `auralis/analysis/mastering_profile.py` |
| Tests | LOW | 5 test files added/modified |

---

## Findings

### INC-001: Double crossfade — server applies crossfade then sends non-zero crossfade_samples to frontend
- **Severity**: HIGH
- **Changed File**: `auralis-web/backend/audio_stream_controller.py` (commit: `27320ace`)
- **Status**: NEW
- **Description**: Commit `27320ace` added server-side crossfade in `_apply_boundary_crossfade()` using equal-power curves. However, it also changed `crossfade_samples` in the WebSocket message from hardcoded `0` to the actual non-zero value. The frontend `PCMStreamBuffer.append()` checks `if (crossfadeSamples > 0)` and applies its own linear crossfade. Result: audio at chunk boundaries is crossfaded twice.
- **Evidence**:
  ```python
  # OLD (prevented frontend crossfade):
  "crossfade_samples": 0,  # Always 0 to prevent frontend from applying crossfade

  # NEW (sends non-zero value):
  "crossfade_samples": crossfade_samples,  # For monitoring/debugging
  ```
  ```typescript
  // Frontend PCMStreamBuffer.ts:119 — still applies crossfade when > 0:
  if (crossfadeSamples > 0 && this.lastChunkEnd !== null) {
    dataToWrite = this.applyCrossfade(pcm, crossfadeSamples);
  }
  ```
- **Impact**: Amplitude dips (up to ~6dB) at every chunk boundary during playback. Creates audible "pumping" artifact every 10 seconds for ALL enhanced streaming.
- **Suggested Fix**: Set `crossfade_samples` back to `0` in the WebSocket message since crossfade is now applied server-side. Keep the server-side crossfade implementation.

---

### INC-002: asyncio.create_task() called from background thread in scan progress callback
- **Severity**: HIGH
- **Changed File**: `auralis-web/backend/config/startup.py` (commit: `59dabc94`)
- **Status**: NEW
- **Description**: The fix for #2127 (startup blocking) moved the library scan to `asyncio.to_thread()`. The progress callback calls `asyncio.create_task()`, but this executes on the thread pool thread where there is no running event loop. This raises `RuntimeError: no running event loop`.
- **Evidence**:
  ```python
  def sync_progress_callback(progress_data: dict[str, Any]) -> None:
      """Synchronous wrapper that schedules async broadcast"""
      asyncio.create_task(progress_callback(progress_data))  # Runs in background thread!

  scanner.set_progress_callback(sync_progress_callback)

  # Runs in thread pool — callback fires on thread, not event loop
  scan_result = await asyncio.to_thread(scanner.scan_directories, ...)
  ```
- **Impact**: Every progress update raises RuntimeError. If LibraryScanner catches this, progress updates are silently lost. If not, the background scan crashes entirely. No scan progress is ever broadcast to WebSocket clients.
- **Suggested Fix**: Capture the event loop reference before `to_thread` and use `loop.call_soon_threadsafe()`:
  ```python
  loop = asyncio.get_running_loop()
  def sync_progress_callback(progress_data):
      loop.call_soon_threadsafe(asyncio.create_task, progress_callback(progress_data))
  ```

---

### INC-003: Spectral flatness threshold changed from 0.6 to 0.4 in "refactor" commits
- **Severity**: MEDIUM
- **Changed File**: `auralis/core/mastering_config.py` + `auralis/core/mastering_branches.py` (commit: `d6bdd7ef`)
- **Status**: NEW
- **Description**: The original `simple_mastering.py` used a spectral flatness threshold of `0.6` with range `[0.6, 1.0]`. The extracted `SimpleMasteringConfig` sets `FLATNESS_PRESERVATION_THRESHOLD = 0.4` with `ramp_to_s_curve(x, 0.4, 1.0)`. This widens the flatness preservation window. The commit message says "refactor" but this changes mastering output for tracks with spectral flatness 0.4-0.6.
- **Evidence**:
  ```python
  # OLD (simple_mastering.py):
  if spectral_flatness > 0.6:
      curve_pos = (spectral_flatness - 0.6) / 0.4  # Range [0.6, 1.0]

  # NEW (mastering_config.py):
  FLATNESS_PRESERVATION_THRESHOLD: float = 0.4  # Was 0.6!

  # NEW (mastering_branches.py QuietBranch):
  if unpacker.spectral_flatness > config.FLATNESS_PRESERVATION_THRESHOLD:
      flatness_factor = SmoothCurveUtilities.ramp_to_s_curve(
          unpacker.spectral_flatness, config.FLATNESS_PRESERVATION_THRESHOLD, 1.0
      )  # Range [0.4, 1.0] — wider than before
  ```
- **Impact**: Tracks with spectral flatness 0.4-0.6 now get gentler soft clipping than before (higher threshold_db). This affects the quiet material branch mastering output. While the change may be an improvement, it's undocumented and labeled as a refactor.
- **Suggested Fix**: Either change `FLATNESS_PRESERVATION_THRESHOLD` to `0.6` to maintain exact behavioral equivalence, or add a note to the commit/config documenting this as an intentional tuning change.

---

### INC-004: ProcessingLockManager instantiated but never used — leaks ThreadPoolExecutor
- **Severity**: MEDIUM
- **Changed File**: `auralis-web/backend/chunked_processor.py` (commit: `edac7f60`)
- **Status**: NEW
- **Description**: Phase 5.2 extraction added `self._lock_manager = ProcessingLockManager()` but the actual locking still uses the old `self._processor_lock = asyncio.Lock()`. ProcessingLockManager creates a `ThreadPoolExecutor(max_workers=1)` in `__init__` that is never shut down.
- **Evidence**:
  ```python
  # Created but never used:
  self._lock_manager: Any = ProcessingLockManager()

  # Still used for actual locking:
  self._processor_lock = asyncio.Lock()
  async with self._processor_lock:  # line 630
  ```
- **Impact**: Resource leak — each ChunkedAudioProcessor instance creates an orphaned thread pool executor. For long-running servers, this accumulates threads.
- **Suggested Fix**: Remove the `_lock_manager` instantiation until the migration to ProcessingLockManager is complete, or complete the migration and remove `_processor_lock`.

---

### INC-005: test_fix_2150.py placed outside pytest testpaths — never discovered by CI
- **Severity**: HIGH
- **Changed File**: `test_fix_2150.py` (commit: `59dabc94` area)
- **Status**: NEW
- **Description**: `test_fix_2150.py` is placed at the project root, but `pytest.ini` defines `testpaths = tests`. This file is never discovered by `pytest` unless explicitly specified. Additionally, the test uses `return True/False` instead of `assert`, so even if discovered, failures would be silent. It also hardcodes `/mnt/data/src/matchering` in `sys.path.insert`.
- **Evidence**:
  ```ini
  # pytest.ini:
  testpaths = tests
  ```
  ```python
  # test_fix_2150.py line 11:
  sys.path.insert(0, '/mnt/data/src/matchering')

  # test_fix_2150.py line 33-38:
  if np.array_equal(original, original_copy):
      return True   # pytest does NOT detect this as failure
  else:
      return False  # pytest ignores return values
  ```
- **Impact**: Regression test for issue #2150 (in-place modification bug) is never run in CI. If the bug recurs, this test will not catch it.
- **Suggested Fix**: Move to `tests/core/test_compression_expansion_invariants.py`, convert return-value assertions to `assert` statements, and remove the hardcoded path.

---

### INC-006: test_startup_background_scan.py tests simulated patterns, not actual production code
- **Severity**: MEDIUM
- **Changed File**: `tests/backend/test_startup_background_scan.py` (commit: `59dabc94`)
- **Status**: NEW
- **Description**: All four tests define their own `simulated_background_scan()` / `slow_scan()` functions that reimplement the pattern from `config/startup.py`. If the production code diverges from these simulations, the tests continue passing despite real bugs.
- **Evidence**:
  ```python
  # Test defines local mock (not testing real code):
  async def simulated_background_scan():
      await manager.broadcast({"type": "library_scan_started", ...})
      for i in range(3):
          await manager.broadcast({"type": "library_scan_progress", ...})
      await manager.broadcast({"type": "library_scan_completed", ...})

  # Actual production code (config/startup.py) uses LibraryScanner,
  # scan_directories, asyncio.to_thread, etc. — never tested.
  ```
- **Impact**: Tests provide false confidence. The asyncio.create_task bug (INC-002) exists in production but these tests pass because they don't exercise the real code path.
- **Suggested Fix**: Test the actual `_background_auto_scan()` function with mocked `LibraryScanner` and `connection_manager`.

---

### INC-007: test_tail_cleaned_on_stream_error is tautological
- **Severity**: MEDIUM
- **Changed File**: `tests/backend/test_audio_stream_crossfade.py` (commit: `27320ace`)
- **Status**: NEW
- **Description**: The test manually calls `controller._chunk_tails.pop(track_id, None)` then asserts the key is gone. It tests that `dict.pop()` works, not that the application properly cleans up on errors.
- **Evidence**:
  ```python
  # Test manually performs the cleanup it's supposed to verify:
  controller._chunk_tails.pop(track_id, None)
  # Then asserts the cleanup "worked":
  assert track_id not in controller._chunk_tails
  ```
- **Impact**: Zero value — if cleanup code in `stream_enhanced_audio` is broken, this test still passes.
- **Suggested Fix**: Test `stream_enhanced_audio()` directly to verify the finally-block cleanup, or test that `_process_and_stream_chunk` propagates exceptions properly.

---

### INC-008: Unused import of apply_crossfade_between_chunks
- **Severity**: LOW
- **Changed File**: `auralis-web/backend/audio_stream_controller.py` (commit: `27320ace`)
- **Status**: NEW
- **Description**: `apply_crossfade_between_chunks` is imported from `chunked_processor` but never used. The controller has its own `_apply_boundary_crossfade` method.
- **Evidence**:
  ```python
  from chunked_processor import ChunkedAudioProcessor, apply_crossfade_between_chunks
  # apply_crossfade_between_chunks is never referenced in the file
  ```
- **Impact**: Linting warning (F401), misleading dependency.
- **Suggested Fix**: Remove the unused import.

---

### INC-009: test_background_scan_does_not_block uses timing-based assertion
- **Severity**: LOW
- **Changed File**: `tests/backend/test_startup_background_scan.py` (commit: `59dabc94`)
- **Status**: NEW
- **Description**: Test asserts `startup_duration < 0.05` seconds, which is flaky on loaded CI machines.
- **Evidence**:
  ```python
  assert startup_duration < 0.05, f"Startup took {startup_duration:.2f}s, expected < 0.05s"
  ```
- **Impact**: Flaky test failures in CI under load.
- **Suggested Fix**: Assert structural non-blocking (task not done, scan not completed) instead of wall-clock timing.

---

## Cross-Layer Impact

| Change | Layers Affected | Impact |
|--------|----------------|--------|
| Server-side crossfade + non-zero crossfade_samples | Backend → Frontend | Double crossfade at every chunk boundary (INC-001) |
| asyncio.create_task from thread | Backend → WebSocket clients | No scan progress updates reach frontend (INC-002) |
| Spectral flatness threshold change | Audio core → Backend → All playback | Different mastering output for quiet tracks with flatness 0.4-0.6 (INC-003) |

## Missing Tests

| Changed Code | Test Coverage |
|--------------|--------------|
| `auralis/core/mastering_branches.py` (475 lines, new) | No unit tests for MaterialClassifier or branch-specific processing |
| `auralis/core/mastering_config.py` (177 lines, new) | No tests verifying config defaults match original magic numbers |
| `auralis/core/dsp/parallel_eq.py` (247 lines, new) | No tests for ParallelEQUtilities filter operations |
| `auralis/core/utils/smooth_curves.py` (178 lines, new) | No tests for SmoothCurveUtilities (S-curve, bell curve, ramp) |
| `auralis/core/utils/fingerprint_unpacker.py` (231 lines, new) | No tests for FingerprintUnpacker defaults or property access |
| `auralis/core/utils/stage_recorder.py` (98 lines, new) | No tests for StageRecorder |
| `auralis-web/backend/core/chunk_boundaries.py` (271 lines, new) | No unit tests for ChunkBoundaryManager |
| `auralis-web/backend/core/processing_lock_manager.py` (195 lines, new) | No tests; design has cross-loop asyncio.Lock flaw |

## Summary

| Severity | Count | IDs |
|----------|-------|-----|
| HIGH | 3 | INC-001, INC-002, INC-005 |
| MEDIUM | 4 | INC-003, INC-004, INC-006, INC-007 |
| LOW | 2 | INC-008, INC-009 |
| **Total** | **9** | |

### Key Themes
1. **Cross-layer contract break**: Server-side crossfade was added without updating the frontend contract (INC-001)
2. **Thread-safety in async fix**: The fix for #2127 introduced asyncio.create_task from a background thread (INC-002)
3. **Behavioral change in refactor**: Config extraction changed a threshold value, altering mastering output (INC-003)
4. **Test quality gaps**: New tests are outside pytest discovery, use wrong assertion patterns, or test simulated code instead of real code (INC-005, INC-006, INC-007)
5. **No tests for 1,700+ lines of new extracted code**: The refactoring created 8 new modules with zero test coverage
