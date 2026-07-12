# Incremental / Delta Audit — 2026-03-01

**Auditor**: Claude Sonnet 4.6 (automated)
**Scope**: `HEAD~10..HEAD` (10 commits, 86 source files changed)
**Method**: Full diff retrieval for all high-risk domains, manual verification of all candidate findings, false-positive elimination before reporting.

---

## 1. Change Summary

| Commit | Description |
|--------|-------------|
| `0acc25a4` | fix: migrate all Color.styles.ts import sites to @/design-system tokens (#2617) |
| `d6b543ac` | fix: correct _get_default_fingerprint() frequency scale from % to 0-1 (#2612) |
| `20b0a166` | fix: prevent clipping in auto_master and fix Rust DSP float64 type mismatch |
| `b65aec91` | fix: resolve 22 test failures across 6 backend test files |
| `54b7e6a2` | Merge PR #2610: batch audit fixes #2609, #2592 |
| `7a22efe0` | fix: resolve 10 audit findings — performance, security, DSP, accessibility |
| `6a59c492` | Refactor tests and enhance coverage |
| `8ee0cad3` | fix: resolve 11 test failures in artwork and audio stream tests |
| `b2899e46` | fix: align API integration tests with actual endpoint contracts |
| `b78615a4` | fix: resolve 4 test failures — fingerprint shape, harmonic fallbacks, WAV truncation, gain smoother |

**Key themes**: Bug-fix sprint covering DSP clipping prevention, security (path disclosure, token migration), database concurrency, audio analysis correctness, and test stabilization.

---

## 2. High-Risk Changes Reviewed

| File | Domain | Assessment |
|------|--------|------------|
| `auralis/player/realtime/auto_master.py` | Player / DSP | SAFE — headroom-based gain cap and adaptive peak ceiling prevent clipping |
| `auralis/dsp/dynamics/compressor.py` | DSP | SAFE — vectorized gain reduction correct; lookahead guard fix correct |
| `auralis/dsp/eq/psychoacoustic_eq.py` | DSP | SAFE — `np.hanning` → `np.hann` deprecation fix |
| `auralis/dsp/utils/spectral.py` | DSP | SAFE — same deprecation fix |
| `auralis/dsp/utils/interpolation_helpers.py` | DSP | SAFE — same deprecation fix |
| `auralis/optimization/parallel_processor.py` | DSP | SAFE — same deprecation fix |
| `auralis/analysis/quality_assessors/base_assessor.py` | Analysis | SAFE — same deprecation fix |
| `auralis/core/processing/continuous_mode.py` | Core | SAFE — `audio.ravel()` for stereo RMS correct; empty fingerprint guard correct |
| `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py` | Analysis | SAFE — shape heuristic and frequency defaults correct |
| `auralis/analysis/fingerprint/utilities/dsp_backend.py` | Analysis | SAFE — float64 coercion for Rust FFI correct |
| `auralis/analysis/fingerprint/utilities/harmonic_ops.py` | Analysis | SAFE — per-metric try/except wrappers re-added correctly |
| `auralis/io/loaders/soundfile_loader.py` | I/O | SAFE — RIFF header truncation detection correct for WAV |
| `auralis/library/repositories/artist_repository.py` | Library | SAFE — selectinload mirrors prior get_all() fix |
| `auralis/library/repositories/track_repository.py` | Library | **BUG** — INC-01 (see below) |
| `auralis/player/queue_controller.py` | Player | SAFE — shuffle() delegation |
| `auralis-web/backend/core/audio_stream_controller.py` | Backend | SAFE — filepath disclosure patched at 4 sites |
| `auralis-web/backend/routers/artwork.py` | Backend | SAFE — ValueError added to path resolution exception tuple |
| `auralis-web/backend/routers/enhancement.py` | Backend | SAFE — CHUNK_INTERVAL fix and np.ceil chunk count correct |
| `auralis-web/backend/routers/serializers.py` | Backend | SAFE — ORM object sanitization in fallback path |
| `auralis-web/frontend/src/components/player/Player.tsx` | Frontend | SAFE — `aria-expanded` accessibility fix |
| `auralis-web/frontend/src/hooks/library/useLibraryData.ts` | Frontend | SAFE — ref-based loadMore guard correct |
| Frontend Color.styles.ts migration (53 files) | Frontend | SAFE — design token migration |

---

## 3. Findings

---

### INC-01: `session.rollback()` on IntegrityError detaches prior-flushed artists on multi-artist tracks

- **Severity**: MEDIUM
- **Changed File**: `auralis/library/repositories/track_repository.py` (commit: `54b7e6a2` / `7a22efe0`)
- **Status**: NEW → #2624
- **Description**: The fix for #2594 adds `IntegrityError` handling to artist and genre creation in `add_track()`. When a concurrent insert conflict is detected, `session.rollback()` is called and the existing record is queried as a fallback. This is correct for single-artist tracks. However, for tracks with multiple artists, `session.rollback()` reverts ALL uncommitted flushes in the session — including the successfully-flushed artists from earlier loop iterations. Those artist objects become detached from the session. Subsequent code on line 122–123 accesses `artists[0].id` (to filter album by `artist_id`) on the now-detached object, raising `DetachedInstanceError`.
- **Evidence**:
  ```python
  # track_repository.py:99-116 — for a 2-artist track:
  for artist_name in track_info.get('artists', []):
      ...
      if not artist:
          try:
              artist = Artist(name=artist_name, normalized_name=normalized)
              session.add(artist)
              session.flush()          # Artist 1: succeeds, id populated
          except IntegrityError:
              session.rollback()       # ← reverts Artist 1's flush too!
              artist = session.query(Artist)...first()
      artists.append(artist)           # artists[0] is now detached (Artist 1)

  # track_repository.py:122-123 — DetachedInstanceError here:
  if artists:
      album_filter = and_(album_filter, Album.artist_id == artists[0].id)
      #                                                   ^^^^^^^^^^^
      #                   DetachedInstanceError: instance not bound to a session
  ```
- **Impact**: `add_track()` raises `DetachedInstanceError` for any track with 2+ artists when the 2nd+ artist's concurrent INSERT collides. The track is not added to the library. Error propagates to the scanner, leaving the track unindexed. Requires concurrent scan sessions and a multi-artist track — realistic in initial full-library scans on large collections.
- **Suggested Fix**: Use `session.flush()` + `session.rollback()` scoped to a savepoint (`session.begin_nested()`) so only the failed artist insert is rolled back, not the entire transaction. Alternatively, re-query all previously-appended artists after rollback to re-attach them to the session.

---

## 4. Cross-Layer Impact

No contract breaks between layers were introduced in this range:
- Backend WebSocket error messages changed from raw exception strings to generic messages — frontend already uses the `detail` field generically; no schema change.
- `enhancement.py` CHUNK_INTERVAL fix aligns the backend calculation with `ChunkedAudioProcessor` indexing — no frontend change needed.
- `serializers.py` fallback path sanitization is transparent to API consumers.
- Frontend Color.styles.ts deletion: all 53 import sites migrated in the same commit; no runtime breakage.

---

## 5. Missing Tests

| Changed Code Path | Test Coverage Status |
|-------------------|----------------------|
| `track_repository.add_track()` multi-artist + IntegrityError (INC-01) | No test for multi-artist concurrent insert — the single-artist case is tested but not 2+ artists |
| `auto_master.py` adaptive peak ceiling | No test verifying that the adaptive ceiling fires after transient enhancement |
| `soundfile_loader.py` RIFF truncation detection | Test added in `b78615a4` (WAV only, covers new code path) |
| `useLibraryData` ref-based loadMore guard | No test for concurrent scroll events triggering duplicate loadMore |

---

## 6. False Positives Eliminated

| Candidate | Reason Eliminated |
|-----------|------------------|
| `soundfile_loader.py`: non-WAV truncation no longer detected | Pre-existing limitation — old `sf.info().frames` comparison was broken for all formats; non-WAV was never reliably detected. No regression. |
| `continuous_mode.py`: `print()` statements remain | These were present before `HEAD~10`; not introduced in this diff range. Pre-existing code quality issue. |
| `audio_fingerprint_analyzer.py`: (1, N) stereo shape heuristic | `audio.shape[0] <= 2` correctly handles mono (shape (N,)) and stereo (2, N). For (N, 2) format, shape[0]=N > 2 → num_samples=N. Correct for all realistic sample counts. |
| `dsp_backend.py`: float64 coercion affects downstream callers | `_validate_inputs` is only called within fingerprint analysis to pass audio to Rust. Return values from Rust are scalar metrics (harmonic_ratio etc.), not audio arrays. No float32 invariant violation. |
| `compressor.py`: `_calculate_gain_reduction_vectorized` knee boundary | Mask `in_knee = (levels_db > threshold - half_knee) & ~above_knee` correctly covers the soft-knee interval. `above_knee` already excludes the threshold+half_knee boundary from `in_knee`. Logic is equivalent to the scalar version. |
| `auto_master.py`: `max(max_safe_gain_db, 0.0)` when peak > 0.98 | Sets makeup_gain to 0 (no gain), leaving peak unchanged. The adaptive ceiling added afterward (`current_peak > target_peak → scale down`) catches and corrects already-hot material. Two-stage protection is correct. |

---

## Summary Table

| Finding | Severity | Status | Issue |
|---------|----------|--------|-------|
| INC-01: session.rollback() detaches artists on multi-artist tracks | MEDIUM | NEW → #2624 |
