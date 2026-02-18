# Incremental Audit — 2026-02-18

**Range**: `HEAD~10..HEAD`
**Auditor**: Claude Code (automated)
**Date**: 2026-02-18

---

## 1. Change Summary

| Stat | Value |
|------|-------|
| Commits | 10 |
| Files changed | 38 (14 source, 11 test, 11 docs/.claude, 2 config) |
| Key themes | Bug fixes from 2026-02-17 audit; DSP correctness; thread safety; DB path hardcoding; upload lifecycle |

### Commits (newest first)

| Hash | Message |
|------|---------|
| `6c8d1db5` | Refactor security audit documentation and add common audit protocol |
| `bd94fd59` | fix: replace offset pagination with ID-cursor in cleanup_missing_files (issue #2242) |
| `8adb8d0a` | fix(#2395): dispose SQLAlchemy engine in MigrationManager.close() |
| `53cef6b4` | fix: update audio loading and threading in AudioFingerprintAnalyzer to prevent blocking on KeyboardInterrupt |
| `12678e8c` | fix: resolve three high/critical bugs from 2026-02-17 audit |
| `cca59d9c` | fix: remove double-windowing in VectorizedEQProcessor to eliminate amplitude modulation artifacts |
| `218b38fb` | feat: enhance FingerprintRepository to accept configurable db_path for raw sqlite3 writes |
| `2701a400` | test: add FingerprintExtractionQueue lifecycle tests (issue #2309) |
| `8637e355` | fix: change fingerprint worker threads to daemon=True for clean process exit (issue #2247) |
| `f9d6e0f8` | fix: prevent prebuffer thread file-handle leak on shutdown (issue #2075) |

---

## 2. High-Risk Changes

| File | Domain | Risk | Commits |
|------|--------|------|---------|
| `auralis/dsp/eq/filters.py` | Audio Core | HIGH | `cca59d9c` |
| `auralis/dsp/eq/parallel_eq_processor/vectorized_processor.py` | Audio Core | HIGH | `cca59d9c` |
| `auralis/player/gapless_playback_engine.py` | Player | HIGH | `f9d6e0f8` |
| `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py` | Analysis | MEDIUM | `53cef6b4` |
| `auralis/analysis/fingerprint/fingerprint_service.py` | Analysis | MEDIUM | `12678e8c` |
| `auralis/library/repositories/track_repository.py` | Library | HIGH | `bd94fd59` |
| `auralis/library/repositories/fingerprint_repository.py` | Library | MEDIUM | `218b38fb` |
| `auralis/library/migration_manager.py` | Library | HIGH | `8adb8d0a` |
| `auralis/services/fingerprint_queue.py` | Analysis | MEDIUM | `8637e355` |
| `auralis-web/backend/routers/files.py` | Backend | HIGH | `12678e8c` |
| `auralis-web/frontend/src/hooks/websocket/useWebSocketSubscription.ts` | Frontend | MEDIUM | `12678e8c` |

---

## 3. Fix Verification (Closed/Addressed Issues)

The following known issues are **verified fixed** by this range:

| Issue | Title | Fix Commit | Status |
|-------|-------|------------|--------|
| #2443/#2446/#2448 | Double-windowing in VectorizedEQProcessor causes amplitude modulation | `cca59d9c` | ✅ FIXED — window removed pre-FFT and post-IFFT |
| #2395 | SQLAlchemy engine not disposed in MigrationManager.close() | `8adb8d0a` | ✅ FIXED — `engine.dispose()` added |
| #2297 | start_prebuffering() TOCTOU race spawns duplicate threads | `f9d6e0f8` | ✅ FIXED — `_thread_lock` + double-check pattern |
| #2242 | cleanup_missing_files offset pagination skips rows after deletion | `bd94fd59` | ✅ FIXED — ID-cursor pagination replaces OFFSET |
| #2247 | Fingerprint worker threads non-daemon prevent clean exit | `8637e355` | ✅ FIXED — `daemon=True` |
| #2075 | Prebuffer thread file-handle leak on shutdown | `f9d6e0f8` | ✅ FIXED — `_shutdown` Event + `daemon=False` + 5 s join |
| #2170 | Temp file TOCTOU in file upload handler | `12678e8c` | ✅ FIXED — `shutil.move` to permanent path before DB commit |
| #2298 | FingerprintRepository bypasses SQLAlchemy with hardcoded DB path | `218b38fb` | ⚠️ PARTIAL — path is now configurable; raw sqlite3 bypass remains |
| #2440 | useWebSocketSubscription deferred listeners accumulate | `12678e8c` | ⚠️ PARTIAL — deferred subscribe implemented; reconnect not handled (see F3) |

---

## 4. Findings

### F1: Non-daemon prebuffer thread blocks process exit if `load()` stalls beyond 5 s cleanup timeout

- **Severity**: MEDIUM
- **Changed File**: `auralis/player/gapless_playback_engine.py` (commit: `f9d6e0f8`)
- **Status**: NEW
- **Description**: `f9d6e0f8` intentionally changed the prebuffer thread from `daemon=True` to `daemon=False` to prevent mid-I/O termination. `cleanup()` now sets `_shutdown` and joins with a 5 s timeout. If the blocking `load(file_path, "target")` call stalls (slow filesystem, NFS mount, or I/O hang), `cleanup()` emits a warning after 5 s but returns — the thread is still alive and non-daemon. Python will then block indefinitely at interpreter exit waiting for the thread to finish.
- **Evidence**:
  ```python
  # gapless_playback_engine.py — cleanup()
  self._shutdown.set()
  if self.prebuffer_thread and self.prebuffer_thread.is_alive():
      self.prebuffer_thread.join(timeout=5.0)
      if self.prebuffer_thread.is_alive():
          warning("Prebuffer thread did not stop within 5s after shutdown signal")
  # ← returns here even if thread is alive; non-daemon thread now blocks exit
  ```
  The `_shutdown` event is checked **before** and **after** the load, but not **during** it — `load()` itself is a synchronous call that cannot be interrupted.
- **Impact**: On hosts with slow/hung storage, app shutdown hangs indefinitely. The old `daemon=True` would have exited cleanly (at the cost of a mid-I/O kill). A 5 s warning fires but is unactionable.
- **Suggested Fix**: After `join(timeout=5.0)` returns with the thread still alive, either force-terminate via a `concurrent.futures.Future` with a separate timeout, or convert `load()` to run in a daemon subprocess so it can be hard-cancelled. Alternatively, re-daemonize the thread concept by running the blocking I/O in an inner daemon thread while the outer non-daemon thread waits on it with a short poll interval using `_shutdown`.

---

### F2: `FingerprintService.analyze_audio` computes features at inconsistent sample rates depending on call path

- **Severity**: LOW
- **Changed File**: `auralis/analysis/fingerprint/fingerprint_service.py` (commit: `12678e8c`)
- **Status**: NEW
- **Description**: Commit `12678e8c` added `sr=22050, mono=False, duration=90.0` to the `librosa.load` call inside `analyze_audio`. However, this load is only invoked when `audio is None or sr is None`. When a caller passes pre-loaded audio directly (the `audio`/`sr` parameters), the original sample rate is used without resampling or duration capping. As a result, two calls to `analyze_audio` for the same track — one with a file path only, one with pre-loaded 44 100 Hz audio — produce fingerprints at different Nyquist cutoffs (11 025 Hz vs 22 050 Hz) with different time extents (90 s cap vs full track). These fingerprints are not directly comparable.
- **Evidence**:
  ```python
  # fingerprint_service.py
  if audio is None or sr is None:
      audio, sr = librosa.load(str(audio_path), sr=22050, mono=False, duration=90.0)
  #   ^ resampled to 22050, capped at 90 s
  # else: caller-provided audio is used as-is at original sr (e.g. 44100 Hz, full length)
  ```
- **Impact**: No current callers pass pre-loaded audio (grep confirmed), so the bug is latent. Future callers (or tests) that supply pre-loaded audio will produce fingerprints incompatible with file-loaded ones, breaking similarity search.
- **Suggested Fix**: Resample caller-supplied audio to 22 050 Hz and cap it at 90 s regardless of how audio was provided:
  ```python
  if audio is None or sr is None:
      audio, sr = librosa.load(str(audio_path), sr=22050, mono=False, duration=90.0)
  else:
      # Normalise to canonical analysis rate
      if sr != 22050:
          import librosa
          audio = librosa.resample(audio, orig_sr=sr, target_sr=22050)
          sr = 22050
      max_samples = 22050 * 90
      if audio.ndim == 1:
          audio = audio[:max_samples]
      else:
          audio = audio[..., :max_samples]
  ```

---

### F3: `useWebSocketSubscription` deferred subscriptions not re-established after WebSocket reconnect

- **Severity**: LOW
- **Changed File**: `auralis-web/frontend/src/hooks/websocket/useWebSocketSubscription.ts` (commit: `12678e8c`)
- **Status**: NEW
- **Description**: The fix correctly defers subscription for hooks that mount before the manager is ready (startup race). However, `managerReadyListeners` is cleared after the first `setWebSocketManager(manager)` call. If the connection drops and `setWebSocketManager(null)` followed by `setWebSocketManager(newManager)` is called (reconnect flow), the set is empty — no hooks re-subscribe to `newManager`. Hooks that subscribed via the deferred path are still registered on the now-defunct old manager.
- **Evidence**:
  ```typescript
  // Reconnect scenario:
  // 1. Hook mounts, manager=null → subscribeToManager added to managerReadyListeners
  // 2. setWebSocketManager(manager1) → listener fires, managerReadyListeners cleared
  // 3. disconnect → setWebSocketManager(null) → managerReadyListeners.clear() (already empty)
  // 4. reconnect → setWebSocketManager(manager2) → managerReadyListeners is empty
  //    Hook still subscribed to defunct manager1 via unsubscribeRef — receives NO messages
  ```
- **Impact**: After a reconnect, hooks that used the deferred path (mounted before initial connect) silently stop receiving WebSocket messages until the component re-mounts. Given that main player hooks mount at app startup, all player state updates would be lost after reconnect.
- **Suggested Fix**: Have `setWebSocketManager(newManager)` notify already-subscribed hooks to re-subscribe. One approach: add a `managerChangeListeners` set separate from `managerReadyListeners` that allows existing subscriptions to migrate. Alternatively, trigger a React Context refresh so all hooks see the new manager instance.

---

## 5. Cross-Layer Impact Assessment

| Change | Frontend | Backend | Engine | Status |
|--------|----------|---------|--------|--------|
| `VectorizedEQProcessor` double-windowing removed | Not affected | Not affected (EQ applied server-side) | ✅ Clean | OK |
| `filters.py` Hermitian symmetry corrected | Not affected | Not affected | EQ output changes for sub-bass bands | Acceptable — correctness fix |
| `FingerprintRepository` configurable `db_path` | Not affected | `startup.py` updated ✅ | `LibraryManager` updated ✅ | OK — consistent threaded pass-through |
| `MigrationManager.close()` disposes engine | Not affected | Called on shutdown only | N/A | OK |
| `files.py` permanent upload path | Frontend receives permanent path in response | ✅ Backend stores permanent path | N/A | OK |
| `useWebSocketSubscription` deferred subscribe | ⚠️ Reconnect not handled (F3) | Not affected | N/A | See F3 |

---

## 6. Missing Test Coverage

| Changed Code | Coverage Status |
|--------------|-----------------|
| `gapless_playback_engine.py` — new `_shutdown` checks | ✅ `test_gapless_playback_engine.py` — `TestPrebufferThreadLifecycle` added |
| `gapless_playback_engine.py` — load-stall after 5 s timeout | ❌ No test for `cleanup()` returning with thread still alive (F1 scenario) |
| `fingerprint_service.py` — `sr=22050, duration=90.0` | ❌ No test verifying behavior when pre-loaded audio at sr≠22050 is passed |
| `useWebSocketSubscription.ts` — reconnect after deferred subscribe | ❌ No test for `setWebSocketManager(null)` → `setWebSocketManager(newManager)` cycle |
| `filters.py` — Hermitian symmetry | ✅ `test_eq_hermitian_symmetry.py` added |
| `vectorized_processor.py` — no double-windowing | ✅ `test_eq_double_window_artifact.py` added |
| `track_repository.py` — ID-cursor pagination | ✅ `test_cleanup_missing_files_pagination.py` added |
| `migration_manager.py` — `engine.dispose()` | ✅ `test_migration_manager_fd_leak.py` added |
| `files.py` — permanent upload path | ✅ `test_files_api.py` updated |

---

## 7. Summary

3 new findings; no CRITICAL or HIGH issues introduced by these commits.

| Finding | Severity | Status |
|---------|----------|--------|
| F1: Non-daemon prebuffer thread blocks exit if load() stalls past 5 s | MEDIUM | NEW |
| F2: FingerprintService inconsistent sr between file-load and pre-loaded paths | LOW | NEW |
| F3: useWebSocketSubscription deferred subscriptions not re-established on reconnect | LOW | NEW |
