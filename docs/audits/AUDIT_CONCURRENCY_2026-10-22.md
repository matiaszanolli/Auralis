# Concurrency and State Integrity Audit: 2026-10-22

**Scope**: all 5 dimensions (Player Thread Safety, Audio Processing, Backend Streaming, Library & Database, Frontend State). Depth `deep`, no limit.
**Tree**: `master` at `44e4d433` (refactor(rust): drop the nine PyO3 bindings that had no production caller, #5764).
**Method**: a fresh read of the current source. One `general-purpose` dimension agent ran per dimension, at most 3 at a time. Findings were deduplicated against all 5,613 GitHub issues (`--state all`, up to #5859), `.claude/issues/`, and prior concurrency reports. The orchestrator re-read and confirmed every HIGH finding against the code before including it. Findings reproduced with throw-away scratch scripts are marked "Reproduced" in their Evidence; no repo file was modified.

## Executive Summary

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 3 |
| MEDIUM | 9 |
| LOW | 30 |
| **Total** | **42** distinct findings (43 sections; CONC-D4-03 is filed together with CONC-D4-02, and CONC-D2-01 was merged into CONC-D3-02) |

Status split: 38 NEW, 4 regressions of closed issues:
- CONC-D5-01 regresses #4563.
- CONC-D5-02 regresses #2259.
- CONC-D3-02 regresses #5323 (residual window).
- CONC-D3-03 regresses #5248 (partial).

Thirty-six open issues were cross-referenced and **not** re-reported (see "Skipped as existing").

The engine core holds up well:
- No CRITICAL finding.
- No in-place mutation of a shared NumPy buffer.
- No lock-order inversion. The player lock graph was re-derived and is acyclic.
- No database corruption path.
- `HybridProcessor._process_lock` serialises every concurrent chunk worker.
- Mastering targets are deep-copied per processor.
- The Rust `compute_fingerprint` copies its input before `py.detach`.
- The migration file lock and the thread lock are both present.

The risk has moved to the **edges of lifecycles**: cancellation, teardown, restart and stream supersession.

### Key themes

1. **Cancellation does not stop the thread.** The same root cause recurs in five findings:
   - CONC-D3-01: a SeekableSource / normal-stream temp-WAV hold is leaked.
   - CONC-D3-03: a recommendation analysis keeps its I/O-pool worker after its timeout.
   - CONC-D3-06: a cancelled job's DSP keeps a job-pool worker.
   - CONC-D3-02: a pre-warm render cannot be aborted.
   - CONC-D4-06: a fingerprint extraction outlives the reset.

   Each time, an `await` on `to_thread`/an executor is cancelled while the worker keeps running, and the result (a refcount, a durable file, a DB row) lands on an object nobody owns any more.
2. **Stream supersession on the client is ordered wrongly.**
   - CONC-D5-01: the #4563 epoch filter cannot see the frames it was built for. They all arrive *before* the new `audio_stream_start`.
   - CONC-D5-02: the seek-resume branch skips `setSeekOffset`.
   - CONC-D5-03: a reissue or reconnect appends onto lookahead.
   - CONC-D5-07: end and error messages carry no epoch.

   All four are the same missing "discard boundary" on the frontend.
3. **Stop/start is not symmetric.**
   - CONC-D4-02/03: `FingerprintExtractionQueue` and `LibraryAutoScanner` never clear their stop flag, so `POST /api/library/reset` silently kills batch fingerprinting and auto-scan for the rest of the session.
   - CONC-D4-05: the on-demand fingerprint queue keeps its in-flight id across stop/start.
   - CONC-D3-05: `JobWorker.stop()` misses semaphore-parked jobs.
   - CONC-D3-10: teardown helpers swallow the caller's own cancellation.
4. **Durable chunk-cache provenance depends on races.** CONC-D3-02, CONC-D3-08 and CONC-D3-09 all let a chunk rendered with the wrong level history or seam state be persisted under the shared durable key and replayed on every later cache hit.

### Most impactful races

- **CONC-D3-01 (HIGH)**: skipping through m4a/aac/wma (or mp3/ogg on the normal path) while the first decode is running permanently pins a full decoded float32 WAV per skip, until the next launch.
- **CONC-D5-01 (HIGH)**: every forward seek made while frames are in flight plays seconds of pre-seek audio at the head of the seek.
- **CONC-D5-02 (HIGH)**: after any in-session seek:
  - the progress clock restarts at 0:00;
  - reconnect and live-setting resumes restart at the wrong point;
  - auto-advance never fires for that track.

## Concurrency Matrix

| Component | Concurrency primitive(s) | Status | Findings |
|---|---|---|---|
| `AudioPlayer` + mixins (`auralis/player/`) | `AudioFileManager._audio_lock` (RLock), `PlaybackController._lock`, thread-local `defer_notifications()` | Safe at buffer level. The composite snapshot tears across a gapless swap. | D1-01, D1-05 |
| `GaplessPlaybackEngine` + `PrebufferMixin` | `update_lock` (outer) → `_audio_lock`; `_thread_lock` leaf | Lock order verified. Narrow lost re-arm. | D1-03 |
| `QueueManager` / `QueueController` mixins | `QueueManager._lock` (borrowed by the `QueueController` mixins) | Safe. Holds the lock across O(n) `to_dict()`. | D1-04 |
| `IntegrationManager` | `_position_lock` → `_audio_lock`; `_stats_lock` leaf | `_position_lock` does not exclude the swap. | D1-01 |
| Backend track-change paths | `transition_lock`, `_sequencer.lock`, `_set_queue_engine_lock`, none on `/load` | Four unrelated locks. Masked by #5563/#5708. | D1-02, D3-11 |
| `realtime/` (`RealtimeProcessor`, matcher, auto-master) | `RealtimeProcessor.lock` → sub-locks | Order verified. O(n) RMS under the lock. | D1-04 |
| `HybridProcessor` / `ContinuousMode` | per-instance `_process_lock` (RLock) | Safe. Serialises calls but does not order them across consumers. | D3-02, D3-09 |
| `hybrid_processor_singleton` | `_processor_cache` lock, keyed by `id(config)` | Identity bug, not tearing. | D2-03 |
| `ProcessorFactory` / `ProcessorPool` | factory `_lock` + build outside; pool pop-on-acquire | Safe. LRU-order nit. Stale `last_*` telemetry on a pooled instance. | D2-04, D2-05 |
| `ChunkedAudioProcessor` (+ `chunk_*`) | `_processor_lock`, `_sync_cache_lock`, `chunk_cancel_event` | `get_wav_chunk_path` mutates level state under the wrong lock. | D2-02, D3-07 |
| `SeekableSource` / `ConvertedWavRegistry` | registry lock + refcounts; **none** on the source | **Race on close vs in-flight acquire.** | **D3-01** |
| Stream controller / `stream_*.py` | module `_stream_semaphore`, per-task ContextVars, epoch counter | Safe (semaphore and epochs verified). | D3-04 |
| Enhancement pre-warm | `_track_is_live_streaming` check only | Check-then-act. Shares the live factory. | D3-02 |
| `proactive_buffer` | own consumer factory | Writes the same durable keys as the live stream. | D3-08 |
| `executors.py` pools | stream / job / I/O (default) pools | Discipline verified. Recommendation analysis on the I/O pool. | D3-03, D3-06 |
| `JobWorker` | `_concurrency_semaphore`, `_tasks` | Watchdog OK. Parked jobs escape `stop()`. | D3-05, D3-06, D3-10 |
| Chunk disk cache + reaper | class-level `_prune_lock` / `_prune_scan_lock`, atomic temp+replace | Writes atomic. TOCTOU on hit-then-read. | D3-07 |
| `LibraryDatabase` engines (3) | `check_same_thread=False`, `pool_pre_ping=True`, shared timeout constants | Safe. A fourth CLI engine drifts. | D4-07 |
| `ScanCoordinator` / `claim_scan` | slot lock + exact-path reservation | Symmetric and fail-closed. Overlapping paths not detected. | D4-08 |
| `migration_lock.py` | `threading.Lock` + `fcntl`/`msvcrt` | Both present. Verified. | none |
| `FingerprintExtractionQueue` | `should_stop` bool, UNIQUE-claim placeholder rows | Workers exit on a lost claim. Not restartable. | D4-01, D4-02, D4-06, D4-10 |
| On-demand fingerprint queue | `_state_lock` | Keeps state across stop/start. | D4-05 |
| `LibraryAutoScanner` + watchdog | `asyncio.Event`s, `call_soon_threadsafe` hops | Hops verified. Not restartable. Lost wake-ups. Observer leak. | D4-03, D4-04, D4-09 |
| Scanner components | plain-bool stop flags | Hardening (no-GIL). | D4-11 |
| Frontend WS frame layer | synchronous FIFO dispatch, seq watermarks | Safe. Watermark reset deferred to an effect. | D5-08 |
| Enhanced streaming session (`hooks/enhancement`) | `streamEpochRef`, `pendingChunksRef`, `isOutOfSequence` heuristic | **No discard boundary at seek/reissue.** | **D5-01**, **D5-02**, D5-03, D5-06, D5-07, D5-11 |
| `AudioPlaybackEngine` | none (async `startPlayback`) | Not cancel-safe. | D5-04 |
| Queue hooks | per-field generation counters, `reconcileQueueIndex` | `useQueueFetch` bypasses reconciliation. | D5-05 |
| Scan / fingerprint UI hooks | refcounted shared stores, timers | Minor ordering gaps. | D5-09, D5-10, D5-12 |

## Relationships

- **"Cancelled await, live thread" family**: D3-01, D3-02, D3-03, D3-06 and D4-06 share a root cause, and so does the decode side of open #5730. One shared helper fixes the family: a holder object whose result is released or discarded by a done-callback when the awaiting task was cancelled, plus a cooperative `cancel_event` threaded into the long call. Fix D3-01 first and reuse its pattern.
- **Frontend discard boundary**: D5-01, D5-02, D5-03 and D5-07 have one fix site. Treat `seek_started`, and a sender-set "reissue pending" flag, as the point where the buffer is reset, `pendingChunksRef` is cleared and the absolute stream-position base is set. That makes the #4563 epoch filter and the `isOutOfSequence` heuristic secondary. D5-02 feeds D5-03 and D5-11: the resume getter they rely on reports seconds since the seek.
- **D5-06 + D5-11**: the frontend never sends `stop`/`pause`. As a result the backend keeps streaming into an unbounded `pendingChunksRef` after a client teardown, and `lastStreamCommand` is never cleared. Adding a client-side `stop` on teardown addresses both.
- **Durable cache provenance**: D3-02, D3-08, D3-09, D2-02, plus BE-D3-02/BE-D11-03 in the backend report. These are writers with different level histories racing for one durable key. Persisting only from the live stream's sequential renders, or keying background renders separately, closes the class.
- **Restart symmetry**: D4-02, D4-03, D4-05, D4-09 and D3-05 all surface through `POST /api/library/reset` → `stop_background_workers()` / `start_background_workers()`. A real stop→start test per worker would have caught every one of them. The existing tests use `AsyncMock` workers.
- **Compound**: D4-01 (workers drop out on a lost claim) combined with D4-02 (no restart) means that after a reset the batch fingerprint pass does not run at all. Before a reset it already runs at a fraction of its configured parallelism.
- **Latent, gated by open issues**: D1-02 becomes MEDIUM once #5563 is fixed and engine next/previous run for real. Re-rate it then.

## Prioritized Fix Order

1. **CONC-D3-01 (HIGH)**: leaks a compounding resource on every quick skip through compressed formats. Self-contained in `seekable_source.py` and `stream_normal.py`, and its fix pattern carries over to D3-03 and D3-06.
2. **CONC-D5-01 + CONC-D5-02 (HIGH)**: audible on every seek, and one fix site in `useEnhancedSeek.ts` / `useEnhancedStreamStart.ts`. Fix them together with D5-03 and D5-07. Add the missing test that emits stale frames *between* `seekTo()` and the new start.
3. **CONC-D4-02/03 + CONC-D4-01 (MEDIUM)**: silent loss of background fingerprinting and auto-scan. Each is a one-line class of fix (clear the flag in `start()`, `continue` instead of `break` on a lost claim) plus real stop→start tests.
4. **CONC-D3-02 (MEDIUM)**: give the pre-warm its own consumer factory and a cancel event, which closes the #5323 residual. Bundle it with D3-08 and D2-02.
5. **CONC-D3-03 (MEDIUM)**: move per-play analysis off the DB-sized I/O pool, and dedup it by `track_id`.
6. **CONC-D5-04, CONC-D5-05, CONC-D5-06 (MEDIUM)**: client engine cancel-safety, queue-fetch reconciliation, and a cap on `pendingChunksRef` plus a client-side `stop`.
7. **CONC-D1-01 (MEDIUM)**: a single-section snapshot helper. Its reach is low today (#5708).
8. The LOW findings, opportunistically. Cheap hardening worth doing early:
   - D3-04: the `TaskGroup` in `send_pcm_chunk`.
   - D3-07: treat a missing file on a hit as a miss.
   - D3-10: discriminate with `Task.cancelling()`.
   - D4-07: use `create_migration_engine`.
   - D5-10: one missing `cancelFingerprintTimeout()`.

## HIGH Findings

### CONC-D3-01: SeekableSource conversion reference is lost when a stream is torn down while the temp-WAV decode is in flight
- **Severity**: HIGH
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/seekable_source.py:241-264` (resolve/close), `:141-176` (acquire); `auralis-web/backend/core/stream_normal.py:132-134,273-277`; `stream_enhanced.py:292-293`; `stream_seek.py:285-286`; `proactive_buffer.py:114-122`
- **Status**: NEW (adjacent to closed #5253 / #5402, whose close-on-teardown is present but does not cover this race)
- **Trigger Conditions**: A non-natively-seekable file (m4a/aac/wma, and every FFMPEG_FORMATS file on the normal-stream path incl. mp3/ogg) is started and the stream is cancelled (seek, track skip, stop, disconnect) or its first chunk hits `CHUNK_PROCESS_TIMEOUT` while the whole-file FFmpeg decode inside `ConvertedWavRegistry.acquire()` is still running (seconds for a normal track, tens of seconds for a long one).
- **Evidence**:
  ```python
  # seekable_source.py
  254:        self._key, self._resolved = self._registry.acquire(self._filepath)   # blocks for the whole decode
  257:    def close(self) -> None:
  258-        if self._key is None:          # still None while acquire() is running -> no-op
  259-            return
  # stream_normal.py
  132:            conversion_key, streaming_filepath = await asyncio.to_thread(
  133:                converted_wavs.acquire, validated_filepath, prefix=stream_temp_prefix()
  # a CancelledError here abandons the thread; `conversion_key` stays None, so the finally at :273 releases nothing
  ```
  Enhanced/seek path: `process_chunk` (executor thread) -> `load_chunk` -> `processor._source.resolve()` -> `acquire()`; the stream `finally` calls `await asyncio.to_thread(processor.close)` (`stream_enhanced.py:293`) immediately after the cancel, while the thread is still decoding. `close()` sees `_key is None` and returns; the thread later stores `_key` on a processor nobody will close again. Reproduction (scratchpad `t4.py`, real `ConvertedWavRegistry`/`SeekableSource`, 1 s fake decode, `close()` at 0.2 s): `refs` stays 1 after `close()`, the conversion is never idle, a following holder's `release` leaves refs at 1, and even `registry.shutdown()` leaves the temp dir on disk.
- **Impact**: Each occurrence permanently pins one full-track decoded float32 WAV (about 0.2 GB per 10 min of stereo 44.1 kHz, over 1 GB for an hour-long file) under the temp root, which may be tmpfs. The leaked ref also keeps the conversion out of the idle/eviction path (`IDLE_CONVERSIONS_RETAINED`), so later streams of that file can never reclaim it. The orphaned thread additionally runs an uncancellable FFmpeg decode to completion. Skipping quickly through an m4a/aac library compounds this per skipped track; only the next-launch startup sweep reclaims it.
- **Siblings**: `proactive_buffer.py:116-119` (same race, plus a synchronous `rmtree` on the event loop, covered by existing #5064 for the cache-worker equivalent); `streamlined_processor_cache.py:64-77` (`close_dropped_processor` on eviction/prune/timeout while a render thread may still be inside `resolve()`); `routers/enhancement_prewarm.py:163` (`finally: processor.close`, same window after a cancelled/timed-out `get_wav_chunk_path`).
- **Suggested Fix**: Make hold ownership explicit and race-free: give `SeekableSource` a lock plus a `_closed` flag. `resolve()` checks `_closed` before acquiring and, if `close()` happened while `acquire()` was in flight, immediately releases the key it just obtained instead of storing it. For the normal stream, acquire into a holder object that the `finally` can inspect (or `asyncio.shield` the acquire and release the result in a done-callback when the awaiting task was cancelled). Optionally thread a cancel event into `convert_to_temp_wav` -> `load_audio(..., cancel_event=...)` so the decode itself stops (see open #5730 for the loader side).
- **Cross-audit overlap**: BE-D2-02 in `AUDIT_BACKEND_2026-10-22.md` and INT-F8-4 in `AUDIT_INTEGRATION_2026-10-22.md` describe the same race. File it once.

### CONC-D5-01: Regression of #4563 — pre-seek frames in flight are still appended to the post-seek buffer
- **Severity**: HIGH
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancedSeek.ts:49-92`; `auralis-web/frontend/src/hooks/enhancement/useEnhancedStreamStart.ts:92-107`; `auralis-web/frontend/src/hooks/enhancement/audioChunkIngest.ts:61-79`; `auralis-web/frontend/src/hooks/enhancement/useStreamMessageHandlers.ts:84-135`
- **Status**: Regression of #4563 (CLOSED; the shipped fix does not meet that issue's acceptance criterion "no PCM frame produced by the superseded stream reaches the audio buffer")
- **Trigger Conditions**: User seeks while the backend stream task is mid-delivery (frames in the send queue / socket buffers — the backend comment `core/audio_stream_controller.py:82-95` itself sizes this at ~0.9-3.5 s of audio). The window is the interval between `seekTo()` and arrival of the seek's `audio_stream_start`; it is narrow (ms, a burst of frames), so any single seek hits it with low probability, but it is deterministic when it does.
- **Evidence**:
  ```ts
  // useEnhancedSeek.ts:67-72 — client resets immediately, BEFORE the old stream is cancelled
  core.playbackEngineRef.current?.stopPlayback();
  core.pcmBufferRef.current?.reset();
  ...
  core.lastReceivedChunkIndexRef.current = -1;
  // audioChunkIngest.ts:71-73 — filter fires only if chunk epoch != the *currently adopted* epoch
  if (incomingEpoch != null && currentEpoch != null && incomingEpoch !== currentEpoch) return 'superseded-epoch';
  // useEnhancedStreamStart.ts:92-107 — is_seek => keep buffer, no reset
  if (isSeek && core.playbackEngineRef.current && core.pcmBufferRef.current) { ... return; }
  ```
  Wire order is FIFO and the backend cancels *and awaits* the old task before emitting `seek_started` and the new `audio_stream_start`
  (`ws_handlers/playback_commands.py:451-455`, `_cancel_prior_task`). So every stale frame arrives **before** the new epoch is adopted, while
  `streamEpochRef` still equals the OLD epoch → `classifyChunk` returns `null` and the frame is appended into the freshly reset buffer. The epoch
  filter only ever drops frames arriving *after* the new `audio_stream_start`, an order the backend cannot produce (the frontend epoch tests
  `useAudioStreamingCore.epoch.test.tsx:149-199` emit the stale chunk after the new start, i.e. the impossible order). The only incidental
  mitigation is `isOutOfSequence` (`audioChunkIngest.ts:88-90`), which resets the buffer only when the seek target is >= 2 chunks *behind* the last stale index.
- **Impact**: Forward seeks (the common scrub direction) and short backward seeks play up to a few seconds of pre-seek audio at the head of the seek
  (audible stutter/rewind) — the defect #4563 reported. `startPlaybackWhenBuffered` may even start the engine on the stale frames.
- **Siblings**: `rg "pcmBufferRef.current\??\.reset\(\)|buffer.reset\(\)" hooks/enhancement` → only `useEnhancedSeek.ts:69` and the OOS branch `useStreamMessageHandlers.ts:130`; reconnect-resume and live-setting `reissueActiveStreamAs` have the same missing boundary (see CONC-D5-03).
- **Suggested Fix**: Treat `seek_started` as the discard boundary (it is ordered after every pre-seek frame): in its subscription (`useEnhancedSeek.ts:99`) call `buffer.reset()`, clear `pendingChunksRef`, reset `lastReceivedChunkIndexRef`/`flowPausedRef`, keep the engine stopped. Equivalent alternative: set a `seekPendingRef` in `seekTo`, make `handleChunk` drop (not queue) while it is set, clear it in the `audio_stream_start` wrapper. Add a test that emits stale old-epoch chunks *between* `seekTo()` and the new `audio_stream_start`.
- **Cross-audit overlap**: INT-F1-1 in `AUDIT_INTEGRATION_2026-10-22.md` and BE-D11-01 in `AUDIT_BACKEND_2026-10-22.md` are the same regression of #4563. File it once.

### CONC-D5-02: Regression of #2259 — engine position loses the seek offset on every in-session seek (UI time, resume position, auto-advance)
- **Severity**: HIGH
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancedStreamStart.ts:92-107,168-172`; `auralis-web/frontend/src/services/audio/PlaybackPositionTracker.ts:70-93`; `auralis-web/frontend/src/hooks/enhancement/usePlaybackTransport.ts:155-169`; `auralis-web/frontend/src/contexts/usePlaybackSessionHooks.ts:118-121`
- **Status**: Regression of #2259 (CLOSED). The `setSeekOffset` fix (5343b23d) lives only in the engine-recreation branch; the #3185 resume branch (be24bfa7) made it unreachable for normal seeks. No test covers it (`rg SeekOffset hooks/enhancement/__tests__` → none).
- **Trigger Conditions**: Any seek while a stream is playing (engine and buffer exist → resume branch). Then any of: reading the progress bar, a live preset/intensity/toggle change, a WS reconnect, or the track reaching its end.
- **Evidence**:
  ```ts
  // useEnhancedSeek.ts:68  seekTo → engine.stopPlayback() → positionTracker.reset() => seekOffsetSeconds = 0 (PlaybackPositionTracker.ts:70-74)
  // useEnhancedStreamStart.ts:92-107 — is_seek with live engine+buffer returns BEFORE setSeekOffset:
  if (isSeek && core.playbackEngineRef.current && core.pcmBufferRef.current) { ...; return; }
  ...
  if (isSeek && seekPosition > 0) { engine.setSeekOffset(seekPosition); }   // :171 only reached when the engine was just recreated
  // PlaybackPositionTracker.ts:89   time = seekOffsetSeconds(0) + samplesPlayed / sampleRate
  ```
- **Impact**: (1) Progress bar / `currentTime` restarts from 0:00 after each seek (`Player.tsx:63-67,130` renders the engine time). (2) The resume-position getter (`usePlaybackTransport.ts:155-169`, used by `reissueActiveStreamAs` and `replayQueueAndResume`) reports "seconds since seek", so a live intensity/preset/enhancement-toggle change or a WS reconnect after a seek restarts the stream at the wrong point (repeat/rewind). While the engine is `stopped` (between `seekTo` and first playback) the getter returns 0, so a reissue/reconnect in that window restarts the track from the beginning. (3) `useAutoAdvance` requires `currentTime >= duration - 0.5` (`usePlaybackSessionHooks.ts:120`); after a seek to S the engine reaches only `duration - S`, so auto-advance / repeat-one never fires for that track.
- **Siblings**: `rg "getCurrentPlaybackTime|setSeekOffset" src --glob '!*test*'` → `AudioPlaybackEngine.ts`, `usePlaybackTransport.ts:155-169` (position getter), `usePlaybackTransport.ts:126` (10 Hz poll), `useEnhancedStreamStart.ts:171` (the only setter).
- **Suggested Fix**: In the resume branch, when the start answers a client `seekTo` (flag set in `seekTo`, or `!engine.isPlaying()` after `stopPlayback`), call `engine.setSeekOffset(message.data.seek_position)` (backend sends the effective, chunk-aligned position). Do not apply it for a reconnect/reissue resume where the engine kept playing. More robust: keep an absolute stream-position base owned by the core and derive the resume getter from `base + samplesPlayed/sr` instead of the tracker that `stopPlayback()` resets.
- **Cross-audit overlap**: INT-F8-1 in `AUDIT_INTEGRATION_2026-10-22.md` is the same regression of #2259. File it once.

## MEDIUM Findings

### CONC-D3-02: Enhancement pre-warm still races a live stream on the shared processor and the durable chunk cache (residual window of #5323)
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/routers/enhancement_prewarm.py:120-159,188-206`
- **Status**: Regression of #5323 (the `_track_is_live_streaming` guard is present, but it is a check-then-act across an await, and the original shared-processor/no-cancel conditions are unchanged)
- **Trigger Conditions**: User toggles enhancement or changes preset/intensity mid-playback after the previous stream task has already finished (streams run far ahead of real time, so there is normally no live task). `_maybe_prewarm_upcoming_chunks` spawns the pre-warm; the frontend then re-issues `play_enhanced` for the same track (the docstring at :27-33 says it does exactly this right after the settings POST returns). If that stream registers while the pre-warm is inside a chunk render, both run on the same pooled `HybridProcessor`.
- **Evidence**:
  ```python
  120:        processor = await asyncio.to_thread(
  121:            ChunkedAudioProcessor,
  122:            track_id=track_id, filepath=filepath, preset=preset, intensity=intensity,
  126:            chunk_cache={},            # no processor_factory= (live STREAM factory) and no cancel_event=
  137:                if _track_is_live_streaming(track_id):   # checked once per chunk ...
  149:                    wav_chunk_path = await run_in_stream_executor(processor.get_wav_chunk_path, chunk_idx)  # ... then 0.2-2 s uncancellable render
  ```
  The pre-warm uses the default (live-stream) `ProcessorFactory` instead of a dedicated consumer, and passes no cancel event, so a render that began before the stream appeared cannot be aborted and `get_wav_chunk_path` (`chunk_streaming.py:217-263`) persists its result unconditionally with a fresh `LevelManager`.
- **Impact**: For about one chunk render the live stream and pre-warm interleave `process()` calls on one stateful processor (EQ/limiter state fed out of chunk order, the #5311 symptom), and pre-warm writes chunk N+1.. to the durable path with gain smoothed against no history; the live stream later serves that file as a cache hit, so a level or EQ seam is baked in permanently.
- **Siblings**: `services/recommendation_service.py:81-86` and `routers/enhancement_recommendation.py:102` also build live-factory `ChunkedAudioProcessor`s (they do not render chunks, so only the factory-LRU churn applies).
- **Suggested Fix**: Give pre-warm its own consumer factory (`get_processor_factory(PRELOAD/PREWARM_CONSUMER)`, as proactive buffer and cache worker have) and a cancel `threading.Event` that `register/handle_play_enhanced` sets when a stream for the same track starts; or have `get_wav_chunk_path` re-check "live stream for this track" immediately before the durable write.
- **Merged duplicates**: CONC-D2-01 (Audio Processing) found the same pre-warm race independently. It adds that the pre-warm `LevelManager` is empty, so its first chunk (`current+1`) takes the "establish baseline" branch and is persisted without level smoothing against `current`. A later stream serves that file as a cache hit and records its level, but never re-smooths it (#4669). The status is recorded as a residual of closed #5323 rather than a strict regression: the #5323 gate is present, but it is a check-then-act across an `await`.
- **Cross-audit overlap**: INT-F3-5 in `AUDIT_INTEGRATION_2026-10-22.md` shows the pre-warm gate reads REST `player_state_manager` state that WS playback never updates, so the pre-warm rarely fires at all. That lowers likelihood, not impact. BE-D3-02 / BE-D11-03 in `AUDIT_BACKEND_2026-10-22.md` cover the same fresh-`LevelManager`-persisted-under-the-durable-key class for the cache worker and seek paths.

### CONC-D4-02: A stopped `FingerprintExtractionQueue` can never be restarted, but library reset restarts it
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/services/fingerprint_queue.py:105,155-203,222,246`; callers `auralis-web/backend/config/background_workers.py:73-98`, `auralis-web/backend/routers/library.py:138,163`
- **Status**: NEW
- **Trigger Conditions**: `POST /api/library/reset` (confirmed): `stop_background_workers()` calls `queue.stop()` which sets `should_stop = True`; the `finally` then calls `start_background_workers()` -> `queue.start()`. `start()` never clears `should_stop` and keeps appending to `self.workers`.
- **Evidence**:
  ```python
  # fingerprint_queue.py
  105  self.should_stop: bool = False                 # only assignment to False
  184  self.should_stop = True                        # in stop()
  222  while not self.should_stop:                    # new threads exit at once
  ```
  Reproduced (`/tmp/audit/concurrency/d4_fpq_restart.py`): `stop()` -> `start()` -> workers made **0** claim calls, `should_stop` still True, 4 entries in `workers`, 0 alive.
- **Impact**: After a library reset the batch fingerprint queue is silently dead until the app restarts; the reset endpoint reports success and logs "Background worker started". Newly scanned tracks are only fingerprinted by the on-demand queue (one at a time, when something requests them), so library-wide similarity/target data never refills. `self.workers` also grows with dead threads, and `_drained_workers`/`_processed_since_drain` are not reset.
- **Siblings**: CONC-D4-03 (auto-scanner, same stop/start contract). `ondemand_fingerprint_queue` clears `_shutdown` in `start()` (OK structurally, but see CONC-D4-05); `SimilarityAutoFitWorker.start()` clears its stop event (`similarity_autofit_worker.py:60-65`, OK).
- **Suggested Fix**: In `start()` reset `should_stop = False`, clear/replace `self.workers`, and reset the drain counters; or, if single-shot is intended, make `BACKGROUND_WORKER_KEYS` restart build a fresh queue. Add a real stop->start test (the current `test_background_workers.py` only asserts `start()` was called on mocks).
- **Merged duplicates**: CONC-D4-03 is merged here as a sibling: `LibraryAutoScanner` has the same stop/start contract break. It is listed separately below for its own location and evidence, but should be filed together with this finding.
- **Cross-audit overlap**: BE-D6-01 in `AUDIT_BACKEND_2026-10-22.md` and E6-04 in `AUDIT_ENGINE_2026-10-22.md` report the same restart defect. File it once.

### CONC-D4-03: A stopped `LibraryAutoScanner` can never be restarted, but library reset restarts it
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis-web/backend/services/library_auto_scanner.py:69,78-99,112-135`
- **Status**: NEW
- **Trigger Conditions**: Same as CONC-D4-02 (`POST /api/library/reset` stops then re-`start()`s `auto_scanner`; the lifespan rollback path uses the same helper).
- **Evidence**:
  ```python
  69   self._stop_event = asyncio.Event()
  78   async def start(self): self._task = spawn_background_task(self._run(), ...)   # no clear()
  88   self._stop_event.set()          # in stop(); never cleared anywhere
  115  while not self._stop_event.is_set():   # restarted _run() returns immediately
  ```
  Reproduced (`/tmp/audit/concurrency/d4_autoscan_restart.py`): first `start()` -> task running; `stop()` then `start()` -> task `done()` is True after 0.2 s, `_stop_event.is_set()` True.
- **Impact**: After a reset, auto-scan (startup scan, periodic poll, and the watchdog-driven rescans, plus `reload_config()` wake-ups from the settings router) never runs again until the backend restarts. The scan-folder watchdog observer is also never recreated. The user sees a successful reset and an enabled "auto scan" setting that does nothing.
- **Siblings**: CONC-D4-02. grep `_stop_event` shows no other restartable-worker with this pattern in `auralis-web/backend/services/`.
- **Suggested Fix**: `start()` should `self._stop_event.clear()` (and `_trigger_event.clear()`) before spawning the task and refuse if the old task is not done; add a stop->start regression test using the real class.

### CONC-D4-01: Fingerprint workers exit permanently when they lose a claim race
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/fingerprint_scheduler_repository.py:168-179,253-268` and `auralis/services/fingerprint_queue.py:222-236,246-258`
- **Status**: NEW
- **Trigger Conditions**: Start the batch fingerprint queue with N>=2 workers on a library that has unfingerprinted tracks (every first start, and after any scan that adds tracks before the pool has drained). All workers call `claim_next_unfingerprinted_track()` with the same cursor, so several `find()` calls return the same track id; only the first INSERT of the placeholder commits.
- **Evidence**:
  ```python
  # scheduler repo 168-179
  except IntegrityError:
      # Another worker already claimed this track (UNIQUE constraint)
      session.rollback()
      return None                      # indistinguishable from "queue empty"
  ...
  except Exception as e:               # also a transient lock/IO error
      session.rollback(); error(...); return None
  # fingerprint_queue.py 225-228
  track = factory.fingerprint_scheduler.claim_next_unfingerprinted_track()
  if not track:
      debug("No more unfingerprinted tracks"); break   # worker leaves Phase 1 for good
  ```
  Reproduced (`/tmp/audit/concurrency/d4_claim_dropout.py`): real `LibraryDatabase` with 60 tracks, 8 workers, 50 ms fake extractor -> 0.3 s after start only **3 of 8** worker threads were alive, peak concurrency 3. The five that lost the first race ran Phase 2 (returns immediately) and terminated.
- **Impact**: The "N-worker pool" collapses to a few effective workers within the first claim round, so the startup fingerprinting pass (the 25D data mastering and similarity depend on) is several times slower than configured, and a worker that hits one transient DB error at the end of the queue also quits for good (tracks left unfingerprinted until restart). Because each dropped worker still calls `_on_worker_drained()` twice (`fingerprint_worker.py:113-136`), `_drained_workers` reaches the real worker count early and `on_drained` (reference-cloud refresh) can fire while other workers are still extracting. No data corruption.
- **Siblings**: `claim_next_outdated_fingerprint` (`fingerprint_scheduler_repository.py:253-268`, "rowcount != 1 -> return None" at `:233`) and the Phase 2 loop (`fingerprint_queue.py:246-258`).
- **Suggested Fix**: Make "lost race / transient error" distinct from "nothing to claim": retry inside the claim methods (loop re-running `find()` a bounded number of times after an IntegrityError, since the winner has advanced the cursor), or return a sentinel and have the worker `continue` (with the existing `time.sleep(0.1)`) instead of `break`. Only `None` from a genuinely empty `find()` should end the phase.

### CONC-D3-03: Per-play mastering-recommendation analysis runs a full-file fingerprint on the shared I/O pool, untracked and unreclaimable after its timeout (partial regression of #5248)
- **Severity**: MEDIUM
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/services/recommendation_service.py:78-98`; spawned from `auralis-web/backend/ws_handlers/playback_commands.py:319-322,374-377`; fingerprint extraction in `core/chunk_mastering.py:50-58`
- **Status**: Regression of #5248 (the timeout exists; the thread it abandons is still on the default pool)
- **Trigger Conditions**: Every `play_enhanced` / `play_normal` spawns `_generate_mastering_recommendation` as a fire-and-forget task. For a track with no fingerprint row yet (fresh library, queue not caught up), `_analyze` extracts a fingerprint from the audio (`MasteringFingerprint.from_audio_file`, up to a 90 s decode and librosa features, or a whole-file FFmpeg decode for FFMPEG_FORMATS). Rapidly skipping through unfingerprinted tracks starts one such analysis per skip.
- **Evidence**:
  ```python
  96:            asyncio.to_thread(_analyze), timeout=_asc.CHUNK_PROCESS_TIMEOUT      # default IO_EXECUTOR (8 workers = DB-pool sized)
  # playback_commands.py:319 - task handle discarded; nothing cancels it on skip/seek/stop/disconnect
  ```
  `wait_for` cancels only the awaiting side, so after 30 s (or after the track was skipped) the extraction thread keeps its slot.
- **Impact**: Up to `IO_POOL_SIZE` (8) concurrent multi-second CPU analyses occupy the pool that `tracks.get_by_id`, `processor.close`, `ChunkedAudioProcessor` construction and every repository call share, delaying the stream set-up of the track the user actually wants (the #5086 starvation pattern, which #5335 fixed for jobs by giving them their own pool). A genuinely hung file pins a worker permanently. There is also no dedup: replaying a track while its analysis is in flight launches a second identical extraction.
- **Siblings**: `routers/enhancement_recommendation.py:117` (`asyncio.to_thread(_run_recommendation)`); `routers/enhancement_prewarm.py:88` (`get_audio_info` ffprobe on the default pool).
- **Suggested Fix**: Run the analysis on a small dedicated executor (or the job pool), key in-flight analyses by `track_id` so duplicates share one future, cancel/ignore the result when the track changes, and skip extraction entirely when the fingerprint queue will produce it (use the DB tier only for the per-play path).
- **Cross-audit overlap**: INT-F5-9 in `AUDIT_INTEGRATION_2026-10-22.md` covers the same per-play analysis from the wasted-work angle.

### CONC-D1-01: Player info/callback snapshot is torn across a gapless swap (position > duration); `_position_lock` does not exclude the swap
- **Severity**: MEDIUM
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/integration_manager.py:204-225` (`_on_playback_state_change`); `auralis/player/integration_reporting.py:41-66` (`get_playback_info`); swap side `auralis/player/gapless_playback_engine.py:216-232`
- **Status**: NEW (the closed #2899/#3363/#3785/#4102 added `_position_lock` and `_audio_lock` for the individual reads but never closed the composition)
- **Trigger Conditions**: A state-change callback or `get_playback_info()` call overlaps `advance_with_prebuffer()`'s swap. A gapless swap always happens with the position at the very end of the outgoing track, so the one moment a snapshot is most likely to straddle it is exactly the moment the old position is largest. Needs the new track to be shorter than the old track's end position.
- **Evidence**:
  ```python
  # integration_manager.py:210-224 (identical shape at integration_reporting.py:45-60)
  with self._position_lock:
      with self.file_manager._audio_lock:
          current_file = self.file_manager.current_file          # read 1, _audio_lock released
      state_info.update({
          'position_seconds': self._get_position_seconds(),      # read 2: get_state_snapshot() + position, own _audio_lock section
          'duration_seconds': self.file_manager.get_duration(),  # read 3: yet another _audio_lock section
          'current_file': current_file,
  ```
  The swap path (`gapless_playback_engine.py:216-227`) takes `update_lock` then `_audio_lock` and never takes `_position_lock`, so the documented guarantee ("`_position_lock` ... gapless-transition consistency", `integration_reporting.py:~118`; `integration_manager.py:99-100` "ensures position + sample_rate are read atomically during gapless transitions") does not hold: the three reads are three separate `_audio_lock` acquisitions and the swap can land between any two.
  Probe `/tmp/audit/concurrency/probe_d1_torn.py` (writer thread alternating a 100 s and a 10 s buffer with the same swap+`seek` under `_audio_lock`/`defer_notifications` as `advance_with_prebuffer`, reader calling `integration.get_playback_info()`): 11 of 1,262,480 snapshots violated the invariant, e.g. `{'position_seconds': 100.0, 'duration_seconds': 10.0, 'current_file': 'long'}`.
- **Impact**: Callbacks/`get_playback_info()` can report a position beyond the duration (the project's `position <= duration` invariant) or pair one track's `current_file` with another's duration. No audio corruption; `_get_position_seconds()` alone is internally consistent because it clamps to the snapshot's own duration. Consumer reach is currently small (no production code registers an engine callback or calls `get_playback_info`, #5233/#5708), so impact is limited to engine consumers and tests, hence MEDIUM rather than HIGH.
- **Siblings**: `integration_manager.py:215-219` and `integration_reporting.py:55-60` are the two copies of the same read sequence; no other `get_duration()` + position composition exists (`grep -n "get_duration()" auralis/player/integration_*.py`).
- **Suggested Fix**: Take one `_audio_lock` section covering all three reads (order `_position_lock -> _audio_lock -> PlaybackController._lock` is already the canonical one), reading `current_file`, `file_manager.get_state_snapshot()` and `playback.get_position_snapshot()` together and deriving `duration_seconds` from that same snapshot instead of calling `get_duration()` again. Factor it into one helper (`_snapshot_position_and_duration()`) used by both sites so the two copies cannot drift. Correct the `_position_lock` comments, which claim an exclusion against the swap that does not exist.

### CONC-D5-03: Live-setting reissue / reconnect resume appends a "restart at playhead" stream onto a buffer that already holds lookahead
- **Severity**: MEDIUM
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/websocket/useOutgoingChannel.ts:71-118`; `auralis-web/frontend/src/hooks/websocket/websocketConnectionCore.ts:55-72`; `auralis-web/frontend/src/hooks/enhancement/useEnhancedStreamStart.ts:92-107`; `auralis-web/frontend/src/hooks/enhancement/audioChunkIngest.ts:88-90`; `auralis-web/frontend/src/hooks/enhancement/useStreamMessageHandlers.ts:121-135`
- **Status**: NEW
- **Trigger Conditions**: User changes intensity/preset/enhancement toggle mid-track (`useEnhancementCommands.ts` → `reissueActiveStreamAs`), a chunk-failure `recovery_position` auto-resume, or a WS reconnect, while the PCM buffer holds <= ~2 content chunks (<= ~20 s) of lookahead (early in a track, slow chunk production, after a pause).
- **Evidence**:
  ```ts
  // useOutgoingChannel.ts:91  start_position = engine PLAYBACK position (not the buffered end)
  const resumePos = startPositionOverride ?? connState.resumeGetters[type]?.() ?? 0;
  // useEnhancedStreamStart.ts:92-107  is_seek (start_position>0) => buffer preserved, nothing trimmed
  // audioChunkIngest.ts:88-90  duplicate detection is a heuristic: incoming < last - 1
  return lastChunkIndex >= 0 && incomingChunkIndex < lastChunkIndex - 1;
  ```
  The new stream starts exactly at the playhead P while the ring still holds `[P .. E]`. If the first new chunk index is within one of the last received index, `isOutOfSequence` is false, nothing is reset, and `[P ..]` is appended after `[P .. E]`: the span `E-P` (up to ~2 chunk intervals) plays twice and the setting change is audible only after the old-settings lookahead drains. If the gap is larger the buffer is reset mid-playback instead (rebuffer to the 8 s high-water mark, `setCurrentTime(0)` flicker).
- **Impact**: Repeated audio segment (or an avoidable rebuffer) on every live preset/intensity change, toggle and reconnect resume; old-settings audio keeps playing for the lookahead duration.
- **Siblings**: three producers of a resume stream — `reissueActiveStreamAs` (`useOutgoingChannel.ts:71`), `replayQueueAndResume` (`websocketConnectionCore.ts:55`), `handleStreamError` auto-resume (`useStreamMessageHandlers.ts:257`).
- **Suggested Fix**: Make the client authoritative about the join point: compute the resume position as the end of buffered audio (`base + (samplesPlayed + bufferedSamples)/sr`) so the new stream continues seamlessly, or reset the buffer deterministically when the start answers a reissue (flag set by the sender, cleared in the `audio_stream_start` wrapper) instead of relying on the chunk-index heuristic.
- **Cross-audit overlap**: INT-F1-3 in `AUDIT_INTEGRATION_2026-10-22.md` is the same finding.

### CONC-D5-04: `AudioPlaybackEngine.startPlayback()` is not cancel-safe — pause is lost and a stop/dispose during its awaits leaks a live worklet + feed interval
- **Severity**: MEDIUM
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts:112-153`; `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts:193-201`; `auralis-web/frontend/src/services/audio/WorkletOutput.ts:57-67,162-192`
- **Status**: NEW
- **Trigger Conditions**: Playback is requested once the buffer crosses the start threshold; `startPlayback()` then awaits `audioContext.resume()` (if suspended) and `bufferScheduler.ensureReady()` → `AudioWorklet.addModule()` (a new `BufferScheduler`, hence a new `addModule`, is built for every stream start). During those awaits the user pauses, or a rapid skip/seek/stream-error runs `stopPlayback()`/`dispose()`. Duplicate calls from subsequent chunks are possible too because `isPlaying()` turns true only after the awaits.
- **Evidence**:
  ```ts
  // AudioPlaybackEngine.ts:112-153
  async startPlayback() {
    if (this.positionTracker.isPlaying()) return;           // false for the whole await window
    ...await this.audioContext.resume(); ...
    await this.bufferScheduler.ensureReady();                // addModule()
    this.bufferScheduler.createProcessor();                  // no re-check that we were stopped/disposed meanwhile
    this.positionTracker.setSamplesPlayed(0);
    this.positionTracker.setState('playing');
  }
  // pausePlayback(): `if (!this.positionTracker.isPlaying()) return;`  → no-op during the window
  ```
- **Impact**: (a) A pause pressed in that window only sets `pauseHoldRef`/`isPaused` (`usePlaybackTransport.ts:85-90`); the engine then flips to `playing`, `onStateChanged('playing')` forces `isPaused=false` and audio plays against the user's pause. (b) If `dispose()` (`cleanupStreaming`, next stream start) ran during the await, the continuation still creates an `AudioWorkletNode` and starts `setInterval(…, 50 ms)` on the orphaned engine; nothing holds a reference to stop it, so one node + timer leaks per occurrence (its buffer is disposed so each tick short-circuits on the low-water check). (c) After `stopPlayback()` for a seek the engine is marked `playing` with an empty ring.
- **Siblings**: `rg "\.startPlayback\(" src --glob '!*test*'` → `useAudioStreamingCore.ts:199` (sole caller, fire-and-forget).
- **Suggested Fix**: Add a monotonically increasing `generation` to the engine, bumped by `stopPlayback()`/`dispose()`/`pausePlayback()`; capture it before the awaits and bail (calling `disconnectProcessor()`) if it changed. Use a `starting` flag so concurrent `startPlayback()` calls coalesce and `pausePlayback()` during `starting` records a "start paused" intent.
- **Cross-audit overlap**: HK-09 in `AUDIT_FRONTEND_2026-10-22.md` is the same finding.

### CONC-D5-05: `useQueueFetch` applies the engine's stale `current_index` raw — every extra `usePlaybackQueue()` mount can rewind the queue pointer
- **Severity**: MEDIUM
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueFetch.ts:39-66`; `auralis-web/frontend/src/hooks/player/usePlaybackQueue.ts:150-174`; `auralis-web/frontend/src/components/playlist/usePlaylistContextActions.ts:28`; `auralis-web/frontend/src/components/layouts/Sidebar/SidebarContent.tsx:62`; `auralis-web/frontend/src/components/core/AppSidebar.tsx:101-124`
- **Status**: NEW (sibling of #5601's reconciliation, which covers `queue_changed`/`player_state`/`track_changed` but not this REST path; backend root cause is open #5460/#5726)
- **Trigger Conditions**: After one or more local Next/Previous/auto-advance skips (these move only Redux and send `play_*`; the engine queue pointer is not advanced — `ws_handlers/playback_commands.py:286-310`), a second `usePlaybackQueue()` instance mounts. `PlaylistList` (via `usePlaylistContextActions`) calls it, and the Sidebar is remounted whenever `AppSidebar` flips between the desktop `Sidebar` and `MobileSidebarDrawer` (window resized across the mobile breakpoint). It also causes a duplicate GET + duplicate `queue_changed` subscription at every app start (QueuePanel + PlaylistList).
- **Evidence**:
  ```ts
  // useQueueFetch.ts:51-54 — no reconcileQueueIndex(), unlike useQueueSubscription.ts:63-75 and playerStateSnapshot.ts:115-123
  dispatch(reduxSetQueue((response.tracks ?? []).map(mapTrackInfoToTrack)));
  dispatch(reduxSetCurrentIndex(response.current_index ?? 0));
  ```
  `GET /api/player/queue` returns the engine's `queue_obj.current_index` (`services/queue_service.py:60-80`).
- **Impact**: The queue highlight jumps back to the pre-skip track while audio continues, and `handleNext`/`useAutoAdvance` (which compute `currentQueueIndex + 1`, `PlaybackSessionContext.tsx:115-140`) then advance from the wrong slot, replaying an already-played track. The fetch also overwrites any in-flight optimistic queue state (no ordering vs. `queue_changed`).
- **Siblings**: `rg "reduxSetCurrentIndex\(|setCurrentIndex\(" src --glob '!*test*'` → `useQueueFetch.ts:52` (unreconciled), `useQueueSubscription.ts` (reconciled), `playerStateSnapshot.ts:115-123` (reconciled), `usePlayerStateSync.ts` `track_changed` (deliberately engine-authoritative), `useQueueMutations.ts` (optimistic/rollback).
- **Suggested Fix**: Route the fetch result through `reconcileQueueIndex(tracks, current_index, playingTrackId)` using the store's current player track; hoist `useQueueFetch`/`useQueueSubscription` into a single app-level provider (or make `usePlaylistContextActions` use `useQueueMutations` only) so there is exactly one subscription and one initial fetch.
- **Cross-audit overlap**: RDX-03 in `AUDIT_FRONTEND_2026-10-22.md` is the same finding.

### CONC-D5-06: After the client tears a stream down (DESYNC, watchdog, error) the backend keeps streaming into an unbounded `pendingChunksRef`
- **Severity**: MEDIUM
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts:155-176`; `auralis-web/frontend/src/hooks/enhancement/useStreamMessageHandlers.ts:106-117,229-262`; `auralis-web/frontend/src/hooks/websocket/socketFrameParser.ts:34-60`
- **Status**: NEW
- **Trigger Conditions**: Any client-side `cleanupStreaming()` while the backend task is still sending: the synthetic `DESYNC` `audio_stream_error` (client-detected, backend unaware), the 45 s start watchdog, or a non-recoverable `audio_stream_error` carrying no `recovery_position`. The frontend never sends `stop`/`pause` over the WebSocket (`rg "type: '(stop|pause)'" src` → none), so the backend is never told.
- **Evidence**:
  ```ts
  // cleanupStreaming(): pcmBufferRef/metadata = null, streamEpochRef.current = null (useAudioStreamingCore.ts:155-176)
  // classifyChunk: currentEpoch == null => no epoch rejection; initialized == false => 'not-initialized'
  pendingChunksRef.current.push(message);               // useStreamMessageHandlers.ts:115 — no cap, no epoch/track check
  ```
  Flow control is never engaged either (`ingestChunk` is not reached), so the backend sends the remainder of the track at full speed.
- **Impact**: Up to the remaining track's PCM (float32; ~21 MB per stereo 44.1 kHz minute, ~100 MB for a 5 min track) accumulates as `ArrayBuffer`s in the ref until the next play command clears it (`useEnhancedPlayCommand.ts:81`).
- **Siblings**: `rg "pendingChunksRef" src --glob '!*test*'` → `useStreamMessageHandlers.ts:115` (push), `useEnhancedStreamStart.ts:100,214-221` (drain/clear), `useEnhancedSeek.ts:79`, `useEnhancedPlayCommand.ts:81`, `useAudioStreamingCore.ts:164`.
- **Suggested Fix**: On client-initiated teardown send a WS `stop` (and clear `connState.lastStreamCommand`), and cap `pendingChunksRef` (drop frames once a byte/length bound is exceeded, or when their epoch differs from the last adopted start's epoch).
- **Cross-audit overlap**: Related to INT-F1-4 in `AUDIT_INTEGRATION_2026-10-22.md` (a skipped chunk is treated as a fatal client-side teardown), which is one of this finding's triggers.

## LOW Findings

### CONC-D1-02: Track-changing engine operations are serialised by four unrelated locks, so a library load / set-queue / navigation can interleave
- **Severity**: LOW (latent MEDIUM: currently masked by #5563 and #5708, see below)
- **Dimension**: Player Thread Safety
- **Location**: `auralis-web/backend/routers/player_playback.py:117-120` (no lock); `auralis-web/backend/services/navigation_service.py:156-157,217-218` (`_sequencer.lock`); `auralis-web/backend/services/queue_set_mixin.py:111-154` and `queue_edit_mixin.py:~200-215` (`_set_queue_engine_lock`); `auralis-web/backend/services/playback_service.py:169-177` (`transition_lock`); engine side `auralis/player/integration_library.py:46-62`, `auralis/player/player_file_loading_mixin.py:51-91,109-150`
- **Status**: NEW
- **Trigger Conditions**: Two of {`POST /api/player/load`, `set_queue()`, `remove_track_from_queue()` (reloads the new current track), next/previous} in flight on different `to_thread` workers at once. `load_track_from_library` has a long tail after the buffer swap (`record_play` DB write, `_auto_select_reference` with `find_similar` and a full reference decode), which widens the window to hundreds of ms. Example: load(A) swaps A and starts its tail; load(B) runs to completion; load(A) then schedules its fingerprint load last.
- **Evidence**: Each operation is individually atomic at the buffer level (`AudioFileManager.load_file` swap + `on_loaded` reset, `advance_with_prebuffer` swap), but the *composite* engine state is several independently written pieces: `file_manager.audio_data/current_file`, `queue.current_index`, `integration._current_track(_dict)` (`set_current_track` runs after the swap, `integration_library.py:~48`), the fingerprint generation (`_schedule_fingerprint_load` runs after `load_track_from_library` returns, `player_file_loading_mixin.py:~139-146`) and the processor's reference. Nothing orders the last-writer of one piece against the last-writer of another. The four locks are separate objects: `playback_event_sequencer.transition_lock`, `navigation_service._sequencer.lock`, `QueueServiceBase._set_queue_engine_lock`, and none for the `/load` route.
- **Impact**: Audio buffer, queue pointer, `current_track` and the applied 25D fingerprint can end up describing different tracks (e.g. audio B + fingerprint A), until the next load. No buffer corruption. Today the reach is small: queue entries built by the backend carry only `filepath`, so engine `next_track()`/`previous_track()` return False early (#5563), and the engine's audio is not consumed by the streaming path (#5708). If #5563 is fixed, the next/previous x load/set_queue interleavings become live and this should be re-rated MEDIUM.
- **Siblings**: `queue_edit_mixin.py` `remove_track_from_queue` -> `load_file` (outside `transition_lock` and `_sequencer.lock`); `queue_set_mixin.py:147-154` `load_file` + `play` (outside `transition_lock`, so a concurrent `pause()` between them is overridden by the later `play()`).
- **Suggested Fix**: One engine-level transport/track-change mutex (a threading `RLock` owned by `AudioPlayer`, or a single process-wide asyncio lock shared by `PlaybackService`, `NavigationService`, `QueueService` track-changing paths and the `/load` route) held across the whole load/advance + `set_current_track` + fingerprint schedule, never across a broadcast. Alternatively, compare a monotonically increasing load generation after the slow tail and skip `set_current_track`/`_schedule_fingerprint_load` for a superseded load.

### CONC-D1-03: Queue-change listener's re-arm is lost when it lands while the prebuffer worker is on its way out
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/gapless_prebuffer.py:150-159` (final re-peek and store); `:228-249` (`on_queue_changed`); `:38-60` (`start_prebuffering` no-op while a worker is alive)
- **Status**: NEW (narrow residual of the closed #5583)
- **Trigger Conditions**: A queue edit that changes the next track lands between the worker's last `peek_next_track()` (line 150) and the worker thread actually ending (after line 160), e.g. a user "remove next track" at the instant a prebuffer completes. Window is microseconds to low milliseconds (the `update_lock` acquire at `:154` can wait on an `advance_with_prebuffer` swap).
- **Evidence**:
  ```python
  latest = self.queue.peek_next_track()                 # :150  edit has not happened yet
  if not self._entries_match(latest, next_track): ...   # :151
  with self.update_lock:                                # :154  stores the now-stale buffer
      self.next_track_buffer = audio_data ...
  # listener on another thread: on_queue_changed() -> _prebuffer_matches() is False (buffer not stored yet) or clears it,
  # then start_prebuffering() -> "Prebuffer thread already running" -> returns; the worker then exits.
  ```
  Neither the worker nor the listener re-checks after the other has acted, so no worker is left running and no buffer matches the new next track.
- **Impact**: The next transition takes the blocking-decode fallback (audible gap of the decode time) instead of the gapless path. `advance_with_prebuffer` still rejects the stale buffer (#2303 match rule), so no wrong audio is played.
- **Siblings**: none (single worker design).
- **Suggested Fix**: After storing, have the worker re-peek once more under the same loop (continue if the stored `next_track_info` no longer matches), or let `start_prebuffering()` set a `_rearm_requested` flag when it declines because a worker is alive and have the worker loop honour it before exiting.

### CONC-D1-04: Locks held across O(n) work on the real-time path; engine queue mutators run synchronously on the event loop
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/realtime/processor.py:64-75` + `auralis/player/realtime/level_matcher.py:44-56`; `auralis/player/queue_loading.py:84-100` and `:119-134`; event-loop callers `auralis-web/backend/services/queue_order_mixin.py:59,156,199`, `queue_edit_mixin.py:190,202,209,220,258`
- **Status**: NEW
- **Trigger Conditions**: (a) `RealtimeProcessor.set_reference_audio()` while playing (the explicit `load_reference()` path, `player_file_loading_mixin.py:~100`; the auto-select path fires only while STOPPED). (b) `load_playlist()`/`set_queue()` of a large queue while the audio thread reaches end-of-track. (c) Any of the listed REST queue edits.
- **Evidence**:
  - (a) `RealtimeProcessor.lock` is held across `RealtimeLevelMatcher.set_reference_audio`, which does `np.sqrt(np.mean(reference ** 2))` over the whole decoded reference while also holding the matcher `_lock`. `process_chunk` needs both locks at the start and end of every chunk (`processor.py:137,188`, `level_matcher.py:86`), so the audio thread stalls for the whole computation. Probe `/tmp/audit/concurrency/probe_d1_ref.py`: a 4-minute stereo float32 reference took 10.4 ms and the concurrent `process_chunk` was blocked for 10.0 ms (budget 23.2 ms); it scales linearly with reference length and doubles for float64, so a 10+ minute reference exceeds the chunk budget.
  - (b) `with self.queue._lock:` wraps `track.to_dict()` for every playlist track (`queue_loading.py:~84-90`); `get_audio_chunk` calls `queue.has_next_track()` while holding `_audio_lock` at end-of-track (`player_streaming_mixin.py:106`), so a long `to_dict()` loop stalls the audio callback and everything else that needs `_audio_lock`. CPU only (detached instances, no SQL), so it is bounded.
  - (c) `QueueManager` mutators run directly on the event loop and then call the change listener (`queue_controller.py:56-63`) which takes `update_lock` and may start a thread; each hold is microseconds to milliseconds, so this is a hygiene issue of the same class as the closed #3916/#4772 (which fixed other call sites).
- **Impact**: (a) possible single-chunk dropout during an explicit reference change on long references; (b) brief `_audio_lock` stall at end-of-track during a large queue replace; (c) sub-millisecond event-loop blocking. No state corruption.
- **Siblings**: `AutoMasterProcessor.set_fingerprint` already computes `_generate_adaptive_parameters` before taking its lock (`auto_master.py:~303-307`), which is the pattern to copy.
- **Suggested Fix**: (a) compute the RMS before taking either lock in `RealtimeProcessor.set_reference_audio` and only publish `reference_rms/enabled` under `_lock`. (b) build the list of `track.to_dict()` results before taking `queue._lock` and replace the contents under it. (c) wrap the queue-shape calls in `asyncio.to_thread` like the add/insert paths already do.

### CONC-D1-05: The `defer_notifications()` contract is enforced only by caller discipline; a violation deadlocks immediately
- **Severity**: LOW
- **Dimension**: Player Thread Safety
- **Location**: `auralis/player/playback_controller.py:71-130` (deferral); contract holders `auralis/player/gapless_playback_engine.py:222-227` (`on_swap` under `update_lock` + `_audio_lock`), `auralis/player/audio_file_manager.py:68-72` (`on_loaded` under `_audio_lock`); lock edge `auralis/player/integration_manager.py:210-215` (`_position_lock -> _audio_lock`)
- **Status**: NEW (hardening; all current callers comply)
- **Trigger Conditions**: Any future/third-party caller that invokes `advance_with_prebuffer(on_swap=...)` or `AudioFileManager.load_file(on_loaded=...)` with a callback that reaches a `PlaybackController` mutator (`seek`, `load_and_stop`, `play`...) outside a `playback.defer_notifications()` scope while another thread is inside `get_playback_info()`/`_on_playback_state_change`.
- **Evidence**: While building probe_d1_torn.py the first version called `p.playback.seek()` under `fm._audio_lock` without the deferral scope and hung forever against `get_playback_info()`: `_on_playback_state_change` runs on the seeking thread holding `_audio_lock`, needs `_position_lock`, which the reader holds while waiting for `_audio_lock`. `advance_with_prebuffer`'s own docstring (`gapless_playback_engine.py:~100-106`) does not state that the *caller* must have opened a deferral scope, and `AudioFileManager.load_file`'s docstring says only "must not fire notifications".
- **Impact**: Total deadlock of the player (every `_audio_lock` taker) if the contract is broken. No current trigger.
- **Siblings**: the two `on_*` hooks above are the only lock-held callbacks.
- **Suggested Fix**: Make the hooks self-protecting: have `advance_with_prebuffer` and `AudioFileManager.load_file` open `self.playback.defer_notifications()` themselves (or pass the controller in), or give `PlaybackController` an assertion (`_audio_lock` held by this thread and not deferring) in `_notify_callbacks` under test. At minimum document the requirement in `advance_with_prebuffer`'s docstring.

### CONC-D2-02: `get_wav_chunk_path` mutates LevelManager / `_dsp_state_advanced` without `_processor_lock`
- **Severity**: LOW
- **Dimension**: Audio Processing
- **Location**: `auralis-web/backend/core/chunk_streaming.py:211-250`, `auralis-web/backend/core/chunk_render.py:154,205`
- **Status**: NEW
- **Trigger Conditions**: Two threads call different entry points on the SAME `ChunkedAudioProcessor`: one in `process_chunk(locked=True)` (holds `_processor_lock`) and one in `get_wav_chunk_path` (holds only `_sync_cache_lock`). Today the only production caller of `get_wav_chunk_path` is the pre-warm, which owns its processor exclusively, so this is latent.
- **Evidence**:
  ```python
  # chunk_streaming.py
  211  with processor._sync_cache_lock:                 # not _processor_lock
  230      processor._dsp_state_advanced = False
  237      extracted_chunk = processor._process_chunk_core(chunk_index, fast_start=False)   # -> _level_manager.smooth_transition (deque appends)
  # chunk_render.py:205  note_cached_chunk_level takes _processor_lock (re-entered from inside _sync_cache_lock)
  ```
  `LevelManager` (two `deque`s plus read-modify-write of the last entries) documents no locking of its own; `_processor_lock` is its only guard.
- **Impact**: If a future caller mixes the two entry points, `rms_history`/`gain_history` can interleave out of order and `_dsp_state_advanced` can be cleared by the wrong call (defeating the #5274 invalidation). The same function already takes `_processor_lock` for cache-hit recording, so the two paths are inconsistent today.
- **Siblings**: `process_chunk(locked=False)` (direct sync call, tests only) has the same gap by design.
- **Suggested Fix**: Take `_processor_lock` inside `get_wav_chunk_path` around the `_process_chunk_core` section (lock order `_sync_cache_lock` -> `_processor_lock` is already the established order), or document `_sync_cache_lock` as the only guard and drop the mixed use.

### CONC-D2-03: `process_adaptive`/`process_reference` cache by `id(config)` and never reset the shared processor between unrelated inputs
- **Severity**: LOW
- **Dimension**: Audio Processing
- **Location**: `auralis/core/hybrid_processor_singleton.py:54` (key), `:63-69` (config deep-copied), `:105-129`
- **Status**: NEW
- **Trigger Conditions**: Library/API callers of `auralis.process_adaptive(audio, config)` / `process_reference(...)` (exported from `auralis/__init__.py:27`; no production caller inside the app). (a) Call once with config object A, let A be garbage collected, then call with a new config B that CPython allocates at the same address: the cache returns the processor built from A's snapshot. (b) Any two unrelated inputs through the same default key share one processor whose limiter `current_gain` and EQ smoothing carry over (no `reset_*` between calls).
- **Evidence**:
  ```python
  54  cache_key = f"{id(config)}_{mode}" if config is not None else f"default_{mode}"
  69  processor = HybridProcessor(owned_config)        # deepcopy: original config may be freed while the entry stays cached
  ```
  Reproduced locally (read-only script `/tmp/audit/concurrency/d2_idreuse.py`): after `del a`, a new `UnifiedConfig(internal_sample_rate=96000)` received the same `id`, and `_get_or_create_processor(b, "adaptive")` returned the original processor with `config.internal_sample_rate == 44100` (`same obj True`, trial 6 of 30).
- **Impact**: Wrong sample rate / EQ frequency mapping / LUFS scale for the second caller (silently, no error), and first-call limiter/EQ state leaking into an unrelated master. Concurrent callers are serialised by the processor lock, so there is no tearing; the defect is cache identity and state carry-over.
- **Siblings**: `ProcessorFactory`/`ProcessorPool` key on content hashes (`hash_config`, `cache_key`), not `id()`; no other `id(...)` keyed cache in `auralis/core` (grep).
- **Suggested Fix**: Key on a content hash of `config.to_dict()` (as `processor_cache_key.hash_config` does) and call `reset_dynamics/reset_psychoacoustic_eq/reset_limiter` under the processor lock before each call in these two helpers, or document that they are single-stream-only.

### CONC-D2-04: Pooled HybridProcessor keeps the previous job's `last_*` profile, so a silent/short job reports stale telemetry
- **Severity**: LOW
- **Dimension**: Audio Processing
- **Location**: `auralis-web/backend/core/job_execution.py:62-76` (`_reset_processor_state`), `auralis/core/hybrid_stage_dispatch.py:79-92` (early returns), `auralis-web/backend/core/job_finalize.py:51,67`
- **Status**: NEW
- **Trigger Conditions**: Mastering job N-1 runs on a pooled processor; job N (same pool key) is empty, <1024 samples, or all-zero. `validate_and_normalize_input` returns before `_process_adaptive_mode`, so `last_content_profile` and `continuous_mode.last_fingerprint` still describe job N-1; `_reset_processor_state` resets only dynamics, EQ and limiter.
- **Evidence**: Reproduced with the Rust fingerprint stubbed (`/tmp/audit/concurrency/d2_stale.py`): job 1 fingerprint `lufs=-9.0`; after processing 3 s of silence, `continuous_mode.last_fingerprint['lufs']` and `last_content_profile['fingerprint']['lufs']` both still `-9.0` (same object). `finalize_job` then writes `job.result_data["lufs"] = -9.0` for the silent file.
- **Impact**: Wrong (previous job's) loudness in the job result for degenerate inputs; telemetry only, no audio effect.
- **Siblings**: `last_coordinates`/`last_parameters` are likewise not cleared when the fingerprint comes back empty (`continuous_mode.py` returns None before setting them). The streaming profile map (`chunk_content_profile.py`) is a documented known limitation (#4601).
- **Suggested Fix**: Add a `reset_run_state()` on HybridProcessor (under `_process_lock`) that clears `last_content_profile` and the `continuous_mode.last_*` fields and call it from `_reset_processor_state`; or have `finalize_job` ignore profiles older than the job's start.

### CONC-D2-05: `ProcessorPool.return_to_cache` LRU invariant breaks when two same-key jobs overlap
- **Severity**: LOW
- **Dimension**: Audio Processing
- **Location**: `auralis-web/backend/core/processor_pool.py:117-147`
- **Status**: NEW
- **Trigger Conditions**: `max_concurrent_jobs=2` and both jobs use the same `(mode, config)` key while the cache lacks that key: each constructs its own instance. When the second returns, `self.processors[key] = processor` re-assigns an existing key, which keeps its OLD dict position.
- **Evidence**:
  ```python
  117  replaced = self.processors.get(key)
  120  self.processors[key] = processor     # existing key keeps its insertion position
  145  evicted = self.processors.pop(cache_keys[0], None)   # eviction trusts "insertion order == last-return order"
  ```
  The comment at :133-142 states the key is always absent on return because `get_or_create` pops; that does not hold when two leases were built independently.
- **Impact**: The most recently returned processor can be the first eviction candidate (an avoidable 200-500 ms rebuild later). No correctness or audio impact.
- **Siblings**: `ProcessorFactory` uses `OrderedDict.move_to_end` and is unaffected.
- **Suggested Fix**: `self.processors.pop(key, None)` before the assignment so it re-appends (keep the replaced-instance close logic), or switch to `OrderedDict` + `move_to_end`.

### CONC-D3-04: Cancelling a stream mid-chunk-send orphans the `send_pcm_chunk` producer task
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/stream_protocol.py:195-283`
- **Status**: NEW
- **Trigger Conditions**: A seek / stop / skip / disconnect cancels the stream task while `send_pcm_chunk` is inside `asyncio.gather(_producer(), _consumer())` and the bounded send queue (`_SEND_QUEUE_MAXSIZE`=4) is full, i.e. the producer is suspended in `queue.put` and the consumer is behind.
- **Evidence**:
  ```python
  254:        finally:
  255:            await queue.put(None)  # sentinel          <- blocks forever: queue full, consumer already cancelled
  282:    await asyncio.gather(_producer(), _consumer())
  ```
  `gather(..., return_exceptions=False)` completes the outer future on the first cancelled child, so the stream task finishes while the producer survives, parked on a future nobody can resolve. Reproduction (scratchpad `t2.py/t3.py`, real `send_pcm_chunk`, 10 s stereo chunk, 50 ms fake sends, cancel at 0.5 s): the outer task is done immediately, `asyncio.all_tasks()` still shows `_producer()` "cancelling", and it survives `gc.collect()`.
- **Impact**: Each occurrence strands a task holding `pcm_flat` for the whole chunk plus up to four queued 300 KB frames (about 3.5-5 MB for 44.1 kHz stereo, more for high sample rates) until the loop closes, and logs "Task was destroyed but it is pending" at shutdown. Exposure is limited to cancels that land inside a send window, so it is rare, but it grows with every seek/skip under a slow-draining client.
- **Siblings**: none with this exact pattern (`stream_normal_chunks.py` and `stream_enhanced_chunks.py` delegate to this function).
- **Suggested Fix**: In `_producer`'s `finally`, use `put_nowait` inside `suppress(QueueFull)` (or drop the sentinel and let the consumer exit on `abort_event`), and wrap the gather in `try/finally` that cancels and awaits both children (`asyncio.TaskGroup` gives this for free).
- **Cross-audit overlap**: BE-D11-04 in `AUDIT_BACKEND_2026-10-22.md` is the same finding.

### CONC-D3-05: `JobWorker.stop()` cannot cancel jobs that are waiting for a concurrency slot, so they start during shutdown
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/job_worker.py:66-92,115-170,205-213`
- **Status**: NEW
- **Trigger Conditions**: More than `max_concurrent_jobs` (2) jobs are queued/running at shutdown (or at a library reset that calls `stop_worker`).
- **Evidence**:
  ```python
  212:                spawn_background_task(self._run_job(job), name=f"_run_job:{job.job_id}")   # dispatcher drains the queue into tasks immediately
  79:            await self._concurrency_semaphore.acquire()
  85:                self._tasks[job.job_id] = task        # registered only AFTER the slot is won
  126:        for job_id, task in list(self._tasks.items()):   # stop() cancels only registered (running) tasks
  ```
  `stop()` drains `job_queue`, but jobs already turned into `_run_job` tasks are not in `_tasks` and not in the queue. When stop() cancels the two running jobs they release their slots, the waiting `_run_job` tasks acquire them, see `QUEUED` status and run `process_job` (`job_lifecycle.py:414-426`).
- **Impact**: A new full-track decode/DSP job starts mid-shutdown; its first `to_thread` call then runs against the already-closed processor pool, executors and DB (`persist` after `_teardown_library_database`), yielding spurious FAILED jobs, warnings and an orphaned thread. No corruption.
- **Siblings**: the same untracked-`_run_job` shape means the queue bound (`max_queue_size`=20) is effectively ineffective as back-pressure, since the dispatcher empties the queue into unbounded tasks.
- **Suggested Fix**: Register the task in `_tasks` before awaiting the semaphore (or keep a separate waiting set), have `_run_job` check `self._stopping` after acquiring, and let `stop()` cancel/mark CANCELLED both sets.
- **Cross-audit overlap**: BE-D4-03 in `AUDIT_BACKEND_2026-10-22.md` is the same finding.

### CONC-D3-06: A cancelled job's DSP thread keeps one of the two job-pool workers, and queue wait counts against the 300 s timeout
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/job_execution.py:164-205`, `core/executors.py:96-99,204-206`
- **Status**: NEW
- **Trigger Conditions**: Cancel (or time out) two long mastering jobs in quick succession, then submit a third. `JOB_POOL_SIZE` (2) equals `max_concurrent_jobs`, but a cancelled job releases its semaphore slot immediately while its `processor.process` thread keeps running (no cooperative cancel on the DSP call).
- **Evidence**:
  ```python
  202:        result = await asyncio.wait_for(
  203:            run_in_job_executor(processor.process, audio),     # wait_for timer starts at submission, not at thread start
  204:            timeout=timeout,
  ```
- **Impact**: The third job's DSP waits in the pool queue behind the abandoned threads (remaining runtime of full-track mastering, tens of seconds up to minutes); that wait is charged to its `DEFAULT_PROCESSING_TIMEOUT`, so a healthy job can fail with "timed out" and poison/discard its processor. Delay and spurious failures only.
- **Siblings**: none.
- **Suggested Fix**: Start the timeout when the callable actually begins (wrap the callable to set a "started" event), or hold the concurrency permit until the worker thread returns (release in a done-callback on the executor future), or add a cooperative cancel check inside `HybridProcessor.process`.
- **Cross-audit overlap**: BE-D4-08 in `AUDIT_BACKEND_2026-10-22.md` is the same finding.

### CONC-D3-07: Cache-hit decode has no recovery if the on-disk chunk is deleted after the lookup (prune/clear TOCTOU drops the chunk)
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/chunk_streaming.py:75-93` (`process_chunk` hit branch), `core/chunk_disk_prune.py:87-130`, `core/encoding/wav_encoder.py:279-320`, `core/cache_cleanup.py:51-62`
- **Status**: NEW
- **Trigger Conditions**: A stream (or its look-ahead) takes a cache hit on chunk N (`lookup_cached` passes `exists()` + `is_wav_complete`) and, before `load_audio(str(cached_path))` finishes reading it, the reaper unlinks it (oldest-mtime-first prune when the dir exceeds 512 MB, which preferentially removes the old files a re-listen is hitting) or `clear_all_caches`/`DELETE /cache/track/{id}` sweeps the track.
- **Evidence**:
  ```python
  89:        audio, _ = load_audio(str(cached_path))      # FileNotFoundError here is not caught as a miss
  # chunk_disk_prune.py docstring: "Deleting a file another stream still references is safe ... treats a missing file as a cache miss"
  # - only true for deletions that happen BEFORE the lookup
  ```
  The error flows to `pump_chunks`' generic `except Exception`, which sends "Failed to process audio chunk N", records it in `failed_chunks` and skips it.
- **Impact**: One chunk (10 s) of audible gap plus an `errored` stream end instead of a transparent re-render. The window is tens of milliseconds per hit, so it is rare in practice; a user-triggered cache clear during playback is the most plausible trigger.
- **Siblings**: `core/chunk_streaming.py:222-224` (`get_wav_chunk_path` returns a path that may vanish before the caller reads it).
- **Suggested Fix**: In the hit branch catch `FileNotFoundError`/`AudioLoadError`, pop the in-memory entry and fall through to the miss/render path.
- **Cross-audit overlap**: Related to BE-D10-01 in `AUDIT_BACKEND_2026-10-22.md`, where the hit path runs the pruner itself before returning. This finding covers a deletion by a different thread or by a cache clear.

### CONC-D3-08: Proactive buffer and the live stream write the same durable chunk key with different, race-dependent render provenance
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/proactive_buffer.py:29-61`; `core/stream_chunk_ops.py:59,78`; `core/chunk_streaming.py:76-93`
- **Status**: NEW (sibling of #5311's cross-consumer seam concern; #5311 isolated the processors but not the shared on-disk key)
- **Trigger Conditions**: Every enhanced stream start spawns `buffer_presets_for_track` for chunks 0-2 alongside the live pump. Whichever writer reaches a chunk first fixes the durable bytes.
- **Evidence**:
  ```python
  # proactive_buffer.py
  35:        chunk_path = processor._get_chunk_path(chunk_idx)
  37:        if chunk_path.exists():
  39:            return True            # skips process_chunk, so the #4669 cache-hit LevelManager recording never happens
  44:        ... await processor.process_chunk_safe(chunk_idx)        # fast_start=False
  # stream_chunk_ops.py:59   fast_start: bool = chunk_index == 0     # live stream renders chunk 0 with fast_start=True
  ```
  If the live stream already wrote chunk 0, the buffer skips it without recording its level, then renders chunk 1 with an empty `LevelManager` history (baseline, no smoothing) on a cold processor; if the buffer wins chunk 0 it renders it with `fast_start=False`.
- **Impact**: The durable chunk 0/1 bytes (served on every later play of the track) differ depending on a startup race: possible unsmoothed level step at the 0/1 seam, or different per-chunk analysis on chunk 0. Small, but it is persisted and non-deterministic.
- **Siblings**: `streamlined_worker._process_chunk` (cache worker, out-of-order renders into the same key); `routers/enhancement_prewarm.py` (CONC-D3-02).
- **Suggested Fix**: Replace the `.exists()` shortcut with `process_chunk_safe` (which already handles hits and records levels), render chunk 0 with the same `fast_start` as the live path, or write background renders under a distinct key / only when absent after a short "live stream owns this chunk" check.
- **Cross-audit overlap**: Related to BE-D3-02 / BE-D11-03 in `AUDIT_BACKEND_2026-10-22.md` (the same durable-key provenance class).

### CONC-D3-09: Two live streams of the same track share one pooled `HybridProcessor` (reconnect / second window)
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/processor_factory.py:340-404`, `core/processor_cache_key.py` (key has no stream identity), `core/processor_registry.py:413-451`
- **Status**: NEW (the open concern behind #5311 for live-vs-live; #5311's fix only separated background consumers)
- **Trigger Conditions**: The old WebSocket of a reconnecting/resuming client is still half-open (heartbeat eviction takes up to about 40 s) and still rendering, or a second tab opens, while the new connection's `play_enhanced` for the same `(track, preset, config, targets)` starts.
- **Evidence**: `ProcessorFactory.get_or_create` returns the identical cached instance for both streams; `HybridProcessor._process_lock` serialises calls but not their order, so EQ envelope / limiter gain-reduction state is fed in interleaved chunk order. Per-stream `ChunkedAudioProcessor` objects (own `LevelManager`) both write the same durable keys.
- **Impact**: Seam artifacts baked into the durable cache for the overlap period. Desktop single-client scope and the usual "old stream already finished before reconnect" ordering make it unlikely.
- **Siblings**: n/a.
- **Suggested Fix**: Lease the processor per stream (pop-on-acquire like `ProcessorPool`), or key live-stream processors on `ws_id`/epoch.

### CONC-D3-10: Stop/teardown helpers swallow the caller's own cancellation (the pattern #5083/#4809 fixed elsewhere)
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/core/state_manager.py:236-243`; `core/job_worker.py:172-177`; `core/streamlined_lifecycle.py:36-45`; `services/library_auto_scanner.py:92-98`
- **Status**: NEW
- **Trigger Conditions**: The task running the helper is cancelled while it is parked in `await <cancelled worker task>` (request handler cancelled on client disconnect during `set_playing(False)`; lifespan shutdown cancelled a second time during `stop_worker()` / `streamlined_worker.stop()`).
- **Evidence**:
  ```python
  240:            try:
  241:                await task
  242:            except asyncio.CancelledError:
  243:                pass            # cannot tell "worker finished cancelling" from "I am being cancelled"
  ```
  `_position_update_loop` and the workers catch their own `CancelledError` and return, so for the inner task the `except` is only ever taken by a cancellation aimed at the caller.
- **Impact**: The caller's cancellation is lost: a cancelled HTTP request continues into the broadcast/persist steps after `set_playing(False)`; a second shutdown cancel does not interrupt the remaining teardown. Cosmetic in practice.
- **Siblings**: `ws_handlers/context.py:await_cancelled_task` and `stream_chunk_ops._caller_is_being_cancelled` already implement the correct `current_task().cancelling()` test; reuse it.
- **Suggested Fix**: Use the same `Task.cancelling()` discrimination (or `await asyncio.wait({task})`, which never raises the inner task's cancellation).

### CONC-D3-11: The process-wide transport lock is held across `asyncio.to_thread` on the shared I/O pool, and WS transport handlers wait on it inside the receive loop
- **Severity**: LOW
- **Dimension**: Backend Streaming
- **Location**: `auralis-web/backend/services/playback_service.py:169-182,218-226,257-266,305-324` (`async with self._playback_lock: ... await asyncio.to_thread(self.audio_player.<op>)`); `ws_handlers/playback_control.py:28,44,88`; `routers/system.py:154-157`
- **Status**: NEW (documented design from #3734/#4751; reported as the "lock held across an await" checklist item)
- **Trigger Conditions**: A REST `play/pause/stop/seek` holds `transition_lock` while its `to_thread` call is queued behind a saturated 8-worker I/O pool (library scan, many repository calls, CONC-D3-03 analyses).
- **Evidence**: `handle_pause/resume/stop` do `async with playback_event_sequencer.transition_lock` directly in the connection's sequential receive loop (`routers/system.py:113-157`), so one waiting handler stalls `buffer_full/buffer_ready`, pong handling and every later message on that socket.
- **Impact**: Bounded stall of flow-control and heartbeat handling (heartbeat eviction after about 40 s of no pong) under I/O-pool saturation. The ordering guarantee the lock provides is intentional.
- **Siblings**: none.
- **Suggested Fix**: Move the engine call for the REST path onto a tiny dedicated transport executor (or run the WS handlers' lock wait in a task) so transport latency cannot depend on the DB-sized pool.

### CONC-D4-04: `_interruptible_sleep` clears the trigger event, losing wake-ups that arrived during the scan
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis-web/backend/services/library_auto_scanner.py:137-153,258-269` (producers: `scanner_watchdog.py:62-72`, `routers/settings_sync.py:26-28`)
- **Status**: NEW
- **Trigger Conditions**: A watchdog event (user copies files into a watched folder) or `reload_config()` (user changes folders / toggles auto-scan) lands while `_run_cycle` is between `get_settings` and the sleep - in practice, any time during `_do_scan`, which can last minutes on a large library.
- **Evidence**:
  ```python
  153  await self._do_scan(scan_folders)
  154  await self._interruptible_sleep(scan_interval)
  264  self._trigger_event.clear()                   # drops anything set since the cycle began
  265  await asyncio.wait_for(self._trigger_event.wait(), timeout=float(seconds))
  ```
- **Impact**: The scan that just finished used the old settings/old file listing, the trigger is erased, and the loop sleeps the full `scan_interval` (default 3600 s). New files or a changed scan-folder list are picked up up to an hour late (the periodic poll is the only backstop, hence LOW). `_stop_event`/`stop()` are unaffected because `stop()` also cancels the task.
- **Siblings**: The 30 s crash back-off at `:134` uses the same helper.
- **Suggested Fix**: Clear the event at the *start* of `_run_cycle` (before reading settings) and have `_interruptible_sleep` skip the wait if it is already set, so a trigger raised any time after the settings snapshot survives into the next sleep.
- **Cross-audit overlap**: INT-F4-6 in `AUDIT_INTEGRATION_2026-10-22.md` is the same finding.

### CONC-D4-05: On-demand fingerprint queue keeps `processing`/queued state across stop()/start()
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis-web/backend/analysis/fingerprint_queue.py:167-179,186-240`
- **Status**: NEW
- **Trigger Conditions**: `stop()` cancels the worker task while it awaits `get_or_generate` for track X (a library reset during an on-demand fingerprint, which is how `ondemand_fingerprint_queue` is stopped/started by the shared helper).
- **Evidence**:
  ```python
  196  self._state.processing = track_id
  ...
  237  except asyncio.CancelledError:
  239      break                      # processing never reset, queue/queued_set never cleared
  # enqueue(): 'if track_id == self._state.processing: return False'
  ```
  Reproduced (`/tmp/audit/concurrency/d4_odq_stuck.py`): after stop()/start(), `processing == 5` and `enqueue(5)` returns False.
- **Impact**: Track X can never be re-enqueued for the rest of the process lifetime ("currently being fingerprinted" is reported forever), and track ids queued before the reset stay queued. Because a fresh (non-AUTOINCREMENT) library reuses ids after reset, this can pin an id that now belongs to a different track. Small blast radius, but compounds CONC-D4-02.
- **Siblings**: none (the batch queue keeps no per-track in-flight id).
- **Suggested Fix**: In the `CancelledError` branch (or `stop()`) clear `processing`, and clear `queue`/`queued_set` under `_state_lock` when stopping for a reset.

### CONC-D4-06: Library reset ignores an incomplete `stop()` of the fingerprint workers
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis-web/backend/config/background_workers.py:73-86`; `auralis/services/fingerprint_queue.py:173-203`; `auralis-web/backend/routers/library.py:138-148`
- **Status**: NEW
- **Trigger Conditions**: A fingerprint worker is inside `_extract_bounded` (`fingerprint_worker.py:141-190`, up to `AURALIS_FINGERPRINT_TRACK_TIMEOUT`=600 s) when the user confirms a reset. `FingerprintExtractionQueue.stop(timeout=30)` returns False ("Worker shutdown timeout exceeded"), but `stop_background_workers` discards the return value and records the key as stopped, so `reset_library` runs while the worker (and its daemon extract thread) are still alive.
- **Evidence**:
  ```python
  # background_workers.py
  await _maybe_await(worker.stop(**WORKER_STOP_KWARGS.get(key, {})))   # result ignored
  stopped.append(key)
  ```
- **Impact**: When the extraction finishes it upserts a fingerprint for the old `track_id`. With foreign keys on the insert normally fails (logged, claim released); but on a database created by `create_all` (no AUTOINCREMENT), ids restart at 1 after reset, so if a rescan has already re-created that id the old file's fingerprint is stored on a different track. Narrow (needs >30 s remaining extraction plus a fast rescan), but the result is a silently wrong 25D fingerprint driving mastering targets/similarity for that track.
- **Siblings**: the auto-scanner's scan thread can outlive `stop_scanner`'s 5 s grace, but the exclusive-access guard (slot held -> reset refused) covers it.
- **Suggested Fix**: Have `stop_background_workers` surface a False/timeout (report or 409/retry before deleting), and/or make the worker re-validate that `track.filepath` still matches the row before the upsert.

### CONC-D4-07: Fourth engine on library.db with a literal timeout and no busy_timeout/FK pragmas
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/migrations/normalize_existing_artists.py:71-77`
- **Status**: NEW
- **Trigger Conditions**: The one-off CLI (`python -m auralis.library.migrations.normalize_existing_artists`) runs while the backend is writing to library.db. It takes `migration_lock`, which the running app does not hold during normal operation.
- **Evidence**:
  ```python
  engine = create_engine(f'sqlite:///{db_path}', pool_pre_ping=True,
                         connect_args={'timeout': 15, 'check_same_thread': False})
  ```
  No connect listener: `busy_timeout` stays at the driver's 15 s (not 60 s) and `foreign_keys` is off while it merges artist rows and rewrites `track_artist`/`albums`.
- **Impact**: Exactly the drift #5799 removed from the other three engines: this is the shortest wait on the file, so it is the one to raise "database is locked" under backend load, mid-merge. Because it runs in a transaction the merge rolls back cleanly; FK-off merging can still orphan references if it fails halfway.
- **Siblings**: `scripts/development/*.py` create ad-hoc engines but are dev scripts.
- **Suggested Fix**: Build the engine with `create_migration_engine(db_path)` (migration_engine.py) instead of a local `create_engine`.

### CONC-D4-08: Overlapping (non-identical) scan directories bypass the per-directory dedup while `max_concurrent_scans` defaults to 4
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/scan_coordinator.py:84-99`; `auralis/library/scanner/scan_stages.py:52-55`; default at `auralis/library/models/settings.py:59`
- **Status**: NEW
- **Trigger Conditions**: Auto-scan is walking `/music` and the user starts a manual scan of `/music/jazz` (or the same folder through a symlink/alternate spelling). Reservation compares exact `normpath(abspath())` strings only, and up to 4 scans are allowed.
- **Evidence**:
  ```python
  clashing = [p for p in paths if p in self._active_scan_paths]   # exact match only
  ```
- **Impact**: Two scanners process the same files concurrently. Both `get_by_path` miss, both `add()`; the loser hits the `filepath_key` UNIQUE index and is recorded as `failed: "Database insert failed"` for a file that was actually added, polluting `scan_complete.failures`; album creation shares the open race of #5595. No corruption.
- **Siblings**: none.
- **Suggested Fix**: Reserve on `os.path.realpath` and reject when a requested path is a prefix of (or prefixed by) an active one.
- **Cross-audit overlap**: E7-07 in `AUDIT_ENGINE_2026-10-22.md` is the same finding.

### CONC-D4-09: `LibraryAutoScanner.stop()` races an in-flight `_sync_watchdog` and can leak an Observer
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis-web/backend/services/library_auto_scanner.py:86-99`; `auralis-web/backend/services/scanner_watchdog.py:79-110`
- **Status**: NEW
- **Trigger Conditions**: `stop()` (shutdown or reset) arrives while `_run_cycle` is suspended at `await asyncio.to_thread(self._stop_watchdog)` inside `_sync_watchdog` (a settings change just altered the folder list).
- **Evidence**: `stop()` runs its own `to_thread(_stop_watchdog)` then cancels the task; if the `_run` task resumes first it executes `self._observer = Observer(); ... .start()` (`scanner_watchdog.py:102-105`) after `stop()`'s watchdog teardown has already finished, and the subsequent `task.cancel()` does not stop the new observer.
- **Impact**: An Observer thread survives stop; after a reset the next `start()` (once CONC-D4-03 is fixed) creates a second observer, and the leaked one calls `loop.call_soon_threadsafe` on a closed loop at exit (exception in the watchdog thread). Very narrow window.
- **Siblings**: none.
- **Suggested Fix**: Cancel the task first, then run `_stop_watchdog`; or check `self._stop_event.is_set()` before creating the new Observer.

### CONC-D4-10: Opening `LibraryDatabase` in a second process deletes the running app's live fingerprint claims
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/database.py:124,229-258`; second process `auralis/cli/fetch_artwork.py:158`
- **Status**: NEW
- **Trigger Conditions**: The backend is mid-fingerprinting (placeholders with `lufs=-100.0` / `fingerprint_version=0` rows are the in-flight claims) and the user runs `fetch_artwork` (or any other `LibraryDatabase(...)` consumer) against the same file.
- **Evidence**: `_cleanup_incomplete_fingerprints()` -> `fingerprint_stats.cleanup_incomplete_fingerprints()` -> `release_claims(session)` with `track_id=None`, i.e. every claim in the table, intended as "crash recovery".
- **Impact**: Live claims vanish, workers in the backend re-claim and re-extract tracks other workers are still processing (duplicate CPU/memory work; final upserts are idempotent). No corruption.
- **Siblings**: none.
- **Suggested Fix**: Only run the sweep from the long-lived backend entry point (or gate it on a stale-claim age), not from every `LibraryDatabase.__init__`.

### CONC-D4-11: `FileDiscovery` / `BatchProcessor` stop flags are plain bools (sibling of #3728)
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner/file_discovery.py:34-38,72,123`; `auralis/library/scanner/batch_processor.py:41-45,64`
- **Status**: NEW
- **Trigger Conditions**: `LibraryScanner.stop_scan()` (loop thread) sets them while the scan thread reads them; under free-threaded CPython (`-X gil=0`, the reason #3728 moved `LibraryScanner.should_stop` to an Event) the cross-thread publish is not synchronized.
- **Evidence**: `self.should_stop = False` / `= True` bare attributes, read in the walk and batch loops.
- **Impact**: Stop latency only; hardening for no-GIL builds. Not reachable on the default build.
- **Siblings**: all three stop-flag holders are signalled together in `scanner.py:113-117`.
- **Suggested Fix**: Hand both components the scanner's `threading.Event` (or give each its own Event).

### CONC-D5-07: `audio_stream_end` / `audio_stream_error` carry no epoch, and their handlers act on the live stream unconditionally
- **Severity**: LOW
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useStreamMessageHandlers.ts:186-262`; `auralis-web/frontend/src/hooks/enhancement/useStreamSubscriptions.ts:112-114`; `auralis-web/frontend/src/types/ws/streaming.ts:76-100,150-175`
- **Status**: NEW
- **Trigger Conditions**: A skip/seek/live reissue lands while the old stream is delivering a failing chunk. The old stream's `audio_stream_error` (or an `errored` `audio_stream_end`) is emitted before cancellation, so it arrives after the client has sent the new command but before the new `audio_stream_start` (the backend serializes cancel-then-start, so it cannot arrive after the new start).
- **Evidence**:
  ```ts
  // handleStreamError: only the Redux dispatch is trackId-guarded; the teardown + reissue are not
  dispatch(setStreamingError({ streamType, error: errorMsg, trackId: message.data.track_id }));
  cleanupStreaming();                                              // :238 disposes the live engine/buffer
  ... wsContext.reissueActiveStreamAs(reissueType, {}, recoveryPosition);   // :257
  ```
  `reissueActiveStreamAs` builds the command from `lastStreamCommand` (already the NEW track after a skip) but with the OLD stream's `recovery_position`.
- **Impact**: A coinciding old-stream failure can restart the new track/seek at the old stream's recovery offset, overriding a user seek or skip target. Also any stale stream frame clears the 45 s start watchdog (`useStreamSubscriptions.ts:112-114`), so a hung worker for the new stream goes undetected. Narrow window, self-correcting on the next user action.
- **Siblings**: `rg "stream_epoch" src --glob '!*test*'` → carried only on `audio_stream_start` and `audio_chunk_meta`.
- **Suggested Fix**: Stamp `stream_epoch` on `audio_stream_end`/`audio_stream_error` in `stream_messages.py` and gate `handleStreamEnd/Error` (and watchdog clearing) on `epoch == streamEpochRef.current`; in `handleStreamError` also require `message.data.track_id === lastStreamCommand.data.track_id` before auto-resuming.
- **Cross-audit overlap**: RDX-05 in `AUDIT_FRONTEND_2026-10-22.md` covers the handler side effects. INT-F1-1 notes the missing epoch on `audio_stream_end`/`audio_stream_error`.

### CONC-D5-08: `player_state` watermark reset is deferred to a React effect, so the initial snapshot after a backend restart can be dropped as "stale"
- **Severity**: LOW
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:69-88,98-106`; `auralis-web/backend/ws_handlers/connection.py:140-160`
- **Status**: NEW
- **Trigger Conditions**: Backend process restarted (its `seq` counter restarts near 0), WS reconnects, and the server's immediate on-connect `player_state` push is dispatched before React commits the `connectionStatus === 'connected'` render that resets `lastSeenSeqRef` (the `setConnectionStatus` in the socket `open` handler is scheduled, not synchronous).
- **Evidence**:
  ```ts
  useEffect(() => { if (connectionStatus === 'connected') { lastSeenSeqRef.current = 0; ... } }, [connectionStatus]);
  ...
  if (state.seq < lastSeenSeqRef.current) return;   // old watermark (pre-restart, large) still in force
  ```
- **Impact**: The only guaranteed re-sync frame after reconnect (queue, volume, track, shuffle/repeat) is discarded; Redux stays stale until the next state-change broadcast.
- **Siblings**: the same ref is shared by `position_changed` (self-heals within 1 s) and the transport/volume/track_changed watermarks (`usePlayerStateSync.ts:76-88`).
- **Suggested Fix**: Reset the watermarks synchronously from the socket `open` handler (a `connState.connectionEpoch` counter bumped in `attachHandlers`, compared inside the subscribe callbacks) instead of via a render-phase effect.

### CONC-D5-09: Scan-status reconnect resync can resurrect `isScanning` after `scan_complete`
- **Severity**: LOW
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/library/useScanProgress.ts:162-198`
- **Status**: NEW
- **Trigger Conditions**: WS reconnects while a scan is finishing: `GET /api/library/scan/status` is evaluated server-side (is_scanning=true) just before `scan_complete` is broadcast and the HTTP response is processed after the WS frame.
- **Evidence**: `.then(data => setSharedState(prev => data.is_scanning ? (prev.isScanning ? prev : { ...prev, isScanning: true }) : ...))` — no sequencing against the WS terminal frames; `scan_complete` already reset the state.
- **Impact**: Scan UI stuck on "Scanning…" until the next scan/reconnect.
- **Siblings**: none (single shared store).
- **Suggested Fix**: Keep a `scanEpoch` that `handleScanMessage` bumps on every lifecycle frame; discard a resync response whose epoch predates the latest frame.

### CONC-D5-10: Fingerprint "complete" auto-clear timer is not cancelled by `resetFingerprint`
- **Severity**: LOW
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useFingerprintStatus.ts:72-77,99-111`
- **Status**: NEW
- **Trigger Conditions**: Track A's fingerprint completes (2 s clear timer armed), the user skips to B within 2 s, B's `fingerprint_progress: analyzing` arrives.
- **Evidence**: `resetFingerprint` sets idle but never calls `cancelFingerprintTimeout()`; A's timer later runs `setFingerprintStatus('idle'); setFingerprintMessage(null)` over B's live status.
- **Impact**: Cosmetic — B's analysis indicator disappears early.
- **Siblings**: `cancelFingerprintTimeout` is called only on disconnect/unmount/next `complete`.
- **Suggested Fix**: Call `cancelFingerprintTimeout()` inside `resetFingerprint`.

### CONC-D5-11: `lastStreamCommand` is effectively never cleared, so a reconnect restarts a finished/failed stream
- **Severity**: LOW
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/websocket/useOutgoingChannel.ts:36-60`; `auralis-web/frontend/src/hooks/websocket/websocketConnectionCore.ts:42-72`
- **Status**: NEW
- **Trigger Conditions**: Playback ends (last queue track finishes, repeat off) or a stream fails fatally, then the WS reconnects (backend restart, sleep/wake).
- **Evidence**: Clearing exists only for outgoing `stop`/`pause` messages, but the frontend never sends either (`rg "type: '(stop|pause)'" src` → none; `pausePlayback`/`stopPlayback` are client-only). `replayQueueAndResume` therefore always re-issues `{...lastStreamCommand, start_position: resumeGetter()}`, and the getter returns engine time (see CONC-D5-02 for its inaccuracy).
- **Impact**: The tail of the finished track (or the failing stream) is replayed / re-requested after a reconnect; the `stop`/`pause` clearing branches are dead code.
- **Siblings**: `useOutgoingChannel.ts:36-60` (send), `websocketConnectionCore.ts:49-56` (replay).
- **Suggested Fix**: Clear `connState.lastStreamCommand` on `audio_stream_end` with `reason: 'completed'` once the engine has drained, and on non-recoverable `audio_stream_error`.
- **Cross-audit overlap**: HK-04 in `AUDIT_FRONTEND_2026-10-22.md` and INT-F3-4 in `AUDIT_INTEGRATION_2026-10-22.md` are the same finding.

### CONC-D5-12: `useOptimisticUpdate` has no supersession guard (exported, currently unused)
- **Severity**: LOW
- **Dimension**: Frontend State
- **Location**: `auralis-web/frontend/src/hooks/shared/useOptimisticUpdate.ts:35-69`
- **Status**: NEW (latent)
- **Trigger Conditions**: Two overlapping `execute()` calls: the second snapshots `previousState` from the first's optimistic value; responses resolve out of order or the first fails after the second started.
- **Evidence**: `const previousState = stateRef.current;` per call; `setState(result)` / `setState(previousState)` with no request id, unlike `useEnhancementCommands`/`queueMutationGuards`.
- **Impact**: A stale response can overwrite a newer result, or a rollback can restore a never-committed optimistic value. No production caller today (`rg useOptimisticUpdate src --glob '!*test*'` → only the `hooks/shared/index.ts` re-export).
- **Siblings**: none.
- **Suggested Fix**: Add a monotonic request id (as in `useEnhancementCommands.ts`) or delete the unused hook.

## Verified Safe (by dimension)

### Player Thread Safety

- **Lock-order docstrings still hold at every call site.**
  - `gapless_prebuffer.py:5-7` ("`update_lock` always outer; `_thread_lock` never held while waiting on `update_lock` or joining"): `_thread_lock` is taken at `gapless_prebuffer.py:51` (Thread construction/start only) and in `gapless_playback_engine.py:279-280` (handle snapshot only; the 5 s join at `:285-288` is outside it). `update_lock` is only nested outside `_audio_lock` (`gapless_playback_engine.py:216-232`), never inside it: nothing that holds `_audio_lock` touches the gapless engine or edits the queue.
  - `integration_reporting.py:5-8` ("`_position_lock` -> `_audio_lock`/`PlaybackController._lock`; `_stats_lock` only after `_position_lock` released"): `get_playback_info` (`integration_reporting.py:41-98`) reads `queue.get_queue_info()` before taking `_position_lock` and `processor.get_processing_info()` and the `_stats_lock` block after releasing it; `record_track_completion` (`:93-103`) releases `_stats_lock` before notifying. No path takes `_audio_lock` and then `_position_lock`.
- **Mixin lock ownership.** Every `QueueManager` mixin method takes the base `_lock` for its whole read-modify-write: `components/queue_navigation.py:44,59,96,116,142,165,181`; `components/queue_shuffle.py:40,74`; `_invalidate_shuffle_snapshot_unlocked` is only called from inside `with self._lock` in `queue_manager.py`. `QueueController`'s borrowed `self.queue._lock` is used consistently (`queue_locked_state.py`, `queue_loading.py:84,119`). `PrebufferMixin` accessors (`has_prebuffered_track`, `get_prebuffered_track`, `invalidate_prebuffer`) take `update_lock`; `_prebuffer_matches` is only called with it held (`gapless_playback_engine.py:140-148`, `gapless_prebuffer.py:241`). `PlaybackReportingMixin` and `LibraryLoadingMixin` touch base state only through locked accessors.
- **Callbacks are never invoked with a lock held.** `PlaybackController._dispatch_callbacks` copies the list under the lock and calls outside it (`playback_controller.py:132-140`); `IntegrationManager._notify_callbacks` same pattern (`integration_manager.py:193-202`); `record_track_completion` is called after the `defer_notifications()` scope closes (`player_queue_navigation_mixin.py:107-116`), so the #4328/#4495 fixes are intact. The two callbacks that DO run under `_audio_lock` (`on_swap` at `gapless_playback_engine.py:226-227`, `on_loaded` at `audio_file_manager.py:71-72`) only call `PlaybackController` mutators, whose notifications are queued by the thread-local `defer_notifications()` (`playback_controller.py:71-116`) and flushed after the lock is released. Every call site that mutates `PlaybackController` while holding `_audio_lock` is inside a `defer_notifications()` scope (`enhanced_audio_player.py:211,248`, `player_queue_navigation_mixin.py:107`, `player_file_loading_mixin.py:~72,~139`). Empirically confirmed that this deferral is load-bearing: a `seek()` issued under `_audio_lock` WITHOUT it deadlocks against `get_playback_info()` immediately (see CONC-D1-05).
- **Seek vs gapless transition.** `AudioPlayer.seek()` and the `position` setter hold `_audio_lock` across the max-samples snapshot and `playback.seek()` (`enhanced_audio_player.py:211-218,248-250`); the gapless swap + `seek(0)` happen in one `_audio_lock` section (`gapless_playback_engine.py:222-227`). A seek therefore either clamps against the old track before the swap (then is reset to 0) or against the new track after it. `get_audio_chunk` does `read_and_advance_position` + slice under the same lock (`player_streaming_mixin.py:82-94`), clamped to `total_samples` (#5114), so the *stored* position never exceeds the buffer length.
- **Audio buffer sharing.** `get_audio_chunk` returns a `.copy()` of the slice taken under `_audio_lock` (`audio_file_manager.py:133-142`); `RealtimeProcessor.process_chunk` operates on `audio.copy()` and every stage returns a new array (`realtime/processor.py:141-170`, `level_matcher.py:112-118`, `auto_master.py:_process_locked`). The prebuffered ndarray is handed to `file_manager` by reference but the engine nulls its own references in the same `update_lock` section (`gapless_playback_engine.py:229-232`) and nothing in `auralis/` or `auralis-web/backend` mutates `audio_data`/`reference_data` in place (grep: only `file_manager` and the properties mixin touch them). `reference_data` shared with the level matcher is read-only (`np.mean(reference ** 2)`).
- **play/pause/stop races.** All `PlaybackController` transitions are single-`_lock` sections with the snapshot-then-notify-outside pattern. The `_stop_requested`/`_pause_requested` flag ordering (#3669, #5240, #5588) is sound for the interleavings reachable in production: REST `play/pause/stop/seek` and the WS `pause/resume/stop` handlers all serialise on `playback_event_sequencer.transition_lock` (`playback_service.py:169,218,257,305`, `ws_handlers/playback_control.py:28,44,88`), so `stop()` cannot interleave inside `play()`'s start-then-clear window.
- **Auto-advance spawn.** Test-and-spawn and compare-and-clear of `_auto_advancing`/`_advance_generation` both run under `_audio_lock` (`player_streaming_mixin.py:106-117,183-185`); `_advance_thread` is written and read (cleanup) under the same lock (`:116`, `enhanced_audio_player.py:283-284`).
- **Prebuffer lifecycle.** `_shutdown` re-check inside `_thread_lock` (`gapless_prebuffer.py:51-60`), join outside the lock, inner daemon loader polled every 200 ms (`gapless_prebuffer.py:~110-134`), store/clear under `update_lock`. Queue-change listener is called after `QueueManager._lock` is released at every `_notify_changed()` site (`queue_controller.py`, `queue_loading.py`), so there is no `queue._lock -> update_lock` edge.
- **Realtime package.** `RealtimeProcessor.lock` always nests outside `AutoMaster._lock`/`LevelMatcher._lock` (`set_fingerprint`, `get_processing_info`, `reset_all_effects`) and `process_chunk` never nests them (lock released between snapshot, DSP and the perf-record section, `processor.py:137-139,188-191`), so there is no inversion. `reset()`/`get_stats()` on the matcher are under its `_lock` (#4340/#4551). `_fingerprint_lock` correctly serialises generation check + `set_fingerprint` (`fingerprint_loader_mixin.py:96-101`).
- **Position <= duration for the stored position and for `_get_position_seconds()` alone.** `min(position_seconds, duration)` at `integration_reporting.py:127`; see CONC-D1-01 for the composed snapshot, which is NOT safe.
- **Backend drivers.** All engine calls from `PlaybackService`/`NavigationService`/`QueueService` go through `asyncio.to_thread` except the queue-shape calls listed in CONC-D1-04; the asyncio locks (`transition_lock`, `_sequencer.lock`, `_set_queue_engine_lock`) are never held across a WS broadcast (#4581, #5324, #4825); the loop-rebinding lock properties handle test loops.

### Audio Processing

- **One HybridProcessor shared by concurrent chunk workers is serialised**: `process()` takes the per-instance RLock (`auralis/core/hybrid_processor.py:162`), as do `set_fixed_mastering_targets` (:185), `set_dynamics_mode`/`reset_dynamics`/`reset_psychoacoustic_eq`/`reset_limiter` (:299-325) and `set_processing_mode` (:351). Every instance attribute `ContinuousMode.process()` writes (`last_fingerprint`, `last_coordinates`, `last_parameters`, `last_journal`, `last_side_effects`, quality-gate counter/evaluators, lazy `_reference_cloud`/`_distance_stats`) is written inside that lock. I found no write to a HybridProcessor/ContinuousMode/EQProcessor/limiter attribute from outside it (grep of `.brick_wall_limiter|.psychoacoustic_eq|.continuous_mode|.content_analyzer|.eq_processor|.current_targets` across backend/player/services returns only `audio_processing_pipeline.py`).
- **`use_fingerprint_analysis` toggle (set/process/restore)** is atomic under `processor._process_lock` in both branches (`auralis-web/backend/core/audio_processing_pipeline.py:197-215`, `:220-236`); #4354 fix intact.
- **Mastering targets are not mutated by workers**: `ProcessorFactory.get_or_create` hands each HybridProcessor its own `deepcopy` (`processor_factory.py:193`, `:198`); `convert_targets_to_parameters` (`core/processing/fixed_target_params.py:29`) only reads and builds new dicts; `get_targets_hash` only serialises; the dict cached in `MasteringTargetService` and held as `ChunkedAudioProcessor.mastering_targets` is only passed as `targets=` (used for `is not None` + hash) and to `invalidate`. Grep for in-place writes to `*targets[...]`/`current_targets[...]`/`fingerprint[...]` in `auralis/` and `backend/` finds only the offline `target_generator.py`, which works on fresh dicts (`.copy()` at :150).
- **MasteringTargetService** cache: every read/insert/`clear_cache` is under `self._lock` (`mastering_target_service.py:143,159,168,182,199`); singleton creation is double-checked under `_service_lock`.
- **Copy-before-modify in the live path**: `ContinuousMode.process` copies first (`continuous_mode.py:223`); `amplify` copies (`auralis/dsp/basic.py:59`); `apply_clip_blend_compression`, `soft_clip`, `BrickWallLimiter.process` (`audio * gain_curve`), `LevelManager.smooth_transition` (new array via multiply), `adjust_stereo_width_multiband`, the WOLA EQ (`eq_processor.py:216` copies each frame; output buffer is fresh) all return new arrays. `intensity` blending creates a new array (`audio_processing_pipeline.py` blend branch). `save_audio` clips into a new array.
- **Offline path** (`simple_mastering.py`, `mastering_*.py`, `stages/`): `master_file` is serialised per instance by `_process_lock` (`simple_mastering.py:137`), per-file state (`_notches`, `_source_lufs`, `_song_peak_db`) is reset at the start of `prepare_file` (`mastering_prepare.py:140-143`); `process_chunk` copies its input (`mastering_process_chunk.py:84`); DSP helpers (`core/dsp/*`, `stages/*`) are stateless static functions with no module-level mutable state; chunks only interact through the crossfade tail, committed after a successful write (`mastering_chunk_loop.py`, `mastering_chunk_assembly.py`). `auto_master.py` is sequential. Sample count is checked per chunk (`mastering_chunk_loop.py` #3700) and the short-render guard covers the total.
- **PsychoacousticEQ** smoothing/history state is under `_state_lock` (`psychoacoustic_eq.py:201,218`, `spectrum_gains.py:184`); BrickWallLimiter `current_gain` is only touched via `HybridProcessor` (locked). `LoudnessMeter` is built fresh per `calculate_loudness_units` call (`dsp/utils/adaptive.py:152`), so K-weighting filter state is never shared.
- **Optimizer / profiler** (`auralis/optimization/performance_optimizer.py`, `profiling/performance_profiler.py`): singleton is a double-checked global under a lock; `time_function` updates `timings`/`counters` under `self.lock` (:43) and the report is read under it (:56). `apply_module_optimizations` runs at import (import lock) behind an `_optimized` flag. Note the wrapped `AdaptiveMode.process` is not on the live ContinuousMode path, so the counters are effectively idle.
- **Rust PyO3 boundary** (`vendor/auralis-dsp/src/py_bindings.rs`): `compute_fingerprint_wrapper` copies the numpy buffer to an owned `Vec<f32>` (:75) while holding the GIL, then runs the compute inside `py.detach` (:98) with `catch_unwind`; the only Python-object work (`PyDict` build) is after re-attaching. `process_chunks_wrapper` does the same with `to_owned()` (:188) + `detach` (:212). No `static`/`lazy_static`/`OnceLock`/`thread_local`/`Mutex`/`unsafe` anywhere in `vendor/auralis-dsp/src/*.rs`; the only parallelism is rayon `par_iter` in `chroma.rs:126` (no Python callbacks, so no GIL/rayon deadlock). Concurrent calls cannot corrupt shared state. `Cargo.toml` has no `panic = "abort"`, so `catch_unwind` is effective.
- **Python fingerprint glue** (`audio_fingerprint_analyzer.py`, `rust_fingerprint.py`): stateless; `close()` is a no-op.
- **`HybridProcessor.close()` called on eviction while another thread may be inside `process()`**: safe, no component implements a real `close()` (grep `def close` in `core/`, `dsp/`, `analysis/fingerprint`), so eviction cannot tear down live state.
- **Lock order**: `ChunkedAudioProcessor._processor_lock` -> (factory `_lock` released before DSP) -> `HybridProcessor._process_lock` -> `PsychoacousticEQ._state_lock`; `_sync_cache_lock` -> `_processor_lock` (via `note_cached_chunk_level`). I found no path that takes them in the opposite order, and factory `clear_cache`/`invalidate` call only the no-op `close()` under `_lock`.
- **ProcessorFactory / ProcessorPool lifecycle**: construction happens outside the cache lock with a re-check afterwards (`processor_factory.py:187-245`, `processor_pool.py:81-106`); the loser of a construct race is closed; pool leases are pop-on-acquire; poisoned (timed-out) processors are discarded (`processor_pool.py:cleanup`), and streaming timeouts invalidate the factory entry (`stream_chunk_ops.py` #5335).
- **Module-level state**: `_chunk_levels` (lock at `chunk_render.py:73`), `_last_content_profiles` (lock at `chunk_content_profile.py:26`), `hybrid_processor_singleton._processor_cache` (lock :38), `converted_wavs` registry (refcounts under its lock; `build_lock` outside) are all guarded. `GENRE_CURVES` is frozen. No filter-coefficient caches or `lru_cache` on arrays exist in `auralis/core` or `auralis/dsp`.
- **HybridProcessor failure mid-chain**: EQ `current_gains` and limiter `current_gain` are advanced as they run, with no rollback if a later stage raises. That is the same "advanced-state" model #5274 already accepts; the chunk is skipped/gapped by the caller, and state converges within a few frames. Not reported as a finding.
- **Sample-count preservation**: backend path enforces `len(processed) == len(audio)` unconditionally (`audio_processing_pipeline.py` #4371/#4795), `HybridProcessor` raises on limiter shape mismatch, offline loop has per-chunk and total checks. I found no path where chunked and whole-file lengths diverge.

### Backend Streaming

- **Stream semaphore release on every exit** — `stream_enhanced.py:72-82,135-303` (permit taken before the `try`, released in `finally` at :285 before any awaited cleanup), `stream_seek.py:362-372,557-569` (release first in `finally`), `stream_normal.py:71-81,265-277`. `Semaphore.acquire()` under `wait_for` is cancel-safe in CPython 3.14 (a cancel after the waiter was woken re-credits the permit), so the pre-`try` acquire cannot leak a permit.
- **Per-connection vs shared controller state** — a fresh `AudioStreamController` is built per stream task (`routers/system_streams.py:69,157,213`); the only shared members are the module semaphore (`audio_stream_controller.py:122`) and the epoch counter (:97, atomic under the GIL, loop-only). `_stream_type_var/_frame_seq_var/_track_id_var/_stream_epoch_var` are ContextVars seeded per task (`stream_messages.py:81-91`); `stream_chunk_ops.py` / `stream_fingerprint.py` read only instance-constant attributes, so two streams on one controller class cannot cross-contaminate.
- **Post-seek stale delivery** — old task is cancelled and awaited before the new one is created (`playback_commands.py:_cancel_prior_task` + `await_cancelled_task`, `context.py:199-220`), `chunk_cancel_event.set()` precedes `task.cancel()` (`playback_commands.py:107-116`, `playback_control.py:101-105`, `connection.py:250-253`), and frames that were already queued carry the old `stream_epoch` (`audio_stream_controller.py:82-101`, `stream_protocol.py:206-241`). Look-ahead task is drained in `pump_chunks`' own `finally` (`stream_enhanced_chunks.py:273-277`) and `drain_cancelled_task` re-raises caller cancellation (`stream_chunk_ops.py:474-528`, #5083).
- **Stale cache write by a cancelled render** — `_raise_if_cancelled` before DSP and again before the durable write (`chunk_streaming.py:101,128,229,240`). Residual window is the encode/fsync duration only (tens of ms); not reported.
- **Cache-write atomicity** — `atomic_io._stage_and_replace` (`encoding/atomic_io.py:359-389`: unique `mkstemp` sibling, fsync, `os.replace`, cleanup on `BaseException`), used by `wav_encoder.encode_and_save` (`wav_encoder.py:179-189`) and `chunk_batch`; thumbnails use a per-writer temp + `Path.replace` (`routers/artwork_thumbnails.py:79-125`). Concurrent writers to one key are last-writer-wins, never torn. `is_wav_complete` gates every hit (`chunk_path_cache.py:289-297`, `chunk_cache_manager.py:468`).
- **Shared disk reaper** — throttle counter and both locks are class attributes addressed via `type(self)` (`chunk_disk_prune.py:46-72`); there is no `ChunkCacheManager` subclass, and an instance attribute cannot shadow them. (Hardening note: a future subclass would fork the counter because `cls._write_counter += 1` assigns on the subclass.)
- **Executor discipline** — every per-chunk DSP/read goes through `run_in_stream_executor` (`chunk_streaming.py:187-189`, `stream_normal_chunks.py:169,189`, `routers/enhancement_prewarm.py:149`); job DSP uses `run_in_job_executor` (`job_execution.py:164-205`); the remaining `asyncio.to_thread` sites are per-stream/per-request setup by design. `install_executors()` runs inside the lifespan loop (`config/startup/__init__.py:165`, `executors.py:208`) and `shutdown_executors()` is the last shutdown step (`shutdown.py:162-172`). Process-wide DSP serialisation is on `HybridProcessor._process_lock` (`audio_processing_pipeline.py:197,220`), so two ChunkedAudioProcessors on one pooled processor cannot tear its state.
- **Processor pool / factory** — `ProcessorPool` pop-on-acquire and shielded cleanup (`processor_pool.py:79-159,199-233`, `job_lifecycle.py:489-511`) have no await between pop and hand-off, so a cancel cannot orphan a leased processor; `ProcessorFactory` constructs outside its lock and reconciles duplicates (`processor_factory.py:340-426`); background consumers have their own factories (`processor_registry.py:413-451`, #5311).
- **Job worker** — watchdog on the worker task (`config/startup/workers.py:217-291,333-340`); `JobWorker.cancel_task()` (`job_worker.py:219-241`) has exactly one caller, `job_lifecycle.cancel_job()` (called from `routers/processing_jobs.py:117`, loop thread). No thread-side path reaches it, so no `call_soon_threadsafe` is needed.
- **Lock ordering** — only `transition_lock -> active_tasks_lock` exists (`playback_control.py:88-90`); no reverse acquisition anywhere. `PlayerStateManager` mutates under its lock and broadcasts outside it with a monotonic `seq` (`state_manager.py:48-92`). `StreamlinedCacheManager` takes no await that yields inside its `_lock` (`cache/manager.py:189-197,227-279`).
- **Gate registries** — `stream_pause_events/stream_flow_events` entries are popped on stop (`playback_control.py:94-97`), on prior-task cancel (`playback_commands.py:94-97`) and on every disconnect via `teardown_connection` (`connection.py:261-268`), which always runs from the endpoint `finally` (`routers/system.py:193-202`).
- **Playback event ordering** — every transport/volume broadcaster draws from `playback_event_sequencer` (`playback_service.py:184,225,266,375`, `playback_control.py:33,49,108`); no other module emits `playback_*` / `volume_changed`.
- **Shutdown** — lifespan `finally` runs `_shutdown_components` (`config/startup/__init__.py:182-186`); position loop, auto-scanner/fingerprint queues/autofit (`background_workers.py:227-252`), streamlined worker, processing engine, processor-factory caches, engine pool, artwork session, fingerprint executor, converted-WAV registry, DB and thread pools are each individually guarded and awaited (`shutdown.py:43-172`). The one gap is CONC-D3-05.

### Library & Database

- **Engine config, all three engines agree.** `auralis/library/database_engine.py:48-65` (`check_same_thread=False`, `timeout=SQLITE_CONNECT_TIMEOUT_S`, `pool_pre_ping=True`, pool 5+5), `:95` (`PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}`); `auralis/library/migration_engine.py:40-62` (same constants, `pool_pre_ping=True`); `auralis/analysis/fingerprint/fingerprint_service.py:43-61` (same constants, `pool_pre_ping=True`, FKs on). Constants live once in `auralis/library/constants.py:19-27`. The only fourth `create_engine` is a one-shot CLI script (see CONC-D4-07). `analysis/fingerprint/catalog.py` opens a separate scratch DB (`scripts/fingerprint.py --database`), not library.db.
- **No raw SQL outside repositories/migrations.** grep for `text(` / `session.execute(` / `exec_driver_sql` outside `library/repositories/`, `library/migrations/`, `migration_*.py` finds only the `PRAGMA` calls in engine setup and `LibraryDatabase.shutdown()` (`database.py:194,203`). Raw `INSERT ... ON CONFLICT` upserts are inside `fingerprint_upsert_mixin.py:72-85` (repository layer) and are atomic.
- **ScanCoordinator symmetry.** `auralis/library/scan_coordinator.py:46-72` (slot counter and exclusive flag under one lock; settings read *before* taking the lock, so no DB I/O under `_scan_slots_lock`). `scanner/scan_stages.py:24-65`: slot acquired, then path reservation; on path clash the slot is released (`:63`, #4330) and nothing else is held. `scanner/scanner.py:127-262`: after `claim_scan` succeeds the `try/finally` at `:139-262` releases paths then slot on return, early `should_stop` return and exception. Fail-closed: no `except AttributeError` around the guard (#5802 holds); `try_acquire_scan_slot` falls back to `max_scans=1` on a settings error. The reset route's `try_begin_exclusive_access()` (`routers/library.py:117`) refuses while any slot is held and blocks new scans until `end_exclusive_access()` in `finally` (`:163-167`).
- **Watchdog/auto-scan thread->loop hops.** `scanner_watchdog.py:55-72`: `_schedule()` (watchdog thread) only calls `loop.call_soon_threadsafe(_schedule_on_loop)`; `call_later`, `TimerHandle.cancel()` and `create_task` all run on the loop (#4748 holds). `auto_scan_events.py:73-79`: scan worker thread -> `loop.call_soon_threadsafe(_schedule)`, `create_task` inside `_schedule` on the loop. `scanner_stop.py:41-66`: only `scanner.stop_scan()` (Event.set) is called across threads; the future is awaited on the loop.
- **migration_lock.py.** Both layers present: process-wide `_thread_lock` (`:42,69-73`) then `fcntl.flock`/`msvcrt.locking` (`:79-109`). Lock file never unlinked (#4523 holds). Single shared deadline; thread lock released in `finally` on every path including a failed `open()`. Not re-entrant, but no nested use exists (`check_and_migrate_database` and `normalize_existing_artists` each take it once; backup/restore take no lock themselves).
- **Migration atomicity and backup/restore.** `migration_steps.py:156-216`: `BEGIN` ... DDL ... version insert ... `COMMIT`, `ROLLBACK` on any BaseException. `migration_backup.py:81-83,127-129`: SQLite online backup API, connections closed via `closing()` (#5316); `restore_pre_migration_backup` disposes the manager engine first and runs inside the migration lock (`migration_manager.py:209-243`). Backup is skipped/aborts safely if it fails (`migration_manager.py:219-228`).
- **SettingsRepository** class-level `RLock` covers every read-modify-write on the singleton row (`settings_repository.py:34,43,76,134-170`, #5334 holds). `TrackRepository.delete` is a single conditional DELETE (`track_repository_lifecycle.py:236-279`, #5173 holds). `_get_or_create_artists/genres` use savepoints + IntegrityError fallback (`track_repository_lifecycle.py:63-93`).
- **Detached-instance handling.** Every Track read path carries `_track_eager_options()` (`track_repository.py:39-52`; used in `track_repository_lookup.py`, `_search.py`, `_lifecycle.py`, `_mutation.py`); Artist/Album/Playlist `get_by_id` carry nested selectinload (`artist_repository.py:74-76`, `album_repository.py:49-52`, `playlist_crud_mixin.py:105-115`). Post-commit `refresh()` sites (`track_repository_lifecycle.py:201-202`, `settings_repository.py`, `playlist_crud_mixin.py:92`) all re-query or touch the relationship before `expunge()`. No new race found.
- **Scan updating a playing track.** `update_by_filepath` (`track_repository_mutation.py:65-119`) updates only the scanner-owned columns in its own short transaction (ORM issues UPDATE of changed columns only, so `play_count`/`favorite` are not lost); the player holds its own metadata snapshot and reads audio from the file, not the row. `cleanup_missing_files` re-verifies paths before deleting (`track_repository_maintenance.py:168-186`).
- **Fingerprint DB writes from worker threads.** Claim = placeholder INSERT guarded by UNIQUE (`fingerprint_scheduler_repository.py:139-173`); upsert is `ON CONFLICT DO UPDATE`; `.25d` sidecar writes are atomic with unique temp names (`utils/atomic_write.py:70-105`); `FingerprintService._load_from_database` rejects placeholders via `band_pct_valid` (`fingerprint_service.py:196-199`). `ResizableSemaphore` is correct under its Condition (`resizable_semaphore.py:35-62`). On-demand queue `enqueue` is lock-guarded (`analysis/fingerprint_queue.py:93-121`, #5261 holds). `release_claims` only touches sentinel rows.
- **Lock-order.** `AdaptiveResourceMonitor._lock` -> `queue.stats_lock` / `ResizableSemaphore._cond` is the only nesting; nothing takes them in the reverse order (callbacks-under-lock hazard is already #5756).
- **SQLite transaction mode.** With pysqlite legacy transaction control `BEGIN` is deferred to the first DML, so repository read-then-write sequences do not hit `SQLITE_BUSY_SNAPSHOT`; I found no path that reads inside an open transaction and then upgrades to a write after another connection committed.

### Frontend State

- Inbound frame dispatch is synchronous FIFO: `WebSocketManager` sets `binaryType = 'arraybuffer'`
  (`utils/errorHandling.ts:101`), so the async Blob branch in `socketFrameParser.ts:99-116` is dead and
  `audio_chunk_meta`/binary pairing (`socketFrameParser.ts:78-96`) cannot interleave with another message.
  `pendingMeta`/`expectedSeq`/`seqStreamEpoch` are reset on every `open` (`websocketConnectionCore.ts:33-37`).
- Single connection / reconnect: `useWebSocketConnection.ts:114-198` reuses the singleton, joins the in-flight
  handshake (`connState.connectPromise`), retires an exhausted manager via `closeCurrentManager()`;
  `WebSocketManager` keeps one retry timer and `detachSocket()` nulls handlers of a replaced socket
  (`errorHandling.ts:148-193`). Queue replay precedes the resume command (`websocketConnectionCore.ts:42-72`).
- Subscriptions: handlers held in refs, resubscription keyed only on sorted type key + stable `subscribe`
  (`useWebSocketMessages.ts:44-70`); `dispatchMessage` isolates each handler in try/catch
  (`WebSocketContext.tsx:140-165`).
- Sequence watermarks for `player_state`, `position_changed`, transport events, volume, `track_changed`
  (`usePlayerStateSync.ts:69-88,98-205`); reducer-level `trackId` guards on progress/complete/error/stall
  (`playerStreamingReducers.ts:108-190`).
- Pre-`audio_stream_start` chunks are queued then drained through `handleChunk`, which applies the epoch filter
  (`useEnhancedStreamStart.ts:213-225`, `audioChunkIngest.ts:61-79`); older-epoch `audio_stream_start` is ignored
  (`useStreamSubscriptions.ts:90-110`). The *play/track-change* path is therefore protected from in-flight old frames
  because the play command does not null `streamEpochRef` (old frames queue as "not-initialized" and are dropped at drain).
- Rapid skip: `useTransportCommand` single-flight gate (`usePlaybackSessionHooks.ts:34-58`), per-invocation
  `AbortController` for the metadata fetch in the play command (`useEnhancedPlayCommand.ts:96-121`) — an aborted
  earlier invocation returns before sending (`:116`) and there is no `await` between the last fetch continuation
  and the `wsContext.send` calls (`:141,150`), so an older play cannot be sent after a newer one. `usePlayTrack.ts:46-52` aborts the queue POST.
- Optimistic queue mutations use call-time store snapshots and per-field generation counters
  (`queueMutationGuards.ts:62-85`, `useQueueMutations.ts:56-85`); enhancement preset/intensity use monotonic
  request ids and toggle uses a ref guard (`useEnhancementCommands.ts:56-72,111-125,164-175`).
- Library hooks: request-id supersession (`useLibraryQuery.ts:123-170`, `useLibraryPagination.ts:62-110,185-215`),
  `useRestAPI` GET stale detection and in-flight counter (`useRestAPI.ts:75-130`).
- Flow control after seek: backend creates a fresh, set `flow_event` for the seek stream
  (`ws_handlers/playback_commands.py:476-481`); the client's `flowPausedRef` self-heals on the first post-seek chunk
  (`audioChunkIngest.ts:98-103`, `useStreamMessageHandlers.ts:141-150`). Not a deadlock.
- Shared stores: `useScanProgress.ts` (refcounted single subscription + reconnect resync), `useArtworkUpdates.ts`
  (refcounted, `useSyncExternalStore`), `useStreamStartWatchdog.ts` (ref-held callback, unmount cleanup).
- `PCMStreamBuffer` is only touched from main-thread tasks (feed loop and chunk append, `WorkletOutput.ts:162-192`);
  samples are transferred (not shared) to the worklet, so no in-place mutation of a shared array crosses threads.

## Skipped as Existing (by dimension)

### Player Thread Safety

- #5706 (OPEN): auto-advance retries forever when `next_track()` returns False. `player_streaming_mixin.py:146-185`. Not re-reported.
- #5705 (OPEN): `previous_track()` rollback skipped on wrap. `player_queue_navigation_mixin.py:194-201`. Not re-reported.
- #5726 (OPEN): `current_track` metadata goes stale after any queue-driven advance (`next_track()` never calls `set_current_track`). Covers the stale `_current_track_dict` seen by `playback_finished` and `get_playback_info`.
- #5725 (OPEN): a failed load forces the player into ERROR (`player_file_loading_mixin.py:51-91,109-150`).
- #5708 (OPEN): production `load_file()` decodes/prebuffers/fingerprints audio nothing consumes. Used above to bound the severity of D1-02/D1-04.
- #5563 (OPEN): engine next/previous/gapless read `file_path`/`path` but production queue entries use `filepath`; `advance_with_prebuffer` therefore returns False at `gapless_playback_engine.py:130-132` for backend-built queues. Used above to bound D1-02.
- #5564 (OPEN): `QueueManager.shuffle()/unshuffle()` track the current track by id only (`queue_shuffle.py` current_track_id handling).
- #5565 (OPEN): `advance_with_prebuffer` treats two missing ids as equal (`_entries_match` vs `_track_matches` divergence is related).
- #5727 / #5728 (OPEN): empty-queue `add_to_queue()` never syncs the queue pointer; `shuffle_enabled` survives `set_queue()/clear_queue()`.
- #5721 / #5707 / #5729 (OPEN): realtime-chain level/gain behaviour (not lock related).

### Audio Processing

- Stale/never-refreshed reference cloud in `ContinuousMode._reference_cloud` / `_distance_stats` (also stays stale after `POST /api/library/refresh-references` in already-cached processors): Existing: #5722
- ContinuousMode quality gate holds `_process_lock` ~2 s per sampled call and can raise `KeyError` on short chunks: Existing: #5712
- `/api/processing/parameters` content profile is keyed by preset only, so concurrent streams overwrite each other: closed as a documented known limitation (#4601), behaviour unchanged.
- `AdaptiveResourceMonitor` callbacks under its lock (#5756), multichannel FFmpeg ignoring `cancel_event` (#5730), auto-advance retry loop (#5706), `previous_track` rollback (#5705): other dimensions, not re-checked here.

### Backend Streaming

- #5064 (OPEN) - `_remember_processor` closes an evicted processor with no in-use check and runs the `rmtree` on the event loop. Same mechanism also applies to `proactive_buffer.py:116-119` (inline `processor.close()` in an async `finally`) and `streamlined_processor_cache.close_dropped_processor` callers; noted as siblings in CONC-D3-01.
- #5078 / #5076 (OPEN) - `StreamState.active_stream_settings` is a per-connection `default_factory` dict (`routers/system.py:82-89`), and `handle_play_normal` / `_cancel_prior_task` do not maintain it.
- #5077 (OPEN) - heartbeat monitoring disabled after a transient send failure; unguarded `websocket.close()` in the eviction path (`ws_handlers/connection.py:70-89`).
- #5258 (OPEN) - no single-flight dedup for concurrent seek requests to the same chunk key.
- #5068 (OPEN) - `reclaim_leftover_stream_temps` / `reclaim_stale_temp_entries` run blocking `shutil.rmtree` on the event loop (`config/startup/tempfiles.py`).
- #5730 (OPEN) - multichannel WAV/FLAC FFmpeg load ignores `cancel_event` (relevant to the decode half of CONC-D3-01).
- #5756 / #5706 / #5705 (OPEN) - outside this dimension's files.

### Library & Database

- #5597 (OPEN): `MigrationManager.get_current_version()` maps any exception (e.g. `database is locked`) to version 0, so `migrate_to_latest()` stamps an old DB as current and the backup is skipped. Same flaw reached through the pre-versioning path: #5851 (OPEN).
- #5595 (OPEN): `TrackRepository.add()` album race guard can never fire (relevant to CONC-D4-08's concurrent-scan outcome).
- #5756 (OPEN): `AdaptiveResourceMonitor` invokes callbacks while holding its lock (`resource_monitor.py:114-173`); confirmed, not re-reported.
- #5381 (OPEN): similarity/graph/fingerprint-queue routers map transient DB-locked errors to HTTP 500.
- Closed and verified still fixed: #4330 (slot leak on path clash), #5802 (fail-closed slot check), #5799 (shared timeout constants), #4748/#2863 (thread->loop hop), #4523 (lock file not unlinked), #4232 (same-process thread lock), #5316 (restore on failed migration), #4816 (reset vs in-flight scan), #5173, #5334, #5261, #4596, #4404, #4775.

### Frontend State

- #5651 — bulk "add to queue" fires N concurrent POSTs (same family: concurrent `removeTrack(index)` / `reorderTrack` REST calls compute indices from the optimistic state and can be applied out of order server-side).
- #5650 / #5190 / #5649 — request cancellation gaps (`useRestAPI` callers cannot abort; un-timed metadata GET gates playback start in `useEnhancedPlayCommand.ts:100`).
- #5655 — shared enhancement-status promise tied to the first consumer's abort (`useEnhancementStatusSync.ts`).
- #5130 — `useQueueHistory` `isMountedRef` never reset on remount.
- #5460 / #5726 — backend queue pointer / `current_track` drift that CONC-D5-05 is the frontend consequence of.
- #5615 — connection slice write-dead (so `connection.wsConnected` selectors cannot be trusted; this audit used `WebSocketContext` state instead).
- #5673 — missing tests for HK-02/RDX-01/HK-04/CMP-04 (relevant to the absence of regression tests for D5-01/D5-02).
