# Integration Audit — 2026-08-13

Cross-layer audit of the 9 critical data flows between the Auralis audio engine
(`auralis/`), the FastAPI backend (`auralis-web/backend/`), and the React
frontend (`auralis-web/frontend/`). Every flow was traced at **deep** depth
against the current working tree; no prior audit report was used as a source.

Dedup baseline: 292 OPEN + 2000 CLOSED issues. Findings that matched an open
issue are recorded as *Existing* and not re-filed.

---

## Executive Summary

| Severity | New findings |
|---|---|
| CRITICAL | 1 |
| HIGH | 5 |
| MEDIUM | 3 |
| LOW | 9 |
| **Total** | **18** |

Plus 13 existing open issues re-confirmed as still present in current code (none
regressed, none escalated).

### Key themes

**1. The boundary is far healthier than the layers' internals.** Flow 3 (Audio
Enhancement) and Flow 5 (WebSocket Lifecycle) produced zero and two LOW new
findings respectively, and the specific hazards the audit brief asked to hunt
for — enhancement settings missing from the chunk cache key, an
`audio_chunk_meta`/`audio_chunk` protocol mismatch, a naive
`ceil(duration/CHUNK_DURATION)` bypassing `content_chunk_count()` — were all
investigated and **disproved**. Both cache tiers embed `preset` and `intensity`;
`audio_chunk_meta` is a deliberately internal frame fused into a public
`audio_chunk` by `websocketConnectionCore.ts`; the one bare `ceil()` found
(`stream_normal.py:186`) belongs to the genuinely non-overlapping normal path.

**2. The most impactful defects are all "one branch of a two-branch path was
never updated."** The CRITICAL and three of the five HIGHs share this exact
shape: a guard, a fix, or an eager-load exists and works on the path its author
was looking at, and is simply absent from the sibling path.

- `chunk_for_position()`'s sliver guard is gated on `index < total_chunks - 1`,
  so it never protects the last chunk (**F8-2**, CRITICAL).
- `setSeekOffset()` is called in the fresh-engine branch and not in the
  resume branch that every real seek actually takes (**F8-1**).
- The `stream_epoch` guard runs on the live chunk path and not on the
  pending-chunk flush path (**F1-1**).
- `PlaylistRepository` chains `selectinload` into `Track.artists`/`genres`;
  `AlbumRepository` — its direct sibling — does not (**F2-1**).

**3. Backend-vs-frontend type declarations drift in one direction: the wire
carries more than the TypeScript admits.** Four independent findings across
three flows (**F4-3**, **F5-3**, **F9-3**, and open #4680) are all "the backend
emits a value the frontend's literal union does not declare." Three are inert
today only because no consumer branches on the field yet.

### Most impactful boundary mismatches

1. **F8-2 (CRITICAL)** — pressing `End` on the scrubber, or dragging it to the
   right edge, delivers **zero audio** while the stream reports
   `reason="completed"` with the full track's sample count. Verified empirically.
2. **F9-1 (HIGH)** — the queue read model silently drops entries it cannot
   resolve but keeps engine indices, so after the background auto-scanner
   removes a missing file, a queue edit deletes or moves the **wrong track**.
3. **F2-1 (HIGH)** — every track row on every album detail page renders with a
   blank artist, 100% reproducible, because of a single missing nested
   eager-load.

---

## Flow Coverage Matrix

| # | Flow | Depth | Boundary checks | New findings | Existing confirmed |
|---|------|-------|-----------------|--------------|--------------------|
| 1 | Track Playback | deep | 10 checked, 8 clean | 1 HIGH, 1 MEDIUM | — |
| 2 | Library Browsing | deep | 13 checked, 11 clean | 2 HIGH | #4709 |
| 3 | Audio Enhancement | deep | 13 checked, 8 clean | **0** | #4587, #4677, #4707, #4425, #4760 (+7 LOW) |
| 4 | Library Scanning | deep | 17 checked, 14 clean | 1 MEDIUM, 1 LOW | #4820 |
| 5 | WebSocket Lifecycle | deep | 8 checked, 6 clean | 2 LOW | #4680 |
| 6 | Fingerprint & Similarity | deep | 9 checked, 9 clean* | 3 LOW | #4629 |
| 7 | Artwork | deep | 11 checked, 11 clean* | 2 LOW | — |
| 8 | Seek & Rebuffer | deep | 11 checked, 7 clean | 1 CRITICAL, 1 HIGH, 1 LOW | #4815 |
| 9 | Queue & Playback State | deep | 10 checked, 8 clean | 1 HIGH, 1 MEDIUM, 1 LOW | — |

\* Flows 6 and 7 had every *listed* checklist boundary come back clean; their
findings are adjacent concerns surfaced during the trace (URL construction,
cache invalidation, DPR) rather than failures of a checklist item.

Per-flow checklist detail (schema match / error handling / timeouts / data types
/ null handling / case conversion) is recorded in each flow's "Boundary check
status" table, reproduced in condensed form under each finding group below.

---

## Findings

### CRITICAL

#### INT-01: Seeking to the end of a track delivers zero audio while reporting `reason="completed"`

- **Severity**: CRITICAL
- **Flow**: 8 — Seek & Rebuffer
- **Boundary**: Frontend `ProgressBar` → WS `seek` → Backend `stream_seek.py` / `stream_normal.py`
- **Location**: `auralis-web/frontend/src/components/player/ProgressBar.tsx:166-169` → `auralis-web/backend/ws_handlers/playback_commands.py:309-312` → `auralis-web/backend/core/chunk_boundaries.py:99-121` → `auralis-web/backend/core/stream_seek.py:260-267` (and `auralis-web/backend/core/stream_normal.py:190-192,216-221`)
- **Status**: NEW
- **Description**: `chunk_for_position()` clamps the chunk *index* to `total_chunks - 1` but never clamps the derived `offset` against the **actual** remaining content of the last chunk. The last chunk's real emitted length is `total_duration - emitted_chunk_start(index)`, almost always shorter than the nominal `CHUNK_INTERVAL` that `emitted_chunk_length()` returns — its own docstring concedes this ("ignoring the last-chunk short case"). The `SEEK_MIN_CHUNK_REMAINDER` sliver guard that would otherwise advance past a too-short remainder is gated on `index < total_chunks - 1`, so it **never applies to the last chunk**. Nothing upstream clamps either: `handle_seek` validates only `position >= 0` and finite, with no upper bound against track duration.
- **Evidence** (empirically verified by executing the real module, not by reading it):
  ```
  CHUNK_DURATION 15.0  INTERVAL 10.0  OVERLAP 5.0
  dur=97.0   chunks=10  seek@end -> idx=9  offset=2.000  emitted_start=95.0  real_remaining=2.000  trims_entire_chunk=True
  dur=180.0  chunks=18  seek@end -> idx=17 offset=5.000  emitted_start=175.0 real_remaining=5.000  trims_entire_chunk=True
  dur=240.5  chunks=24  seek@end -> idx=23 offset=5.500  emitted_start=235.0 real_remaining=5.500  trims_entire_chunk=True
  ```
  ```python
  # chunk_boundaries.py:112-119 — the guard that cannot protect the last chunk
  if (
      index < total_chunks - 1
      and emitted_chunk_length(index) - offset < min_remainder
  ):
  ```
  ```python
  # stream_seek.py:261-263 — trim_samples >= len(pcm_samples) yields an empty
  # array with no error and no warning
  if chunk_idx == start_chunk_idx and seek_offset > 0:
      trim_samples = round(seek_offset * processor.sample_rate)
      pcm_samples = pcm_samples[trim_samples:]
  ```
  ```ts
  // ProgressBar.tsx:166-169 — End sets the position to duration exactly
  case 'End':
    event.preventDefault();
    newPosition = duration;
  ```
  Because `chunk_idx + 1 < processor.total_chunks` is false for the last chunk, no further chunk is attempted; the loop falls through to the completion branch and reports `total_samples = int(processor.duration * processor.sample_rate)` — the **whole track's** count — for a stream that delivered no PCM at all. `send_pcm_chunk` computes `num_frames = 0` for an empty array, so zero binary frames go out. The normal (unenhanced) path reaches the same state by a different route: `sf.read()` at/past EOF returns fewer frames than requested (deliberately un-padded per #2124).
- **Impact**: `End` on the scrubber and dragging the thumb to the right edge are ordinary interactions — the former is the standard keyboard-accessibility affordance. Both silently produce no audio with a success report, so the frontend has no error path to take: `audio_stream_end(reason="completed")` simply dispatches `completeStreaming(...)`. This is the "truncated playback / dropped audio chunks across the boundary" case the integration severity table names as CRITICAL. It compounds with INT-03: with `currentTime` left short of `trackDuration`, the `nearEnd` auto-advance heuristic may also never fire, leaving playback silently stalled.
- **Suggested Fix**: Backend, in `chunk_for_position()`. Accept `total_duration` and clamp `pos` to it before deriving `index`/`offset`, and bound `offset` so the remaining length of the target chunk can never go negative — which also lets the sliver guard finally cover the last chunk. Apply the same correction to `stream_normal.py`'s `start_chunk`/`first_chunk_trim_samples` derivation. Clamping `position` in `handle_seek` against the known duration is worthwhile defense-in-depth but does not by itself fix the near-end sliver case.

---

### HIGH

#### INT-02: The queue read model drops unresolvable entries but keeps engine indices, so index-based mutations hit the wrong track

- **Severity**: HIGH
- **Flow**: 9 — Queue & Playback State
- **Boundary**: Engine queue → Backend queue service → Frontend (and back, as an index)
- **Location**: `auralis-web/backend/services/queue_enrichment.py:97-104` and `auralis-web/backend/services/queue_service.py:204-214` → `auralis-web/frontend/src/hooks/player/useQueueMutations.ts:203-229` → `auralis-web/backend/services/queue_service.py:445-462`
- **Status**: NEW
- **Description**: `QueueEnricher.enrich_tracks()` deliberately **drops** engine queue entries it cannot resolve to a `TrackInfo`. `QueueService.get_queue_info()` substitutes that shortened list for `info["tracks"]` but leaves every positional field untouched — `current_index`, `track_count`, `has_next`, `has_previous` all still describe the **full** engine list (`auralis/player/components/queue_manager.py:409-422`). The response is internally inconsistent (`len(tracks) != track_count`), and the frontend computes `removeTrack(index)` / `reorderTrack(fromIndex, toIndex)` from its own — shortened — array and posts those integers straight back, where `remove_track_from_queue` validates them against `queue_manager.get_queue_size()` (the full size) and applies them to the full engine list.
- **Evidence**:
  ```python
  # queue_enrichment.py:99-104 — no else, no index bookkeeping
  for entry, fp in zip(entries, filepaths):
      if isinstance(entry, TrackInfo):
          resolved.append(entry)
      elif fp is not None and fp in by_fp:
          resolved.append(by_fp[fp])
  ```
  ```python
  # queue_service.py:208-212 — tracks replaced, current_index never recomputed
  tracks = await self._enricher.enrich_tracks(info.get("tracks", []))
  info["tracks"] = tracks
  info["current_track"] = self._enricher.resolve_current_track(
      tracks, raw_current, info.get("current_index", 0)
  )
  ```
  ```ts
  // useQueueMutations.ts:203-209 — array position posted straight back
  const removeTrack = useCallback(
    (index: number): Promise<void> =>
      runOptimistic(() => dispatch(reduxRemoveTrack(index)),
        () => apiDelete(`/api/player/queue/${index}`), 'REMOVE_TRACK_ERROR'),
  ```
  Reachability is confirmed, not hypothetical: the background auto-scanner removes missing files from the library and broadcasts about it —
  ```python
  # services/library_auto_scanner.py:330-335
  if removed:
      logger.info(f"🗑️  Removed {removed} missing tracks from library")
      await connection_manager_safe_broadcast(
          self._connection_manager,
          {"type": "library_tracks_removed", "data": {"count": removed}})
  ```
  — so a queued track whose file has disappeared is deleted from the DB while still sitting in the engine queue, which is exactly the condition that makes `enrich_tracks` drop it. `resolve_current_track` compensates by matching the *current* track on filepath, but nothing compensates for the index the client sends back.
- **Impact**: After the auto-scanner prunes a queued track, the user's next queue edit deletes or moves a **different** track than the one they clicked, and the panel highlights the wrong "now playing" row. The queue is user data and the corruption is silent; recovery means rebuilding the queue. Low frequency, high blast radius.
- **Suggested Fix**: Backend. Make the drop index-preserving — either emit a placeholder for unresolvable entries so positions stay 1:1 with the engine, or return an explicit engine index alongside each track and have the mutation endpoints consume that instead of an array position. Either way, recompute `track_count`/`current_index`/`has_next`/`has_previous` from the emitted list so the response stops contradicting itself.

#### INT-03: The seek resume path never restores the position tracker's seek offset

- **Severity**: HIGH
- **Flow**: 8 — Seek & Rebuffer
- **Boundary**: Backend `audio_stream_start(is_seek=true)` → Frontend `useEnhancedStreamStart.handleStreamStart`
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancedStreamStart.ts:86-101` (resume branch, returns early) vs `:146-148` (the sole `setSeekOffset` call site) → `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts:192-201` → `auralis-web/frontend/src/services/audio/PlaybackPositionTracker.ts:63-90`
- **Status**: NEW (adjacent to #2259, whose fix is intact and correct for the branch it covers)
- **Description**: `useEnhancedSeek.seekTo()` calls `stopPlayback()` (which resets `seekOffsetSeconds` to 0) and `pcmBufferRef.current?.reset()` on every seek, but never nulls the refs. So when the follow-up `audio_stream_start(is_seek: true)` arrives, the resume guard `isSeek && core.playbackEngineRef.current && core.pcmBufferRef.current` is true for **every ordinary seek**, not only the WS-reconnect case its comment describes. That branch returns at line 101, never reaching the `engine.setSeekOffset(seekPosition)` call at line 147.
- **Evidence**: A repo-wide grep confirms `setSeekOffset` has exactly one call site in the whole frontend outside the audio service itself:
  ```
  services/audio/PlaybackPositionTracker.ts:63   setSeekOffset(offsetSeconds: number): void {
  services/audio/AudioPlaybackEngine.ts:236      setSeekOffset(offsetSeconds: number): void {
  hooks/enhancement/useEnhancedStreamStart.ts:147        engine.setSeekOffset(seekPosition);
  ```
  ```ts
  // useEnhancedStreamStart.ts:87-101 — taken on every seek with a live engine
  if (isSeek && core.playbackEngineRef.current && core.pcmBufferRef.current) {
    ...
    return;                              // setSeekOffset never called
  }
  ```
  `getCurrentPlaybackTime()` returns `seekOffsetSeconds + samplesPlayed / sampleRate`, so with the offset stuck at 0 it counts up from zero.
- **Impact**: After every seek the progress bar and time display jump back toward 0:00 and count up from there — the audio is correct (the backend delivered the right samples), but the UI looks like the seek reverted. It also undermines `PlaybackSessionContext`'s auto-advance heuristic (`nearEnd = currentTime >= trackDuration - 0.5`): a seek into the last ~30 s leaves `currentTime` far below `trackDuration` while the track actually finishes, so advancing to the next queued track does not fire.
- **Suggested Fix**: Frontend. Hoist the `setSeekOffset` call so it runs unconditionally whenever `isSeek && seekPosition > 0`, regardless of which branch handles the start.

#### INT-04: `pendingChunksRef` flush skips the stream-epoch guard the live chunk path enforces

- **Severity**: HIGH
- **Flow**: 1 — Track Playback
- **Boundary**: Backend WS stream (superseded task's in-flight frames) → Frontend `useEnhancedStreamStart.ts`
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts:244-264` (guarded) vs `auralis-web/frontend/src/hooks/enhancement/useEnhancedStreamStart.ts:187-206` (unguarded) → enabler: `auralis-web/frontend/src/hooks/enhancement/useEnhancedPlayCommand.ts:73-79`
- **Status**: NEW (a distinct gap from the closed #4563 fix, not a regression of it)
- **Description**: #4563 added a per-stream `stream_epoch` so frames still in flight from a superseded stream get dropped rather than landing in the new stream's buffer. The guard lives in `handleChunk` and runs *before* the "buffer not yet initialized" branch that queues early chunks. But `useEnhancedPlayCommand` starts a new track by nulling `pcmBufferRef`/`pendingChunksRef` directly without calling `core.cleanupStreaming()` — the only place that resets the core-private `streamEpochRef` (`useAudioStreamingCore.ts:198`). Between sending the new play command and receiving its `audio_stream_start`, `streamEpochRef` still holds the *previous* epoch, so an old-epoch frame passes the check and is queued. When the new `audio_stream_start` arrives it bumps the epoch and then flushes every queued entry into the fresh buffer with **no epoch or track_id check at all**.
- **Evidence**:
  ```ts
  // useEnhancedStreamStart.ts:191-201 — flush path, no epoch filter
  const queuedChunks = [...core.pendingChunksRef.current];
  core.pendingChunksRef.current = [];
  for (const queuedMessage of queuedChunks) {
    const { samples } = decodeAudioChunkMessage(queuedMessage, message.data.sample_rate, message.data.channels);
    buffer.append(samples);
  }
  ```
  Verified: `streamEpochRef` appears at only four lines in the core (`164` declare, `198` reset inside `cleanupStreaming`, `245` read, `431` bump), and `useEnhancedPlayCommand` never calls `cleanupStreaming`.
- **Impact**: On a rapid track switch (skip, or re-clicking play while a stream drains), a stray PCM frame from the **previous, different track** can be spliced into the head of the new track's buffer — the exact symptom class #4563 exists to prevent, through a path its test suite never exercises (every test in `useAudioStreamingCore.epoch.test.tsx` pre-seeds a non-null buffer, so the queue-then-flush branch is never hit).
- **Suggested Fix**: Frontend. Either stamp each queued message with the epoch current at queue time and filter at flush, or have `useEnhancedPlayCommand` clear the epoch ref before sending a new play command so stray frames are rejected outright rather than deferred.

#### INT-05: `AlbumRepository.get_by_id()` never eager-loads `Track.artists`/`Track.genres`, so every album's track list renders with a blank artist

- **Severity**: HIGH
- **Flow**: 2 — Library Browsing
- **Boundary**: Engine (repository) → Backend (serializer) → Frontend (render)
- **Location**: `auralis/library/repositories/album_repository.py:56` → `auralis-web/backend/routers/albums.py:185` → `auralis/library/models/core.py:163-206` → `auralis-web/frontend/src/components/library/Items/tables/TrackTableRowItem.tsx:91`
- **Status**: NEW (distinct from the CLOSED #4568, a frontend camelCase-misread on the same endpoint; that fix is still correctly in place, this is a separate backend data-loss bug underneath it)
- **Description**: The detail eager-load set loads the `Track` rows but never chains into their relationships:
  ```python
  _ALBUM_DETAIL_OPTIONS = (joinedload(Album.artist), selectinload(Album.tracks))
  ```
  The repository then calls `session.expunge_all()` and closes the session. `Track.to_dict()` reads `self.artists` inside a bare `try/except Exception`, which swallows the resulting `DetachedInstanceError` and degrades `artists` to `[]`, `genres` to `[]`, and `album` to `None`. This is precisely the pattern CLAUDE.md names as a real finding, and `Track.to_dict()` is also the one serializer that hand-rolls these guards instead of using `_safe_collection()`/`_safe_scalar()` (`auralis/library/models/core.py:37,66`), which log a WARNING naming the missing eager-load — so the failure is entirely silent.
- **Evidence**: `PlaylistRepository.get_by_id()` is the correct sibling and does chain them:
  ```python
  # playlist_repository.py:130-132
  selectinload(Playlist.tracks).selectinload(Track.artists),
  selectinload(Playlist.tracks).selectinload(Track.genres),
  selectinload(Playlist.tracks).selectinload(Track.album)
  ```
  The flow-2 trace reproduced the failure against a real SQLite-backed session (not a mock), obtaining `{'album': None, 'artists': [], 'genres': []}` for a track added with all three populated. No existing test catches it: `tests/backend/test_album_tracks_key_contract.py` uses a plain `_FakeTrack` with no `to_dict()`, and `tests/backend/test_albums_api.py` mocks the repository entirely — `Mock()` objects never raise `DetachedInstanceError`.
- **Impact**: Every track row on every album detail page shows a blank artist — 100% reproducible, not a race. It propagates: "Play Album" pushes `album.tracks[0]` (artist `''`) into the player, so the Now Playing bar also shows no artist when playback starts from an album. Genres are silently empty everywhere this payload is consumed.
- **Suggested Fix**: Backend. Chain the same nested eager-loads `PlaylistRepository` already uses. Separately, migrate `Track.to_dict()`'s three hand-rolled `except Exception` blocks to `_safe_collection()`/`_safe_scalar()` so the next missing eager-load announces itself in the log instead of silently emptying a field.

#### INT-06: Album-grid fingerprint decoration re-fetches every accumulated album on each page load

- **Severity**: HIGH
- **Flow**: 2 — Library Browsing
- **Boundary**: Frontend (album grid) → Backend (`GET /api/albums/{id}/fingerprint`)
- **Location**: `auralis-web/frontend/src/components/library/Items/albums/CozyAlbumGrid.tsx:75-81` → `auralis-web/frontend/src/hooks/fingerprint/useAlbumFingerprint.ts:104-136` → `auralis-web/backend/routers/albums.py:200-295`
- **Status**: NEW (the 5 related issues found during dedup are all CLOSED and address different aspects: #3334 fixed the *within-one-album* N+1, #3644 added the concurrency cap, #4142/#4937/#4595 are unrelated bugs on the same hook). The gap is self-acknowledged in the code: `useAlbumFingerprint.ts:93-95` still reads *"For production, consider implementing a batch endpoint like GET /api/albums/fingerprints?ids=1,2,3"*.
- **Description**: `CozyAlbumGrid` computes `albumIds` from **every album across all accumulated infinite-scroll pages**, not the virtualized subset, and hands the full list to `useAlbumFingerprints()`, which issues one `fetch('/api/albums/{id}/fingerprint')` per ID at a concurrency of 10. Each request costs two DB round trips plus a NumPy median. There is no batch endpoint.
- **Evidence**: The cost is **quadratic, not linear** — a detail the per-flow trace understated and which I confirmed directly. The React Query key is the full sorted ID list:
  ```ts
  // useAlbumFingerprint.ts:106
  queryKey: ['album-fingerprints-batch', [...albumIds].sort().join(',')],
  ```
  and the `queryFn` loops over **all** of `albumIds`. Loading a new page changes the key, so nothing from the previous key is reused: page 1 costs 50 requests, page 2 costs 100 (all re-fetched), page 3 costs 150 — `50·N(N+1)/2` after N pages, not `50·N`.
  ```ts
  // CozyAlbumGrid.tsx:75-81
  const albums = useMemo(() => data?.pages.flatMap(page => page.albums) ?? [], [data?.pages]);
  const albumIds = useMemo(() => albums.map(album => album.id), [albums]);
  const { fingerprints } = useAlbumFingerprints(albumIds);
  ```
- **Impact**: Scrolling five pages of a large library issues ~750 requests where ~250 would already be too many, all against the single-threaded ASGI loop that also serves audio streaming — the hook's own #3644 comment states that saturating it "starves audio-streaming requests of I/O time." The payload is decorative (a gradient placeholder). Not CRITICAL because the concurrency cap and React Query's 5–30 min cache bound the damage within a page.
- **Suggested Fix**: Add the batch endpoint the frontend comment already specifies (`GET /api/albums/fingerprints?ids=…`, one `IN`-query) and call it once per newly loaded page. Independently, key the query per page (or fetch only the near-viewport subset) so an additional page stops re-fetching everything before it.

---

### MEDIUM

#### INT-07: `queue_changed`'s hydration fallback broadcasts raw engine entries, leaking `filepath` and violating the message's own type

- **Severity**: MEDIUM
- **Flow**: 9 — Queue & Playback State
- **Boundary**: Backend (WS broadcast) → Frontend (Redux queue slice)
- **Location**: `auralis-web/backend/services/queue_service.py:152-164` → `auralis-web/frontend/src/hooks/player/useQueueSubscription.ts:47-55`, `auralis-web/frontend/src/types/ws/queue.ts:36-47`
- **Status**: NEW
- **Description**: `_broadcast_queue_changed` hydrates each engine entry into a `TrackInfo` and calls `model_dump()`, which correctly honours `filepath: str = Field(exclude=True)` (`auralis-web/backend/player_state.py:42-43`, "Server-only; excluded from API responses (#3205)"). When hydration fails — the batched `get_by_ids` raised, the id is absent from the DB, or `library_manager is None` — it falls back to `dict(entry)` (the raw engine entry, which the method's own docstring describes as carrying "only id + filepath") or `{'filepath': entry}`. Those go straight onto the wire, and the frontend does `if (data.tracks) dispatch(reduxSetQueue(data.tracks))` with no shape validation.
- **Evidence**:
  ```python
  # queue_service.py:152-157 (and the identical pair again in the except at :158-163)
  if track_dict is None:
      if isinstance(entry, dict):
          track_dict = dict(entry)
      else:
          track_dict = {'filepath': entry}
  ```
  ```ts
  // types/ws/queue.ts:38-40 — the declared contract this violates
  data: { tracks: TrackInfo[]; ... }
  ```
  The frontend `TrackInfo` has no `filepath`, so these entries are not merely extra-keyed — they are missing every required field.
- **Impact**: Two problems from one fallback. Server filesystem paths reach the client on exactly the path #3205/#4586 spent effort removing them from (mitigated to MEDIUM by the desktop-only, localhost-bound deployment), and the queue UI renders blank rows while untyped entries corrupt a camelCase-typed slice — the same defect class as open #5009, via a different ingress.
- **Suggested Fix**: Backend. Emit a schema-valid placeholder instead of the raw entry, so the payload can never carry `filepath` and always satisfies `TrackInfo[]`. Fix alongside INT-02: this fallback is also what keeps the WS queue length in agreement with the engine while the REST path drops entries, so the two surfaces currently disagree about how long the queue is.

#### INT-08: Settings "Scan Now" times out client-side at 30 s against a scan the backend allows 3600 s

- **Severity**: MEDIUM
- **Flow**: 4 — Library Scanning
- **Boundary**: Frontend (Settings dialog) → Backend (`POST /api/library/scan`)
- **Location**: `auralis-web/frontend/src/services/settingsService.ts:147-149` → `auralis-web/frontend/src/utils/apiRequest.ts:19` → `auralis-web/backend/routers/library_scan.py:148,160`
- **Status**: NEW
- **Description**: `POST /api/library/scan` is synchronous — the handler blocks on `asyncio.wait_for(asyncio.shield(scan_future), timeout=scan_timeout)` for the entire scan, up to the 3600 s default. `triggerLibraryScan()` passes no `timeoutMs`, so it inherits `DEFAULT_TIMEOUT_MS = 30000`. Any scan longer than 30 s — essentially any non-trivial first import — aborts client-side and `useSettingsDialog.ts:149-158` unconditionally sets `'Failed to start scan'`, even though the scan was accepted and is running (per open #4820, the client abort does not reach the scanner thread).
- **Evidence**:
  ```ts
  // settingsService.ts:147-149 — no timeoutMs override
  await post(ENDPOINTS.LIBRARY_SCAN, { directories, recursive: true, skip_existing: true });
  ```
  ```python
  # library_scan.py:148,160
  scan_timeout = float(os.environ.get("AURALIS_SCAN_TIMEOUT", "3600"))
  result = await asyncio.wait_for(asyncio.shield(scan_future), timeout=scan_timeout)
  ```
  The sibling entry point is unaffected: `useLibraryScan.ts:103-108` uses a raw `fetch()` with only its own `AbortController`.
- **Impact**: Clicking "Scan Now" shows a red "Failed to start scan" while `ScanStatusCard` simultaneously shows live WebSocket progress — the two UI signals directly contradict each other. A user who believes the error and retries gets a 409 "Scan already in progress" from the still-running first attempt, i.e. a second misleading failure.
- **Suggested Fix**: Either pass a `timeoutMs` matching `AURALIS_SCAN_TIMEOUT` on this call, or make the endpoint return 202 immediately and let the existing WS/`scan/status` channel carry completion — the latter also removes the need for any long client timeout.

#### INT-09: The play command dispatches raw snake_case REST JSON into a camelCase-typed Redux field

- **Severity**: MEDIUM
- **Flow**: 1 — Track Playback
- **Boundary**: Backend `GET /api/library/tracks/{track_id}` → Frontend `useEnhancedPlayCommand.ts`
- **Location**: `auralis-web/backend/routers/tracks.py:120-121` → `auralis-web/frontend/src/hooks/enhancement/useEnhancedPlayCommand.ts:96-106`
- **Status**: NEW (same defect class as open **#5009**, which is scoped to `useQueueFetch.ts`; this is the play-command path — a separate file and call site, so a new instance rather than a duplicate)
- **Description**: The endpoint returns `TrackResponse` (snake_case, `artwork_url`). The hook dispatches the raw parsed JSON as though it already matched `PlayerTrack` (which declares `artworkUrl`), bypassing `transformTrack()` — the project's own mapper that exists for exactly this conversion.
- **Evidence**:
  ```ts
  // useEnhancedPlayCommand.ts:96-105
  const track = await response.json();
  dispatch(setCurrentTrackAndSyncQueue(track));   // track.artworkUrl is undefined
  ```
  ```ts
  // api/transformers/trackTransformer.ts:34 — the transform that should run
  artworkUrl: apiTrack.artwork_url ?? undefined,
  ```
- **Impact**: Every playback start through the primary path leaves `player.currentTrack.artworkUrl` undefined even though the backend returned artwork, so Now Playing artwork renders blank until an unrelated WS `player_state` sync overwrites it (`usePlayerStateSync.ts:117,168` maps the field correctly). Cosmetic; no effect on audio.
- **Suggested Fix**: Frontend. `dispatch(setCurrentTrackAndSyncQueue(transformTrack(track)))`.

---

### LOW

#### INT-10: Nine hooks build API URLs as bare relative paths, bypassing `getApiUrl()`

- **Severity**: LOW · **Flow**: 6 (cross-cutting: 2, 4, 9) · **Status**: NEW (sibling gap of CLOSED #3988, which fixed only `useInfiniteAlbums`, `usePlayNormal`, `usePlayEnhanced`)
- **Location**: `auralis-web/frontend/src/hooks/fingerprint/useSimilarTracks.ts:176`, `useTrackFingerprint.ts:37`, `useAlbumFingerprint.ts:31`, `auralis-web/frontend/src/hooks/shared/useAPIHealthPoll.ts:30`, `auralis-web/frontend/src/hooks/library/useLibraryStats.ts:39`, `useLibraryScan.ts:103`, `useScanProgress.ts:80`, `auralis-web/frontend/src/hooks/app/useAppDragDrop.ts:140,165,189` → `auralis-web/frontend/src/config/api.ts:18-30`
- **Description**: `config/api.ts` is the single place that decides the API origin, and #4468 added `VITE_API_URL` specifically so a user whose port 8765 is taken can move the backend. These nine sites hardcode a bare relative `/api/...` and ignore the override, always resolving against the document origin. Neighbouring hooks in the same directories do use `getApiUrl()` (`useInfiniteAlbums.ts:45`, `usePlayTrack.ts:49`, `useEnhancedPlayCommand.ts:97`), so the codebase is split on the same decision.
- **Impact**: Latent, not live — in `--dev` the Vite proxy forwards `/api` and in the shipped Electron build the backend serves the SPA from its own origin, so both forms resolve identically today. Set `VITE_API_URL` and the app splits: nine features hit the wrong origin while the rest follow the override.
- **Suggested Fix**: Route all nine through `getApiUrl()`. Consider a lint rule banning a string literal starting with `/api/` as `fetch`'s first argument, so #3988 does not re-grow a third time.

#### INT-11: `useSimilarTracks`' module-level cache is never invalidated by any backend similarity-state change

- **Severity**: LOW · **Flow**: 6 · **Status**: NEW (related to OPEN #4629, a *different* defect in the same cache — the key omitting `use_graph`)
- **Location**: `auralis-web/backend/core/stream_messages.py:194-221`, `auralis-web/backend/routers/similarity.py:302-348` → `auralis-web/frontend/src/hooks/fingerprint/useSimilarTracks.ts:83-91,218-222`
- **Description**: `similarityCache` is a module-level `Map` with LRU eviction but no invalidation input. Every backend event that changes what "similar" means — a track finishing fingerprinting, a `POST /fit` refit, a graph rebuild, a track deletion — leaves cached neighbour lists in place for the life of the page. The precedent is the artwork palette cache, given exactly this treatment in #4530; the driving message (`fingerprint_progress`) already exists and is already subscribed, but only by `useFingerprintStatus.ts:98` for playback UI, which never touches this cache. `clear()` deliberately resets React state without touching the cache, so remounting the modal re-serves the stale list.
- **Impact**: In a library still being fingerprinted in the background — the normal state after an import — a user who opens "similar tracks" early keeps a thin or wrong list for that session with no refresh short of a reload. Discovery quality only.
- **Suggested Fix**: Subscribe once to `fingerprint_progress` (or a coarser library revision) and either clear the cache or fold a revision into `getCacheKey` — the latter composes cleanly with the `use_graph` fix #4629 already calls for.

#### INT-12: The similarity router family registers inside a swallowing `try/except`, so a startup failure surfaces as unexplained 404s

- **Severity**: LOW · **Flow**: 6 · **Status**: NEW
- **Location**: `auralis-web/backend/config/routes.py:253-271` → `auralis-web/frontend/src/hooks/fingerprint/useSimilarTracks.ts:186-190`
- **Description**: All three similarity routers are imported and registered inside one `try/except Exception` whose handler is a `logger.warning`. If anything there fails, the app boots minus ~10 endpoints with no runtime signal — no health flag, no WS notice. The frontend then renders `Similarity search failed: 404 Not Found`, which reads as "this track has no similar tracks" rather than "the subsystem failed to load".
- **Impact**: A subsystem-wide outage is indistinguishable from an empty result; debugging requires reading backend logs. Only manifests when registration actually fails.
- **Suggested Fix**: Record the failure on the health/system surface (e.g. `similarity_available: false`) so the frontend can say "similarity unavailable" instead of a bare 404.

#### INT-13: Thumbnail size hints are CSS pixels, so artwork is served at half resolution on HiDPI displays

- **Severity**: LOW · **Flow**: 7 · **Status**: NEW
- **Location**: `auralis-web/frontend/src/components/album/AlbumCard/AlbumCard.tsx:68-71` (and `AlbumArt.tsx:93-97`, `components/track/TrackCard.tsx:43,61`, `components/library/Items/tracks/TrackRow.tsx:101`, `components/library/Search/ResultAvatar.tsx:39`) → `auralis-web/backend/routers/artwork.py:82-87,159`
- **Description**: `size` is a device-pixel dimension on the backend — `_bucket_size()` snaps it to a bucket and `image.thumbnail((bucket, bucket))` produces an image that many pixels wide. Every frontend call site passes a CSS-pixel layout size instead (`size: 256` for a card whose own comment says it "renders ~200px"). `devicePixelRatio` appears nowhere in the frontend (`grep -rn devicePixelRatio auralis-web/frontend/src` → no matches). On a 2× display — the common case for the laptops this Electron app ships to — a 200 CSS-px card occupies 400 device px but receives a 256-px bitmap.
- **Impact**: Visibly soft album art in the grid, detail hero, track rows and search results on HiDPI screens. No correctness impact. It is a boundary bug rather than a frontend-only one because the unit the two layers agreed on is ambiguous and undocumented as to CSS-vs-device pixels.
- **Suggested Fix**: Multiply in one place — inside `getArtworkUrl`/`withArtworkSize`, clamp `Math.min(window.devicePixelRatio || 1, 2) * size` — and document `size` as a device-pixel dimension in the backend `Query(...)`. The bucket ladder already has 512/1024 headroom, so the cache footprint stays bounded.

#### INT-14: The frontend can construct an artwork `size` the backend rejects with 422

- **Severity**: LOW · **Flow**: 7 · **Status**: NEW
- **Location**: `auralis-web/frontend/src/services/artworkService.ts:72-78,84-100` → `auralis-web/backend/routers/artwork.py:295-303`
- **Description**: The backend constrains `size` to `ge=16, le=2048`; the frontend's only guard is `size > 0`. A small-avatar or oversized-hero size would 422 on an `<img src>`, surfacing as a broken image rather than falling back to full resolution — the graceful degradation the render path otherwise guarantees. Every current call site (40, 64, 80, 216, 256, 280) is in range, so this is latent.
- **Suggested Fix**: Clamp in `artworkService.ts` (`Math.min(2048, Math.max(16, rounded))`). Pairs naturally with INT-13, which is exactly the change that would first push a value past 2048.

#### INT-15: `scan_progress.phase` can carry a `'counting'` value the frontend type system does not declare

- **Severity**: LOW · **Flow**: 4 · **Status**: NEW
- **Location**: `auralis/library/scanner/scanner.py:242-251` → `auralis-web/backend/routers/library_scan.py:99,135`, `auralis-web/backend/services/library_auto_scanner.py:248` → `auralis-web/frontend/src/types/ws/library.ts:105`, `auralis-web/frontend/src/hooks/library/useScanProgress.ts:26`
- **Description**: The pre-count pass emits `stage: 'counting'` every 250 discovered files; both WS emitters forward `stage` verbatim as `phase`. The frontend declares `'discovering' | 'processing' | 'fingerprinting'` in both the message type and the hook's own state type, and assigns the raw value through with no validation — so at runtime `state.phase` can hold a string outside its declared type.
- **Impact**: Inert today (no component reads `.phase`), but it would surface silently the moment any component branches on `phase` for UI text — which is what the union's shape suggests it is for.
- **Suggested Fix**: Add `'counting'` to both unions, and consider a "Counting files…" label since the pre-count pass is noticeable on slow or network storage and is otherwise indistinguishable from `'discovering'`.

#### INT-16: `setup_connection` proceeds unconditionally even when the origin check has already closed the socket

- **Severity**: LOW · **Flow**: 5 · **Status**: NEW
- **Location**: `auralis-web/backend/config/globals.py:79-108` → `auralis-web/backend/ws_handlers/connection.py:95-158`
- **Description**: `ConnectionManager.connect()` returns bare `None` on both the accept and the origin-reject path, so `setup_connection()` cannot tell them apart. It proceeds to derive a `connection_id`, construct a `HeartbeatManager`, spawn the heartbeat loop, and perform a DB round-trip to push the initial `player_state`. The heartbeat loop's first iteration sleeps a full 30 s interval before its first `safe_send_text` detects the closed socket and exits.
- **Impact**: Bounded and self-terminating (≤30 s per rejected attempt, one dangling task plus one wasted DB read), not a compounding leak. Downgraded for the desktop-only/localhost scope — triggering it needs a local client sending a disallowed `Origin`. A retry-looping misconfigured local tool would accumulate concurrent dangling tasks for the duration of the burst.
- **Suggested Fix**: Have `connect()` return `bool` and have `setup_connection()` return immediately on `False`.

#### INT-17: `PositionChangedMessage` omits the `seq` field the backend sends and the frontend reads

- **Severity**: LOW · **Flow**: 5 · **Status**: NEW
- **Location**: `auralis-web/backend/core/state_manager.py:336-339` → `auralis-web/frontend/src/types/ws/player.ts:172-177`, `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:198-221`
- **Description**: The 1 Hz position tick carries `seq` so the frontend can drop a stale tick arriving after a newer `player_state` snapshot (#4544, a real rewind-the-progress-bar bug). The consumer reads and acts on it — via an ad hoc inline cast (`message as { data?: { position?: number; seq?: number } }`), because the declared `PositionChangedMessage.data` is only `{ position: number }`.
- **Impact**: No functional bug today; the #4544 fix works by bypassing the type system. The risk is that `PositionChangedMessage` — the type other code would naturally reach for — claims a shape the wire does not match, so a future edit trusting the interface would silently drop `seq` and reopen #4544.
- **Suggested Fix**: Add `seq?: number` to the interface and consume it through the typed message.

#### INT-18: `QueueChangedMessage.action` omits three action values the backend emits

- **Severity**: LOW · **Flow**: 9 · **Status**: NEW (same drift class as OPEN #4680, which covers the message-*type* registry; this is the `action` enum inside one message)
- **Location**: `auralis-web/backend/services/queue_service.py:636,681`, `auralis-web/backend/routers/player.py:609` → `auralis-web/frontend/src/types/ws/queue.ts:46`
- **Description**: The backend emits seven `action` values — `added`, `removed`, `reordered`, `shuffled`, `unshuffled`, `cleared`, `undo`. The frontend declares four.
- **Impact**: None at runtime — `useQueueSubscription` never switches on `action`. Latent: the first `switch (data.action)` gets a type-checked exhaustive switch that is silently wrong for three real cases. The sibling `QueueUpdatedMessage.action` carries the same four-value list.
- **Suggested Fix**: Widen both unions to the seven emitted values, derived from one shared union so the two message types cannot drift apart from each other.

---

## Existing Issues Re-Confirmed (not re-filed)

Verified present in current code during this audit; none regressed.

| Issue | Sev | Flow | Note |
|---|---|---|---|
| #4820 | HIGH | 4 | Scan cancellation never reaches the backend; `scanAbortRef` is destructured and discarded in `useLibraryWithStats.ts:57`, no cancel UI wired |
| #4815 | HIGH | 8 | Unthrottled `mousemove`-driven seeks during a scrubber drag; the old `usePlayerControls` debounce no longer exists post-#4541 |
| #4680 | MEDIUM | 5 | WS message-type registry drift — `job_progress` emitted but unregistered; `queue_updated` declared but has zero backend emitters since #3492/#4420 |
| #4587 | MEDIUM | 3 | Settings-dialog enhancement defaults never reach the live session |
| #4677 | MEDIUM | 3 | `handle_seek` lets recorded stream settings override the client-sent preset/intensity |
| #4629 | MEDIUM | 6 | `useSimilarTracks` cache key omits `use_graph` |
| #4707, #4425, #4760 | LOW | 3 | intensity not applied to `HybridProcessor`; mid-playback settings change restarts the stream; toggle pre-warm writes to a throwaway cache |
| #4709 | LOW | 2 | `serialize_album_detail` maps a `genre` key `Album.to_dict()` never produces |
| #4942, #4710, #4654, #4647, #4971, #4861, #3884 | LOW | 3 | Type-contract/dead-code items, spot-checked, unchanged |

---

## Relationships

**R1 — "The sibling branch never got the fix" (INT-01, INT-03, INT-04, INT-05).**
The single highest-value structural theme. In each case a correct guard, offset
restoration, epoch check, or eager-load exists and is exercised by tests, and the
parallel branch that real usage actually takes has none of it. Three of the four
also have test suites that structurally cannot reach the broken branch —
`useAudioStreamingCore.epoch.test.tsx` always pre-seeds a buffer; the album-tracks
tests use a `_FakeTrack` and a mocked repository. **Fixing these one at a time
without adding a test that enters the previously-unreachable branch will let the
same class regress.**

**R2 — Frontend type declarations are narrower than the wire (INT-15, INT-17,
INT-18, and open #4680).** Four independent instances across three flows. All are
LOW individually and all are inert only because no consumer branches on the field
yet. Worth one consolidated pass over `types/ws/` rather than four separate fixes.

**R3 — Untransformed backend payloads entering camelCase-typed Redux (INT-09,
INT-07, open #5009).** Three ingresses of one defect: `useQueueFetch` (#5009,
open), the play command (INT-09), and the `queue_changed` WS fallback (INT-07).
The transformers exist and are correct; the problem is that nothing forces a
payload through them. A typed boundary helper — or making the slice reducers
accept only the domain type — would close all three at once.

**R4 — INT-01 and INT-03 compound.** INT-03 leaves `currentTime` short of
`trackDuration` after a seek, which can suppress the `nearEnd` auto-advance; INT-01
makes an end-of-track seek deliver silence. Together they produce "playback
silently stalls at the end of a track after any seek," a symptom neither finding
fully explains alone.

**R5 — INT-02 and INT-07 are two halves of one inconsistency.** The REST path
drops unresolvable queue entries while the WS path keeps them as raw dicts, so the
two surfaces disagree about how long the queue is, and whichever arrives last
wins. They must be fixed together or the disagreement simply inverts.

---

## Prioritized Fix Order

1. **INT-01 (CRITICAL)** — silent zero-audio on an ordinary, keyboard-accessible
   interaction, reported as success. Fix `chunk_for_position()` to clamp against
   `total_duration`; this also finally lets the sliver guard cover the last chunk.
2. **INT-03 (HIGH)** — one-line hoist, immediately visible UX repair, and it
   removes half of the R4 compound failure. Highest fix-value-to-effort ratio in
   this report.
3. **INT-05 (HIGH)** — one-line eager-load addition that repairs a 100%-reproducible
   blank artist on every album page. Add the `_safe_collection()`/`_safe_scalar()`
   migration for `Track.to_dict()` in the same change so the next omission is loud.
4. **INT-02 + INT-07 (HIGH + MEDIUM)** — fix together per R5. Wrong-track deletion
   is the worst *data* outcome in this report even though its trigger is less
   frequent than INT-01's.
5. **INT-04 (HIGH)** — wrong-track audio at playback start; narrower window than
   INT-01 but the same symptom class. Add a test that enters the queue-then-flush
   branch (per R1) rather than only fixing the branch.
6. **INT-06 (HIGH)** — quadratic request growth starving the shared ASGI loop that
   also serves audio. Larger change (new endpoint), hence below the one-line fixes
   despite equal severity.
7. **INT-08, INT-09 (MEDIUM)** — user-visible but cosmetic/misleading rather than
   incorrect.
8. **LOW cluster** — take R2 (INT-15/17/18) as one `types/ws/` pass and R3's typed
   boundary helper as one change; the rest (INT-10 through INT-14, INT-16) are
   independent and opportunistic.

---

*Report generated by `/audit-integration` (comprehensive suite). No GitHub issues
were created. To publish: `/audit-publish docs/audits/AUDIT_INTEGRATION_2026-08-13.md`*
