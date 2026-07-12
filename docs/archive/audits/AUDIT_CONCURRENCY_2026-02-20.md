# Concurrency and State Integrity Audit
**Date**: 2026-02-20
**Auditor**: Claude Sonnet 4.6 (automated)
**Scope**: Race conditions, thread-safety violations, state machine bugs, and unsafe concurrent access across player, processing pipeline, backend services, library, and frontend.

---

## Deduplication — Existing Open Issues

The following concurrency issues are open and **excluded** from new findings:

| Issue | Description |
|-------|-------------|
| #2328 | ProcessorFactory cache eviction unsafe during concurrent dict iteration |
| #2326 | `_chunk_tails` accessed concurrently without lock causing crossfade race |
| #2314 | Module-level processor caches lack thread safety |
| #2308 | `PlaybackController.add_callback` not thread-safe |
| #2297 | `start_prebuffering()` TOCTOU race — duplicate threads |
| #2213 | `PerformanceMonitor` accessed outside lock in realtime processor |
| #2077 | Lock contention in parallel processor window cache |

---

## Dimension 1: Player Thread Safety

**Files audited**: `enhanced_audio_player.py`, `gapless_playback_engine.py`, `queue_controller.py`, `playback_controller.py`, `audio_file_manager.py`

### Safe Patterns Found

| Pattern | Location | Notes |
|---------|----------|-------|
| `_auto_advancing` threading.Event | `enhanced_audio_player.py:110` | Atomic guard prevents duplicate auto-advance threads |
| Snapshot callbacks before iteration | `gapless_playback_engine.py:62-63` | Copies list under lock, iterates outside lock (fixes #2412) |
| Non-daemon outer + daemon inner thread | `gapless_playback_engine.py:87-147` | Resilient shutdown without mid-I/O kill |
| `update_lock` holds buffer writes | `gapless_playback_engine.py:159-172` | Both success and error paths protected |
| Atomic read-advance position | `playback_controller.py:122-137` | `read_and_advance_position()` under RLock (fixes #2153) |
| Load outside lock, swap inside | `audio_file_manager.py:59-64` | I/O outside lock, atomic dict swap inside |
| Chunk copy before return | `audio_file_manager.py:129` | `chunk.copy()` prevents caller modifications of internal array |

### CC-01: `audio_file_manager.py` — `reference_data`/`reference_file` Written Without Lock

- **Severity**: MEDIUM
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/audio_file_manager.py:41-42, 93-94, 180-181`
- **Status**: NEW
- **Trigger Conditions**: Background fingerprint-loading or reference analysis writes `reference_data` while the playback thread reads it for level matching.
- **Evidence**:
  ```python
  # Instance variables (lines 41-42) — NOT protected by _audio_lock
  self.reference_data: np.ndarray | None = None
  self.reference_file: str | None = None

  # Write without lock (lines 93-94)
  self.reference_data = loaded_audio
  self.reference_file = filepath

  # clear_reference() also holds NO lock (line 180-181)
  self.reference_data = None
  self.reference_file = None
  ```
  Contrast with `audio_data` / `current_file` which are consistently protected by `_audio_lock`.
- **Impact**: A playback thread reading `reference_data` concurrently with a write can observe a torn state — non-None `reference_file` pointing to None `reference_data` or vice versa. On NumPy arrays this can cause wrong level matching or silent crashes.
- **Suggested Fix**: Extend `_audio_lock` coverage to `reference_data`/`reference_file` reads and writes. Mirror the existing `clear_audio()` pattern with a `clear_reference()` that acquires `_audio_lock`.

---

### CC-02: `enhanced_audio_player.py` — `_current_fingerprint` Dict Unprotected

- **Severity**: MEDIUM
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/enhanced_audio_player.py:106, 206-218`
- **Status**: NEW
- **Trigger Conditions**: Fingerprint loads in a background thread (or deferred call) while the playback thread reads `_current_fingerprint` for adaptive DSP parameters.
- **Evidence**:
  ```python
  self._current_fingerprint: dict | None = None  # line 106 — no lock

  # Written at lines 206, 213, 218 without any lock:
  self._current_fingerprint = fingerprint_data   # line 213

  # Read at line 207 without lock:
  if self._current_fingerprint:
      ...
  ```
  The player has `threading.Event._auto_advancing` for auto-advance guard but no lock for `_current_fingerprint`.
- **Impact**: Reader observes `_current_fingerprint is not None` but then reads a partially initialised dict (Python dict assignment is not guaranteed atomic under concurrent access without the GIL being held across the full assignment and subsequent reads). At minimum, adaptive mastering could apply a stale or incorrect fingerprint. At worst, `KeyError` on partially constructed dict.
- **Suggested Fix**: Add a `threading.Lock()` (e.g., `self._fingerprint_lock`) and wrap all reads/writes to `_current_fingerprint` with it.

---

### CC-03: `queue_controller.py` — Unprotected Track List Iteration and Length Checks

- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/queue_controller.py:204-206, 241, 245, 249, 268-275`
- **Status**: NEW
- **Trigger Conditions**: Any code path that modifies the queue (e.g., `add_to_queue`, `remove_from_queue`) races with `load_playlist` or `set_queue` iterating the track list on another thread.
- **Evidence**:
  ```python
  # Unprotected iteration (lines 204-206)
  for track in playlist.tracks:   # list could be modified mid-iteration
      self.queue.add(track)

  # Unprotected len() checks (lines 241, 245, 249)
  if len(self.queue.tracks) == 0: ...
  idx = len(self.queue.tracks) - 1

  # Unprotected iteration in set_queue (lines 268-275)
  for track in track_list:
      ...
  ```
  `QueueController` has no local locks; all safety is assumed to be delegated to `QueueManager`. If `QueueManager` lacks a lock around iteration (not verified), these are unsafe.
- **Impact**: `RuntimeError: dictionary changed size during iteration` or `IndexError` on concurrent queue operations. Could cause skipped tracks or crashed playback thread.
- **Suggested Fix**: Verify `QueueManager` holds a lock across iteration, or add a snapshot pattern (`tracks = list(self.queue.tracks)`) before iterating.

---

## Dimension 2: Audio Processing Pipeline

**Files audited**: `simple_mastering.py`, `parallel_processor.py`, `audio_file_manager.py`

### Findings: NONE (all safe)

| Pattern | Location | Notes |
|---------|----------|-------|
| Double-check lock for fingerprint service lazy init | `simple_mastering.py:47-51` | Thread-safe singleton creation |
| `processed = audio.copy()` before in-place ops | `simple_mastering.py:298` | Explicit copy; never modifies input |
| Transactional tail state commit | `simple_mastering.py:244-248` | `new_tail` staged, `prev_tail` committed only after write succeeds |
| `new_tail = ...copy()` in crossfade paths | `simple_mastering.py:202, 230, 238` | Independent copy per chunk boundary |
| Window/FFT cache behind `threading.Lock` | `parallel_processor.py:42, 60-64` | All cache lookups/inserts lock-protected |
| ThreadPoolExecutor in context managers | `parallel_processor.py:108, 112, 225` | Guaranteed cleanup on exception |
| List comprehension (not `* n`) for band arrays | `parallel_processor.py:218-222` | Prevents shared-reference aliasing (fixes #2424) |

No new findings in this dimension.

---

## Dimension 3: Backend WebSocket & Streaming

**Files audited**: `audio_stream_controller.py`, `chunked_processor.py`, `processing_engine.py`

### Safe Patterns Found

| Pattern | Location | Notes |
|---------|----------|-------|
| `_global_stream_semaphore` (asyncio.Semaphore) | `audio_stream_controller.py:60` | Module-level cap across all instances (fixes #2469) |
| `SimpleChunkCache._lock` (threading.Lock) | `audio_stream_controller.py:79` | All cache ops locked (fixes #2436) |
| `_SEND_QUEUE_MAXSIZE = 4` bounded async queue | `audio_stream_controller.py:50, 1000` | Prevents unbounded heap growth when client is slow |
| `asyncio.to_thread()` for CPU-bound work | `processing_engine.py` | Avoids starving event loop |
| `asyncio.Lock` for `_processor_lock` | `processing_engine.py` | Serialises concurrent access to processing engine |
| `invalidate_chunk()` on processing failure | `audio_stream_controller.py:558-564` | Evicts corrupt cache entry (fixes #2085) |
| Chunk tail cleanup in `finally` blocks | `audio_stream_controller.py:598, 1361` | Guaranteed cleanup on disconnect |
| Per-chunk open/read/close for normal stream | `audio_stream_controller.py:712-719` | Avoids loading full file into memory (fixes #2121) |

### CC-04: `AudioStreamController._stream_type` — Shared Instance Variable Corrupted by Concurrent Coroutines

- **Severity**: MEDIUM
- **Dimension**: Backend WebSocket & Streaming
- **Location**: `auralis-web/backend/audio_stream_controller.py:183, 431, 623, 1030, 1085`
- **Status**: NEW
- **Trigger Conditions**: Two WebSocket clients connect concurrently — one requesting enhanced audio (`stream_enhanced_audio`) and one requesting normal audio (`stream_normal_audio`) — sharing the same `AudioStreamController` singleton instance.
- **Evidence**:
  ```python
  # Line 183: single shared field on instance
  self._stream_type: str | None = None

  # Line 431 (stream_enhanced_audio):
  self._stream_type = "enhanced"
  # ... then awaits semaphore (yields to event loop) ...
  await asyncio.wait_for(self._stream_semaphore.acquire(), timeout=5.0)

  # Line 623 (stream_normal_audio, runs concurrently):
  self._stream_type = "normal"   # overwrites "enhanced" while enhanced is mid-stream

  # Line 1030 (_send_pcm_chunk) — reads _stream_type long after it was set:
  "stream_type": self._stream_type,  # now "normal" for an enhanced stream!
  ```
  The `await asyncio.wait_for(...)` at line 441 yields control to the event loop, allowing `stream_normal_audio` to begin and overwrite `_stream_type` before enhanced streaming reads it.
- **Impact**: Enhanced audio chunks are tagged `stream_type: "normal"` (and vice versa) in WebSocket messages. The frontend dispatches based on `stream_type` to decide which Redux state to update; mismatched tags cause the normal-stream playback state machine to receive enhanced-stream data and vice versa, producing silent playback or stuck UI.
- **Suggested Fix**: Convert `_stream_type` from an instance field to a local variable passed through the call chain, or capture it as a closure variable at the start of each streaming method before any `await` point.

---

## Dimension 4: Library & Database

**Files audited**: `library/manager.py`, `library/scanner/scanner.py`, `library/scanner/batch_processor.py`, `library/migration_manager.py`, `library/cache.py`

### Safe Patterns Found

| Pattern | Location | Notes |
|---------|----------|-------|
| `pool_pre_ping=True` | `manager.py:118` | Prevents stale connection re-use |
| `pool_size=5, max_overflow=5` | `manager.py:119-120` | Bounded pool for SQLite WAL |
| `PRAGMA journal_mode=WAL` | `manager.py:129` | Readers don't block writers |
| `_delete_lock` (RLock) + PRE+POST cache invalidation | `manager.py:527-551` | Serialises concurrent deletes; double-invalidation closes repopulation window |
| `_scan_slots_lock` (Lock) | `manager.py:162, 245-254` | Protected scan slot counter with underflow guard |
| Inter-process `migration_lock` (fcntl / msvcrt) | `migration_manager.py:34-116` | Non-blocking retry with 30s timeout; guaranteed cleanup |
| Double-check version re-read after acquiring migration lock | `migration_manager.py:423-426` | Another process migrating concurrently is handled |
| SQLite Online Backup API (`src.backup(dst)`) | `migration_manager.py:349` | Consistent snapshot through WAL; not raw file copy |
| Scan slot released in `finally` | `scanner.py:185-189` | Cannot leak slot on exception |

### CC-05: `QueryCache._global_cache` — Dict Operations Not Thread-Safe

- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/cache.py:70-93, 95-122, 124-156, 179`
- **Status**: NEW
- **Trigger Conditions**: The background library scanner runs as a `threading.Thread`; when it completes scanning a batch it may trigger cache invalidation (via `manager.delete_track()` → `invalidate_cache()`) while async FastAPI HTTP handlers are concurrently calling `cache.get()` or `cache.set()` on the same `_global_cache` instance.
- **Evidence**:
  ```python
  # cache.py:179 — module-level shared instance, no lock
  _global_cache = QueryCache(max_size=256, default_ttl=300)

  # QueryCache.get() (lines 80-93) — no lock:
  if key in self.cache:          # check
      self.cache.move_to_end(key)  # access — key may be deleted between check and here
      return self.cache[key]     # KeyError if deleted by concurrent invalidate()

  # QueryCache.invalidate() (lines 124-156) — iterates dict without lock:
  for key in list(self.cache.keys()):
      if pattern.match(key):
          del self.cache[key]    # races with concurrent get()/set()
  ```
  Scanner thread calls `invalidate()` while event-loop coroutines call `get()`. Despite Python's GIL, the check-then-act pattern at lines 80-88 is not atomic: the GIL can be released between the membership check (`if key in self.cache`) and the subsequent `move_to_end()` / `del`, yielding a `KeyError`.
- **Impact**: Intermittent `KeyError` in library query handlers when scanner completes and invalidates cache entries concurrently. Results in 500 errors for library browsing operations during or immediately after library scans.
- **Suggested Fix**: Add `threading.Lock()` to `QueryCache.__init__` and wrap all `get()`, `set()`, and `invalidate()` bodies with it. The lock scope is narrow (no I/O inside cache methods), so contention will be minimal.

---

## Dimension 5: Frontend State Consistency

**Files audited**: `store/slices/playerSlice.ts`, `hooks/websocket/useWebSocketSubscription.ts`, `services/websocket/protocolClient.ts`, `services/audio/AudioPlaybackEngine.ts`, `hooks/api/useRestAPI.ts`

### Findings: All issues resolved in preceding frontend audit

Three frontend concurrency bugs were identified and fixed during the `/audit-frontend` pass earlier in this session:

| Bug | Location | Fix Applied | Issue |
|-----|----------|-------------|-------|
| PONG handler accumulates on reconnect | `protocolClient.ts:269-295` | `pongUnsubscribe` ref stored; `stopHeartbeat()` removes it | #2486 |
| `useWebSocketSubscription` churn from inline array deps | `useWebSocketSubscription.ts:129` | `[messageTypes.join('\x00')]` value-stable string dep | #2487 |
| Stale `AnalyserNode` from closed `AudioContext` | `AudioPlaybackEngine.ts:24-40` | Context identity + state check before reuse | #2488 |

No new frontend state findings in this concurrency pass.

---

## Summary Table

| ID | Severity | Dimension | Location | Status |
|----|----------|-----------|----------|--------|
| CC-01 | MEDIUM | Player Thread Safety | `audio_file_manager.py:41-42,93-94` | NEW → Issue created |
| CC-02 | MEDIUM | Player Thread Safety | `enhanced_audio_player.py:106,206-218` | NEW → Issue created |
| CC-03 | LOW | Player Thread Safety | `queue_controller.py:204-275` | NEW → Issue created |
| CC-04 | MEDIUM | Backend WebSocket | `audio_stream_controller.py:183,431,623` | NEW → Issue created |
| CC-05 | MEDIUM | Library & Database | `library/cache.py:70-156,179` | NEW → Issue created |
| — | HIGH | Player Thread Safety | `playback_controller.py:42,46` | Existing #2308 |
| — | MEDIUM | Backend Streaming | `audio_stream_controller.py:208` | Existing #2326 |
| — | MEDIUM | Backend Streaming | `chunked_processor.py` | Existing #2314 |
| — | MEDIUM | Player Thread Safety | `gapless_playback_engine.py` | Existing #2297 |
| — | MEDIUM | Player Thread Safety | `realtime_processor.py` | Existing #2213 |
| — | HIGH | Audio Processing | `parallel_processor.py` | Existing #2077 |
| — | MEDIUM | Audio Processing | `chunked_processor.py` | Existing #2328 |

## Key Safe Architecture Decisions

- **Migration**: Inter-process file locking + double-check version + backup-before-migrate is a robust pattern. No findings.
- **Audio DSP**: Copy-before-modify consistently enforced across all processing paths. No sample-count violations found.
- **Backend streaming**: `asyncio.Semaphore` (module-level), `asyncio.Lock`, and `asyncio.to_thread()` are correctly used. Processing engine is well-protected.
- **Library pool**: WAL + `pool_pre_ping` + appropriate pool size is correct for multi-threaded SQLite access.
