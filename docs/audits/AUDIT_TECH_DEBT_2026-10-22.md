# Tech-Debt Audit: 2026-10-22

**Scope:** all 10 dimensions, depth `deep`, no limit, run at `44e4d433`. This is a fresh read of the current tree. About 160 commits landed since the 2026-10-21 run (`db9cc2e7..HEAD`), mostly the #5831-#5841 god-file splits plus #5763, #5764, #5795 and #5824.
**Method:** the orchestrator ran the Phase 1 greps and gates, then one subagent per dimension (max 3 concurrent). The orchestrator spot-checked TD3-07, TD6-01 and TD8-05 against the code and removed cross-dimension duplicates.
**Dedup:** checked against `gh issue list --state all` (5,613 issues, highest #5859) and today's unpublished AUDIT_ENGINE, BACKEND, FRONTEND and INTEGRATION reports. Overlaps carry a "Cross-audit overlap" line. No GitHub issues were created.

## Executive Summary

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 6 |
| LOW | 92 |
| **Total** | **98** |

The 98 come from 102 dimension findings minus four merged at the end. TD3-04 is already tracked as open #5381. TD6-06 was merged into TD2-01, TD6-11 into TD10-04, and TD10-05 into TD7-06.

By dimension:

| Dimension | Findings |
|---|---|
| Stale Markers | 4 |
| Dead Code | 13 |
| Logic Duplication | 19 |
| Magic Numbers | 13 |
| Stub Implementations | 1 |
| Test Hygiene | 9 |
| Stale Documentation | 12 |
| Backwards-Compat Cruft | 12 |
| File/Function Complexity | 11 |
| Audit-Finding Rot | 4 |

All six MEDIUMs fire the same promotion rule: duplicated logic where a fix reached only one copy.
- **TD3-01:** manual-scan and auto-scan WebSocket publishing.
- **TD3-02:** three stereo-width gates. #5108 fixed only the continuous one.
- **TD3-03:** the hand-copied 25D name list in `FingerprintGenerator`. Two of its names are stale.
- **TD3-06:** two WebSocket hooks bypass `useMessageSubscriptions`.
- **TD3-07:** `ProcessorPool.cache_key` is keyed on five attributes that no longer exist.
- **TD4-01:** `MIN_SAMPLES` has opposite short-buffer policies in the engine and the backend.

Direction against the 2026-10-21 snapshot:
- **Splits:** yesterday's splits removed most oversized Python modules (89 to 33 files over 300 LOC) and most oversized shipped TS (25 to 1).
- **Debt the splits created:**
  - About 100 test-only re-export names (TD2-01, TD8-08).
  - Twelve `NotImplementedError` mixin hooks (TD5-01). No MRO shadowing; each composed class was checked.
  - Five unused imports (TD2-13).
  - Inert test patches (TD6-04).
  - Drifted `file.py:NNN` doc anchors (TD7-04).
  - Closed split targets missing from `loc-ceilings.json` (TD9-01).
- **Gates:** the path gate is green again (exit 0; it was exit 1 yesterday). One CI step is newly red: `check_weak_assertions.py --zero`, because #5764 left three zero-assertion tests (TD6-01).

## Baseline Snapshot

Captured 2026-10-22 at `44e4d433` with the Phase 1 greps in `.claude/commands/audit-tech-debt.md`. Labels follow the #4564 metric notes.

| Metric | 2026-10-22 | 2026-10-21 | Read it as |
|---|---|---|---|
| markers, genuine (src) | 3 | 2 | Every hit is listed in the census below. `TODO(#5858)` is new today and cites an OPEN issue. `TODO(#5484)` cites an OPEN issue. `TODO(#5537)` in `py_bindings.rs:174` cites a CLOSED issue; it is still not filed separately because OPEN #5738's acceptance criterion removes it. |
| markers, genuine (tests/) | 1 | 0 | `TODO(#5851)` at `tests/backend/test_database_migrations.py:339`. #5851 is OPEN, so the marker is legitimate. |
| markers, raw (pre-filter) | 4 | 3 | Diagnostic only. The gap is the `0.xxxxxxxx` false positive in `errorTrackingMiddleware.test.ts:451`. |
| prose deferrals (non-test) | 9 | 10 | All 9 are ordinary prose. Yesterday's `continuous_dsp_ops.py` "revisit" deferral is gone. Wider greps found 4 untracked deferrals, TD1-01 to TD1-04. |
| NotImplementedError | **12** | 0 | All 12 are mixin "host must provide this" hook declarations from the #5833-#5839 splits (TD5-01). None is reachable: each composed class's MRO resolves to the host. The metric note needs updating (TD10-04). |
| type: ignore (py) | 44 | 51 | `mypy --warn-unused-ignores` flags 4 as unused, all `[attr-defined]` on `mutagen.File` (TD2-11). |
| @ts-ignore/@ts-expect-error | 10 | 10 | Unchanged composition. 0 are in shipped code. |
| 'any' non-test (ts) | 3 | 3 | The same three: `loggerMiddleware.ts:93,160` and `Text.tsx:102` (`ref as any`). |
| 'any' raw incl. tests (ts) | 493 | 496 | Trend continuity only. |
| skipped tests (py) | 31 | 35 | About 29 real decorators; the regex also matches prose (TD10-04). The hard skip and the strict xfails cite OPEN #5187 and #5191, and a fixture-wide skip cites OPEN #5685. No skip guards a closed CRITICAL/HIGH regression test. |
| skipped tests (ts) | 3 (**0 real**) | 3 (0 real) | All prose. TD10-04 covers the metric fix. |
| py files >300 LOC | **33** | 89 | The #5831-#5839 splits. None of the 33 is covered by an open issue (#5831-#5841 are all closed); they are grouped in TD9-04/05/07/08/09. Python functions over 100 LOC fell from 76 to 59, and nesting over 4 from 32 to 25 functions. |
| ts/tsx files >300 LOC | **69** | 104 | 1 shipped (`AudioPlaybackEngine.ts`, 308, TD9-02) and 68 test files. |
| allow(dead_code) (rust) | 0 | 0 | Clean. #5764 left unused Cargo dependencies and a dead `pub use` block (TD2-10), and `chunk_processor` (#5738, open). |
| sample_rate=44100 defaults | 20 | 22 | **A drift indicator, not a debt count** (#4924). The −2 is two deleted sites, `learning/reference_library.py` (`f44e3153`, #5765) and the `create_content_analyzer` factory (`d76026a4`, #5770). `base_spectrum_analyzer.py` became `spectrum_analyzer.py` (#5806), a net-0 move. **Zero new sites.** |

Marker census (every genuine hit):

| Marker | Location | Blame | Issue | State |
|---|---|---|---|---|
| TODO(#5858) | `auralis/core/analysis/target_generator.py:269` | 92fca886 2026-10-22 | #5858 | OPEN |
| TODO(#5484) | `auralis-web/backend/config/middleware/security_headers.py:96` | 254d9305 2026-09-16 | #5484 | OPEN |
| TODO(#5537) | `vendor/auralis-dsp/src/py_bindings.rs:174` | 3ef9ac77 2026-10-17 | #5537 | **CLOSED**. Covered by open #5738's acceptance criterion; retarget it or delete it with the binding. |
| TODO(#5851), tests/ | `tests/backend/test_database_migrations.py:339` | c3492d1c 2026-10-22 | #5851 | OPEN |

Other gates checked this run:
- **`_audit-validate.sh`: exit 0.** The strict scope has 0 stale refs, and the ratchet sits at 280 against a baseline of 280. The gate checks backticked paths only; the doc rot it cannot see is in TD7-01 to TD7-12.
- **`scripts/check_doc_counts.py`.** Live counts are 59 analysis files, 20 routers, 709 test files, 7,112 test functions, 18 docs topic dirs, 12 repositories and schema v23. It reports "current", but it does not validate the analysis-file or test-subdir counts, which are stale in CLAUDE.md (TD7-06).
- **Baseline files.** `pytest-baseline.json` has 80 entries and `test-baseline.json` has 96, with 0 phantom entries in either. Yesterday's figures were 127 and 101.
- **`scripts/check_weak_assertions.py --zero`: exit 1** at HEAD (TD6-01). Both assertion baselines also carry stale entries.
- **`scripts/check_loc_ratchet.py --list`.** No ceiling points at a missing file. Three closed split targets are missing from the list (TD9-01), and 83 of 85 ceilings are the blanket 299 (TD9-03).
- **`scripts/sync_agent_commands.sh --check`.** The `.agents/` mirror matches `.claude/commands`. Both carry uncommitted working-tree edits from another session, and no finding sits on an edited line.

## Top 10 Quick Wins

| # | ID | Effort | Why now |
|---|---|---|---|
| 1 | TD6-01 | trivial | `check_weak_assertions.py --zero` fails a step in `backend-tests.yml` at HEAD. Add assertions to the three `test_fingerprint_{nan,inf,empty}_audio_no_process_crash` tests and prune the stale baseline entries. |
| 2 | TD3-03 | trivial | Replace `_record_to_dict`'s seven literal lists with `DIMENSION_NAMES`. This fixes the 23-vs-25-key cache-hit shape (MEDIUM; also INT-F6-7). |
| 3 | TD4-01 | trivial | Point the backend `audio_processing_pipeline.py` at the engine's `MIN_SAMPLES` pass-through policy and delete its second constant (MEDIUM). |
| 4 | TD3-07 | small | Build `ProcessorPool.cache_key` from `processor_cache_key.hash_config` and delete the five dead `getattr`s (MEDIUM). |
| 5 | TD2-13 + TD2-11 | trivial | Delete five unused imports left by the splits and four unused `type: ignore[attr-defined]` comments on `mutagen.File`. |
| 6 | TD2-10 | trivial | Drop the unused `realfft`/`criterion` dependencies, the 12-name `pub use` block and the unused `sample_rate` parameter in the Rust crate. |
| 7 | TD6-04 + TD6-05 | trivial | Delete inert test patches: four on `get_processor_factory` and one on `AVAILABLE_PRESETS`. They give false confidence. |
| 8 | TD7-09 | trivial | `index.tsx:31` shows `1.0.0-beta.13` to users. Read the version from the build, not a literal. |
| 9 | TD10-03 | trivial | The dedup `--limit 6000` has 141 issues of headroom left, and a truncated dump fails silently. Raise the limit, or derive it from the highest issue number. |
| 10 | TD9-01 | small | Add `audio_stream_controller.py`, `stream_enhanced.py` and `mastering_branches/continuous.py` (closed split targets now at 300-303 LOC) to `loc-ceilings.json`. |

## Top 5 Medium Investments

| # | IDs | Effort | Consolidation |
|---|---|---|---|
| 1 | TD3-01 | small-medium | One `scan_events` module for the manual and auto scan paths: progress callback, fingerprint enqueue and the `scan_complete` payload. It removes a drifted copy and settles `files_processed` semantics (route that to /audit-backend). |
| 2 | TD3-02 | small-medium | Make `StereoWidthProcessor.apply_stereo_width_safe` the one implementation, carrying the #5108 `smooth_gate` knee. `AdaptiveMode` and `ContinuousDSPOpsMixin` call it, and the hard `> 0.8` switch and the `print()`s go. |
| 3 | TD2-01 + TD8-08 + TD2-09 | medium | Remove the about 100 split-created re-export names and the unused package barrels. Retarget the ~49 test files to the defining modules first. |
| 4 | TD3-12 + TD9-06 | medium | Extract a `StreamSession` context manager shared by `stream_enhanced`, `stream_seek` and `stream_normal`. It collapses the five 190-264 LOC functions and about 110 duplicated lifecycle lines. |
| 5 | TD3-09 + TD3-10 | medium | Add `BaseRepository` helpers for get-one-and-expunge and write-with-rollback-default. They absorb 13 read sites and 20 write paths, and define the missing selectinload option tuples once at module scope. |

## Deferred

| Finding | Gated on |
|---|---|
| TD2-04 (HybridProcessor dynamics facade) | Open #5098 proposes wiring dynamics back in. Decide wire-or-delete there first. |
| TD8-05 (queue-entry path key spellings) | /audit-engine has to confirm whether the gapless prebuffer and previous-track readers are reachable with production `filepath` entries (a possible live defect) before the key is normalized. |
| TD8-07 (vestigial `mastering_profile`/`preferred_profile` columns) | Schema scope of open #5755. The v23 migration comment assigns them there, but #5755's body does not cover them. |
| TD2-10, `chunk_processor` part | Open #5738 (dead `process_chunks`), which also removes the closed-issue `TODO(#5537)`. |
| TD9-06 | Open #5481 (function census) defers these functions to #5032, which is closed. Retarget #5481, or fold the work into TD3-12. |

## HIGH findings (0)
None. No promotion trigger fired: every DSP copy that mutates audio copies first, no stub is reachable from a route or the player, and no skip guards a closed CRITICAL/HIGH regression test.

## MEDIUM findings (6)

### Dimension 3: Logic Duplication

#### TD3-01: Manual and auto library-scan WebSocket publishing are two copies that have drifted
- **Severity**: MEDIUM
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/services/auto_scan_events.py:21-129` vs `auralis-web/backend/routers/library_scan_events.py:25-191`
- **Status**: NEW
- **Age**: ea535fbd 2026-10-22 (#5837 part) and f033c8b4 2026-10-22 (#5831): both files were born in the same-day god-file splits, each carrying its original's drift
- **Effort**: small
- **Description**: `make_progress_callback`, `enqueue_added_for_fingerprinting` and the `scan_complete` payload builder exist twice with the same names. Fixes landed in one copy only, so the two scan paths now disagree on what the frontend sees.
- **Evidence**:
  - Progress bridge. Manual wraps its body in `try/except` (#3864) but fires `asyncio.run_coroutine_threadsafe(broadcast_typed(...), loop)` and never inspects the returned future, so a failed `scan_progress`/`library_scan_started` broadcast is dropped silently. Auto schedules via `loop.create_task(...).add_done_callback(log_task_exception)` (#3512) and passes `suppress_errors=True`.
  - `current_file`. Auto: `data.get('current_file') or data.get('file') or data.get('directory')`. Manual: `progress_data.get('current_file') or progress_data.get('file')` (no `directory` fallback).
  - `scan_complete`. Manual builds `"files_processed": result.files_processed or result.files_found`; auto builds `scan_result.files_processed if scan_result else 0` (no `or files_found`). The manual docstring claims "Field shape matches ... the auto-scanner path (fixes #3502)" but that is no longer true for `files_processed`.
  - Fingerprint enqueue. Both do `get_fingerprint_queue()` plus `sum(1 for t in added if fp_queue.enqueue(t.id))` offloaded to `asyncio.to_thread`, with different guard shapes (`(scan_result, added_tracks, fingerprint_queue)` vs `added_tracks`) and different log text.
- **Impact**: A scan-progress or payload fix has to be made twice and has already been made once. The manual-scan UI can lose a progress/start frame silently where auto-scan logs it.
- **Siblings**: `services/library_auto_scanner.py` (caller of the auto copy), `routers/library_scan.py` (caller of the manual copy), `websocket/outbound_messages.py::ScanCompletePayload`.
- **Related**: `/audit-backend` should decide which `files_processed` semantics is right (`or files_found` looks like the intended fallback for the streaming scan).
- **Suggested Fix**: Keep one module (e.g. `services/auto_scan_events.py` renamed `scan_events.py`) exposing `make_progress_callback(schedule, connection_manager, fallback_dirs)`, `enqueue_added_for_fingerprinting(added_tracks)` and `scan_complete_payload(result)`. The auto path injects `loop.call_soon_threadsafe` plus `log_task_exception`, and the manual path injects `run_coroutine_threadsafe` plus a `.add_done_callback` that logs. Delete the manual copies from `library_scan_events.py`.

#### TD3-02: Stereo-width loudness gating exists three times; the #5108 smooth-gate fix reached only the continuous copy
- **Severity**: MEDIUM
- **Dimension**: Logic Duplication
- **Location**: `auralis/core/processing/adaptive_mode.py:199-228`, `auralis/core/processing/base/stereo_width_processor.py:49-109`, `auralis/core/processing/continuous_dsp_ops.py:118-181`
- **Status**: NEW
- **Age**: 63f5b1f2 2026-08-14 (#5108, continuous only); adaptive copy last touched a28f2daa 2026-10-22
- **Effort**: small
- **Description**: `StereoWidthProcessor`'s docstring says it "consolidates 70% duplicate logic between adaptive and continuous modes", but continuous never uses it (its only caller is `AdaptiveMode`). `AdaptiveMode._apply_stereo_width` then repeats the helper's own clamp inline before calling it, and `ContinuousDSPOpsMixin._apply_stereo_width` is a third implementation.
- **Evidence**:
  ```python
  # adaptive_mode.py:215-220  (hard gate, input_level is a linear 0..1 reading, print() not debug())
  if spectrum_position.input_level > 0.8 and target_width > WIDTH_FACTOR_UNITY:
      max_width_increase = 0.6
      target_width = min(target_width, WIDTH_FACTOR_UNITY + max_width_increase)
      print(f"[Stereo Width] Limited expansion for loud material: ...")
  # stereo_width_processor.py:90-94  (same clamp again, gated on peak_db > 3.0)
  if peak_db > 3.0 and target_width > WIDTH_FACTOR_UNITY:
      max_width_increase = 0.6
      target_width = min(target_width, WIDTH_FACTOR_UNITY + max_width_increase)
  # continuous_dsp_ops.py:158-163  (#5108: ramp the widening away across a peak knee)
  gate = smooth_gate(pre_peak_db, WIDTH_PEAK_KNEE_START, WIDTH_PEAK_KNEE_END)
  target_width = target_width + (WIDTH_FACTOR_UNITY - target_width) * gate
  ```
  The #5108 commit message describes the hard peak switch as "an audible stereo-image difference from an inaudible input difference". `AdaptiveMode` still has the hard `> 0.8` switch, and the helper's `peak_db > 3.0` branch cannot fire for normalised float audio. The helper's `"conservative"` mode has no caller. The helper also keeps a `abs(target_width - 1) > 0.1` dead-zone that the continuous copy lacks, so the two paths do not widen identically. The `audio.ndim == 2 and audio.shape[1] == 2` stereo test is re-spelled inline at `continuous_stages.py:198` and `stage_snapshot.py:68,93` instead of `StereoWidthProcessor.validate_stereo`.
- **Impact**: A fix to stereo-widening safety has to be made in three places and was made in one. `AdaptiveMode` is still constructed (`hybrid_setup.py:89`) and reachable through HybridProcessor adaptive/hybrid mode.
- **Siblings**: the three `ndim == 2 and shape[1] == 2` stereo checks above; `print()` calls at `adaptive_mode.py:99,104,125,220` and `base/processing_logger.py` (output channel is a separate concern).
- **Related**: #4503 (closed, the width-factor/decorrelation axis fix, applied to all three). Owning audit for the behavioural difference: `/audit-engine`.
- **Suggested Fix**: Make `StereoWidthProcessor.apply_stereo_width_safe` the single implementation carrying the `smooth_gate` knee and `adjust_stereo_width_multiband` call. Have both `AdaptiveMode._apply_stereo_width` and `ContinuousDSPOpsMixin._apply_stereo_width` call it, delete the `"conservative"` branch and the inline clamp, and use `validate_stereo` at the other two stereo checks.

#### TD3-03: `FingerprintGenerator._record_to_dict` hand-copies the 25 dimension names and two of them are already stale
- **Severity**: MEDIUM
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/analysis/fingerprint_generator.py:325-375`
- **Status**: NEW (residual sibling of closed #5786, which derived five other lists from `DIMENSION_NAMES` but did not cover this one)
- **Age**: 8a8bd5a4 2026-02-21 (file move); the stale names predate it (`TrackFingerprint` renamed to `tempo_bpm` / `loudness_variation_std` in 1ee77eba 2025-10-31)
- **Effort**: trivial
- **Description**: The method lists the 25 columns in seven literal lists and guards each with `hasattr`. Two names no longer exist on `TrackFingerprint`, so the guard silently drops them.
- **Evidence**:
  ```python
  for field in ['tempo', 'rhythm_stability', 'transient_density', 'silence_ratio']:        # column is tempo_bpm
  for field in ['dynamic_range_variation', 'loudness_variation', 'peak_consistency']:      # column is loudness_variation_std
      if hasattr(fp_record, field): fingerprint_dict[field] = getattr(fp_record, field)
  ```
  `auralis/library/models/fingerprint.py:55,72` define `tempo_bpm` and `loudness_variation_std`. A DB cache hit therefore returns 23 keys, while a fresh generation returns 25. The only caller (`FingerprintQueue._worker_loop`, `fingerprint_queue.py:220`) checks truthiness only, so nothing visibly breaks today.
- **Impact**: This is the textbook cost of a hand-copied schema list: drift with no failing test. Any future consumer of `get_or_generate()` receives different shapes on cache hit versus miss.
- **Siblings**: `routers/albums_fingerprint.py:60-87` (`db_to_api` column list, needs the rename map but should iterate `DIMENSION_NAMES`), `library/repositories/fingerprint_upsert_mixin.py:119-150` (25-keyword signature plus dict literal), `core/mastering_notch_context.py:48` (band subset, legitimate). Separately, the same module competes with `auralis/services/fingerprint_extractor.py` as a second fingerprint producer and DB writer: `FingerprintGenerator` stores via `repo.add` and has no file-size cap or sidecar write, `FingerprintExtractor` stores via `upsert`, caps at `MAX_FINGERPRINT_FILE_SIZE_MB = 300` and writes the `.25d`. They share only `compute_windowed_fingerprint` (#5531).
- **Related**: #5786 (closed; this site missed), #5531 (closed; converged the compute path only).
- **Suggested Fix**: Replace the body with `{name: getattr(fp_record, name) for name in DIMENSION_NAMES}` (import from `auralis/analysis/fingerprint/schema.py`). Optionally make `TrackFingerprint.to_dict()`'s flat variant the single serialiser.
- **Cross-audit overlap**: INT-F6-7 in AUDIT_INTEGRATION_2026-10-22.md reports the same 23-key dict as a correctness defect; publish once, with this finding's `DIMENSION_NAMES` consolidation as the fix.

#### TD3-06: Three WebSocket hooks hand-roll subscribe/unsubscribe next to `useMessageSubscriptions`, the churn-free implementation
- **Severity**: MEDIUM
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/frontend/src/components/playlist/usePlaylistWebSocket.ts:34-86`; `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:92-262`; reference implementation `auralis-web/frontend/src/hooks/websocket/useWebSocketMessages.ts:41-75`
- **Status**: NEW
- **Age**: usePlaylistWebSocket 660f6569 2026-05-26; usePlayerStateSync 8e7eb193 2026-10-22
- **Effort**: small
- **Description**: `useMessageSubscriptions` documents itself as "the single implementation of the subscription lifecycle" (#4668, #5621): ref-held handlers, order-independent type key, an effect depending only on `subscribe` plus the key. Two hooks still call `subscribe()` per type and unsubscribe by hand.
- **Evidence**:
  - `usePlaylistWebSocket` declares `}, [subscribe, onPlaylistCreated, onPlaylistUpdated, onPlaylistDeleted, onPlaylistsRefresh]);`. It tears down and rebuilds three WS subscriptions whenever a caller passes a fresh callback identity, which is precisely the churn #4668 removed from the shared hook. It also emits a `console.log` on every re-subscribe.
  - `usePlayerStateSync` has eight `subscribe(...)` calls (`player_state`, `position_changed`, `playback_started/resumed/paused/stopped`, `volume_changed`, `track_changed`) and an 8-line manual cleanup block (`unsubscribe?.(); unsubscribePosition?.(); ...`). It also repeats the seq-watermark guard five times (`usePlayerStateSync.ts:106,145,160,188,212`: `if (data.seq < lastSeen*Ref.current) return; lastSeen*Ref.current = data.seq`).
- **Impact**: A fix to subscription lifecycle (strict-mode, reconnect) lands in one hook. The playlist hook's resubscribe loop is the exact bug class the shared hook closed.
- **Siblings**: `useScanProgress.ts:238` and `useArtworkUpdates.ts:93` also call `subscribe` directly but use a deliberate module-level refcount (single global subscription, #3575) and are not copies.
- **Related**: `/audit-frontend` Hook-missing-cleanup sibling row.
- **Suggested Fix**: Convert `usePlaylistWebSocket` and `usePlayerStateSync` to `useMessageSubscriptions(subscribe, { type: handler, ... })` (it already accepts a bare `subscribe` for hooks handed a context value). Extract `acceptIfNewer(ref, seq)` for the five watermark checks.
- **Cross-audit overlap**: HK-07 in AUDIT_FRONTEND_2026-10-22.md covers the same two hooks; publish once.

#### TD3-07: `ProcessorPool.cache_key` reads five config attributes that no longer exist, next to the content-hash key `ProcessorFactory` uses
- **Severity**: MEDIUM
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/core/processor_pool.py:48-77` vs `auralis-web/backend/core/processor_cache_key.py:100-120` (`hash_config`)
- **Status**: NEW
- **Age**: bc533e03 2026-09-14 (licence-header commit, the key logic is #3528 era); attribute removals in #5302
- **Effort**: small
- **Description**: The job engine's processor pool and the streaming `ProcessorFactory` cache `HybridProcessor` instances under two different key schemes. The pool hand-picks `AdaptiveConfig` attributes (`eq_gains`, `compressor`, `target_lufs`, `gain`, `genre_override`) via `getattr(..., None)`. `AdaptiveConfig` (`core/config/settings.py:36-62`) has none of them since #5302 and the engine-side `job_config.py:46-51` says the pipeline never reads them.
- **Evidence**: `repr(getattr(adaptive, "eq_gains", None)) if adaptive else ""` and four siblings in `processor_pool.py:71-75` always yield `'None'`. The factory side hashes `json.dumps(config.to_dict(), sort_keys=True)`, which covers `fft_size`, `max_length`, `adaptation_strength`, `enable_genre_detection`, `chunk_size_ms`, `latency_budget_ms`. The pool key covers none of those six. Anyone changing `adaptation_strength` on a job config would get a pooled processor built for a different value. Today `job_config.py` only sets the sample rate and mode, so there is no live wrong hit.
- **Impact**: The #3528 fix ("hash the settings that matter") was frozen to a field list that went stale; the sibling derives the key from the config and cannot go stale. The next job-level knob will be silently excluded from the key.
- **Siblings**: `mastering_target_service._get_cache_key`, `fingerprint_storage._get_cache_key` (different domains, no overlap).
- **Related**: owning audit `/audit-backend`; dead-attribute reads also qualify for Dim 2 (Dead Code).
- **Suggested Fix**: Make `ProcessorPool.cache_key` return `f"{mode}|{hash_config(config)}"` using `processor_cache_key.hash_config`, and delete the five dead `getattr`s.
- **Orchestrator spot-check**: confirmed `processor_pool.py:71-75` still `getattr`s `eq_gains`/`compressor`/`target_lufs`/... on `config.adaptive`.

### Dimension 4: Magic Numbers

#### TD4-01: `MIN_SAMPLES = 1024` is defined twice with opposite policies; the backend copy still raises where the engine copy was fixed
- **Severity**: MEDIUM
- **Dimension**: Magic Numbers
- **Location**: `auralis-web/backend/core/audio_processing_pipeline.py:25,86-90` and `auralis/core/hybrid_stage_dispatch.py:36,81-87`
- **Status**: NEW (related open #5191 covers only the engine copy's ordering)
- **Age**: backend copy `be9ded4e` 2025-12-16; engine copy moved by `22d0228c` 2026-09-16 (#5463), policy change #4520
- **Effort**: trivial
- **Description**: The same "minimum DSP buffer" constant is typed in both layers. The engine's docstring (`hybrid_stage_dispatch.py:52-66`) records that the `raise ValueError` for short buffers "broke the pipeline's core invariant `len(output) == len(input)`" and was replaced by return-unprocessed. `AudioProcessingPipeline.validate_audio` (the per-chunk entry used by `chunk_render.py:236`, and documented as also serving `RealtimeProcessor.process_chunk`) still raises, with a stale rationale ("prevents Rust FFT/DSP panics") the engine says is fixed at the source. One copy got the bug fix, the other did not.
- **Evidence**: `if audio.shape[0] < MIN_SAMPLES: raise ValueError(...)` (backend) vs `warning(...); return target_audio, target_audio.copy()` (engine); the backend message also hardcodes `/44100*1000 ... at 44.1kHz` (`:89`).
- **Impact**: A sub-23 ms buffer fails the stream with a ValueError in the backend but passes through in the engine; changing the threshold in one place silently desyncs the other. Reachable only for buffers under 1024 samples (tiny tracks / realtime tail), so latent, not live.
- **Siblings**: `audio_processing_pipeline.py:89` hardcoded `44100` in a message; engine message uses `processor.config.internal_sample_rate` correctly.
- **Related**: #5191 (engine ordering), `/audit-backend` for the raise-vs-passthrough behavior itself
- **Suggested Fix**: Export `MIN_SAMPLES` from `hybrid_stage_dispatch.py` (or `auralis/core/config/`) and import it in the backend; make `validate_audio` return short audio unprocessed like the engine, or delete the backend guard since the engine handles it. Compute the ms in the message from the real sample rate.

## LOW findings (92)

### Dimension 1: Stale Markers

#### TD1-01: Dead TIER2_MAX_TRACKS constant carries an untracked "separate follow-up" deferral
- **Severity**: LOW
- **Dimension**: Stale Markers
- **Location**: `auralis-web/backend/cache/models.py:42-49`
- **Status**: NEW
- **Age**: ba3f628c 2026-09-14 (comment); constant older
- **Effort**: trivial
- **Description**: `TIER2_MAX_TRACKS = 2  # Keep last 2 tracks fully cached` is never read, and the NOTE above it says the count-based eviction policy "isn't actually implemented" and was "Flagged as a separate follow-up". No issue is cited and I found no open or closed issue for it (#4793, cited as "sibling", is closed). Meanwhile `cache/manager.py:90-92` states the opposite stance as settled: "Purely size-driven (TIER2_MAX_SIZE_MB) — TIER2_MAX_TRACKS is not a separate eviction trigger". Two comments disagree on whether this is pending work, and a constant that reads as live config is exported through `cache/__init__.py`. A prose deferral like this is exactly what CLAUDE.md principle 5 says is invisible to a marker sweep.
- **Evidence**: `grep -rn TIER2_MAX_TRACKS auralis auralis-web/backend tests` returns only the definition (`models.py:49`), the `manager.py:58` import, the `cache/__init__.py:30,46` re-export, and the `manager.py:91` docstring mention. No reader and no test.
- **Impact**: A reader trusting the constant name believes a 2-track cap exists; the "follow-up" invites someone to implement a policy the manager docstring has already declared out. Dead exports also widen the surface of `cache/`.
- **Siblings**: none found (the other `TIER*` constants are all read).
- **Related**: #4793 (closed, size accounting). Dim 2 may also list the dead constant; merge there if it is reported.
- **Suggested Fix**: Delete `TIER2_MAX_TRACKS` from `models.py`, the `manager.py` import and the two `cache/__init__.py` lines, drop the NOTE, and reduce the `manager.py` docstring sentence to "size-driven (TIER2_MAX_SIZE_MB)". If a count cap is wanted, file an issue and write `# TODO(#NNNN)` instead.

#### TD1-02: "Consolidate the three stream-teardown sites" is an untracked follow-up
- **Severity**: LOW
- **Dimension**: Stale Markers
- **Location**: `auralis-web/backend/ws_handlers/playback_control.py:72-87` (siblings: `playback_commands.py:110-136`, `connection.py:208-262`)
- **Status**: NEW
- **Age**: e99a58eb 2026-08-14
- **Effort**: medium
- **Description**: The comment says "Consolidating all three teardown sites behind one shared module is a reasonable follow-up, but it is a behaviour change for this handler and is out of scope for a consistency fix." It names no issue. The three sites (`_cancel_prior_task`, `handle_stop`, `teardown_connection`) each re-express "pop task, set the chunk cancel token, cancel, await" with small deliberate differences (which registries are popped, whether `chunk_cancel_events` is `pop`ped or `get`ted, lock-split versus single block), and each carries a comment explaining why it differs from the others. Three hand-synced copies of safety-critical cancel ordering have already needed #4815 applied at each site.
- **Evidence**: `playback_control.py:85-87` quoted above; `connection.py:234-241` ("deliberately a lock-split variant of the teardown that playback_commands._cancel_prior_task expresses in one block"); `playback_commands.py:126-136` (#4815 cancel-token sequence repeated).
- **Impact**: The next teardown fix (a new per-ws registry, as #4364/#4742/#4815 each added) has to be applied three times; a miss leaks a per-connection entry or an in-flight DSP thread.
- **Siblings**: the three sites above; Dim 3 (Logic Duplication) should own the duplication analysis.
- **Related**: #4704, #4815, #4364, #5319 (all closed); `/audit-concurrency` for any ordering concern.
- **Suggested Fix**: File one issue for "single `cancel_stream(ws_id, state, *, keep_settings, ...)` helper in `ws_handlers/` used by all three sites" and change the comment to `# TODO(#NNNN): ...`; or, if the divergence is judged permanent, delete the "reasonable follow-up" sentence and keep only the reasons.

#### TD1-03: "Rename standardizedAPIClient.ts" is an untracked mechanical follow-up
- **Severity**: LOW
- **Dimension**: Stale Markers
- **Location**: `auralis-web/frontend/src/services/api/standardizedAPIClient.ts:1-25`
- **Status**: NEW
- **Age**: a5f0a9d3 2026-08-20
- **Effort**: small
- **Description**: The header says the file now holds only `CacheStats`/`CacheHealth` types and their two shape guards (112 lines, zero `API_BASE_URL`, no client), that it "keeps its name because six modules import" from the path, and that "Renaming it to match its contents is a mechanical follow-up, not part of the retirement" (#4693, closed). No issue tracks the rename, so the misleading name has stood for two months. The wrong name has leaked: `vite-env.d.ts:5` still says `VITE_API_URL` overrides "API_BASE_URL in config/api.ts and standardizedAPIClient", and `config/api.ts`, `api/responseGuards.ts`, `utils/apiRequest.ts` and `StatCards.tsx` also mention the path.
- **Evidence**: importers of the path: `store/slices/cacheSlice.ts`, `store/slices/__tests__/{cacheSlice,deterministic-timestamps}.test.ts`, `services/api/__tests__/{cacheShapeGuards,responseGuards.any}.test.ts`, `StatCards.tsx`; 12 files reference the name in total.
- **Impact**: A name promising an HTTP client sends readers (and audits: `vite-env.d.ts` is already wrong) to a file with no client in it.
- **Siblings**: the stale `vite-env.d.ts:5` comment (route to Dim 7 if it is reported there).
- **Related**: #4693 (closed, retired the client).
- **Suggested Fix**: `git mv` to `services/api/cacheShapeGuards.ts`, update the importers (a sed on the import path), fix the `vite-env.d.ts` sentence, and delete the "keeps its name" paragraph.

#### TD1-04: Bundled-FFmpeg deferral cites an audit ID, not an issue
- **Severity**: LOW
- **Dimension**: Stale Markers
- **Location**: `auralis/io/loaders/ffmpeg_probe.py:23-34`
- **Status**: NEW
- **Age**: 98ac7615 2026-07-18 (written for #4344; moved to this file by 0d2efc30 on 2026-10-22, which is why blame shows today)
- **Effort**: trivial
- **Description**: The comment records "Bundling a pinned FFmpeg build was considered (tracked alongside SEC-M2) but deferred ... a version floor + warning is the interim mitigation until (or instead of) bundling." `SEC-M2` is a finding ID in `docs/audits/AUDIT_SECURITY_2026-07-12.md` (it is about unpinned Python requirements, not FFmpeg; the FFmpeg item there is SEC-M3), not a GitHub issue, and #4344 is closed with the warning-only fix. The bundling decision is therefore tracked nowhere that a `TODO(#NNNN)` sweep can see, and "until (or instead of)" leaves it open whether the deferral is live.
- **Evidence**: lines 30-33 quoted above; `grep` of issues.json for ffmpeg + bundl/pinned/minimum finds only closed #4344, #4117, #3672.
- **Impact**: A desktop app that decodes untrusted media with the ambient system binary has an undocumented open product decision; the comment points a reader at the wrong audit finding.
- **Siblings**: none.
- **Related**: #4344 (closed); `/audit-security` owns whether the ambient binary is acceptable.
- **Suggested Fix**: Decide: either file an issue and write `# TODO(#NNNN): bundle a pinned FFmpeg` (correcting SEC-M2 to SEC-M3), or reword to a settled decision ("not bundled; warn below 4.0") and delete "tracked alongside SEC-M2" and "until (or instead of)".

### Dimension 2: Dead Code

#### TD2-01: Router-split re-export shims keep ~100 names alive that no production module imports
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/backend/routers/{player,enhancement,artwork,metadata,playlists,similarity,files,library_scan,albums,processing_api}.py` (the `# noqa: F401` import blocks); `auralis-web/backend/cache/manager.py:41-60`; `auralis/io/loaders/ffmpeg_loader.py:25-45`
- **Status**: NEW
- **Age**: f033c8b4 2026-10-22 (#5831); ffmpeg_loader split same day
- **Effort**: medium (tests must be retargeted at the defining modules first)
- **Description**: #5831 split ten router modules and kept every moved name importable from the old module ("re-export the moved names", commit message). Desktop-only, single-client: nothing outside `tests/` consumes these modules by name, and `config/routes.py` imports only `create_*_router` factories. An AST scan of every `noqa: F401` import block that is not itself used in the file body found 102 re-exported names with no non-test importer (no `from routers.X import n`, no `routers.X.n`, no `<module>.n` anywhere in `auralis*/`, `scripts/`, `desktop/`). 25 of them are referenced by no test either (the shim is the only place that lists them besides their defining module). The remaining ~60 are reached only because tests do `from routers import player as player_router` / `monkeypatch.setattr(module, "_get_x", ...)` through the shim. This is the same pattern #5775/#5827 just removed for `chunked_processor`/`adaptive`/`unified_loader`, regrown one commit later, now spread over 12 modules and 20+ shim blocks. The brief's named targets confirm: `cache/manager.py` (8 names; `CHUNK_INTERVAL`, `chunk_for_position`, `content_chunk_count`, `TIER2_MAX_TRACKS` have no importer at all) and `routers/enhancement.py` (11 names, 5 referenced nowhere) have **no** non-test importer.
- **Evidence**: names re-exported with zero references anywhere outside the shim and the defining module:
  - `enhancement.py`: `_maybe_prewarm_upcoming_chunks`, `_track_is_live_streaming`, `_get_streamlined_cache`, `_get_player_state_manager`, `_persist_enhancement_setting`
  - `similarity.py`: `_with_similarity_error_handling`, `_get_graph_builder_getter`, `_get_repository_factory_getter`, `_get_similarity_system_getter`, `_graph_builder_getter`, `_unavailable`
  - `metadata.py`: `BatchMetadataResultItem`, `_METADATA_FIELD_TO_COLUMN`, `_validate_track_filepath`; `player.py`: `_get_player_state_manager`, `AddTracksToQueueRequest`, `RepeatModeRequest`; `artwork.py`: `_THUMB_GUARD`, `_thumb_render_lock`; `files.py`: `UploadResultItem`, `_get_repos_provider`; `playlists.py`: `MAX_PLAYLIST_DESCRIPTION`; `cache/manager.py`: `TIER2_MAX_TRACKS`; `ffmpeg_loader.py`: `_PROTOCOL_WHITELIST_ARGS`, `FFMPEG_TERMINATE_GRACE_S`
  - `routers/player.py:30-48` re-exports 18 names from `player_deps`/`player_models`; the only users are tests that reach them as `player_router._get_playback_service` (`tests/integration/test_phase4_player_workflow.py:370`).
- **Impact**: Every future move of a helper has to keep two import paths alive or break a test patch target; tests patching the shim instead of the defining module pass vacuously when the code under test imports from the defining module (the exact failure mode noted for `chunked_processor`).
- **Siblings**: counts per shim file (no-prod-importer / referenced-nowhere): player 18/3, similarity 14/6, artwork 13/2, enhancement 11/5, metadata 11/3, playlists 9/1, ffmpeg_loader 9/2, cache/manager 8/1, files 5/2, processing_api 2/0, albums 1/0, library_scan 1/0.
- **Related**: #5775, #5827 (closed, same pattern); #5831 (closed, introduced it)
- **Suggested Fix**: Repoint the ~60 test references at the defining sibling modules (`player_deps`, `enhancement_prewarm`, `albums_models`, ...), then delete the `noqa: F401` blocks, leaving only names the shim body itself uses. Do the 25 zero-reference names first; they need no test edits.
- **Merge note**: absorbs Dim 6 TD6-06 (86 re-exported names on the player, playlists, metadata, artwork, enhancement, similarity and files facades; ~63 are referenced only from ~49 test files, so the fix retargets those tests to the defining module before deleting the blocks). TD8-08 lists the split-created re-exports outside these files.

#### TD2-02: Production methods and functions whose only callers are tests (about 580 lines)
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: see Evidence table
- **Status**: NEW
- **Age**: 2025-10 to 2025-12 for most (`jump_to_track`/`set_track_by_index` `a8687a0c` 2025-12-05; `get_recommendation_for_track`, `extract_batch` older)
- **Effort**: medium (each deletion takes its test with it; no behaviour change)
- **Description**: Per-name `rg -w` over `auralis/`, `auralis-web/backend/`, `auralis-web/frontend/src`, `desktop/`, `scripts/` finds no call site outside tests. These survived yesterday's #5771-#5774 sweeps, which deleted the zero-reference methods but left the test-pinned ones (and #5774's own list of "test-only" `get_or_create_from_config` / `cleanup_track` / `cleanup_track_chunks` is still present). The largest is `NavigationService.jump_to_track` (83 lines, 22 test hits); it is the only emitter of the `'jumped'` action that `types/ws/player.ts:172` still advertises, so deleting it also lets the TS union and any `'jumped'` handling shrink.
- **Evidence** (symbol, size, number of test hits):
  - `auralis-web/backend/services/navigation_service.py:259` `jump_to_track` 83L, 22; `services/recommendation_service.py:160` `get_recommendation_for_track` 31L, 11
  - `auralis-web/backend/core/processor_factory.py:253` `get_or_create_from_config` 34L ("CLI tools, batch processing" — none exist), 1 file; `core/processor_maintenance.py:81` `cleanup_track` 28L, 1 file; `:119` `get_statistics` 14L, 1 file; `core/encoding/wav_encoder.py:261` `cleanup_track_chunks` 16L, 3 files
  - `auralis-web/backend/analysis/fingerprint_queue.py:150` `is_queued`; `cache/recommendations_mixin.py:100` `clear_mastering_recommendations`; `core/chunk_render.py:95` `reset_chunk_levels`; `core/seekable_source.py:196` `release_idle`
  - `auralis/player/components/queue_navigation.py:171` `set_track_by_index` 15L; `components/queue_manager.py:141` `remove_tracks` 20L; `gapless_prebuffer.py:169,175` `has_prebuffered_track`, `get_prebuffered_track`; `playback_controller.py:304` `is_stopped`; `queue_controller.py:197` `is_queue_empty`; `audio_file_manager.py:203` `has_reference`
  - `auralis/services/fingerprint_extractor.py:237` `extract_batch` 45L; `services/artwork_service.py:317` `fetch_album_artwork` 24L
  - `auralis/analysis/fingerprint/rust_fingerprint.py:118` `prepare_rust_audio` 26L (the docstring at `:157` tells callers to use it; the one production function in the file builds the array inline); `fingerprint/normalizer.py:215` `denormalize` 29L; `mastering_fingerprint.py:211` `classify_quality` 31L; `analysis/dynamic_range.py:279` and `phase_correlation.py:269` `get_*_history` accessors
  - `auralis/core/processing/continuous_mode.py:189` `process_album` 25L; `core/config/unified_config.py:153` `set_mastering_preset` 17L (22 test hits; presets are narrowed to `adaptive`)
  - `auralis/library/repositories/album_repository.py:89` `get_by_title` 14L; `track_repository_search.py:130` `get_popular` 28L
- **Impact**: Open correctness issues keep landing on code no user path executes (e.g. #5565/#5708 sit next to `has_prebuffered_track`/`get_prebuffered_track`); each dead method also drags a mock-heavy test that must be kept green.
- **Siblings**: TD2-03 (zero-reference variants), TD2-07, TD2-08.
- **Related**: #5772, #5773, #5774 (closed; same class, partial)
- **Suggested Fix**: Delete the methods together with the tests that only exercise them, one module per commit, starting with `jump_to_track` + `'jumped'` (largest).

#### TD2-03: Methods and functions referenced by nothing at all (no prod, no test)
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: see Evidence
- **Status**: NEW
- **Age**: `analyze_album` d5adc356 2025-11-27; `to_yaml_file`/`from_yaml_file` 549d4db0 2025-11-27; `is_last_chunk` a8687a0c 2025-12-05; `delete_by_track_id` a8d4721c 2026-01-02; `get_model_info` e116da5e 2025-10-02
- **Effort**: trivial
- **Description**: Zero references anywhere (code, tests, scripts, frontend). Same list class as #5771-#5773, which missed these. `analyze_album` is additionally named in a comment at `mastering_fingerprint.py:100` ("analyze_album() delegates here") as if it were live. The YAML pair needs the optional `yaml` import (`mastering_profile.py:24-27` sets `yaml = None` on ImportError and PyYAML is in no dependency list), so calling it without PyYAML would raise `AttributeError`.
- **Evidence**:
  - `auralis/analysis/mastering_fingerprint.py:244-300` `analyze_album` (57L)
  - `auralis/analysis/mastering_profile.py:223-244` `to_yaml_file`, `from_yaml_file` (22L) + the `try: import yaml` block at `:24-27`
  - `auralis/analysis/ml/genre_classifier.py:137-152` `get_model_info` (16L; also hard-codes feature counts)
  - `auralis/library/repositories/similarity_graph_repository.py:39-59` `delete_by_track_id` (21L)
  - `auralis-web/backend/core/chunk_boundaries.py:336-338` `is_last_chunk`
  - `auralis-web/backend/core/level_manager.py:342-365` `get_statistics` (24L); `core/encoding/wav_encoder.py:239-259` `get_statistics` (21L)
  - `auralis/optimization/performance_optimizer.py:39` `get_optimization_stats` and `:44` `shutdown` (see TD2-05)
- **Impact**: ~200 lines; `delete_by_track_id` is a repository DELETE that looks like the right tool for the orphan-edge cleanup tracked in #5596, so a fix could adopt an untested path.
- **Siblings**: `GenreRepository.get_tracks_by_genre` is the same class but already tracked (#5754).
- **Related**: #5754 (open), #5596 (open), #5771-#5773 (closed)
- **Suggested Fix**: Delete the symbols above and the `yaml` import block; no test edits needed.

#### TD2-04: HybridProcessor's dynamics facade exists only to be reset
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis/core/hybrid_processor.py:293-306`; `auralis/core/hybrid/dynamics_manager.py:1-46`; `auralis/dsp/advanced_dynamics.py:34-147`; `auralis/core/hybrid_setup.py:56-85`
- **Status**: NEW
- **Age**: 36ce3c81 2025-09-29 (methods); processing path retired in #4873/#5295
- **Effort**: small (but see Related: #5098 is an open decision about wiring this back in)
- **Description**: After #4873/#5295 `HybridProcessor.dynamics_processor` never processes audio. `get_dynamics_info()` and `set_dynamics_mode()` have zero callers (code or tests; only the comment at `hybrid_setup.py:60` and a test docstring name them). The sole live call is `job_execution.py:72 processor.reset_dynamics()`, which resets the state of a facade whose `AdaptiveCompressor` (built with a lookahead buffer), `adaptation_state` dict and `gate_gain` nothing reads. So `DynamicsManager` (46L), `DynamicsProcessor` (114L), the construction block in `hybrid_setup.py` and two public methods exist to keep a reset call and `tests/regression/test_dynamics_processor_wiring.py` alive. The comment in `hybrid_setup.py:56-72` documents why it must not be wired in; it does not document why it must exist.
- **Evidence**: `rg -w "get_dynamics_info|set_dynamics_mode"` returns only definitions, `hybrid_setup.py:60` and `tests/regression/test_dynamics_processor_wiring.py:11`. `AdaptiveCompressor` has one other, live consumer (`player/realtime/auto_master.py:55`), so the compressor class itself stays.
- **Impact**: Every dynamics-settings change (e.g. #5022, #5000 history) had to be applied to a processor that shapes no audio; #5098 proposes to wire it up and would collide with any partial deletion.
- **Siblings**: TD2-05 (other write-only learning-era state).
- **Related**: #5098 (open: decide wire-or-delete first), #5295, #4873 (closed)
- **Suggested Fix**: If #5098 is declined, delete `DynamicsManager`, `DynamicsProcessor`/`create_dynamics_processor`, the two methods and the `hybrid_setup` block, drop `reset_dynamics()` from `job_execution.py`, and reduce the wiring test to its negative assertion (ContinuousMode must not call dynamics).

#### TD2-05: Write-only state left behind by the removed learning / stats paths
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis/dsp/eq/psychoacoustic_eq.py:121,187-210`; `auralis/core/hybrid_setup.py:141` + `hybrid_processor.py:90`; `auralis/optimization/performance_optimizer.py:34-45` + `optimization/profiling/performance_profiler.py:22-70`; `auralis/dsp/eq/psychoacoustic_eq.py:113`; `auralis/library/database.py:115`; `auralis/services/fingerprint_queue.py:98`; `auralis/analysis/{loudness_meter.py:41,phase_correlation.py:33,dynamic_range.py:25-26,ml/feature_extractor.py:41-42}`
- **Status**: NEW
- **Age**: `processing_history` ae2e2a76 2025-10-02; profiler wrap since #5325/#4524
- **Effort**: small
- **Description**: Attributes assigned in `__init__` or updated per chunk that no code or test ever reads. The sharpest are two leftovers of the preference-learning engine removed in #5763: `PsychoacousticEQ.processing_history` ("Store processing history for learning", `:187`) copies `gains` and `band_energies` arrays into a 100-entry list on every realtime chunk and nothing reads it; `HybridProcessor.processing_history` (`hybrid_processor.py:90`, `hybrid_setup.py:141`) is declared and set to `[]` and never touched again. The second cluster is `auralis/optimization`: `apply_module_optimizations()` wraps `AdaptiveMode.process` in `PerformanceProfiler.time_function` at import time, but the timings are only readable through `get_performance_report()`, whose single caller is `get_optimization_stats()`, which has no caller (and `shutdown()` has none; `PerformanceProfiler.memory_usage` is never written). Instrumentation is paid for on every `AdaptiveMode.process` call, forever unread. CLAUDE.md calls the package "LIVE, not test-only (#5142)": it executes, but nothing consumes its output.
- **Evidence**: `rg "processing_history" -g '*.py'` outside `psychoacoustic_eq.py`: only `hybrid_setup.py:141`, `hybrid_processor.py:90`. `rg "get_performance_report|get_optimization_stats|\.shutdown\(\)" auralis/optimization`: definitions only. Other zero-read attributes (no test reads either): `PsychoacousticEQ.perceptual_weighting` (`:113`; its builder `create_perceptual_weighting` is then reachable only from `tests/test_phase_7_1_linear_interpolation.py`), `LibraryDatabase._delete_lock` (an RLock never acquired), `FingerprintExtractionQueue.max_workers_limit`, `LoudnessMeter.overlap_size`, `PhaseCorrelationAnalyzer.phase_histogram`, `DynamicRangeAnalyzer.peak_hold_time` / `gate_threshold`, `FeatureExtractor.n_chroma` / `n_tonnetz`.
- **Impact**: Dead per-chunk work and memory in the realtime EQ path; a lock that looks like it serialises deletes but does not.
- **Siblings**: TD2-04; `scripts/check_optimization_importers.py` guards the import-time wrapper and would need updating.
- **Related**: #5763, #5325, #5142 (closed). `LibraryDatabase._delete_lock` is for /audit-concurrency: confirm delete paths are in fact serialised by `scan_coordinator` before deleting the lock.
- **Suggested Fix**: Delete the attributes and the history append; delete `get_optimization_stats`/`shutdown`/`memory_usage` and either the profiler wrap in `apply_module_optimizations()` or keep it and add a consumer (a debug log line); then `PerformanceOptimizer` collapses to nothing.
- **Cross-audit overlap**: `LibraryDatabase._delete_lock` is also E7-09 in AUDIT_ENGINE_2026-10-22.md; publish it once. TD8-02 lists the same lock; it is reported here only.

#### TD2-06: Dead constants and knobs: 47 of 71 `AssessmentConstants` attributes, 11 mastering tuning constants, 4 module constants
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis/analysis/quality_assessors/utilities/assessment_constants.py:17-170`; `auralis/core/mastering_config.py:108-222`; `auralis/core/mastering_presets.py:136,212`; `auralis-web/backend/core/encoding/wav_encoder.py:58`; `auralis/analysis/fingerprint/fingerprint_storage.py:35`; `auralis/library/repositories/base.py:25`; `auralis/version.py:21`
- **Status**: NEW
- **Age**: `assessment_constants.py` created 2025-11 (methods deleted 27023865 2026-10-22, constants left)
- **Effort**: trivial
- **Description**: #5768 deleted the dead assessor *methods* and one `AssessmentConstants` method but left their constants. Of the 71 class attributes, 47 are referenced nowhere (not in `get_standard_compliance_targets`, not in the assessors, not in tests): `TARGET_DR_VALUE`, `*_CORRELATION`, `*_STEREO_WIDTH`, `*_MONO_COMPATIBILITY`, `*_BAND_RANGE`, `*_SNR_DB`, `DEFAULT_FFT_*`, the A/C-weighting tables, etc. In `SimpleMasteringConfig`, nine documented tuning knobs have no reader anywhere: `PRE_EQ_HEADROOM_DB`, `MAX_TARGET_CREST_INCREASE_DB`, `RMS_EXPANSION_AMOUNT`, `SOFT_CLIP_BASE_KNEE`, `SOFT_CLIP_BASE_THRESHOLD`, `MAX_SUB_BASS_CUT_DB`, `MAX_MID_BOOST_DB`, `MAX_PRESENCE_BOOST_DB`, `MAX_AIR_BOOST_DB`; `MasteringPresetDefaults` adds `CLARITY_TARGET_PCT` and `SUB_TARGET_PCT`. Tuning one of these has no effect, and the mastering-engine notes in memory say these are exactly the knobs people reach for when changing the sound. Plus `WAVEncoder.DEFAULT_SUBTYPE`, `FingerprintStorage.SIGNATURE_READ_SIZE`, `LIKE_ESCAPE`, `version.SEMANTIC_VERSION`.
- **Evidence**: `rg -w` per name over `auralis*/`, `tests/`, `scripts/`: only the definition line (comments excluded). `rg "fields\(|asdict\(|getattr\(.*config" auralis/core/mastering*.py auralis/core/stages` finds no dynamic access that could consume them.
- **Impact**: A tuner editing a dead knob hears no change. This is the "orphaned config knobs" pattern #5763/#5764 prompted a check for; the removed engines are clean, these are older.
- **Siblings**: `logging.INFO_*` constants and `QUANTIZATION_VERSION` are test-only (left out).
- **Related**: #5768 (closed, partial); none open. If any mastering knob was meant to be live, route to /audit-engine instead of deleting.
- **Suggested Fix**: Delete the dead attributes; keep the 7 live `AssessmentConstants` entries plus those read by `get_standard_compliance_targets`. For the nine mastering knobs, confirm with the engine owner that no stage was meant to read them before deleting.

#### TD2-07: `FingerprintQueueManager` is test-only and its docstring still promises a re-export
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis/services/fingerprint_queue_manager.py:1-80`
- **Status**: NEW
- **Age**: 3da52800 2026-10-22 (#5827 removed the re-export that kept it importable)
- **Effort**: trivial
- **Description**: Startup builds `FingerprintExtractionQueue` directly (`config/startup/fingerprint.py:34-45`); `FingerprintQueueManager` is imported only by `tests/auralis/services/test_fingerprint_queue_lifecycle.py` and `tests/test_fingerprint_extraction.py`. The module docstring still says "`fingerprint_queue` re-exports this name, so the historical import path keeps resolving", which #5827 made false.
- **Evidence**: `rg FingerprintQueueManager -g '*.py'` outside the module and tests: nothing.
- **Impact**: A 80-line lifecycle facade (`initialize`/`shutdown`/`get_stats`/`set_progress_callback`) duplicating `FingerprintExtractionQueue.start/stop`, with two test files that give it the look of a supported path.
- **Siblings**: none.
- **Related**: #5827, #5039 (closed)
- **Suggested Fix**: Delete the module and its two test classes.

#### TD2-08: Three `require_*` dependency helpers are used only by their own test
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis-web/backend/routers/dependencies.py:38-91`
- **Status**: NEW
- **Age**: f6d5e612 2025-11-12
- **Effort**: trivial
- **Description**: `require_audio_player`, `require_player_state_manager`, `require_connection_manager` have no production caller; routers do the `if not x: raise ...Unavailable` inline (`player_playback.py:91`, `player_queue.py:155` even raises a different type, `ServiceUnavailable`). The only users are three tests in `tests/backend/test_typed_unavailable_errors_wired_5400.py`, named "wired" although nothing is wired. `require_repository_factory`, `require_service`, `require_processing_engine` in the same file are live.
- **Evidence**: `rg "require_(audio_player|player_state_manager|connection_manager)" -g '*.py'` returns the three defs, the test and `dependencies.py` itself.
- **Impact**: Two spellings of the same 503 contract; #5783 just unified the other spellings and missed this one.
- **Siblings**: `PlayerStateUnavailableError` / `ConnectionManagerUnavailableError` in `routers/errors.py` lose their only raisers if these go.
- **Related**: #5783, #5400 (closed)
- **Suggested Fix**: Either call the helpers from the routers (and fix the `ServiceUnavailable` in `player_queue.py`), or delete the three helpers, their test file and the two orphaned error classes.

#### TD2-09: Package `__init__` barrels that no consumer imports through (routers, core, cache, schemas, services)
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis-web/backend/routers/__init__.py:7-33`; `core/__init__.py`; `cache/__init__.py:18-45`; `schemas/__init__.py`; `services/__init__.py:16-45`
- **Status**: NEW
- **Age**: routers/core barrels pre-date 2025-12; `cache/__init__.py` forwards documented as "so callers keep resolving them"
- **Effort**: small
- **Description**: `config/routes.py:16-32` imports every `create_*_router` from its own module, so `routers/__init__` re-exports 11 factories nobody imports through the package (and it is already incomplete: albums, artists, metadata, settings are missing), while forcing every `import routers.x` to eagerly import 11 router modules. `core/__init__` re-exports `ChunkBoundaryManager`, `LevelManager`, `WAVEncoder`, all imported from their modules everywhere. `cache/__init__` forwards 9 constants/types (`CHUNK_DURATION`, `CHUNK_INTERVAL`, `CHUNK_SIZE_MB`, `TIER1_*`, `TIER2_*`, `CachedChunk`, `TrackCacheStatus`); production uses only `StreamlinedCacheManager` and `streamlined_cache_manager` from `cache`; its docstring also still advertises "monitoring utilities" (module deleted in #4766). `schemas/__init__` re-exports `CacheTierStats`, `INTENSITY_MIN`, `MAX_TRACK_ID_LIST`, `WebSocketMessageType`, `WeightedProfileResponse` with no importer; `services/__init__` re-exports `ServiceError`, `InvalidRequest`, `OperationFailed`, `ResourceNotFound`, `QueueEnricher`, `AudioPlayerWithQueue`, `QueueManager` with none (routers import the other five).
- **Evidence**: `rg "from routers import|from core import (ChunkBoundaryManager|LevelManager|WAVEncoder)|from cache import"` in prod: only `streamlined_cache_manager`/`StreamlinedCacheManager`.
- **Impact**: Hidden import-time coupling (eager router imports) and a second, drifting list of what each package exports.
- **Siblings**: TD2-01 (the shim layer behind `cache/manager.py`). Public-library packages (`auralis/analysis/__init__`, `auralis/io/__init__`, etc.) show the same zero-importer pattern but were not flagged under the "public API of `auralis/`" exception.
- **Related**: #5452, #4645 (closed, same pattern on `advanced_dynamics.py`)
- **Suggested Fix**: Reduce each barrel to the names with a real importer (or empty it); delete the `routers/__init__` imports; fix the `cache/__init__` docstring.

#### TD2-10: `vendor/auralis-dsp` after #5764: unused dependencies, dead `pub use` block, one unused parameter
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `vendor/auralis-dsp/Cargo.toml:15-28`; `vendor/auralis-dsp/src/lib.rs:33-41`; `vendor/auralis-dsp/src/fingerprint_compute.rs:431`
- **Status**: NEW
- **Age**: `realfft` 5393d122 2025-12-17; `criterion` 0e7ee0aa 2025-11-24
- **Effort**: trivial
- **Description**: #5764 removed the HPSS/YIN/tempo/envelope/compressor/limiter modules and the benches but not their dependencies. `realfft = "3.3"` is not referenced in any `src/` file (HPSS used it); `criterion = "0.5"` is a dev-dependency with no `benches/` directory, no `[[bench]]` and no `use criterion`. `lib.rs` re-exports 12 functions/types (`pub use chroma::chroma_cqt`, the `compute_*` family, `AudioFingerprint`, `compute_complete_fingerprint`) for "convenience", but the crate has no Rust consumer (no `tests/`, no `benches/`; `fingerprint_compute.rs` reaches siblings through `crate::module::`). `cargo check --offline --lib` emits one warning: unused parameter `sample_rate` in `estimate_pitch_stability` (`fingerprint_compute.rs:431`). There is no `#[allow(dead_code)]` left in `src/`, and everything else is reachable from `compute_fingerprint_wrapper` (`rhythm_stability`/`silence_ratio`, spectral/variation/stereo/chroma). `chunk_processor.rs` + `process_chunks_wrapper` are the other unreachable part and are already tracked in #5738.
- **Evidence**: `rg -l '\brealfft\b' src` and `rg -l criterion src benches` return nothing; `cargo check` warning quoted above.
- **Impact**: Two crates in the audit/build graph (`cargo audit` CI gate, build time) for no code; the `pub use` block advertises a Rust API surface that does not exist.
- **Siblings**: none.
- **Related**: #5738 (open, chunk_processor), #5764 (closed), #5859 (open, Rust unit failures in the same crate)
- **Suggested Fix**: Remove `realfft` and `criterion` from `Cargo.toml` (regenerate `Cargo.lock`), delete the `pub use` block, prefix or remove the unused `sample_rate` parameter.

#### TD2-11: Four `# type: ignore[attr-defined]` on `mutagen.File` are unused since mutagen ships `py.typed`
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis/library/metadata_editor/metadata_editor.py:15`; `auralis/library/artwork.py:15`; `auralis-web/backend/core/fingerprint_loading.py:20`; `auralis-web/backend/routers/tracks.py:189`
- **Status**: NEW
- **Age**: `tracks.py` 57342a06 2026-06-01
- **Effort**: trivial
- **Description**: `mypy --warn-unused-ignores --ignore-missing-imports` over the 24 files that contain the 44 `type: ignore` comments reports exactly these 4 `unused-ignore` errors; the other 40 are still needed. The installed mutagen 1.48.1 ships `py.typed` and exports `File`, so the ignores silence nothing. `tracks.py:188` carries the now-false comment "mutagen ships no py.typed marker: File is exported at runtime only", which is what keeps the stale ignore alive.
- **Evidence**: `mypy` output: `Unused "type: ignore" comment [unused-ignore]` at the four locations; `.venv/.../mutagen/py.typed` exists.
- **Impact**: Mutagen-API errors added on those lines would be silently swallowed; the ignores drift as `pyproject.toml` pins only `mutagen>=1.48`.
- **Siblings**: none (checked all 44).
- **Related**: #5782, #4397 (closed; earlier unused-ignore sweeps)
- **Suggested Fix**: Delete the four comments and the stale sentence in `tracks.py`.

#### TD2-12: Frontend exports with no production importer (queueService, enhancement slices, selectors, helpers)
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancementSlices.ts:1-69`; `services/queueService.ts:60-153`; `hooks/shared/useOptimisticUpdate.ts`; `hooks/player/usePlaybackQueue.ts:197`; `store/selectors/queue.ts:37,98-124`; `utils/apiRequest.ts:235`; `components/shared/ContextMenu/contextMenuActions.tsx:131`; `hooks/shared/useStandardizedAPI.ts` (`useCacheHealth`)
- **Status**: NEW
- **Age**: `queueService` `aad6d2cd` 2025-10-21; `useEnhancementSlices.ts` created in ab3c022c 2026-10-22 (#5840)
- **Effort**: small
- **Description**: A name-level scan of all `export`s under `src/` (no knip/ts-prune available) leaves these value exports with no non-test importer (barrels excluded). The newest is the 69-line `useEnhancementSlices.ts` that #5840 just split out: `usePresetControl`, `useIntensityControl`, `useEnhancementToggle` are imported only by `useEnhancementControl.test.ts`. `queueService.ts` exports eight functions plus a default object; production imports only `addTrackToQueue`, `addTracksToQueue`, `setQueue` and the `QueueResponse` type, so `getQueue`, `removeTrackFromQueue`, `reorderQueue`, `shuffleQueue`, `clearQueue` and the default export are tests-only (queue mutations go through `useQueueMutations`). Others: `useOptimisticUpdate` (88L, barrel + test only), `usePlaybackQueueView`, `makeSelectTrackAtIndex` / `makeSelectTracksInRange` / `makeSelectFilteredTracks` / `makeSelectTracksByDuration` / `selectFormattedQueueTime`, `getBlob`, `getAlbumContextActions` (barrel only), `useCacheHealth`.
- **Evidence**: `rg -l -w <name> src -g '!**/__tests__/**'` returns only the defining file (and a barrel for `useOptimisticUpdate`, `getAlbumContextActions`, `transformAlbum`). Excluded as already tracked: orphan components (#5628), dead selector cluster in `combined/player/cache/connection` (#5129), `themeConfig` palette (#5646), unused design-system primitives (#5132).
- **Impact**: Mutation logic exists in two places (`queueService.reorderQueue` vs `useQueueMutations`), so a fix to one (cf. #5189, #5612) does not reach the other.
- **Siblings**: ~45 exported-only `*Props`/`*Return` types and the `components/library/Styles/*.styles.ts` unused styled exports (`Container.styles`, `Typography.styles`, `BorderRadius.styles`, parts of `Skeleton.styles`/`Spinner.styles`) were seen but are low-value type or style noise and not itemised.
- **Related**: #5129, #5628, #5767 (closed), #5788 (closed)
- **Suggested Fix**: Delete `useEnhancementSlices.ts` (and its three test cases), the five unused `queueService` functions and default export, and the rest of the list with their tests.

#### TD2-13: Five unused imports left by the god-file splits
- **Severity**: LOW
- **Dimension**: Dead Code
- **Location**: `auralis/library/artwork.py:13` (`Any`); `auralis/library/database.py:19` (`Any`); `auralis/library/metadata_editor/metadata_editor.py:30` (`MetadataUpdate`); `auralis/library/sidecar_manager.py:24` (`warning`); `auralis/player/gapless_playback_engine.py:19` (`debug`)
- **Status**: NEW (recurrence of #5781, which fixed an earlier set)
- **Age**: 036a7fbe, 512923b1, c7293b9a, b9e92f9e (all 2026-10-22, #5836/#5837 splits)
- **Effort**: trivial
- **Description**: `ruff check --select F401,F811,F841 auralis auralis-web/backend` reports exactly these five: each is a name the coordinator needed before the mixin/sibling module took the code that used it. No test patches `sidecar_manager.warning` or `gapless_playback_engine.debug` (checked).
- **Evidence**: ruff output; `metadata_editor.py` only referenced the type in the moved `batch_update`.
- **Impact**: Mild; also shows that no lint step runs between god-file splits.
- **Siblings**: none (F811/F841 clean; the 5 `SimpleMasteringPipeline` hits from vulture are `TYPE_CHECKING` imports used in quoted annotations, not findings).
- **Related**: #5781 (closed), #5836, #5837
- **Suggested Fix**: `ruff check --select F401 --fix` on those five files; consider adding F401 to the pre-push hook so splits cannot reintroduce it.

---

### Dimension 3: Logic Duplication

#### TD3-05: `tracks.py` and `fingerprint_status.py` still hand-roll the try/except that `with_error_handling` replaces
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/routers/tracks.py:73-91,100-113,122-129,141-146,158-163,225-233`; `auralis-web/backend/routers/fingerprint_status.py:62-91,189-196`
- **Status**: NEW
- **Age**: 54812c99 2026-10-22 (#5832 moved them to module level without converting)
- **Effort**: trivial
- **Description**: 8 handlers repeat `try: ... except HTTPException: raise; except Exception as e: raise handle_query_error("<op>", e)`. `with_error_handling("<op>")` (used on 60+ handlers: `albums.py`, `artists.py`, `playlists_crud.py`, `settings.py`, ...) is the exact same behaviour and is already async-safe and `functools.wraps`-preserving for FastAPI signature introspection.
- **Evidence**: `tracks.py:89-91` `except HTTPException: raise / except Exception as e: raise handle_query_error("get tracks", e)`, identical at lines 111-113, 127-129, 144-146, 161-163, 231-233, and `fingerprint_status.py:89-91,194-196`.
- **Impact**: Each copy is one more place to forget a fix to the shared mapping (see TD3-04).
- **Siblings**: `metadata_tracks.py` (3) and `library_scan.py` (1) have extra `except` arms and are legitimately bespoke.
- **Suggested Fix**: Decorate the 8 handlers with `@with_error_handling("...")` and delete the try/except bodies (dedent the handler body).

#### TD3-08: Four `*_deps.py` modules hand-roll the "repository factory or 503" provider that `RepositoryFactoryDeps` exists to replace
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/routers/albums_deps.py:15-37`, `files_deps.py:14-41`, `playlists_deps.py:14-39`, `artwork_deps.py:15-52`; the shared form is `routers/repo_deps.py:30-43`
- **Status**: NEW
- **Age**: f033c8b4 2026-10-22 (#5831) for the four; 54812c99 (#5832) added `repo_deps.py`
- **Effort**: small
- **Description**: `repo_deps.py` was written so routers whose only collaborator is `get_repository_factory` stop carrying "the same ten-line `RouterDeps` holder". `tracks.py`, `artists.py`, `fingerprint_status.py` and `fingerprint_queue.py` use it. `albums_deps.py` and `files_deps.py` are exactly that holder (one field, one `_get_repos`) and were not migrated; `playlists_deps.py` and `artwork_deps.py` re-implement the same `_get_repos` body next to a `connection_manager` field.
- **Evidence**: `playlists_deps.py:39`, `artwork_deps.py:52` and `files_deps.py:27` are the same line, `return require_repository_factory(_deps.current().get_repository_factory)`. `albums_deps.py` adds a `Depends(_get_repository_factory)` indirection to reach the same call.
- **Impact**: 4 copies of the per-request lookup plus 4 `_XDeps` holder classes; a change to the 503 policy touches 5 files.
- **Siblings**: `metadata_deps.py:86`, `enhancement_deps.py:58`, `similarity_deps.py:46`, `library.py:61,76,98` resolve the factory themselves (some by design: order of checks, #5832 comments).
- **Suggested Fix**: Switch `albums_deps.py` and `files_deps.py` to `RepositoryFactoryDeps` (delete both holder classes). For playlists/artwork, compose `RepositoryFactoryDeps` for the repo part and keep only the `connection_manager` field.

#### TD3-09: Repository read-path scaffolding: per-call `expunge` shapes and the option tuples that #5028 missed
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis/library/repositories/` (13 get-one sites, ~21 expunge-loop sites, 71 `expunge*` calls in total); inline options at `playlist_crud_mixin.py:106-113`, `artist_repository.py:240-251`, `playlist_query_mixin.py:62-69,132-139`; `_total_duration_subquery` at `album_repository.py:24-32` and `playlist_query_mixin.py:84-96`
- **Status**: NEW (adjacent to closed #5028 and #5791, neither covers these)
- **Age**: playlist/artist copies bc533e03 2026-09-14; #5791 2689d71f 2026-10-22
- **Effort**: medium
- **Description**: The same read scaffold, `with self._session_scope() as session: x = session.execute(select(M).options(*OPTS).where(...)).scalars().first(); if x: session.expunge(x); return x`, appears at 13 get-one sites (album 5, artist 2, genre 2, track lookup 2, playlist 1, fingerprint 1). Detach style diverges per file: `expunge_all()` in album/playlist/fingerprint paths, per-item `expunge` loops in artist/genre/track paths. The comments cite different closed fixes for each (#2406, #4236, #3709) for what is the same operation. `_session_scope` already `close()`s the session, which detaches everything, so this is also a place where a single helper can own the rule.
- **Evidence**:
  - Playlist detail loads `selectinload(Playlist.tracks).selectinload(Track.artists/genres/album)` inline, while Album, Artist, Genre and Track define module-level constants (#5028's rule: "so a future read path can't silently omit it").
  - `playlist_query_mixin.py` writes the `with_expression(track_count_expr, correlated_count(...))` + `with_expression(total_duration_expr, self._total_duration_subquery())` pair twice (`get_all`, `search`), whereas Album/Artist/Genre have `_*_LIST_OPTIONS`.
  - `ArtistRepository.get_all_artists` (cli-only caller `cli/fetch_artwork.py:71`) hand-writes a third artist tuple that deliberately omits `Track.genres`.
  - #5791 unified `correlated_count`, but the two `_total_duration_subquery` bodies (Album direct FK vs Playlist M2M join) remain separate copies.
- **Impact**: The #4236 DetachedInstanceError bug class (one method's tuple fixed, sibling's stale) is still structurally possible for playlists.
- **Siblings**: see counts above.
- **Related**: `/audit-engine` library area if the missing `Track.genres` in `get_all_artists` matters to `fetch_artwork`.
- **Suggested Fix**: Add `BaseRepository._first_detached(session, stmt)` / `_all_detached(session, stmt)` (one `expunge_all` policy), add `_PLAYLIST_DETAIL_OPTIONS` and `_PLAYLIST_LIST_OPTIONS` module constants, and add `correlated_sum(source, value_col, fk, parent, via=None)` next to `correlated_count` in `base.py`.

#### TD3-10: Twenty repository write paths repeat `except -> session.rollback() -> log -> return default`
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis/library/repositories/` (counts per file from a regex: fingerprint_crud 3, playlist_crud 3, playlist_ordering 3, fingerprint_upsert 2, fingerprint_scheduler 2, playlist_membership 2, track_lifecycle 2, track_mutation 2, fingerprint_stats 1)
- **Status**: NEW
- **Age**: a964d4f1 2026-08-22 (#4604) migrated these to `_session_scope`; #5117 added the rollback to the scope
- **Effort**: medium
- **Description**: 20 methods catch `Exception`, call `session.rollback()`, log "Failed to ...", and return `None`/`False`. `BaseRepository._session_scope` (#5117) now rolls back on escape and `close()` always discards the open transaction, so the explicit rollback is redundant, and the whole shape is one helper.
- **Evidence**: e.g. `fingerprint_crud_mixin.py:82-87` `except Exception as e: session.rollback(); error(f"Failed to add fingerprint for track {track_id}: {e}"); return None; finally: session.expunge_all()`.
- **Impact**: Log wording, whether the rollback precedes the log, and the return default all vary by file, so failure handling cannot be changed in one place (a retry-on-locked policy, say, needs 20 edits).
- **Suggested Fix**: Add `BaseRepository._guarded(op_name, default)` as a context manager (swallow, log once, yield default) on top of `_session_scope`, and migrate the 20 sites file by file; drop their explicit `session.rollback()` calls.

#### TD3-11: dB and linear-amplitude conversions are still inline about 55 times after #5785 created `amplitude_to_db`
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis/dsp/utils/conversion.py:19-65` (the home); inline copies across `auralis/` and `auralis-web/backend/core/level_manager.py`
- **Status**: NEW (residual of closed #5785, which fixed the scalar peak/RMS forward conversion only)
- **Age**: 994cbbfb 2026-10-21
- **Effort**: medium
- **Description**: `conversion.py` has `amplitude_to_db`, `peak_db`, `rms_db`, plus a second `to_db` (floor `1e-10`, one caller `dsp/utils/spectral.py:168`) that the module's own header calls one of "the three" disagreeing conventions. There is no inverse (`db_to_amplitude`). `core/processing/base/db_conversion.py::DBConversion` is a static wrapper over `amplitude_to_db` with `to_linear` as the only inverse, imported by exactly one file for it (`peak_management.py:93`).
- **Evidence**:
  - 29 inline `10 ** (x / 20)` sites: `dsp/basic.py:60`, `dsp/eq/filters.py:95`, `dsp/dynamics/brick_wall_limiter.py:74`, `dsp/dynamics/compressor.py:142`, `core/dsp/parallel_eq.py:115,188,266`, `core/dsp/harmonic_exciter.py:114,121`, `core/dsp/transient_shaper.py:135`, `core/mastering_chunk_assembly.py:23,88,91`, `core/mastering_process_chunk.py:64`, `core/mastering_branches/continuous.py:215,266`, `core/stages/loudness_maximizer.py:74`, `core/processing/base/compression_expansion.py:64,166,180`, `player/realtime/auto_master.py:179`, `level_manager.py:221,226,274,339`, and more.
  - About 26 inline `20 * np.log10(...)` sites with their own silence handling: `windowed_compute.py:112-113`, `loudness_meter.py:184,202,267-268`, `dynamic_range.py:152`, `content_analyzer.py:291`, `stages/safety_limiter.py:42`, `mastering_prepare.py:72`, `level_manager.py:118`, `auto_master.py:171,174,214,215`, and more.
- **Impact**: The silence-convention disagreement #5785 set out to remove can re-enter at any inline site; the three-names situation (`to_db`, `DBConversion.to_db`, `amplitude_to_db`) persists.
- **Suggested Fix**: Add `db_to_amplitude(db)` beside `amplitude_to_db` in `dsp/utils/conversion.py`; delete the `to_db` floor variant (repoint `spectral.py:168` at `amplitude_to_db(..., silence_db=...)`); retire `DBConversion` in favour of the module functions; migrate the 29 + ~26 sites opportunistically, starting with the `core/stages/` and `core/dsp/` modules.

#### TD3-12: `stream_enhanced.py` and `stream_seek.py` share about 110 lines of stream lifecycle skeleton; `stream_normal.py` repeats the tail
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/core/stream_enhanced.py:60-303`, `auralis-web/backend/core/stream_seek.py:60-292`, `auralis-web/backend/core/stream_normal.py:66-277`
- **Status**: NEW (#5032, closed, extracted the track-resolution and chunk-pump halves only)
- **Age**: 90245885 2026-10-22 (latest touch)
- **Effort**: medium
- **Description**: After #5032, what remains in the two enhanced paths is a byte-for-byte skeleton: guards, semaphore acquire with `STREAM_ACQUIRE_TIMEOUT_SECONDS`, `chunk_cancel_event` registration in `routers.system._stream_chunk_cancel_events`, `asyncio.wait_for(asyncio.to_thread(controller.chunked_processor_class, track_id=..., filepath=..., preset=..., intensity=..., cancel_event=...), timeout=CHUNK_PROCESS_TIMEOUT)` with its `TimeoutError` branch, `validate_processor_metadata`, `_send_stream_start`, `pump_chunks`, `_send_stream_completion`, `except WebSocketDisconnect / except Exception -> _safe_error_message`, and a `finally` that releases the semaphore, `await asyncio.to_thread(processor.close)` (#5253), and pops the cancel event only if it is still ours (#4815). The 6-line window scan found the processor-construction block and the `track_id=/preset=/intensity=` kwargs duplicated at `stream_enhanced.py:147-154` and `stream_seek.py:139-146`.
- **Evidence**: The cancel-event identity guard `if _stream_chunk_cancel_events.get(_ws_id_key) is chunk_cancel_event: ... pop(...)` appears verbatim at `stream_enhanced.py:298-299` and `stream_seek.py:291-292`. History of the cost: #5074 (closed) was "stream_seek.py never got #4999's chunk-timeout abort", and #5253's temp-WAV fix had to be applied to both `finally` blocks.
- **Impact**: Every lifecycle fix (semaphore leak #4329, cancel event #4815, temp WAV #5253) must be applied in both enhanced files and checked in the normal one.
- **Siblings**: `stream_normal.py:66-277` (semaphore + error tail; no processor/cancel event).
- **Related**: #5074 (closed, evidence of drift); `/audit-concurrency` coordinator-sibling row.
- **Suggested Fix**: Add an `async with stream_session(controller, websocket, track_id, preset, intensity) as sess:` context manager in `stream_protocol.py` (or a new `stream_session.py`) that acquires the permit, registers/pops the cancel event, builds the processor with the timeout, and releases and closes in its exit. The three files then keep only their mode-specific middle (buffer task for enhanced, `chunk_for_position` for seek).
- **Merge note**: TD9-06 measures the same three handlers as the longest functions in the repo; one shared `StreamSession` extraction closes both.

#### TD3-13: `ParallelEQUtilities` repeats extract-band + parallel-add three times, and the `ndim` axis idiom lives in four more DSP modules
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis/core/dsp/parallel_eq.py:105-122,181-192,259-270`; idiom at `core/dsp/transient_shaper.py:98`, `core/dsp/resonance_notcher.py:179`, `core/dsp/harmonic_exciter.py:123`, `core/stages/sub_bass_control.py:75`
- **Status**: NEW
- **Age**: 01848a75 2026-10-20 (#5116 touched all three copies by hand, each commented "sibling")
- **Effort**: small
- **Description**: `apply_low_shelf_boost`, `apply_high_shelf_boost` and `apply_bandpass_boost` differ only in the `butter(...)` design line. Each then does `if audio.ndim == 1: band = sosfiltfilt_safe(...) else: ... axis=1 ...`, `.astype(audio.dtype)`, `boost_diff = 10 ** (boost_db / 20) - 1.0` and `(audio + band * boost_diff).astype(audio.dtype)`.
- **Evidence**: `sosfiltfilt_safe` (`dsp/utils/filters.py:60-111`) documents "always returns the input dtype" and takes an `axis`, so both the `ndim` branch (use `axis=-1`) and the `.astype(audio.dtype)` after it are redundant. The copy guard is satisfied (no in-place write) in all three.
- **Impact**: #5116 needed the same edit in three places; a fourth variant would be a fourth copy.
- **Suggested Fix**: Extract `_parallel_add(audio, sos, boost_db, context)` in `parallel_eq.py` (call `sosfiltfilt_safe(sos, audio, axis=-1, context=context)`; add `band * (db_to_amplitude(boost_db) - 1)`), leaving each public method as clamp + `butter` + one call. Optionally add `audio_time_axis(audio)` to `dsp/utils` for the four other `axis = -1 if ndim > 1 else 0` sites.

#### TD3-14: `useRestAPI` keeps a second HTTP transport (`restApiTransport.ts`) that `apiRequest.ts` already calls a duplicate to be removed
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/frontend/src/hooks/api/restApiTransport.ts:18-70` vs `auralis-web/frontend/src/utils/apiRequest.ts:1-100`, `auralis-web/frontend/src/config/api.ts` (`getApiUrl`)
- **Status**: NEW (no open issue tracks the convergence; #5649 and #5650 cover consequences, see Skipped)
- **Age**: 61ad7103 2026-10-22 (#5841 split, carrying the duplicate along)
- **Effort**: medium
- **Description**: The `apiRequest.ts` header states the target end state ("`useRestAPI` ... reimplements the transport rather than wrapping it ... Do not add a third transport"). #5841 moved that reimplementation into its own file instead of removing it. `fetchWithTimeout` is a second timeout-to-`APIRequestError` mapper (its own comment says "Mirrors utils/apiRequest.ts's identical mapping (#5019)"), and `buildUrl` is a second spelling of `getApiUrl`.
- **Evidence**: `apiRequest.fetchWithTimeout` composes the caller's `AbortSignal` and supports `timeoutMs <= 0`; `restApiTransport.fetchWithTimeout` takes an `activeControllers` Set and drops the caller signal. This is the cancellation gap #5650 reports. `buildUrl` does `endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`` while `getApiUrl` normalises the leading slash; `apiRequest` has no `params` option at all.
- **Impact**: Every transport fix (#5609 timeout mapping, #5019, #4442) has been applied to both copies by hand; the signal-forwarding fix reached only one.
- **Related**: #5650 (open), #5649 (open), #5198 (closed, verbs inside useRestAPI).
- **Suggested Fix**: Re-implement `useRestAPI`'s verbs over `apiRequest` (keeping only the React state, per-hook controller and stale-request filter), delete `restApiTransport.fetchWithTimeout`, and move `QueryParams`/`buildUrl` into `utils/apiRequest.ts` as an optional `params` request option.

#### TD3-15: Library list URL, page size and query-string assembly live in five frontend places beside `ENDPOINTS`
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `hooks/library/libraryQueryRequest.ts:33-37,49-70`, `hooks/library/libraryPageFetch.ts:18,35-38`, `hooks/library/useInfiniteAlbums.ts:29,36-49,79`, `services/playlistService.ts:96-100`, `config/api.ts:73-76` (all under `auralis-web/frontend/src/`)
- **Status**: NEW
- **Age**: 2026-10-22 (#5840 split `libraryPageFetch.ts` out of `useLibraryPagination`)
- **Effort**: small
- **Description**: `QUERY_TYPE_ENDPOINT` in `libraryQueryRequest.ts` re-types `ENDPOINTS.LIBRARY_TRACKS/ALBUMS/ARTISTS`. `libraryPageFetch.tracksEndpoint` hard-codes `/api/library/tracks` and `/api/library/tracks/favorites` with its own `PAGE_LIMIT = 50`. `useInfiniteAlbums.fetchAlbums` rebuilds `/api/albums?offset&limit&search` with its own `limit = 50` default (twice). `buildEndpoint` falls back to a third `|| 50`. The page size `50` is typed in six places; `URLSearchParams` assembly appears in `artworkService.ts` (x2), `playlistService.ts`, `useSimilarTracks.ts`, and the three above.
- **Evidence**: `libraryPageFetch.ts:36-37` `` `/api/library/tracks/favorites?limit=${PAGE_LIMIT}&offset=${offset}` `` vs `libraryQueryRequest.ts:57-58` `params.append('limit', String(options.limit || 50))`, no shared constant. `useInfiniteAlbums` omits `order_by` support that `buildEndpoint` has.
- **Impact**: Changing the library page size or an endpoint means editing 4-6 files; the endpoint constants already in `config/api.ts` are not the ones used.
- **Related**: #5133 (closed; hard-coded relative API URLs, a sibling sweep).
- **Suggested Fix**: Export `LIBRARY_PAGE_LIMIT` from `config/api.ts`, derive `QUERY_TYPE_ENDPOINT` from `ENDPOINTS`, and route all five query-string builders through the shared `params` option proposed in TD3-14 (`get(endpoint, { params })`).

#### TD3-16: The processing-mode list ("reference", "adaptive", "hybrid") is mirrored in six places instead of one exported type
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis/core/config/unified_config.py:27,102,124`, `auralis/core/config/settings.py:39`, `auralis/core/hybrid_processor.py:349`, `auralis-web/backend/core/job_config.py:59-65`, `auralis-web/backend/core/processor_factory.py:256`, `auralis-web/backend/routers/processing_models.py:24`
- **Status**: NEW
- **Age**: 2026-10-22 (latest touches)
- **Effort**: trivial
- **Description**: `PROCESSING_MODES` exists in `unified_config.py`, but `HybridProcessor.set_processing_mode` re-validates with an inline `["reference", "adaptive", "hybrid"]` right before calling `config.set_processing_mode`, which raises on the same list. `job_config.py` rewrites the three modes as an `if/elif` chain that does the same as `config.set_processing_mode(job.mode)`. Four `Literal[...]` copies sit next to it.
- **Evidence**: `hybrid_processor.py:349` `if mode not in ["reference", "adaptive", "hybrid"]:`; `job_config.py:60-65` `if job.mode == "adaptive": config.set_processing_mode("adaptive") elif ...`.
- **Impact**: A fourth mode needs seven edits; the `job_config` chain silently ignores an unknown mode where the config method raises.
- **Related**: preset row in Sibling Detection (the equivalent for presets is clean, this is its processing-mode analogue).
- **Suggested Fix**: In `core/config/settings.py` define `ProcessingMode = Literal["reference","adaptive","hybrid"]` and `PROCESSING_MODES = get_args(ProcessingMode)`; import it in the other five, delete the inline list in `HybridProcessor`, and replace the `job_config` chain with `config.set_processing_mode(job.mode)`.

#### TD3-17: Fingerprint fallbacks and the -14 LUFS default still have raw copies after #5795
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: raw `-14.0`: `auralis/core/config/genre_profiles.py:31,106`, `auralis/core/config/preset_profiles.py:99`; raw fingerprint fallbacks: `auralis/player/realtime/auto_master.py:185-186`, `auralis/core/analysis/spectrum_mapper/spectrum_mapper.py:46,48`, `auralis-web/backend/core/mastering_target_generation.py:58`, `auralis/dsp/eq/curves.py:104`, `auralis/core/processing/eq_processor.py:122`
- **Status**: NEW (residual of closed #5795; `TODO(#5858)` for the percent/fraction mismatch at `target_generator.py:268-275` is open and excluded)
- **Age**: 92fca886 2026-10-22
- **Effort**: small
- **Description**: #5795 created `DEFAULT_TARGET_LUFS` and `FINGERPRINT_DEFAULTS` and swept most sites. The config layer's default profile and the sole shipped preset (`preset_profiles.py:99`, genre `pop` and `default`) still say `target_lufs=-14.0`, the same meaning as `DEFAULT_TARGET_LUFS`. `fingerprint_unpacker.FINGERPRINT_DEFAULTS` has `'crest_db': 12.0`, yet `spectrum_mapper.py:46` and `mastering_target_generation.py:58` re-type 12.0. `auto_master.py:185-186` uses `fingerprint.get('lufs', 0)` / `('crest_db', 0)`, so a partial fingerprint reads as 0 LUFS (silently fails the `lufs < -13 and crest > 14` gate) rather than the table default of -14 / 12. `spectral_centroid` falls back to `2000` (Hz) in three modules while the unpacker table holds a normalised `0.5` for the same name.
- **Evidence**: `auto_master.py:185` `lufs = self.fingerprint.get('lufs', 0)` versus `FINGERPRINT_DEFAULTS['lufs'] == -14.0`; `curves.py:104`, `eq_processor.py:122`, `spectrum_mapper.py:48` each `.get('spectral_centroid', 2000)`.
- **Impact**: The "one home" the #5795 header promises is still not the only home; two different units for `spectral_centroid` defaults sit in one codebase.
- **Siblings**: `assessment_constants.py:24-41` `-14.0` for streaming platforms (platform facts, legitimate); `mastering_presets.py:269` `-14.5` (deliberate engine target).
- **Suggested Fix**: Use `DEFAULT_TARGET_LUFS` in `genre_profiles.py` / `preset_profiles.py` (`dsp/utils/loudness_targets.py` is importable from `core/config`), `fingerprint_default('crest_db')` / `'lufs'` at the listed sites, and add a `'spectral_centroid_hz': 2000.0` entry to the table for the three Hz fallbacks.

#### TD3-18: Frontend WebSocket reconnect budget has three values: 5 (Redux), 10 (manager default), `DEV ? 3 : 10` (hook)
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/frontend/src/store/slices/connectionSlice.ts:35`, `auralis-web/frontend/src/utils/errorHandling.ts:31-36`, `auralis-web/frontend/src/hooks/websocket/useWebSocketConnection.ts:188`
- **Status**: NEW (adjacent to closed #5800, which de-duplicated backoff but not this)
- **Age**: 2026-10-22 (#5841)
- **Effort**: trivial
- **Description**: `WebSocketManager`'s `DEFAULT_WEBSOCKET_CONFIG.maxReconnectAttempts` is 10 and the hook re-types `10` in `import.meta.env.DEV ? 3 : 10`, while the Redux slice's `maxReconnectAttempts: 5` feeds `canReconnect` in `selectors/connection.ts:43` and `useConnectionRedux.ts:66`.
- **Evidence**: slice initialState `maxReconnectAttempts: 5`; hook `const maxAttempts = import.meta.env.DEV ? 3 : 10;` immediately above a comment saying delays "come from WebSocketManager's defaults".
- **Impact**: `canReconnect` can say false while the manager is still retrying. `setMaxReconnectAttempts` is flagged as having no production dispatch (#4921), so nothing reconciles the values.
- **Related**: `utils/errorHandling.ts` now contains only `WebSocketManager` (its header lists "Error Handling Utilities" and the retry rule moved to `queryRetry.ts` in #5841); rename candidate for Dim 7.
- **Suggested Fix**: Export `DEFAULT_MAX_RECONNECT_ATTEMPTS` from `config/timing.ts`; use it as the manager default, in the hook (`DEV ? 3 : DEFAULT_...`) and as the slice's initial state.

#### TD3-19: The fingerprint hooks repeat "404 means null" and the cache options
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/frontend/src/hooks/fingerprint/useTrackFingerprint.ts:36-53,86-90` and `useAlbumFingerprint.ts:46-67,92-96,153`
- **Status**: NEW
- **Age**: 2026-08 to 2026-10 (#4847 fixed the track copy, #5122 fixed the album copy a month later)
- **Effort**: trivial
- **Description**: Both files wrap `get<...>()` in `try { ... } catch (err) { if (err instanceof APIRequestError && err.statusCode === 404) return null; throw err; }`, and repeat `staleTime: QUERY_STALE_TIME_MS` / `gcTime: 30 * 60 * 1000` (three occurrences of the bare 30-minute literal).
- **Evidence**: #5122's own issue text: "#4847 fixed exactly this in the sibling `useTrackFingerprint`; this is the half that sweep missed". The album `queryFn` also declares a `signal` parameter and then calls `fetchAlbumFingerprint(albumId)` without passing it (`useAlbumFingerprint.ts:~92`), the exact gap #5650 reports for React Query `queryFn`s.
- **Impact**: The pair has already diverged once and needed a second fix.
- **Related**: #5650 (open).
- **Suggested Fix**: Add `getOrNullOn404<T>(endpoint, options)` to `utils/apiRequest.ts` and `FINGERPRINT_QUERY_OPTIONS = { staleTime, gcTime }` to `config/timing.ts`; both fetchers become one-liners.

#### TD3-20: Pagination `limit`/`offset` Query pair is re-spelled in five handlers
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/routers/artists.py:80-81`, `albums.py:100-101`, `playlists_crud.py:23-24`, `tracks.py:61-62,95-96`
- **Status**: NEW (envelope duplication is tracked separately as open #5499)
- **Age**: 54812c99 2026-10-22
- **Effort**: trivial
- **Description**: `pagination.py` defines `PaginationParams` constants and `compute_has_more`, but each handler still writes `Query(PaginationParams.DEFAULT_LIMIT, ge=PaginationParams.MIN_LIMIT, le=PaginationParams.MAX_LIMIT)` and the offset equivalent, then builds a `{ items, total, offset, limit, has_more }` dict with a different key order in each (`tracks.py:79-85` vs `:104-110`).
- **Impact**: Changing a bound or adding a field is five edits.
- **Related**: #5499 (open, `TrackListResponse`/`AlbumListResponse` envelope), #5823 (open, `has_more`/`hasMore`).
- **Suggested Fix**: Add `limit_query()` / `offset_query()` factories (or a `Depends(pagination_params)` dataclass) in `routers/pagination.py` and a `paginated(key, items, total, offset, limit)` builder next to `compute_has_more`.

### Dimension 4: Magic Numbers

#### TD4-02: `SILENCE_FLOOR_DB` exists twice with different values (-96 vs -60) and different meanings
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis/dsp/utils/conversion.py:18` (= -96.0, re-exported at `dsp/utils/__init__.py:26,63`) and `auralis-web/backend/core/level_manager.py:33` (= -60.0)
- **Status**: NEW
- **Age**: `b6163423` 2026-07-29 (level_manager); `994cbbfb` 2026-10-21 (#5785 conversion.py)
- **Effort**: trivial
- **Description**: #5785 (yesterday) introduced `SILENCE_FLOOR_DB = -96.0` as the codebase's named silence convention (16-bit noise floor). `level_manager.py` already had a module constant of the same name meaning "RMS below this carries no level information, skip smoothing" at -60 dB. A grep for the name now returns two constants that disagree by 36 dB, and `level_manager.py:115` returns `SILENCE_FLOOR_DB` as the "no prior level" RMS, a third convention next to `-inf` and `to_db`'s 1e-10 floor that #5785 set out to remove. Neighbouring floors are also unrelated bare values: `adaptive.py:74,82` `LOUDNESS_FLOOR_LUFS = -70` / `SILENCE_FLOOR_LUFS = -50`, `dynamic_range.py:26` gate -70, `settings.py:74` gate -60.
- **Evidence**: `SILENCE_FLOOR_DB: float = -96.0` (dsp) vs `SILENCE_FLOOR_DB = -60.0` (backend level_manager, comment block ending "Below this floor, level differences are ignored").
- **Impact**: A future import of the dsp name into level logic (or the reverse) silently changes the #4729 runaway-gain guard threshold.
- **Siblings**: `adaptive.py:74,82`, `dynamic_range.py:26`, `dsp/dynamics/settings.py:74`, `estimation_ops.py:143` (-90), `assessment_constants.py:117-118`
- **Related**: #5785 (closed, introduced the second name)
- **Suggested Fix**: Rename the backend constant to `LEVEL_SMOOTHING_GATE_DB` (it is a gate, not a silence convention); keep `SILENCE_FLOOR_DB` as the single dsp name.

#### TD4-03: Harmonic-exciter bypass threshold `wet_db <= -60.0` is typed in the exciter and mirrored by hand in its stage wrapper
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis/core/dsp/harmonic_exciter.py:98` (and docstring `:73`), `auralis/core/stages/harmonic_exciter.py:72`
- **Status**: NEW
- **Age**: `2a162a99` 2026-05-20 (exciter); `94ef07ca` 2026-08-07 (stage mirror, #4900)
- **Effort**: trivial
- **Description**: #4900 made the stage report `no_op` when the exciter will bypass, by copying the exciter's own bypass literal into the stage ("Mirror HarmonicExciter.apply()'s own bypass conditions here"). The coupling is explicit in the comment but carried only by two identical bare `-60.0`s. If the exciter threshold moves, the stage resumes claiming `stage_info` for a stage that never ran (the exact bug #4900 fixed).
- **Evidence**: `if wet_db <= -60.0: return audio.copy()` / `if wet_db <= -60.0: return no_op(audio)`.
- **Impact**: Silent regression of #4900 on the next threshold edit; no test ties the two.
- **Siblings**: none beyond the docstring mention.
- **Related**: #4900 (closed)
- **Suggested Fix**: Add `HarmonicExciter.BYPASS_WET_DB = -60.0` (or a `will_bypass(wet_db)` static method) and use it in both places.

#### TD4-04: `PLACEHOLDER_LUFS_SENTINEL` exists but five repository sites still type `-100.0`
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis/library/repositories/fingerprint_scheduler_repository.py:45,147,221` and `fingerprint_stats_repository.py:103,112`; the constant is `fingerprint_shared.py:39`
- **Status**: NEW
- **Age**: `6900b251` 2026-06-01 (stats predicate); constant `9811f198` 2026-07-30 (#4822)
- **Effort**: trivial
- **Description**: #4822 introduced `PLACEHOLDER_LUFS_SENTINEL` and `_current_fingerprint_clause()` so the placeholder-row predicate has one home, and used them in `fingerprint_shared.py:56,70`. The scheduler (`delete(...).where(lufs == -100.0)`, the placeholder row constructor, and a raw-SQL `tf.lufs != -100.0` string) and the stats repo (`lufs != -100.0` twice) kept private copies of both the value and the predicate. A sentinel change would update the readers in `fingerprint_shared` but not the claim writer, orphaning placeholder rows.
- **Evidence**: `TrackFingerprint.lufs != -100.0,` (stats :103,:112) next to `TrackFingerprint.lufs != PLACEHOLDER_LUFS_SENTINEL,` (shared :56).
- **Impact**: Writer and readers of the claim sentinel can drift; the raw-SQL site cannot be found by renaming the constant.
- **Siblings**: docstring mentions `scheduler:32,106`, `stats:137`, `database.py:241`.
- **Related**: #4822, #2506 (both closed)
- **Suggested Fix**: Import `PLACEHOLDER_LUFS_SENTINEL` in both repos; for the raw-SQL site bind it as `:sentinel`; reuse `_current_fingerprint_clause()` in the stats counts.

#### TD4-05: Loudness-target literals: "-11 LUFS" defined three times, and #5795 left bare `-14.0` at five more sites
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: -11: `auralis/core/mastering_config.py:61` (`TARGET_LUFS`), `auralis/dsp/utils/adaptive_loudness.py:27` (`TARGET_LUFS`), `auralis/core/mastering_branches/soft_clip_params.py:36` (bare `-11.0` plus `/ 9.0`). -14: `auralis/core/config/genre_profiles.py:31,106`, `auralis/core/config/preset_profiles.py:99`, `auralis/core/utils/fingerprint_unpacker.py:24`, `auralis/analysis/quality_assessors/utilities/assessment_constants.py:24`
- **Status**: NEW (residual of closed #5795)
- **Age**: -11: `2ff93f25` 2025-12-15, `9f460102` 2026-02-14, `211cfaba` 2026-07-18; -14: various
- **Effort**: small
- **Description**: #5795 (`92fca886`, yesterday) created `loudness_targets.DEFAULT_TARGET_LUFS` for `-14.0`, whose commit message claims "-14 LUFS has two names". The same module's reason for existing ("changing either meant a grep") still applies: `get_default_genre_profile()` ("default" profile) and the `adaptive` preset still say `target_lufs=-14.0`, `FINGERPRINT_DEFAULTS['lufs']` is a bare `-14.0`, and `AssessmentConstants.TARGET_INTEGRATED_LUFS` (zero readers) plus `SPOTIFY/YOUTUBE/TIDAL_TARGET_LUFS = -14.0` are separate copies. Separately, the "loud master" anchor `-11.0` is `SimpleMasteringConfig.TARGET_LUFS` (used only for advisory evaluation, `simple_mastering.py:247`), `AdaptiveLoudnessControl.TARGET_LUFS` (drives makeup gain), and a literal in `soft_clip_params.py:36` that must move together with them to keep the soft-clip ramp anchored to the same loudness.
- **Evidence**: `loudness_factor = max(0.0, min(1.0, (-11.0 - unpacker.lufs) / 9.0))`; `TARGET_LUFS: float = -11.0` (mastering_config) vs `TARGET_LUFS = -11.0` (adaptive_loudness).
- **Impact**: Retuning the loud-master target requires editing three files with no link between them; the `-14` family is half-migrated, so `loudness_targets.py`'s docstring overstates its coverage.
- **Siblings**: `quality_metrics.py:53` and `loudness_assessment.py:25` both default `(-16.0, -14.0)`; `continuous_space.py:186` `_LUFS_CENTER = -14.3887` (a fitted value, leave).
- **Related**: #5795 (closed), #5858 (open, percent-vs-fraction fallbacks in `target_generator.py:272-275`, not duplicated here)
- **Suggested Fix**: Add `LOUD_MASTER_TARGET_LUFS = -11.0` to `dsp/utils/loudness_targets.py` and reference it from the three -11 sites; import `DEFAULT_TARGET_LUFS` in `genre_profiles.py`, `preset_profiles.py` and `fingerprint_unpacker.py`; delete the unused `TARGET_INTEGRATED_LUFS`.

#### TD4-06: The only production `PlayerConfig(...)` re-types six defaults; its docstring cites a deleted path
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis-web/backend/config/startup/components.py:174-183`; `auralis/player/config.py:19-26`
- **Status**: NEW (follow-on to closed #5421)
- **Age**: `89cb8dc3` 2026-09-14
- **Effort**: trivial
- **Description**: #5421 fixed the `buffer_size` default (4410 -> 1024) so it matches the one production caller. That left `PlayerConfig(buffer_size=1024, sample_rate=44100, enable_level_matching=True, enable_frequency_matching=False, enable_stereo_width=False, enable_auto_mastering=False, enable_advanced_smoothing=True, max_db_change_per_second=2.0)` as a full restatement of the constructor defaults. The comment in `config.py:20` still says "config/startup.py" (it is `config/startup/components.py` now). The "optimized config" comment above the call has no content.
- **Evidence**: every keyword at `components.py:175-182` equals the signature default at `config.py:19-31`.
- **Impact**: Changing a default does nothing for the shipped app, and the real tunable (sample rate, which #5729 shows the realtime chain never updates per track) looks configured when it is just the default repeated.
- **Siblings**: none.
- **Related**: #5421 (closed), #5729 (open, realtime chain not told the track rate)
- **Suggested Fix**: Replace the call with `PlayerConfig()`; fix the stale path in `config.py`.

#### TD4-07: The `1024 / 44100` / `512 / 44100` "time-anchored window" idiom is typed at five sites in three files
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis/dsp/utils/spectral.py:238-239`, `auralis/analysis/ml/feature_extractor.py:199-200`, `auralis/analysis/phase_correlation.py:233`
- **Status**: NEW
- **Age**: `dc7e7334` 2026-07-18, `526f5feb` 2026-09-14 (#5418)
- **Effort**: trivial
- **Description**: #4308/#5418 replaced bare sample-count windows with `frames_for_seconds(sr, 1024 / 44100)`. The fix hardcodes the 44.1 kHz reference rate as an inline division each time, and each site carries the same "1024/512 samples at 44.1kHz" comment. The onset analysis is itself implemented twice (`spectral.py` and `feature_extractor._onset_rate`) with identical window/hop.
- **Evidence**: `window_size = frames_for_seconds(sample_rate, 1024 / 44100)` / `hop_size = frames_for_seconds(sample_rate, 512 / 44100)` x2, plus `nperseg = frames_for_seconds(self.sample_rate, 1024 / 44100)`.
- **Impact**: One more analysis tuning the window has to copy a magic ratio; the two onset copies can diverge.
- **Siblings**: the three files above.
- **Related**: #4308, #5418 (closed)
- **Suggested Fix**: Define `ANALYSIS_WINDOW_S = 1024 / 44100` and `ANALYSIS_HOP_S = 512 / 44100` beside `frames_for_seconds` in `dsp/utils/spectral.py` and use them at all five sites; the Dim 3 audit should also fold the two onset implementations.

#### TD4-08: FFT size 4096 is a default in four config classes and a bare literal ~14 times in the feature extractor
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: defaults: `auralis/core/config/unified_config.py:40`, `auralis/dsp/eq/psychoacoustic_eq.py:41`, `auralis/analysis/spectrum_analyzer.py:28`, `auralis/analysis/spectrum_operations.py:49`; literals: `auralis/analysis/ml/feature_extractor.py:129-131,146,153-154,168,219,232,248-250,265,288-290` (4096 / 2049 / 8192), `auralis/dsp/utils/spectral.py:62,67`
- **Status**: NEW
- **Age**: `e116da5e` 2025-10-02 (feature_extractor)
- **Effort**: small
- **Description**: `UnifiedConfig.fft_size` is the sanctioned owner and does feed `EQSettings(fft_size=config.fft_size)` (`hybrid_setup.py:50`), so `EQSettings.fft_size = 4096` is a shadow default. `SpectrumSettings.fft_size = 4096` and `SpectrumOperations(..., fft_size=4096)` are only ever overridden (the one production caller passes 8192, `quality_metrics.py:68`), so those defaults are unused. `AssessmentConstants.DEFAULT_FFT_SIZE = 2048` has no reader. `feature_extractor.py` is the genre classifier's model input, where 4096/2049 are a feature contract, repeated rather than named, and `[:2049]` is `4096 // 2 + 1` typed by hand.
- **Evidence**: `spectrum = np.fft.fft(audio[:4096]); magnitude = np.abs(spectrum[:2049]); freqs = np.fft.fftfreq(4096, 1/self.sample_rate)[:2049]` (three copies of this triple).
- **Impact**: Changing the classifier's FFT length means 14 coordinated edits; the dead defaults mislead a reader about which size is live.
- **Siblings**: `resonance_notcher.py:90` `max(4096, ...)` (a floor, tracked by closed #4030).
- **Related**: #5244 (open, extractor hardcoded to 44.1 kHz)
- **Suggested Fix**: In `feature_extractor.py` add `_FFT_SIZE = 4096` and `_N_BINS = _FFT_SIZE // 2 + 1`; make `EQSettings`/`SpectrumSettings` fft_size required (or read `UnifiedConfig`'s default) and delete `DEFAULT_FFT_SIZE`.

#### TD4-09: Epsilon / dB-floor guards are typed inline as 1e-10 (~20 code sites), 1e-9 (x7), 1e-12 (x3) and 1e-8 (x3)
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: representative: `auralis/dsp/utils/conversion.py:57` (`to_db` floors at 1e-10), `auralis/dsp/dynamics/compressor.py:118`, `dsp/eq/spectrum_gains.py:74`, `dsp/eq/masking.py:58`, `analysis/loudness_meter.py:267-268`, `analysis/spectrum_weighting.py:44,76`, `analysis/ml/feature_extractor.py:169,192,228,257-259,273`, `core/hybrid_stage_dispatch.py:91`, `auralis-web/backend/core/level_manager.py:118`, `backend/core/audio_processing_pipeline.py:76,342`; 1e-9: `dsp/utils/stereo.py:68`, `core/processing/stage_snapshot.py:72`, `core/mastering_prepare.py:72`, `analysis/fingerprint/windowed_compute.py:109,113`; 1e-12: `core/dsp/resonance_notcher.py:107`, `stage_snapshot.py:53`, `scoring_ops.py:252`; 1e-8: `parameter_generator_eq.py:36,173`, `continuous_space.py:188`
- **Status**: NEW
- **Age**: n/a (spread over history)
- **Effort**: medium
- **Description**: The only named epsilon is fingerprint-local (`FingerprintConstants.EPSILON = 1e-10`, `metrics/constants.py:36`); `to_db` documents its 1e-10 floor in prose. #5785 unified the *scalar* amplitude->dB convention but not the array forms (`20 * np.log10(x + 1e-10)`), and "is this silent" tests use four different thresholds (`np.allclose(..., atol=1e-10)` in two layers, `std < 1e-9` in two copies of the same stereo-correlation guard, `total < 1e-12`).
- **Evidence**: `np.std(left) < 1e-9 or np.std(right) < 1e-9` in both `dsp/utils/stereo.py:68` and `core/processing/stage_snapshot.py:72`.
- **Impact**: No bug found; the cost is that "what counts as digital silence" has four answers (1e-8..1e-12, i.e. -160..-240 dB) and cannot be changed in one place.
- **Siblings**: see Location.
- **Related**: #5785 (closed, scalar half), Dim 3 (`_compute_phase_correlation` duplicates the stereo correlation helper)
- **Suggested Fix**: Add `AMPLITUDE_EPS = 1e-10` and an array `amplitude_to_db_array()` to `dsp/utils/conversion.py`; make `FingerprintConstants.EPSILON` alias it; convert the ~20 sites mechanically.

#### TD4-10: `FingerprintStorage.save` fabricates `sample_rate=44100` / `duration=0.0` when `_metadata` is absent, and `FingerprintService` never supplies it
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis/analysis/fingerprint/fingerprint_storage.py:105-107,118-119`; caller `auralis/analysis/fingerprint/fingerprint_service.py:169`
- **Status**: NEW
- **Age**: `583e0160` 2025-11-05
- **Effort**: trivial
- **Description**: The backend path stamps `_metadata` from a header probe (`backend/core/fingerprint_loading.py:222`), but `FingerprintService.get_or_compute` calls `FingerprintStorage.save(audio_path, fingerprint, {})` with `sr` in scope and no `_metadata`. Every sidecar written there records `"sample_rate": 44100, "duration_seconds": 0.0` regardless of the file. A grep shows nothing reads either field back today, so the damage is wrong data on disk rather than wrong audio.
- **Evidence**: `sample_rate = fingerprint.get('_metadata', {}).get('sample_rate', 44100)`.
- **Impact**: A future reader of these fields (e.g. a staleness or resample check) would trust a 44.1 kHz claim for a 96 kHz file.
- **Siblings**: none.
- **Related**: `/audit-engine` if the fields ever get a reader
- **Suggested Fix**: Make `save()` take `sample_rate`/`duration` explicitly (no default), pass `sr`/`len(audio)/sr` from `FingerprintService`, or drop the two fields.

#### TD4-11: Frontend playback constants hand-mirror backend constants and assume 48 kHz stereo
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis-web/frontend/src/services/audio/audioConstants.ts:20,28-34` (`minBufferSamples: 96000`, water marks 5 s / 8 s); `hooks/enhancement/useStreamStartWatchdog.ts:25` (`STREAM_START_WATCHDOG_MS = 45000`); fallbacks `services/audio/BufferScheduler.ts:229` and `WorkletOutput.ts:166` (`|| 44100`), `PCMStreamBuffer.ts:52` (`= 48000`)
- **Status**: NEW (the three differing fallbacks were noted as harmless in the 2026-10-21 report; the rest is new)
- **Age**: `6848315a` 2026-06-28, `1d898e97` 2026-08-26
- **Effort**: small
- **Description**: The start gate is a raw interleaved sample count (`96000`, "~1 s at 48 kHz stereo") compared against `getAvailableSamples()` in `AudioPlaybackEngine.startPlayback`, although sample rate and channels are known from stream metadata; at 96 kHz stereo it is 0.5 s, at 44.1 kHz mono 2.2 s. The water marks and the 45 s watchdog are justified only by comments referring to backend `CHUNK_INTERVAL = 10 s` and `CHUNK_PROCESS_TIMEOUT = 30 s + 5 s semaphore`; the backend's `audio_stream_start` already ships `chunk_duration`, which no frontend code consumes.
- **Evidence**: `minBufferSamples: 96000`; `export const STREAM_START_WATCHDOG_MS = 45000;` with "must exceed ... CHUNK_PROCESS_TIMEOUT = 30s, plus a 5s stream-semaphore wait" in the header.
- **Impact**: Changing a backend constant breaks a frontend invariant with no compile- or test-time signal; the start gate misbehaves for rate/channel combinations other than the one in its comment.
- **Siblings**: three sample-rate fallbacks listed above (44100, 44100, 48000).
- **Related**: `/audit-frontend` (start-gate behavior on tracks shorter than the gate)
- **Suggested Fix**: Express the gate as `minBufferSeconds` and multiply by `sampleRate * channels` at use; add one `BACKEND_STREAM_TIMING` block in `audioConstants.ts` that derives the watchdog from the named parts, or send the backend values in `audio_stream_start`.

#### TD4-12: Graceful-shutdown budgets (5 s + 10 s x3) are bare literals and exceed the Electron 2 s SIGKILL that governs them
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis-web/backend/services/scanner_watchdog.py:116` (`join(timeout=5)`), `services/library_auto_scanner.py:96` (`wait_for(..., timeout=10.0)`), `config/startup/shutdown.py:54` (`asyncio.wait(..., timeout=10.0)`), `analysis/fingerprint_generator.py:93` (`timeout: float = 10.0`); `desktop/main.js:488-503` (`setTimeout(..., 2000)` then SIGKILL)
- **Status**: NEW
- **Age**: `cc289d55` 2026-02-22 (desktop)
- **Effort**: small
- **Description**: The backend's teardown waits sum to 35 s worst case, each an inline literal with its own comment, while `AURALIS_SCAN_STOP_GRACE_SECONDS` is the only one named/env-tunable. The desktop wrapper sends SIGTERM and then SIGKILL after 2 s ("reduced from 5"), so any teardown step that actually needs its budget is cut off, including the late WAL checkpoint ordering the lifespan was reworked for (#4569, #4801). The two sides have no shared notion of the budget.
- **Evidence**: see Location; `desktop/main.js:487` "Force kill after 2 seconds (reduced from 5)".
- **Impact**: Tuning either side is guesswork; a slow shutdown becomes a hard kill that skips cleanup.
- **Siblings**: same four backend sites.
- **Related**: `/audit-integration` (is the WAL checkpoint reached within 2 s?)
- **Suggested Fix**: Add `SHUTDOWN_STEP_TIMEOUT_S` and `OBSERVER_JOIN_TIMEOUT_S` to `config/limits.py` (env-tunable like the scanner grace) and one `BACKEND_KILL_GRACE_MS` constant in the Electron wrapper documented against their sum.

#### TD4-13: Hard-coded hex colours outside the design system: crash screen (incl. the retired `#667eea`), dev logger palette, a dead test page
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis-web/frontend/src/index.tsx:25-26,54` (13 hex values: `#00d4ff` x2, `#1a1a1a`, `#fff`, `#ff6b6b`, `#ccc`, `#999`, `#222`, `#444`, `#667eea`, `#888`); `src/store/middleware/loggerMiddleware.ts:63-67,215,221` (7: Material-palette console colours); `auralis-web/frontend/public/mse-test.html:17,29,79` (`#667eea`, `#764ba2`); `components/shared/CacheStatsDashboard/StatCards.tsx:33-39` (`${color}33` hex-alpha concatenation)
- **Status**: NEW (the 2026-10-21 report counted 0 beyond TD4-07/#5801 and did not list these)
- **Age**: `be0f3619` 2025-11-22 (index.tsx)
- **Effort**: small
- **Description**: A full sweep of `src/` (excluding `design-system/`, tests) finds no `rgb()/rgba()` literal and only three hex-bearing production files; the rest of the 1,200 `#xxxx` grep hits are issue numbers in comments. `index.tsx`'s fatal-init fallback inlines a 700-char HTML string with ten off-token colours, including `#667eea`, the deprecated brand colour that #2356 and #2966 removed everywhere else (the design-system README still shows it too, `design-system/README.md:192,345`). `public/mse-test.html` ships in the build, is referenced by nothing (Dim 2), and carries the same colour. Data-driven `hsla(${hue}, ...)` in `AlbumCharacterPane/*` and `utils/fingerprintToGradient.ts` computes colour from fingerprint data and is not flagged.
- **Evidence**: `style="background:#1a1a1a;color:#fff; ... color:#667eea;cursor:pointer ..."` in `index.tsx:54`.
- **Impact**: The crash screen is the one UI that bypasses the light/dark theme and would not follow a brand-colour change; low frequency, so low cost.
- **Siblings**: counts per file above (index.tsx 13, loggerMiddleware 7, mse-test.html ~10, StatCards 1 pattern).
- **Related**: `/audit-frontend` Dim 5, #2356/#2966 (closed `#667eea` removals), Dim 2 for the orphan page
- **Suggested Fix**: Build the crash fallback from `tokens.colors.*` (importing the token module is safe pre-render) and delete `public/mse-test.html`; the logger palette is dev-only and can stay or move into `design-system/` as a `consolePalette`.

### Dimension 5: Stub Implementations

#### TD5-01: Twelve mixin "host must provide this" hooks are `raise NotImplementedError` methods; the same repo already has a cheaper, shadow-proof idiom
- **Severity**: LOW
- **Dimension**: Stub Implementations
- **Location**: `auralis/analysis/dynamic_range_dynamics.py:26-27`; `auralis/player/integration_library.py:28-32`; `auralis/player/queue_loading.py:25-29`; `auralis/player/gapless_prebuffer.py:35-36`; `auralis/player/components/queue_navigation.py:33-34`; `auralis/player/components/queue_shuffle.py:23-24`; `auralis/player/integration_reporting.py:38-39`; `auralis/library/metadata_editor/batch.py:22-23`; `auralis-web/backend/services/scanner_watchdog.py:76-77`; `auralis-web/backend/core/streamlined_lifecycle.py:23-24`
- **Status**: NEW
- **Age**: d67af1ae, 237d8bb6, b3fb7346, b9e92f9e, bea58c81, c7293b9a, ea535fbd, 96b3e02c, all 2026-10-22 (the #5833-#5839 splits); census was 0 on 2026-10-21
- **Effort**: small
- **Description**: Each split mixin calls a method that the composed host class defines (`self._notify_callbacks(...)`, `self.write_metadata(...)`, `await self._process_priorities()`, ...). To keep mypy happy the author wrote a real method whose body is `raise NotImplementedError`. I verified the host wins in every case: importing each composed class and walking its `__mro__`, `IntegrationManager._notify_callbacks`, `IntegrationManager.set_current_track`, `QueueController.add_track/_notify_changed`, `GaplessPlaybackEngine._load_audio`, `QueueManager._get_current_track_unlocked`, `MetadataEditor.write_metadata`, `LibraryAutoScanner.reload_config`, `StreamlinedCacheWorker._process_priorities` (bound at `streamlined_worker.py:108` as `= streamlined_tiers.process_priorities`) and `DynamicRangeAnalyzer._get_dynamic_range_recommendations` each resolve to the host class itself, never to a stub, and signatures are identical. So there is no MRO-shadowing bug and nothing reachable from a route or the player ends up in `NotImplementedError`. The cost is structural: (a) it is a *runtime* stub for a *typing-only* concern, so the declaration sits in `__dict__`, sits ahead of any sibling mixin that might later legitimately provide the method (that is exactly the hazard `player_queue_navigation_mixin.py:34-41` documents and avoids), and shows up in every `NotImplementedError` census as fake debt; (b) three hooks are declared twice in sibling mixins of the same host (`_notify_callbacks` in `LibraryLoadingMixin` and `PlaybackReportingMixin`; `_get_current_track_unlocked` in `QueueNavigationMixin` and `ShuffleMixin`), so a signature change touches two stubs plus the real method; (c) the repo has no single convention: 10 of 55 `*Mixin` classes use the stub-method idiom, 3 player mixins use bare `Callable[...]` annotations, and the rest declare only data attributes.
- **Evidence**:
  ```
  # stub idiom (this finding)                       # in-repo alternative that does NOT occupy the MRO
  auralis/player/queue_loading.py:25                auralis/player/player_queue_navigation_mixin.py:50-55
      def add_track(self, track_info) -> None:          # Provided by PlayerFileLoadingMixin.
          raise NotImplementedError                     load_file: Callable[[str], bool]
                                                        load_track_from_library: Callable[[int], bool]
  ```
  I also compiled both forms under mypy 2.4 in `/tmp/audit/auralis/tech-debt/scratch_5/m.py`: a bare `add_track: Callable[[dict[str, Any]], None]` annotation, and an `if TYPE_CHECKING: def add_track(self, t) -> None: ...` block, both type-check cleanly against a host that defines `add_track` as a real method, and neither adds a name to the mixin's `__dict__`.
- **Impact**: Fake debt in the stub census (the 2026-10-21 audit baseline of 0 is now 12 and will need the same explanation every run); a latent shadowing hazard if any hook is later moved from the host into a sibling mixin; duplicate declarations that drift when a signature changes; two idioms for one job in the same package.
- **Siblings**: all 12 sites above (`integration_library.py` x2, `queue_loading.py` x2, one each in the other eight files). Idiom already in use and not to be changed: `player_streaming_mixin.py:58` (`next_track`), `player_queue_navigation_mixin.py:52-55`, `player_file_loading_mixin.py:49`. Attribute-only mixins (no method hooks, nothing to do): the `cache/*_mixin.py` set, `fingerprint_loader_mixin.py`, `player_callbacks_mixin.py`, `player_properties_mixin.py`, `core/processing/continuous_*.py`, `dsp/eq/spectrum_gains.py`, `analysis/loudness_filters.py`, `analysis/fingerprint/normalizer_stats.py`, `services/fingerprint_queue_scaling.py`, `core/mastering_stage_delegates.py`, `core/chunk_disk_prune.py`, `core/processor_maintenance.py`. Subclass-the-base mixins (repositories on `BaseRepository`, `queue_*_mixin.py` on `QueueServiceBase`) need no hooks.
- **Related**: `LibraryLoadingMixin._get_repos` (`integration_library.py:34-36`) and `QueueLoadingMixin._get_repos` (`queue_loading.py:36-38`) are byte-for-byte the same two-line method; if Dim 3 does not already list it, fold it into a one-line call to `resolve_repository_factory` at both call sites or a shared helper. No owning-audit bug.
- **Suggested Fix**: Replace each of the 12 `raise NotImplementedError` methods with the bare `Callable[...]` annotation form already used by the player mixins (or one `if TYPE_CHECKING:` method block per mixin), delete the duplicate `_notify_callbacks` / `_get_current_track_unlocked` declarations from the second mixin of each pair by typing both mixins against one tiny `Protocol` per host, and record the chosen idiom in one sentence under CLAUDE.md "Patterns" so the next split follows it. Drop the `NotImplementedError` baseline expectation back to 0.

### Dimension 6: Test Hygiene

#### TD6-01: Zero-assertion CI gate is red at HEAD, and both assertion baselines carry stale entries
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/vendor/test_rust_panic_handler.py:97-110`; `weak-assertions-baseline.json`, `zero-assertions-baseline.json`
- **Status**: NEW
- **Age**: 44e4d433 2026-10-22 (the #5764 binding removal rewrote these tests)
- **Effort**: trivial (<=30 min)
- **Description**: `python scripts/check_weak_assertions.py --zero` exits 1 today ("3 test(s) assert nothing and are not baselined"). `backend-tests.yml:160-162` runs that exact command as a blocking step, so the job fails on a gate rather than on a test. The three offenders are `test_fingerprint_{nan,inf,empty}_audio_no_process_crash`. Before #5764 each was `result, exc = _call_and_catch(...)` followed by `assert isinstance(exc, RuntimeError)` (and an array-like check); the rewrite for `compute_fingerprint` kept the call and dropped the assertions. They are the #2225 "panic must not abort the process" regression tests, so they currently pass against any outcome except a hard crash. Separately both baselines are out of date: the default-mode baseline lists 37 and allows 37 but only 33 are still weak (4 stale: `test_boundary_advanced_scenarios.py::test_corrupted_audio_file_handling`, `::test_invalid_metadata_values`, `test_error_handling.py::test_error_cleanup_on_exception`, `test_similarity_api.py::test_build_graph_uses_to_thread`), and the zero baseline has 1 stale entry (`tests/test_hpss_rust_validation.py::test_audio_file`). Stale entries re-permit regressions of exactly those tests.
- **Evidence**: `tests/vendor/test_rust_panic_handler.py:100-110`: `nan_audio = np.full(44100, np.nan, dtype=np.float32)` / `_call_and_catch(lambda: auralis_dsp.compute_fingerprint(nan_audio, 44100, 1))` with no following assert. `python scripts/check_weak_assertions.py --zero` -> rc=1; `python scripts/check_weak_assertions.py` -> "+ 4 baseline entry(ies) no longer weak".
- **Impact**: CI red on a gate that is meant to be the ratchet; the Rust panic-containment tests cannot detect a regression in how a panic surfaces (RuntimeError vs. other exception type vs. silent success).
- **Siblings**: none (the other 31 zero-assertion tests are baselined "does not raise" tests).
- **Related**: #2225, #5764, #5807 (closed, introduced the zero gate)
- **Suggested Fix**: restore `result, exc = _call_and_catch(...); assert exc is None or isinstance(exc, RuntimeError)` in the three tests, then run `check_weak_assertions.py --update` and `--zero --update` to drop the 5 stale baseline entries.
- **Orchestrator spot-check**: `check_weak_assertions.py --zero` is a step in `.github/workflows/backend-tests.yml:162`, so this adds a second red step to that job, independent of the pytest baseline step.

#### TD6-02: Tautological assertions the ratchets cannot see (`assert True`, `or True`, `len(x) >= 0`)
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/edge_cases/test_filesystem_errors.py:270,560,590`; `tests/edge_cases/test_network_failures.py:113`; `tests/load_stress/test_concurrent_operations.py:462`; `tests/auralis/player/test_realtime_processor.py:263`; `tests/auralis/player/test_queue_changed_rearms_prebuffer_5583.py:119`; `tests/regression/test_detached_instance_error.py:334`; `tests/boundaries/test_library_operations_boundaries.py:599`
- **Status**: NEW
- **Age**: 770fbac0 2025-11-08 (filesystem), 4fa49f0b 2025-10-25 (realtime_processor); others older than the #5225/#5807 sweeps
- **Effort**: small (<=2 h)
- **Description**: Both gates count any `assert` as an assertion, so `assert True, "..."` and always-true comparisons satisfy them. #5286 and #5285 removed earlier `assert True` instances; these survived. Concretely: (1) `test_filesystem_errors.py` truncated-file, file-locking and delete-open-file tests end in `assert True, "Handled ..."` after computing `failed` / `can_write_while_reading` / `delete_succeeded` and never asserting them; (2) `test_network_failures.py:113` opens a raw `socket` to 169.254.1.1 and asserts `True` — it exercises no Auralis code at all (the `connected` variable is unused); (3) `test_concurrent_operations.py:462` runs 5 processor threads, collects `results`/`errors`, then `assert True`; (4) `test_realtime_processor.py:263` is `new_rms = matcher.reference_rms` followed by `assert new_rms != matcher.reference_rms or True` (compares a value to itself, then `or True`); (5) `test_queue_changed_rearms_prebuffer_5583.py:119` wraps a `_wait_until(...)` result in `or True` so the wait can time out unnoticed; (6) `assert len(album.tracks) >= 0` and `assert len(results) >= 0, "Should handle unicode search"` can never fail — the latter's own comment says "Should find the track", yet the track added one line earlier is never looked for.
- **Evidence**: `tests/auralis/player/test_realtime_processor.py:261-263`: `new_rms = matcher.reference_rms` / `assert new_rms is not None` / `assert new_rms != matcher.reference_rms or True  # RMS should be different or at least valid`; `tests/boundaries/test_library_operations_boundaries.py:595-599`: `track_repo.add(create_test_track(0, title="Track 日本語 🎵"))` ... `assert len(results) >= 0`.
- **Impact**: ten tests read as coverage for filesystem-error, concurrency, unicode-search and level-matcher behavior and cover none of it (the detached-instance one is the weakest: its loop body is the only check that `album.tracks` is eager-loaded and `len(...) >= 0` passes even for an empty list).
- **Siblings**: bool-type-only assertions with the same "ran without error" strength: `tests/auralis/player/test_enhanced_player.py:235,366,572` and `tests/auralis/player/conftest.py:127` (`assert isinstance(success, bool)`); extend `check_weak_assertions.py` to flag `assert True`, `... or True` and `len(...) >= 0` so the class stays at zero.
- **Related**: #5286, #5285, #5807, #5225 (all closed, same class, narrower scope)
- **Suggested Fix**: for each, assert the computed variable (e.g. `assert failed or result_audio is not None`, `assert len(results) == 1` for the unicode search, `assert new_rms != old_rms`), or delete the test if it only exercises the stdlib (`test_network_failures.py:113`); add the three patterns to the AST checker's zero-gate.

#### TD6-03: Phase-5C "dual-mode" tests assert on Mocks they configure themselves (about 41 tests, 68 collected)
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/backend/test_phase5c_example.py` (15 tests, whole file); `Test*DualModeParametrized` classes in `tests/backend/test_{albums_api.py:424, artists_api.py:647, main_api.py:1711, metadata.py:525, processing_api.py:867, processing_parameters.py:171, similarity_api.py:569}`; `tests/backend/test_api_endpoint_integration.py:536`; fixture `mock_data_source` at `tests/backend/conftest.py:487-506`
- **Status**: NEW
- **Age**: e991809a / b629c6ce 2025-12-12
- **Effort**: small (<=2 h)
- **Description**: The pattern is `source.albums.get_all = Mock(return_value=([a1, a2], 2))`, then `albums, total = source.albums.get_all(limit=50, offset=0)`, then `assert total == 2`. Nothing in Auralis runs; the tests verify `unittest.mock`. 27 tests take `mock_data_source` (parametrized over `"library_database"` and `"repository_factory"` = 54 collected); the "library_database" arm is documented as the retired `LibraryManager` (`conftest.py:492`, #4915 deleted it). `test_phase5c_example.py` states "These are example tests" and holds 11 more of the same shape plus `print(f"✅ ... passed for mode")`. `TestAPIEndpointDualMode` (3 tests) only asserts `hasattr` on fixtures defined in the same conftest. Related dead scaffolding in `test_metadata.py:40-47`: the autouse fixture `patch_track_repository` patches `auralis.library.repositories.TrackRepository`, but the metadata router never constructs a `TrackRepository` (the `client` fixture injects `mock_repository_factory` directly), so the patch wraps every test in that module and is a no-op.
- **Evidence**: `tests/backend/test_albums_api.py:441-470` (`source.albums.get_all = Mock(...)`; `albums, total = source.albums.get_all(limit=50, offset=0)`), `tests/backend/test_phase5c_example.py:1-15` ("Phase 5C Example ... These are example tests").
- **Impact**: ~41 green tests that inflate the 7,300-function count (CLAUDE.md "Codebase Map") and make the `phase5c` marker look like API coverage; the fixture docstring still instructs authors to write more of them.
- **Siblings**: `tests/integration/test_repositories.py:568` `TestDualModeCompatibility` (already known-broken, #4234); `tests/performance/test_phase5d_example.py` is real-DB and is not part of this finding. `mock_library_database` itself is still used by `test_files_api.py`, `test_streamlined_worker_*` and `test_artists_api.py` outside the dual-mode classes, keep it.
- **Related**: #5225 (closed, removed assertion-free tests but left these), #4915 (LibraryManager removal)
- **Suggested Fix**: delete the 8 `*DualMode*` classes, `test_phase5c_example.py`, the `mock_data_source` fixture, the `phase5c` marker (`pytest.ini:86`), and the autouse `patch_track_repository` in `test_metadata.py`; the endpoint behavior is already covered by the real-router tests in the same files.

#### TD6-04: Four shutdown tests patch `get_processor_factory`, which shutdown stopped calling in #5311
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/backend/test_player_state_manager_shutdown_4747.py:44`, `tests/backend/test_startup_rollback.py:245`, `tests/backend/test_shutdown_step_isolation.py:50`, `tests/backend/test_startup_worker_death_watchdog.py:205`
- **Status**: NEW
- **Age**: production change 90ceb0c2 2026-09-14 (#5311); the patch string was retargeted to `core.processor_registry` by 2fde5e80 2026-10-22 (#5833 split), which kept it alive instead of noticing it was inert
- **Effort**: trivial (<=30 min)
- **Description**: `config/startup/shutdown.py:112-114` clears caches via `from core.processor_registry import all_processor_factories` and `for processor_factory in all_processor_factories(): processor_factory.clear_cache()`. `get_processor_factory` is not referenced anywhere in `config/startup/`. The four tests still `patch("core.processor_registry.get_processor_factory", MagicMock())` as part of their `_run()` stubs, so the patch is a no-op and the real registry's factories are cleared on every shutdown test (a cross-test side effect, not isolation). The retargeting in the split commit is exactly how an inert patch survives a refactor.
- **Evidence**: `grep -n "get_processor_factory" auralis-web/backend/config/startup/*.py` -> empty; `shutdown.py:112`: `from core.processor_registry import all_processor_factories`.
- **Impact**: the isolation the stubs claim to give (no real processor factory touched) is not given; if `all_processor_factories()` ever raises, these tests would hit it unpatched.
- **Siblings**: the neighbouring patches in the same `_run()` blocks (`services.artwork_downloader.close_artwork_downloader`, `analysis.fingerprint_generator.shutdown_fingerprint_executor_bounded`) are lazy-imported by `shutdown.py` and are effective.
- **Related**: #5311, #5833
- **Suggested Fix**: replace the four patches with `patch("core.processor_registry.all_processor_factories", return_value=[])` (or drop them), and consider a shared `_shutdown_stubs()` helper since the block is repeated in all four files.

#### TD6-05: `AVAILABLE_PRESETS` is a production constant that only tests read, plus an inert patch of it
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `auralis-web/backend/core/proactive_buffer.py:22-25`; `tests/backend/test_silent_exception_swallowing_cluster.py:124`; `tests/backend/test_proactive_buffer_cancellation_5378.py:345,375`; `tests/backend/test_proactive_buffer_offload.py:67-84`
- **Status**: NEW
- **Age**: abb02d00 2026-10-22 (loop removed, constant kept); constant dates from 8a8bd5a4 2026-02-21
- **Effort**: trivial (<=30 min)
- **Description**: #5839 (abb02d00) removed the one-element `for preset in AVAILABLE_PRESETS` loop. The constant survives with a comment claiming it is "the list form other code and tests count against"; a grep shows no production reader (`buffer_presets_for_track` now uses `BUFFER_PRESET` directly). The tests are what remains: `test_silent_exception_swallowing_cluster.py:124` does `patch.object(pb, "AVAILABLE_PRESETS", ["adaptive"])` (replacing the list with an equal list, and nothing reads it), and four assertions multiply by `len(AVAILABLE_PRESETS)` (always 1), e.g. `assert processed == [0, 1] * len(AVAILABLE_PRESETS)`.
- **Evidence**: `proactive_buffer.py:23-25`: `# AVAILABLE_PRESETS stays as the list form other code and tests count against.` / `BUFFER_PRESET = "adaptive"` / `AVAILABLE_PRESETS = [BUFFER_PRESET]`; `grep -rn AVAILABLE_PRESETS auralis auralis-web/backend` -> only the definition.
- **Impact**: a constant kept alive for tests misleads the next reader into thinking per-preset buffering still exists; it is the pre-split pattern CLAUDE.md "no variants / no test-only shims" forbids.
- **Siblings**: none.
- **Related**: #5839 (open, the loop-removal issue this commit partly closed)
- **Suggested Fix**: delete `AVAILABLE_PRESETS` and the stale comment; in the three tests replace `len(AVAILABLE_PRESETS)` with the literal 1 and drop the no-op `patch.object`.

#### TD6-07: Skip guards that cannot fire in the monorepo, and failure-to-skip conversions
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: frontend-presence guards: `tests/backend/test_artist_created_at_contract_4833.py:102`, `test_artist_albums_key_contract_4752.py:77,88`, `test_album_tracks_key_contract.py:57`, `test_stream_epoch.py:224`, `test_readiness_and_stream_end_contracts.py:233`, `test_ws_broadcast_type_registry_contract.py:76` (skipif), `tests/regression/test_ws_connect_state_push.py:24`; data-count guards: `tests/backend/test_library_pagination_invariants.py:404-879` (12 sites), `tests/backend/test_api_endpoint_integration.py:416,422`
- **Status**: NEW
- **Age**: 19a41f86 2026-08-13 (guard style); 241512d5 2025-11-18 (api_endpoint)
- **Effort**: small (<=2 h)
- **Description**: Eight cross-layer contract tests (backend test reads a frontend file to assert the wire shape) skip when the file is missing, commented `# pragma: no cover - frontend not checked out`. The frontend lives in the same repo and checkout; all eight paths resolve today. Because the frontend was just split (#5840/#5841) and `api/transformers` and `types/ws` are active refactor areas, a rename turns the contract test into a silent SKIP and neither CI gate notices (both check only for new failures and a non-zero collected count). This is the class #5808 closed for first-party `ImportError`, one marker over. Second: `test_library_pagination_invariants.py` has 12 `if total == 0: pytest.skip("No albums/tracks in test database")` guards after fixtures whose docstring says they insert 100 tracks / 20 albums; #5810's body flagged these as convertible to `assert total > 0` and the issue closed without touching them. `test_api_endpoint_integration.py:416-422` converts "playlist creation returned non-2xx" and "could not parse playlist_id" into skips, so a broken create endpoint reads as skipped coverage. (`tests/auralis/analysis/fingerprint/test_similarity_system.py:110-263` has 8 more `Need at least N fingerprints` skips whose fixture populates them; defensive only.)
- **Evidence**: `test_artist_created_at_contract_4833.py:102-103`: `if not _FRONTEND_TRANSFORMER.exists():  # pragma: no cover - frontend not checked out` / `pytest.skip("frontend artistTransformer.ts not present")`.
- **Impact**: contract drift between backend and the React transformers (the most expensive class of integration bug here) can pass CI as "skipped" after a rename.
- **Siblings**: see Location (all listed).
- **Related**: #5808, #5810, #4969 (closed siblings); `test_no_unaccountable_skips_4691.py` only polices module-level `pytestmark` skips
- **Suggested Fix**: replace the existence checks with `assert path.exists(), "..."` (the repo always has the frontend), change `if total == 0: pytest.skip(...)` to `assert total > 0`, and make the playlist-create guard `assert create_response.status_code in (200, 201)`.

#### TD6-08: Tests that only run on the author's machine (personal library paths, a `/tmp` artifact from a script)
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/test_phase6_library_characterization.py` (4 tests, paths under `/mnt/audio/Audio/Remasters`), `tests/test_phase6_realworld_validation.py` (7 tests), `tests/test_phase25_2b_real_audio_validation.py` (1 test, module-level skipif on `/mnt/Musica/Musica/Blind Guardian`), `tests/backend/test_adaptive_mastering_weighted.py` (4 skipif tests), `tests/backend/test_adaptive_mastering_multistyle.py` (0 tests)
- **Status**: NEW (the closed #4047/#4251 fixed the zero-assertion form of the same files)
- **Age**: bff4f4f6 2025-11-17 (phase6), 6db68ec2 2026-09-16 (weighted)
- **Effort**: small (<=2 h)
- **Description**: 16 collected tests are skipped on every machine that lacks the developer's music directories (CI, any contributor, the clean checkout), and 4 of them (`test_adaptive_mastering_weighted.py`) gate on `Path("/tmp/multistyle_mastering_results.json")`, a file written only by running `tests/backend/test_adaptive_mastering_multistyle.py` as a script (`python test_adaptive_mastering_multistyle.py`; the module defines no `test_` function, so pytest collects 343 lines and zero tests). The weighted tests therefore depend on an undeclared side-effect file and cannot be satisfied by `pytest` alone.
- **Evidence**: `test_adaptive_mastering_weighted.py:18-21`: `@pytest.mark.skipif(not Path("/tmp/multistyle_mastering_results.json").exists(), reason="Requires multistyle mastering results. Run test_adaptive_mastering_multistyle.py first")`; `test_phase6_library_characterization.py:34`: `REMASTERS_DIR = Path("/mnt/audio/Audio/Remasters")`.
- **Impact**: 16 tests of "real-world validation" are invisible in CI and `-m "not slow"` runs; they inflate the test count in CLAUDE.md and can rot undetected (the phase6 files predate the preset narrowing and the 25D fingerprint changes).
- **Siblings**: none beyond the five files.
- **Related**: #4047, #4251, #5155 (closed)
- **Suggested Fix**: move the script `test_adaptive_mastering_multistyle.py` and the five dependent tests (or the whole group) to `scripts/` or `tools/validation/` (outside `testpaths = tests`), or mark them `@pytest.mark.local_library` with an opt-in env var and a registered marker so the skip is declared rather than ambient.

#### TD6-09: Three skipped slow tests are empty `pass` stubs
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/stress/test_large_library.py:71-76` (`test_library_scan_10k_files`), `tests/stress/test_large_library.py:468-473` (`test_24_hour_playback_session`), `tests/stress/test_processing_stress.py:74-79` (`test_batch_process_1000_files`)
- **Status**: NEW (yesterday's TD6 listed these as "documented slow-test skips ... acceptable"; they are acceptable as slow tests only if they have a body)
- **Age**: 8b9f0d70 2025-11-09
- **Effort**: trivial (<=30 min)
- **Description**: Each is `@pytest.mark.skip(reason="Very slow test ...")` over a body of comments and `pass` ("# Would simulate long playback session"). A skip reason of "slow" implies the test works when run; these cannot ever run. #5428 removed non-skipped bare-`pass` tests; these were exempted because they are skipped. The skips carry no issue reference, so the #4691 gate does not apply (it only checks module-level marks).
- **Evidence**: `test_large_library.py:468-473`: `@pytest.mark.skip(reason="Very long test (simulates 24 hours)")` / `def test_24_hour_playback_session(self):` / `# Would simulate long playback session` / `pass`.
- **Impact**: counted as skipped tests in the baseline (`skipped tests (py)` metric) and read as planned coverage; none is.
- **Siblings**: none.
- **Related**: #5809, #5428, #4767 (closed)
- **Suggested Fix**: delete the three stubs (the real 1k-file variants stay), or implement them behind `@pytest.mark.slow`.

#### TD6-10: Source-text pinning tests dictate production file structure (45 `inspect.getsource` files, 64 `read_text` files)
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/regression/test_sample_count_invariant.py:21-44`, `tests/auralis/core/test_post_limiter_invariants_5533.py:26-35`, `tests/auralis/core/test_hybrid_processor_close_4744.py:183-186`; effect on `auralis/core/hybrid_processor.py:9-19` and `loc-ceilings.json:51`
- **Status**: NEW
- **Age**: ebc760b3 2026-02-22 (source-pin tests); #5463/#5830 docstring
- **Effort**: medium (<=1 day)
- **Description**: 45 test files call `inspect.getsource` and 64 `read_text()` on production files to assert text (e.g. `"if processed.shape != target_audio.shape:" in source`, `"Releases nothing today" in HybridProcessor.close.__doc__`). The cost is already visible: `hybrid_processor.py`'s own docstring says `_process_adaptive_mode`/`_process_hybrid_mode` "stay inline rather than moving too: tests/regression/test_sample_count_invariant.py inspects their source directly" and that `close()`'s docstring is kept verbatim because "two tests assert specific substrings in it". The module is 359 lines (CLAUDE.md ceiling 300) and `loc-ceilings.json` still allows 415, so the waiver is both test-driven and 56 lines looser than the file. The same invariant (limiter must not change the sample count) already has a behavioral test (`test_reference_dispatch_raises_on_limiter_shape_change`), so the two `getsource` tests are redundant with `test_post_limiter_invariants_5533.py::_SITES`.
- **Evidence**: `hybrid_processor.py:9-12` ("tests/regression/test_sample_count_invariant.py inspects their source directly via `inspect.getsource()`, so the sample-count assertion has to live in the bound method's own body").
- **Impact**: refactors that preserve behavior fail these tests (or, worse for negative `... not in source` assertions, pass them vacuously after the code moves out of the inspected function); splitting is blocked by test text rather than by design.
- **Siblings**: ~35 negative `assert "<text>" not in source` tests (list via `grep -rn "not in source\|not in src" tests`), notably `tests/backend/test_system_api.py:945-953`, `test_enhanced_seek_accuracy.py:240,293`, `test_startup_temp_sweep_ownership.py:93,108,330`.
- **Related**: Dim 9 (complexity/ceilings); #5463, #5830
- **Suggested Fix**: replace the two `test_sample_count_invariant.py` source greps with behavioral tests that monkeypatch the limiter to drop a sample and assert `RuntimeError` (the pattern already in `test_post_limiter_invariants_5533.py:38-60`), delete the docstring-substring test, then lower the `hybrid_processor.py` ceiling to its real size.

### Dimension 7: Stale Documentation

#### TD7-01: Architecture overview and data-flow still describe the retired gRPC fingerprint server, equal-power crossfade and Rust HPSS/pitch
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `docs/architecture/overview.md:34,65,71-73`; `docs/architecture/data-flow.md:33,44-45,62-70`; `docs/architecture/module-map.md:17`
- **Status**: NEW
- **Age**: `dbb3b4a5` 2026-07-11 (the docs rebuild wrote these; the gRPC server was deleted in #4533, crossfade in #4642, Rust HPSS/YIN bindings in #5764 on 2026-10-22)
- **Effort**: small
- **Description**: The three docs that `docs/README.md` names as the "spine" of the developer docs contradict the subsystem docs and the code. They say: the Rust layer is "PyO3 + gRPC fingerprint svc" with "a standalone gRPC fingerprint server as the primary extraction path" (overview.md:34,72; module-map.md:17); chunks are "crossfaded with equal-power curves so there are no audible seams" and `PCMStreamBuffer.write (... crossfade at boundaries)` (overview.md:65, data-flow.md:33,44); the heavy analysis DSP "(harmonic/percussive separation, pitch detection, chromagram ...) runs in Rust" (overview.md:71); fingerprint extraction tries "Rust gRPC server (port 8766) -> native 25D (primary)" then a "Python analyzer (<=300 MB) fallback" (data-flow.md:67-68). In the code: no gRPC anywhere (`git grep -i "8766\|grpc" -- auralis auralis-web/backend vendor` is empty), `dsp-engine.md:192` and `fingerprinting.md:160` say the server was removed, emitted chunks are 10 s non-overlapping segments with no crossfade (`chunked_processor.py:8`, `dsp-engine.md:240`, `PCMStreamBuffer.ts:35`), and `py_bindings.rs` registers only `compute_fingerprint` and `process_chunks`. Gate scope: `docs/architecture/*.md` is STRICT, so the gate reports these docs "clean" while they are wrong.
- **Evidence**: `overview.md:72`: "with a standalone gRPC fingerprint server as the primary extraction path. **There is no Python fallback**"; `data-flow.md:67`: "2. Rust gRPC server (port 8766) -> native 25D (primary)"; versus `dsp-engine.md:192`: "Standalone gRPC fingerprint server -- **removed**".
- **Impact**: A new contributor or an audit agent reading "the spine" first designs against a server and a crossfade that do not exist (the audit tooling already has a Retired Architecture table precisely because this happens). Two docs in the same strict-scope set give opposite answers.
- **Siblings**: `docs/subsystems/frontend.md:198,205` ("append w/ crossfade", "applies a linear crossfade blend at chunk boundaries"; code says none, #4642); `docs/subsystems/backend-api.md:188` ("see dsp-engine.md section 6 for crossfade math", which says "There is no crossfade math"); `docs/features/cache-system/CHUNK_AND_CACHE_ARCHITECTURE.md:20,27` (self-labelled "Current / code-verified": "overlap ... for equal-power crossfade" and an in-memory `SimpleChunkCache` in `audio_stream_controller.py`, deleted #5492); root `ARCHITECTURE.md:33` ("Crossfade between chunks for gapless playback"); `docs/subsystems/frontend.md:91` lists `useFingerprintCache` (hook deleted today, `ef0c6464`; `hooks/fingerprint/index.ts` says "no client-side fingerprinting or cache").
- **Related**: #4324, #4988, #5053 (closed, earlier rounds of the same chunk-model drift); #4642, #5776 (crossfade removal); #4533 (gRPC server removal).
- **Suggested Fix**: Rewrite the 8 sentences to the current model (in-process `compute_fingerprint`; 10 s tiled segments, no crossfade; data-flow step 2 becomes "sidecar -> in-process Rust -> Python fallback" per `fingerprint_extractor.py`), and delete the siblings' crossfade clauses and `useFingerprintCache`. One pass, same commit.

#### TD7-02: module-map.md describes a pre-streamlining layout (deleted modules, wrong dirs and counts)
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `docs/architecture/module-map.md:17,19,32,39-40,43,55,60,77,79-80,102,113,138`; `docs/architecture/overview.md:26,119`
- **Status**: NEW
- **Age**: `dbb3b4a5` 2026-07-11 (`module-map.md:55` still lists the learning engine deleted in #5763 2026-10-22)
- **Effort**: small
- **Description**: The doc's own header says "Counts are approximate ... trust the tree", but it also states structure that is simply false. Verified against the tree: `dsp/stages.py` ("Legacy Matchering reference matcher") was deleted in #4867; `mastering_branches/` is described as "Material-classified mastering branches" but is continuous-only (`continuous.py` + `soft_clip_params.py`; classification retired); `analysis/content/` does not exist (59 files, doc says 57); `learning/` is documented as "Preference engine, reference analysis" but holds only `reference_seeder.py` since #5763/#5765; `utils/` is "Logging, helpers, preview creator" but `helpers.py` (#5777) and `preview_creator.py` (#4277) are gone; `config/startup.py` is now a `startup/` package (#5236); `routers/` is "~23 route modules (... wav_streaming ...)" with no `wav_streaming` anywhere and 75 router modules (76 files with `__init__.py`) of which 20 are registered; `main.tsx` ("is stale -- ignore it") no longer exists; components "265 .tsx" (283 tracked, 195 non-test); the tests section names "18 subdirectories" and lists `unit`, `boundary`, `load`, none of which exist (live: 16 dirs, `boundaries`, `load_stress`, no `unit`). `overview.md:26` says "19 routers" (20 registered) and `overview.md:119` names `migration_manager.py` as the schema-version source of truth though it only imports `__db_schema_version__` from `auralis/__version__.py`.
- **Evidence**: `ls auralis/dsp` -> no `stages.py`; `ls auralis/learning` -> `reference_seeder.py`; `git grep wav_streaming -- auralis-web/backend` -> only the agent note saying there is none.
- **Impact**: `docs/README.md` sends newcomers here to "find where code lives on disk"; half the entries for `auralis/` lead to nothing. Because the file is in the STRICT gate set, the clean gate output lends it credibility it has not earned.
- **Siblings**: CLAUDE.md Codebase Map has the same class of errors (TD7-06).
- **Related**: #5815 (closed; fixed numeric counts in a different set of files), #4055 (closed, same file family).
- **Suggested Fix**: Regenerate the three `auralis/` and backend trees from `ls` (trim to the directories that matter, drop all counts except those `check_doc_counts.py` prints) and fix the tests paragraph to "16 subdirectories under tests/ (`ls tests`)".

#### TD7-03: dsp-engine.md documents `HybridProcessor.process_realtime_chunk()` -> `RealtimeDSPPipeline`, neither of which exists
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `docs/subsystems/dsp-engine.md:36-52,185`; `docs/architecture/data-flow.md:25`
- **Status**: NEW
- **Age**: `dbb3b4a5` 2026-07-11 (RealtimeDSPPipeline deleted #4873 2026-08-14; PyO3 0.29 bump #5485 2026-09-17)
- **Effort**: trivial
- **Description**: Section 2's call tree ends with `HybridProcessor.process_realtime_chunk()  # real-time chunk (:406) -> RealtimeDSPPipeline.process_chunk()  # low-latency path`, and "Mode selection" lists a "Latency axis -- offline (`process()`) vs real-time (`process_realtime_chunk()`)". `HybridProcessor` has no such method (its methods: `process`, `_process_impl`, `_process_{reference,adaptive,hybrid}_mode`, `set_*`, `reset_*`; `process_realtime_chunk` exists only on `PsychoacousticEQ`), and `RealtimeDSPPipeline` was deleted in #4873, which the same doc's section "Deleted paths" and line 29-30 record. The same sentence says it "instantiates **four mode processors**" and the table beneath lists three. `data-flow.md:25` repeats `HybridProcessor.process_realtime_chunk / process()` for the enhanced-playback hot path. `dsp-engine.md:185` says "PyO3 0.23 + numpy 0.23"; `Cargo.toml:20-21` pins `0.29` (#5485).
- **Evidence**: `git grep -n "def process_realtime_chunk" -- auralis` -> `auralis/dsp/eq/psychoacoustic_eq.py:161` only.
- **Impact**: The doc that tells readers "do not conflate the two pipelines" shows a real-time entry point a reader will search for and not find; the streaming hot path in `data-flow.md` is traced through a method that is not called.
- **Siblings**: `dsp-engine.md:23,24,37,56,57,69,93,96,128,130,137,225,237,251,302` line anchors (see TD7-04).
- **Related**: #4873 (closed, the deletion); #5485 (closed, pyo3 bump).
- **Suggested Fix**: Delete the `process_realtime_chunk` branch and the "Latency axis" bullet, say "three mode processors", point data-flow step to `HybridProcessor.process()` via `ContinuousMode`, and change "0.23" to "0.29".

#### TD7-04: Hard-coded `file.py:NNN` anchors in subsystem docs point at unrelated lines
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `docs/subsystems/dsp-engine.md:23,24,37,56,57,69,93,96,128,130,137,225,237,251,302`; `docs/subsystems/backend-api.md:24,31,129,169,178`; `docs/subsystems/fingerprinting.md:17,19,21,35,40,45,124,125,155,169,188`
- **Status**: NEW
- **Age**: `dbb3b4a5` 2026-07-11; broken progressively by the #5831-#5841 splits
- **Effort**: small
- **Description**: 31 markdown links carry a literal line number. Measured today, at least 13 land on the wrong thing: `hybrid_processor.py:44` is an import (class is at :60), `:54` is a comment (constructor :93); `simple_mastering.py:40` is an import (class :44); `continuous_mode.py:83` is a statement (class :38); `adaptive_mode.py:33` is blank (class :34); `processor_factory.py:53` is inside a docstring (class :45); `chunk_boundaries.py:37` is a docstring line (function :26); `unified_config.py:22` is a comment (class :30); backend `main.py:97` is `lifespan = create_lifespan(deps)` (`globals_dict` is :57); `config/app.py:28` is blank (`create_app` :53); `ws_handlers/connection.py:33` is blank (`setup_connection` :96); `config/globals.py:46` is an import (`ConnectionManager` :88); `fingerprint_service.py:387` is past EOF (file is 264 lines; `fingerprinting.md:45`). Several more are off by a few lines. The gate checks the path half of each link and passes.
- **Evidence**: `fingerprinting.md:45`: "`< 25` dims are discarded, not cached ([`fingerprint_service.py:387`](...))" vs `wc -l fingerprint_service.py` = 264.
- **Impact**: Every future split or edit silently re-breaks them (this round's 11 splits did). `_audit-common.md` and CLAUDE.md already instruct "grep the symbol -- line numbers drift"; these docs are the one place that still does the opposite.
- **Siblings**: `dsp-engine.md:39-47` inline `(:220) (:298) (:323) (:379)` in the call tree.
- **Related**: TD7-03; #5815.
- **Suggested Fix**: Replace every `:NNN` suffix with a symbol name (`hybrid_processor.py` -> `HybridProcessor`), the convention the audit commands already use (`file.py::symbol`), and add a 10-line check to `_audit-validate.sh` that rejects `\.(py|ts|tsx|rs):[0-9]+` inside the strict doc set.

#### TD7-05: Root ARCHITECTURE.md is the pre-2026-01 hierarchy (deleted classes, wrong repo count, nonexistent path) and sits outside the gate
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `ARCHITECTURE.md:13-36,47-50,53-56,115-121,166,200-210`
- **Status**: NEW
- **Age**: `85b5d4fd` 2026-01-03 (created); never reconciled since
- **Effort**: small
- **Description**: `docs/README.md:91` links it as the "processor-hierarchy summary", `WEBSOCKET_API.md:975` links it as "Architecture Overview", and no gate globs include it. It states: `ContinuousMode` is "Continuous learning mode" (it is the stateless fingerprint -> 3D-space default path; learning was removed #5763); "Crossfade between chunks for gapless playback"; "**Deprecated**: `ProcessorManager` - Replaced by ProcessorFactory" (class and file are gone; `processor_factory.py:7` already narrates it in past tense); an "Optimization Layer" whose example is "**ParallelProcessor** - Multi-threaded batch processing" (deleted #4565; the layer is now only `performance_optimizer.py` + profiling); a "**BatchProcessor** - Bulk fingerprint extraction" under the scanner (the scanner no longer extracts fingerprints; the phase was deleted in #4648); `Manager ... Example: LibraryManager (deprecated - use RepositoryFactory)` (deleted #4915); "`AlbumRepository`, `FingerprintRepository` -- all 14 extend `BaseRepository`" (12 repositories); and a FingerprintQueue entry citing `auralis-web/backend/fingerprint_queue.py` (the file is `auralis-web/backend/analysis/fingerprint_queue.py`). The "Architecture Evolution" section is a 2026-01 progress log with checkmarks.
- **Evidence**: `ls auralis/optimization` -> `performance_optimizer.py`, `profiling/`; `git ls-files auralis-web/backend/fingerprint_queue.py` -> empty.
- **Impact**: It reads as authoritative (root of the repo, linked from the doc hub) and teaches the exact retired architecture the audit protocol warns against, plus a "Manager" naming rule whose only example is deleted.
- **Siblings**: none (other root docs: `README.md`, `FIRST_TIME_SETUP.md` verified current).
- **Related**: #5030 (closed; AGENTS.md rot, same family), TD7-01.
- **Suggested Fix**: Either delete it and repoint the two links at `docs/architecture/overview.md`, or cut it to the naming-convention and repository/DI rules (sections "Service Architecture" and "Naming Conventions") and add it to the STRICT list in `_audit-validate.sh`.

#### TD7-06: CLAUDE.md Codebase Map: 18 test subdirs (16), 55 analysis files (59), nonexistent analyzers/ and utilities/, "realtime pipeline", "neural nets", "streaming" router
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `CLAUDE.md:92,100,102,104,106,141,164`; `docs/architecture/module-map.md:19`; `README.md:10`
- **Status**: NEW
- **Age**: `3e44f533` 2026-02-12 (analyzers/utilities/neural nets), `c333adb1` 2026-07-06 (processing row), `2030b97d` 2026-10-22 (test line, edited yesterday and still wrong)
- **Effort**: trivial
- **Description**: `CLAUDE.md:164` says "across 18 subdirs"; `ls tests` has 16 directories (`_audit-common.md:56` says 16, correctly; `module-map.md:19` repeats 18). `CLAUDE.md:100` "largest module, 55 files" -> 59 (`check_doc_counts.py` prints 59, `_audit-common.md` says 59). `CLAUDE.md:102,104` list `fingerprint/analyzers/` ("Batch & streaming analyzers") and `fingerprint/utilities/` ("DSP ops, backend selection"); neither directory exists (only `metrics/` does). `CLAUDE.md:92` lists a "realtime pipeline" under `core/processing/` (deleted #4873). `CLAUDE.md:106` calls `ml/` "Genre classification (neural nets)"; it is `RuleBasedGenreClassifier` (`module-map.md:44` and `fingerprinting.md:180` both say not a neural net). `CLAUDE.md:141` lists a "streaming" router; there is none (`config/routes.py` registers processing, health, system, settings, files, enhancement, artwork, playlists, library, tracks, library_scan, fingerprint_status, metadata, albums, artists, player, cache, similarity x2, fingerprint_queue). `README.md:10` badge says backend tests "~5,400" vs 7,112 pytest functions live.
- **Evidence**: `ls -d tests/*/ | wc -l` = 16; `ls auralis/analysis/fingerprint` has no `analyzers`/`utilities`.
- **Impact**: CLAUDE.md is loaded into every agent session; a wrong layout here sends file searches to nonexistent directories. The "Structural counts ... run check_doc_counts.py" note exists, yet the script cannot catch these (see Related).
- **Siblings**: the CLAUDE.md/`_audit-common.md` test-function/file lines (7,300/706 vs 7,112/709) are within tolerance and not counted here.
- **Related**: #5815, #4401, #4055 (closed; each fixed that round's numbers and the subdir count drifted again). Root cause: `scripts/check_doc_counts.py` `--check-docs` re-parses only `TEST_COUNT_LINE_RE` plus the repo count.
- **Suggested Fix**: Fix the 7 lines now; then extend `check_doc_counts.py --check-docs` to also assert the "N subdirs", "N files" (analysis) and "N registered routers" numbers it already computes, exact-match, so the next split cannot drift them silently.
- **Merge note**: absorbs TD10-05 (Dim 10 reached the same CLAUDE.md:100/:164 counts from the skill side: 55 analysis files vs 59 live, 706 test files vs 709, ~7,300 functions vs 7,112, 18 subdirs vs 16; `scripts/check_doc_counts.py --check-docs` validates neither the analysis-file nor the subdir count, which is why it reports "current"). Fix the text and extend the checker in the same change.

#### TD7-07: WEBSOCKET_API.md: wrong `subscribe` signature, nonexistent APIs and log names, wrong volume scale, incomplete `queue_changed` actions
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `auralis-web/backend/WEBSOCKET_API.md:3-4,70-110,132-178,586-587,760-776,807-847,857,865-896`
- **Status**: NEW
- **Age**: `e9f70a3c` 2025-10-23 (most of the payload and debugging sections); `4ee21e87` 2026-06-28 (queue_changed line)
- **Effort**: small
- **Description**: The message-type list matches the code (all 34 types in the union are present and `test_ws_type_registry_drift_4680.py` guards that), but shapes and the usage sections drifted. (1) The "Subscription Example" calls `subscribe(['playback_started', 'playback_paused'], cb)`; `WebSocketContext.tsx:66` is `subscribe(messageType: WebSocketMessageType, handler)`, single type; and the Debugging Tips use `subscribe('*', ...)` -- there is no wildcard, the API is `subscribeAll`. (2) "Connection Manager" documents `send_personal(message, websocket)`; `ConnectionManager` has `connect`, `disconnect`, `broadcast` and no `send_personal` (only this doc contains the name). (3) Debugging tips: `localStorage.setItem('debug_websocket', 'true')` and `logging.getLogger("auralis.websocket")` appear nowhere in code (grep finds only this file); `auralis-backend.log` / `grep "WS:"` likewise. (4) `volume_changed` is documented `volume: number // 0.0 - 1.0`; `VolumeChangedPayload.volume` is `int` on the 0-100 scale (the doc's own line 752 says "a 0-100 `volume`"). (5) `playback_started/paused/stopped`, `track_changed`, `position_changed`, `volume_changed` payload blocks omit `seq` (all payload TypedDicts in `outbound_messages.py:60-92` carry it), and `track_changed` shows `"next" | "previous"` while code emits `"next" | "previous" | "jumped"` plus `track_index`. (6) `queue_changed` action is listed as 4 values; `QueueChangeAction` has 7 (adds `shuffled`, `unshuffled`, `undo`; `types/ws/queue.ts:43` agrees with the code). (7) Header "Status: Phase 0.2 Complete", a "Phase 0.2 Completion Summary" file-change log and "Future Work: Phase 0.4 ... ~40 broadcast locations" are project-management residue in a reference doc (`outbound_messages.py` `broadcast_typed` already standardised the envelope).
- **Evidence**: `WebSocketContext.tsx:66-67`: `subscribe: (messageType, handler)` and `subscribeAll: (handler)`; `outbound_messages.py:16-23` `QueueChangeAction`.
- **Impact**: The doc is a STRICT-scope "authoritative" API reference; copy-pasting its subscribe example fails type-check, and the 0.0-1.0 volume note invites a scale bug in any new consumer.
- **Siblings**: none outside this file.
- **Related**: #5476, #4988, #4991, #4058, #4680 (closed rounds on this file); route payload-shape correctness to `/sync-contracts`.
- **Suggested Fix**: Replace the example with `subscribe('playback_started', cb)` and a `subscribeAll` snippet, delete `send_personal`, the debug-flag/logger lines and the Phase 0.2/0.4 sections, correct volume/`seq`/`jumped`/queue actions, and drop "Status"/"Last Updated" from the header (git has both).

#### TD7-08: Docstrings and comments cite renamed or deleted symbols and Rust modules
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `auralis/core/config/unified_config.py:120`; `auralis/library/scanner/scanner.py:66-68`; `auralis/core/processing/base/compression_expansion.py:23`; `auralis/io/results.py:31`; `auralis/dsp/utils/spectral.py:206-210`; `auralis/core/hybrid_stage_dispatch.py:62-64`; `vendor/auralis-dsp/src/fingerprint_compute.rs:323-335`; `tests/auralis/dsp/test_short_audio_no_crash_4520.py:24-25`; `tests/auralis/test_audio_processing_invariants.py:494-495`
- **Dimension**: Stale Documentation
- **Status**: NEW
- **Age**: `7e9c401f` 2026-08-14 (unified_config), `5b43e875` 2026-08-21 (scanner), `2f6bde0d` 2026-07-30 (compression_expansion), `0089780c` 2026-06-02 (results), `3288441d` 2026-08-20 (spectral), `22d0228c` 2026-09-16 (hybrid_stage_dispatch), `b03bf54e` 2026-08-13 (fingerprint_compute.rs); the Rust files they cite were deleted by #5764 on 2026-10-22
- **Effort**: trivial
- **Description**: Each comment names a symbol that has no definition anywhere in the tree (verified by grep): `ProcessorFactory.get_or_create_for_config` (renamed `get_or_create_from_config`, `processor_factory.py:253`); `LibraryAutoScanner._run_scan_cycle` (the enqueue now lives in `LibraryAutoScanner._do_scan` -> `auto_scan_events.enqueue_added_for_fingerprinting`, and `routers/library_scan.py` now only imports it from `library_scan_events.py` after #5832); `ContinuousMode._convert_targets_to_parameters` (now `fixed_target_params.convert_targets_to_parameters`); `simple_mastering.process_to_file` (no such function; the saver is `io/saver.py::save`); `tempo.rs::detect_tempo` "is therefore an unused binding" (file and binding deleted in #5764; the same docstring two lines earlier already says "has since been deleted"); `hpss.rs short-circuits below one FFT frame` (`hybrid_stage_dispatch.py:63`, two tests); and the whole "Relationship to `tempo::detect_tempo` (#4599)" doc block above `estimate_tempo` in `fingerprint_compute.rs`, which argues about a sibling implementation in `tempo.rs` that no longer exists. `tests/auralis/dsp/test_short_audio_no_crash_4520.py:24` also says `TestRustHpssShortSignal` "pins that so it cannot silently regress"; that class does not exist in the file (classes: `TestPadlenHelper`, `TestStereoWidthOnShortAudio`, `TestHybridProcessorShortAudio`).
- **Evidence**: `git grep -n "get_or_create_for_config\|_run_scan_cycle\|process_to_file\|_convert_targets_to_parameters" -- auralis auralis-web/backend` -> only the comments.
- **Impact**: Each is a "see X" pointer that dead-ends; the Rust block is ~13 lines justifying code that no longer has a counterpart, which invites someone to "re-unify" two implementations that are now one.
- **Siblings**: `docs/development/PYTHON_3_13_vs_3_14_COMPATIBILITY.md:225` ("every array-accepting entry point (`limit`, `compress`, `envelope_follow`, ...) returns normally") verifies bindings removed in #5764.
- **Related**: #5764, #5832, #5463 (closed); `auralis-web/backend/routers/library_scan_events.py:114` and `services/auto_scan_events.py:88` both define `enqueue_added_for_fingerprinting` with different signatures -> `/audit-tech-debt` Dim 3 candidate (not a Dim 7 item).
- **Suggested Fix**: One commit: rename the 4 Python symbols in the comments, delete `spectral.py:206-210` and the `tempo.rs` block in `fingerprint_compute.rs`, and reword the three `hpss.rs` mentions to past tense or drop them.

#### TD7-09: Hard-coded product versions disagree with `auralis/version.py`
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `auralis-web/frontend/src/index.tsx:31`; `desktop/preload.js:48`; `auralis-web/backend/schemas/system.py:32`
- **Status**: NEW
- **Age**: `19ae0a6e` 2025-11-17 (index.tsx); noted as known drift in `docs/subsystems/frontend.md:246` (and `overview.md:116` tells readers to ignore "the frontend constant") but never fixed
- **Effort**: trivial
- **Description**: All five manifests agree on 1.5.1 (`package.json` x3, `pyproject.toml`; `Cargo.toml` is the independent crate version 0.1.0 and is fine). Three hard-coded strings do not: `window.__AURALIS_DEBUG__ = { ..., version: '1.0.0-beta.13' }` is built into every renderer boot (`index.tsx:28-32`; `types/window.d.ts:11` types it as the app version); `desktop/preload.js:48` exposes `version: process.env.npm_package_version || '1.0.0'` (`npm_package_version` is not set in a packaged Electron app, so the fallback is what ships; `electronAPI.version` has no consumer); `schemas/system.py:32` uses `'1.2.1-beta.1'` as the field example. `sync_version.py` does not touch any of them. `MIN_CLIENT_VERSION = "1.0.0"` in `backend/version.py` is a policy value and is not flagged.
- **Evidence**: `index.tsx:31` `version: '1.0.0-beta.13'`; `auralis/version.py:8` `__version__ = "1.5.1"`.
- **Impact**: A bug report's debug blob says beta.13; two docs call this out as "Version drift" yet it persists, which is the signature of an item that nobody owns.
- **Siblings**: `auralis-web/frontend/src/test/mocks/handlers.ts:713` (`'1.0.0-beta.10'` mock; fine, mock data).
- **Related**: #4052, #4051, #4287, #4628 (closed version-drift precedents); #5383 (closed, `version.py` helpers).
- **Suggested Fix**: Vite `define: { __APP_VERSION__: JSON.stringify(pkg.version) }` (package.json is already kept in sync by `sync_version.py`) and use it in `index.tsx`; read the version from `app.getVersion()` in main and drop the unused `preload.js` field; change the schema example to `'1.5.1'`; delete the two "Version drift" caveats.

#### TD7-10: 21 phase/week report markdowns (8,140 lines) live under auralis-web/ outside every doc gate and describe deleted components
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `auralis-web/PHASE_7_ARCHITECTURAL_FIX.md`, `auralis-web/PHASE_7_VIEWING_GUIDE.md`; 14 files `auralis-web/frontend/*.md` (`FRONTEND_TEST_ANALYSIS.md`, `TEST_GAPS_AND_QUICK_WINS.md`, `WEEK5_MSE_STREAMING_TESTS.md`, `WEEK4_WEBSOCKET_TESTS_COMPLETE.md`, `PHASE_2_TESTS_COMPLETE.md`, `PHASE_3_TESTS_COMPLETE.md`, `PHASE3_*`, `REFACTORING_COMPLETION_REPORT.md`, `TRANSFORMATION_LAYER*.md`, `TEST_*SUMMARY*.md`, `COMPLETE_FRONTEND_TESTING_SUMMARY.md`); `auralis-web/frontend/docs/PHASE3C_ERROR_HANDLING_GUIDE.md`; `auralis-web/frontend/src/{PHASE1,PHASE2}_COMPLETION_REPORT.md`, `src/REFACTORING_PLAN_ComfortableApp.md`, `src/components/library/Items/REFACTORING_SUMMARY.md`, `src/components/player/PHASE4_UI_COMPONENTS_PLAN.md`, `src/tests/MSW_QUICK_START.md`, `src/tests/integration/LIBRARY_MANAGEMENT_TEST_RESULTS.md`
- **Status**: NEW
- **Age**: mostly Nov-Dec 2025 (`48bed341` 2025-12-01 and earlier)
- **Effort**: small
- **Description**: `_audit-validate.sh` globs cover `.claude/**`, a short list of root docs, `docs/architecture|subsystems` and a `docs/` subset; nothing under `auralis-web/**.md` except `WEBSOCKET_API.md` is checked, and `docs/archive/` is where the same kind of file was moved in the 2026-07 cleanup. These 21 files have no historical banner. Examples that now describe deleted code: `PHASE_7_*.md` documents `QueueSearchPanel`, `QueueStatisticsPanel`, `QueueRecommendationsPanel` and their three hooks (all deleted in this range, #5642); `FRONTEND_TEST_ANALYSIS.md:257` and `TEST_GAPS_AND_QUICK_WINS.md:203` list `ParameterChip.tsx` as a coverage target (deleted); `WEEK5_MSE_STREAMING_TESTS.md` reports "20/20 MSE tests passing" for a streaming path that was removed (#4324). `docs/STYLE_GUIDE_AUDIT.md:49-50,251-252` (ratchet scope) links the same panels at `player/QueueSearchPanel.tsx`-style paths that do not resolve (the live player dir has only `QueuePanel`).
- **Evidence**: `git ls-files '*.md' | grep -E "^auralis-web/(PHASE|frontend/[A-Z_0-9]+\.md)"`; `ls auralis-web/frontend/src/components/player/QueueSearchPanel` -> missing.
- **Impact**: Roughly 8k lines of "status: complete" prose that grep and agent searches surface alongside real docs; the largest uncovered rot pool in the repo by volume.
- **Siblings**: n/a (the whole group).
- **Related**: #4547, #4984 (closed; widened the gate to docs/ but not auralis-web/); #5142-style "deletion without follow-through" pattern.
- **Suggested Fix**: `git mv` all 21 into `docs/archive/frontend-history/` (or `git rm`; the information is in git history), keeping only `src/design-system/README.md`, `src/test/README.md`, `src/tests/integration/README.md`, `components/shared/ui/README.md`.

#### TD7-11: The 280-entry docs ratchet is 57% concentrated in 10 historical files, and one of them is labelled ACTIVE and mandatory
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `.claude/commands/_audit-validate-baseline.txt`; `docs/UI_DESIGN_GUIDELINES.md`
- **Status**: NEW
- **Age**: baseline `2030b97d` 2026-10-22
- **Effort**: small
- **Description**: Per-file baseline counts: `CACHE_AND_CHUNKING_AUDIT.md` 22, `PHASE1_2_3_LAUNCH_CHECKLIST.md` 21, `PLAYER_COMPONENT_CONSOLIDATION_PLAN.md` 20, `UI_DESIGN_GUIDELINES.md` 20, `ui_audit/IMPLEMENTATION_STATUS.md` 16, `FRONTEND_REMEDIATION_PLAN.md` 13, `testing/TESTING_ANALYSIS.md` 12, `PHASE_5_IMPLEMENTATION_PLAN.md` 12, `analysis/AUDIT_SUMMARY.md` 12, `PHASE0_QUICK_START.md` 12 = 160 of 280. Nine are plans/audits/launch checklists whose banners say SUPERSEDED, "Planning Complete", "Ready for Execution" (a Dec-2025 checklist), or "Complete"; they are history, not reference, sitting in the gate's "current docs" scope. The tenth, `UI_DESIGN_GUIDELINES.md`, says "Status: ACTIVE (Mandatory for all UI development)" yet names 20 components/hooks that do not exist (`EnhancedButton.tsx`, `EnhancedCorrelationDisplay.tsx`, `MagicalMusicPlayer.tsx`, `PresetCard.tsx`, `Phase5VisualizationSuite.tsx`, `usePlayer.ts`, ...), several of which are the "Enhanced*/V2" variants CLAUDE.md principle 3 forbids.
- **Evidence**: `cut -f1 _audit-validate-baseline.txt | sort | uniq -c | sort -rn | head`.
- **Impact**: Nine files absorb the ratchet's "may shrink" headroom for no reader benefit, and the mandatory design guide gives UI authors a vocabulary of deleted components.
- **Siblings**: lower-count files in the same baseline (`docs/frontend/analysis/*`, `docs/testing/PHASE2_COMPLETE.md`, `docs/getting-started/START_HERE.md`, `docs/getting-started/LAUNCH.md` which is already self-labelled "Historical snapshot").
- **Related**: #4984 (closed; created the ratchet), #5144 (closed).
- **Suggested Fix**: Move the 9 historical files to `docs/archive/` and regenerate the baseline (`--update-baseline`: 280 -> ~120 without touching any live doc); rewrite `UI_DESIGN_GUIDELINES.md` against `design-system/` primitives or demote it to archive and drop "ACTIVE".

#### TD7-12: Contributor-facing docs carry commands and claims the project has since ruled out
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `docs/CONTRIBUTING.md:112,117,121`; `docs/development/BUILD_QUICK_REFERENCE.md:17`; `docs/development/DEVELOPMENT_SETUP_FRONTEND.md:17-326`; `docs/development/AUTOMATED_TESTING_GUIDE.md:59-612`; `README.md:429-430`; `auralis/library/migrations/README.md:8-10`
- **Status**: NEW
- **Age**: `dbb3b4a5` 2026-07-11 (CONTRIBUTING); `c76ffd22` 2026-07-18 (README backlog); Oct 2025 (migrations README, dev guides)
- **Effort**: small
- **Description**: (1) `CONTRIBUTING.md:112` lists `python -m pytest tests/ -v   # all (~2-3 min)` as the first test command; CLAUDE.md states this is "tens of minutes" and that two files hang, and the same CONTRIBUTING section (lines 125-127) tells readers those files hang. Lines 117 and 121 use `npm run test:memory` / `npm run type-check` although the repo is pnpm-only (#4357; `packageManager` is declared in every `package.json`) and CLAUDE.md names `pnpm`. `BUILD_QUICK_REFERENCE.md:17` repeats the whole-tree pytest and `docs/development/DEVELOPMENT_SETUP_FRONTEND.md` and `AUTOMATED_TESTING_GUIDE.md` use `npm install` / `npm run test` ~60 times; `docs/development/` is deliberately excluded from the gate. (2) `README.md` "Open Backlog" lists "`response_model=` coverage for ~28 backend endpoints (#3838)" and "Rust LUFS measurement -> full BS.1770 K-weighting (#4123)" as open items; both issues are CLOSED, and #4123 was resolved as an intentional RMS proxy (`dsp_math.rs:26`; #5343 fixed the identical wording in a code comment). (3) `auralis/library/migrations/README.md:8-10` gives `migration_v001_to_v002_add_processing_history.sql` / `migration_v002_to_v003_add_user_preferences.sql` as the naming convention; the live migrations are `migration_v001_to_v002.sql` ... `migration_v022_to_v023.sql` (no description suffix).
- **Evidence**: `docs/CONTRIBUTING.md:112`; `ls auralis/library/migrations | head`.
- **Impact**: The command a new contributor is most likely to paste first hangs their terminal; the backlog misleads release planning toward two settled items.
- **Siblings**: `docs/CONTRIBUTING.md:125`: "broken v15->v16 migration cascades" (schema is v23; unverified, likely historical wording).
- **Related**: #4558, #4805, #5445, #5842, #5161 (closed rounds fixing the same drift in README/FIRST_TIME_SETUP/commands).
- **Suggested Fix**: Replace line 112 with the scoped `-m "not slow" tests/auralis/dsp` form from CLAUDE.md, swap `npm`->`pnpm` in CONTRIBUTING and the two dev guides (or banner the guides as historical), delete the two README backlog bullets, and drop the description suffix from the migrations README examples.

### Dimension 8: Backwards-Compat Cruft

#### TD8-01: "Removed/deleted in #NNNN" breadcrumbs: #5820 trimmed ~30, ~85 more remain, and its proposed grep gate was never added
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: ~40 Python files and ~34 TS/TSX files; full hit lists in `/tmp/audit/auralis/tech-debt/scratch_8/bc_py.txt` and `bc_ts.txt`
- **Status**: Regression of #5820 (closed 2026-10-22 by `ef0c6464`; same pattern, 6th recurrence after #4088, #4293, #4649, #5034, #5820)
- **Age**: mostly 2026-07 to 2026-10 (e.g. `a2a72d91` #5056, `134c74ae`, `8373b8d1` #5763, `44e4d433` #5764)
- **Effort**: small (comment-only)
- **Description**: Comments that narrate code that no longer exists and cite the deleting issue. `ef0c6464` trimmed the sites listed in #5820's body but not the rest, and did not add the grep gate #5820's Proposed Fix asked for (`scripts/` still has no such check), which is why the pattern has now recurred six times. Sites not in #5820's list, or that survived it (pure history sentences, no present-tense constraint):
  - Python: `core/job_config.py:81-86` (parameter_mapper deleted #4926), `security/path_security.py:20-22` (validate_scan_path removed), `optimization/performance_optimizer.py:12-19` (#5325/#5769 deleted list), `core/chunk_cache_manager.py:70-73` (get_wav_cache_key removed), `core/hybrid_processor_singleton.py:6-7` (process_hybrid deleted #5203), `core/stream_chunk_ops.py:66-68,145` (#5492, #3514), `core/config/preset_profiles.py:55-66` (five profiles removed), `core/config/settings.py:50-63` (#4613/#5302/#5763 removed fields), `core/audio_stream_controller.py:17-20` (stream_prefetch.py deleted #3879), `core/processor_maintenance.py:110-116` (#4618), `core/job_execution.py:125-127` (#4873), `core/chunked_processor.py:100-104` (#5056; this one was in #5820's list at its old line 196 and survived the file split), `ws_handlers/messages.py:7-11` (#5525), `cache/__init__.py:12-15` (#4738), `core/hybrid_setup.py:57-58` (#4873/#5295), `core/mastering_branches/continuous.py:296-298` (#5245), `core/processing/hybrid_mode.py:92-95`, `helpers.py:11-15` (#4606), `learning/__init__.py:5-6` (#5763), `io/results.py:35-37` (#4106), `dsp/__init__.py:12-18` (#4867), `dsp/dynamics/lookahead_buffer.py:13` (#4873), `dsp/utils/spectral.py:190-200` (#5168/#5764), `player_state.py:35-36`, `routers/enhancement.py:105-112` ("Moved to routers/processing_api.py (#5073)"), `core/stream_seek.py:90-91,275-276` (moved into pump_chunks), `vendor/auralis-dsp/src/lib.rs:11`, `py_bindings.rs:6` (#5764).
  - TypeScript: `a11y/focusManagement.ts:9`, `services/artworkService.ts:11`, `services/playlistService.ts:262,269`, `services/api/standardizedAPIClient.ts:6-18`, `types/api.ts:4`, `types/ws/queue.ts:21`, `types/ws/guards.ts:6`, `types/ws/library.ts:114-117`, `store/slices/{queueSlice:282,playerSlice:256,274,283,cacheSlice:119,123,connectionSlice:201}.ts`, `store/middleware/{errorTrackingMiddleware:80,282,loggerMiddleware:248}.ts`, `store/selectors/combined.ts:40`, `hooks/shared/{usePlayerRedux:70,useCacheRedux:22,useAppRedux:35,useStandardizedAPI:25}.ts`, `hooks/app/useKeyboardShortcuts.ts:13`, `hooks/enhancement/useAudioStreamingCore.ts:8`, `utils/{queryRetry:45,apiRequest:20,audio/pcmDecoding:15}.ts`, `services/audio/PCMStreamBuffer.ts:40`, `components/library/Styles/Icon.styles.ts:25-27` and `EmptyState.styles.ts:20` ("No longer needed after consolidation"), `components/library/Details/{AlbumDetailView,ArtistDetailView}.tsx`, `components/core/AppViewAnnouncement.tsx:4`, `components/player/Player.tsx:175`.
  - Stale migration/"new" narration of the same family: `components/album/AlbumCard/AlbumCard.tsx:1-12,56`, `components/track/TrackCard.tsx:1-8,34` ("Maintains/Provides backwards compatibility ... Migration: Refactored from 109 lines to 60 lines"), `components/library/Styles/ArtistList.styles.ts:21` ("renamed for backwards compat"), `# NEW:` tags at `backend/cache/manager.py:108`, `core/analysis/target_generator.py:52`, `analysis/mastering_profiles_builtin.py:111`.
- **Evidence**: `rg -n -i "(was|were|been|now|since) +(removed|deleted|dropped|retired)|(deleted|removed|retired) +(by|in|with) +#[0-9]"` gives 50 Python and 44 TS hits at HEAD (about 10 are docstring false positives such as "True if track was removed"). Example: `# #4618: set_mastering_targets() was deleted here. It was a deprecated, caller-less public method ...` (`core/processor_maintenance.py:110`).
- **Impact**: Each is a place a future refactor must decide whether the history is still true; the git log already carries it. The recurrence shows manual sweeps do not stick.
- **Siblings**: `AlbumCard`/`TrackCard` are genuine thin adapters over `MediaCard`; only their prose is stale.
- **Related**: #5820, #5034, #4649, #4293, #4088 (all closed). CLAUDE.md principle 5 prefers `TODO(#NNNN)` markers for deferrals and no prose history.
- **Suggested Fix**: Delete the history sentences in one pass, keeping at most one present-tense constraint where code would otherwise invite re-adding the thing ("Do not re-add X: Y"). Then add the gate #5820 proposed (a `scripts/check_breadcrumbs.py` run from `backend-tests.yml`, failing on `(was|were) (removed|deleted) (in|by|with) #\d+` under the three source roots with the survivors baselined) so a seventh sweep is not needed.

#### TD8-02: Parameters and write-only fields left by refactors, still fed by live callers (the #5821 class, 16 more sites)
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: see Evidence table
- **Status**: NEW (#5821 closed 2026-10-22 fixed a different list; none of these were in it)
- **Age**: `harmonic_exciter` args `c4a7d31f` 2026-06-01 / `dcb5858f` 2026-07-28; `_notify_progress` `b63a4030` 2026-08-23; `_delete_lock` `b02c8543` 2026-07-29; `map_to_bands` `380159b0` 2025-11-29
- **Effort**: small (signature + call-site edits; one test file per symbol)
- **Description**: AST scan of every function for a parameter never read in the body (stubs, abstract methods, `__exit__`, event/exception-handler and framework-invoked signatures excluded), then each hit traced to its callers. In each row below at least one live caller computes or passes a value that the callee discards, so the parameter advertises a behaviour that does not exist. Two cases hide wasted work: `HybridMode.process` runs a full `content_analyzer.analyze_content(target_audio)` only to hand `content_profile` to `_apply_hybrid_processing`, which ignores it, and `GenreClassifier._classify_genre_rule_based` computes `spectral_rolloff` only to pass it to `_classify_genre`, which ignores it.
- **Evidence**:
  | Callee | Unused | Fed by |
  |---|---|---|
  | `core/stages/harmonic_exciter.py:12-51` `apply` (it ends its argument handling with `del presence_pct, air_pct, spectral_rolloff`; docstring "Retained for the stable stage-call interface") | `presence_pct`, `air_pct`, `spectral_rolloff` | `core/mastering_stage_delegates.py:107-112`, `core/mastering_branches/continuous.py:170-173`; tests pass `1.0, 1.0, 1.0` |
  | `core/stages/sub_bass_control.py:18` `apply` | `bass_pct` (documented as used) | `mastering_stage_delegates` + `continuous.py` |
  | `core/processing/adaptive_mode.py:145` `_apply_dynamics_processing` | `spectrum_position` | `adaptive_mode.py:129` |
  | `core/processing/hybrid_mode.py:70` `_apply_hybrid_processing` | `content_profile`; also `HybridMode.target_generator` (`:38`) is write-only ("remains injected for a future adaptive-targets pass") | `hybrid_mode.py:62` after a full content analysis |
  | `core/analysis/target_generator.py:246` `_apply_fingerprint_enhancements` | `content_profile` | `target_generator.py:54` |
  | `core/processing/cross_dimensional_guard.py:153` `check_normalization_side_effects` | `post_dynamics` | `cross_dimensional_guard.py:217` (a dropped crest check? route to `/audit-engine`; yesterday's report flagged the same) |
  | `core/analysis/genre_classification.py:55` `_classify_genre` | `rolloff` | `:53`, after `spectral_rolloff(mono_audio, ...)` |
  | `analysis/adaptive_mastering_engine.py:168,184` | `_fallback_recommendation(fingerprint)`, `_generate_reasoning(profile)` | `:71,113` and `:90,128` |
  | `analysis/ml/genre_classifier.py:117` | `_get_feature_importance(features)` | `:84` |
  | `analysis/spectrum_operations.py:100` / `analysis/spectrum_analyzer.py:197` | `map_to_bands(sample_rate)` | one caller |
  | `analysis/quality_assessors/utilities/estimation_ops.py:24` | `estimate_thd(sr)` ("not required for THD estimation") | `quality/distortion_assessment.py:39,82` pass nothing, tests pass it |
  | `analysis/fingerprint/metrics/robust_scaling.py:141` | `robust_scale_with_winsorization(epsilon)` | re-exported via `normalization.py:61` |
  | `core/utils/smooth_curves.py:180` | `bipolar_s_curve(center)`; the function itself has zero callers anywhere, and its docstring promises "center maps to 0.0" while the body ignores `center` | none |
  | `backend/core/processing_engine.py:183` | `_notify_progress(message)`; 7 callers pass strings such as "Processing audio..." (`job_execution.py:88,99,122,207,239`, `job_lifecycle.py:145,172`) | live |
  | `backend/core/streamlined_tiers.py:164` | `build_tier2_cache(current_chunk)` | `streamlined_tiers.py:88` |
  | `library/scanner/scanner.py:264` | `scan_folder(**kwargs)` (method already kept by decision #4973, but the dead `**kwargs` is not part of that decision) | tests |
  - Write-only `_`-fields: `library/database.py:115` `LibraryDatabase._delete_lock = threading.RLock()` ("Thread-safe locking for delete operations") is never acquired; `analysis/quality_assessors/base_assessor.py:25,55` `_cached_analysis` and its `clear_cache()` (no caller on any assessor); `analysis/fingerprint/fingerprint_service.py:104` `_session_factory`.
- **Impact**: A parameter that looks like a tuning knob but is ignored (`bipolar_s_curve(center=...)`, `harmonic_exciter` percentages) invites someone to tune it; `_delete_lock` reads as a concurrency guard that does not exist; the two discarded analyses cost CPU in `hybrid`-mode jobs and rule-based genre fallback.
- **Siblings**: `harmonic_exciter` is one of three exciter-related locations (see TD4's `core/dsp/harmonic_exciter.py` finding, different file).
- **Related**: #5821 (closed, same class). `check_normalization_side_effects` is possibly a dropped check, owned by `/audit-engine`.
- **Suggested Fix**: Drop each parameter and the arguments that feed it (start with the exciter chain and `_notify_progress`, the most visible), delete `bipolar_s_curve`, `_delete_lock`, `_cached_analysis`/`clear_cache`, `_session_factory`, and the discarded `analyze_content`/`spectral_rolloff` computations. Update the handful of tests that pass the dead arguments.
- **Merge note**: `LibraryDatabase._delete_lock` is reported under TD2-05 (and E7-09 in AUDIT_ENGINE_2026-10-22.md), not here.

#### TD8-03: `contextMenuActions.tsx` takes four entity-id parameters it never reads
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/frontend/src/components/shared/ContextMenu/contextMenuActions.tsx:38,132,171,210`
- **Status**: NEW
- **Age**: `592891db` 2026-03-01 (TS 5.x `noUnusedParameters` fix pass renamed them to `_`)
- **Effort**: trivial
- **Description**: `getTrackContextActions(_trackId, isLoved, callbacks)`, `getAlbumContextActions(_albumId, callbacks)`, `getArtistContextActions(_artistId, callbacks)`, `getPlaylistContextActions(_playlistId, callbacks)`. The `_` prefix is how the 2026-03 TS-upgrade pass silenced `noUnusedParameters` instead of deleting the parameter (CLAUDE.md-style rule: delete, do not rename). All three live callers pass an id that is discarded (`usePlaylistContextActions.ts:34` `playlist.id.toString()`, `artists/useContextMenuActions.ts:113` `artist.id`, `tracks/useTrackContextMenu.ts:124` `track.id`). `getAlbumContextActions` has no caller at all (re-exported from `ContextMenu/index.ts:15`; Dim 5 observed the same).
- **Evidence**: `export const getTrackContextActions = (\n  _trackId: number,\n  isLoved: boolean,` ... the id never appears in the body; every action closes over `callbacks.*`.
- **Impact**: Call sites keep computing `playlist.id.toString()` for nothing; the leading unused positional makes every call site depend on an argument order that carries no information.
- **Siblings**: `getAlbumContextActions` itself is dead (Dim 2 domain).
- **Related**: TD8-04 of the 2026-10-21 report/#5822 (closed) fixed the same idiom elsewhere in the frontend.
- **Suggested Fix**: Delete the four leading parameters and the id argument at the three live call sites; delete `getAlbumContextActions` and its barrel line if nothing adopts it.

#### TD8-04: Frontend and backend accept response/request shapes the app never produces
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/frontend/src/api/responseGuards.ts:62-80,150-157`; `hooks/library/libraryQueryRequest.ts:97-104`; `services/playlistService.ts:89-131`; `store/slices/playerStreamingReducers.ts:182-186`; `services/audio/PCMStreamBuffer.ts:31,64`; backend `routers/metadata_models.py:21-30`
- **Status**: NEW (adjacent to open #5823, which covers `currentIndex`/`hasMore`/Track twin fields, not these keys)
- **Age**: `has_more ?? hasMore` `ca49fde6` 2026-10-20; envelope tolerance older than 2026-03
- **Effort**: small
- **Description**: Dual-read of old vs new shapes in a single-client desktop app. (1) List guards and readers accept a generic `items` key (`o[collectionKey] ?? o.items`, `r.tracks ?? r.items ?? []`, `o.playlists ?? o.items`); the backend never emits `items` (`rg '"items"' auralis-web/backend` finds only a comment in `routers/pagination.py:21` saying it deliberately does not). (2) `playlistService.fetchPlaylistsPage` and `isPlaylistsListShape` accept a bare `Playlist[]` "(older serializer / older backend)"; `GET /api/playlists` (`routers/playlists_crud.py:22`) returns only the paginated envelope, and the `TList = PlaylistsResponse | Playlist[]` union exists only to type that fallback. (3) `completeStreaming.prepare` accepts a bare `StreamType` string "Back-compat"; the only production dispatch (`useStreamMessageHandlers.ts:215`) passes the object form, bare-string calls are in tests only. (4) `PCMStreamBuffer`'s constructor default capacity is documented as "only a legacy fallback" and is used only by tests (production sizes via `capacityForStream`). (5) Backend `MetadataUpdateRequest` accepts both `track`/`track_number` and `disc`/`disc_number` (`validate_by_name` + `validate_by_alias`); the frontend sends only `track`/`disc`; pinned by `test_metadata_update_request_validate_by_name_4960.py`.
- **Evidence**: `const collection = o[collectionKey] ?? o.items;` (`responseGuards.ts:72`); `const [playlistsArray, envelope] = Array.isArray(response) ? [response, null] : [response.playlists, response];` (`playlistService.ts:122`).
- **Impact**: Each tolerance has to be reasoned about and tested ("a guard failure means a genuinely unexpected payload" is untrue when an unreachable shape is also accepted); guards that accept both shapes cannot fail loudly on a real backend regression.
- **Siblings**: `types/api.ts:48` scrapes `/^HTTP (\d{3}):/` from error messages "for any thrower that uses neither" `.status` nor `.statusCode`; the first two transports are live (#4643), the third thrower is not identified, so left unreported.
- **Related**: #5823 (open), #4960 (closed), `/audit-frontend` for the guard semantics.
- **Suggested Fix**: Make the guards read the one real key per endpoint, collapse `fetchPlaylistsPage` to the envelope type and drop `| Playlist[]`, make `completeStreaming` take only the object form (update its two test files), drop the `PCMStreamBuffer` default argument, and decide whether `MetadataUpdateRequest` keeps one name per field.

#### TD8-05: Queue-entry file path is read as `file_path`/`path` in the player engine while every producer writes `filepath`
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis/player/gapless_prebuffer.py:99,214-215`; `auralis/player/gapless_playback_engine.py:130`; `auralis/player/player_queue_navigation_mixin.py:168,227`; `auralis/player/components/queue_navigation.py:20-21`; `backend/services/queue_enrichment.py:53`; `backend/services/queue_edit_mixin.py:211`
- **Status**: NEW
- **Age**: `b8522341` 2025-11-11 (EnhancedAudioPlayer refactor); `peek_next_track` readers rewritten `b9e92f9e` 2026-10-22 (#5836, part)
- **Effort**: small
- **Description**: Three spellings of one key coexist in queue entry dicts: `filepath`, `file_path`, `path`, probed with `a.get('file_path') or a.get('path')` chains. Production writes only `filepath` (`queue_loading.py:128` `{'filepath': track}`, `queue_edit_mixin.py:56,135` `{'id', 'filepath'}`) or `track.to_dict()`, which carries no path key at all (#3205). The engine-side readers at the first five locations look only for `file_path`/`path`, so no production entry can match them; the tests pass because they hand-build entries with `file_path` (`tests/auralis/player/test_gapless_playback_engine.py:290,318`, `test_queue_changed_rearms_prebuffer_5583.py:30`). The two backend readers probe `filepath` first with `file_path` as the dead "compat" fallback.
- **Evidence**: `file_path = next_track.get('file_path') or next_track.get('path')` / `if not file_path: warning("Next track has no file path")` (`gapless_prebuffer.py:99-101`) versus `self.queue.add_track({'filepath': track})`.
- **Impact**: Besides the spelling debt, this looks like a live defect: with production queue entries the prebuffer, `advance_with_prebuffer` and `previous_track` path lookups return None. Whether that path is reachable in the shipped app (the engine queue may be a disconnected control plane, #4541) is for the engine audit.
- **Siblings**: `Track.to_dict()` vs `TrackInfo` vs scanner `AudioFileInfo.filepath` all use `filepath`; `unified_loader.py:182` is the lone `'file_path'` key producer (loader result, unrelated).
- **Related**: `/audit-engine` should confirm and decide whether this is a correctness bug (gapless playback silently failing) before the spelling is normalized.
- **Suggested Fix**: Pick `filepath` (what is written everywhere), add one `queue_entry_path(entry)` helper in `auralis/player/components/queue_navigation.py`, replace the 7 `get(...) or get(...)` chains with it, and change the player tests to build entries with `filepath`.
- **Orchestrator spot-check (2026-10-22)**: confirmed that `gapless_prebuffer.py:99,214-215`, `gapless_playback_engine.py:130`, `player_queue_navigation_mixin.py:168` and `components/queue_navigation.py:20-21` read only `file_path`/`path`, while `queue_loading.py:128` and `queue_edit_mixin.py:56,135` write `filepath`. `player_queue_navigation_mixin.py:227` already falls back to `filepath`, so it is a spelling sibling, not a broken reader. Route the possible gapless/previous-track defect to /audit-engine before normalizing the key.

#### TD8-06: `PreferenceVector` is always the neutral vector, yet ~100 `preference` references bias every parameter generator
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis/core/processing/continuous_space.py:96-152` (`PreferenceVector.from_preset_name`); `core/processing/continuous_mode.py:267-269`; consumers `parameter_generator.py` (38 refs), `parameter_generator_eq.py` (29), `parameter_generator_dynamics.py` (30), `parameter_generator_stereo.py` (6)
- **Status**: NEW
- **Age**: `ad7f5245` 2025-11-04 (introduced); preset narrowing 2026-09-13; preference engine removed `8373b8d1` #5763
- **Effort**: medium
- **Description**: `from_preset_name` builds `presets = {'adaptive': cls()}` and returns `presets.get(preset.lower(), cls())`, i.e. `cls()` for every input; its docstring justifies the tolerant fallback "for backward compatibility with anything still holding an old value" of the five retired preset names. With schema v23 (#5824) normalizing the stored value and writes restricted to the Literal, no old value can arrive. Its single production caller is `ContinuousMode` (`continuous_mode.py:269`), so the vector passed to `ContinuousParameterGenerator.generate_parameters` is always all-zero: every `preference.loudness_bias * 2.0`, `preference.bass_boost * 2.0`, `coords + preference.spectral_bias * BIAS_STRENGTH`, ... term is `0 * k`, and `if preference.dynamic_bias != 0` blocks never run. Only `tests/test_continuous_space.py:234-250` constructs a non-neutral `PreferenceVector`.
- **Evidence**: `presets = {'adaptive': cls()}  # Neutral - pure content-driven processing` / `return presets.get(preset.lower(), cls())` (`continuous_space.py:147-151`); `preference = PreferenceVector.from_preset_name(preset_name)` is the only construction in `auralis/`.
- **Impact**: ~100 lines of arithmetic and a `PreferenceVector | None` parameter threaded through five modules and eight private methods that do nothing; it also keeps the removed-preset vocabulary (`gentle/warm/bright/punchy/live`) alive in docstrings and `tests/test_continuous_space.py:211`.
- **Siblings**: `AdaptiveMode` (kept by decision, STREAMLINING_PLAN #5) has its own preset-profile path (`preset_profiles.py`, one entry), not affected.
- **Related**: #5763 (removed the engine that could have produced a non-neutral vector), #5824 (normalized the data); `/audit-engine` for the DSP-equivalence check before deleting.
- **Suggested Fix**: Delete `PreferenceVector`, `from_preset_name` and the `preference`/`user_preference` parameter and every bias term in the four `parameter_generator*.py` modules and `_apply_preference_bias`; drop the `continuous_mode.py:267-269` step; delete the three non-neutral test cases and the retired-name assertion. Verify output equality on a fixture before and after.

#### TD8-07: `playlists.mastering_profile` and `genres.preferred_profile` are vestigial columns carrying removed-preset vocabulary, and the v23 migration points at an issue that does not cover them
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis/library/models/playlist.py:35,77`; `auralis/library/models/genre.py:31,55`; `auralis/library/repositories/genre_repository.py:158-175`; `backend/schemas/library.py:192`; `frontend/src/services/playlistService.ts:31`; `auralis/library/migrations/migration_v022_to_v023.sql:16-17`
- **Status**: NEW (prior report: TD8-06 in `AUDIT_TECH_DEBT_2026-10-21.md`, unpublished for this half; #5824 fixed only the `default_preset` half)
- **Age**: columns from `migration_v000_to_v001_initial_schema.sql` (2025-12); `genre.py` comment `a800893e` 2026-09-17
- **Effort**: small (needs a migration)
- **Description**: Both columns default to `'balanced'` (not a valid preset), are written by nobody (`GenreRepository.create(preferred_profile=...)` is passed only by a test), and are read by nobody. `Playlist.mastering_profile` is serialized into `PlaylistResponse` and typed in `PlaylistWire` with no reader (frontend fixtures set it to `'adaptive'`, a value the real backend never returns). `genre.py:31` still documents the vocabulary as `# warm, bright, punchy, balanced`. The v23 migration comment says they "are left for the column-removal migration tracked in #5755", but #5755's body covers `file_hash`, level columns, fingerprint-status columns/indexes and `LibraryStats`, not these two, so nothing tracks them.
- **Evidence**: `mastering_profile: Mapped[str | None] = mapped_column(String, default='balanced')`; `preferred_profile: Mapped[str | None] = mapped_column(String, default='balanced')  # warm, bright, punchy, balanced`.
- **Impact**: A removed-preset surface in the DB and on the wire that cannot be deleted until someone owns it; the migration comment misdirects the next reader.
- **Siblings**: none (checked all five removed names across `auralis/`, `auralis-web/`: only `preset_anchors.py`, the Player test sentinel, comments and these two columns).
- **Related**: #5755 (open; add these two columns to its scope), #5824 (closed).
- **Suggested Fix**: Add both columns to #5755's column-removal migration (or file them with it), drop the model fields, `to_dict` keys, `GenreRepository.create` parameter, `PlaylistResponse.mastering_profile` and `PlaylistWire.mastering_profile`, and correct the v023 SQL comment.

#### TD8-08: Split-created compat re-exports outside TD2-01/TD2-09's lists: `config/middleware`, `library/models/core.py`, `config/__init__`, `system_streams`
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/backend/config/middleware/__init__.py:8-9,27-40`; `auralis/library/models/core.py:5-12,20,41-44`; `auralis-web/backend/config/__init__.py:20-34`; `auralis-web/backend/routers/system_streams.py:30-33`
- **Status**: NEW
- **Age**: `254d9305` 2026-09-16 (#5479, middleware/schemas packages); `4626d65d` 2026-08-22 (#4511, models/core); `config/__init__` pre-2026-07
- **Effort**: small
- **Description**: (1) `config/middleware/__init__.py` states "every name is re-exported here, so `from config.middleware import X` is unchanged". Four re-exports have no consumer: `_middleware_error_response`, `_TRUSTED_HOSTS`, `_TEST_HOSTS` (zero importers anywhere; the sibling modules import from `.error_response`/`.hosts` directly) and `_ARTIST_ARTWORK_IMG_HOSTS` (one test, `test_csp_artist_artwork_4526.py:32`, which can import `security_headers`). (2) `library/models/core.py` is a pure re-export module after #4511 ("so every existing import keeps working"): the only production importer is `RepositoryFactory.reset` (`repositories/factory.py:175`, which can import `..models`), the rest are ~10 test imports; its `_safe_collection`/`_safe_scalar` re-export is commented "kept importable from here for back-compat" and nothing imports them from there. CLAUDE.md still tells readers these helpers live in `library/models/core.py`. (3) `config/__init__.py` is a PEP 562 `__getattr__` shim whose four lazy names (`create_app`, `setup_middleware`, `setup_routers`, `create_lifespan`) have no importer: `main.py:30-37` imports each from its submodule. (4) `system_streams._stream_pause_events = stream_pause_events` and `_stream_flow_events = ...` are renaming aliases (the registries moved to `core.stream_gates`, #5761) imported under the alias name by `system.py:31-32`.
- **Evidence**: `from .error_response import _middleware_error_response  # noqa: F401` with no body use; `rg -w _TRUSTED_HOSTS` finds `hosts.py` and this re-export only.
- **Impact**: Same maintenance cost as TD2-01 (two import paths per moved helper; tests patching the shim instead of the definer pass vacuously) on four more modules, plus a CLAUDE.md pointer that names the wrong file.
- **Siblings**: `routers/{system,settings,library,artists,fingerprint_queue}.py` and `core/chunk_cache_manager.py` also carry `# noqa: F401` blocks, but every name there is used in the body (the `noqa` is unnecessary, not a shim); not reported.
- **Related**: TD2-01 (router/cache/ffmpeg shims), TD2-09 (package `__init__` barrels); doc fix needed in CLAUDE.md ("in `library/models/core.py`" should point at `library/models/_helpers.py`).
- **Suggested Fix**: Delete the four middleware re-exports and repoint the one test; repoint `factory.py` and the ~10 test imports at `library.models` / the per-model modules and reduce `models/core.py` to nothing (or delete it); delete `config/__init__`'s `__getattr__` and `_LAZY`; use the `core.stream_gates` names directly in `system.py`.

#### TD8-09: `auralis/__version__.py` mirrors `__version__`/`__version_info__` "for older importers" that do not exist, at the cost of three scripts keeping the mirror in sync
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis/__version__.py:1-10`; `sync_version.py:111-126`; `scripts/validate_release_metadata.py:83,129-135`; `tests/regression/test_release_version_consistency.py:14,37`
- **Status**: NEW
- **Age**: `e4353a53` 2026-07-25
- **Effort**: trivial
- **Description**: The module docstring says the two product constants are "retained for older importers". `rg` finds no importer of `auralis.__version__.__version__` or `__version_info__` anywhere in `auralis/`, `auralis-web/`, `scripts/`, `desktop/` (every real importer takes `FINGERPRINT_ALGORITHM_VERSION` or `__db_schema_version__`; the product version comes from `auralis/version.py` and `auralis/__init__.py:15`). The only consumers are the machinery that keeps the mirror in sync: `sync_version.py` rewrites it, `validate_release_metadata.py` checks it, and a regression test asserts it.
- **Evidence**: `__version__ = "1.5.1"` / `__version_info__ = (1, 5, 1, "", 0)` in a module that every importer uses only for `__db_schema_version__` and the fingerprint algorithm version.
- **Impact**: Every version bump touches a second file to feed a name nobody reads; the mirror is a third spelling of the version next to `version.py` and `pyproject`.
- **Siblings**: none.
- **Related**: #4051 (single source of truth for the version).
- **Suggested Fix**: Delete the two constants and their rewrite/validation code and test assertions; leave `auralis/__version__.py` holding only the schema and fingerprint versions (and update its docstring).

#### TD8-10: Two orphan migration artefacts for schema versions long passed: `add_artist_artwork.sql` and `normalize_existing_artists.py`
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis/library/migrations/add_artist_artwork.sql`; `auralis/library/migrations/normalize_existing_artists.py` (307 lines); references at `auralis/library/database.py:41`, `auralis/library/migrations/__init__.py:7`, `migration_v010_to_v011.sql:10`, `tests/concurrency/test_migration_lock_identity_4523.py`
- **Status**: NEW
- **Age**: both `936b8856` / `68cdf8e2` 2025-12-27 to 2025-12-29
- **Effort**: small
- **Description**: (1) `add_artist_artwork.sql` is not named `migration_vNNN_to_vNNN.sql`, so `migration_steps.py:84` (which builds the filename from the version pair) can never load it, and it duplicates `migration_v009_to_v010.sql` (`ALTER TABLE artists ADD COLUMN artwork_url` / `artwork_source`), so running it by hand on any DB at v10+ fails with "duplicate column". It is referenced nowhere. (2) `normalize_existing_artists.py` is a one-time `python -m` data-repair script for the v010-to-v011 upgrade ("Run this after applying migration_v010_to_v011.sql"). It re-adds `normalized_name` if missing (duplicating the SQL migration), inserts into `sys.path`, and has been kept in step with locking changes (#3682, #4523) even though no code path invokes it; fresh databases (v000 chain) never hold the pre-normalization duplicates it merges. The concurrency audit already spent effort on it (`AUDIT_CONCURRENCY_2026-10-22.md:724`).
- **Evidence**: `python -m auralis.library.migrations.normalize_existing_artists` is documented only inside the file and `migrations/__init__.py`; `rg normalize_existing_artists` outside docs/tests finds comments only.
- **Impact**: Dead upgrade tooling for a version nobody can be on needs maintenance whenever the lock or engine code changes (it is the "second migration entry point" the lock tests must cover).
- **Siblings**: `batch_processor.py:123` NULL `file_mtime` handling for "pre-v22 rows" is legitimate (the column is nullable by design), not reported.
- **Related**: `/audit-engine` if the duplicate-artist merge is still wanted as a maintenance command (then move it out of `migrations/` and call it from a CLI).
- **Suggested Fix**: Delete `add_artist_artwork.sql`; delete `normalize_existing_artists.py` with its two comment references and the `normalize_existing_artists` half of `test_migration_lock_identity_4523.py`, unless a maintainer wants the merge kept as a supported command.

#### TD8-11: `FingerprintRepository` keeps four "so callers keep working" stats delegators; three have no production caller
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis/library/repositories/fingerprint_repository.py:62-86` (and the `_stats` composition at `:62-66`)
- **Status**: NEW (partial overlap with open #5755, which proposes deleting `FingerprintStatsRepository.update_status()`/`get_fingerprint_status()` themselves; this finding is the facade layer and `cleanup_incomplete_fingerprints`)
- **Age**: `0366f46c` 2026-06-28 (#4108)
- **Effort**: trivial
- **Description**: After #4108 moved the status/stats methods to `FingerprintStatsRepository`, the facade kept thin delegators "so callers that hold the facade keep working". Production callers of the facade methods: `get_fingerprint_stats` (3 router sites) is live; `update_status`, `get_fingerprint_status` and `cleanup_incomplete_fingerprints` have none. `database.py:249` calls `self.fingerprint_stats.cleanup_incomplete_fingerprints()` directly; tests (`test_fingerprint_status_update.py`, `tests/integration/test_repositories.py:311,346`, `tests/backend/conftest.py:447-448` mocks) are the only callers. The facade builds a second `FingerprintStatsRepository` (`self._stats`) only for these.
- **Evidence**: `rg "\.update_status\(|\.get_fingerprint_status\(|\.cleanup_incomplete_fingerprints\("` in `auralis/`, `auralis-web/backend/`: only the delegator bodies and `database.py:249` (stats repo, not facade).
- **Impact**: Two repositories exposing the same operations with the same names; the facade's `_stats` is an extra session-factory consumer.
- **Siblings**: `PlaylistRepository` and the other split facades are pure mixin inheritance, no delegators.
- **Related**: #5755 (open), #4108 (closed).
- **Suggested Fix**: Delete the three dead delegators (keep `get_fingerprint_stats`), repoint the tests at `repository_factory.fingerprint_stats`, and drop `_stats` if only one delegator remains (or have the router call `fingerprint_stats` and delete the facade composition entirely).

#### TD8-12: Styled-component alias exports with no importer or two meanings: `StyledTabs`, `DetailViewTabs`, `CancelButtonForDialog`
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/frontend/src/components/library/Styles/ArtistDetail.styles.ts:14`; `Dialog.styles.ts:13-14`; `Button.styles.ts:104-107`; `Tabs.styles.ts:62-65`
- **Status**: NEW
- **Age**: stylesheet split `592891db` 2026-03-01 era
- **Effort**: trivial
- **Description**: `export { DetailViewTabs as StyledTabs }` in `ArtistDetail.styles.ts` and `export { DialogTabs as StyledTabs, DetailViewTabs }` in `Dialog.styles.ts` give one name two different components; only `Dialog.styles.StyledTabs` is imported (`SettingsTabNav.tsx:10`). `ArtistDetail.styles.StyledTabs` and `Dialog.styles.DetailViewTabs` have no importer, and the NOTE in `Tabs.styles.ts:62-65` tells readers to "import StyledTabs from ArtistDetail.styles", which is the unused one. `CancelButtonForDialog = CancelButton` ("Alias for CancelButton") makes two names for one component, used by two files while two sibling dialogs import `CancelButton` directly.
- **Evidence**: `rg -w StyledTabs` finds `SettingsTabNav.tsx` plus the two re-export lines and the note.
- **Impact**: Wrong guidance in a comment and a name that resolves to different components depending on the import path.
- **Siblings**: `ArtistList.styles.ts:21` ("renamed for backwards compat") and `playlist/PlaylistList.styles.ts:62` both define a different `StyledListItem` (covered by TD8-01 for the comment).
- **Related**: Dim 2 already covers the unused styled exports in `components/library/Styles/*.styles.ts` (BorderRadius, Container, Typography); not repeated here.
- **Suggested Fix**: Delete the `ArtistDetail.styles` `StyledTabs` export, `Dialog.styles`' `DetailViewTabs` re-export and the stale NOTE; rename the settings import to `DialogTabs` and delete the `StyledTabs` alias; replace `CancelButtonForDialog` with `CancelButton` at its two importers.

---

### Dimension 9: File/Function Complexity

#### TD9-01: Closed split targets missing from loc-ceilings.json are sitting at or over 300
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `loc-ceilings.json` (85 entries); missing entries listed under Evidence
- **Status**: NEW
- **Age**: ceilings file last touched f886a735 2026-10-22; `audio_stream_controller.py` has 15 commits in the last 90 days
- **Effort**: small (<=2 h) for the ceiling entries; the two files over 300 need a split each (trivial to small)
- **Description**: #5830 added the ratchet for closed split targets, but only the targets of #5831-#5838 and the older #4245/#4249/#4250/#5463 were enrolled. Targets of earlier closed split issues (#4071, #4252, #4254, #5032, #5238, #5236) were never added, and they are the ones that have crept back to the limit. Two are over or exactly at the rule, and `audio_stream_controller.py` is regrowing at the same rate that originally broke the other files.
- **Evidence** (LOC / closed issue / listed?):
  - `auralis-web/backend/core/audio_stream_controller.py` 302 / #4071 (1962L) / no  (over 300; 15 commits in 90 d)
  - `auralis-web/backend/core/stream_enhanced.py` 303 / #5032 / no  (over 300)
  - `auralis/core/mastering_branches/continuous.py` 300 / #4252 / no  (exactly at the limit)
  - `auralis-web/backend/core/stream_seek.py` 292 / #5032 / no
  - `auralis/core/processing/continuous_mode.py` 284 / #4254 / no
  - `auralis-web/backend/cache/manager.py` 283 / #5238 / no
  - `auralis-web/backend/config/startup/tempfiles.py` 260 / #5236 / no
- **Impact**: A closed split issue has no mechanism holding the line, so these files regrow a few lines per fix (the exact failure #5830 described) and the next audit re-files them.
- **Siblings**: all seven above; `stream_normal.py` (277) is the same family.
- **Related**: #5830 (closed, ratchet origin), #5454 (closed, "three closed god-file splits have regrown"). Not a runtime bug.
- **Suggested Fix**: Split the two offenders first: `audio_stream_controller.py` -> move the epoch registry (`next_stream_epoch`, `ws_id`, lines 104-153) to `stream_epoch.py` and replace the 11 one-line `_send_*` wrappers (190-235) with direct calls to `stream_messages`; `stream_enhanced.py` -> see TD9-06. Then add the seven paths and run `python scripts/check_loc_ratchet.py --update` so each is held at its real size, not 299.

#### TD9-02: The LOC ratchet is Python-only, and the one closed frontend split target has already regrown past 300
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts:1-308`; `loc-ceilings.json` (no `.ts`/`.tsx` entry)
- **Status**: NEW
- **Age**: split in 8f7d350d (#4301, 595 L); regrown by a5ee430b (#5657) and f65a4913
- **Effort**: small (<=2 h)
- **Description**: `AudioPlaybackEngine.ts` was split under #4301 (closed) and is now 308 lines. All 85 ratchet entries are Python, so the frontend closes of #4301, #4456, #4916, #5631, #5840 and #5841 have nothing holding them. Fifteen shipped TS files already sit between 285 and 298 lines (`useLibraryQuery.ts` 298, `StarfieldBackground.tsx` 296, `AlbumCharacterPane.tsx` 295, `useAudioStreamingCore.ts` 293, `useWebSocketConnection.ts` 291, `useProgressBarInteraction.ts` 290, `CozyLibraryView.tsx` 289, `useQueueMutations.ts` 288, `PCMStreamBuffer.ts` 287, `errorTrackingMiddleware.ts` 286...), so the next fix pushes several of them over.
- **Evidence**: `wc -l` 308; `scripts/check_loc_ratchet.py` `measure()` accepts any file path, so no script change is needed to enrol TS files. `loc-ceilings.json` has zero `.ts`/`.tsx` keys.
- **Impact**: Frontend god-file splits regress silently, the same way Python ones did before #5830.
- **Siblings**: the near-limit files above.
- **Related**: TD9-11 (several of those files only fit by being one 200+ line function).
- **Suggested Fix**: Split `AudioPlaybackEngine.ts`: move `createGlobalAnalyser` (lines 25-57, window-global analyser wiring) to `analyserNode.ts` and the three `on*` subscription methods (273-302) to a small listener-set helper, bringing it to about 250. Then add the engine and the closed #5840/#5841 targets to `loc-ceilings.json` with real-size ceilings.

#### TD9-03: 83 of 85 ceilings are the blanket 299, so the ratchet allows up to 240 lines of regrowth per file
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `loc-ceilings.json`
- **Status**: NEW
- **Age**: f886a735 2026-10-22
- **Effort**: trivial (<=30 min)
- **Description**: A ratchet should hold each file at its closed size. 83 of 85 entries use 299 (the project rule), not the file's size: 58 entries have 50+ lines of free headroom and 36 have 100+. Examples (ceiling vs current): `player/queue_locked_state.py` 299 vs 58, `library/database_accessors.py` 299 vs 76, `library/migration_versions.py` 299 vs 78, `analysis/spectrum_weighting.py` 299 vs 97, `routers/health.py` 299 vs 111, `main.py` 299 vs 130. A 58-line file can quadruple before CI objects. The two non-299 entries are stale in the other direction: `core/hybrid_processor.py` ceiling 415 vs 359 now (still an offender, see TD9-08) and `core/processing_engine.py` ceiling 330 vs 299 now. No entry points at a missing file (checked).
- **Evidence**: `python scripts/check_loc_ratchet.py --list` (all 85 resolve to existing files).
- **Impact**: The gate only fails once a file crosses the 300-line rule, which `wc` and the audit already detect; it adds no early warning.
- **Siblings**: n/a
- **Related**: #5830
- **Suggested Fix**: Run `python scripts/check_loc_ratchet.py --update` once (it lowers each ceiling to current size) after TD9-01/TD9-02 enrol their paths, and say in the script docstring that new entries are written at current size. `hybrid_processor.py` stays above 300 until TD9-08 lands.

#### TD9-04: Backend WebSocket contract files over 300 (outbound_messages 501, playback_commands 495, stream_messages 315, state_manager 304)
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `auralis-web/backend/websocket/outbound_messages.py`, `auralis-web/backend/ws_handlers/playback_commands.py`, `auralis-web/backend/core/stream_messages.py`, `auralis-web/backend/core/state_manager.py`
- **Status**: NEW
- **Age**: `outbound_messages.py` c98bfb15 2026-10-20 (6 commits in 90 d); `playback_commands.py` ecb97003 2026-10-22 (14 commits)
- **Effort**: medium (<=1 day) for the four
- **Description**: Four files in the same WS layer, each mixing a second responsibility.
  - `outbound_messages.py` (501): ~45 Pydantic payload models in one flat file (lines 30-501) spanning player transport, queue, library/playlist/metadata, enhancement/mastering and system. Axis: package `websocket/outbound/` with `player.py` (Track/PlayerState/Playback*/Position/Volume), `queue.py` (QueueChanged*, Shuffled, RepeatMode), `library.py` (Library/Metadata/Playlist*/Artwork/CacheCleared), `enhancement.py` (EnhancementSettings, WeightedProfile, AlternativeProfile, MasteringRecommendation).
  - `playback_commands.py` (495): `resolve_enhancement_params` (44-110) and `_generate_mastering_recommendation` (139-186) are enhancement-parameter plumbing, not command handlers; `handle_seek` (380-495, 116 LOC) is a separate command. Axis: `ws_handlers/enhancement_params.py` (~110 LOC) and `ws_handlers/seek_command.py` (~120 LOC), leaving ~260 for `handle_play_enhanced`/`handle_play_normal`/`_cancel_prior_task`.
  - `stream_messages.py` (315): five `send_*` functions (stream start 49-134 at 85 LOC, end, error, completion 209-286 at 77 LOC, fingerprint progress). Axis: lifecycle messages (`send_stream_start/end/completion`, `ChunkPumpResult`) vs notifications (`send_error`, `send_fingerprint_progress`) in `stream_notifications.py`.
  - `state_manager.py` (304): the position ticker (`_start_position_updates`, `_stop_position_updates`, `_position_update_loop`, lines 222-304, nesting 5) is independent of the state mutators. Axis: `position_ticker.py`.
- **Evidence**: `grep -nE '^(class|def|async def)'` listings; 304/315/495/501 lines.
- **Impact**: `playback_commands.py` is the hottest file in the set (14 commits in 90 d), so every transport fix lands in a 495-line module that also owns seek and recommendation logic.
- **Siblings**: n/a
- **Related**: TD9-06 (the stream handlers called from playback_commands)
- **Suggested Fix**: As per axes above; repoint importers, no shims.

#### TD9-05: Backend chunk/processing pipeline files over 300 (chunk_boundaries 419, audio_processing_pipeline 373, level_manager 365, wav_encoder 329, chunk_operations 314)
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `auralis-web/backend/core/chunk_boundaries.py`, `audio_processing_pipeline.py`, `level_manager.py`, `encoding/wav_encoder.py`, `chunk_operations.py`
- **Status**: NEW
- **Age**: `chunk_boundaries.py` f3ea819a 2026-10-22 (8 commits in 90 d); `audio_processing_pipeline.py` ef0c6464 2026-10-22 (8)
- **Effort**: medium (<=1 day)
- **Description**:
  - `chunk_boundaries.py` (419): free functions and `NormalStreamPlan` (1-208) vs `ChunkBoundaryManager` (209-419). Axis: move the class to `chunk_boundary_manager.py`; the module stays the sole geometry authority for constants and pure functions (~210 LOC). Constants stay only in `chunk_boundaries.py` per the CLAUDE.md invariant.
  - `audio_processing_pipeline.py` (373): `validate_audio` (42-104), `select_processor` (104-151), `apply_enhancement` (151-293, 140 LOC), `process_audio`. Axis: `audio_validation.py` for input validation; `apply_enhancement` splits into resample/dispatch/finite-guard helpers.
  - `level_manager.py` (365): `smooth_transition` is 145 LOC (143-289) plus `_gain_envelope`; the rest is history/RMS bookkeeping. Axis: `level_transition.py` with `smooth_transition` and `_gain_envelope` as pure functions.
  - `wav_encoder.py` (329): `encode_and_save` (135-194) and `encode_and_save_from_path` (194-239) are two encode paths in one class beside path/cleanup/statistics methods (`get_chunk_path`, `cleanup_track_chunks`, `delete_chunk_files`, `get_statistics`). Axis: `chunk_files.py` (path layout and cleanup) vs the encoder.
  - `chunk_operations.py` (314): one class with two methods, `load_chunk_from_file` (130 LOC) and `extract_chunk_segment` (134 LOC). Axis: load vs extract modules, each with helpers pulled out (the 130-line functions are the real cost).
- **Evidence**: method line offsets from `grep -nE '^\s*(class|def|async def)'`; function sizes from the AST scan (`/tmp/audit/auralis/tech-debt/scratch_9/scan.py`).
- **Impact**: This is the audio-integrity path (sample counts, finite guards, chunk geometry). Smaller units make "does every path keep the finite guard" checkable.
- **Siblings**: n/a
- **Related**: #4895 (closed: two encode+persist WAV pipelines, one missing a guard) is the kind of drift the `wav_encoder` axis exposes; owning audit for any drift found is /audit-engine.
- **Suggested Fix**: As per axes above.

#### TD9-06: Five streaming functions of 190-264 LOC are the worst functions in the repo, and #5481's deferral cites a closed issue
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `auralis-web/backend/core/stream_enhanced.py:40` `stream_enhanced_audio` (264 LOC, file 303); `stream_seek.py:42` `stream_enhanced_audio_from_position` (251); `stream_normal.py:42` `stream_normal_audio` (236); `stream_normal_chunks.py:56` `pump_normal_chunks` (217, nesting 5); `stream_enhanced_chunks.py:94` `pump_chunks` (190, nesting 5)
- **Status**: NEW (open census #5481 puts these in "group 2, deferred by #5032", but #5032 is CLOSED, so the deferral has no live gate)
- **Age**: `stream_enhanced.py` 90245885 2026-10-22 (24 commits in 90 d, the most-churned file in this audit's list)
- **Effort**: medium (<=1 day) for one shared skeleton; large if done per handler
- **Description**: The three entry handlers repeat the same skeleton: semaphore permit (#2185/#4329), cooperative-cancel event registration (#4815), early-exit accounting (#4659), skipped-chunk accounting (#4790), processor construction under timeout, release in `finally`. Each handler's own comments say "same as stream_enhanced.py" (see `stream_seek.py:102-118`), which is the duplication signal. The two pump loops carry the per-chunk try/recover and look-ahead logic at nesting depth 5. Note that part of each function's length is long rationale comments.
- **Evidence**: `stream_seek.py:102-104` "same mechanism as stream_enhanced.py, see its comment for the full rationale"; `stream_seek.py:115-117` "see stream_enhanced.py's identical field for the full rationale".
- **Impact**: Every stream-lifecycle fix (the #4329, #4815, #4659, #4790, #5253 history) has to be applied to three handlers by hand; one copy missing a fix is a leaked permit or temp WAV.
- **Siblings**: the five functions above; `handle_seek` in `playback_commands.py` (116 LOC) is the WS-side peer.
- **Related**: #5481 (open, update group 2), #5032 (closed), Dim 3 overlap on the repeated skeleton. If a missed fix is found, route to /audit-backend and /audit-concurrency.
- **Suggested Fix**: Extract an `async with StreamSession(...)` context manager (permit, cancel-event registration, processor release, error send) in `stream_session.py`; each handler keeps only its start-position/plan logic. Then split each pump into `_process_one_chunk` + loop to get nesting to 3. Verify `stream_enhanced.py` is under 300 LOC at close.
- **Merge note**: the duplication half of this is TD3-12; fix them together.

#### TD9-07: Backend service, security and route-support files over 300 (artwork_downloader 410, playback_service 390, path_security 383, fingerprint_generator 375, navigation_service 341, serializers 334)
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `auralis-web/backend/services/artwork_downloader.py`, `services/playback_service.py`, `security/path_security.py`, `analysis/fingerprint_generator.py`, `services/navigation_service.py`, `routers/serializers.py`
- **Status**: NEW
- **Age**: `playback_service.py` ef0c6464 2026-10-22 (13 commits in 90 d); `navigation_service.py` fdb22aee 2026-10-22 (10); `path_security.py` 87b33dcb 2026-10-22 (13)
- **Effort**: medium (<=1 day)
- **Description** (axis per file):
  - `artwork_downloader.py` (410): provider clients `_try_musicbrainz` (204-278) and `_try_itunes` (278-351) mixed with session/cache/save. Axis: `artwork_providers/musicbrainz.py`, `itunes.py`; downloader keeps session, `_save_artwork`, cache.
  - `playback_service.py` (390): lines 23-70 declare local `AudioPlayer`/`PlayerStateManager` stub classes for typing, then the service. Axis: move the stubs to `playback_protocols.py`; `play/pause/stop/seek/set_volume` stay.
  - `path_security.py` (383): allowlist registry (50-105: `register/unregister/clear_extra_allowed_directories`, `_system_directory_roots`) vs error types plus decorator (105-196) vs validators (196-383, `validate_file_path` 106 LOC). Axis: `path_allowlist.py` and `path_errors.py`.
  - `fingerprint_generator.py` (375): executor lifecycle (`_get_fingerprint_executor`, `shutdown_fingerprint_executor`, `shutdown_fingerprint_executor_bounded`, `_compute_windowed_fingerprint_in_thread`, lines 64-170) vs `FingerprintGenerator`. Axis: `fingerprint_executor.py`.
  - `navigation_service.py` (341): `_TrackChangeSequencer` (31-83) is a standalone sequencing primitive; `next_track`/`previous_track`/`jump_to_track` are 60/60/83 LOC at nesting 5 with the same follow-engine/broadcast shape. Axis: `track_change_sequencer.py` (-52 LOC) and one shared `_apply_track_change()` for the three.
  - `serializers.py` (334): generic `serialize_object` (1-200, with the Mock branches and `DEFAULT_*_FIELDS` maps tracked by open #5803) vs per-entity serializers (212-334). Axis: entity serializers to `serializers_library.py`; coordinate with #5803, which may shrink the generic half by itself.
- **Evidence**: method-offset listings; file sizes 410/390/383/375/341/334.
- **Impact**: `playback_service`, `navigation_service` and `path_security` are high-churn (10-13 commits in 90 d) and carry lock or security invariants that are easier to audit in small modules.
- **Siblings**: n/a
- **Related**: #5803 (open, serializers), TD9-09 note on the duplicated MusicBrainz client.
- **Suggested Fix**: As per axes above.

#### TD9-08: Engine core files over 300 (recording_type_detector 494, target_generator 371, hybrid_processor 359, adaptive_mode 342, mastering_presets 311, eq_processor 308, continuous_space 304, fingerprint_unpacker 304)
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `auralis/core/` (files listed)
- **Status**: NEW (`hybrid_processor.py` is a closed split target, #5463/#5830, held by ceiling 415, which is still above the 300 rule)
- **Age**: `hybrid_processor.py` 8373b8d1 2026-10-22 (23 commits in 90 d, highest churn of the set)
- **Effort**: medium (<=1 day) overall
- **Description** (axis per file):
  - `hybrid_processor.py` (359): `_process_reference_mode` / `_process_adaptive_mode` / `_process_hybrid_mode` (214-293) and the delegation block (293-340). `get_dynamics_info()` and `set_dynamics_mode()` have zero production callers (only `tests/regression/test_dynamics_processor_wiring.py` pins them; the `hybrid_setup.py:60` comment confirms); deleting both removes about 9 lines. Axis: move the three mode methods to `core/processing/mode_dispatch.py` beside the existing `adaptive_mode.py`/`continuous_mode.py`, and keep only construction, lifecycle and `process()` here.
  - `target_generator.py` (371): `_apply_preset_overrides` (139-246, 106 LOC) and `_apply_fingerprint_enhancements` (246-371, 126 LOC) dominate. Axis: `target_preset_overrides.py` and `target_fingerprint_adjustments.py`. (Open #5858 touches the second; fold the split into that fix.)
  - `adaptive_mode.py` (342): `_apply_final_normalization` is 109 LOC (230-340). Axis: `adaptive_normalization.py`.
  - `eq_processor.py` (308): `_process_with_psychoacoustic_eq` is 113 LOC (157-271). Axis: extract curve building (`_targets_to_eq_curve`, `_eq_curve_to_array`, `_apply_content_adjustments`) to `eq_curve.py`.
  - `continuous_space.py` (304): coordinate/parameter dataclasses (36-160) vs `ProcessingSpaceMapper` (161-304). Axis: `continuous_space_types.py`.
  - `fingerprint_unpacker.py` (304): ~25 hand-written one-line property accessors (lines 126-270). Axis: generate them from a field-name table (one descriptor), which also removes the need to touch two places per new dimension.
  - `recording_type_detector.py` (494): kept on purpose (offline scripts only, #4873/#5780) but still over the rule: scoring (`_score_bootleg/_score_metal/_score_studio`, 218-325) vs the four `_parameters_*` tables (345-494). Axis: `recording_type_parameters.py` with the tables.
  - `mastering_presets.py` (311): one dataclass of calibrated constants where most lines are per-field docstrings; it is a data file. If enforced, split by stage group into 2 dataclass bases; lowest priority.
- **Evidence**: method-offset listings; AST function sizes; `grep -rn "get_dynamics_info\|set_dynamics_mode" auralis auralis-web/backend` finds only the definitions and a comment.
- **Impact**: This is the DSP pipeline; 100+ LOC functions here (`_apply_final_normalization`, `_apply_fingerprint_enhancements`) are where sample-count and finite guards are easiest to drop.
- **Siblings**: n/a
- **Related**: #5858 (open), #5463/#5830 (closed), TD9-03 (`hybrid_processor` ceiling 415 vs 359).
- **Suggested Fix**: As per axes above; for `hybrid_processor.py` close only when verified under 300 LOC, then lower its ceiling.

#### TD9-09: Analysis, IO, player, service and library files over 300 (artwork_service 399, similarity 346, unified_loader 336, feature_extractor 322, playback_controller 320, fingerprint_worker 313, normalize_existing_artists 307, distance 302)
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: files listed
- **Status**: NEW
- **Age**: `unified_loader.py` ef0c6464 2026-10-22 (15 commits in 90 d); `playback_controller.py` 11b7e1b0 2026-10-22; `normalize_existing_artists.py` b6b51e9a 2026-05-27 (0 commits in 90 d)
- **Effort**: medium (<=1 day) overall
- **Description** (axis per file):
  - `artwork_service.py` (399): provider fetchers (`_fetch_from_musicbrainz` 150-219, `_fetch_from_discogs` 219-268, `_fetch_from_lastfm` 268-317, `_fetch_album_from_musicbrainz` 342+) plus a redirect handler. Axis: one module per provider. This class is used only by `auralis/cli/fetch_artwork.py`, while the server uses `backend/services/artwork_downloader.py` with its own MusicBrainz client: two parallel provider stacks (Dim 3 overlap); a per-provider split is the first step to sharing them.
  - `unified_loader.py` (336): `load_audio` is 121 LOC; `get_audio_info` plus `_get_info_with_soundfile`/`_get_info_with_ffprobe`/`_reject_oversize_probe` (162-325) are the probe layer. Axis: `audio_probe.py`.
  - `similarity.py` (346) and `distance.py` (302): axis: `get_similarity_explanation` (230-301) and `_get_prefiltered_candidates` to `similarity_explanation.py`; `DimensionWeights` (20-117) to `dimension_weights.py`.
  - `feature_extractor.py` (322): `extract_features` plus 12 private feature helpers. Axis: spectral/temporal helpers (127-217) vs MFCC/chroma/tonnetz/mel filterbank (263-322).
  - `playback_controller.py` (320): `defer_notifications` and `_dispatch_callbacks` (68-142, notification deferral) vs the transport state machine. Axis: `playback_notifier.py`.
  - `fingerprint_worker.py` (313): `_extract_bounded` (141-198) and `_process_track` (198-282) are per-track execution. Axis: `fingerprint_track_runner.py`.
  - `normalize_existing_artists.py` (307): `_normalize_inner` is 191 LOC at nesting 5; a one-off migration script untouched since May. Axis: if kept, split into collect/merge/commit helpers; if no migration step still invokes it, delete it (Dim 2).
- **Evidence**: method-offset listings; `grep -rn ArtworkService` importers (CLI only).
- **Impact**: moderate; these are lower-churn than TD9-04..08.
- **Siblings**: n/a
- **Related**: TD9-07 (artwork downloader), #5481.
- **Suggested Fix**: As per axes above.

#### TD9-10: `auralis/dsp/utils/__init__.py` re-exports 25 names; only 6 have any importer via the package
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `auralis/dsp/utils/__init__.py:12-81`
- **Status**: NEW
- **Effort**: trivial (<=30 min)
- **Description**: The package re-exports 25 names (`__all__` 25) across 7 submodules. Via `from auralis.dsp.utils import ...` only `create_mel_triangular_filters` (one production importer, `analysis/ml/feature_extractor.py:22`) and five names in `tests/auralis/dsp/test_level_measurement_helpers_5785.py` (`SILENCE_FLOOR_DB, amplitude_to_db, peak_db, rms_db, to_db`) are used; 78 other imports go straight to submodules. The other 19 names are re-exports with no importer.
- **Evidence**: `grep -rn "dsp.utils import" auralis auralis-web tests --include='*.py'` returns those two files. The other barrels over 20 are healthy facades (`backend/schemas/__init__.py` 32 names with 52 barrel importers; `design-system/index.ts` 37 and `primitives/index.ts` 31 with 199 barrel importers).
- **Impact**: A 25-name facade nobody uses invites a second import route and hides which submodule owns a function.
- **Siblings**: none over 20 elsewhere.
- **Related**: #5778 (closed: 27 unimported frontend barrels), same pattern on the Python side.
- **Suggested Fix**: Point the production file and the test at `auralis.dsp.utils.interpolation_helpers` / `.conversion`, then reduce `__init__.py` to a docstring.

#### TD9-11: Frontend hooks whose single function runs 195-250 lines; several only meet the 300-line file rule by being one function
- **Severity**: LOW
- **Dimension**: File/Function Complexity
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueMutations.ts:40` (249), `components/player/useProgressBarInteraction.ts:43` (248), `contexts/PlaybackSessionContext.tsx:42` (235), `hooks/library/useLibraryQuery.ts:59` (235), `hooks/library/useLibraryPagination.ts:27` (229), `hooks/websocket/useWebSocketConnection.ts:67` (225), `hooks/enhancement/useAudioStreamingCore.ts:80` (212), `hooks/enhancement/useEnhancementCommands.ts:44` (209), `hooks/enhancement/useStreamMessageHandlers.ts:64` (204), `hooks/player/usePlayerStateSync.ts:46` (196)
- **Status**: NEW (#5481 covers Python only; #5840/#5841, which touched four of these files, are closed and measured file size, not function size)
- **Effort**: medium (<=1 day) for the group; each hook is small
- **Description**: 85 shipped TS functions exceed 100 lines; most are JSX components (acceptable), but these ten are hooks/providers with no JSX, so the length is logic. Axis per hook:
  - `useQueueMutations`: `runOptimistic` plus nine mutations; split into `useQueueEditMutations` (add/remove/reorder/clear) and `useQueueModeMutations` (shuffle/repeat), composed by a thin hook.
  - `useProgressBarInteraction`: mouse (97-179), keyboard (179-197) and touch (197-258) handlers in one body; split into `useProgressBarDrag` and `useProgressBarTouch`, keep keyboard inline.
  - `useEnhancementCommands`: `toggleEnabled` / `setPreset` / `setIntensity` repeat the same request-id/in-flight guard (`isTogglingRef`, `presetRequestIdRef`, `intensityRequestIdRef`); extract `useLatestRequestGuard`.
  - `useLibraryQuery` / `useLibraryPagination`: `executeQuery` (120-191), `fetchMore` (191-253) and `fetchTracks` (66-148) / `refreshTracks` / `loadMore` carry the same request-id/abort bookkeeping; move it into the existing `libraryQueryRequest.ts` / `libraryPageFetch.ts`.
  - `useWebSocketConnection`: `connect` is 105 lines (135-240); extract reconnect scheduling and handler attachment to `wsConnectionLifecycle.ts`.
  - `PlaybackSessionProvider`: `handleNext` / `handlePrevious` / `handlePlayPause` (115-203) plus context value assembly (242-278); extract `usePlaybackSessionControls`.
  - `useAudioStreamingCore` (14 refs) and `useStreamMessageHandlers` (`handleChunk` 99 LOC): split by lifecycle stage (start / chunk / end-error).
- **Evidence**: TS compiler-API scan (`/tmp/audit/auralis/tech-debt/scratch_9/ts_scan.cjs`); `themeComponents.ts createComponents` (275) and the 20+ JSX components over 150 lines are omitted as declarative.
- **Impact**: These sit on the player/streaming path; the request-guard duplication is where one hook gets a race fix and its sibling does not.
- **Siblings**: the near-limit file list in TD9-02.
- **Related**: TD9-02; Dim 3 overlap on the request-guard pattern.
- **Suggested Fix**: As per axes above; start with `useLatestRequestGuard` since it also removes duplication.

---

### Dimension 10: Audit-Finding Rot

#### TD10-01: `_audit-common.md` says a closed issue "tracks" the remaining LibraryManager docs, and the claim is also wrong
- **Severity**: LOW
- **Dimension**: Audit-Finding Rot
- **Location**: `.claude/commands/_audit-common.md:80`
- **Status**: NEW
- **Age**: b75d62a4 2026-08-27
- **Effort**: trivial (<=30 min)
- **Description**: The Retired Architecture row for `LibraryManager` says a grep for the old name "returns nothing outside `tests/` and the docs #5031 tracks". #5031 is CLOSED (2026-08-07, "docs/subsystems/backend-api.md still describes LibraryManager..."), so no open issue tracks any remaining docs. The claim is also false in the other direction. The name still appears in `auralis-web/PHASE_7_VIEWING_GUIDE.md:65-66` (`from auralis.library import LibraryManager; lm = LibraryManager()`) and in `docs/MIGRATION_GUIDE.md` (31 hits, written in present tense: "marked DEPRECATED ... removed once those call sites are migrated"). It appears in about 10 more non-archive docs under `docs/development/` and `docs/features/`. An auditor following the row concludes the leftovers are known and tracked, or treats `MIGRATION_GUIDE.md` as live guidance. The row is the only place that tells them which it is.
- **Evidence**: `git grep -l LibraryManager -- auralis auralis-web scripts` returns `auralis-web/PHASE_7_VIEWING_GUIDE.md` and a past-tense comment in `scripts/development/profile_fingerprint_memory.py:60`. `git grep -c LibraryManager -- docs ':!docs/archive' ':!docs/audits'` returns 15 or more files. `auralis/library/manager.py` does not exist.
- **Impact**: A stale "tracked" pointer. A reader skips the leftovers as accounted for, though nothing tracks them. The present-tense migration guide for a class deleted in #4915 keeps misleading.
- **Siblings**: The same "tracked by closed issue" shape is not present elsewhere; every other closed-issue ref in the skill and agent files is provenance (about 380 refs checked, 371 CLOSED, 9 OPEN, none phrased as pending).
- **Related**: Dim 7 (the stale docs themselves: `docs/MIGRATION_GUIDE.md`, `auralis-web/PHASE_7_VIEWING_GUIDE.md`). Report those under Dim 7 and only the skill wording here.
- **Suggested Fix**: Reword the sentence to "... outside `tests/`, `docs/` (e.g. `docs/MIGRATION_GUIDE.md`, `auralis-web/PHASE_7_VIEWING_GUIDE.md`) and past-tense comments; none of it is tracked by an open issue — report doc mentions under Dim 7, not as a live construction". Delete the `#5031` reference.

#### TD10-02: #5847's `/tmp/audit` namespacing fix reached only audit-tech-debt.md; six sibling audits and the shared dedup recipe still use bare `/tmp/audit/<name>`
- **Severity**: LOW
- **Dimension**: Audit-Finding Rot
- **Location**: `.claude/commands/_audit-common.md:180`; `.claude/commands/audit-backend.md:197,252`; `audit-concurrency.md:112,161`; `audit-engine.md:164,214`; `audit-frontend.md:158,210`; `audit-integration.md:171,226`; `audit-security.md:143,199`
- **Status**: NEW (sibling gap of closed #5847, whose point (d) was fixed in `audit-tech-debt.md` only)
- **Age**: b869bca7 2026-03-19 (engine); namespaced fix in 2030b97d 2026-10-22
- **Effort**: small (<=2 h)
- **Description**: `audit-tech-debt.md` now writes to `/tmp/audit/auralis/tech-debt/` and says why: "`/tmp/audit/<audit-name>` is shared by every repo on the machine, and a second project's tech-debt run overwrote this one's `dim_*.md` files (#5847)". Its Phase 4 `rm -rf`s only that namespaced directory. The six deep audits and `_audit-common.md`'s generic dedup recipe still write `/tmp/audit/engine`, `/tmp/audit/backend`, `/tmp/audit/frontend`, `/tmp/audit/concurrency`, `/tmp/audit/integration`, `/tmp/audit/security` and `/tmp/audit/issues.json`, and each runs `rm -rf /tmp/audit/<name>` in Phase 4. The hazard is real on this machine: another repo's `.claude/commands/` (`/mnt/data/src/distributed-ai-platform/.claude/commands/audit-backend.md`, `audit-concurrency.md`, `audit-frontend.md`, `_audit-common.md`) uses the same `/tmp/audit/` prefix, and `/tmp/audit/issues.json` already exists there as a shared bare-path file. A concurrent run of either repo's backend or engine audit clobbers the other's `issues.json` and `dim_*.md`, and its cleanup deletes the other's inputs mid-run.
- **Evidence**: `grep -n "rm -rf /tmp/audit" .claude/commands/*.md` lists `concurrency`, `backend`, `engine`, `frontend`, `integration`, `security` (bare) and `auralis/tech-debt` (namespaced). 17+11+13+15+15+16 `/tmp/audit/` mentions in the six files.
- **Impact**: Silent cross-project input/output overwrite for any multi-repo session; a dedup file from the wrong repo makes "NEW" findings that are really closed issues from the other project, or the reverse.
- **Siblings**: The six audit files above plus `_audit-common.md:180`. `audit-deprecation.md` and `audit-incremental.md` write only to `docs/audits/` and are unaffected.
- **Related**: #5847 (closed, partial fix), #5848 (open: `/audit-sync` skill, separate defect).
- **Suggested Fix**: Mechanical rename `/tmp/audit/<name>` to `/tmp/audit/auralis/<name>` in the six files and in `_audit-common.md`'s dedup path (`/tmp/audit/auralis/issues.json`). Add a one-line rule in `_audit-common.md` ("scratch lives under `/tmp/audit/auralis/`") so the next audit skill copies the right prefix.

#### TD10-03: Every dedup recipe hardcodes `--limit 6000` while the rule beside it says the limit must exceed the highest issue number (now 5859)
- **Severity**: LOW
- **Dimension**: Audit-Finding Rot
- **Location**: `.claude/commands/_audit-common.md:180-181`; `audit-tech-debt.md:62`; `audit-backend.md:197`; `audit-concurrency.md:112`; `audit-engine.md:164`; `audit-frontend.md:158`; `audit-integration.md:171`; `audit-security.md:143`; `audit-publish.md:42`
- **Status**: NEW
- **Age**: 2030b97d 2026-10-22 (the `--state all --limit 6000` form from the #5843 fix)
- **Effort**: trivial (<=30 min)
- **Description**: `_audit-common.md:181` states "The `--limit` must exceed the highest issue number, or the dump is silently truncated". The literal `6000` sits 141 numbers above the current highest (#5859). Today's dump has 5613 issues (PRs consume numbers, so the real constraint is the issue count, margin 387). That margin is already used up at the pace of one audit publish (this audit alone files tens of issues), and a truncated dump makes dedup silently miss the highest-numbered issues, i.e. exactly the newest ones an audit most needs to match. Nine copies must each be edited when it breaks.
- **Evidence**: `gh issue list --state all --limit 1 --json number` returns 5859; `issues.json` length 5613; nine occurrences of `--limit 6000`.
- **Impact**: A silent dedup hole that appears with no error: NEW findings that duplicate recent issues, or missed "Regression of #N" matches. The failure is invisible to the path gate.
- **Siblings**: The nine files listed. `audit-search.md:84` (`--limit 1000 --state open`, label histogram only) and `audit-regression.md:33` (`--limit 50`, intentionally bounded) are different.
- **Related**: #5843 (closed; introduced `--state all` and this literal).
- **Suggested Fix**: Define the command once in `_audit-common.md` Deduplication with a limit that cannot be exceeded in practice (for example `--limit 100000`) and make the eight audit files point to it. Alternatively add a post-dump assertion (`jq 'map(.number)|max'` against `gh issue list --limit 1 --state all`) to the recipe.

#### TD10-04: audit-tech-debt.md Phase 1 reports two metrics whose values are entirely false positives, with no metric note and no Dim 5 carve-out
- **Severity**: LOW
- **Dimension**: Audit-Finding Rot
- **Location**: `.claude/commands/audit-tech-debt.md:128` (NotImplementedError), `:138` (skipped tests (ts)), the Metric notes table (`:150-164`), Dim 5 checklist `:243`
- **Status**: NEW
- **Age**: 1b7b5135 2026-05-30 (both greps); notes table added by the #4564 pass
- **Effort**: trivial (<=30 min)
- **Description**: The Metric notes table carries rows for seven metrics and leaves out the others, including these two, which today read as debt but are not.
  - `skipped tests (ts)` = 3 in baseline.txt. All three hits are English prose, none an actual skipped test: `auralis-web/frontend/src/tests/integration-tests-exercise-production-code.test.ts:104` (an error-message string saying "mark it describe.skip"), and `auralis-web/frontend/src/tests/integration/README.md:11,92` (a Markdown file, matched because the grep has no `--include`). The true skipped frontend test count is 0. This is the same prose-in-a-guard-test noise the `'any'` metric was fixed for in #5451.
  - `NotImplementedError` = 12 in baseline.txt. All 12 are one-line cross-mixin hook declarations in mixin base classes (`raise NotImplementedError` as the typed declaration of a method the composing class provides). Examples: `auralis/player/integration_library.py:29,32`, `auralis/player/queue_loading.py:26,29`, `auralis/player/components/queue_shuffle.py:24`, `auralis/player/components/queue_navigation.py:34`, `auralis/player/gapless_prebuffer.py:36`, `auralis/player/integration_reporting.py:39`, `auralis/analysis/dynamic_range_dynamics.py:27`, `auralis-web/backend/services/scanner_watchdog.py:77`, `auralis/library/metadata_editor/batch.py:23`, `auralis-web/backend/core/streamlined_lifecycle.py:24`. Dim 5's first bullet says to examine "every `raise NotImplementedError` ... is the call site reachable ... (Reachable → promote to MEDIUM)", and the promotion table has the same trigger, so each Dim 5 run re-derives that all 12 are hook declarations and risks promoting them.
- **Evidence**: See above; `grep -RInE '\b(it|test|describe)\.(skip|todo)\b' auralis-web/frontend/src` returns only the three prose hits.
- **Impact**: The report's Baseline Snapshot overstates skipped tests (3 vs 0) and stub count (12 vs 0 genuine stubs), and Dim 5/Dim 6 agents spend time re-proving it each run.
- **Siblings**: `skipped tests (py)` (31) legitimately counts `skipif`; not a false positive. The duplicated hook names (`_get_current_track_unlocked` declared in both `queue_shuffle.py` and `queue_navigation.py`, `_notify_callbacks` in both `integration_library.py` and `integration_reporting.py`) are a separate Dim 3 question; not reported here.
- **Related**: #4564, #5451 (same class of metric fix); #5238 (mixin composition pattern).
- **Suggested Fix**: Add `--include='*.ts' --include='*.tsx'` to the `skipped tests (ts)` grep and drop lines in string literals, or exclude the guard test. Add two Metric notes rows ("NotImplementedError: counts mixin hook declarations, a typed-contract idiom; read as 'hooks', not debt. Only a body with logic, or a hook with no overriding class, is a Dim 5 finding"). Add the same Don't-flag line to the Dim 5 checklist.
- **Merge note**: absorbs TD6-11. The Python `skipped tests (py)` figure (31) is also inflated, to about 29 real decorators, because the regex matches prose. Anchor both skip greps (e.g. `^\s*@pytest\.mark\.` and `^\s*(it|test|describe)\.(skip|todo)\(`) when adding the metric notes.

## Appendix: per-dimension skipped (existing issues) and checked-clean notes

### Dimension 1: Stale Markers

#### Skipped: existing open issues
- `TODO(#5537)` at `vendor/auralis-dsp/src/py_bindings.rs:174` cites a CLOSED issue: already covered by OPEN #5738 (its body names the dangling marker and its acceptance criteria require "No `TODO(#5537)` marker remains"). Note #5764 (closed, removed nine bindings) left `process_chunks_wrapper` and `chunk_processor.rs` in place, so the marker and the dead binding are both still present, and the file header (`py_bindings.rs:5-6`) now cites #5738 while line 174 cites #5537. Status: Existing: #5738. Prior report: TD1-01 in AUDIT_TECH_DEBT_2026-10-21.md (merged into #5738 there).
- `tests/test_pyo3_channel_axis_guards_4502.py` is the only Python caller of `auralis_dsp.process_chunks`; it goes with #5738.

#### Checked and clean
- Marker census: 4 genuine markers, each with an issue number; 3 cite OPEN issues (#5858, #5484, #5851); no bare marker; none older than 6 months; none in a `NotImplementedError`/`pass`/`...` stub body.
- Reachability: `TODO(#5858)` is on the live path (`hybrid_setup.py` creates `AdaptiveTargetGenerator`; `target_generator.py:54` calls `_apply_fingerprint_enhancements`) but it is a correctness issue already tracked open (fraction vs percent thresholds): owner `/audit-engine`. `TODO(#5484)` is a documented accepted risk. Nothing under `auralis/player/` or `routers/` carries a marker.
- HACK/XXX/FIXME around DSP math (`auralis/dsp`, `auralis/core`): zero hits, case-insensitive, including `vendor/auralis-dsp/src`. Nothing to route to `/audit-engine` from this dimension beyond #5858.
- The 9 `prose deferrals` hits are all ordinary prose: `mastering_chunk_loop.py:103` (umask explanation), `audio_processing_pipeline.py:198` (a lock-guarded save/restore of a flag, `try/finally`), `routers/errors.py:20,21,143` (503 copy), `queryRetry.ts:24` ("501 Not Implemented" status), `useEnhancementCommands.ts:84` ("not a workaround"), `security_headers.py:96` (the TODO(#5484) line, double-counted), `useAlbumFingerprint.ts:100` ("Settled decision, not a pending revisit"). The `continuous_dsp_ops.py:285` "revisit if peaky-chunk loudness loss matters" hit from the previous report is gone (the module still exists; the phrase was removed from it).
- Widened grep (`later|eventually|until we|once .* lands|follow-up|followup|placeholder`) over non-test source: ~750 raw lines, mostly `AGPL-3.0-or-later` license headers, "later chunk"/"later request" in race-condition explanations, "(#4250 follow-up)" back-references to closed work, and UI "placeholder" gradients/skeletons. Read the plausible ones; deferrals found are TD1-01..03. Not reported: `AlbumsTab.tsx:82` ("can be enhanced later", a 2025-12 JSX wish-comment, not a deferred decision), `processing_parameters.py:28` and `similarity_deps.py:16` (documented placeholder defaults with tests/flags, `is_default: True` per #3779), the "out of scope" in `security_headers.py:106` (the settled CSP style-src rationale, tracked by #5484), `ffmpeg_probe.py` aside from TD1-04.
- Second widening (`out of scope|separate issue|not yet implemented|in the future|time being|stopgap|interim|kludge|tech debt|stub`): 12 hits, only `playback_control.py:87` and `ffmpeg_probe.py:32` are deferrals (TD1-02, TD1-04); the rest are descriptions of existing test doubles or fallback pages.
- tests/ census: 1 genuine marker (`TODO(#5851)`, OPEN, filed today); the former `TODO(#5172/#5173/#5174)` markers are gone. The two `XXXX` redaction/temp-name hits remain filtered false positives.

### Dimension 2: Dead Code

#### Skipped: existing open issues
- `GenreRepository.get_tracks_by_genre` dead method: Existing #5754
- Rust `process_chunks` / `chunk_processor.rs` dead: Existing #5738
- `process_all_chunks_async` zero production callers: Existing #5495; `HeartbeatManager.is_alive` dead: Existing #5494
- Orphaned frontend components (ProcessingToast, TrackCardInfo/Overlay, SearchInputAdornments, LibraryHeader, EmptyState, AlbumArtDisplay, LoadingSpinner ...): Existing #5628
- Dead selector cluster `store/selectors/*` and `selectConnectionHealth`: Existing #5129
- `themeConfig.ts` dead parallel palette / `glassEffects`: Existing #5646; unused design-system primitives: Existing #5132; duplicate ErrorBoundary: Existing #5128; write-dead connection slice: Existing #5615
- Scanner `file_hash` and unused schema columns: Existing #5755
- `proactive_buffer.buffer_presets_for_track` dead loop level: Existing #5839

#### Checked and clean
- `ruff F811/F841`: no hits; F401 only the five in TD2-13 (`noqa`-marked re-exports are TD2-01).
- Retired clusters from `_audit-common.md` (LibraryManager, parallel/, stream_prefetch, crossfade helper, preference-learning engine, nine PyO3 bindings): no live identifier or import remains. `rg` for preference-learning terms finds only the breadcrumb comment at `auralis/core/config/settings.py:60` (a "removed in #5763" note; belongs to the breadcrumb sweep of Dimension 8/#5820, not dead code). `auralis/learning/` holds only `reference_seeder.py` (live: `startup/components.py:112`, `routers/library.py:60`).
- #5764 fallout on the Python side: no `.pyi` stubs exist; no Python or test references `auralis_dsp.hpss/yin/detect_*`; the two remaining mentions (`dsp/utils/spectral.py:195`, `tests/auralis/dsp/test_tempo_estimate_no_dead_rust_path_5168.py:12`) are explanatory text about a removed branch.
- Rust: no `#[allow(dead_code)]` or `#[allow(unused)]` anywhere in `vendor/auralis-dsp/src`; all `pub fn` in `rhythm`, `chroma`, `frequency_analysis`, `spectral_features`, `variation_analysis`, `stereo_analysis` are called from `fingerprint_compute` (reachable from `compute_fingerprint_wrapper`); only `chunk_processor` is unreachable (#5738).
- Stale `# type: ignore`: 40 of 44 still required (mypy `warn_unused_ignores` is already enabled in `pyproject.toml`).
- Private (`_name`) functions left in coordinators after the splits: vulture lists none; the only private unused hits are `_reset_registry_miss_warning` (test hook, documented) and framework callbacks (`_set_pragmas`, `set_sqlite_pragma` SQLAlchemy events).
- Mixin hook stubs: no `raise NotImplementedError` or `...` bodies in any `*mixin*.py`.
- Frontend barrels: the 25 index.ts barrels removed by #5778 stay gone; remaining `index.ts` re-export names with no importer are covered by #5628/#5129/#5132 or are type-only.
- Out-of-scope observations for other dimensions: `set_sqlite_pragma` is defined twice (`library/database_engine.py:75`, `library/migration_engine.py:53`) with overlapping but not identical PRAGMA lists (Logic Duplication); the mixin/`routers` split commits left "removed in #NNNN" comments at `core/hybrid_setup.py:56-72` (Dimension 8).

### Dimension 3: Logic Duplication

#### Skipped: existing open issues
- Raw `fetch()` sites that bypass the shared transport (`useEnhancedPlayCommand.ts:100`, `usePlayTrack.ts:50`, `useFingerprintCoverage.ts:85,104`): Existing #5649.
- `useRestAPI` callers cannot abort and `queryFn`s never forward `signal`: Existing #5650 (consequence of TD3-14, and visible in TD3-19).
- `TrackListResponse` / `AlbumListResponse` paginated envelope duplicated: Existing #5499.
- `has_more`/`hasMore` and `current_index`/`currentIndex` dual spellings on the wire: Existing #5823.
- `target_generator` percent-vs-fraction band comparison and its percent-scale fallbacks: Existing #5858 (open, carried as `TODO(#5858)`).
- `GenreRepository.get_tracks_by_genre()` lacks `Track.genres` eager load (dead method): Existing #5754.
- `SimilarityGraphRepository` bypasses `RepositoryFactory`: Existing #5368.

#### Checked and clean
- Enhancement preset list: only `VALID_PRESETS` / `EnhancementPresetLiteral` (`schemas/enhancement.py:30-31`), `ENHANCEMENT_PRESETS` (`types/domain.ts:115`), and the deliberate `proactive_buffer.py:24-25` mirror; no `gentle/warm/bright/punchy/live` string is accepted or emitted anywhere outside the two documented survivors and comments. `playerSlice` / `enhancementState` derive from the domain type (#5610).
- DSP copy-before-modify: `amplify`, `normalize`, `CompressionStrategies.*`, `ExpansionStrategies.*` all `audio.copy()`; grep for in-place `*=`, `out=`, `[:] =`, `np.copyto` across `core/`, `dsp/`, `player/` found only `amplify` (post-copy) and `LookaheadBuffer.fill` (internal buffer). No sibling omits a guard its neighbour has, so no HIGH.
- NaN/finite guards: `validate_audio_finite` is one shared helper with consistent `repair` choice per stage; no private `nan_to_num` copies.
- Clip-to-[-1,1]: two sites only (`mastering_chunk_loop.py:208`, `io/saver.py:52`), different purposes.
- `dsp/utils/filters.py::sosfiltfilt_safe` is adopted at every `sosfiltfilt` call site (no raw `sosfiltfilt` left outside the helper).
- Backend exact-AST duplicate scan of all `auralis-web/backend` functions >250 chars of AST: none.
- Same-name function scan (auralis + backend): remaining same-name pairs are layered delegates (router -> service -> engine) or distinct domains, apart from those reported above; `version.py` pair and `get_cache_key` trio are not duplicates.
- Shared router helpers: HTTP error spellings go through `errors.py` (only 8 inline `raise HTTPException(status_code=...)` remain, all with bespoke detail); 503 spellings go through `require_service` (#5783).
- Frontend color helpers: single `colorSpace.ts` (`rgbToHex`, `rgbToHsl`, `colorDistance`) and one `hexToRgb` in the design system; no second RGB/HSL implementation.
- `queryRetry.ts` is the sole retry-eligibility rule; the only other backoff is `WebSocketManager` and `useProgressiveImageLoader` (UI image, different domain).
- Chunk constants and `content_chunk_count()` bypass: no new literal found in `stream_*` / `chunk_*` for this dimension (Dim 4 owns magic numbers).

- Dropped at merge, TD3-04: Existing: #5381 (OPEN, MEDIUM) already tracks `_with_similarity_error_handling` mapping OperationalError to 500 instead of 503; the consolidation onto `with_error_handling` is its fix. Also listed as Existing #5381 in AUDIT_BACKEND_2026-10-22.md.

### Dimension 4: Magic Numbers

#### Skipped: existing open issues
- Hardcoded 44.1 kHz in the genre-classifier `FeatureExtractor()` singleton: Existing #5244.
- Realtime chain built for `config.sample_rate`, not the track's: Existing #5729.
- `target_generator` compares fractional shares against percent defaults (`target_generator.py:272-275` bare `15.0/30.0/10.0/5.0` fallbacks): Existing #5858.
- Engine `MIN_SAMPLES` short-circuit skips `validate_audio_finite`: Existing #5191 (only the engine copy; the backend duplicate is TD4-01).

#### Checked and clean
- Chunk geometry literals (15/10/5 s): only `chunk_boundaries.py:20-23`; `grep` for `CHUNK_*`/`chunk_duration`/`overlap_duration` assignments outside it finds `mastering_config.CHUNK_DURATION_SEC = 30` (offline file-master loop, a different pipeline, name close but not the same concept) and nothing else.
- `ceil(duration / CHUNK_*)` bypassing `content_chunk_count()`: none; frontend has no chunk/seek arithmetic (it reads `chunk_duration` as a type only).
- Backend timeouts/TTLs/queue sizes: all in `config/limits.py`, `core/env_config.py` callers (`MAX_CONCURRENT_STREAMS`, `_SEND_QUEUE_MAXSIZE`, pool sizes, rate limits), or named module constants (`CHUNK_PROCESS_TIMEOUT`, `STREAM_ACQUIRE_TIMEOUT_SECONDS`, `BROADCAST_SEND_TIMEOUT`); the only inline literals are the shutdown waits in TD4-12. Yesterday's ffprobe/busy_timeout fixes verified in place (`SQLITE_BUSY_TIMEOUT_MS` used at all three sites).
- Port 8765 single-sourced in `config/origins.py:39`; `windows.py` fingerprint geometry single-sourced (`FINGERPRINT_SAMPLE_RATE`); accent RGB only in `globalStyles.ts:60` (`--accent-rgb`).
- Frontend timers/delays: every `setTimeout`/`setInterval`/delay in production code is a named constant or default parameter (`useAPIHealthPoll`, `useAutoHide`, `errorHandling.ts` reconnect config).
- Frontend `rgb()/rgba()`: zero literals outside `design-system/`.
- HIGH-trigger search: bare `44100/48000/96000` in sample-count arithmetic: only the `or 44100` None-narrowing after metadata load (`chunked_processor.py:119`, `chunk_render.py:158`), `_NOMINAL_SAMPLE_RATE` in `cache/models.py:31` (named, documented, eviction estimate), and message/ms formatting. No site computes a sample count from a hardcoded rate for a file of unknown rate.
- Frequency band edges (250/500/2000/4000/8000 Hz) repeat across `eq_processor.py`, `stage_snapshot.py`, `curves.py`, `stereo.py`, `mastering_notch_context.py`; treated as per-stage tuning tables with differing semantics, not flagged.
- Pagination bounds in routers (`le=100/1000/10000`) are per-endpoint API contracts, not shared tunables.

### Dimension 5: Stub Implementations

#### Skipped: existing open issues
- Track context menu "Add to Favourites / Go to Album / Go to Artist / Track Info" render as clickable but do nothing in the main library list and album table (`contextMenuActions.tsx:57-234` `callbacks.onX || (() => {})`; `TrackListViewContent.tsx:224` and `TrackTableRowItem.tsx:47` omit `onToggleFavorite`/`onShowAlbum`/`onShowArtist`/`onShowInfo`): Existing #5614 (MEDIUM, still reproduces on HEAD).
- Track context menu "Add to Playlist" never loads playlists (`TrackRow.tsx:192` `onPlaylistsLoad={() => { /* fetch playlists */ }}`): Existing #5617.

#### Checked and clean
- Pass-only / `...` / docstring-only bodies (AST over `auralis/` and `auralis-web/backend/`, 8 non-stub hits): every `...` body is a `Protocol` member (`queue_protocols.py`, `playback_service.py`, `outbound_messages.py` `@overload`s and `BroadcastManager`, `cache_cleanup.py:ClearableChunkCache`, `reference_seeder.py:_FingerprintRepoLike`) or an `@abstractmethod` of `BaseAssessor` (5 implementers). No `...` outside Protocol/abstract/overload.
- Empty constructors `AudioFingerprintAnalyzer.__init__` (`pass`) and `SidecarManager.__init__` (docstring-only): trivial, carried forward from the 2026-10-21 "not a finding" note; `AudioFingerprintAnalyzer.close()` no-op is deliberate and consumed by `HybridProcessor.close()` (documented in its docstring, #4744), not a stub.
- Functions returning `[]`/`{}`/`0.0`/`None` with stub/placeholder/not-yet/real-impl comments: regex sweep with 3 lines of context over both Python trees returned only `fingerprint_shared.py:70` (placeholder-row sentinel check, real logic) and `similarity_deps.py:16` (`_unavailable` default getter replaced by `RouterDeps` wiring before any request).
- Routes returning hardcoded/mock data: AST scan of all 95 `add_api_route` handlers plus decorator-registered routes for bodies with at most one real call found only `get_enhancement_status` (returns the live shared settings dict). `GET /api/processing/parameters` returns `_DEFAULT_PARAMETERS` only when no live profile exists and tags it `is_default: True` (#3779), which is an honest documented fallback; note its only frontend references are MSW handlers (no production consumer), a Dim 2 / `/sync-contracts` matter, not a stub. `ProcessingEngine.job_store: JobStore = JobStore()` ("no-op until wired") is wired in `config/startup/workers.py:120` and the class default is relied on by `tests/backend/test_reference_mode_wiring_4735.py:43` (`__new__`-built engine), so not removed.
- Prose deferrals / "not implemented" / 501 / "unsupported" in `routers/`, `ws_handlers/`, `services/`, `core/`: only user-input rejection paths (`files_upload.py`) and error-class docstrings.
- Frontend "Coming soon" / lorem / `throw new Error('Not implemented')` / mock data in non-test source: none (`AddToPlaylistMenu.tsx:6` is a comment recording the removed "Coming soon!" toast). `PanePlaceholders.tsx` renders genuine empty/pending states for `AlbumCharacterPane`, not stub content. Empty `() => {}` handlers: `contextMenuActions.tsx` (#5614), `TrackRow.tsx:192` (#5617), `MobileSidebarDrawer.tsx:40` (required `onOpen` of MUI `SwipeableDrawer`, intentional), plus `onStateChange`/`onBufferUnderrun` default-callback initialisers in `services/audio/` (legitimate null-object defaults). No disabled-without-handler controls: the three `<MenuItem disabled>` are "no playlists" label rows.
- Single-implementer ABCs (yesterday's TD5-06, #5806) and the placeholder barrel (TD5-04, #5805): both fixed and still fixed (`mastering_branches/` has no `base.py`; `BaseSpectrumAnalyzer` is gone). Settings-reset toast and `CozyLibraryView` no-ops (#5804) closed; not re-checked beyond the grep above.
- Observation for Dim 2 (not reported here): `getAlbumContextActions` (`contextMenuActions.tsx:131`) is exported from `shared/ContextMenu/index.ts` but has no caller anywhere in `src/`, so the album context-menu action builder is dead.

### Dimension 6: Test Hygiene

#### Skipped: existing open issues
- #5685: `tests/integration/test_api_workflows.py` -- all 20 tests error out through the hard-skipping `api_client` fixture (`pytest.skip(...)` at line 63); revival tracked there. Note this is the shape `test_no_unaccountable_skips_4691.py` cannot see (fixture-level skip, not `pytestmark`).
- #5187 / #5191: the only hard `@pytest.mark.skip` in `tests/backend/test_boundary_max_min_values.py:386` and the two strict `xfail`s in `tests/backend/test_error_handling.py:173,213` name these open issues; both are correctly accountable.
- #5678: frontend `vi.mock` targets that do not exist (`Integration.test.tsx`, `redux-flow.test.tsx`, `LibraryEmptyState.test.tsx`, `TrackRow*` ContextMenu); re-verified by my scanner, same 11 targets, no new ones after the #5840/#5841 splits.
- #5674: vacuous `expect(error).toBeDefined()` assertions (frontend: 38 spec files use `toBeTruthy()/toBeDefined()`; heaviest `useRestAPI.test.ts` 19, `testFixtures.test.ts` 14, `useAlbumFingerprint.test.ts` 12).
- #5682: the weak-assertion gate has no frontend equivalent.
- #5680: `setup.ts` console.error filter dead under `restoreMocks: true`.
- #5839: `proactive_buffer.buffer_presets_for_track` dead loop level (partly fixed by abb02d00; the leftover constant is TD6-05).
- #5803: `serialize_object()` Mock-class-name branch (production code branching on Mock; out of scope here).

#### Checked and clean
- **Skip rot (item 1)**: no skip/xfail guards a regression test for a closed CRITICAL/HIGH issue. Every remaining `skipif` is a platform, ffmpeg, mutagen, psutil, Pillow or soundfile dependency. The only issue-tagged hard skips name open #5187/#5191. Frontend: 0 real `it/test/describe.skip`/`.todo` (see TD6-11).
- **Post-split vacuous patches (item 5)**: scanned ~290 string `patch`/`monkeypatch.setattr` targets and every `patch.object(<module alias>, "name")`. All first-party targets resolve; no patch refers to a deleted module (checked all 91 files deleted since db9cc2e7 against `tests/` and frontend `src/`); every re-exported-only target (`auralis.io.loaders.load_with_ffmpeg`, `auralis.library.scanner.LibraryScanner`, `auralis.library.repositories.TrackRepository` aside) is reached by production through function-local imports; patched constants are read through the module (`_asc.CHUNK_PROCESS_TIMEOUT`, engine method `_load_audio` documented as resolving `gapless_playback_engine.load`), `ffmpeg_loader._probe_audio/_run_ffmpeg_cancellable/check_ffprobe` are used by `load_with_ffmpeg` itself, `services.scanner_watchdog.HAS_WATCHDOG` is read in the mixin. Inert patches found: TD6-04, TD6-05, and the dead autouse patch in TD6-03.
- **Source-text tests across the splits**: spot-checked the ones touching split files (`test_chunk_loop_sample_count_5511.py` reads `mastering_chunk_loop.py` + `mastering_chunk_assembly.py`; `test_post_limiter_invariants_5533.py` includes `hybrid_stage_dispatch.py`; `test_ws_connect_state_push.py` reads `ws_handlers/connection.py`); all were updated with the split.
- **Frontend mocks (item 4)**: `vi.mock` keys checked against production import names for all 190 mocks; no mock factory exports names production no longer imports from that path (`ComfortableApp.test.tsx` mocks both default and named). `NO_PROD_CONSUMER` hits (`SettingsDialog`, `KeyboardShortcutsHelp`) are `React.lazy` dynamic imports. Global auto-mock in `src/test/setup.ts` covers only `WebSocketContext` (8 specs `vi.unmock` it); the `vi.fn` factory survives `mockReset: true` in vitest 4. Only dead preamble comment: `// Mock window.matchMedia` sits above the IntersectionObserver mock (trivial, not reported).
- **Commented-out assertions (item 3)**: none in `tests/` (2 hits are prose containing the word "assert"); in the frontend the only commented `expect(` lines are the intentional placeholders in `src/test/TEMPLATE.example.tsx` (not collected, name does not match `*.test.tsx`). Print-only tests: the zero-assertion gate lists 34 tests and none is print-based (#5807 and #5225 cleared them); the only skipped bare-`pass` bodies are TD6-09.
- **Baseline files (item 6)**: `pytest-baseline.json` 80 entries (generatedFrom 149 failed / 6,889), all 80 ids resolve to existing files/classes/functions; `auralis-web/frontend/test-baseline.json` 96 entries (generatedFrom 96 failed / 3,349), all 17 files exist and all 96 titles are found in their spec files. No doc under `docs/` (excluding audits/archive), `CLAUDE.md`, `AGENTS.md`, `_audit-common.md` quotes a baseline entry count (they say "count the file"). The `validate.txt` figure "ratchet 280" is the doc-path-reference ratchet, unrelated to pytest-baseline.
- **Must-not-regress references (item 7)**: 48 distinct test paths named in `.claude/commands/audit-*.md` and `.agents/commands/audit-*.md`, all exist; none contains a skip other than platform guards (`test_artwork_path_validation.py` symlink, `test_migration_manager_fd_leak.py` `/proc/self/fd`, `tests/conftest.py` soundfile); no bare `test_xxx` name quoted in the skills is undefined.
- **Smoke-only assertions (item 2)**: `check_weak_assertions.py` default mode: 33 sole-`is not None` tests, worst files 3 each (`tests/stress/test_processing_stress.py`, `tests/boundaries/test_string_input_boundaries.py`, `tests/backend/test_string_input_boundaries.py`); all are baselined, none newly added. Gate stale entries and the red `--zero` run are TD6-01.

- Dropped at merge, TD6-06: Merged into TD2-01 (same `# noqa: F401` router-facade re-export blocks; Dim 6 counted 86 names on 7 facades, ~63 test-only across ~49 test files; the test retargeting is part of TD2-01's fix).

- Dropped at merge, TD6-11: Merged into TD10-04 (same fix site: the Phase 1 skip-count greps in audit-tech-debt.md).

### Dimension 7: Stale Documentation

#### Skipped: existing open issues
- None of the above overlaps an open issue (searched open titles for doc/stale/readme/version/websocket/architecture/contract; nearest are #5373 dev-launch paths and #5538 quantizer docstring, both different locations).

#### Checked and clean
- Version drift: `auralis/version.py` = `auralis/__version__.py` = `pyproject.toml` = root, `desktop/` and `auralis-web/frontend/` `package.json` = 1.5.1; `Cargo.toml` 0.1.0 is an independent crate version; README correctly says no 1.5.1 tag/binaries exist and quotes v1.2.0-beta.2 as the last binary; `docs/README.md` banner correct. Only the three hard-coded strings in TD7-09.
- `_audit-common.md` Project Layout: every named file/dir resolves (script over all `*.py|rs|ts|md` tokens; only deleted modules named in prose as deleted); 11 `vendor/auralis-dsp/src/*.rs`, "2 functions via py_bindings.rs", Learning row, Backend Streaming families, Library mixins, router sibling lists, Backend Cache mixins all match the live tree; test counts (~7,100 / 709 / 16 subdirs) correct.
- CLAUDE.md quantities: 20 routers, 12 repos, schema v23, docs topic dirs 18, test file/function line within the script's 10% tolerance (706/7,300 vs 709/7,112).
- `.claude/agents/*.md` repo and router counts (12, 20) correct.
- `file.py::symbol` anchors: only 5 in `.claude`/CLAUDE.md/docs/architecture/docs/subsystems; all are placeholders or deliberate deleted-path references.
- README / FIRST_TIME_SETUP / `auralis-web/README.md` command examples: use `launch-auralis-web.py` blocker note, `uv venv --python-preference only-managed`, `pnpm`; no `build_auralis.py` / `python -m auralis.library.init` outside `.claude/settings.local.json.backup` (not a doc).
- PyO3 binding removal (#5764) in `.pyi`: no stubs exist; `docs/features/RUST_DSP_STATUS.md`, `dsp-engine.md:189`, `fingerprinting.md:160-163`, `.claude/agents/dsp-specialist.md:32`, `tests/vendor/test_rust_panic_handler.py` are accurate (only the leftovers in TD7-08).
- Preference-engine removal (#5763): `auralis/learning/__init__.py`, `core/config/settings.py` comments, CLAUDE.md and `_audit-common.md` accurate; leftovers only in `module-map.md:55` (TD7-02) and `docs/MASTER_ROADMAP.md:133` (a roadmap row naming `preference_engine`/`reference_library` as the foundation; roadmap is a frozen historical doc per #4263, left out).
- WEBSOCKET_API.md message-type inventory: 34-member union matches `registry.ts`, `BroadcastMessageType` (26) plus stream/system types emitted from `stream_messages.py`; no type documented-but-never-emitted and none emitted-but-undocumented (client commands `play_enhanced/play_normal/pause/resume/stop/seek/buffer_*/ping/pong/heartbeat` match `WebSocketMessageType`).
- Yesterday's TD7-01/02/04/05/06 targets (queue-history refs, `components/shared/ui/README.md`, `quick_build.sh`, PyInstaller hiddenimports) are fixed in the tree; `auralis-backend.spec` imports all resolve.
- Backticked-path convention in `.claude/commands/audit-*.md`: gate clean.

### Dimension 8: Backwards-Compat Cruft

#### Skipped: existing open issues
- #5686: `QueueController.set_queue()` docstring "for backward compatibility" (`auralis/player/queue_loading.py:115`) and the duplicate `get_track_count()`/`get_queue_size()`: already covers the stale label I found on a live method.
- #5755: dead `tracks` columns and indexes; partial overlap with TD8-11 (stats-repo methods) and the home for TD8-07's two columns.
- #5823: `currentIndex`/`hasMore` and Track twin fields; adjacent to TD8-04 but different keys.
- #5689: pytest.ini ignores `PendingDeprecationWarning`; no deprecation shims remain in source for it to hide.

#### Checked and clean
- `@deprecated` JSDoc / `warnings.warn(DeprecationWarning)` / `@deprecated` decorator: none in `auralis/`, `auralis-web/backend/`, `auralis-web/frontend/src/` (rg); only `Navigator.platform`/`clip` comments describing replaced browser APIs.
- Backend dual request field names: no `AliasChoices`/`validation_alias`; only `MetadataUpdateRequest` (in TD8-04).
- `__getattr__` module shims: exactly one (`backend/config/__init__.py`, in TD8-08).
- Module-level alias assignments (`Old = New`): only `system_streams` (TD8-08), `CancelButtonForDialog` (TD8-12), three type aliases that are used (`PresetName`, `ConnectionStatusType`, `ChipProps`-style MUI props). No `export { X as Y }` compat alias besides the tabs ones.
- No-Variants names: no `*_v2`/`*2.tsx`/`*New`/`*Old`/`*Legacy` module, class or component exists. `advanced_dynamics.py` has no non-advanced sibling (`dsp/dynamics/` is the component package; the `DynamicsProcessor`/`DynamicsManager` dead chain is TD2's finding). `Simple*` (`SimpleMasteringPipeline/Config`) has no non-Simple pair (#5829 closed). `useEnhanced*` hooks are the enhanced-stream path, `usePlayNormal` was removed, no pair. `enhanced_audio_player.py` (class `AudioPlayer`) is the sanctioned name.
- `AdaptiveMode` "Legacy path" and the "legacy deficit-based EQ" fallback: both live and documented (STREAMLINING_PLAN #5 product decision; deficit EQ is the no-reference-cloud fallback, `hybrid_setup.py:98`).
- `HAS_AURALIS`/`HAS_*` flags: still present in `config/routes.py` and `config/startup`; closed #5826 kept them on purpose as a test seam (decision recorded in the issue), so not re-reported.
- Removed preset names (`gentle/warm/bright/punchy/live`): no code literal accepts or maps them; survivors are `preset_anchors.py`, the Player test sentinel, comments, and the two vestigial columns (TD8-07). `default_preset` read sites are clean after #5824 (`helpers.py:110` seeds directly; `SettingsDialogContent.tsx:89`'s `?? 'adaptive'` guards the pre-fetch state only).
- DB-schema compat for passed versions: `batch_processor.py:123` NULL `file_mtime` ("pre-v22 rows") is real semantics; `models/fingerprint.py:116` and `schema_indexes.py:28` index-name parity with upgraded DBs is a live need; the old `migration_manager` re-exports of backup/lock helpers are used internally.
- `_`-prefixed parameters in frontend: remaining `_error`/`_e`/`_event` are required-signature callbacks (MUI `onChange`, ErrorBoundary `fallback`); `_exhaustive: never` is an exhaustiveness idiom. `tsconfig.json` has `noUnusedParameters: true`.
- Python `_`-prefixed parameters: `_exc`, `_record`, `connection_record`, `_args/_kwargs` are required by `__exit__`/event-listener/callback signatures.
- Rust `vendor/auralis-dsp/src`: no compat/deprecated/legacy code; only two `#5764` breadcrumb comments (listed in TD8-01).
- `desktop/resources/auralis/` (stale mirror of the package) is untracked build output (`git ls-files` empty), not audited.

### Dimension 9: File/Function Complexity

#### Skipped: existing open issues
- #5481 (open): Python function-length census. Today 59 functions over 100 LOC (was 76). Worst: `stream_enhanced_audio` 264, `stream_enhanced_audio_from_position` 251, `stream_normal_audio` 236, `config/routes.py setup_routers` 231, `ContinuousMasteringBranch.apply` 225, `pump_normal_chunks` 217, `_normalize_inner` 191, `pump_chunks` 190, `advance_with_prebuffer` 168, `files_upload.upload_files` 164, `prepare_file` 155, `playlist add_track` 151. Its group-2 reference to #5032 is stale (closed); covered by TD9-06. Suggest updating #5481's numbers rather than re-filing.
- #5839 (open): nesting above 4. Today 25 functions (was 32); worst `migration_steps.apply_migration_sql` 6, then depth 5 in `artwork_service._fetch_from_musicbrainz`, `file_discovery._walk_directory`, `batch_processor.process_single_file`, `track_repository_lifecycle.add`, `playlist_crud_mixin.create`, `normalize_existing_artists._normalize_inner`, `migration_manager.check_and_migrate_database`, `migration_lock`, `queue_set_mixin._set_queue_impl`, `navigation_service` x3, `tracks.get_track_lyrics`, `fingerprint_status.get_track_fingerprint`, the `stream_*_chunks` pumps, `state_manager._position_update_loop`, `job_cleanup.cleanup_expired_jobs`, `fingerprint_queue._worker_loop`. `proactive_buffer.buffer_presets_for_track` no longer exceeds 4, so #5839's first bullet looks already done; re-measure when that issue is worked.
- #5803 (open): `serialize_object` Mock-class branching; relevant to the `serializers.py` split in TD9-07.
- #5858 (open): `target_generator._apply_fingerprint_enhancements` thresholds; fold the TD9-08 split into that fix.

#### Checked and clean
- Ratchet entries for deleted files: 0 (all 85 paths resolve; no stale entries).
- Closed split issues #5831-#5838: every named target is in `loc-ceilings.json` and under its ceiling.
- Mixin fan-out: the largest composition is `AudioPlayer` with 6 mixins (`TrackRepository` 5, `PlaylistRepository` 5, `FingerprintRepository` 4, `StreamlinedCacheManager` 4); none exceed 6. The `AudioPlayer` mixins declare the host attributes they read as class annotations (e.g. `player_streaming_mixin.py:45-53`, `player_queue_navigation_mixin.py:44-49`), so the shared-state contract is typed; no finding.
- React components with many hooks: no file exceeds 8 `useState`; one file exceeds 5 `useEffect` (`hooks/enhancement/usePlaybackTransport.ts`, 6 effects in 193 LOC), but it is already an extracted sub-hook and each effect has a single purpose (volume sync, time tick, pause sync, resume getter, disconnect), so no extraction proposed.
- `__init__.py`/`index.ts` over 20 re-exports: `backend/schemas/__init__.py` (32), `design-system/index.ts` (37), `design-system/primitives/index.ts` (31) are documented single-job facades with real importers; only `dsp/utils/__init__.py` produced a finding (TD9-10).
- Shipped TS files over 300: only `AudioPlaybackEngine.ts` (68 of the 69 offenders are test files and need no split under this checklist).

### Dimension 10: Audit-Finding Rot

#### Skipped: existing open issues
- #5848 — `/audit-sync` has never run and cites `/audit-suite` for a rule `/audit-suite` contradicts (the other session's uncommitted `audit-sync` work appears to address this; not re-reported).
- #5738 — Rust `process_chunks` is dead code (cited in audit-engine.md, verify-dsp.md, dsp-specialist.md, `_audit-common.md` as "dead/open"; correct, OPEN).
- #5823 — wire spelling cleanup, part 1 landed in `7d276150`; `sync-contracts.md:78` and `audit-integration.md:155` cite it as provenance for the removed camelCase fallbacks, which is accurate while the issue stays open for part 2 (Track twin fields).
- #5839 — nesting-depth issue, still OPEN with partial commits; `audit-engine.md:30` cites it only as provenance.

#### Checked and clean
- Path gate (`validate.txt`): exit 0, strict 0 stale, ratchet 280 = baseline 280. No auto-eligible findings.
- Symbol anchors: no `file.py::symbol` refs exist (only the two documentation examples `tests/path.py::test_name`, `some_module.py::function_name`). I checked every backticked identifier of 5+ characters (snake_case, CamelCase, UPPER_CASE) in `.claude/commands`, `.claude/agents` and CLAUDE.md for existence anywhere in `auralis/`, `auralis-web/`, `vendor/`, `scripts/`, `tests/`: the 81 misses are all intentional (deleted-symbol provenance such as `CacheMonitor`, `FingerprintCache`, `ProgressNotifier`, `apply_crossfade_between_chunks`, `VariationMetrics` etc., or placeholders/templates like `dim_N`, `flow_N`, `AUDIT_*_`). I verified every "`symbol` in `file`" pair in prose: only intentional list-style false positives. Symbols moved by the #5831-#5841 splits and `ClassName.method` refs (`JobWorker.cancel_task`, `BaseRepository._session_scope`, `PreferenceVector.from_preset_name`, `MigrationManager.close`, etc.) all resolve.
- Italic-marked "deleted" paths (`*factory.py*`, `*routers/files.py*`) are correctly described (`core/config/factory.py` gone; `routers/files.py` exists and the prose says it serves no files). The `_audit-common.md` Project Layout block (not backticked, so the gate does not see it) was checked line by line: no missing file.
- #5763/#5764/#5795/#5824 removals: the nine PyO3 binding names (hpss, yin, chroma_cqt, detect_tempo, envelope_follow, compress, limit, apply_multiband_eq, detect_onsets) appear only as "deleted in #5764" in `_audit-common.md`, `audit-engine.md`, `dsp-specialist.md`, `verify-dsp.md`. The `py_bindings.rs` registration shows exactly 2 functions (`compute_fingerprint`, `process_chunks`), `vendor/auralis-dsp/src` has 11 `.rs`. The preference engine is described only as removed (#5763).
- Issue refs: about 380 `#NNNN` mentions across commands, agents and CLAUDE.md. 371 are CLOSED, all provenance ("deleted in", "split by", "since"); 9 are OPEN (#5738, #5823, #5839, none called closed). Zero closed refs phrased as pending ("tracked in"/"until #N lands"/"open issue") apart from TD10-01. No open-issue number is described as fixed or closed.
- Dimension/flow/invariant counts: audit-tech-debt "all 10" matches its 10 Dimension headings and the 10-name Dimension field list; audit-integration "9 flows" matches Flow 1-9; verify-dsp "6 invariants" matches INV-1..6; audit-security lists A01-A10; audit-suite preset audit counts (comprehensive 8, tech-debt-deep 2, streaming-deep 3, pre-release 3, post-sprint 2, security-deep 3, audio-deep 3) match the listed steps, and its `--focus`/`--flows` numbers map to the intended dimensions (frontend 3/6, concurrency 1/2/3, backend 2/3/10/11, integration 1/3/5/8); the `(dim N)`/`(flow N)` routing in audit-search.md matches. No skill description carries a stale count.
- `.agents/` mirror: `scripts/sync_agent_commands.sh` is the generator (copies non-underscore commands, regenerates four `source-command-audit-*` SKILL.md wrappers). `scripts/sync_agent_commands.sh --check` reports "mirror is up to date" against the working tree, and `cmp` of every command shows zero differences. No drift.
- `docs/audits/` reports older than 90 days (before 2026-07-24): only the eight `*_2026-07-12.md` reports (`AUDIT_RECOVERY_2026-07-24.md` is exactly 90 days, not older). Every HIGH finding in them is triaged: BACKEND B3-01 #4352, B4-01 #4354 (and CONCURRENCY CC-1, same defect), INTEGRATION F5-01 #4406, F2-01 #4407, F7-01 #4408, FRONTEND H3-01 #4426, ENGINE ENG-D1-1 #4494, D3-1 #4495, D4-1 #4496, D4-2 #4497, D3-3 #5105; SECURITY, DEPRECATION and TECH_DEBT reports have no CRITICAL/HIGH. All CLOSED.
- audit-tech-debt.md Dim 2 re-export examples still exist: the `.models` `noqa: F401` block in `auralis-web/backend/cache/manager.py:52` and five `noqa: F401` imports in `routers/enhancement.py:36-60`; commit `78a39d25` exists. Dim 9's `loc-ceilings.json`, `scripts/check_loc_ratchet.py` (wired at `.github/workflows/backend-tests.yml:167`) and `7c75b75c` all exist; the "only AudioPlaybackEngine.ts (308) exceeds 300 in shipped src/" claim in audit-frontend.md:51 is accurate. The Phase 1 sample_rate/markers/`'any'` metric notes describe their metrics accurately (baseline: genuine src markers 3, tests/ 1).
- CI claim "`backend-tests.yml` is currently red on every run" (`_audit-common.md:102`, CLAUDE.md) holds: the last six runs all concluded `failure`.

- Dropped at merge, TD10-05: Merged into TD7-06 (same CLAUDE.md Codebase Map counts).
