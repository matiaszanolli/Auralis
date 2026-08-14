# Backend Audit — 2026-08-13

**Scope**: `auralis-web/backend/` — routers, WebSocket streaming, chunked
processing, processing engine, schemas, middleware, error handling,
performance, test coverage, caching, seek/buffering.
**Depth**: deep (full call-graph tracing) across all 11 dimensions.
**Method**: 11 independent dimension agents, each performing a fresh read of the
current source. Every finding was deduplicated against 292 OPEN and 2,000 CLOSED
GitHub issues before inclusion. No prior audit report was used as a source.

---

## Executive Summary

| Severity | Count | Findings |
|----------|-------|----------|
| CRITICAL | 0 | — |
| HIGH | 5 | B4-1, B7-1, B10-1, B10-2, B11-1 |
| MEDIUM | 7 | B2-1, B9-1, B10-3, B10-4, B10-5, B11-2, B11-3 |
| LOW | 4 | B3-1, B5-1, B6-1, B9-2 |
| **Total** | **16** | |

### Key themes

1. **Caching is the weakest subsystem (5 of 16 findings, both non-seek HIGHs).**
   The three independent caches have drifted apart in rigor. The *fallback*
   in-memory chunk cache (`SimpleChunkCache`) received a file-signature fix in
   #4358; the *production* one (`StreamlinedCacheManager`) never did. The
   cache-clear endpoint clears bookkeeping dicts but not the WAV bytes on disk,
   which `ChunkedAudioProcessor` then silently rediscovers — so the user's only
   troubleshooting lever is a no-op.

2. **Resource-lifecycle gaps at *newly split* call sites.** Both B11-1 (temp WAV
   never closed on the seek/enhanced paths) and B4-1 (pooled processor config
   mutated and never restored) are cases where a fix was applied correctly at
   one call site and the sibling site was missed. B11-1's own predecessor
   (#5062) explicitly warned that a "future third removal" would need the same
   treatment — and it did.

3. **Timeout discipline is uneven.** Streaming paths wrap every
   `ChunkedAudioProcessor` construction in `asyncio.wait_for(CHUNK_PROCESS_TIMEOUT)`
   (per #2125/#3852). The per-play background recommendation task, which runs on
   *every single track play*, does not (B7-1) — and shares the same default
   executor, so one bad file can starve unrelated backend work.

4. **The rest of the backend is genuinely mature.** Dimensions 1 (Route
   Handlers) and 8 (Performance) produced **zero** new findings after full
   sweeps. Backpressure, per-connection isolation, lock-across-await, binary
   framing, atomic cache writes, `selectinload()` usage, SQLAlchemy pooling,
   middleware ordering, CORS, static-mount path restriction, and global
   exception handling were each independently verified as correct — mostly with
   an issue number in a comment documenting the prior fix.

### Most impactful issues

1. **B10-1** — the production chunk cache serves stale audio indefinitely after
   an in-place file edit. Most user-visible caching bug in the backend.
2. **B10-2** — "Clear cache" does not actually clear the cache.
3. **B4-1** — one narrow race silently downgrades *every subsequent*
   reference-mastering job to adaptive-only, with no error and a job record that
   still claims `mode="reference"`.
4. **B11-1** — every seek/play on `.m4a`/`.aac`/`.wma` permanently leaks a
   full-track temp WAV; not reclaimed at restart (wrong glob prefix).
5. **B7-1** — an unbounded blocking call on the hottest possible trigger
   (every track play) can exhaust the shared thread executor.

---

## Route Coverage Matrix

All 20 routers registered via `auralis-web/backend/config/routes.py` (derived
live, not from a hardcoded list). "Validation" = Pydantic bodies + path/query
constraints; "Tests" = at least one dedicated test file exercising its routes.

| # | Router | Registration | Validation | Tests | Notes |
|---|--------|-------------|-----------|-------|-------|
| 1 | `health.py` | unconditional | n/a | ✅ | extracted from system in #4074 |
| 2 | `system.py` | unconditional | ✅ | ✅ | hosts the WebSocket endpoint |
| 3 | `settings.py` | unconditional | ✅ | ✅ | `volume` 0.0–1.0 (see #4711) |
| 4 | `files.py` | unconditional | ✅ | ✅ | TOCTOU-safe upload (#2560/#2170) |
| 5 | `enhancement.py` | unconditional | ⚠️ | ✅ | `preset: str` not `Literal` (#4710); path validation gap #4817 |
| 6 | `artwork.py` | unconditional | ✅ | ✅ | path traversal guarded (#4532/#4527) |
| 7 | `playlists.py` | unconditional | ✅ | ⚠️ | both test files hard-skipped (#4381) |
| 8 | `library.py` | unconditional | ✅ | ✅ | `reset_library` orphans artwork — B10-5 |
| 9 | `tracks.py` | unconditional | ⚠️ | ✅ | `get_track_lyrics` discards validated path (#4814) |
| 10 | `library_scan.py` | unconditional | ✅ | ✅ | bounded by `AURALIS_SCAN_TIMEOUT` |
| 11 | `fingerprint_status.py` | unconditional | ✅ | ✅ | |
| 12 | `metadata.py` | unconditional | ✅ | ✅ | |
| 13 | `albums.py` | unconditional | ✅ | ✅ | `serialize_album_detail` genre key (#4709) |
| 14 | `artists.py` | unconditional | ✅ | ✅ | |
| 15 | `player.py` | unconditional | ✅ | ✅ | route ordering explicitly commented |
| 16 | `processing_api.py` | `try/except` guarded | ✅ | ✅ | 500MB sync write on loop (#4653) |
| 17 | `cache_streamlined.py` | `try/except` guarded | ✅ | ✅ | clear is a partial no-op — B10-2 |
| 18 | `similarity.py` | `try/except` guarded | ✅ | ✅ | `similarity_score` bounds → 500 (#5057) |
| 19 | `similarity_graph.py` | `try/except` guarded | ✅ | ✅ | shares `/api/similarity` prefix |
| 20 | `fingerprint_queue.py` | `try/except` guarded | ✅ | ✅ | shares `/api/similarity` prefix |

**Registration failure visibility**: the 3 conditionally-imported factory groups
are wrapped in `try/except Exception` with `logger.warning(..., exc_info=True)` —
visible, not silent, not debug-only. The other 17 are top-level imports with no
guard, an intentional fail-loud tradeoff documented at `config/routes.py:34-39`.

**Prefix sharing**: `similarity.py`, `similarity_graph.py`, and
`fingerprint_queue.py` all register under `/api/similarity` with distinct tags —
verified as non-colliding on concrete paths.

---

# Findings

## HIGH

### B4-1: Reference-mode fallback mutates a pooled processor's shared config, silently corrupting future reference/hybrid jobs into adaptive-only processing

- **Severity**: HIGH
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/processing_engine.py:575-616` (specifically :612), `auralis-web/backend/core/processor_pool.py:48-157`
- **Status**: NEW
- **Description**: `ProcessorPool` caches `HybridProcessor` instances keyed by
  `cache_key(mode, config)`, hashing both the caller's `mode` string and
  `config.adaptive.mode`. `_execute_job`'s reference-unavailable fallback (added
  by #4735) calls `processor.config.set_processing_mode("adaptive")`. Because
  `HybridProcessor.__init__` stores `self.config = config` **by reference**, on a
  cache hit this mutates the *pooled* instance's own, older config object — and
  nothing restores it. `return_to_cache`'s key is computed from the *fresh,
  unmutated* local config, so the poisoned processor is filed back under its
  original `"reference"` key.
- **Evidence** — full reproduction chain:
  1. Job A (`mode="reference"`), reference file becomes unavailable between
     submission and execution (the narrow race `_execute_job`'s own comment
     describes). Pooled processor P is leased on a cache hit.
  2. Fallback fires: `processor.config.set_processing_mode("adaptive")` mutates
     P's config in place. Job A processes correctly.
  3. `finally:` → `_return_processor("reference", config_A, P)`. `config_A` is
     unmutated, so P is stored back under the `"reference"` key with
     `P.config.adaptive.mode == "adaptive"`.
  4. Job B (`mode="reference"`, **valid** reference file) hits the same key and
     pops the poisoned P.
  5. `HybridProcessor._process_impl` (`auralis/core/hybrid_processor.py:295-297`):
     ```python
     if self.config.is_reference_mode() and reference is not None:
         return self._process_reference_mode(...)
     elif self.config.is_adaptive_mode():
         return self._process_adaptive_mode(target_audio, results)
     ```
     `is_reference_mode()` is now `False`, so control falls into the adaptive
     arm — `reference_audio` is silently discarded, no exception, no
     distinguishing log.
  6. `_finalize_job` reports success with `mode` still `"reference"`.

  `tests/backend/test_reference_mode_wiring_4735.py` pins the fallback mutation
  against a standalone `HybridProcessor` that is never returned to the pool, so
  it does not exercise this path.
- **Impact**: Once the race is hit even once, every subsequent
  `mode="reference"`/`"hybrid"` job sharing that cache key silently gets
  adaptive-only mastering with a perfectly valid reference file — no error,
  and a job record that still claims `mode="reference"`. On a desktop app with
  typically one active sample-rate/profile combination, this can degrade every
  reference-mastering request for the rest of the process lifetime (LRU eviction
  requires 5 other distinct keys to churn through first).
- **Siblings**: None — `processor_factory.py` (streaming/chunked path) always
  builds a fresh `deepcopy(config)` and never mutates a cached instance.
- **Suggested Fix**: Restore `processor.config.set_processing_mode(job.mode)`
  before the processor can be returned to the pool, or operate on a private
  config copy for the fallback call. Longer-term, derive `return_to_cache`'s key
  from `job.mode` alone so the two can never diverge.

---

### B7-1: Per-play background mastering-recommendation task has no timeout on its `ChunkedAudioProcessor` construction, unlike every sibling streaming path

- **Severity**: HIGH
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/services/recommendation_service.py:76-109` (and `:135-158`); triggered from `auralis-web/backend/ws_handlers/playback_commands.py:233-237,288-293`; REST twin at `auralis-web/backend/routers/enhancement.py:487-511`
- **Status**: NEW
- **Description**: `generate_and_broadcast_recommendation()` is spawned from
  **both** `handle_play_enhanced` and `handle_play_normal` — on every track play,
  not an edge case. Its body is:
  ```python
  def _analyze() -> dict[str, Any] | None:
      processor = ChunkedAudioProcessor(track_id=..., filepath=track_path, ...)
      rec = processor.get_mastering_recommendation(confidence_threshold=...)
      ...
  rec_dict = await asyncio.to_thread(_analyze)
  ```
  There is no `asyncio.wait_for(..., timeout=...)`. The three streaming entry
  points (`stream_enhanced.py:132-147`, `stream_seek.py:134-149`,
  `stream_chunk_ops.py:110-122`) wrap the *exact same* constructor in
  `asyncio.wait_for(..., timeout=_asc.CHUNK_PROCESS_TIMEOUT)` precisely because
  "File may be corrupt or on slow storage" (#2125, #3852). #3553 moved this path
  off the event loop but did not re-apply the hang guard.
- **Evidence**: The only `ThreadPoolExecutor(` in the backend is the dedicated
  fingerprint executor — every `asyncio.to_thread` call shares Python's single
  default per-loop executor (`min(32, cpu_count+4)` workers).
  `ChunkedAudioProcessor.__init__` → `_load_metadata()` is bounded to ~30s *only*
  for FFmpeg formats (`subprocess.run(ffprobe_cmd, timeout=30)`,
  `auralis/io/unified_loader.py:233-236`); for natively-decodable formats it
  calls `sf.info()` (`:198`) with no timeout at all.
- **Impact**: One problematic file (corrupt header stalling native decode, or a
  track on network/removable storage that disappears mid-read) played once
  permanently pins a worker thread — the outer `except Exception` never runs
  because the hang is inside the blocking call. Repeated plays exhaust the shared
  executor, after which every other `asyncio.to_thread` in the backend (streaming
  DB lookups, chunk reads, library scans) queues behind it.
- **Siblings**: `routers/enhancement.py:487-511` (REST twin, identical gap);
  `RecommendationService.get_recommendation_for_track()` (currently unused).
- **Note on in-flight work**: an uncommitted `auralis-web/backend/core/executors.py`
  (#5086 / #4810) was present in the working tree at audit time; it splits the
  single implicit default pool into `STREAM_EXECUTOR` and `IO_EXECUTOR`. That
  narrows the *blast radius* of this finding — a hang would pin an `IO_EXECUTOR`
  thread rather than the one pool everything shares — but does not address the
  finding itself: the call still has no timeout and the thread is still never
  reclaimed.
- **Suggested Fix**: Wrap the `await asyncio.to_thread(_analyze)` and its twins
  in `asyncio.wait_for(..., timeout=CHUNK_PROCESS_TIMEOUT)`, catching
  `TimeoutError` the same way the existing `except Exception` branch does.

---

### B10-1: `StreamlinedCacheManager`'s cache key omits the file signature — stale audio served indefinitely after an in-place file edit

- **Severity**: HIGH
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/cache/manager.py:96-99` (`CachedChunk.key()`), `:339` (`get_chunk()`), `:394` (`add_chunk()`)
- **Status**: NEW
- **Description**: `StreamlinedCacheManager` is the **production-wired** chunk
  cache — `routers/system.py` and `config/startup.py` inject the module-level
  singleton into every `AudioStreamController`; `core/chunk_cache.SimpleChunkCache`
  is only a fallback used when no manager is injected. Its key is:
  ```python
  cache_key = f"{track_id}_{preset_key}_{intensity:.1f}_{chunk_idx}"
  ```
  The file signature is absent. `get_chunk()` is consulted *first*, before
  `ChunkedAudioProcessor`/`WAVEncoder` (which do embed the signature in both
  their key and their on-disk filename) are ever invoked.
- **Evidence**: `SimpleChunkCache` — the *fallback* layer — already got exactly
  this fix in #4358, and its docstring spells out the failure mode: *"Without it,
  this in-memory layer would keep serving the previously-processed samples … for
  the process lifetime, causing stale/wrong-speed audio after a replacement file
  with a different rate."* No caller of `get_chunk`/`add_chunk`/`CachedChunk`
  passes a file signature — the parameter does not exist on this API. `grep -rn
  "clear_track" services/ core/ routers/` shows only the manual HTTP endpoint
  calls it; nothing in the scanner/rescan pipeline invalidates on mtime change.
- **Impact**: A user who edits or replaces a track's audio file without
  removing/re-adding it from the library (same `track_id`) keeps hearing the old
  audio for the remainder of the backend's uptime, until LRU eviction happens to
  reclaim the entry — even though the signature-aware disk tier and
  `SimpleChunkCache` would both correctly detect the change.
- **Siblings**: None — the on-disk `WAVEncoder`/`ChunkCacheManager` keys are
  correct; this is the one layer that was missed.
- **Suggested Fix**: Add `file_signature` to `CachedChunk.key()` and the
  `get_chunk()`/`add_chunk()` key strings, mirroring #4358 and the on-disk key
  shape.

---

### B10-2: `/api/cache/clear` and `DELETE /api/cache/track/{id}` do not force reprocessing — on-disk WAV chunks survive and are silently rediscovered

- **Severity**: HIGH
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/routers/cache_streamlined.py:135-169`, `auralis-web/backend/cache/manager.py:676-710`, `auralis-web/backend/core/chunked_processor.py:546-592`
- **Status**: NEW
- **Description**: `POST /api/cache/clear`'s docstring says *"Use with caution -
  this will force re-processing of all chunks."* Both endpoints only call
  `StreamlinedCacheManager.clear_all()`/`clear_track()`, which empty the
  `tier1_cache`/`tier2_cache` **dicts** — bookkeeping of `Path` objects. Neither
  ever deletes the WAV bytes from `/tmp/auralis_chunks`.
- **Evidence**:
  ```python
  # cache/manager.py:702-709
  async def clear_all(self) -> None:
      async with self._lock:
          self.tier1_cache.clear()
          self.tier2_cache.clear()      # no filesystem interaction whatsoever

  # core/chunked_processor.py:577-592 — runs regardless of the dict above
  wav_chunk_path = self._get_wav_chunk_path(chunk_index)  # deterministic path
  if wav_chunk_path.exists():
      if is_wav_complete(wav_chunk_path):
          self._cache_manager.cache_chunk_path(cache_key, wav_chunk_path)
          return wav_chunk_path   # stale file served again, no reprocessing
  ```
  `ChunkedAudioProcessor` was given its own independent disk-existence fallback
  in #4792, so clearing the dict has no effect. There is no
  `force_reprocess`/`bypass_cache` flag anywhere in the codebase (zero grep
  hits), and nothing else deletes from the chunk directory except the
  size-triggered, content-agnostic `prune_chunk_directory` (512 MB LRU).
- **Impact**: The cache-clear action — the user's primary troubleshooting tool
  for "the cached audio sounds wrong, let me clear and retry" — is a no-op for
  anything already on disk. The exact same bytes are served again while the user
  believes they forced a clean reprocess.
- **Related**: B10-1 (both let stale bytes survive), B10-3 (same method).
- **Suggested Fix**: Have `clear_all()`/`clear_track()` also delete the
  corresponding on-disk WAV files (the `CachedChunk.chunk_path` values are known
  before the dicts are cleared), or expose a shared invalidation helper that both
  the router and `ChunkedAudioProcessor` call.

---

### B11-1: `SeekableSource` temp WAV is never closed on the live streaming/seek paths — leaks a full-track decode per seek on m4a/aac/wma

- **Severity**: HIGH
- **Dimension**: Seek & Buffering
- **Location**: `auralis-web/backend/core/stream_seek.py:41-433` (no `.close()` in the `finally:` at :430-433), `auralis-web/backend/core/stream_enhanced.py` (no `.close()` anywhere in the file), `auralis-web/backend/config/startup.py:271-290`
- **Status**: NEW (sibling of CLOSED #5062, which fixed the same bug class at a different call site and explicitly warned that a future third removal would need the same treatment)
- **Description**: `ChunkedAudioProcessor.__init__` builds a
  `SeekableSource(filepath)` (`chunked_processor.py:179`). For formats libsndfile
  cannot open natively — `.m4a`/`.aac`/`.wma` — the first `load_chunk()`
  converts the whole track to a temp WAV under a fresh
  `tempfile.mkdtemp(prefix="auralis_seekable_")` (`seekable_source.py:56-77`,
  `:98-118`). `SeekableSource`'s docstring requires the holder to call `close()`;
  `ChunkedAudioProcessor.close()` does exactly that (`chunked_processor.py:719-727`).
  Neither production entry point calls it. The only two call sites that do are
  `proactive_buffer.py` (dead — #3884) and `stream_prefetch.py` (dead — #3513).
- **Evidence**:
  ```python
  # stream_seek.py:430-433 — the only cleanup; no processor.close()
  finally:
      await controller._drain_cancelled_task(lookahead_task)
      controller._stream_semaphore.release()
  ```
  ```python
  # config/startup.py:282 — wrong glob, misses SeekableSource's prefix
  for leftover in temp_root.glob("auralis_stream_*"):
  # seekable_source.py:56 — the prefix actually used, never swept
  def convert_to_temp_wav(filepath: str, *, prefix: str = "auralis_seekable_") -> ...
  ```
  `stream_from_position` constructs a **brand-new** `ChunkedAudioProcessor` (and
  therefore a new `SeekableSource`) on every seek — no reuse or pooling.
- **Impact**: On any `.m4a`/`.aac`/`.wma` track (iTunes/Apple Music purchases,
  Windows Media exports), every `play_enhanced` and every subsequent seek leaks
  one full-track temp WAV — tens to hundreds of MB — forever. Not reclaimed by
  GC (no `__del__`) and not reclaimed at process restart (wrong glob). Since
  rapid seeking is a common action, one scrubbing session can leak several times
  the track's decoded size in minutes.
- **Siblings**: `stream_enhanced.py` (non-seek play) has the identical gap; the
  seek path amplifies it via per-seek processor construction.
- **Suggested Fix**: Add `processor.close()` to the `finally:` blocks of
  `stream_seek.py` and `stream_enhanced.py` (mirroring `proactive_buffer.py`),
  and extend `reclaim_leftover_stream_temps`'s glob to cover
  `auralis_seekable_*`.

---

## MEDIUM

### B2-1: `audio_stream_end.reason` is sent by the backend but never read by the frontend, so truncated/degraded streams are reported as 100% complete

- **Severity**: MEDIUM
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/core/stream_messages.py:118-154` (producer) ↔ `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts:372-385` (consumer); also `auralis-web/frontend/src/store/slices/playerSlice.ts:378-393` and `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx:212-227`
- **Status**: NEW
- **Description**: `send_stream_end()` emits `reason: "completed" | "stopped" |
  "errored"` on every `audio_stream_end` — added by #4659/#4790 specifically so
  clients could tell a finished stream from one that stopped early or ran to the
  end while skipping failed chunks. `handleStreamEnd` never reads
  `message.data.reason`; it unconditionally dispatches `completeStreaming`,
  whose reducer unconditionally sets `state = 'complete'` and `progress = 100`.
  A repo-wide grep for reads of `.reason` on this message across `frontend/src`
  returns zero matches.
- **Evidence**:
  ```ts
  // useAudioStreamingCore.ts:372-385
  const handleStreamEnd = useCallback((message: AudioStreamEndMessage) => {
    if (!acceptsStreamType(message.data.stream_type)) return;
    dispatch(completeStreaming({ streamType, trackId: message.data.track_id }));
  }, [...]);
  // playerSlice.ts:378-393 — no reason branch, always forces progress=100
  s.state = 'complete';
  s.progress = 100;
  ```
- **Impact**: Any stream ending with `reason: "stopped"` (enhancement toggled off
  mid-track, semaphore/timeout abort) or `"errored"` (chunks failed and were
  skipped, per #4790) is reported to Redux as 100% complete regardless of how
  much audio arrived — reproducing the exact bug class #4659/#4790 fixed, one
  hop further down the pipeline. Two concrete effects: progress affordances snap
  to 100% on a partial stream, and `PlaybackSessionContext`'s auto-advance
  (`isComplete && nearEnd`) can skip to the next queue track on a degraded
  stream near a track's end.
- **Siblings**: Same "computed but unread" pattern as already-filed #4655
  (`audio_stream_error.recovery_position`); this is the `audio_stream_end`
  sibling of that gap.
- **Suggested Fix**: Branch on `message.data.reason` in `handleStreamEnd` — only
  dispatch `completeStreaming` for `'completed'` (or undefined, for back-compat);
  use a neutral transition for `'stopped'` and an error-visible state for
  `'errored'` so auto-advance does not fire on a degraded stream.

---

### B9-1: Two security tests for injection attacks assert nothing — `assert True` regardless of outcome

- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `tests/security/test_input_validation.py:92-93`, `:166-167`
- **Status**: NEW
- **Description**: `test_homograph_attack` and `test_ldap_injection` in
  `TestAdditionalInjectionVectors` exercise `TrackRepository.add()` /
  `.search()` with homograph and LDAP-metacharacter payloads, but each ends in an
  unconditional `assert True, "<message>"`. No code path through those repository
  methods can fail these tests — a repository that stored the raw attack string,
  returned unsanitized data, or leaked every record on `"*"` would pass
  identically to one that handled the input correctly.
- **Evidence**:
  ```python
  # test_homograph_attack, :92-93
  track = track_repo.add(track_info)
  assert True, "Homograph handled without crash"
  # test_ldap_injection, :166-167
  result = track_repo.search(attack, limit=10, offset=0)
  assert True, "LDAP injection handled safely"
  ```
  Contrast the neighboring `test_unicode_normalization_attack` (:55-61), which
  actually asserts `'<script>' not in track.title.lower()`.
- **Impact**: A regression making LDAP-metacharacter search return the entire
  table, or storing a homograph-spoofed title without normalization, would ship
  silently. Only an unhandled exception — not the assertion — can fail these.
- **Siblings**: None elsewhere in `tests/security/`;
  `test_null_byte_injection` (:118-126) does assert a real condition.
- **Suggested Fix**: Replace each `assert True` with a concrete check mirroring
  `test_unicode_normalization_attack` — assert the stored title round-trips or is
  rejected outright, and assert `len(results) <= <known track count>` for the
  LDAP case.

---

### B10-3: `clear_track()` Tier1 eviction uses substring matching, over-evicting unrelated tracks

- **Severity**: MEDIUM
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/cache/manager.py:676-700`
- **Status**: NEW
- **Description**: `clear_track()` removes Tier1 entries with
  `str(track_id) in str(k)` — a **substring** test against the composite key
  `"{track_id}_{preset}_{intensity}_{chunk_idx}"` — while Tier2's removal, three
  lines later, correctly matches on the parsed `CachedChunk.track_id` attribute.
  Since track IDs are sequential SQLite integers, false positives are reliable.
- **Evidence**:
  ```python
  # cache/manager.py:682-693
  t1_keys = [k for k in self.tier1_cache if str(track_id) in str(k)]   # substring — BUG
  t2_keys = [k for k, chunk in self.tier2_cache.items()
             if chunk.track_id == track_id]                            # exact — correct
  ```
  `clear_track(1)` matches track 12's key `"12_adaptive_1.0_3"`, and can even
  match on digits inside another track's chunk index or `.1f` intensity.
- **Impact**: `DELETE /api/cache/track/{id}` silently evicts hot Tier1 entries
  (current + next chunk) for unrelated currently-playing tracks, causing an
  unnecessary re-buffer hiccup. Not a correctness bug — Tier2's exact filter is
  unaffected and an evicted Tier1 entry is a miss, not wrong content.
- **Suggested Fix**: Filter Tier1 on `CachedChunk.track_id == track_id` exactly
  as Tier2 already does (Tier1 entries are also `CachedChunk` instances).

---

### B10-4: Tier2 hit/miss counters are structurally wrong — `tier2_misses` is dead and the reported tier2 "hit_rate" is not a hit rate

- **Severity**: MEDIUM
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/cache/manager.py:196`, `:319-360`, `:541-587`
- **Status**: NEW
- **Description**: `get_chunk()` increments `self.tier1_misses` on its only miss
  branch — reached when **both** tiers missed — and never increments
  `self.tier2_misses` anywhere in the class (assigned only once, to `0`, in
  `__init__`). Consequently `stats["tier2"]["misses"]` is permanently `0`, and
  `stats["tier2"]["hit_rate"] = tier2_hits / max(1, total_requests)` divides
  tier2's hits by the **combined** total of all four counters — a request
  satisfied by Tier1 never touches Tier2 yet inflates its denominator.
- **Evidence**:
  ```python
  # :357-360
  self.tier1_misses += 1   # tier2_misses never touched here or anywhere
  # :559-565
  "misses": self.tier2_misses,                                        # always 0
  "hit_rate": self.tier2_hits / max(1, total_requests) ...            # wrong denominator
  ```
  `cache/monitoring.py::CacheMonitor` reads these verbatim and surfaces them as
  trends/alerts — it propagates the wrong numbers faithfully rather than
  compounding them.
- **Impact**: Anyone watching `/api/cache/stats` or `CacheMonitor` to detect a
  Tier2 regression (the warm cache that matters for seek/back-navigation) sees an
  artificially low, differently-scaled ratio and will never see a Tier2 miss
  count move — hiding exactly the regression class the metric exists to catch.
- **Suggested Fix**: Split the single miss branch into "tier1 miss" and
  "tier1+tier2 miss", and compute `tier2["hit_rate"]` as
  `tier2_hits / max(1, tier2_hits + tier2_misses)`, matching Tier1.

---

### B10-5: Thumbnail cache has no backstop eviction — `POST /api/library/reset` orphans the entire artwork tree with no cap

- **Severity**: MEDIUM
- **Dimension**: Caching & Invalidation
- **Location**: `auralis-web/backend/routers/library.py:134-181` (`reset_library`), `auralis-web/backend/core/thumbnail_cache.py`, `auralis-web/backend/routers/artwork.py:187-210`
- **Status**: NEW
- **Description**: The thumbnail cache's only cleanup mechanisms are
  `purge_thumbnails()` — called from exactly 3 sites in `routers/artwork.py`
  (extract, upload, delete-artwork) — and `reap_orphan_temp_files()`, which only
  removes stale `.tmp-*` crash-write staging files. There is no size cap, TTL, or
  orphan sweep for published thumbnails whose source album no longer exists,
  unlike the chunk cache's hard 512 MB `prune_chunk_directory()` ceiling.
  `POST /api/library/reset` deletes every `Album` row but never touches
  `~/.auralis/artwork/`.
- **Evidence**: `grep -rn "purge_thumbnails\|reap_orphan_temp_files"
  auralis-web/backend --include="*.py"` shows the only callers are the three
  sites in `routers/artwork.py`; `reset_library` and `repos.reset_library()`
  never reference `core/thumbnail_cache.py` or the artwork directory.
- **Impact**: Each use of the "nuke and rescan" workflow orphans every thumbnail
  (and full-resolution artwork file) for every pre-reset album in one shot, with
  no reclamation path — bounded only by how much artwork the library ever
  accumulated, times up to 5 size buckets each. Low urgency for a desktop app
  with small thumbnails, but genuinely uncapped, unlike the chunk cache.
- **Suggested Fix**: Have `reset_library` also clear `~/.auralis/artwork/`
  (including `thumbnails/`), or add a size-capped sweep to `thumbnail_cache.py`
  analogous to `ChunkCacheManager.prune_chunk_directory()`.

---

### B11-2: Seeking to (or past) the exact track duration silently drops the entire final chunk to zero samples but reports success

- **Severity**: MEDIUM
- **Dimension**: Seek & Buffering
- **Location**: `auralis-web/backend/core/chunk_boundaries.py:72-121` (`chunk_for_position`), `auralis-web/backend/core/stream_seek.py:260-267`, `auralis-web/backend/core/chunk_operations.py:242-258`
- **Status**: NEW
- **Description**: `chunk_for_position(position, total_chunks)` clamps only the
  lower bound and the chunk index; it has no access to `total_duration` so it
  cannot clamp `offset` to the audio actually available in the target chunk. For
  the last chunk, `extract_chunk_segment` emits exactly
  `total_duration - emitted_chunk_start(index)` seconds — the same quantity
  `chunk_for_position` computes as `offset` when `position == total_duration`. A
  seek to precisely `total_duration` (dragging the scrub bar to the end;
  `useEnhancedSeek.seekTo()` passes the raw slider value with no client clamp)
  yields `trim_samples == len(pcm_samples)` exactly, so
  `pcm_samples = pcm_samples[trim_samples:]` produces an empty array.
- **Evidence**:
  ```python
  # chunk_boundaries.py — sliver-avoidance only fires when there IS a next chunk
  if (index < total_chunks - 1 and emitted_chunk_length(index) - offset < min_remainder):
      ...   # for the LAST chunk this guard is a no-op
  # stream_seek.py:261-263
  trim_samples = round(seek_offset * processor.sample_rate)
  pcm_samples = pcm_samples[trim_samples:]   # empty when trim >= len
  ```
  `stream_protocol.send_pcm_chunk` on a 0-length array computes `num_frames = 0`,
  never runs its producer loop, sends no `audio_chunk_meta` or binary frame at
  all — and still returns `True` (only `abort_event` gates the return).
- **Impact**: Seeking to the very end of a track sends `audio_stream_start`
  (`is_seek=true`) followed immediately by `audio_stream_end` with
  `reason="completed"` and **zero audio delivered** — no error, no chunk. The UI
  jumps to 100% with no sound, indistinguishable from a normal end-of-track. It
  recovers (no hang) but silently discards the seek.
- **Siblings**: `stream_normal.py`'s seek-continuation path (`start_chunk` /
  `first_chunk_trim_samples`, :203-236) has the identical failure mode.
- **Suggested Fix**: Give `chunk_for_position` an optional `total_duration` and
  clamp `pos` to at most `total_duration - epsilon` (or clamp `offset` to leave
  at least `SEEK_MIN_CHUNK_REMAINDER`), so a seek to/past the end lands on the
  last audible instant; alternatively detect the empty chunk and send
  `reason="stopped"` with a recovery position.

---

### B11-3: A successfully-completed seek stream reports the whole track's `total_samples`/`duration`, not what was delivered

- **Severity**: MEDIUM (currently latent — no live consumer)
- **Dimension**: Seek & Buffering
- **Location**: `auralis-web/backend/core/stream_seek.py:413-421`, `auralis-web/backend/core/stream_normal.py:474-482`
- **Status**: NEW (adjacent gap left by CLOSED #4659, which fixed the `stopped_early`/`failed_chunks` branches but not the plain `reason="completed"` branch)
- **Description**: `send_stream_end`'s docstring (added by #4659) states:
  *"total_samples and duration describe what was actually delivered, not the whole
  track."* Both seek paths track `delivered_samples` and use it correctly for the
  `stopped_early` and `failed_chunks` branches — but the success (`else:`) branch
  ignores it and reports `processor.duration`/`total_frames` for the full track,
  even though a seek stream by definition delivers only the tail.
- **Evidence**:
  ```python
  # stream_seek.py:413-421 — "completed" branch ignores delivered_samples
  else:
      await controller._send_stream_end(
          websocket, track_id=track_id,
          total_samples=int(processor.duration * processor.sample_rate),  # full track
          duration=processor.duration,                                    # full track
          reason="completed",
      )
  ```
- **Impact**: Verified against the frontend — `useAudioStreamingCore.ts`'s
  `handleStreamEnd` reads these fields only for a debug `console.log`, and
  `completeStreaming` takes no sample/duration argument. So today this has no
  observable symptom, but it violates the documented wire contract and would
  silently mis-report to any future consumer (scrobbling, played-percentage) that
  trusts `audio_stream_end.total_samples` the way #4659 intended.
- **Siblings**: The two listed seek-capable "completed" branches only.
- **Suggested Fix**: Use `delivered_samples` / `delivered_samples / sample_rate`
  in the `else:` branch exactly as the sibling branches already do.

---

## LOW

### B3-1: Zero-duration track crashes chunk 0 via `WAVEncoder`'s empty-array guard

- **Severity**: LOW
- **Dimension**: Chunked Processing
- **Location**: `auralis-web/backend/core/chunk_operations.py:230-240`, `auralis-web/backend/core/chunked_processor.py:670-681`, `auralis-web/backend/core/encoding/wav_encoder.py:133-134`
- **Status**: NEW
- **Description**: If `total_duration` is exactly `0.0` (a valid header with zero
  data frames), `content_chunk_count(0.0)` still clamps to `max(1, ...) == 1`, so
  chunk 0 is processed rather than the track being rejected upstream.
  `extract_chunk_segment`'s chunk-0 branch computes
  `max_duration = min(15.0, 0.0) = 0.0` (chunk 0 is also `is_last` when
  `total_chunks == 1`), so `expected_samples = 0` and the padding/trim validation
  leaves a 0-sample array. `WAVEncoder.encode_and_save_from_path` then raises
  `ValueError("Cannot encode empty audio array")`.
- **Evidence**:
  ```python
  # chunk_operations.py — extract_chunk_segment, chunk_index == 0
  max_duration = min(chunk_duration, total_duration)   # min(15.0, 0.0) == 0.0
  expected_samples = int(round(max_duration * sample_rate))  # == 0
  extracted = processed_chunk[:expected_samples]             # 0-length
  # core/encoding/wav_encoder.py:133
  if audio.size == 0:
      raise ValueError("Cannot encode empty audio array")
  ```
- **Impact**: Not a crash and not audio corruption — the exception is caught by
  the per-chunk handler in `stream_enhanced.py`, so the stream ends with
  `reason="errored"`. Practical effect: a degenerate zero-length file can never
  be played (every attempt fails on chunk 0) instead of failing earlier with a
  clear "empty/corrupt file" message. Requires a probe that succeeds while
  reporting `duration_seconds == 0.0`.
- **Siblings**: None — very short but nonzero tracks hit the earlier
  `MIN_SAMPLES` check in `AudioProcessingPipeline.validate_audio`, which raises a
  clear, distinct error.
- **Suggested Fix**: Reject `total_duration <= 0` in
  `ChunkedAudioProcessor._load_metadata()` with a clear "empty audio file" error,
  or have `extract_chunk_segment` emit the untrimmed silence buffer instead of a
  0-length slice.

---

### B5-1: `TrackApiResponse.crest_factor` / `.centroid` are frontend-typed fields no backend path populates

- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**: `auralis-web/frontend/src/api/transformers/types.ts:102-103`, `auralis-web/frontend/src/api/transformers/trackTransformer.ts:56-57`, `auralis-web/frontend/src/types/domain.ts:46-47`
- **Status**: NEW
- **Description**: `TrackApiResponse` declares `crest_factor?: number | null` and
  `centroid?: number | null`, and `transformTrack()` maps them into
  `Track.crestFactor` / `Track.centroid`. No backend serialization path emits
  either key: `Track.to_dict()` (`auralis/library/models/core.py:194-227`),
  `DEFAULT_TRACK_FIELDS` (`routers/serializers.py:20-49`), and
  `schemas.TrackResponse` (`schemas.py:194-249`) all lack them. The engine
  computes `crest_factor_db` internally and the fingerprint endpoint exposes
  `crest_db` on a different response type.
- **Impact**: Both domain fields are always `undefined` at runtime. No component
  reads either, so this is dead/aspirational schema surface rather than a live
  bug — but the type promises data that does not exist.
- **Suggested Fix**: Either wire `crest_factor_db` into `Track.to_dict()` under
  the API naming convention, or drop the two dead fields from
  `TrackApiResponse`/`Track`/`trackTransformer.ts`.

---

### B6-1: `OriginCheckMiddleware`'s registration comment claims a causal order the code does not produce

- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `auralis-web/backend/config/middleware.py:424-437`
- **Status**: NEW
- **Description**: The inline comment says `OriginCheckMiddleware` "wraps
  TrustedHost (so the Host header is already known-good)". Verified against the
  installed `starlette==1.3.1` source (`add_middleware` → `insert(0, ...)`;
  `build_middleware_stack` → `for cls in reversed(middleware)`), the
  last-registered middleware is outermost and runs first. `OriginCheckMiddleware`
  is registered *after* `TrustedHostMiddleware`, so it runs **before** it — the
  reverse of the comment's claim. The top-of-function docstring (:397-404) and
  the "Resulting request-inbound order" comment (:417-419) are both correct; only
  this parenthetical is inverted.
- **Evidence**: Registration order in `setup_middleware` (top to bottom):
  RateLimit, TrustedHost, OriginCheck, NoCache, SecurityHeaders, CORS → actual
  inbound order: CORS → SecurityHeaders → NoCache → **OriginCheck → TrustedHost**
  → RateLimit → app.
- **Impact**: No functional or security bypass today —
  `OriginCheckMiddleware.dispatch()` (:292-318) never reads the `Host` header, so
  the assumption is not load-bearing. The risk is to future maintenance: a
  reader trusting this comment could extend origin/host cross-checks on the false
  premise that `Host` was already validated.
- **Siblings**: None — the other five `add_middleware` comments were each
  re-derived from the real insert/reverse mechanics and are self-consistent.
- **Suggested Fix**: Fix the comment to say `OriginCheckMiddleware` runs *before*
  `TrustedHostMiddleware` and drop the "Host header is already known-good" claim
  (lower-risk than reordering, since no behavior needs to change).

---

### B9-2: Two regression tests name a specific guarantee but verify nothing that could break it

- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `tests/regression/test_version_compatibility.py:404-420`, `tests/regression/test_data_migration.py:356-369`
- **Status**: NEW
- **Description**:
  - `test_deprecated_import_paths_still_work` wraps three legacy imports in
    `try/except ImportError`, computes `success = True/False`, then asserts `True`
    unconditionally — `success` is never checked, so the test passes whether all
    three imports succeed or all three raise.
  - `test_artwork_cache_directory_created` claims to verify `~/.auralis/artwork/`
    exists, but only builds a `Path` and asserts it `is not None` — a `Path`
    construction can never return `None`. It never calls `.exists()`/`.is_dir()`.
- **Evidence**:
  ```python
  assert True, "Import attempt should not crash"   # `success` unused
  artwork_dir = Path.home() / '.auralis' / 'artwork'
  assert artwork_dir is not None                    # Path() is never None
  ```
- **Impact**: Both read as guard rails for real regressions (deleted legacy
  import path; artwork directory not created) but cannot fail no matter what the
  production code does.
- **Siblings**: `test_old_processing_parameters_mapped`
  (`test_version_compatibility.py:422-434`) constructs `HybridProcessor(config)`
  with a *default* config and asserts only `processor is not None` — it never
  exercises the legacy→current parameter mapping its docstring claims to guard.
- **Suggested Fix**: Assert `success is True` for the import test; call the
  startup path and assert `artwork_dir.exists()` (or delete the test if creation
  is intentionally lazy); pass an actual legacy parameter name through
  `UnifiedConfig`/`HybridProcessor` and assert it took effect.

---

## Relationships

**Shared root cause — "fix applied at one call site, sibling missed":**
B4-1, B10-1, and B11-1 are all the same failure mode at three different layers.
Each has a documented predecessor fix that was correct for its own site:
#4735 (reference fallback), #4358 (`SimpleChunkCache` file signature), and
#5062 (`SeekableSource` close). In every case a structurally identical sibling
was left unpatched, and in B11-1's case the predecessor's own comment predicted
it. A grep-for-siblings step at fix time would have caught all three.

**Cluster — stale bytes survive invalidation:** B10-1 (key omits the signature)
and B10-2 (clear does not reach disk) compound. With both present, there is
currently *no* reliable way for a user to force a chunk to be reprocessed: the
automatic path never invalidates, and the manual path does not delete the bytes.
Fix B10-2 first — it restores a working escape hatch even before B10-1 lands.

**Cluster — the `reason` / `delivered_samples` wire contract (#4659/#4790):**
B2-1 and B11-3 are both incomplete adoptions of the same contract. #4659 added
the fields; the backend populates `reason` correctly but under-populates
`total_samples` on the success branch (B11-3), and the frontend ignores `reason`
entirely (B2-1). Together they mean the contract's stated purpose — letting a
client distinguish a finished stream from a truncated one — is not achieved
end-to-end despite both closed issues.

**Cluster — shared default executor pressure:** B7-1 (unbounded blocking call on
every play) interacts with open #4815 (stream cancellation orphans a live
executor thread). Both consume the same `min(32, cpu_count+4)` default pool;
either alone is survivable, together they make exhaustion substantially more
likely on a library containing even one problematic file.

**Cluster — vacuous tests:** B9-1 and B9-2 share an anti-pattern (`assert True`
as a terminal assertion) across `tests/security/` and `tests/regression/`. Worth
a single grep-driven sweep rather than three separate fixes.

---

## Prioritized Fix Order

1. **B10-2** (HIGH) — restores the user's only cache-troubleshooting lever, and
   is a prerequisite for validating any fix to B10-1. Small, self-contained.
2. **B10-1** (HIGH) — the fix already exists in `SimpleChunkCache` (#4358); this
   is porting a known-good pattern one layer over. Highest user-visible payoff.
3. **B11-1** (HIGH) — two `processor.close()` calls plus one glob widening.
   Trivially small relative to a permanent, unbounded disk leak.
4. **B4-1** (HIGH) — silent correctness corruption of an explicitly requested
   feature. Fix the config restore, and add a pool-reuse case to
   `tests/backend/test_reference_mode_wiring_4735.py`, which currently cannot
   catch this.
5. **B7-1** (HIGH) — one `asyncio.wait_for` wrapper at three call sites; the
   pattern to copy is three files away.
6. **B10-3 / B10-4** (MEDIUM) — both in `cache/manager.py`; fix alongside
   B10-1/B10-2 while the file is already open. B10-4 in particular should land
   *before* the others so the metrics can validate them.
7. **B2-1** (MEDIUM) — completes the #4659/#4790 contract end-to-end; frontend
   change, coordinate with B11-3.
8. **B11-2** (MEDIUM) — user-reachable via an ordinary scrub-to-end gesture.
9. **B11-3** (MEDIUM, latent) — three-line change; do it with B2-1 so the
   contract is fixed on both ends in one pass.
10. **B10-5** (MEDIUM) — unbounded but slow-growing; no correctness impact.
11. **B9-1** (MEDIUM) — false confidence on security tests; cheap to fix.
12. **B3-1, B5-1, B6-1, B9-2** (LOW) — opportunistic. B6-1 is a one-line comment
    fix; B9-2 pairs naturally with B9-1.

---

## Dimensions with No New Findings

- **Dimension 1 (Route Handler Correctness)** — full sweep of all 26 files in
  `routers/` plus `config/routes.py`. Every checklist item (async correctness,
  validation, error handling, idempotency, route ordering, DI, missing
  endpoints, path security) is already hardened, with inline comments citing the
  issue that fixed it. Two candidates matched open issues #4817 and #4814 and
  were deduped.
- **Dimension 8 (Performance & Resource Management)** — blocking calls are
  consistently wrapped in `asyncio.to_thread`/`asyncio.wait_for`; look-ahead
  chunk processing eliminates streaming gaps; both chunk caches are size-bounded
  with LRU/mtime eviction; SQLAlchemy pooling is explicitly configured;
  repository list/search methods use `selectinload()`; executors are singleton
  with shutdown hooks; every `asyncio.Queue` is bounded. Two candidates matched
  open issues #4653 and #4857/#4766 and were deduped.

## Notable Verifications (no regression)

- **#4737** (per-chunk whole-file decode) — `SeekableSource.resolve()` is
  memoized per processor instance and triggers on capability, not extension.
- **#4557** (seek landing 5s past target) — `chunk_for_position` /
  `emitted_chunk_start` used correctly, including in the `audio_stream_start`
  response fields.
- **#4563** (in-flight frames from a superseded stream) — stream epoch stamped
  on `audio_stream_start`/`audio_chunk_meta` and filtered on by the frontend.
- **#3806 / #5083** (rapid-seek interleaving) — `handle_seek` awaits the prior
  task before starting a new one; `drain_cancelled_task` correctly lets a
  caller-targeted cancellation escape.
- **#4367 / #3832** (level continuity across cache hits) —
  `note_cached_chunk_level` restores the true trailing gain from cache metadata.
- **#4919** (`core/encoding/wav_encoder.py` bare `OSError` misclassification) —
  fix present: it now raises `WAVEncoderError`, and `processing_engine.py:68-69`
  inserts that class at position 0 of `_ERROR_CATEGORIES`, ahead of the generic
  `OSError`/`ValueError` entries. The duplication hotspot flagged in the audit
  brief is closed.
- **#3222** (SQLite `OperationalError` → 500 instead of 503) — `handle_query_error`
  still present and correctly used where adopted.
- **CORS / static mount / middleware ordering / lifespan symmetry** — each
  re-derived from the actual code (including the installed Starlette source for
  stack construction) rather than assumed. All correct.
- **Bare `except:`** — none exist anywhere under `auralis-web/backend/`.
- **`except Exception: pass` returning a false success** — none found.

---

## Deduplicated Against Existing Issues

The following were independently rediscovered by dimension agents and confirmed
still present in the live code, but match OPEN issues and are **not** re-reported
as findings: #3873, #3878, #3879, #3884, #3886, #3891, #3893, #3903, #3909,
#4234, #4245, #4289, #4381, #4431, #4582, #4625, #4629, #4653, #4654, #4655,
#4666, #4676, #4677, #4680, #4703, #4704, #4709, #4710, #4711, #4750, #4761,
#4766, #4770, #4814, #4815, #4817, #4838, #4857, #4861, #4930, #4942, #4953,
#5009, #5018, #5032, #5048, #5050, #5051, #5056, #5057, #5066, #5077, #5079,
#5081, #5082, #5093.

Issue **#3838** (~28 endpoints missing `response_model=`) was explicitly excluded
from re-reporting as a known LARGE deferred item.

---

*Generated by `/audit-backend` on 2026-08-13. Findings were produced by a fresh
read of the current source; no prior audit report was consulted.*
