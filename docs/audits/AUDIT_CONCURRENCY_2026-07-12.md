# Concurrency & State Integrity Audit — 2026-07-12

**Scope**: Race conditions, missing locks, thread-safety violations, state-machine bugs, unsafe concurrent access across the player, DSP pipeline, backend WebSocket/streaming, library/database, and frontend state.
**Method**: Fresh read of current source across 5 dimensions (2 independent passes per dimension). Each finding re-derived, adversarially checked, and deduplicated against `gh issue list` (142 open issues) plus prior fixes. Auralis is a desktop-only Electron app bound to localhost — findings that require hostile remote clients are downgraded; concurrent legitimate clients, reconnects, and backend restarts are treated as realistic.

## Executive Summary

**9 unique NEW findings** (after cross-dimension dedup) + **1 severity re-rating recommendation** on an existing issue.

| Severity | Count | IDs |
|----------|-------|-----|
| CRITICAL | 0 | — |
| HIGH | 1 | CC-1 |
| MEDIUM | 5 | CC-2, CC-3, CC-4, CC-5, CC-6 |
| LOW | 3 | CC-7, CC-8, CC-9 |
| Re-rate (existing) | 1 | #3735 (LOW → HIGH) |

**Key themes**

1. **The `_process_lock` regression is the headline.** A Phase-2 refactor moved the live chunk-processing path onto `AudioProcessingPipeline.apply_enhancement`, which toggles the *shared* `HybridProcessor`'s `use_fingerprint_analysis` flag **without** the processor's own `_process_lock`. The fix for this exact race (#3808) still exists but only inside `_process_chunk_with_hybrid_processor`, which is now **dead code** (also filed as #3879). Found independently by both the Audio-Processing and Backend dimensions (CC-1).
2. **Two "acquire-then-leak-on-cancellation" resource bugs.** A process-global stream semaphore permit (CC-3) and a scan slot (CC-4) are both acquired *before* the `try`/`finally` that guarantees their release, so a cancellation/early-return in the intervening window leaks the resource permanently until app restart — eventually wedging all streaming / all scanning.
3. **State-sync guards that don't survive a reconnect/restart.** The frontend `player_state` seq guard never resets when the backend process restarts (CC-6), silently freezing authoritative UI state; and the Blob PCM fallback path can clobber the next chunk's metadata (CC-5).
4. **Both subsystems that were expected to be fragile — the player facade and the backend WS surface — are exceptionally hardened.** Dozens of prior fixes were verified present and correct. Most classic races are already fixed or already filed; the findings here are the residue.

**Most impactful races**: CC-1 (wrong mastering / audible EQ-level inconsistency, regression), CC-3 (streaming wedges after enough cancellations), #3735 re-rate (audio-thread dropout on skip).

## Concurrency Matrix

| Component | Shared state | Lock(s) | Thread-safety status |
|-----------|--------------|---------|----------------------|
| `AudioPlayer` facade | audio_data, position, current_file | `_audio_lock` (RLock), `_position_lock`, `defer_notifications()` | Sound except CC-2 (callback under lock) + #3735 (blocking I/O under lock) |
| `RealtimeProcessor` → `LevelMatcher` | enabled/reference_rms/gain_smoother | `RealtimeProcessor.lock` **vs** `LevelMatcher._lock` | CC-8: two mutexes guard the same fields |
| `HybridProcessor.process()` | DSP envelope/limiter state | `_process_lock` (RLock) | Sound — self-locks whole body |
| `AudioProcessingPipeline.apply_enhancement` | shared processor's `use_fingerprint_analysis` | **none** (should hold `_process_lock`) | **CC-1 (HIGH)** — regression of #3808 |
| `ParallelProcessor` | per-band audio | per-worker `audio.copy()` | Sound (#3355/#3673/#4229 intact) |
| Rust DSP (PyO3) | none (fresh output arrays) | `py.allow_threads` + `catch_unwind` | Sound — GIL released on all long compute |
| `_stream_semaphore` | global `Semaphore(10)` | acquire/release | **CC-3 (MEDIUM)** — permit leak on cancellation |
| `ChunkedAudioProcessor` | per-instance chunk state | per-instance `_processor_lock` (RLock) | Sound per-instance; cross-instance sharing is the CC-1 hole |
| `_last_content_profiles` | module-global dict | **none** | **CC-9 (LOW)** — unsynchronised (benign under GIL) |
| `ProcessingEngine` job/pool | jobs, callbacks, pool | `_jobs_lock`, `_processor_lock`, job semaphore | Sound (#3531/#3201 balanced) |
| Scanner slots | `_active_scans`, `_active_paths` | `_scan_slots_lock`, `_active_paths_lock` | **CC-4 (MEDIUM)** — slot leak on dedup rejection |
| SQLite engine | connection pool | `pool_pre_ping=True`, WAL, `busy_timeout=60000`, `_delete_lock`, `_migration_lock` (threading + file lock) | Sound — config baseline verified |
| Frontend `usePlayerStateSync` | `lastSeenSeqRef` | seq guard | **CC-6 (MEDIUM)** — no reset on reconnect |
| Frontend WS Blob path | `pendingAudioChunkMeta` | module var | **CC-5 (MEDIUM)** — async clobber |
| Frontend enhancement setters | intensity/preset | none (`toggleEnabled` has `isTogglingRef`) | **CC-7 (LOW)** — no in-flight guard |

## Findings

### HIGH

#### CC-1: `apply_enhancement` toggles shared `use_fingerprint_analysis` without `_process_lock` — regression of #3808
- **Severity**: HIGH
- **Dimension**: Audio Processing / Backend Streaming (found by both)
- **Location**: `auralis-web/backend/core/audio_processing_pipeline.py` (`apply_enhancement`, both the targets and fast_start toggle branches); dead fixed twin at `auralis-web/backend/core/chunked_processor.py:436,450`
- **Status**: Regression of #3808
- **Trigger Conditions**: Two concurrent streaming tasks whose `ChunkedAudioProcessor` instances resolve to the **same cached `HybridProcessor`** (same config-keyed `ProcessorFactory._processor_cache` entry). Each instance holds only its **own** per-instance `_processor_lock`, which does not mutually exclude across instances. Realistic on desktop when two WebSocket connections (two Electron windows, or a stale-reconnect overlap before the ~30 s heartbeat evicts the old socket) drive the same track/preset simultaneously.
- **Evidence**:
  ```python
  # apply_enhancement — flag write/restore straddles process()'s lock but is NOT itself locked
  processor.content_analyzer.use_fingerprint_analysis = False   # write — NO lock held
  try:
      processed = processor.process(audio)   # process() acquires processor._process_lock INTERNALLY
  finally:
      processor.content_analyzer.use_fingerprint_analysis = original_setting  # restore — NO lock held
  ```
  The #3808 fix wraps the identical toggle in `with self._processor_lock, self.processor._process_lock:` (chunked_processor.py:436/450) with an in-code comment explaining that the per-instance lock alone is insufficient because the factory can hand the same processor to another stream. That method (`_process_chunk_with_hybrid_processor`) is now **dead code** (no production callers; also filed #3879). The live path `_process_chunk_core → process_audio → apply_enhancement` dropped the `processor._process_lock`. `_process_lock` is an RLock (hybrid_processor.py:159), so re-entry by `process()` under the caller's hold is safe.
- **Impact**: Interleaving on the shared boolean: (a) thread B captures `original_setting` as thread A's transient `False`, then B's `finally` writes `False` **permanently** — fingerprint analysis stays disabled on the shared processor for all subsequent normal chunks → wrong mastering targets for the rest of playback; or (b) A's restore flips the flag to `True` mid-`process()` in B, so a chunk that should skip per-chunk fingerprint runs it (or vice-versa) → audible EQ/level discontinuity between chunks. No crash, no sample-count change, no DSP-state corruption (`process()` is internally locked) — silent wrong-audio. The narrower single-chunk-transient reading was also noted independently; the permanent-latch case (a) is the worst case and is why this is rated HIGH (audio-integrity, and a regression of a previously-fixed bug). Downgraded from CRITICAL because the cross-stream trigger is narrow on a single-user desktop.
- **Related**: #3808 (original fix), #3879 (the dead-code twin), CC-9 (adjacent unsynchronised global on the same path).
- **Suggested Fix**: Guard the read-modify-`process()`-restore span in `apply_enhancement` with `with processor._process_lock:` (RLock re-entry is safe), matching the dead-code fix — or pass the toggle intent into `process()` so the flag is set/read atomically inside the existing lock. Then delete the dead `_process_chunk_with_hybrid_processor` so there is one implementation.

### MEDIUM

#### CC-2: `record_track_completion()` fires application callbacks while holding `_audio_lock` (bypasses the #3781 deferral)
- **Severity**: MEDIUM
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/enhanced_audio_player.py:332-336`; callback dispatch `auralis/player/integration_manager.py:297-305` / `132-141`
- **Status**: NEW (incomplete fix of #3781)
- **Trigger Conditions**: An application registers a callback via the public `AudioPlayer.add_callback()` that reads playback state (e.g. `get_playback_info()`), AND a gapless/auto-advance `next_track()` fires while another thread polls `get_playback_info()`.
- **Evidence**: `next_track()` runs `with self.playback.defer_notifications(), self.file_manager._audio_lock:` then calls `self.integration.record_track_completion()`, which calls `IntegrationManager._notify_callbacks(...)` **synchronously while `_audio_lock` is held**. The #3781 `defer_notifications()` context only queues `PlaybackController._notify_callbacks`; `IntegrationManager` has no deferral check. A callback re-entering `get_playback_info()` acquires `_position_lock → _audio_lock`, while the advance thread holds `_audio_lock` and the poller holds `_position_lock` → the exact `_audio_lock → _position_lock` AB-BA inversion #3781 was written to eliminate.
- **Impact**: Latent hard deadlock of the playback/advance thread against any status-poll thread (frozen audio + UI). Latent today only because production registers no external callbacks — reachable the moment any consumer uses the documented `add_callback` API to observe track completion.
- **Related**: #3781, #3785 (both touch the same lock-order surface).
- **Suggested Fix**: Move `record_track_completion()` (which only needs `_stats_lock` + callbacks) out of the `_audio_lock` critical section, or route `IntegrationManager._notify_callbacks` through the same `defer_notifications()` deferral so callbacks flush after `_audio_lock` releases.

#### CC-3: Stream semaphore permit leaked on task cancellation during track lookup
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/stream_enhanced.py:69-101`; identical pattern in `stream_seek.py:73-103` and `stream_normal.py:64-95`
- **Status**: NEW
- **Trigger Conditions**: A streaming task is cancelled (client disconnect → `teardown_connection`, or a superseding play/seek → `_cancel_prior_task`/`handle_stop`) while suspended at `await asyncio.to_thread(factory.tracks.get_by_id, track_id)` (or the `_send_error` inside that block). The window is normally ms but widens under SQLite lock contention and rapid track-switch/seek-scrub.
- **Evidence**: `await asyncio.wait_for(controller._stream_semaphore.acquire(), timeout=5.0)` acquires the permit at L69, **before** the L103 `try` whose `finally` releases it (L297). The intervening lookup block's handler is `except Exception` (L97) — but `asyncio.CancelledError` is a `BaseException`, so it is not caught, and it is raised before control reaches the releasing `try`. The permit is never released; `system.py::stream_audio` catches the `CancelledError` upstream but has no reference to the semaphore.
- **Impact**: `_global_stream_semaphore` is a module-level `asyncio.Semaphore(MAX_CONCURRENT_STREAMS=10)` shared across all controllers. Each leak is **permanent** for the backend process lifetime. After enough cancellations, every new stream waits 5 s then fails with "Server busy - too many active streams"; A/B mode (2 permits) degrades sooner. Playback stops working until app restart. Blast radius: all streaming for the session.
- **Related**: CC-4 (same acquire-before-try anti-pattern in the scanner).
- **Suggested Fix**: Acquire immediately before a single `try:` whose `finally` releases exactly once, deleting the manual `release()` calls; or change the lookup block to `except BaseException:` + `release()` + re-raise. Apply identically to all three entry points.

#### CC-4: Scan slot leaked when the per-directory dedup guard rejects a scan
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner/scanner.py:124-148` (slot acquired at 124; released only in the `finally` at 227 attached to the `try` at 152)
- **Status**: NEW
- **Trigger Conditions**: `max_concurrent_scans >= 2` (user setting; default 1 masks it). Two scans target the SAME directory concurrently: Scan B acquires a slot (`_active_scans` 2 ≤ max), then hits the dedup guard (140-146), finds the directory in `_active_paths`, sets `result.rejected = True` and `return`s at 146 — **before** entering the `try` at 152.
- **Evidence**: The early `return` at line 146 skips the `try`/`finally` (152/227) that calls `release_scan_slot()`, so the slot acquired at line 124 is never released.
- **Impact**: Permanent leak of one scan slot per dedup-rejected scan. After enough occurrences `_active_scans` saturates at `max_concurrent_scans` and ALL subsequent scans are rejected at line 128 until process restart. Resource exhaustion / denial-of-scanning, not DB corruption. MEDIUM (not HIGH) because it is unreachable at the default `max_concurrent_scans == 1`.
- **Related**: CC-3 (same anti-pattern).
- **Suggested Fix**: Release the slot before the early return in the dedup-rejection branch, or restructure so acquisition and both rejection checks live inside the same `try` whose `finally` releases only when `_acquired`.

#### CC-5: Blob PCM path can clobber the next chunk's `audio_chunk_meta`
- **Severity**: MEDIUM
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/contexts/WebSocketContext.tsx:294-310`
- **Status**: NEW
- **Trigger Conditions**: Browser delivers binary PCM as `Blob` (fallback path, not `ArrayBuffer`). `Blob.arrayBuffer()` is async; if it resolves after the NEXT chunk's `audio_chunk_meta` text frame has already set `pendingAudioChunkMeta`, the `.then` callback unconditionally nulls it.
- **Evidence**:
  ```js
  if (event.data instanceof Blob) {
    const meta = pendingAudioChunkMeta;
    event.data.arrayBuffer().then((buffer) => {
      if (meta) { ...; pendingAudioChunkMeta = null; /* nulls whatever is pending NOW, not `meta` */ dispatchMessage(combined); }
    });
    return;
  }
  ```
- **Impact**: Chunk N+1's metadata is discarded; its binary frame then arrives with `pendingAudioChunkMeta === null` → "binary frame without preceding audio_chunk_meta" warning + a dropped audio chunk (gap/glitch). The `ArrayBuffer` path (common case when `binaryType='arraybuffer'`) is unaffected → MEDIUM.
- **Suggested Fix**: Only null if still equal to the captured value (`if (pendingAudioChunkMeta === meta) pendingAudioChunkMeta = null;`), or capture-and-clear synchronously before the await rather than relying on module-level pairing in the async path.

#### CC-6: `player_state` seq guard never resets on reconnect — stale UI after backend restart
- **Severity**: MEDIUM
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:73,86-89`
- **Status**: NEW
- **Trigger Conditions**: Backend process restarts (crash, or `uvicorn --reload` in dev) while the frontend stays mounted and auto-reconnects. Backend `StateManager._update_seq` (`core/state_manager.py:41,79-80`) resets to 0 on restart; the frontend `lastSeenSeqRef` (a `useRef`) persists across the reconnect.
- **Evidence**:
  ```js
  const lastSeenSeqRef = useRef(0);
  if (typeof state.seq === 'number') {
    if (state.seq < lastSeenSeqRef.current) return;   // drops all post-restart snapshots
    lastSeenSeqRef.current = state.seq;
  }
  ```
  After restart, new snapshots arrive with seq 1,2,3… while `lastSeenSeqRef.current` may be ~500, so every authoritative `player_state` snapshot is discarded until the counter climbs past the old max.
- **Impact**: currentTrack / queue / duration / shuffle / repeat in Redux freeze on pre-restart values and never re-sync. Masked/confusing because discrete events (position_changed, playback_*, track_changed, volume_changed) are NOT seq-gated, so isPlaying/position still update. Workaround: reload the page.
- **Suggested Fix**: Reset `lastSeenSeqRef.current = 0` on WS reconnect (subscribe to connection status / on-open), or have the backend send a session-epoch id and reset the guard when it changes, or accept a snapshot whose seq is far below last-seen (large backward jump ⇒ counter restart).

### LOW

#### CC-7: `setPreset`/`setIntensity` have no in-flight or request-sequence guard
- **Severity**: LOW
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancementControl.ts:296-341,349-381`
- **Status**: NEW
- **Trigger Conditions**: User drags the intensity slider / clicks presets rapidly. Each call fires an un-aborted POST and, on resolution, does `setState(...)` + `reissueRef.current('play_enhanced', ...)`. Unlike `toggleEnabled` (`isTogglingRef`), these have no in-flight guard or request-sequence tracking.
- **Evidence**: The optimistic `setState` runs *after* the await, so the last fetch to **resolve** wins, not the last dispatched; out-of-order resolution (0.9 before 0.5) leaves the client showing 0.5. Each resolution also restarts the stream via `reissueActiveStreamAs`.
- **Impact**: Transient wrong preset/intensity (self-heals via the `enhancement_settings_changed` WS broadcast, which arrives in backend order) plus a burst of stream restarts during a drag → audible glitches/re-buffering. LOW: reconciles + workaround exists.
- **Suggested Fix**: Add an in-flight/last-request-id guard (like `isTogglingRef`), debounce/throttle slider→POST, and apply the optimistic `setState` only if the request is still the most recent.

#### CC-8: `RealtimeProcessor` mutates `RealtimeLevelMatcher` internals under the wrong lock
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/realtime/processor.py:68-80` (`set_effect_enabled`), `193-209` (`reset_all_effects`) vs `auralis/player/realtime/level_matcher.py:44-94`
- **Status**: NEW
- **Trigger Conditions**: The audio thread is inside `process_chunk() → level_matcher.process()` (holding `level_matcher._lock`) while another thread calls `set_effect_enabled('level_matching', ...)` (backend enhancement API) or `reset_all_effects()` (cleanup).
- **Evidence**: `set_effect_enabled`/`reset_all_effects` write `level_matcher.enabled` / `reference_rms` / `gain_smoother` as raw attributes under `RealtimeProcessor.lock`, but `level_matcher.process()` reads the same fields under `RealtimeLevelMatcher._lock` — two different mutexes guarding one piece of state, so the paths don't serialize. (`auto_master` mutations are safe — they use `auto_master._lock`.)
- **Impact**: Bounded data race — the `reference_rms is None` guard catches the enabled/reference mismatch, and the `gain_smoother` swap is an atomic ref replace (in-flight `process()` keeps its old object). Worst case: a single-buffer level step (possible faint click) at toggle/cleanup. No corruption.
- **Suggested Fix**: Route mutations through the level matcher's own locked API (`set_reference_audio(None)` already exists; add a locked `reset()`/`set_enabled()` for the gain-smoother swap) instead of raw attribute writes.

#### CC-9: `_last_content_profiles` module-global written outside any lock
- **Severity**: LOW
- **Dimension**: Audio Processing / Backend Streaming (found by both)
- **Location**: `auralis-web/backend/core/chunked_processor.py:838-844` (write) / `:901-915` (read `get_last_content_profile`)
- **Status**: NEW
- **Trigger Conditions**: `get_wav_chunk_path` runs in `asyncio.to_thread` workers; concurrent chunk processing across streams writes `_last_content_profiles[self.preset.lower()] = ...` from multiple threads (the write sits AFTER the `with self._sync_cache_lock:` block closes). The visualizer endpoint reads it from the event-loop thread.
- **Evidence**: `_last_content_profiles[self.preset.lower()] = processor_profile` executed with no lock; module-global dict read by `get_last_content_profile`.
- **Impact**: Benign under CPython (dict `__setitem__` is atomic under the GIL — no structural corruption); worst case is last-writer-wins staleness, so `/api/processing/parameters` may display another concurrent track's profile. Cosmetic/telemetry only, no audio-path effect.
- **Suggested Fix**: Guard with a dedicated module `threading.Lock`, or key by `(track_id, preset)` and snapshot under the lock on read; otherwise document as intentionally best-effort.

### Existing issue — severity re-rating recommended

#### #3735 (OPEN, currently LOW) — `next_track()` holds `_audio_lock` across blocking `load_file()` on prebuffer miss → audible dropout
- **Recommendation**: Re-rate to **HIGH** (do not file new).
- **Location**: `auralis/player/enhanced_audio_player.py:332`, blocking I/O at `auralis/player/gapless_playback_engine.py:341,291`.
- **Rationale**: `next_track()` holds `_audio_lock` across the entire `advance_with_prebuffer()`, whose fallback (prebuffer-miss) path calls `file_manager.load_file() → load()` synchronous disk I/O (~100 ms+) while `_audio_lock` is held. This blocks the audio thread's `get_audio_chunk()` for the full load → real-time buffer underrun / audible dropout on a user-initiated skip whose next track was not prebuffered. Same bug class as #3656 (fixed for `add_to_queue`). #3735 already names the root cause but is filed LOW; the concrete harm (audio-thread stall on blocking I/O under lock) is HIGH per the audio-integrity severity rule. Fix: hold `_audio_lock` only across the in-memory pointer swap, never across `load()`.

## Relationships

- **CC-1 ↔ CC-9 ↔ #3879 ↔ #3808**: All four center on the same live vs dead code split. The Phase-2 refactor routed processing onto `AudioProcessingPipeline` and left `_process_chunk_with_hybrid_processor` (which carried both the #3808 lock discipline and the sync-cache handling) as dead code. Fixing CC-1 and deleting the dead twin should be a single change; CC-9 sits on the same file/path and can be swept in.
- **CC-3 ↔ CC-4**: Identical "acquire a shared resource *before* the release-guaranteeing `try`, then an early-return/cancellation skips the `finally`" anti-pattern, in two subsystems (streaming semaphore, scanner slots). Both leak permanently until restart. Worth a lint/grep sweep for `acquire()` / `try_acquire_*` not immediately followed by `try:`.
- **CC-2 ↔ #3735 ↔ #3781 ↔ #3782 ↔ #3785**: All touch the player's `_audio_lock` / `_position_lock` discipline. CC-2 is a hole in the #3781 deferral; #3735 is blocking work under the same lock. These are the residual player-lock surface after an otherwise very complete hardening pass.
- **CC-5 ↔ CC-6 ↔ CC-7**: Frontend state-sync robustness against async/reconnect ordering. None corrupt audio; all cause stale/dropped UI or a glitch burst that eventually reconciles.

## Prioritized Fix Order

1. **CC-1 (HIGH)** — Restore `_process_lock` around the `apply_enhancement` toggle and delete the dead `_process_chunk_with_hybrid_processor`. It is a regression of a previously-fixed audio-integrity bug, has silent wrong-audio impact, and the fix is small and self-contained. Sweep CC-9 in the same change.
2. **CC-3 (MEDIUM)** — Semaphore permit leak wedges *all* streaming after enough cancellations (rapid seek/skip is common). One-line-ish fix repeated across three files; high leverage.
3. **#3735 re-rate + fix (was LOW, → HIGH)** — Narrow `_audio_lock` to the pointer swap; removes an audible dropout on skip.
4. **CC-6 (MEDIUM)** — Reset the seq guard on reconnect; removes a confusing frozen-UI failure after every dev `--reload` / backend crash.
5. **CC-4 (MEDIUM)** — Scan-slot leak; fix alongside CC-3 (same anti-pattern), even though default config masks it.
6. **CC-2 (MEDIUM)** — Move `record_track_completion()` out of `_audio_lock`; closes a latent deadlock before any consumer uses `add_callback`.
7. **CC-5 (MEDIUM)** — Guard the Blob-path meta null; low effort, prevents dropped chunks on the fallback path.
8. **CC-7, CC-8, CC-9 (LOW)** — Opportunistic hardening.

## Coverage Notes — verified sound (attempted to disprove, could not)

- **Rust PyO3 boundary**: `py.allow_threads` + `catch_unwind` on every long compute (HPSS/YIN/chroma/tempo/envelope/compressor/limiter/fingerprint); read-only borrow + `.to_vec()` copy + fresh output arrays; correct dtype/shape; no shared mutable Rust state.
- **ParallelProcessor**: per-worker `audio.copy()` everywhere (#3355/#3673/#4229 intact); in-place band filters cannot corrupt siblings.
- **Sample-count preservation**: shape asserts after the limiter in reference/adaptive/hybrid modes; realtime asserts `len(out)==input_len`.
- **HybridProcessor setters**: `set_fixed_mastering_targets`, `set_user`, realtime/dynamics/EQ setters all hold `_process_lock` (#3714/#3787/#3792) — `apply_enhancement` (CC-1) is the only unguarded toggle.
- **Player facade**: seek-vs-gapless overlap, position/duration invariant, stop()/play() flag race, queue-iteration races, auto-advance duplicate-thread spawn, fingerprint-apply race, and Player→Library lock ordering all verified correctly handled (#2153/#2423/#3352/#3474/#3656/#3669/#3691/#3713/#3717/#3718/#3719/#3781/#3783/#4100/#4126/#4212/#4227).
- **Backend WS surface**: per-task ContextVars isolate stream metadata (#2493/#3841); `SimpleChunkCache` fully locked (#3192); cancel-and-await-outside-lock consistent (#3828/#3806/#2425); pause/flow `Event` waits can't deadlock on disconnect; all blocking DSP/DB/IO offloaded via `asyncio.to_thread` + `wait_for` — no event-loop starvation; `ProcessingEngine` job semaphore balanced (#3531/#3201).
- **Database**: `check_same_thread=False`, `pool_pre_ping=True`, WAL + `synchronous=NORMAL` + `busy_timeout=60000` + `foreign_keys=ON`; migration under file-lock (`fcntl`/`msvcrt`) **and** same-process `threading.Lock` `_migration_lock` (#4232, still present) with fail-fast backup-before-migrate; no raw-SQL ORM bypass (single documented `insert().from_select()` with bound params).

## Deduplicated against existing OPEN issues (not re-reported)

#3870 (heartbeat send unguarded), #3906 (WS finally swallows errors), #3889 (`cancel_job` outside `_jobs_lock`), #3890 (`_notify_progress` outside lock), #3868 (`subscribe_job_progress` captures websocket), #3867 (serial broadcast), #3780 (seq vs sequence naming), #3885 (LevelManager unbounded), #3888 (sync `get_by_id` from async), #3919 (always-`None` `processor_lock` param), #3782 / #3785 (player lock-order latents, confirmed still present), #4294 (`_session_scope` unused, 111 hand-rolled sites), #3879 (dead `_process_chunk_*` — referenced by CC-1), #3762 / #4309 (DSP dup/pool), #3992 / #4296 / #4297 / #4292 / #4301 / #3654 (frontend state/size). #3732/#3345/#2385/#3393 verified present and correct.

---

*Report generated by `/audit-concurrency`. Next step:*

```
/audit-publish docs/audits/AUDIT_CONCURRENCY_2026-07-12.md
```
