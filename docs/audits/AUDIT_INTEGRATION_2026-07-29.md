# Integration Audit — Backend ↔ Frontend ↔ Engine

**Date**: 2026-07-29
**Audit type**: `audit-integration` (part of the `comprehensive` audit suite)
**Scope**: 7 critical data flows traced across the Auralis audio engine (`auralis/`), the FastAPI backend (`auralis-web/backend/`), and the React frontend (`auralis-web/frontend/`)
**Depth**: deep (full data-path tracing, all 7 flows)
**Method**: 7 independent flow agents, each reading current source only. Prior audit reports were used for deduplication exclusively, never as a source of findings.
**Dedup baseline**: 1500 GitHub issues (#3194–#4717, 239 open) + prior integration reports (2026-07-12, 2026-07-25).

---

## Executive Summary

**29 new findings**: 0 CRITICAL, 7 HIGH, 14 MEDIUM, 8 LOW.

All 7 flows were traced to completion. No flow was left untraced, though each carries its own reachability caveats (recorded in the coverage matrix below and preserved verbatim in each finding).

### Key themes

**1. The enhancement control path is broken in three independent, compounding ways (HIGH ×3).**
This is the headline of the audit. `usePlayTrack` — the documented "single source of truth for play this track now", used by every library row, album view, artist view, and "Play All" — hardcodes `preset: 'adaptive', intensity: 1.0` and never checks the `enabled` flag (INT3-01, INT3-02). Independently, the backend's `handle_play_enhanced` deduplicates on `track_id` alone, so a mid-stream preset or intensity change is silently swallowed while the shared `enhancement_settings` dict is still updated to claim it applied (INT3-04). The net effect: the enhancement panel, the REST status endpoint, and the WebSocket broadcast all report the user's settings as active, while the audio the user actually hears is something else. **Everything except what you hear says the change took effect.** INT3-04 was independently corroborated with a live empirical repro (same `asyncio.Task` object survives the reissue) and is a **regression of #3763/#3759**, whose frontend-only fix was never exercised against real backend behavior.

**2. "Cancel"/"stop" affordances that do not reach the backend (HIGH ×2, MEDIUM ×1).**
The library-scan `AbortController` never cancels the server-side scan (INT4-01) — the endpoint takes the parsed Pydantic body as its `request` parameter, so it has no ASGI `Request` and cannot poll `is_disconnected()`; the only real cancellation trigger is the 1-hour timeout or shutdown. The same shape appears in the similarity `fit`/`graph/build` path (INT6-02), where the frontend's hard 30 s fetch timeout aborts client-side while the `asyncio.to_thread` job keeps running to completion, inviting duplicate concurrent runs.

**3. WebSocket broadcasts are fire-and-forget with no resync-on-reconnect for non-playback state (HIGH ×1).**
Playback state resyncs correctly on reconnect (`setup_connection` re-pushes `enhancement_settings_changed` + `player_state`; `replayQueueAndResume` + `seq` watermark handle ordering). Scan state does not: there is no REST scan-status endpoint anywhere, so a WebSocket blip during a long scan strands the UI on "Scanning…" permanently (INT4-02). Reconnect is the *common* case in this app (`--dev` reloads, laptop sleep), which elevates this.

**4. Sentinel/placeholder rows leak into the similarity engine (HIGH ×1).**
The `lufs == -100.0` in-progress placeholder guard and the stale-`fingerprint_version` guard exist in exactly one place — `FingerprintService._load_from_database()`, on the mastering path. The five repository methods the similarity engine, K-NN graph builder, and fingerprint-display endpoints actually call apply neither (INT6-01), so all-zero vectors can be compared as real fingerprints, baked into the persisted graph, and fed into the normalizer's percentile fit.

**5. Non-deterministic pagination on the single most-used browse path (HIGH ×1).**
`TrackRepository.search()` pages with `LIMIT`/`OFFSET` and no `ORDER BY` at all, and the router silently drops the caller's `order_by` before calling it (INT2-01) — the sibling `AlbumRepository.search()` does this correctly, so tracks is the outlier. Combined with a concurrent background scanner inserting rows, infinite-scroll search can duplicate or skip tracks.

**6. Contract drift at the REST boundary (MEDIUM ×5).** Fields declared on one side and never produced by the other (`Artist.dateAdded`, `LibraryTrack.genre`), backend `detail` bodies discarded before they reach the UI, a 200-item playlist cap with no consumer of `has_more`, and three conflicting unused pagination-parameter definitions.

### Most impactful boundary mismatches

| # | Boundary | Why it matters |
|---|----------|----------------|
| INT3-04 | Frontend `reissueActiveStreamAs` → Backend `handle_play_enhanced` | Regression; DSP output silently diverges from every status surface |
| INT3-01 / INT3-02 | Frontend `usePlayTrack` → Backend WS | The primary play entry point ignores both `enabled` and the user's preset |
| INT6-01 | Library repositories → similarity engine | Placeholder fingerprints served as real similarity results |
| INT4-01 | Frontend abort → Backend scan endpoint | Cancellation is cosmetic; scan slot held up to an hour |
| INT2-01 | Backend router → track repository | Unordered `LIMIT`/`OFFSET` on the main search path |

---

## Flow Coverage Matrix

| Flow | Boundaries verified | Not reached / caveats | Findings |
|------|--------------------|-----------------------|----------|
| **1. Track Playback** | Frontend play trigger (`usePlayTrack`, `usePlaybackControl`) → REST → `routers/player.py` → `auralis/io/unified_loader.py` → `hybrid_processor.py` / `simple_mastering.py` → `chunked_processor.py` + `chunk_boundaries.py` / `chunk_crossfade.py` / `chunk_mastering.py` / `chunk_cache*.py` → `audio_stream_controller.py` / `stream_*.py` / `proactive_buffer.py` / `job_worker.py` / `state_manager.py` → frontend WS client + Web Audio. Sample-rate matching, chunk overlap math, WS binary framing, flow-control backpressure and seek offset math all held up under fresh scrutiny. | Seek-while-buffering races traced statically only (no live runtime repro). Electron/desktop IPC layer out of scope. | 1 MEDIUM |
| **2. Library Browsing** | Frontend hooks (`useLibraryQuery`, `useLibraryPagination`, `useInfiniteAlbums`, `playlistService`) → `useRestAPI` → `tracks.py` / `albums.py` / `artists.py` / `playlists.py` / `library.py` → track/album/artist/playlist repositories → `models/core.py` → `api/transformers/*` → `types/domain.ts`. Pagination contracts, `selectinload`/`joinedload` on every list endpoint, camel/snake boundaries, optional-metadata null handling. | Favorites-list sort options (no `order_by` exposed by design); similarity/fingerprint browsing (Flow 6); scan progress (Flow 4); artwork bytes (Flow 7). | 1 HIGH, 4 MEDIUM, 1 LOW |
| **3. Audio Enhancement** | `useEnhancementControl` → `POST/GET /api/player/enhancement/*` and the `play_enhanced`/`play_normal` WS commands → shared `enhancement_settings` dict → `ChunkedAudioProcessor` / `AudioProcessingPipeline` / `ProcessorFactory` → `HybridProcessor` → `continuous_space.py`. Range validation, cache-key correctness, preset-name enumeration across all three layers. Cross-audit dedup claim independently verified with a live repro. | — | 3 HIGH, 1 LOW |
| **4. Library Scanning** | `useLibraryScan` ↔ `routers/library_scan.py`; `auralis/library/scanner/*` ↔ `track_repository.py` ↔ `models/core.py`; scan-slot guard in `database.py`; progress broadcast (manual route + `library_auto_scanner.py`) ↔ `useScanProgress` / `types/ws/library.ts`; reconnect semantics in `websocketConnectionCore.ts`; auto-scan folder config (`routers/settings.py`, `FoldersList.tsx`). | No live multi-GB scan executed. Cross-platform (Windows/macOS filesystem) behavior assessed by static reasoning against the shipped desktop targets only — INT4-05 rests on that reasoning. | 2 HIGH, 3 MEDIUM, 1 LOW |
| **5. WebSocket Lifecycle** | Connection accept (`ws_handlers/connection.py`, `ConnectionManager.connect`), dispatch (`messages.py`, `playback_commands.py`, `playback_control.py`), inbound Pydantic contract (`schemas.py`), heartbeat (`websocket_protocol.py` + client keepalive), teardown, and the full frontend transport stack. Full bidirectional message-type diff built (see below). | Binary/text frame pairing and chunk backpressure checked at the *lifecycle* level only — chunk math is Flow 1's territory and was not re-derived. | 1 MEDIUM (+2 existing confirmed) |
| **6. Fingerprint & Similarity** | Frontend hooks (`useSimilarTracks`, `useTrackFingerprint`, `useAlbumFingerprint`, `FingerprintCache`, `similarityService`) → `similarity.py` / `similarity_graph.py` / `similarity_common.py` / `fingerprint_queue.py` / `fingerprint_status.py` → `auralis/analysis/fingerprint/*` (similarity, distance, normalizer, knn_graph, schema, rust_fingerprint) → fingerprint repositories → Rust PyO3 boundary (`py_bindings.rs`, `frequency_analysis.rs`). | — | 1 HIGH, 3 MEDIUM, 4 LOW |
| **7. Artwork** | Frontend (`artworkService`, `useArtworkUpdates`, `useArtworkPalette`, `colorExtraction`, `AlbumArt`, `ProgressiveImage`, `MediaCardArtwork`) → `routers/artwork.py` (incl. thumbnail bucketing/locking), `routers/artists.py`, `services/artwork_downloader.py`, `config/middleware.py` → `auralis/library/artwork.py`, `auralis/services/artwork_service.py` → `album_repository.py`. Path validation re-derived and confirmed correct (inline `is_relative_to()` against `~/.auralis/artwork`; no string-prefix bypass). `NoCacheMiddleware` confirmed to exclude `/api`, so artwork `ETag`/`Cache-Control` survive. | `auralis/cli/fetch_artwork.py` execution not reachable (offline batch CLI, no live request boundary). Two initially-plausible theories were actively **disproved** and not reported: a blob-URL leak (no `createObjectURL` in shipped artwork code) and a decompression-bomb risk (Pillow's `MAX_IMAGE_PIXELS` guard never disabled). | 2 MEDIUM, 1 LOW |

**Flows not covered**: none. All 7 flows were traced end-to-end.

### WebSocket message-type diff (Flow 5)

Backend-emitted vs frontend-registered:

| Backend emits | Frontend registers? | Note |
|---|---|---|
| `job_progress` | **No** (absent from `ALL_MESSAGE_TYPES` and `INTERNAL_MESSAGE_TYPES`) | Existing: #4680 |
| `queue_updated` | Frontend registers it; backend no longer sends it (renamed `queue_changed` by #3492) | Dead type, not a gap — Existing: #4680 |
| ~34 other emitted types (`player_state`, `position_changed`, `audio_stream_*`, `playback_*`, `queue_changed`, `queue_shuffled`, `repeat_mode_changed`, `library_*`, `metadata_*`, `playlist_*`, `enhancement_settings_changed`, `mastering_recommendation`, `artwork_updated`, `fingerprint_progress`, `seek_started`, `cache_cleared`, `error`, `ping`/`pong`/`audio_chunk_meta`) | Yes | Registered or internal |

Frontend-sent vs backend-routed:

| Frontend sends | Backend routes it? | Note |
|---|---|---|
| `ping`, `pong`, `heartbeat`, `play_enhanced`, `play_normal`, `pause`, `stop`, `seek`, `buffer_full`, `buffer_ready` | Yes, all routed | Live call sites confirmed for each |
| `resume` | **Never sent** — fully implemented and dispatched server-side (`handle_resume`) with zero frontend callers | Existing: #4541 |
| `subscribe_job_progress` | **Never sent** | Existing: #4680 |

No camelCase/snake_case mismatches at the WS boundary: every `data` payload is snake_case on both sides, with an explicit downstream mapping layer (`types/ws/player.ts` maps `is_playing` → `isPlaying` for Redux) rather than a silent mismatch.

---

# Findings

29 new findings, grouped by severity. Cross-flow duplicates have been removed; findings whose `Status` is `Existing: #NNNN` are collected in the appendix rather than counted here.

## HIGH Findings

### INT2-01: `TrackRepository.search()` has no `ORDER BY` — LIMIT/OFFSET pagination is non-deterministic while searching
- **Severity**: HIGH
- **Flow**: Flow 2 (Library Browsing)
- **Boundary**: Backend router → Engine repository
- **Location**: `auralis-web/backend/routers/tracks.py:52-58` → `auralis/library/repositories/track_repository.py:402-449`
- **Status**: NEW
- **Description**: `GET /api/library/tracks?search=...` pages through results with `LIMIT`/`OFFSET` but the underlying query has zero `ORDER BY` clause. The router doesn't even forward the caller's `order_by` selection to `search()` — it silently drops it:
  ```python
  # tracks.py
  if search:
      tracks, total = await asyncio.to_thread(repos.tracks.search, search, limit=limit, offset=offset)
  else:
      tracks, total = await asyncio.to_thread(repos.tracks.get_all, limit=limit, offset=offset, order_by=order_by)
  ```
  `TrackRepository.search()`'s signature has no `order_by` parameter at all, and its query never calls `.order_by(...)`:
  ```python
  # track_repository.py
  def search(self, query: str, limit: int = 50, offset: int = 0) -> tuple[list[Track], int]:
      ...
      results = session.execute(
          select(Track)
          .join(Track.artists, isouter=True)
          .join(Track.album, isouter=True)
          .options(*_track_eager_options(collections_via_selectin=True))
          .where(search_filter)
          .distinct()
          .limit(limit)
          .offset(offset)
      ).scalars().unique().all()
  ```
  Per SQL semantics, `LIMIT`/`OFFSET` without `ORDER BY` has an implementation-defined row order that is not guaranteed stable across two separate executions of the same query — especially here, where `.distinct()` after an outer join can force SQLite to build a temporary B-tree whose emission order isn't tied to insertion order.
- **Evidence**: See code above. Compare with the sibling `AlbumRepository.search()` (`album_repository.py:127-176`), which correctly accepts and applies `order_by` with a whitelist and an explicit `.order_by(order_column.asc())` — the tracks path is the outlier.
- **Impact**: `useLibraryQuery.ts`'s infinite-scroll `fetchMore()` (and the older `useLibraryPagination.ts`) request subsequent pages of the *same* search by increasing `offset`. Without a stable order, concurrent writes from the background library scanner (Flow 4, running any time the app is open) or even routine SQLite query-plan variance can cause the same track to appear twice across pages, or a track to be skipped entirely, while a user scrolls through search results. This is exactly the "large/actively-changing library" scenario the app is built around.
- **Suggested Fix**: Add an `order_by` parameter to `TrackRepository.search()` (mirroring `AlbumRepository.search()`'s whitelist pattern) and always call `.order_by(...)` — at minimum `Track.id.asc()` as a stable tiebreaker — before `.limit()/.offset()`. Update `tracks.py` to forward the caller's `order_by`.

---

### INT3-01: Every fresh-playback entry point ignores the `enabled` flag and always sends `play_enhanced`, so disabling enhancement silently breaks starting/advancing any track
- **Severity**: HIGH
- **Flow**: Flow 3 (Audio Enhancement)
- **Boundary**: Frontend (Player.tsx / usePlayTrack.ts) → Backend (ws_handlers/playback_commands.py)
- **Location**: `auralis-web/frontend/src/components/player/Player.tsx:114,138,163` and `auralis-web/frontend/src/hooks/player/usePlayTrack.ts:77-84` → `auralis-web/backend/ws_handlers/playback_commands.py:133-188`
- **Status**: NEW
- **Description**: The backend's documented contract (`WEBSOCKET_API.md:640-649`) is explicit: *"`enabled` ... the **stored** setting governs by default. If global enhancement is disabled, `play_enhanced` is rejected... `force: true` overrides the gate... The UI leaves `force` unset, so the enhancement panel toggle still gates normal playback."* This means the frontend is expected to route to `play_normal` (which is unconditionally allowed) whenever `enabled === false`. It only does this in exactly one place: `useEnhancementControl.toggleEnabled()`, which calls `reissueActiveStreamAs('play_normal')` — but only when a stream is already active and the user is *toggling right now*. Every other place that starts playback — `Player.tsx`'s `handleNext`/`handlePrevious`/`handlePlayPause`, and `usePlayTrack.ts` (the sole "play this track" entry point used by every library track row / "Play All" action, per its own docstring) — unconditionally sends `play_enhanced` with no check of `enabled` at all, and never falls back to `play_normal`.
- **Evidence**:
  Backend gate (`playback_commands.py:174-188`):
  ```python
  if not enhancement_enabled and not force:
      logger.warning(f"Enhancement disabled, rejecting play_enhanced request for track {track_id}")
      ...
      await websocket.send_text(json.dumps({
          "type": "audio_stream_error",
          "data": {..., "code": "ENHANCEMENT_DISABLED", ...}
      }))
      return
  ```
  Frontend `Player.tsx:160-164` (same pattern in handleNext/handlePrevious):
  ```tsx
  } else {
    // Not streaming - start new stream
    await playEnhanced(currentTrack.id, enhancementPreset, enhancementIntensity);
  }
  ```
  No reference to `enabled` (from `useEnhancementControl()`) anywhere in `Player.tsx`. `usePlayTrack.ts:77-84` sends the WS frame directly, also with no `enabled` check:
  ```ts
  wsContext.send({
    type: 'play_enhanced',
    data: { track_id: track.id, preset: 'adaptive', intensity: 1.0 },
  });
  success(`Now playing: ${track.title}`);
  ```
  The `success()` toast fires unconditionally — `wsContext.send` is fire-and-forget, so the toast claims playback started even when the backend is about to reject it.
- **Impact**: Once a user disables enhancement (a first-class, documented feature, not an edge case), every subsequent "start a track that isn't the currently-active enhanced stream" action — Next, Previous, Play/Pause-from-stopped, and any library track click — sends `play_enhanced` with `force` unset, gets rejected with `ENHANCEMENT_DISABLED`, and produces silence. The `usePlayTrack` toast falsely reports success. The user's only way to hear audio again is to re-enable enhancement, defeating the purpose of the toggle. This reaches the user through the primary, currently-wired control surfaces (Player.tsx + usePlayTrack), not the already-flagged legacy REST control plane (#4541).
- **Suggested Fix**: Every playback-start call site needs to branch on `enabled` (from `useEnhancementControl`) the same way `toggleEnabled()` already does: send `play_normal` when disabled, `play_enhanced` otherwise. This logic belongs in one place — ideally `usePlayTrack` and `useEnhancedPlayCommand`/`Player.tsx` should share a single "start playback for track X" helper that reads `enabled` and picks the message type, rather than three independent call sites each needing the same fix.

---

### INT3-02: `usePlayTrack` hardcodes `preset: 'adaptive', intensity: 1.0` for every library-initiated play, silently overwriting the shared runtime settings and desyncing the displayed UI state
- **Severity**: HIGH
- **Flow**: Flow 3 (Audio Enhancement)
- **Boundary**: Frontend (usePlayTrack.ts) → Backend (ws_handlers/playback_commands.py) → shared `enhancement_settings` dict
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayTrack.ts:77-84` → `auralis-web/backend/ws_handlers/playback_commands.py:120-156`
- **Status**: NEW
- **Description**: `usePlayTrack` is documented as "the single source of truth for 'play this track now'... Call it directly at the leaf (a track row, 'Play All', etc.)" and is consumed from `ArtistDetailView.tsx`, `AlbumDetailView.tsx`, and `usePlaybackState.ts`. It sends a literal `preset: 'adaptive', intensity: 1.0` instead of reading the user's actual current selection from `useEnhancementControl()`. Because the backend treats an explicit, valid `preset`/`intensity` in the `play_enhanced` payload as authoritative (`playback_commands.py:120-122`, "client-sent values are primary" per `WEBSOCKET_API.md:640-642`), this isn't just a display bug — it actively overwrites the shared `enhancement_settings` dict (`playback_commands.py:154-155`, `settings["preset"] = preset; settings["intensity"] = intensity`) with the hardcoded values, and **no WebSocket broadcast is sent from this write-back path** (only the REST `enhancement.py` handlers broadcast `enhancement_settings_changed`). So after any library track click: (a) the track plays at Adaptive/100% regardless of what the user had selected (e.g. Warm/70%), and (b) the enhancement panel's displayed preset/intensity (driven by `useEnhancementControl`'s local `state`) now shows the user's last manual selection while the actual live DSP parameters silently became Adaptive/100% — a second-order UI/reality desync. This is the same class of bug `#4410` fixed for `Player.tsx`'s own `handleNext`/`handlePrevious`/`handlePlayPause` (confirmed intact — those three correctly thread `enhancementPreset`/`enhancementIntensity` through), but the fix was never applied to `usePlayTrack`, which is the *initial* entry point used before Next/Previous ever get exercised.
- **Evidence**:
  ```ts
  // usePlayTrack.ts:77-84
  wsContext.send({
    type: 'play_enhanced',
    data: {
      track_id: track.id,
      preset: 'adaptive',
      intensity: 1.0,
    },
  });
  ```
  ```python
  # playback_commands.py:120-156
  raw_preset = data.get("preset", "")
  preset = raw_preset.lower() if (... raw_preset.lower() in VALID_PRESETS) else None
  ...
  if deps.get_enhancement_settings is not None:
      settings = deps.get_enhancement_settings()
      ...
      if preset is None:
          preset = settings.get("preset", "adaptive")
      ...
      # Write the accepted values back (#4601) ... Mutated in place: the dict
      # is shared by reference with the routers (#4409)
      settings["preset"] = preset
      settings["intensity"] = intensity
  ```
  Since `usePlayTrack` sends `'adaptive'`/`1.0` (both valid, non-empty), `preset`/`intensity` are never `None`, so the settings-fallback branch is skipped and the hardcoded values are written straight into the shared dict — and this is confirmed intentional/tested: `usePlayTrack.test.ts:88-99` asserts the hardcoded `{preset: 'adaptive', intensity: 1.0}` payload as the "correct" behavior.
- **Impact**: Any user who sets a non-default preset/intensity in the enhancement panel, then plays a track from an album/artist detail view or any track row ("Play All" etc.) — the overwhelmingly common way to start playback — gets silently downgraded to Adaptive/100%, and the enhancement panel keeps showing their real selection as if it were still in effect. This is an audible, silent DSP-parameter mismatch, not merely cosmetic.
- **Suggested Fix**: `usePlayTrack` should accept (or read via context/hook) the current `preset`/`intensity` from `useEnhancementControl()` and forward them, mirroring the fix already applied to `Player.tsx`. Since `usePlayTrack` is a plain hook (not inside the `Player` component tree), the simplest fix is to call `useEnhancementControl()` inside `usePlayTrack` itself and use its live `preset`/`intensity`/`enabled` (also fixes INT3-01's library-click case) instead of literals.

---

### INT3-04: `play_enhanced` dedup keys on `track_id` alone, so live preset/intensity changes — and re-enabling mid-stream — are silently swallowed while the shared settings dict is corrupted to claim they applied
- **Severity**: HIGH
- **Flow**: Flow 3 (Audio Enhancement)
- **Boundary**: Frontend (`useEnhancementControl.setPreset`/`setIntensity`/`toggleEnabled` → `reissueActiveStreamAs`) → Backend (`ws_handlers/playback_commands.py::handle_play_enhanced`)
- **Location**: `auralis-web/frontend/src/hooks/websocket/useWebSocketConnection.ts:321-355` (`reissueActiveStreamAs`) → `auralis-web/backend/ws_handlers/playback_commands.py:190-198`
- **Status**: Regression of #3763 (and the "mirror case" named in the same fix commit, tracked under #3759) — verified NOT fixed in current source; see below. Distinct from, and more severe than, the open #4425 (LOW, "tears down and reissues... re-buffer gap"), whose premise that a teardown/restart actually occurs does not hold — empirically confirmed no restart happens at all for this scenario. Flagging both for reconciliation.
- **Description**: CONFIRMED the claim passed to me for verification. `handle_play_enhanced`'s duplicate-suppression guard is:
  ```python
  # playback_commands.py:190-198
  ws_id = _ws_id(websocket)
  # Deduplicate: if the same track is already streaming, skip
  async with state.active_tasks_lock:
      existing_track = state.active_track_ids.get(ws_id)
      existing_task = state.active_tasks.get(ws_id)
      if (existing_track == track_id and existing_task is not None and not existing_task.done()):
          logger.info(f"Ignoring duplicate play_enhanced for track {track_id} (already streaming on ws {ws_id})")
          return
  await _cancel_prior_task(ws_id, state)
  ```
  The comparison is `existing_track == track_id` — **track_id only**. It does not consider `preset`, `intensity`, or even which stream *type* (`play_enhanced` vs `play_normal`) is currently running, since `handle_play_normal` also writes `state.active_track_ids[ws_id] = track_id` (line 279, explicitly for this dedup's benefit per #3509). `stream_audio` is a long-lived task that runs for the whole track, so `existing_task.done()` stays `False` for the entire duration of playback — the dedup window is open the whole time the track is playing.

  On the frontend, `useEnhancementControl.setPreset`/`setIntensity`/`toggleEnabled` (toggle-ON direction) all call `reissueActiveStreamAs('play_enhanced', {...})` (`useWebSocketConnection.ts:321-355`), which re-sends the **same `track_id`** (read from `connState.lastStreamCommand`) with the new preset/intensity and a `start_position`. This message is dispatched straight to `handle_play_enhanced` with no interception (`connection.py:120-121`), so it hits exactly the guard above.

  I confirmed this empirically (not just by static reading) with a standalone script that calls `handle_play_enhanced` twice against a live `StreamState`: once to start a long-running stream task for track 1 at preset `adaptive`/intensity `1.0`, then again for the same track with preset `warm`/intensity `0.4` while the first task is still running (`task.done() == False`). Result:
  ```
  After first call:      settings: {'preset': 'adaptive', 'intensity': 1.0}   task1 done? False
  After reissue (warm/0.4, same track_id, stream still active):
      settings: {'preset': 'warm', 'intensity': 0.4}
      is it the SAME task object as before (i.e. no restart)? True
  ```
  The settings **dict** picks up 'warm'/0.4 (the write-back at `playback_commands.py:154-155` runs *before* the dedup check), but the **running task is untouched** — it is literally the same `asyncio.Task` object, still driving `ChunkedAudioProcessor` constructed with the original `adaptive`/`1.0`. `_cancel_prior_task` — the only code that would actually swap in a new processor — is never reached.
- **Evidence**: See the quoted guard and empirical repro above. Also: `git show 0e686fe7` (the commit that closed #3759/#3763, "fix(frontend): re-issue active stream on enhancement config changes") touched only `WebSocketContext.tsx`, `useEnhancementControl.ts`, and their tests — it never touched `playback_commands.py` or its predecessor in `routers/system.py`. The track_id-only dedup guard predates that fix by two months (`git log -S "Ignoring duplicate play_enhanced"` → `04d5b816`, March 23 2026, vs. the #3759/#3763 fix on May 27 2026), so the frontend-only fix was never actually exercised against the backend's real behavior — its own test suite mocks the WS context and never asserts what the backend does with the reissued message.
- **Impact**: Two of the three scenarios the #3759/#3763 fix commit explicitly named as fixed do not work in current source:
  1. Moving the intensity slider or picking a different preset while a track is already streaming enhanced audio has **zero effect on the audio the user hears** — the old processor keeps running unchanged for the rest of the track (or until the user switches tracks, which uses a different `track_id` and bypasses the guard).
  2. Re-enabling enhancement (`toggleEnabled` → `enabled=true`) while the *same* track is already streaming as `play_normal` also does nothing — the reissued `play_enhanced` is swallowed, so the user stays on unenhanced audio despite the UI now showing enhancement as ON.
  Worse than a silent no-op: the shared `enhancement_settings` dict *does* get updated to the new values (the write-back runs before the guard), so every other consumer — `GET /api/player/enhancement/status`, `GET /api/processing/parameters`, the `enhancement_settings_changed` broadcast that updates the enhancement panel UI — reports the change as successful. Only the actual audio output is stale, making this exceptionally hard to diagnose from either the UI or the API surface: everything *except what you hear* says the change took effect.
  (The one scenario from that fix commit that *does* work: toggling OFF mid-enhanced-stream sends `play_normal`, which has no dedup guard at all and always cancels+restarts — confirmed intact.)
- **Suggested Fix**: The dedup guard needs to also compare the values that actually affect the running processor — at minimum `preset`/`intensity`/stream-type, or more robustly, have `reissueActiveStreamAs` reasons distinguish "same config, ignore" from "config changed, restart" so the guard can key on more than `track_id`. The simplest fix: extend the guard's condition to also require the incoming `preset`/`intensity` to equal what's already recorded in `enhancement_settings` before treating it as a no-op duplicate — a mismatch should fall through to `_cancel_prior_task` + restart, exactly as a different `track_id` does today.

---

### INT4-01: Frontend scan "cancellation" never reaches the backend — the scan keeps running after abort/unmount
- **Severity**: HIGH
- **Flow**: Flow 4 (Library Scanning)
- **Boundary**: Frontend (fetch abort) → Backend (FastAPI endpoint)
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryScan.ts:39,70` → `auralis-web/backend/routers/library_scan.py:38,212-234`
- **Status**: NEW
- **Description**: `useLibraryScan` aborts the in-flight `fetch('/api/library/scan')` on unmount and whenever a new scan supersedes it (`scanAbortRef.current?.abort()`). The backend handler's own comment (lines 212-220) claims this abort is one of two triggers that raise `asyncio.CancelledError` inside `scan_library()`, which then calls `scanner.stop_scan()`. This is not how FastAPI/Starlette/uvicorn works: the endpoint signature is `async def scan_library(request: LibraryScanRequest)` — the parameter named `request` is the *parsed Pydantic body*, not the ASGI `Request` object, so the handler has no way to observe `is_disconnected()` even if it wanted to. Nothing in the codebase (checked `config/middleware.py`, `main.py`) wraps routes with disconnect-triggered cancellation. A client closing its fetch/socket does not, by itself, cancel an already-scheduled endpoint coroutine in Starlette; the coroutine keeps running to completion or to its own `asyncio.wait_for(..., timeout=scan_timeout)` (default 3600s).
- **Evidence**:
  Frontend (`useLibraryScan.ts:35-41,68-72`):
  ```ts
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      scanAbortRef.current?.abort();
    };
  }, []);
  ...
  setScanning(true);
  // Abort any prior in-flight scan and make this one cancellable (#3987).
  scanAbortRef.current?.abort();
  const controller = new AbortController();
  scanAbortRef.current = controller;
  ```
  Backend (`library_scan.py:38,212-234`):
  ```python
  async def scan_library(request: LibraryScanRequest) -> ScanResultResponse:
      ...
      except asyncio.CancelledError:
          # ...The frontend has two triggers that cancel this request (unmount and
          # supersede), plus server shutdown.
          if connection_manager:
              await connection_manager.broadcast({
                  "type": "library_scan_error",
                  "data": {"error": "library scan cancelled"},
              })
          raise
  ```
  There is no `Request` parameter, no `is_disconnected()` polling loop, and no middleware that cancels route tasks on disconnect anywhere in `auralis-web/backend/`.
- **Impact**: Navigating away from the library view, or clicking "scan" a second time on a different folder, does not stop the first scan's filesystem walk / audio-info extraction / DB writes on the backend — it silently continues consuming CPU, disk I/O, and holds the single scan slot (`max_concurrent_scans` default 1) for up to an hour (`AURALIS_SCAN_TIMEOUT`), rejecting any subsequent scan attempt with 409 even though the user believes they cancelled it. The `except asyncio.CancelledError` branch is real, working code, but its only genuine trigger is app shutdown (uvicorn's own task cancellation during lifespan teardown), not the two frontend triggers the comment describes.
- **Suggested Fix**: Either (a) give the endpoint access to the real `Request` object and poll `await request.is_disconnected()` alongside the scan future so a genuine client disconnect can call `scanner.stop_scan()`, or (b) add an explicit `POST /api/library/scan/cancel` endpoint that the frontend calls on unmount/supersede instead of relying on fetch abort, and update the misleading comment either way.

---

### INT4-02: No resync after a WebSocket drop during a scan — UI can be stuck on "Scanning…" forever
- **Severity**: HIGH
- **Flow**: Flow 4 (Library Scanning)
- **Boundary**: Backend (WebSocket broadcast) → Frontend (WebSocket subscriber)
- **Location**: `auralis-web/backend/routers/library_scan.py:168-190`, `auralis-web/backend/services/library_auto_scanner.py:341-372` → `auralis-web/frontend/src/hooks/library/useScanProgress.ts:59-120`, `auralis-web/frontend/src/hooks/websocket/websocketConnectionCore.ts:210-235`
- **Status**: NEW
- **Description**: Scan lifecycle (`library_scan_started` / `scan_progress` / `scan_complete` / `library_scan_error`) is communicated exclusively via WebSocket broadcast — there is no REST scan-status endpoint (confirmed: no `scan_status`/`is_scanning` route anywhere in `auralis-web/backend/routers/`). If the WebSocket connection drops mid-scan (network blip, laptop sleep/wake, backend restart, or simply the up-to-30s reconnect backoff mentioned in `useWebSocketConnection.ts`) and the scan finishes or errors while the client is disconnected, that terminal broadcast is sent only to clients connected at that instant and is gone. The reconnect/replay logic in `websocketConnectionCore.ts` explicitly only replays *outgoing* client→server messages (queued playback commands) and re-issues the last streaming command — it has no concept of replaying missed *incoming* broadcasts, and `useScanProgress` has no on-reconnect resync call to any status endpoint.
- **Evidence**:
  Backend broadcast is fire-and-forget to currently-connected sockets (`library_scan.py:168-190`):
  ```python
  if connection_manager:
      await connection_manager.broadcast({
          "type": "scan_complete",
          "data": {...},
      })
  ```
  Frontend reconnect only replays outgoing commands (`websocketConnectionCore.ts:210-213`):
  ```ts
  * On (re)connect: flush the offline send-queue, then re-issue the last active
  * ...
  export function replayQueueAndResume(
  ```
  `useScanProgress.ts` has no reconnect hook — `isScanning` only changes on receipt of `library_scan_started`, `scan_progress`, `scan_complete`, or `library_scan_error`, none of which fire again after a reconnect if they were already broadcast while the client was offline.
- **Impact**: A user whose WebSocket connection blips during a long scan (very plausible on a laptop with wifi power-saving, or a backend restart triggered by another concurrent dev/test session per project conventions) sees the "Scanning…" indicator freeze permanently, even though the scan actually completed and the library was updated. The only recovery is a full page reload.
- **Suggested Fix**: Add a lightweight `GET /api/library/scan/status` (or fold into an existing polled endpoint) that `useScanProgress` calls once on WebSocket reconnect to resync `isScanning`/`lastResult`, or have the backend retain the last scan-lifecycle frame and replay it to newly-(re)connected sockets the way `lastStreamCommand` is replayed for playback.

---

### INT6-01: Similarity engine and fingerprint-display endpoints compare in-progress/stale-version fingerprint rows as if valid
- **Severity**: HIGH
- **Flow**: Flow 6 (Fingerprint & Similarity)
- **Boundary**: Library repository (Engine) → Similarity engine / REST endpoints (Backend)
- **Location**: `auralis/library/repositories/fingerprint_repository.py:139-155,234-261,437-453` → `auralis/analysis/fingerprint/similarity.py:132,155,198-199` and `auralis/analysis/fingerprint/knn_graph.py:112-166` and `auralis-web/backend/routers/similarity.py:136` and `auralis-web/backend/routers/fingerprint_status.py:91`
- **Status**: NEW
- **Description**: `FingerprintSchedulerRepository.claim_next_unfingerprinted_track()` inserts a placeholder `TrackFingerprint` row the moment a track is claimed for processing — all 25 dimensions zeroed except a `lufs=-100.0` sentinel — and critically sets `fingerprint_version=FINGERPRINT_ALGORITHM_VERSION` (the *current*, not a sentinel, version). Elsewhere, `claim_next_outdated_fingerprint()` marks re-fingerprinting claims with `fingerprint_version=0`. Both sentinel states (`lufs==-100.0` in-progress placeholders, and stale `0 < fingerprint_version < FINGERPRINT_ALGORITHM_VERSION` rows) are known and explicitly filtered in exactly one place: `FingerprintService._load_from_database()` (the Tier-1 DB cache used by the real-time mastering/streaming path). Every other consumer of `FingerprintRepository` — `exists()`, `get_by_track_id()`, `get_all()`, `get_by_track_ids()`, `get_by_multi_dimension_range()` — applies no such filter, and these are exactly the methods `FingerprintSimilarity`, `KNNGraphBuilder`, and the `/api/similarity/*` and `/api/tracks/{id}/fingerprint` / `/api/albums/{id}/fingerprint` endpoints call directly.
- **Evidence**:
  Guarded path (`auralis/analysis/fingerprint/fingerprint_service.py:189-205`):
  ```python
  # lufs == -100.0 is the placeholder sentinel written by claim_next_unfingerprinted_track
  if fp is None or getattr(fp, 'lufs', -100.0) == -100.0:
      return None
  row_version = int(getattr(fp, 'fingerprint_version', 1) or 1)
  if row_version < FINGERPRINT_ALGORITHM_VERSION:
      logger.info(f"Discarding v{row_version} DB fingerprint ...")
      return None
  ```
  Unguarded path used by similarity (`auralis/library/repositories/fingerprint_repository.py:139-155`):
  ```python
  def get_by_track_id(self, track_id: int) -> TrackFingerprint | None:
      with self._session_scope() as session:
          fingerprint = session.execute(
              select(TrackFingerprint).where(TrackFingerprint.track_id == track_id)
          ).scalars().first()
          if fingerprint:
              session.expunge(fingerprint)
          return fingerprint
  ```
  Placeholder insert (`auralis/library/repositories/fingerprint_scheduler_repository.py:62-75`):
  ```python
  placeholder = TrackFingerprint(
      track_id=track_id,
      sub_bass_pct=0.0, ..., air_pct=0.0,
      lufs=-100.0, crest_db=0.0, ..., stereo_width=0.0, phase_correlation=0.0,
      fingerprint_version=FINGERPRINT_ALGORITHM_VERSION,
  )
  ```
  Consumer that trusts `exists()` alone (`auralis-web/backend/routers/similarity.py:135-150`):
  ```python
  if not await asyncio.to_thread(repos.fingerprints.exists, track_id):
      ... raise HTTPException(404, ...)
  # else: proceeds straight to graph lookup / similarity.find_similar using the row as-is
  ```
- **Impact**: While a track is mid-fingerprinting (a normal, frequent state during a library scan or on-demand enqueue), `exists()` returns `True` for its placeholder row, so `/api/similarity/tracks/{id}/similar` does *not* enqueue it and instead runs a real similarity search using an all-zero vector with `lufs=-100` (far outside the real `-40..-6` LUFS range) — producing meaningless/misleading "similar tracks". `KNNGraphBuilder.build_graph()` pulls the same unfiltered rows via `get_all()`, so a placeholder can be baked into the persisted K-NN graph and served as a plausible neighbor to real tracks until the graph is rebuilt. `FingerprintNormalizer.fit()` also ingests placeholders (and any stale-version rows) into its percentile statistics, skewing normalization for the whole library. `/api/tracks/{id}/fingerprint` and `/api/albums/{id}/fingerprint` (median across tracks) can likewise surface or blend in placeholder/stale data with no indication to the caller that the fingerprint is not the final, current-algorithm value — unlike the mastering path, which self-heals by discarding and recomputing.
- **Suggested Fix**: Add a `lufs != -100.0 AND fingerprint_version = :current_version` (or a small shared helper, mirroring `FingerprintService._load_from_database`'s guard) to `FingerprintRepository.exists()`, `get_by_track_id()`, `get_all()`, `get_by_track_ids()`, and `get_by_multi_dimension_range()` — or expose a repository-level "current, complete fingerprints only" query and have `FingerprintSimilarity`/`KNNGraphBuilder`/the display routers use it exclusively.

---


## MEDIUM Findings

### INT1-01: `usePlayTrack`'s "Now playing" toast fires before the backend confirms `play_enhanced` succeeded, masking silent stream-start rejection
- **Severity**: MEDIUM
- **Flow**: Flow 1 (Track Playback)
- **Boundary**: Frontend (`usePlayTrack`) → Backend (`playback_commands.handle_play_enhanced`) → Frontend (`Player.tsx`)
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayTrack.ts:77-86` → `auralis-web/backend/ws_handlers/playback_commands.py:174-188` → `auralis-web/frontend/src/components/player/Player.tsx:243,327`
- **Status**: NEW
- **Description**: `usePlayTrack.playTrack()` — the hook used by library rows / "Play All" buttons — sends `play_enhanced` over the WebSocket and, without waiting for any acknowledgement, immediately shows a success toast `Now playing: ${track.title}`. `wsContext.send()` is fire-and-forget (no response awaited). If the backend rejects the request — most concretely when the user has toggled enhancement off via `EnhancementToggle`/`useEnhancementControl` (`enabled: false` in the shared runtime settings dict) and `force` is not set — `handle_play_enhanced` sends back `audio_stream_error` with `code: "ENHANCEMENT_DISABLED"` and starts no streaming task at all. Nothing in `usePlayTrack.ts` observes that response, so the toast has already told the user playback started while zero audio ever streams.
  This is a real, easily reachable path: `usePlayTrack` always sends `preset: 'adaptive', intensity: 1.0` with no `force` field, so `force = bool(data.get("force", False))` is always `False` for this entry point — every click through this hook while enhancement is disabled is silently rejected.
  By contrast, the "canonical" player-bar path (`useEnhancedPlayCommand.ts`) does this correctly: it dispatches a neutral `startStreaming` (buffering) state instead of declaring success, and only surfaces `setStreamingError` (shown inline in `Player.tsx`) if the backend rejects the stream — no premature success signal.
- **Evidence**:
  Frontend (`usePlayTrack.ts:74-86`):
  ```ts
  wsContext.send({
    type: 'play_enhanced',
    data: { track_id: track.id, preset: 'adaptive', intensity: 1.0 },
  });
  success(`Now playing: ${track.title}`);
  ```
  Backend (`playback_commands.py:174-188`):
  ```python
  if not enhancement_enabled and not force:
      logger.warning(f"Enhancement disabled, rejecting play_enhanced request for track {track_id}")
      await websocket.send_text(json.dumps({
          "type": "audio_stream_error",
          "data": {"track_id": track_id, "error": "Auto-mastering is currently disabled...",
                   "code": "ENHANCEMENT_DISABLED", "stream_type": "enhanced"}
      }))
      return
  ```
  The only consumer of `audio_stream_error` is `useAudioStreamingCore.ts`'s `handleStreamError`, which dispatches Redux `setStreamingError` — `usePlayTrack.ts` never subscribes to it, so it cannot retract or correct its already-fired toast.
- **Impact**: A user with enhancement disabled who clicks Play from any library/album/playlist row (the majority of real-world play entry points, as opposed to the currently-playing track's own transport controls) sees a green "Now playing: X" toast while audio never starts. The correct information does eventually appear as a contradicting inline error in the always-mounted bottom Player bar (`ComfortableApp.tsx:374`), but the toast itself is never corrected or dismissed, producing conflicting feedback in the same UI at the same time.
- **Suggested Fix**: Either (a) have `usePlayTrack` subscribe to `audio_stream_error`/`audio_stream_start` (scoped to the track it just requested, matching on `track_id`) and only show the success toast once `audio_stream_start` confirms, replacing it with an error toast on `audio_stream_error`; or (b) pass `force: true` from this specific entry point if silently bypassing the enhancement gate is the intended UX for library-initiated plays, and reserve the confirmation toast for genuine failures only.

---

### INT2-02: `useLibraryPagination`'s track transformer never surfaces track genre (reads a field the backend never sends)
- **Severity**: MEDIUM
- **Flow**: Flow 2 (Library Browsing)
- **Boundary**: Backend → Frontend (transformer)
- **Location**: `auralis/library/models/core.py:176-215` (`Track.to_dict()`) → `auralis-web/frontend/src/types/domain.ts:419-434` (`transformBackendTrack`)
- **Status**: NEW
- **Description**: `Track.to_dict()` — the real wire format returned by `GET /api/library/tracks` (via `serialize_tracks()`, which prefers `to_dict()` over the `DEFAULT_TRACK_FIELDS` getattr fallback for real ORM rows) — only ever emits a `genres` **array**, never a singular `genre` key:
  ```python
  # core.py Track.to_dict()
  'artists': artist_names,
  'genres': genre_names,
  ```
  The canonical transformer (`api/transformers/trackTransformer.ts:23`) correctly falls back through the array: `const genre = apiTrack.genres?.[0] ?? apiTrack.genre;`. But `useLibraryPagination.ts` — the hook backing the main "Library" page via `useLibraryWithStats` — uses a second, independent transformer that only reads the singular field:
  ```typescript
  // types/domain.ts transformBackendTrack()
  artist: Array.isArray(track.artists) && track.artists.length > 0
    ? track.artists[0] : track.artist || 'Unknown Artist',   // correctly array-aware
  ...
  genre: track.genre ?? null,                                 // NOT array-aware — always null
  ```
  Note the `artist` field right above it *was* fixed to read the array; `genre` was not, so the two fields in the same function diverge in correctness.
- **Evidence**: Code quoted above from both sides; `LibraryTrack = Pick<Track, ... | 'genre' | ...>` (`types/domain.ts:57`) exposes `genre` as part of the public `LibraryTrack` shape the main library view consumes.
- **Impact**: Any track fetched through the main Library page's `useLibraryWithStats`/`useLibraryPagination` path always has `genre: null`, even when the track has one or more genres recorded in the DB. Today no row-level UI in the main library view actually renders `LibraryTrack.genre` (grep found no consumer besides the edit-metadata dialog, which sources its data separately), so the immediate visual impact is limited — but the field is part of the public hook contract and any future feature (genre badge/filter/group-by-genre in the main list) built against `LibraryTrack.genre` will silently get nothing.
- **Suggested Fix**: Either delete the two competing transformers and route `useLibraryPagination` through the canonical `transformTrack`/`transformTracks` (preferred — matches the project's "no duplicate logic" principle and is exactly what `useLibraryQuery.ts` already did per its own #4611 comment), or fix `transformBackendTrack` to read `track.genres?.[0] ?? track.genre`.

---

### INT2-03: `useRestAPI.ts` discards the backend's error `detail` body on every non-2xx response
- **Severity**: MEDIUM
- **Flow**: Flow 2 (Library Browsing)
- **Boundary**: Backend → Frontend (REST client)
- **Location**: `auralis-web/backend/routers/errors.py:24-33` (`NotFoundError`) → `auralis-web/frontend/src/hooks/api/useRestAPI.ts:108-109`
- **Status**: NEW
- **Description**: Backend errors (e.g. `NotFoundError`, `BadRequestError`, FastAPI's own 422 validation errors) all carry a specific `detail` message in the JSON body, e.g. `{"detail": "Track 123 not found"}`. `useRestAPI.ts` — the shared REST client behind `useLibraryQuery.ts` (tracks/albums/artists list+detail fetching for Flow 2) — throws before ever reading that body:
  ```typescript
  // useRestAPI.ts get()/post()/put()/patch()/delete()
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  ```
  `ApiErrorHandler.parse()` (`types/api.ts:364-373`) then only extracts the numeric status out of that generic string via regex — the specific backend `detail` text is unrecoverable at that point (the response body was never parsed).
- **Evidence**: Quoted above. This is the same underlying pattern already reported for two *other* files — `#4626` (fingerprint/similarity fetches) and `#4643` (`useAlbumDetails.ts`'s own bespoke `fetch`) — but this instance is in the shared, generic `useRestAPI` hook that backs Flow 2's `useLibraryQuery`/track/album/artist listing and detail calls, not in a domain-specific fetch wrapper.
- **Impact**: Every 4xx/5xx from `/api/library/tracks*`, `/api/albums*`, `/api/artists*` surfaces to the UI (and to `error.message` shown in toasts) as a generic "HTTP 404: Not Found" / "HTTP 400: Bad Request" rather than the actionable backend message (e.g. distinguishing "Track not found" from "Invalid confirmation header" from a validation error listing which field failed). No crash, but debugging and user-facing error messages are systematically less useful across the whole flow.
- **Suggested Fix**: Before throwing, attempt `await response.json()` and prefer its `detail` (or FastAPI's `detail` array for 422s) as the error message, falling back to `statusText` only if the body isn't JSON or lacks `detail`.

---

### INT2-04: `GET /api/playlists` results beyond the 200-item page cap are silently unreachable
- **Severity**: MEDIUM
- **Flow**: Flow 2 (Library Browsing)
- **Boundary**: Frontend service → Backend router
- **Location**: `auralis-web/frontend/src/services/playlistService.ts:53,73-79` → `auralis-web/backend/routers/playlists.py:88-127`
- **Status**: NEW (distinct from the now-fixed `#4554`, which added pagination to an endpoint that previously had none at all)
- **Description**: `#4554` fixed `GET /api/playlists` to be properly paginated (`limit`/`offset`/`total`/`has_more`, capped at `le=200`). The frontend's fix, however, was to always request the maximum page size once (`PLAYLISTS_PAGE_LIMIT = 200`) and stop there — none of its three consumers read `has_more`/`offset` to fetch a second page:
  ```typescript
  // playlistService.ts
  export const PLAYLISTS_PAGE_LIMIT = 200;
  ...
  list: (params) => {
    const search = new URLSearchParams({
      limit: String(params?.limit ?? PLAYLISTS_PAGE_LIMIT),
      offset: String(params?.offset ?? 0),
    });
    return `${ENDPOINTS.PLAYLISTS}?${search.toString()}`;
  },
  ```
  `AddToPlaylistMenu.tsx`, `useTrackContextMenu.ts`, and `usePlaylistOperations.ts` all call `getPlaylists()` with no params and never reference `has_more`/`offset` afterward (confirmed via grep — zero matches for those identifiers in any of the three files).
- **Evidence**: See above; `getPlaylists()` (`playlistService.ts:97-124`) does return `has_more`/`offset` in its `PlaylistsResponse`, but the return value is simply unused by every current caller.
- **Impact**: A user with more than 200 playlists (achievable over time via smart playlists / manual creation, no server-side cap on creation) will never see the 201st+ playlist in the playlist view, the "Add to playlist" menu, or the track context menu — with no error, loading indicator, or "load more" affordance. The data is silently truncated.
- **Suggested Fix**: Either wire `has_more`/`offset` into an actual "load more"/pagination UI for the three consumers, or — given playlists are a bounded, user-curated collection unlike tracks — raise the cap and page through it internally in `getPlaylists()` until `has_more` is false, similar to how `getPlaylists()` already aggregates today's single page.

---

### INT2-05: Artist `dateAdded` is part of the frontend contract but the backend never returns it
- **Severity**: MEDIUM
- **Flow**: Flow 2 (Library Browsing)
- **Boundary**: Backend → Frontend (schema/transformer)
- **Location**: `auralis-web/backend/routers/artists.py:23-31` (`ArtistResponse`) → `auralis-web/frontend/src/api/transformers/artistTransformer.ts:29-33`
- **Status**: NEW
- **Description**: `ArtistResponse`, the Pydantic model backing `GET /api/artists`, has no `date_added`/`created_at` field at all:
  ```python
  class ArtistResponse(BaseModel):
      id: int
      name: str
      album_count: int
      track_count: int
      genres: list[str] | None = None
      artwork_url: str | None = None
      artwork_source: str | None = None
  ```
  Yet `transformArtist()` maps a `date_added` field that can never exist on the wire, and the frontend's `ArtistApiResponse` TS type even declares it optional in anticipation:
  ```typescript
  dateAdded: apiArtist.date_added ?? undefined, // snake → camel, null → undefined
  ```
  `Artist.to_dict()` (the ORM model, `models/core.py:329-344`) *does* compute `created_at`, but the router builds `ArtistResponse` field-by-field from the ORM object and never copies it across.
- **Evidence**: Quoted above; confirmed no test exercises the real endpoint's response shape for this field — `useLibraryQuery.test.ts:1086` asserts `artist.dateAdded` against a hand-authored mock response that includes `date_added`, which the real backend endpoint never produces, masking the gap.
- **Impact**: `Artist.dateAdded` is always `undefined` from every artist-list code path today. No current UI reads it (grep found zero consumers outside tests/transformers), so there's no visible breakage yet, but the contract is misleading — a future "sort/filter artists by date added" feature would silently get nothing, and the passing unit test creates false confidence that the field round-trips correctly.
- **Suggested Fix**: Either add `created_at: str | None` to `ArtistResponse` (populated from `artist.created_at.isoformat()`) and rename to match the transformer's expectation, or drop `dateAdded` from the `Artist` domain type and `ArtistApiResponse`/transformer until it's actually wired up.

---

### INT4-03: Discovery walks every folder twice before processing, doubling I/O with no feedback during the first pass
- **Severity**: MEDIUM
- **Flow**: Flow 4 (Library Scanning)
- **Boundary**: Engine (file discovery) → Frontend (progress display)
- **Location**: `auralis/library/scanner/scanner.py:191-195` → `auralis/library/scanner/file_discovery.py:86-108` → `auralis-web/frontend/src/hooks/library/useScanProgress.ts:42-53`
- **Status**: NEW
- **Description**: To give `scan_progress.percentage` a real (non-null) denominator (per the #4616 fix), `scan_directories()` runs a full recursive `count_audio_files()` pass over every configured directory *before* the actual streaming discovery+processing pass runs the same recursive walk again. `count_audio_files()` is implemented as `sum(1 for _ in self.discover_audio_files(...))` — i.e. it performs the identical `os.scandir` recursion (including `Path.stat()` per directory for the symlink-cycle check) a second time. During this first pass the scanner emits only `stage: 'discovering'` progress with `progress: None` (indeterminate) and no `current`/`total` a user can read as forward motion.
- **Evidence**:
  ```python
  # scanner.py:191-196
  total_expected: int = 0
  for directory in directories:
      if self.should_stop.is_set():
          break
      total_expected += self.file_discovery.count_audio_files(directory, recursive)
  ```
  ```python
  # file_discovery.py:86-108
  def count_audio_files(self, directory: str, recursive: bool = True) -> int:
      ...
      return sum(1 for _ in self.discover_audio_files(directory, recursive))
  ```
  `useScanProgress.ts`'s `ScanProgress.percentage` stays `null` (indeterminate spinner, no count) for the entire duration of this first pass.
- **Impact**: For very large libraries (tens/hundreds of thousands of files) or folders on slow storage (network shares, external/USB drives — a realistic desktop-app scenario), the recursive stat-per-entry counting pass can itself take minutes, during which the UI shows nothing but an indeterminate spinner with zero numeric feedback, then repeats the identical directory walk for real. Net effect: total wall-clock scan time for discovery-bound (many small files, slow storage) libraries is roughly doubled versus a single-pass design.
- **Suggested Fix**: Either cache/stream file paths discovered in the counting pass into the batches consumed by the processing pass (trading the "#2160 unbounded memory" concern only for the count metadata, e.g. store paths in a spill-to-disk queue or accept a bounded in-memory list capped at a size threshold), or emit periodic `stage: 'discovering'` progress frames with a running counted-so-far value during the count pass itself so the UI at least shows movement instead of pure indeterminate silence.

---

### INT4-04: Per-file scan failures reach the UI only as an opaque aggregate count — no filename or reason crosses the boundary
- **Severity**: MEDIUM
- **Flow**: Flow 4 (Library Scanning)
- **Boundary**: Engine (batch processor) → Backend (WS broadcast) → Frontend (UI)
- **Location**: `auralis/library/scanner/batch_processor.py:85-89,147-149` → `auralis-web/backend/routers/library_scan.py:172-180` → `auralis-web/frontend/src/hooks/library/useLibraryScan.ts:87-96`
- **Status**: NEW
- **Description**: When a file can't be read, has corrupt tags, or fails audio-info extraction, `BatchProcessor` catches the exception and only logs it (`debug`/`error`), returning a bare `'failed'` status with no file path or reason retained on the `ScanResult`. The router/auto-scanner then broadcast only `files_failed: <int>` to the frontend. `useLibraryScan.ts` and `useScanProgress.ts` (`ScanResult.filesFailed`) can therefore only ever tell the user "N files failed" — never which files, or why (permission denied vs. corrupt header vs. unsupported codec all collapse into the same integer).
- **Evidence**:
  ```python
  # batch_processor.py:85-89
  except Exception as e:
      error(f"Failed to process {file_path}: {e}")
      result.files_failed += 1
  ```
  ```python
  # batch_processor.py:147-149 (process_single_file's own catch)
  except Exception as e:
      debug(f"Error processing {file_path}: {e}")
      return 'failed', None
  ```
  ```python
  # library_scan.py:172-176 — only the count crosses the boundary
  "files_failed": result.files_failed,
  ```
  ```ts
  // useLibraryScan.ts:88-96 — UI can only ever show a count
  const failed = result.files_failed || 0;
  ...
  const summary = `Scan complete! Added ${added} tracks${extras ? ` (${extras})` : ''}`;
  if (failed > 0) toastRef.current.toastError(summary);
  ```
  Note the `process_single_file` failure path even uses `debug()`, a level generally not surfaced in default logging configurations, for the more common failure ("audio_info extraction returned falsy" / any exception), while the batch-level wrapper uses `error()` — the per-file detail is inconsistently leveled even server-side.
  ```python
  # batch_processor.py:106-127 (excerpt)
  audio_info = self.audio_analyzer.extract_audio_info(file_path)
  if not audio_info:
      return 'failed', None
  ```
- **Impact**: A user who scans a folder with a handful of corrupt/unreadable files gets a toast saying e.g. "Scan complete! Added 40 tracks (3 failed)" with no way to identify or fix the 3 problem files short of digging through backend logs (which may not even be visible to a desktop-app end user, and one of the two failure sites logs at `debug`).
- **Suggested Fix**: Accumulate `(filepath, reason)` pairs on `ScanResult` (bounded, e.g. first N failures) and thread them through the `scan_complete` WS payload / `ScanResultResponse`, or add a lightweight follow-up “Scan issues” panel populated from a small failures list.

---

### INT4-05: Exact case-sensitive filepath matching causes duplicate library rows on rescan for the officially-shipped Windows/macOS builds
- **Severity**: MEDIUM
- **Flow**: Flow 4 (Library Scanning)
- **Boundary**: Engine (file discovery / repository lookup)
- **Location**: `auralis/library/scanner/file_discovery.py:157-161` → `auralis/library/repositories/track_repository.py:316-326` (`get_by_path`), `auralis/library/models/core.py:92`
- **Status**: NEW
- **Description**: `TrackRepository.get_by_path()` (used by `BatchProcessor.process_single_file` for `skip_existing`) and `Track.filepath` itself match/store paths via plain, case-sensitive string equality (`Track.filepath == filepath`), and the discovered path is whatever string `os.scandir`/`Path` produced during that particular walk — no case-folding or canonicalization is applied anywhere in the scan path. On Linux (the primary dev/test target) filesystems are case-sensitive so this is a non-issue in practice. However, per project history the desktop app ships Windows and macOS builds too (`docs/audits` / project memory: "Desktop build pipeline restored… Windows/macOS/Linux… all 4 targets verified green"), and both NTFS (Windows) and default APFS (macOS) are case-insensitive-but-preserving: the *same physical file* is reachable via multiple differently-cased path strings that the OS treats as identical but that Auralis's DB layer treats as different rows.
- **Evidence**:
  ```python
  # track_repository.py:316-326
  def get_by_path(self, filepath: str) -> Track | None:
      """Get track by file path with relationships loaded"""
      with self._session_scope() as session:
          track = session.execute(
              select(Track)
              .options(*_track_eager_options())
              .where(Track.filepath == filepath)
          ).scalars().unique().first()
  ```
  ```python
  # models/core.py:92
  filepath: Mapped[str] = mapped_column(String, nullable=False, unique=True)
  ```
  No `.lower()`/`os.path.normcase()` call exists anywhere between file discovery and this comparison (`grep -rn "normcase\|filepath.lower" auralis/library/` returns nothing).
- **Impact**: On Windows/macOS, if the same folder is scanned twice with a differently-cased path component anywhere in the tree (e.g. the manual-scan web-fallback text field is retyped with different casing, or a case-varying mount point is used), `get_by_path()` returns `None` for the "new" casing, `skip_existing`/`check_modifications` never recognizes the file as already present, and a second `Track` row is inserted for the same physical audio file — `filepath`'s DB-level `unique=True` only protects against an *identical* string, not a case-insensitive collision, so no `IntegrityError` guards this case. Result: duplicate entries in albums/playlists/library views for what the OS considers one file.
- **Suggested Fix**: Canonicalize discovered paths (e.g. `os.path.normcase()` combined with a platform check, or resolving to the OS's canonical casing before storing/looking up) at the single point where filenames enter the pipeline (`file_discovery.py` or `batch_processor.py`), rather than at every call site.

---

### INT5-01: `HeartbeatManager.timeout_seconds` cannot influence detection latency — it is dominated by the 30s ping cadence
- **Severity**: MEDIUM
- **Flow**: Flow 5 (WebSocket Lifecycle)
- **Boundary**: Backend → Backend (internal heartbeat loop, self-check) — surfaced here because it governs how fast a dead/hung connection is evicted, i.e. how fast the frontend's reconnect logic gets triggered
- **Location**: `auralis-web/backend/ws_handlers/connection.py:46-62` (`_heartbeat_loop`) → `auralis-web/backend/websocket/websocket_protocol.py:19-84` (`HeartbeatManager`)
- **Status**: NEW
- **Description**: `HeartbeatManager` is constructed with `interval_seconds=30, timeout_seconds=10` (`connection.py:46`). The loop body is:
  ```python
  while True:
      await asyncio.sleep(heartbeat.interval_seconds)   # always waits the full 30s
      if heartbeat.is_stale(connection_id):
          ...close...
      await websocket.send_text(json.dumps({"type": "ping"}))
      heartbeat.mark_ping(connection_id)
  ```
  `is_stale()` is only ever evaluated once per 30-second cycle, immediately *before* the next ping is sent — i.e. exactly `interval_seconds` after the previous `mark_ping()`, never `timeout_seconds` after it. Since `is_stale()`'s own check is `elapsed > self.timeout_seconds` (`websocket_protocol.py:82-83`), and `elapsed` at check time is always ≈`interval_seconds` (30s) once a ping goes unanswered, the check is `30 > 10`, which is unconditionally `True` regardless of what `timeout_seconds` is configured to (unless someone sets `timeout_seconds >= interval_seconds`, which would delay detection by a further full cycle instead of shortening it). The `timeout_seconds=10` value can never make detection happen any faster than one full `interval_seconds` cycle — it is effectively inert for its stated purpose ("timeout before considering connection dead"). A reader of the constructor signature or the docstring (`websocket_protocol.py:26-31`, "timeout_seconds: Timeout before considering connection dead (default 10s)") would reasonably expect a ~10s detection window; the actual worst-case latency is up to `2 × interval_seconds` (60s) from the client's last real activity, and best case is `interval_seconds` (30s) after the missed ping.
- **Evidence**:
  ```python
  # ws_handlers/connection.py:46-62
  heartbeat = HeartbeatManager(interval_seconds=30, timeout_seconds=10)
  async def _heartbeat_loop() -> None:
      while True:
          await asyncio.sleep(heartbeat.interval_seconds)
          if heartbeat.is_stale(connection_id):
              await websocket.close(code=1001, reason="Heartbeat timeout")
              return
          try:
              await websocket.send_text(json.dumps({"type": "ping"}))
              heartbeat.mark_ping(connection_id)
          except Exception:
              return
  ```
  ```python
  # websocket/websocket_protocol.py:77-83
  def is_stale(self, connection_id: str) -> bool:
      """Check if connection has pending pong for too long."""
      if connection_id not in self.pending_pongs:
          return False
      elapsed = (datetime.now(timezone.utc) - self.pending_pongs[connection_id]).total_seconds()
      return elapsed > self.timeout_seconds
  ```
  Trace: ping sent at t=30 → `mark_ping` sets `pending_pongs[cid]=t30`. If unanswered, the *next* opportunity to observe this is the *next* loop wake at t=60, where `elapsed = 60-30 = 30s`, and `30 > 10` is already true — the 10s boundary was crossed 20 seconds before anyone checked.
- **Impact**: Not a correctness bug (dead connections are still evicted, and the frontend's own `onclose`-triggered reconnect plus its independent 30s client `heartbeat` keepalive (`utils/errorHandling.ts:213-221`) bound the practical outage), but the configured SLA is misleading: anyone tuning `timeout_seconds` down (e.g. to 3s, expecting faster failover for a hung connection) gets no improvement at all unless `interval_seconds` is also lowered, since the check only ever fires on the `interval_seconds` cadence. Mitigated by the localhost desktop deployment, where TCP-level `onclose` typically fires immediately on process death anyway, making this heartbeat path mainly a backstop for an application-level hang (e.g. a blocked event loop) rather than the primary disconnect-detection mechanism.
- **Suggested Fix**: Either check staleness on a shorter cadence than `interval_seconds` (e.g. `asyncio.sleep(min(interval_seconds, timeout_seconds))` in the loop, with ping-sending gated separately), or drop the separate `timeout_seconds` parameter/docstring claim and document that detection latency is simply `~1-2× interval_seconds`.


---

### INT6-02: `/api/similarity/fit` and `/api/similarity/graph/build` are documented as multi-minute operations but the frontend client hard-caps every request at 30s with no override
- **Severity**: MEDIUM
- **Flow**: Flow 6 (Fingerprint & Similarity)
- **Boundary**: Frontend `similarityService.ts` → Backend `similarity.py` / `similarity_graph.py`
- **Location**: `auralis-web/frontend/src/services/similarityService.ts:97,153-155` → `auralis-web/frontend/src/utils/serviceFactory.ts:29-31,174-203` and `auralis-web/frontend/src/utils/apiRequest.ts:18` → `auralis-web/backend/routers/similarity_graph.py:53-63` / `auralis-web/backend/routers/similarity.py:326-334`
- **Status**: NEW
- **Description**: The backend's own docstrings state both operations can take "several minutes for large libraries" and are deliberately CPU-bound O(N²) work offloaded to a thread (`asyncio.to_thread`) precisely so they can run that long without blocking the event loop. The frontend's shared request layer defaults every fetch to a 30-second timeout (`DEFAULT_TIMEOUT_MS = 30000`), and the CRUD-factory `custom()` method that both `fit()` and `buildGraph()` go through only accepts a `signal` override (`CrudRequestOptions = Pick<RequestOptions, 'signal'>`) — `timeoutMs` is intentionally not exposed to callers. Neither `similarityService.fit()` nor `similarityService.buildGraph()` passes any override, so both are subject to the 30s default regardless of library size.
- **Evidence**:
  Backend intent (`auralis-web/backend/routers/similarity_graph.py:59-63`):
  ```python
  """
  Build K-nearest neighbors similarity graph
  Pre-computes similarity relationships for fast queries.
  This can take several minutes for large libraries.
  """
  ```
  Frontend caller with no timeout override (`auralis-web/frontend/src/services/similarityService.ts:153-155,180-182`):
  ```ts
  export async function buildGraph(k: number = 10): Promise<GraphStats> {
    return crudService.custom<GraphStats>('buildGraph', 'post', { k });
  }
  export async function fit(minSamples: number = 10): Promise<FitResult> {
    return crudService.custom<FitResult>('fit', 'post', { minSamples });
  }
  ```
  Factory intentionally narrows options to `signal` only (`auralis-web/frontend/src/utils/serviceFactory.ts:24-31`):
  ```ts
  export type CrudRequestOptions = Pick<RequestOptions, 'signal'>;
  // Widening this to the full `RequestOptions` would let a caller pass `validate`
  // and silently override the endpoint's configured `guards`... Cancellation is
  // the capability the factory was missing; nothing else.
  ```
- **Impact**: On a library large enough to make `fit`/`build_graph` take longer than 30s, the browser's fetch aborts and the UI surfaces a spurious timeout/failure — while the backend keeps running the `asyncio.to_thread` job to completion in the background (nothing observes client disconnection to cancel it). A user who retries after the apparent failure can kick off a second concurrent `fit()`/`build_graph()` against the same unsynchronized `FingerprintNormalizer`/graph-build state. The end-state the UI reports ("failed") does not match the true end-state (eventually succeeds), and repeated retries waste CPU.
- **Suggested Fix**: Either expose a per-call `timeoutMs` override in `CrudRequestOptions` for long-running admin operations (fit/build_graph specifically, not the general case the comment guards against), or have the two endpoints move to a background-job pattern (submit + poll status) consistent with how the rest of the fingerprint pipeline already handles long-running work (the fingerprint queue).

---

### INT6-03: Similarity "explain" dimension values render as if already percentages, but the raw values backing `_pct` dimensions are 0-1 fractions
- **Severity**: MEDIUM
- **Flow**: Flow 6 (Fingerprint & Similarity)
- **Boundary**: Backend `similarity.py` (explain endpoint) → Frontend `SimilarityTopDifferences.tsx` / `useSimilarityFormatting.ts`
- **Location**: `auralis/analysis/fingerprint/similarity.py:258-272` (raw denormalized values) and `auralis/analysis/fingerprint/schema.py:46-52` (unit definitions) → `auralis-web/frontend/src/components/features/discovery/useSimilarityFormatting.ts:28-31` and `SimilarityTopDifferences.tsx:70,73`
- **Status**: NEW
- **Description**: `schema.py`'s `DIMENSION_SCHEMA` defines every `*_pct` dimension (`sub_bass_pct` … `air_pct`) as `Unit.FRACTION` with semantic ranges like `(0.00, 0.30)` — i.e., the DB/vector values are 0-1 fractions despite the `_pct` name. `get_similarity_explanation()` returns these exact raw values (`raw1[idx]`, `raw2[idx]`) as `value1`/`value2` in `DimensionContribution`, unconverted. The frontend's `formatValue()` special-cases any dimension whose name contains `"pct"` and renders `${value.toFixed(1)}%` directly — i.e., it assumes the value is already on a 0-100 scale and only needs a `%` suffix appended.
- **Evidence**:
  Backend schema truth (`auralis/analysis/fingerprint/schema.py:46-52`):
  ```python
  'sub_bass_pct':  (Unit.FRACTION, 0.00, 0.30),
  'bass_pct':      (Unit.FRACTION, 0.05, 0.50),
  ...
  ```
  Backend explain payload (`auralis/analysis/fingerprint/similarity.py:262-272`):
  ```python
  def _entry(dim: str, contrib: float) -> dict[str, Any]:
      idx = dim_index.get(dim)
      v1 = float(raw1[idx]) if idx is not None and idx < len(raw1) else 0.0
      v2 = float(raw2[idx]) if idx is not None and idx < len(raw2) else 0.0
      return {'dimension': dim, 'contribution': float(contrib), 'value1': v1, 'value2': v2, 'difference': v1 - v2}
  ```
  Frontend rendering (`auralis-web/frontend/src/components/features/discovery/useSimilarityFormatting.ts:28-31`):
  ```ts
  if (dimension.includes('pct')) {
    return `${value.toFixed(1)}%`;
  }
  ```
  called with the raw fraction (`SimilarityTopDifferences.tsx:70,73`):
  ```tsx
  Track 1: {formatValue(diff.value1, diff.dimension)}
  Track 2: {formatValue(diff.value2, diff.dimension)}
  ```
- **Impact**: A `bass_pct` value of `0.25` (25% of spectral energy) renders as `"0.3%"` in the SimilarityVisualization "top differences" panel — roughly 100x too small — for every one of the 7 frequency-band dimensions whenever they appear in the top contributors. This misrepresents the actual acoustic difference driving the similarity score to anyone inspecting why two tracks were matched.
- **Suggested Fix**: Either have `formatValue()` multiply `_pct` dimension values by 100 before formatting (matching how `SimilarityAllDimensions.tsx` already does `contrib.contribution * 100` for the weighted-contribution display), or have the backend's `_entry()` denormalize `_pct` dims to 0-100 before sending, consistent with whichever convention the rest of the payload should use.

---

### INT6-04: `useTrackFingerprint`'s error handling collapses server errors into the same "not ready yet" state as a queued fingerprint, causing indefinite 5s polling on persistent failures
- **Severity**: MEDIUM
- **Flow**: Flow 6 (Fingerprint & Similarity)
- **Boundary**: Frontend `useTrackFingerprint.ts` ↔ Backend `fingerprint_status.py`
- **Location**: `auralis-web/frontend/src/hooks/fingerprint/useTrackFingerprint.ts:29-46,85-91`
- **Status**: NEW
- **Description**: `fetchTrackFingerprint()` treats a 404 (legitimately "not fingerprinted yet") and every other failure mode (5xx, network error, JSON parse error) identically: both paths resolve to `null` rather than the error propagating to React Query. `useQuery`'s `refetchInterval` callback then polls every 5s (default) *whenever `query.state.data === null`* — which is now true both for "genuinely queued" and "the endpoint is broken" — with no upper bound, no backoff, and `retry: false` masking the fact that `query.error` will never be populated (the query function never rejects).
- **Evidence**:
  ```ts
  const fetchTrackFingerprint = async (trackId: number): Promise<TrackFingerprintResponse | null> => {
    try {
      const response = await fetch(`/api/tracks/${trackId}/fingerprint`);
      if (!response.ok) {
        if (response.status === 404) { return null; }
        throw new Error(`Failed to fetch track fingerprint: ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      console.warn(`Failed to fetch fingerprint for track ${trackId}:`, error);
      return null; // Graceful fallback
    }
  };
  ...
  refetchInterval: (query) => {
    if (query.state.data === null) { return retryInterval; }  // default 5000ms
    return false;
  },
  ```
- **Impact**: If the `/api/tracks/{id}/fingerprint` endpoint starts returning 500s (DB issue, unhandled exception) or the network is briefly degraded, the AlbumCharacterPane silently polls that track's fingerprint every 5 seconds forever for as long as the component stays mounted, with the UI stuck showing "pending" (`isPending: query.data === null` is also always true in this state) instead of ever surfacing an error — the one case the hook's own JSDoc claims to handle ("Error handling with graceful fallback") is exactly the case that becomes invisible and unbounded.
- **Suggested Fix**: Distinguish the two states — keep returning `null` (no polling change) only for a genuine 404, but let other failures reject (or return a tagged `{status: 'error'}` result) so `refetchInterval` can stop polling and `isPending`/`error` can be reported distinctly to the caller.

---

### INT7-01: Embedded/folder artwork extractor still mislabels non-JPEG/PNG bytes with the wrong file extension — the sibling bug to #4419, never fixed on this path
- **Severity**: MEDIUM
- **Flow**: Flow 7 (Artwork)
- **Boundary**: Engine (embedded-artwork extraction) → Backend (artwork GET endpoint's extension-based Content-Type)
- **Location**: `auralis/library/artwork.py:281-320` (`ArtworkExtractor._save_artwork`) → `auralis-web/backend/routers/artwork.py:269-291` (`get_album_artwork` MIME detection)
- **Status**: NEW
- **Description**: `#4419` fixed exactly this bug class in `services/artwork_downloader.py`: online-downloaded artwork used to always save with a `.jpg` extension regardless of the actual bytes, so a PNG/WebP response got served as `image/jpeg`. The fix there was to sniff magic bytes (`_detect_image_extension`) before choosing the extension. The **embedded/folder-artwork extractor** (`auralis/library/artwork.py`, a completely separate code path used by `POST /artwork/extract` and initial library scanning) has the identical defect and was never touched: `_save_artwork` only special-cases `'png' in mime_type.lower()`; every other MIME — including `image/gif` and `image/webp`, both of which are valid, real-world ID3 `APIC` / FLAC `PICTURE` MIME values — falls through to the `.jpg` default. Once saved as `.jpg`, the GET endpoint's `mimetypes.guess_type()` succeeds on the extension alone (`image/jpeg`) and never reaches its own magic-byte fallback, because that fallback only triggers `if not media_type or not media_type.startswith("image/")` — an incorrect-but-still-`image/*` guess passes silently.
- **Evidence**:
  ```python
  # auralis/library/artwork.py:293-298 (_save_artwork)
  if mime_type and 'png' in mime_type.lower():
      ext = '.png'
  else:
      ext = '.jpg'  # Default to JPEG -- also hit for image/gif, image/webp
  ```
  ```python
  # auralis/library/artwork.py:166-182 (_extract_from_id3) -- passes the tag's REAL mime through unchanged
  for key in tags.keys():
      if key.startswith('APIC'):
          apic = tags[key]
          return apic.data, apic.mime   # e.g. "image/gif" is passed straight to _save_artwork
  ```
  ```python
  # auralis-web/backend/routers/artwork.py:272-291
  media_type, _ = mimetypes.guess_type(str(requested_path))  # ".jpg" -> "image/jpeg", succeeds
  if not media_type or not media_type.startswith("image/"):
      # magic-byte sniff never reached -- media_type already "image/jpeg"
      ...
  ```
  Compare to the already-fixed sibling in `services/artwork_downloader.py:30-47,341-343`, which sniffs magic bytes before choosing the extension — the fix that was never ported to `auralis/library/artwork.py`.
- **Impact**: A track with an embedded GIF or WebP cover (nonstandard but valid; also reachable via the `METADATA_BLOCK_PICTURE`/FLAC `Picture.mime` path) gets saved as `album_{id}_{hash}.jpg` and served with `Content-Type: image/jpeg`. Since `SecurityHeadersMiddleware` sets `X-Content-Type-Options: nosniff`, browsers are discouraged from correcting a wrong subtype via content sniffing for `<img>` in strict UAs, and at minimum the browser attempts to decode GIF/WebP bytes as JPEG and fails — the artwork renders as a broken image (falls to the frontend's onError placeholder, so not a crash, but the user's actual cover art never displays).
- **Suggested Fix**: Reuse `services/artwork_downloader._detect_image_extension()` (or hoist it to a shared utility both modules import — same DRY pattern already established) inside `ArtworkExtractor._save_artwork`, sniffing the real bytes instead of trusting the tag's declared `mime_type` string.

---

### INT7-02: Re-extracting or re-downloading album artwork orphans the previous artwork file — unbounded disk growth, no cleanup path
- **Severity**: MEDIUM
- **Flow**: Flow 7 (Artwork)
- **Boundary**: Backend (`extract`/`download` endpoints) → Library repository (artwork path persistence)
- **Location**: `auralis-web/backend/routers/artwork.py:333-376,414-482` → `auralis/library/repositories/album_repository.py:180-215` (`extract_and_save_artwork`), `:272-306` (`update_artwork_path`)
- **Status**: NEW
- **Description**: The explicit `DELETE /api/albums/{id}/artwork` path correctly removes the on-disk file (`self.artwork_extractor.delete_artwork(album.artwork_path)` before clearing the DB column). Neither of the other two write paths does this: `extract_and_save_artwork()` (backing `POST /artwork/extract`) and `update_artwork_path()` (backing `POST /artwork/download`) both simply overwrite `album.artwork_path` with a new value — if the album already had artwork at a different path (e.g., the user previously extracted embedded art, then clicks "download from web", or re-extracts after re-tagging a track so the content hash — and therefore filename — changes), the old file is never unlinked. Since every write generates a unique `album_{id}_{content_hash}.ext` filename (by design, to make caching keys well-defined), every re-extract/re-download that produces different bytes leaves one more permanent orphan under `~/.auralis/artwork`, and there is no sweeper anywhere in the codebase (`scanner.py`, `manager.py`, `database.py` have no references to artwork cleanup).
- **Evidence**:
  ```python
  # album_repository.py:245-265 (delete_artwork) -- DOES delete the file
  if album and album.artwork_path:
      self.artwork_extractor.delete_artwork(album.artwork_path)
      album.artwork_path = None
      session.commit()
  ```
  ```python
  # album_repository.py:272-301 (update_artwork_path) -- used by the download flow, no file cleanup
  album.artwork_path = artwork_path   # overwrites; old file at the previous album.artwork_path untouched
  session.commit()
  ```
  ```python
  # album_repository.py:201-213 (extract_and_save_artwork) -- same gap
  if artwork_path:
      album.artwork_path = artwork_path   # previous artwork_path (if any) never unlinked
      session.commit()
  ```
- **Impact**: Slow, unbounded accumulation of orphaned image files in `~/.auralis/artwork` (and their now-unreachable derived thumbnails in `~/.auralis/artwork/thumbnails`, compounding #4532) every time a user re-extracts or re-downloads artwork for the same album. Not user-visible per action, but a library with frequent re-tagging/artwork touch-ups slowly leaks disk space with no way to reclaim it short of manually clearing the directory.
- **Suggested Fix**: Before overwriting `album.artwork_path` in both `extract_and_save_artwork()` and `update_artwork_path()`, capture the old path and unlink it (mirroring `delete_artwork`'s existing file-removal call) once the new path is successfully committed — same pattern, two more call sites.

---


## LOW Findings

### INT2-06: Three separate, unused pagination-parameter definitions with three different limits
- **Severity**: LOW
- **Flow**: Flow 2 (Library Browsing)
- **Boundary**: Backend (internal) — dead code / doc rot
- **Location**: `auralis-web/backend/routers/pagination.py:95-121` vs `auralis-web/backend/schemas.py:265-282` vs actual inline `Query(50, ge=1, le=200)` in `tracks.py`/`albums.py`/`artists.py`/`playlists.py`
- **Status**: NEW
- **Description**: `routers/pagination.py` defines `PaginationParams` (`MAX_LIMIT = 200`) and a generic `PaginatedResponse[T]` model with a docstring claiming it "eliminates the duplication... that appears in 6+ router response models" — but grepping the whole backend shows `PaginatedResponse` is never imported by any router, and `PaginationParams` is only referenced by its own module. Separately, `schemas.py` defines its *own*, differently-capped `PaginationParams`/`CursorPaginationParams` (`le=500`) and `SearchRequest` (`le=100`), none of which are imported by any router either. Every real list endpoint (`tracks.py`, `albums.py`, `artists.py`, `playlists.py`) instead hand-rolls `Query(50, ge=1, le=200)` and its own `has_more` arithmetic inline.
- **Evidence**: `grep -rln "PaginatedResponse\b" auralis-web/backend` outside `pagination.py` → no matches. `grep -rn "schemas\.PaginationParams\|schemas\.CursorPaginationParams\|schemas\.SearchRequest"` → no matches.
- **Impact**: No functional bug (the real endpoints are internally consistent at `le=200`), but three conflicting "the max page size is X" definitions (200 / 200 / 500) sit unused in the codebase, which is exactly the kind of drift that leads someone to wire up the `schemas.py` 500-cap model against an endpoint expecting 200 and get an unexpected 422, or to "consolidate" onto the wrong one.
- **Suggested Fix**: Delete the two unused model sets (or actually adopt `PaginatedResponse`/`PaginationParams` from `pagination.py` as the shared dependency across the four routers, per its own stated intent, and delete `schemas.py`'s duplicates).

---

### INT3-03: Engine defines a sixth "live" preset that is unreachable through the API — absent from `VALID_PRESETS`/`EnhancementPresetLiteral` and the frontend's `ENHANCEMENT_PRESETS` union
- **Severity**: LOW
- **Flow**: Flow 3 (Audio Enhancement)
- **Boundary**: Engine (auralis/core/processing/continuous_space.py) ↔ Backend (schemas.py) ↔ Frontend (types/domain.ts)
- **Location**: `auralis/core/processing/continuous_space.py:106-152` vs `auralis-web/backend/schemas.py:27-28` vs `auralis-web/frontend/src/types/domain.ts:169-182`
- **Status**: NEW
- **Description**: `PreferenceVector.from_preset_name()` — actively called on the live processing path from `continuous_mode.py:301-302` (`preference = PreferenceVector.from_preset_name(preset_name)` where `preset_name = self.config.mastering_profile`) — defines a `'live'` preset with its own distinct DSP bias (`dynamic_bias=0.4, stereo_bias=0.2, bass_boost=-0.2`), documented as one of "adaptive, gentle, warm, bright, punchy, live". But `VALID_PRESETS`/`EnhancementPresetLiteral` in `schemas.py:27-28` (the single source of truth the enhancement router, settings route, and WS handler all import) only lists the first five, and the frontend's `ENHANCEMENT_PRESETS`/`EnhancementPreset` union (`types/domain.ts:169-182`) matches that same five. Since `config.mastering_profile` can only ever be set to one of those five values (`ProcessorFactory.get_or_create`: `config.mastering_profile = preset.lower()`, itself constrained by the API-level Literal/enum upstream), `'live'` can never be reached by any real request — it is either dead code that should be removed, or a shipped-but-never-exposed feature.
- **Evidence**:
  ```python
  # continuous_space.py:114,145-149
  # Args: preset: Preset name (adaptive, gentle, warm, bright, punchy, live)
  'live': cls(
      dynamic_bias=0.4, stereo_bias=0.2, bass_boost=-0.2,
  ),
  ```
  ```python
  # schemas.py:27-28
  VALID_PRESETS = ["adaptive", "gentle", "warm", "bright", "punchy"]
  EnhancementPresetLiteral = Literal["adaptive", "gentle", "warm", "bright", "punchy"]
  ```
- **Impact**: No wrong output for any reachable request (the `.get(preset.lower(), cls())` fallback is safe), so this is purely a maintainability/enumeration-consistency gap, not a functional bug — but it means "live" mode DSP tuning work has already been done in the engine with no way for a user to ever select it, and no test can exercise it via the real API surface.
- **Suggested Fix**: Either add `'live'` to `VALID_PRESETS`/`EnhancementPresetLiteral`/`ENHANCEMENT_PRESETS` (and the corresponding frontend UI) to ship it, or delete the `'live'` branch from `PreferenceVector.from_preset_name` as dead code, per the project's "no unreachable variants" principle.

---

### INT4-06: Bulk settings update accepts unvalidated `scan_folders`, unlike the dedicated add-folder endpoint
- **Severity**: LOW
- **Flow**: Flow 4 (Library Scanning)
- **Boundary**: Backend (schema validation asymmetry)
- **Location**: `auralis-web/backend/routers/settings.py:63` (`SettingsUpdateRequest.scan_folders`) vs. `auralis-web/backend/routers/settings.py:200-214` (`add_scan_folder`)
- **Status**: NEW
- **Description**: `POST /api/settings/scan-folders` validates and canonicalizes every folder through `validate_user_chosen_directory()` (resolves symlinks, rejects `..`, requires existence) before persisting. The generic bulk `PUT /api/settings` (`SettingsUpdateRequest.scan_folders: list[str] | None`) has no such validator — any caller of the bulk endpoint can set `scan_folders` to arbitrary, unresolved, or nonexistent strings that the auto-scanner (`library_auto_scanner.py::_parse_scan_folders`) will later consume with zero validation. Checked the current frontend: `useSettingsDialog.ts`'s add/remove handlers only ever call the dedicated `addScanFolder`/`removeScanFolder` endpoints, never send `scan_folders` through the generic `updateSettings(pendingChanges)` call, so this gap is not reachable from the shipped UI today — it is a latent API-surface inconsistency, not a currently user-triggerable bug.
- **Evidence**:
  ```python
  # settings.py:200-210 — dedicated endpoint validates
  async def add_scan_folder(body: _ScanFolderRequest) -> dict[str, Any]:
      try:
          validated = validate_user_chosen_directory(body.folder.strip())
      except PathValidationError as e:
          raise HTTPException(status_code=400, detail=str(e))
  ```
  ```python
  # settings.py:63 — bulk-update field, no validator
  scan_folders: list[str] | None = None
  ```
- **Impact**: None today (unreachable from the shipped UI). If a future UI change or direct API script writes `scan_folders` via the bulk endpoint, a nonexistent/unresolved folder would be silently accepted and would scan 0 files forever with no error surfaced anywhere (the auto-scanner's `discover_audio_files` just logs a warning for a missing directory and returns empty).
- **Suggested Fix**: Add the same `field_validator` used by `LibraryScanRequest.directories` to `SettingsUpdateRequest.scan_folders` for defense-in-depth, since the two endpoints represent the same underlying concept (auto-scan folder list).

---

### INT6-05: `BAND_RANGES_HZ` documents presence/air band boundaries that don't match the actual Rust computation
- **Severity**: LOW
- **Flow**: Flow 6 (Fingerprint & Similarity)
- **Boundary**: Engine schema (`schema.py`) vs. Engine DSP (`frequency_analysis.rs`) / Frontend type comments
- **Location**: `auralis/analysis/fingerprint/schema.py:87-95` vs. `vendor/auralis-dsp/src/frequency_analysis.rs:17-18,122` and `auralis-web/frontend/src/utils/fingerprintToGradient.ts:21-22`
- **Status**: NEW
- **Description**: `schema.py`'s `BAND_RANGES_HZ` states `'presence_pct': (4000.0, 6000.0)` and `'air_pct': (6000.0, 20000.0)`. The actual Rust band-splitting code that computes these dimensions uses `freqs = [20.0, 60.0, 250.0, 500.0, 2000.0, 4000.0, 8000.0, 20000.0]` — i.e., presence is 4000-8000 Hz and air is 8000-20000 Hz, matching the frontend's own comment (`presence, // 4000-8000 Hz` / `air, // 8000-20000 Hz`). `BAND_RANGES_HZ` is unused anywhere else in the codebase (only defined and exported), so this doesn't affect a live computation, but it is wrong documentation-as-code that would mislead anyone using it for "EQ targeting" as its docstring suggests.
- **Evidence**: See locations above; `grep -rn BAND_RANGES_HZ` across `auralis/` and `auralis-web/` shows only the definition and its `__all__` export — no call sites.
- **Impact**: None currently (dead constant), but a future consumer (e.g., an EQ-targeting feature the docstring anticipates) would silently compute against the wrong 2kHz-wide slice of the presence/air split.
- **Suggested Fix**: Fix the two tuples to `(4000.0, 8000.0)` and `(8000.0, 20000.0)` to match `frequency_analysis.rs`.

---

### INT6-06: `rolloff_to_hz()` uses the wrong normalization constant (dead code, self-acknowledged in a comment)
- **Severity**: LOW
- **Flow**: Flow 6 (Fingerprint & Similarity)
- **Boundary**: Engine schema (`schema.py`) vs. Engine Rust glue (`rust_fingerprint.py`)
- **Location**: `auralis/analysis/fingerprint/schema.py:108-110` vs. `auralis/analysis/fingerprint/rust_fingerprint.py:20-23,45,98`
- **Status**: NEW
- **Description**: `rust_fingerprint.py` normalizes `spectral_rolloff` against `ROLLOFF_NORMALIZATION_HZ = 10_000.0`, but `schema.py`'s `rolloff_to_hz()` inverse helper multiplies by `CENTROID_NORMALIZATION_HZ` (8000.0) — the constant meant for `spectral_centroid`. The inconsistency is called out in a comment in `rust_fingerprint.py` ("note `schema.rolloff_to_hz` uses 8 kHz, a pre-existing inconsistency in that helper") but left unfixed. `grep` shows `rolloff_to_hz` has zero call sites anywhere in the repo, so it is currently dead code.
- **Evidence**:
  ```python
  # rust_fingerprint.py:20-23
  # ``spectral_rolloff`` raw Hz → 0-1 via ``/ ROLLOFF_NORMALIZATION_HZ`` (10 kHz — matches
  # the Python analyzer's historical convention; note ``schema.rolloff_to_hz`` uses 8 kHz,
  # a pre-existing inconsistency in that helper).
  ROLLOFF_NORMALIZATION_HZ: float = 10_000.0
  ```
  ```python
  # schema.py:108-110
  def rolloff_to_hz(rolloff_normalized: float) -> float:
      """Convert a normalized 85%-rolloff value back to Hz."""
      return float(rolloff_normalized) * CENTROID_NORMALIZATION_HZ  # 8000.0 — wrong constant
  ```
- **Impact**: None today (unused). Whoever wires up `rolloff_to_hz()` next (e.g., for a debug/inspector view) will get Hz values 20% low without any signal something is wrong.
- **Suggested Fix**: Change `rolloff_to_hz()` to multiply by `ROLLOFF_NORMALIZATION_HZ` (importing it from `rust_fingerprint.py`, or hoisting the constant into `schema.py` as the single source of truth both modules import).

---

### INT6-07: Pre-built K-NN graph silently returns fewer neighbors than requested when the graph's build-time `k` is smaller than the client's `limit`
- **Severity**: LOW
- **Flow**: Flow 6 (Fingerprint & Similarity)
- **Boundary**: Backend `similarity.py` → Engine `knn_graph.py`
- **Location**: `auralis-web/backend/routers/similarity.py:155-170` → `auralis/analysis/fingerprint/knn_graph.py:255-271`
- **Status**: NEW
- **Description**: `GET /tracks/{id}/similar?limit=N&use_graph=true` calls `graph_builder.get_neighbors(track_id, limit=limit)`, which simply caps the pre-computed edge list at `limit` — it never backfills from a real-time search when the graph was built with a smaller `k` (e.g., `POST /graph/build?k=10` then a client requests `limit=50`). The router only falls back to real-time calculation when the neighbor list is empty (`if neighbors: ... else: graph_builder = None`), not when it's merely shorter than requested.
- **Evidence**:
  ```python
  # similarity.py:156-170
  neighbors = await asyncio.to_thread(graph_builder.get_neighbors, track_id, limit=limit)
  if neighbors:
      for neighbor in neighbors:
          results.append(SimilarTrack(...))
  else:
      # Graph not built yet, fall back to real-time calculation
      graph_builder = None
  ```
  ```python
  # knn_graph.py:255-271
  def get_neighbors(self, track_id: int, limit: int | None = None) -> list[dict[str, Any]]:
      edges = self.graph_repo.get_neighbors(track_id, limit)
      return [edge.to_dict() for edge in edges]
  ```
- **Impact**: A client asking for `limit=50` "similar tracks" silently gets only however many the graph's fixed `k` provides (commonly 10, the router's own default), with nothing distinguishing "the library only has this many similar tracks" from "the graph just wasn't built wide enough." Frontend consumers (`useSimilarTracks`, `useSimilarTracksLoader`) have no way to detect or communicate this to the user.
- **Suggested Fix**: When `len(neighbors) < limit`, either top up with a real-time search for the remaining slots (excluding already-returned IDs) or surface a response field indicating the result was graph-capped.

---

### INT6-08: Four fingerprint/queue status endpoints have zero frontend consumers
- **Severity**: LOW
- **Flow**: Flow 6 (Fingerprint & Similarity)
- **Boundary**: Backend `fingerprint_status.py` / `fingerprint_queue.py` → Frontend (absent)
- **Location**: `auralis-web/backend/routers/fingerprint_status.py:36-68` and `auralis-web/backend/routers/fingerprint_queue.py:43-225`
- **Status**: NEW
- **Description**: `GET /api/library/fingerprints/status`, `GET /api/similarity/fingerprint-queue/status`, `GET /api/similarity/fingerprint-stats`, and `POST /api/similarity/fingerprint-queue/enqueue-all` are fully implemented (progress percentages, ETA estimate, queue depth, processing/failed counts) but have no caller anywhere in `auralis-web/frontend/src` — confirmed via repo-wide search for their paths and response field names (`fingerprinted_tracks`, `pending_tracks`, `progress_percent`).
- **Evidence**: `grep -rn "fingerprints/status\|fingerprint-queue\|fingerprint-stats" auralis-web/frontend/src` returns no matches outside the backend itself.
- **Impact**: Not a correctness bug — but there is no UI surface (progress bar, settings panel, "X/Y tracks analyzed" indicator) for background fingerprinting at the library level, and no manual way for a user to trigger `enqueue-all` from the app. Any future frontend work adding this needs to be built from scratch; it is not a case of a broken wire between two existing sides.
- **Suggested Fix**: If library-wide fingerprint progress is intended to be user-visible (the backend's effort in building `estimated_remaining_seconds` and status messages suggests it was meant to be), wire a settings/library page to poll `/api/library/fingerprints/status`. Otherwise, consider these endpoints candidates for removal per the project's dead-code hygiene practice.

---

### INT7-03: `useProgressiveImageLoader`'s retry cache-buster appends a second `?` to already-parameterized artwork URLs (currently latent, not exercised)
- **Severity**: LOW
- **Flow**: Flow 7 (Artwork)
- **Boundary**: Frontend hook (`useProgressiveImageLoader`) ↔ Frontend URL builder (`artworkService.getArtworkUrl`)
- **Location**: `auralis-web/frontend/src/components/shared/ui/media/useProgressiveImageLoader.ts:65` ← consumed by `auralis-web/frontend/src/components/album/AlbumArt.tsx:116-129`
- **Status**: NEW
- **Description**: On a retry, the loader rebuilds the image `src` as `` `${src}?retry=${retryCount}` `` unconditionally — it does not check whether `src` already contains a `?`. `artworkService.getArtworkUrl()` routinely returns URLs with an existing query string (`?size=64&v=3`), so a retried load for such a URL would request `.../artwork?size=64&v=3?retry=1` — a malformed query string where the second `?` is treated as a literal character in the `v` value by most HTTP clients/routers rather than starting a new parameter, meaning the `retry` cache-buster is silently absorbed into `v`'s value instead of taking effect, and repeated retries would keep hitting the exact same (now stale-cached) URL. This is not exercised today only because `AlbumArt.tsx`, the sole current caller, explicitly passes `retryOnError={false}` and `maxRetries={0}`, so `retryCount` never advances past 0 and the buggy branch is dead in production.
- **Evidence**:
  ```typescript
  // useProgressiveImageLoader.ts:64-65
  // Add cache busting for retries
  img.src = retryCount > 0 ? `${src}?retry=${retryCount}` : src;
  ```
  ```typescript
  // AlbumArt.tsx:116-129 -- the only current caller, retries disabled
  <ProgressiveImage
    src={artworkUrl}         // from getArtworkUrl(albumId, { size, revision }) -- already has ?size=&v=
    retryOnError={false}
    maxRetries={0}
    ...
  />
  ```
- **Impact**: None today. If a future caller re-enables retries for an artwork (or any already-parameterized) URL, retries would not actually cache-bust and could loop ineffectively against the same failing/stale response.
- **Suggested Fix**: Build the retry URL with a proper query-append helper (`url.includes('?') ? '&retry=' : '?retry='`), matching the pattern already used correctly in `artworkService.withArtworkSize()`.

---

**Confirmed-existing, not re-reported** (verified present in current source, already tracked): #4686 (no `ClientTimeout` on `ArtworkDownloader`'s shared `aiohttp.ClientSession` — also the root cause of any frontend-30s-timeout-vs-backend-hang mismatch during online artwork downloads), #4676 (`artwork_updated` WS payload untyped dict), #4532 (thumbnail cache has no eviction / DELETE doesn't purge derived thumbnails), #4530 (`useArtworkPalette` module cache never invalidated by `artwork_updated`), #4526 (artist-artwork CSP — verified the fix's `_ARTIST_ARTWORK_IMG_HOSTS` allowlist is intact in `config/middleware.py`), #4447/#4439/#4437/#4408/#4419/#4233/#4121/#3563/#3575/#3590 (all verified intact in current source, no regression).

---


---

# Relationships

## R1 — The enhancement control plane: one product feature, three independent breaks

INT3-01, INT3-02, INT3-04, and INT1-01 are four distinct bugs that all converge on the same user-visible outcome: *the enhancement settings the UI shows are not the settings the DSP is running.* They have different root causes and require different fixes, so they are not duplicates — but they must be triaged together, because fixing any one of them alone leaves the feature broken.

| Finding | Layer at fault | What breaks |
|---|---|---|
| INT3-02 | Frontend `usePlayTrack` | Hardcoded `adaptive`/`1.0` overwrites the user's real preset on every library-initiated play |
| INT3-01 | Frontend `usePlayTrack` + `Player.tsx` | `enabled === false` never routes to `play_normal`, so playback is rejected outright |
| INT3-04 | Backend `handle_play_enhanced` | `track_id`-only dedup swallows mid-stream preset/intensity changes and toggle-ON |
| INT1-01 | Frontend `usePlayTrack` | Fire-and-forget send + unconditional success toast hides the rejection from (3) and (2) |

INT1-01 is the *symptom amplifier* for INT3-01: even if the routing bug were fixed, `usePlayTrack`'s unconditional `success()` toast would still mask any other rejection reason (track not found, processor unavailable). It therefore stays a separate finding with a separate fix.

**Shared root cause**: there is no single "start playback for track X" helper. `usePlayTrack`, `Player.tsx`'s transport handlers, `useEnhancedPlayCommand`, and `usePlaybackControl` are four independent implementations of the same intent. #4410 fixed the preset-threading bug in exactly one of them (`Player.tsx`); the others were never touched. Per the project's **no-variants / DRY** principle, the structural fix is to collapse them into one hook that reads `enabled`/`preset`/`intensity` from `useEnhancementControl()` and picks the message type — which fixes INT3-01 and INT3-02 in one change and makes INT1-01's ack-handling a single place to add.

## R2 — "Cancel" that never crosses the boundary

INT4-01 (scan abort) and INT6-02 (fit/build_graph 30 s timeout) are the same architectural gap in two features: **the frontend can abandon a request, but the backend has no mechanism to learn it was abandoned.** No FastAPI handler anywhere in `auralis-web/backend/` polls `Request.is_disconnected()`, and no middleware cancels route tasks on disconnect. Both long-running operations (`asyncio.to_thread` for fit/graph-build, the scan future for scanning) therefore run to completion regardless. The comment in `library_scan.py` asserting the opposite is actively misleading. A single fix — either a shared disconnect-polling wrapper or an explicit submit-and-poll job pattern — addresses both.

## R3 — WebSocket state that resyncs vs. state that does not

Flow 5 confirmed that the playback control plane resyncs correctly on reconnect (`setup_connection` re-pushes `enhancement_settings_changed` + `player_state` per #2507/#2606; `replayQueueAndResume` + the `seq` watermark per #3732/#4338 handle out-of-order snapshots and backend-restart seq resets). Scan state (INT4-02) and, structurally, `job_progress` (INT5-03 / #4680) have no equivalent. The asymmetry is the finding: reconnect-safety was solved once for playback and never generalized. `replayQueueAndResume` replays *outgoing* client→server messages only — it has no concept of replaying missed *incoming* broadcasts, and there is no REST status endpoint to fall back on for scans.

## R4 — Guards that exist in one place and were never applied to siblings

A recurring shape across four findings: a correct guard exists, is well-commented, and was never propagated to the sibling code path that needs it identically.

- INT6-01: the `lufs == -100.0` placeholder + stale-version guard lives only in `FingerprintService._load_from_database()`; the five `FingerprintRepository` methods the similarity engine calls have neither.
- INT7-01: magic-byte sniffing was added to `services/artwork_downloader.py` by #4419 and never ported to `auralis/library/artwork.py::_save_artwork`, which has the identical defect.
- INT7-02: `delete_artwork()` unlinks the old file; `extract_and_save_artwork()` and `update_artwork_path()` overwrite the path without unlinking.
- INT2-01: `AlbumRepository.search()` accepts and applies a whitelisted `order_by`; `TrackRepository.search()` accepts none and applies none.
- INT4-06: `POST /api/settings/scan-folders` validates through `validate_user_chosen_directory()`; the bulk `PUT /api/settings` accepts the same field unvalidated.

This is the **sibling-detection** pattern from the audit protocol showing up as a systemic habit, not a coincidence: fixes are applied at the call site that reported the bug rather than to the class of call sites.

## R5 — Declared-but-never-produced contract fields

INT2-02 (`LibraryTrack.genre`), INT2-05 (`Artist.dateAdded`), and the confirmed-existing #4709 (album `genre`) are the same defect class: a frontend transformer maps a field the backend never emits, so the value is permanently `null`/`undefined`. In two of the three cases a passing unit test asserts the field round-trips correctly — against a hand-authored mock that includes the field the real endpoint never sends. **The tests actively create false confidence.** Any contract-sync tooling (`/sync-contracts`) should treat "transformer reads a key absent from every response model" as a first-class check.

## R6 — Dead / unreachable surfaces on both sides

INT3-03 (`'live'` preset defined in the engine, absent from `VALID_PRESETS`), INT6-08 (four fully-implemented fingerprint status endpoints with zero frontend consumers), INT2-06 (three unused pagination definitions with three different caps), INT6-05/INT6-06 (dead constants with wrong values), and the existing #4680 (`job_progress`) all describe capability that exists on exactly one side of a boundary. None is a live bug. Collectively they are the surface area where the *next* integration bug will be introduced, because each one looks wired up.

---

# Prioritized Fix Order

### Tier 1 — Fix first (silent wrong output; user cannot detect it)

1. **INT3-04** (HIGH, regression of #3763/#3759) — `play_enhanced` `track_id`-only dedup. Fix first because it is a confirmed regression with an empirical repro, and because every status surface lies about it. Cheapest correct fix: extend the guard to compare `preset`/`intensity`/stream-type, falling through to `_cancel_prior_task` on mismatch.
2. **INT3-02 + INT3-01** (HIGH ×2) — `usePlayTrack` hardcoding and the missing `enabled` check. Fix together via a single shared "start playback" helper (see R1); fixing them separately re-creates the duplication that caused them.
3. **INT6-01** (HIGH) — placeholder/stale fingerprints in the similarity path. Add the existing `FingerprintService` guard to the five repository methods, or expose one "current, complete fingerprints only" query and route the similarity engine, K-NN builder, and display endpoints through it exclusively.

### Tier 2 — Fix next (fails under realistic conditions)

4. **INT2-01** (HIGH) — add `order_by` to `TrackRepository.search()` with at minimum an `Track.id.asc()` tiebreaker, and forward the router's `order_by`. Small, self-contained, mirrors an existing correct sibling.
5. **INT4-01** (HIGH) — real scan cancellation (either `Request.is_disconnected()` polling or an explicit cancel endpoint). Also fix the misleading comment either way. Pairs naturally with INT6-02.
6. **INT4-02** (HIGH) — add `GET /api/library/scan/status` and call it from `useScanProgress` on WS reconnect, or replay the last scan-lifecycle frame the way `lastStreamCommand` is replayed.

### Tier 3 — Contract and UX correctness

7. **INT1-01** — gate `usePlayTrack`'s success toast on `audio_stream_start` (matched on `track_id`). Best done as part of the Tier 1 #2 consolidation.
8. **INT6-03** — the ~100× `_pct` rendering error in the similarity explain panel. One-line frontend fix; visible wrong number today.
9. **INT2-03** — parse and surface the backend `detail` body in `useRestAPI`. Same pattern as #4626/#4643 but in the shared client, so it fixes the whole browse flow at once.
10. **INT6-02**, **INT6-04**, **INT4-04**, **INT4-03** — long-operation timeouts, unbounded error polling, opaque scan-failure counts, double directory walk.
11. **INT7-01**, **INT7-02** — port the #4419 magic-byte sniff to the embedded extractor; unlink orphaned artwork on overwrite.
12. **INT2-02**, **INT2-04**, **INT2-05**, **INT4-05**, **INT5-01** — contract drift, playlist cap, case-insensitive filesystems, heartbeat SLA.

### Tier 4 — Opportunistic

13. All LOW findings (INT2-06, INT3-03, INT4-06, INT6-05, INT6-06, INT6-07, INT6-08, INT7-03). INT6-05 and INT6-06 are one-line constant corrections and can be swept in with any adjacent change.

### Structural recommendations (not individual findings)

- **Consolidate the four playback-start implementations** (R1). This is the highest-leverage change in the report — it closes INT3-01, INT3-02, and INT1-01 and prevents the next instance.
- **Decide on a disconnect/cancellation policy** for long-running endpoints (R2), rather than fixing scan and fit independently.
- **Add a contract check** for "transformer reads a key no response model produces" (R5), since the existing unit tests demonstrably do not catch it.

---

# Appendix A — Existing issues re-confirmed present (not re-reported)

Verified still present in current source during this audit. Not counted in the finding totals.

| Issue | Severity | Confirmed at | Note |
|---|---|---|---|
| #4541 | HIGH | `usePlaybackControl.ts`, `Player.tsx`, `playback_control.py::handle_resume` | Dual uncoordinated pause/resume control planes. Independently re-derived by both Flow 1 and Flow 5. Flow 5 additionally confirmed: spacebar "resume" sends `play_normal` with no `start_position` (restart at 0:00, enhancement dropped) into a stream type no live frontend hook consumes — `usePlayNormal` is never instantiated outside its own tests. |
| #4680 | MEDIUM | `ws_handlers/messages.py` ↔ `types/ws/registry.ts` | `job_progress` / `subscribe_job_progress` orphaned message pair; the `/api/processing/*` job infrastructure behind it has no frontend caller either. |
| #4431 | LOW | `stream_seek.py:197` vs `stream_normal.py:222` | `audio_stream_start.total_duration` still diverges between enhanced seek (full duration) and normal seek (remaining duration). |
| #3884 | LOW | `proactive_buffer.py` | `buffer_presets_for_track` still dead; `buffer_presets_fn` wired through but never invoked. |
| #4709 | LOW | `serializers.py:227-248`, `models/core.py:256-289` | Album `genre` always null. Flow 2 additionally confirmed a **second independent consumer** of the same gap: `useAlbumDetails.ts` → `AlbumHeaderActions.tsx` → `AlbumMetadata.tsx` conditionally renders "Genre: {genre}" and never does, for any album — via the *different* `/api/albums/{id}/tracks` endpoint. Root cause is identical (`Album` has no genre column), so not filed separately. |
| #4674, #4629, #4625, #4630, #4626 | — | Fingerprint/similarity paths | Re-verified still open in current source. |
| #4686, #4676, #4532, #4530 | — | Artwork paths | Re-verified still open in current source. #4686 (no `ClientTimeout` on the shared `aiohttp.ClientSession`) is also the root cause of any frontend-30 s-timeout-vs-backend-hang mismatch during online artwork downloads. |

# Appendix B — Fixes verified INTACT (no regression)

Spot-checked against current source and confirmed still fixed. Recorded because the 2026-07-25 audit found that 11 closed issues had never actually been fixed — this list is the counter-evidence for the ones checked this round.

- **Flow 3**: #4600 (intensity contract unification), #4601/#4542 (preset write-back + recommendation trigger), #4707/#4675 (processor cache-key issues, already tracked), #4610 (dead legacy `config.py`, already tracked), #4587 (settings-dialog/live-session desync, already tracked).
- **Flow 4**: #4602, #4603, #4616, #3710, #3987.
- **Flow 5**: #2507/#2606 (reconnect re-push of `enhancement_settings_changed` + `player_state`), #3732/#4338 (`seq` watermark handling out-of-order snapshots and backend-restart resets), #3509 (`active_track_ids` bookkeeping), #3492 (`queue_updated` → `queue_changed` rename). `teardown_connection` verified thorough and idempotent per-step — no leak found.
- **Flow 7**: #4526 (artist-artwork CSP allowlist `_ARTIST_ARTWORK_IMG_HOSTS` intact), #4447, #4439, #4437, #4408, #4419, #4233, #4121, #3563, #3575, #3590.

**Note on INT3-04**: the exception to this appendix. #3763/#3759 were closed by commit `0e686fe7`, which touched only `WebSocketContext.tsx`, `useEnhancementControl.ts`, and their tests. The backend guard it needed to work against (`04d5b816`, two months earlier) was never modified, and the fix's own tests mock the WebSocket context so they never assert backend behavior. Two of the three scenarios that commit named as fixed do not work in current source.

# Appendix C — Hypotheses actively disproved

Recorded so a future audit does not re-derive them. Each was investigated and could not be sustained against the source.

- **Blob-URL leak in artwork rendering** — no `URL.createObjectURL` exists anywhere in shipped artwork production code; the only occurrences are in test-local mock components.
- **Decompression-bomb / unbounded memory in thumbnail generation** — Pillow's default `MAX_IMAGE_PIXELS` guard is never disabled anywhere in the codebase, so undownsized downloaded artwork is already bounded.
- **Artwork path traversal** — `routers/artwork.py` does not use `security/path_security.py`, but has its own equivalent inline `is_relative_to()` validation against `~/.auralis/artwork`, re-derived and confirmed correct (no string-prefix bypass; checked before existence).
- **`NoCacheMiddleware` stripping artwork cache headers** — it explicitly excludes `/api` paths, so the artwork route's `ETag`/`Cache-Control` survive.
- **CORS tainting the artwork canvas read** — `cors_allowed_origins()` includes the dev Vite ports, so `colorExtraction.ts`'s `img.crossOrigin = 'Anonymous'` canvas read does not taint in dev cross-origin mode.
- **Flow 1 audio integrity** — sample-rate matching (AudioContext created at the stream's native rate), chunk boundary/overlap math, WS binary frame framing, flow-control backpressure, and seek offset math were all specifically targeted and held up. No audio-integrity finding was sustainable in the playback pipeline.
- **WS case-conversion mismatch** — none exists; both sides are snake_case with an explicit mapping layer.

---

## Next step

```
/audit-publish docs/audits/AUDIT_INTEGRATION_2026-07-29.md
```

No GitHub issues were created by this audit. No source files were modified.
