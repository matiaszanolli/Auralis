# Concurrency and State Integrity Audit — 2026-05-27

Scope: Dimensions 1 (Player Thread Safety) and 2 (Audio Processing Pipeline). Dimensions 3 (Backend Streaming), 4 (Library & Database), and 5 (Frontend State) are out of scope for this run per `--focus 1,2`.

Project root: `/mnt/data/src/matchering`. Depth: deep. Dedup baseline: 200-issue snapshot fetched into `/tmp/audit/concurrency/issues.json` at audit start.

## Executive Summary

| Severity | Count | Highlights |
|----------|-------|------------|
| CRITICAL | 0 | — |
| HIGH | 0 | — |
| MEDIUM | 4 | Lock-inversion deadlock surface re-emerged on three paths (#3670 regression); `HybridProcessor.process_realtime_chunk` and `RealtimeAdaptiveEQ` / `DynamicsProcessor` lack internal locks |
| LOW | 9 | Queue raw-attribute reads, fingerprint daemon thread tracking, sample-count assertion on realtime path, miscellaneous defensive gaps |

**Most impactful race**: PTS-1 — lock-ordering inversion between `_audio_lock` and `_position_lock` is reachable via `seek()`, `load_file()`, AND `next_track()`. The original fix for #3670 only addressed `add_to_queue`; the three other paths reintroduce the same deadlock geometry. Issue #3670 remains OPEN, so this is a partial-regression finding.

**Key themes**:
1. **Lock ordering** — `_audio_lock → _position_lock` (via callback chain) collides with `_position_lock → _audio_lock` (via `get_playback_info`). Three callsites still hold `_audio_lock` while invoking state-change callbacks.
2. **Shared processor instances** — `HybridProcessor.process_realtime_chunk` and several setters bypass `_process_lock`. Real-time DSP subcomponents (`RealtimeAdaptiveEQ`, `DynamicsProcessor`) have no locking of their own. Today the player wraps DSP with its own outer lock, but any future caller of `HybridProcessor.process_realtime_chunk` on a cached instance corrupts state silently.
3. **Raw-attribute access** — `QueueController.current_index`, `shuffle_enabled`, `repeat_enabled`, and `AudioFileManager.sample_rate` / `current_file` bypass the locks their underlying mutators hold.
4. **Cleanup gaps** — fingerprint loader threads are spawned (line 260) but not tracked or joined in `cleanup()` (only the auto-advance thread is) — already reported as #3438.

## Concurrency Matrix

| Component | Lock(s) | Thread Safety | Notes |
|-----------|---------|---------------|-------|
| `AudioPlayer` (`enhanced_audio_player.py`) | `_fingerprint_lock`, `_auto_advancing` Event, `_stop_requested` Event, `_cleanup_in_progress` Event | Mostly safe | Callback-under-`_audio_lock` reintroduces #3670 |
| `PlaybackController` | `_lock` (RLock) | Safe | Snapshot-under-lock, notify-outside pattern correct |
| `AudioFileManager` | `_audio_lock` (RLock) | Safe for writers; raw attribute reads exist | `get_state_snapshot()` is the canonical helper but not all readers use it |
| `QueueController` / `QueueManager` | `_lock` (RLock) inside `QueueManager` | Safe via locked helpers; raw `.current_index` / `.shuffle_enabled` / `.repeat_enabled` properties bypass it | LOW finding PTS-3 |
| `GaplessPlaybackEngine` | `update_lock` (plain Lock), `_thread_lock`, `_shutdown` Event | Safe under current caller; latent ordering hazard | LOW finding PTS-2 |
| `IntegrationManager` | `_callbacks_lock`, `_stats_lock`, `_position_lock` (RLock) | Partial — lock inversion still exists | MEDIUM finding PTS-1 |
| `RealtimeProcessor` (player) | `self.lock` (plain Lock) | Safe; layered with inner component locks | LOW finding PTS-4 |
| `AutoMasterProcessor` | `_lock` (plain Lock) | Safe |  |
| `HybridProcessor` | `_process_lock` (RLock) | Safe only for `process()` and three setters; `process_realtime_chunk` + 7 other setters bypass | MEDIUM finding APP-1 |
| `RealtimeAdaptiveEQ` | (none) | **Not thread-safe** | MEDIUM finding APP-2 |
| `DynamicsProcessor` (advanced_dynamics) | (none) | **Not thread-safe** in ADAPTIVE mode | MEDIUM finding APP-3 |
| `BrickWallLimiter` | (none) | Safe via outer `_process_lock` (always called from `_process_*_mode`) | |
| `SimpleMasteringPipeline` | `_fp_service_lock`, `_process_lock` (RLock) | Safe (#3715) |  |
| `ParallelBandProcessor` / `ParallelFeatureExtractor` | (none, but per-worker `audio.copy()`) | Safe (#3355, #3673) |  |
| `ParallelFFTProcessor.window_cache` | `self.lock` (plain Lock) + unlocked fast-path | Minor TOCTOU on eviction | LOW finding APP-5 |
| Rust DSP (`vendor/auralis-dsp`) | GIL released via `py.allow_threads`; per-call `to_vec()` copy | Safe; no shared mutable state |  |

## Findings — Dimension 1 (Player Thread Safety)

### PTS-1: Lock-ordering inversion `_audio_lock` ↔ `_position_lock` deadlock still reachable via seek / load / next_track
- **Severity**: MEDIUM
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/enhanced_audio_player.py:185-192, 222-223, 387-417`; `auralis/player/integration_manager.py:143-156, 250-281, 293-314`
- **Status**: Regression of #3670 (#3670 is OPEN; the original `add_to_queue` trigger is fixed but three other paths reintroduce the same geometry)
- **Trigger Conditions**:
  - Thread A: `player.seek()`, `player.load_file()`, OR `player.next_track()`. All three hold `_audio_lock` AND invoke `playback.seek/load_and_stop/play` which calls `PlaybackController._notify_callbacks` (after releasing `PlaybackController._lock`). The callback `IntegrationManager._on_playback_state_change` then acquires `_position_lock` (`integration_manager.py:149`). Order: `_audio_lock → _position_lock`.
  - Thread B: `player.get_playback_info()` → `integration.get_playback_info()` → acquires `_position_lock` (`integration_manager.py:254`), then calls `file_manager.get_state_snapshot()` which acquires `_audio_lock`. Order: `_position_lock → _audio_lock`.
- **Evidence**:
  ```python
  # enhanced_audio_player.py:185-192 — seek() holds _audio_lock across playback.seek()
  with self.file_manager._audio_lock:
      ...
      return self.playback.seek(position_samples, max_samples)   # notifies under lock
  ```
  ```python
  # integration_manager.py:148-155 — callback then takes _position_lock
  def _on_playback_state_change(self, state_info):
      if state_info is None:
          state_info = {}
      with self._position_lock:
          state_info.update({
              'position_seconds': self._get_position_seconds(),  # → _audio_lock
              ...
          })
  ```
  ```python
  # integration_manager.py:254-263 — opposite order
  with self._position_lock:
      state_value, is_playing = self.playback.get_state_snapshot()
      playback_info = {
          ...
          'duration_seconds': self.file_manager.get_duration(),  # → _audio_lock
      }
  ```
- **Impact**: Two concurrent threads — typically a UI action (seek/skip/load) and the WebSocket state broadcaster polling `get_playback_info` — can deadlock both indefinitely. Playback freezes; UI stops updating; only kill -9 recovers. Reproducer: register a callback that calls `get_playback_info()` while another thread loops `seek()`.
- **Suggested Fix**: Hoist callback notification outside `_audio_lock`. The cleanest pattern: have `PlaybackController.seek/play/load_and_stop` return the `state_info` dict instead of notifying internally, then notify in the player AFTER releasing `_audio_lock`. The snapshot-under-lock / notify-outside pattern is already in `_notify_callbacks` but the wrapping at the player layer voids it.

### PTS-2: `gapless.update_lock → _audio_lock` nested acquisition on a non-reentrant Lock
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/gapless_playback_engine.py:48, 287-298`
- **Status**: NEW
- **Trigger Conditions**: `update_lock` is `threading.Lock()` (non-reentrant). `advance_with_prebuffer` line 287 takes it, then line 290 takes `_audio_lock`. The caller (`enhanced_audio_player.next_track()`, line 387) already holds `_audio_lock` (RLock reentry OK). So order is `_audio_lock → update_lock → _audio_lock`. Latent — only manifests if `_audio_lock` becomes a plain Lock OR if a path takes `update_lock` first and then `_audio_lock`.
- **Evidence**: `update_lock = threading.Lock()` (line 48); inner acquisition at lines 287/290.
- **Impact**: None today. Refactor hazard.
- **Suggested Fix**: Promote `update_lock` to RLock OR document the ordering constraint as a code comment on `update_lock`.

### PTS-3: `QueueController` property accessors (`current_index`, `shuffle_enabled`, `repeat_enabled`) bypass `QueueManager._lock`
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/queue_controller.py:64-91`
- **Status**: NEW
- **Trigger Conditions**: The three properties read/write `self.queue.current_index`, `self.queue.shuffle_enabled`, `self.queue.repeat_enabled` as raw attributes — no lock. Locked helpers (`snapshot_index`, `set_track_by_index`, etc.) exist on `QueueManager` but these properties slip past them.
- **Evidence**:
  ```python
  # queue_controller.py:63-71
  @property
  def current_index(self) -> int:
      return self.queue.current_index    # raw read — no _lock
  @current_index.setter
  def current_index(self, value: int) -> None:
      self.queue.current_index = value   # raw write — no _lock
  ```
- **Impact**: A read of `current_index` while another thread is mid-`remove_track()` (which may decrement the index) can return a stale value → off-by-one navigation. Window is small but exists.
- **Suggested Fix**: Route through locked helpers (`snapshot_index()` / `set_track_by_index()`), or deprecate the raw-attribute properties.

### PTS-4: `RealtimeProcessor.lock` widens contention across an entire chunk; layered locking duplicates inner component locks
- **Severity**: LOW (latency, not correctness)
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/realtime/processor.py:33, 116-143`
- **Status**: NEW
- **Trigger Conditions**: `process_chunk` holds the outer `self.lock` for the entire DSP chain (level matcher + auto master + safety limiter). Concurrent `set_fingerprint()` from the fingerprint loader thread blocks on the same lock until the chunk finishes (≤23 ms per chunk at 1024 samples / 44.1 kHz). `auto_master.process()` and `level_matcher.process()` each have their OWN lock, so the outer lock is redundant.
- **Impact**: Mild latency spikes during fingerprint loads at track-load boundaries.
- **Suggested Fix**: Remove the outer `lock` from `process_chunk()` and rely on inner component locks. `effects_enabled[dict]` can be guarded by a copy-on-read pattern.

### PTS-5: `AudioFileManager.sample_rate` / `current_file` / `reference_file` raw attribute reads bypass `_audio_lock`
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/audio_file_manager.py:30, 38, 42`; consumers throughout the codebase
- **Status**: NEW
- **Trigger Conditions**: Writes occur inside `_audio_lock`, but readers (e.g., `enhanced_audio_player.py:752, 359`; `integration_manager.py:153, 264`) often read these as raw attributes. The GIL keeps each individual read torn-free, but a pair of reads can straddle a track-swap.
- **Impact**: Brief windows of mis-paired (audio_data, sample_rate) reads during a track swap → wrong duration reported for one broadcast cycle. Self-correcting.
- **Suggested Fix**: Direct external callers to use `get_state_snapshot()` (already present in the API) or add locked getters.

### PTS-6: Fingerprint loader threads spawned per `load_file` are not tracked or joined in `cleanup()`
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/enhanced_audio_player.py:260-265, 761-783`
- **Status**: Existing: #3438 (OPEN — "Fingerprint daemon threads survive cleanup() and apply stale parameters")
- **Trigger Conditions**: `_schedule_fingerprint_load` spawns daemon threads; only the most recent auto-advance thread is tracked and joined. Fingerprint loaders accumulate; the staleness-generation check protects against applying their results, but file-handle and CPU pressure remain.
- **Evidence**: No `_fingerprint_threads` list; `cleanup()` joins only `_advance_thread`.
- **Impact**: Test-suite flakiness on rapid create/destroy; minor production resource pressure on long-running sessions.
- **Suggested Fix**: Track `_fingerprint_threads: list[threading.Thread]` and join with a small timeout in `cleanup()`, mirroring the `_advance_thread` pattern from #3694.

### PTS-7: `IntegrationManager.current_track` write outside any lock
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/integration_manager.py:75, 154, 180, 272`
- **Status**: NEW
- **Trigger Conditions**: Read in `_on_playback_state_change` and `get_playback_info` happens under `_position_lock`. Write in `load_track_from_library` (line 180) does NOT take any lock. Snapshot pattern under `_position_lock` does not protect this attribute.
- **Impact**: A reader may observe `current_track` pointing at the new track while `position_seconds` still points at the old one — one broadcast cycle of inconsistent UI state.
- **Suggested Fix**: Acquire `_position_lock` for the write in `load_track_from_library`.

## Findings — Dimension 2 (Audio Processing)

### APP-1: `HybridProcessor.process_realtime_chunk` and most public setters bypass `_process_lock` on the shared module-level cache
- **Severity**: MEDIUM
- **Dimension**: Audio Processing
- **Location**: `auralis/core/hybrid_processor.py:390-413, 424-446, 448-462, 488-501`
- **Status**: NEW
- **Trigger Conditions**:
  - `process()` (line 193), `set_fixed_mastering_targets()` (line 155), and `set_processing_mode()` (line 488) DO acquire `_process_lock`.
  - But: `process_realtime_chunk()` (line 390), `set_realtime_eq_parameters()` (line 428), `reset_realtime_eq()` (line 432), `set_dynamics_mode()` (line 440), `reset_dynamics()` (line 444), `set_user()` (line 448), `record_user_feedback()` (line 453), `record_parameter_adjustment()` (line 459) do NOT.
  - The module-level cache `_processor_cache` returns the SAME HybridProcessor instance to concurrent callers of `process_adaptive` / `process_reference` / `process_hybrid` (lines 590-631). The backend `processing_engine.py:332` uses `pop` semantics and is therefore safe, but the module cache is unconditionally shared.
- **Evidence**:
  ```python
  # hybrid_processor.py:390-413 — no lock
  def process_realtime_chunk(self, audio_chunk, content_info=None):
      audio_chunk = validate_audio_finite(audio_chunk, ...)
      processed_chunk = self.realtime_processor.process_chunk(audio_chunk, content_info)
      processed_chunk = sanitize_audio(processed_chunk, ...)
      return processed_chunk
  ```
  Currently no caller invokes `process_realtime_chunk` through the module cache (confirmed by repo-wide grep). The bug is **latent**, not exploited.
- **Impact**: Latent. If future code calls `process_realtime_chunk` on a processor returned from `_get_or_create_processor` from two threads, the underlying `RealtimeAdaptiveEQ` / `DynamicsProcessor` / `preference_engine` state is corrupted concurrently (see APP-2, APP-3). Audible: glitched EQ, gain pumping, sample-count violations.
- **Suggested Fix**: Wrap `process_realtime_chunk` and all the listed setters in `with self._process_lock:`. RLock allows reentry; cost is one extra acquire per chunk (≤1 µs).

### APP-2: `RealtimeAdaptiveEQ` has no locks; concurrent `process_realtime` + `set_adaptation_parameters` + `reset` races shared buffer state
- **Severity**: MEDIUM
- **Dimension**: Audio Processing
- **Location**: `auralis/dsp/realtime_adaptive_eq/realtime_eq.py:23-251`
- **Status**: NEW
- **Trigger Conditions**:
  - `process_realtime()` mutates `performance_stats`, `input_buffer`, and the embedded `adaptation_engine` + `psychoacoustic_eq` state.
  - `set_adaptation_parameters()` writes to `settings` and `adaptation_engine.settings`.
  - `reset()` REPLACES `self.adaptation_engine` with a fresh instance and clears the buffers.
  - No lock present (verified via `grep -n threading` on the file).
  - Concurrent callers on a shared instance: `input_buffer.append/clear` races; `reset()` mid-`process_realtime` causes a use-after-replace.
- **Evidence**:
  ```python
  # realtime_eq.py:30-71 — no self._lock initialised
  self.input_buffer: deque[Any] = deque(maxlen=64)
  ```
  ```python
  # realtime_eq.py:142, 176 — concurrent append / clear race
  self.input_buffer.append(audio_chunk)
  ...
  self.input_buffer.clear()
  ```
- **Impact**: Concurrent realtime EQ calls on a shared instance produce silently corrupted output (dropped or out-of-order chunks). Shared instance is owned by `HybridProcessor.realtime_eq`. The player wraps DSP with `RealtimeProcessor.lock`, so the player path is safe; any direct caller of `HybridProcessor.process_realtime_chunk` is not.
- **Suggested Fix**: Add `self._lock = threading.Lock()` and wrap `process_realtime`, `set_adaptation_parameters`, `reset`, and `get_current_eq_curve`. Lock cost is negligible vs the FFT.

### APP-3: `DynamicsProcessor` mutates compressor settings on every adaptive chunk without protection
- **Severity**: MEDIUM
- **Dimension**: Audio Processing
- **Location**: `auralis/dsp/advanced_dynamics.py:39-309`
- **Status**: NEW (related to #2897 OPEN "DynamicsProcessor unused in offline pipeline" — confirms the realtime path is the only consumer)
- **Trigger Conditions**:
  - `process()` calls `_adapt_to_content()` which **writes** `self.compressor.settings.threshold_db`, `ratio`, `makeup_gain_db` (lines 237-254) on every chunk in ADAPTIVE mode.
  - `self.gate_gain` (line 139), `self.adaptation_state` (line 265), `self.content_history` (lines 269-271) are mutated without protection.
  - Same shared-instance hazard as APP-1/APP-2 — the instance is owned by `HybridProcessor.dynamics_processor`.
- **Evidence**:
  ```python
  # advanced_dynamics.py:237-238, 254
  self.compressor.settings.threshold_db = new_threshold
  self.compressor.settings.ratio = new_ratio
  self.compressor.settings.makeup_gain_db = auto_makeup_gain
  ```
- **Impact**: Torn settings reads → temporarily incorrect compression curve → audible pumping or under-compression for the affected chunk window.
- **Suggested Fix**: Add an RLock and wrap `process()` and `_adapt_to_content()`. Alternative: snapshot-and-swap (`new_settings = copy(...); self.settings = new_settings`) for lock-free atomicity.

### APP-4: `HybridProcessor.current_user_id` and `last_content_profile` are mutated outside `_process_lock` from setter paths
- **Severity**: LOW
- **Dimension**: Audio Processing
- **Location**: `auralis/core/hybrid_processor.py:128, 448-451`
- **Status**: NEW
- **Trigger Conditions**: `set_user()`, `record_user_feedback()`, `record_parameter_adjustment()` mutate state via `self.preference_manager` without `_process_lock`. `current_user_id` (line 450) write is also unlocked.
- **Impact**: A `set_user()` call concurrent with `process()` could attribute the chunk's preference recording to the previous user. Marginal — preference learning already buckets feedback per session.
- **Suggested Fix**: Wrap all preference-related setters in `with self._process_lock:`.

### APP-5: `ParallelFFTProcessor.window_cache` fast-path read can race with concurrent eviction
- **Severity**: LOW
- **Dimension**: Audio Processing
- **Location**: `auralis/optimization/parallel_processor.py:42-86`
- **Status**: NEW
- **Trigger Conditions**: Fast path `if size in self.window_cache: return self.window_cache[size]` (lines 66-67) is unlocked. Slow path (line 72) holds the lock and may `del` the same entry. Window between the membership check and the index read is a few CPython bytecodes; `KeyError` is possible.
- **Evidence**:
  ```python
  if size in self.window_cache:
      return self.window_cache[size]   # ← race target
  ```
- **Impact**: Very rare KeyError raised into the FFT path → fall-through to slow recompute (still correct, just slower). Not a correctness bug.
- **Suggested Fix**: Use `cached = self.window_cache.get(size); if cached is not None: return cached`.

### APP-6: `process_realtime_chunk` lacks the sample-count assertion present on all three offline mode handlers
- **Severity**: LOW
- **Dimension**: Audio Processing
- **Location**: `auralis/core/hybrid_processor.py:291-294, 347-350, 379-382, 390-413`
- **Status**: NEW
- **Trigger Conditions**: `_process_reference_mode`, `_process_adaptive_mode`, `_process_hybrid_mode` each `assert processed.shape == target_audio.shape` after the brick-wall limiter (#2519 fix). `process_realtime_chunk` (line 390-413) returns whatever `realtime_processor.process_chunk` returns without a length check.
- **Impact**: A future DSP refactor changing chunk length in the realtime path would silently break gapless playback. The existing assertions cover batch processing only.
- **Suggested Fix**: Add `assert processed_chunk.shape == audio_chunk.shape` to `process_realtime_chunk` after the call to `self.realtime_processor.process_chunk`.

## Relationships

- **PTS-1 ↔ #3670**: Same deadlock geometry. #3670 was filed for `add_to_queue`; current PTS-1 covers `seek`/`load_file`/`next_track`. Should be reopened with the broader scope OR a fresh issue created and #3670 closed-as-superseded.
- **APP-1 ↔ APP-2 ↔ APP-3**: All three describe the same shared-instance hazard at different layers. The proper fix is at the outermost layer (APP-1 — add `_process_lock` to `process_realtime_chunk`), which also closes APP-2 and APP-3 for the player path. APP-2 and APP-3 are still worth independent locking for defensive depth (e.g. any caller invoking the realtime EQ directly).
- **PTS-6 ↔ #3438**: Same finding; #3438 is the canonical entry. Audit confirms regression is still present in current code.
- **PTS-2 ↔ PTS-1**: Both stem from cross-component lock-ordering. PTS-2 is latent; PTS-1 is live. Fixing PTS-1 via callback hoisting also reduces PTS-2's blast radius (fewer paths hold `_audio_lock` during callback chains).
- **APP-1 ↔ #2897**: #2897 ("DynamicsProcessor unused in offline pipeline") indicates the dynamics processor is currently only reachable via the realtime path. That confirms APP-3's shared-instance hazard is real for the realtime caller surface.

## Prioritized Fix Order

1. **PTS-1 (MEDIUM)** — close the lock-inversion deadlock. Highest user-visible impact: a real production freeze under simultaneous user action + WS broadcast. The fix (hoist callback notification outside `_audio_lock` in `seek`/`load_file`/`next_track`) is structural and small.
2. **APP-1 (MEDIUM)** — add `_process_lock` to `process_realtime_chunk` and the seven setters. Single-line wrap each; closes APP-2 and APP-3 for all current callers.
3. **APP-2 (MEDIUM)** — add internal lock to `RealtimeAdaptiveEQ` even after APP-1 lands, for defensive depth. Required if any future caller bypasses `HybridProcessor`.
4. **APP-3 (MEDIUM)** — same defensive depth for `DynamicsProcessor`. Can be combined with APP-2 in one commit.
5. **PTS-3 (LOW)** — route raw `current_index`/`shuffle_enabled`/`repeat_enabled` through locked helpers. Touch list is small; eliminates a real off-by-one navigation race.
6. **PTS-7 (LOW)** — lock the `current_track` write in `load_track_from_library`. One-line fix.
7. **APP-6 (LOW)** — add the sample-count assertion to `process_realtime_chunk`. Belt-and-suspenders.
8. **PTS-2 (LOW)** — promote `gapless.update_lock` to RLock. Future-proofing.
9. **APP-5 (LOW)** — replace fast-path `in`+`[]` with `dict.get()`. Trivial.
10. **PTS-4 (LOW)** — drop the redundant outer `RealtimeProcessor.lock`. Mild latency win.
11. **PTS-5 (LOW)** — direct external readers to `get_state_snapshot()`. Mostly documentation + a few call-site updates.
12. **PTS-6 (LOW)** — link to #3438. Already tracked; ensure regression test is added.
13. **APP-4 (LOW)** — wrap preference setters in `_process_lock`. Tiny.

## Methodology Notes

- Dimensions 3 (Backend Streaming), 4 (Library & Database), 5 (Frontend State) deliberately skipped per `--focus 1,2` parameter — not because they're clean, only because they're not in scope for this run.
- All findings are based on reading the current source tree; no claims rely on prior reports. Where a prior issue exists with the same root cause, it's noted in **Status** with the issue number and current state.
- File-paths and line-ranges have been re-verified against the live tree as of audit start; line numbers may drift on subsequent commits.
- The `_process_lock` on `HybridProcessor` is correctly used for the offline batch path (`process()` → `_process_impl()` → `_process_*_mode`). The audit found no integrity issue in that path itself.
- Module-level optimisation idempotency (#3353) is correctly guarded with the `_optimized` flag (line 516); no double-wrap concern.

---

To publish these findings as GitHub issues:

```
/audit-publish docs/audits/AUDIT_CONCURRENCY_2026-05-27.md
```
