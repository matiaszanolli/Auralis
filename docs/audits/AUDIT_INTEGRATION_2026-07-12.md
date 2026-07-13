# Integration Audit — Backend ↔ Frontend ↔ Engine Data Flows

**Date**: 2026-07-12
**Scope**: The 7 critical cross-layer data flows between the Auralis audio engine (`auralis/`), the FastAPI backend (`auralis-web/backend/`), and the React frontend (`auralis-web/frontend/`).
**Depth**: deep (full data-path tracing)
**Method**: One agent per flow traced each boundary end-to-end, re-reading both sides to confirm every mismatch and attempting to disprove each finding before recording it. Findings deduplicated against 142 open/closed GitHub issues (`gh issue list`) and prior `docs/audits/` reports.

---

## Executive Summary

**Total findings: 30** — 0 CRITICAL, **3 HIGH**, **11 MEDIUM**, **16 LOW**. 27 NEW, 3 pre-existing (2× #3892, 1× #3490).

The audio-integrity core is sound. Every boundary that carries PCM audio — file-load sample rate propagation, chunk-boundary sample continuity (no dropped/duplicated samples at 15s/10s edges), binary WS frame format (native LE float32, meta+binary pairing), backpressure/flow-control, and the 25-D fingerprint dimensionality/order — was verified correct and could not be disproven. There is **no sample-count or audio-corruption defect** in this audit.

The defects cluster in three themes:

1. **Protocol / lifecycle correctness on live paths (the 3 HIGH findings).** A WebSocket heartbeat contract mismatch force-closes every socket ~60s (F5-01); infinite scroll double-counts its offset and hides ~half of any large library (F2-01); and online artwork download saves to a directory the serving endpoint refuses to read, breaking that feature end-to-end (F7-01). These are the only findings with unmistakable, present-day user impact.

2. **Status/progress and "settings that do nothing."** Two independent progress bars are meaningless — streaming buffering (F1-01) and library-scan progress (F4-01) both divide the wrong numerator by the wrong denominator. Persisted enhancement settings are never seeded into the runtime audio path (F3-01), and Next/Previous silently resets the user's preset/intensity to adaptive/1.0 (F3-02). Scan failures are counted server-side but never surfaced (F4-02), and a timed-out manual scan leaves the UI stuck "Scanning…" forever (F4-03).

3. **Latent contract mismatches behind dead/unmounted frontend surfaces.** A large share of the MEDIUM/LOW findings (F1-04, F2-06, F3-03, F6-01/02/03, F5-03, F7-02) are real backend↔frontend contract breaks — wrong `response_model`, snake_case leakage, dict-vs-array, id-field divergence — that produce no live impact today only because the consuming component or service has no mounted caller. They are correctness time-bombs: the moment anyone wires the consumer, they 500 or render `undefined`.

A recurring root cause across themes is **duplicated/divergent implementations** (a direct No-variants violation): two library-pagination hooks that disagree on `hasMore` correctness (F2-01/F2-03), two snake→camel mappers where the inline copy is incomplete (F2-02), two `scan_progress` emitters with different payload shapes (F4-04), and three coexisting pagination response shapes (#3892). The correct sibling in each pair is what makes the buggy one diagnosable.

### Most impactful boundary mismatches
| Rank | Finding | Boundary | Present-day impact |
|------|---------|----------|--------------------|
| 1 | **F5-01** (HIGH) | backend heartbeat loop → frontend (no `pong`) | Every WS torn down ~60s; playback re-buffer/interruption ~once a minute all session |
| 2 | **F7-01** (HIGH) | artwork downloader → serving endpoint | Online artwork download 100% broken; user loses retry buttons too |
| 3 | **F2-01** (HIGH) | backend pagination → `useLibraryQuery` | ~Half of any large library becomes silently un-browsable via scroll |

---

## Flow Coverage Matrix

| Flow | Boundaries traced | Verified clean | Findings |
|------|-------------------|----------------|----------|
| **1. Track Playback** | REST play → WS dispatch → load → process → chunk → binary framing → decode/playback | sample-rate propagation, chunk-boundary sample continuity, binary frame format, backpressure (3 layers) | 1 MED, 3 LOW |
| **2. Library Browsing** | hooks/services → albums/artists/playlists/tracks routers → repos → `to_dict` | backend eager-loading (no N+1), backend pagination arithmetic | 1 HIGH, 1 MED, 4 LOW |
| **3. Audio Enhancement** | sliders → services → enhancement/settings routers → runtime dict → engine config → realtime | intensity clamp [0,1] both sides, preset `Literal` validation, realtime↔offline config coherence | 2 MED, 3 LOW |
| **4. Library Scanning** | scan hooks → scan router + auto-scanner → scanner → repos → WS progress | schema field names, skip-and-continue on bad file, rescan idempotency, off-event-loop scan, path-traversal guard | 3 MED, 1 LOW |
| **5. WebSocket Lifecycle** | connect/reconnect → single `/ws` accept → dispatch → framing → decode | binary/text framing, backpressure matching, reconnect state recovery, seq monotonicity | 1 HIGH, 2 LOW |
| **6. Fingerprint & Similarity** | similarity hooks/service → similarity/fingerprint routers → engine → repos | 25-D order/dimensionality, 0-1 score contract (no inversion), missing-fp 404 fallback | 3 MED, 1 LOW |
| **7. Artwork** | image components → artwork router → extract/download services → FileResponse | (download path broken — see F7-01) | 1 HIGH, 1 MED, 2 LOW |

---

## Findings

### HIGH

#### F5-01: Client never answers server `ping` with `pong` → backend force-closes every WS ~60s
- **Severity**: HIGH
- **Flow**: WebSocket Lifecycle
- **Boundary**: backend heartbeat loop → frontend (missing `pong` response)
- **Location**: `auralis-web/backend/ws_handlers/connection.py:48` / `auralis-web/backend/websocket/websocket_protocol.py:77` → `auralis-web/frontend/src/utils/errorHandling.ts:211`, `auralis-web/frontend/src/contexts/WebSocketContext.tsx:315`
- **Status**: NEW (interacts with #3866 fix; not covered by open #3869/#3870/#3873)
- **Description**: The backend heartbeat loop sends `{"type":"ping"}` and arms `pending_pongs` via `mark_ping`. `is_stale()` returns true when a `pending_pongs` entry is older than `timeout_seconds` (10s) and is cleared ONLY by `mark_pong()`, which fires ONLY on a client `{"type":"pong"}` frame. The frontend never sends `pong` — `WebSocketManager.startHeartbeat` emits `{"type":"heartbeat"}` (routes to `mark_alive`, which updates `last_heartbeat`, a field `is_stale` never reads), and the incoming-`ping` branch replies to nobody. So the armed pong can never clear.
- **Evidence**: Timeline from connect t0: t=30s loop sends first ping and sets `pending_pongs[cid]=30`; t=60s `is_stale` → `elapsed 30 > 10` → `await websocket.close(code=1001, reason="Heartbeat timeout")` (`connection.py:53-54`). `grep 'pong'` / `type:'ping'` over `frontend/src` (excl. tests) returns nothing. The `#3866` comment in `websocket_protocol.py:55-65` documents the deliberate switch from `mark_pong` to `mark_alive` that removed the accidental keepalive previously holding these sockets open.
- **Impact**: The main app WebSocket is torn down roughly every 60s regardless of activity. During playback each close triggers auto-reconnect + re-issue of the stream command from the resume position — a re-processing/re-buffering gap and likely audible interruption about once a minute for the entire session. Recovery exists so playback isn't permanently broken, but it is periodically disrupted.
- **Suggested Fix**: Frontend (cleanest): add a handler replying to `{"type":"ping"}` with `{"type":"pong"}` — implement the pong the protocol assumes. Alternatively backend: have `mark_alive` also clear `pending_pongs`, or check `heartbeat.is_alive()` alongside `is_stale`.

#### F2-01: `useLibraryQuery.hasMore` double-counts offset, stopping infinite scroll at ~half the library
- **Severity**: HIGH
- **Flow**: Library Browsing
- **Boundary**: backend pagination contract → frontend hook
- **Location**: `auralis-web/backend/routers/tracks.py:58` / `artists.py:151` (correct `has_more`) → `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts:180` (and `:282`,`:322-334`)
- **Status**: NEW
- **Description**: The backend returns a correct `has_more`, but `useLibraryQuery` ignores it and recomputes `const hasMore = (offset + data.length) < total`. `offset` state holds the **request offset of the last fetched page** while `data` is the **cumulative** appended array, so the two are added and double-count consumed items. After *k* full pages of size *L*: `offset=(k-1)*L`, `data.length=k*L`, gate evaluates `(2k-1)*L < total` → flips false once `k ≳ total/(2L)` (~half the pages). The declared `LibraryQueryResponse.hasMore` field is never read.
- **Evidence**: Backend `tracks.py:58` `has_more = (offset + len(tracks)) < total`. Frontend `useLibraryQuery.ts:180` `const hasMore = (offset + data.length) < total;`, `:322-334` `nextOffset = offset + limit; setOffset(nextOffset); setData(prev => [...prev, ...items]);`. Consumers: `CozyArtistList.tsx:54`, `TrackList.tsx:62`. Sibling `useLibraryPagination.ts:86` does it correctly via backend `data.has_more`.
- **Impact**: Worked example (`total=200`, `limit=50`): loads 150 rows then `(100+150) < 200` = false; last 50 unreachable. For a 100k-track library at `limit=50`, scroll stalls at ~50k — roughly half the library silently un-browsable in any `useLibraryQuery`-backed view. No error surfaces.
- **Suggested Fix**: Gate on the backend flag or cumulative length only: `const hasMore = data.length < total;` (prefer reading the already-declared `LibraryQueryResponse.hasMore`). Do not add `offset` to `data.length`.
- **Related**: F2-03 (duplicate stack `useLibraryPagination` has the correct version).

#### F7-01: Downloaded artwork saved outside the directory the GET endpoint serves — online download silently non-functional
- **Severity**: HIGH
- **Flow**: Artwork
- **Boundary**: download service → serving endpoint (surfaces to frontend)
- **Location**: `auralis-web/backend/services/artwork_downloader.py:84` (+`298-319`) → `auralis-web/backend/routers/artwork.py:82,99-104`
- **Status**: NEW
- **Description**: `ArtworkDownloader` saves into `~/.auralis/artwork_cache/` and stores that path in `album.artwork_path`. The GET endpoint hard-codes the allowed directory as `~/.auralis/artwork/` and rejects anything not `is_relative_to()` it with 403 "path outside artwork directory". `artwork_cache` is a *sibling* of `artwork`, so every downloaded image fails the check. The embedded-tag extractor uses the correct `~/.auralis/artwork/`, so extract works while download does not.
- **Evidence**: Verified in Python: `Path('~/.auralis/artwork_cache/…').resolve().is_relative_to(Path('~/.auralis/artwork').resolve())` → `False`. Compounding: after a "successful" download, `serializers.py:191-194` sets `artwork_url=/api/albums/{id}/artwork`, so `AlbumGridContent.tsx:99` computes `hasArtwork=true`, hides the download/extract retry buttons, and shows only the gradient fallback with no error.
- **Impact**: Online artwork download (MusicBrainz/iTunes) fully broken end-to-end: POST returns 200, DB updated, but every subsequent GET returns 403 and no art ever renders — and the user loses the retry affordances.
- **Suggested Fix**: Point the downloader's `cache_dir` at `~/.auralis/artwork` (single served directory), or add `artwork_cache` to the allowed set and validate the resolved path is under *either*. Add a cross-layer test: download → GET returns 200 with image body.
- **Related**: F7-02 (extension bug becomes live once this is fixed).

### MEDIUM

#### F3-01: Persisted enhancement settings (default preset, intensity, auto-enhance) never affect playback
- **Severity**: MEDIUM
- **Flow**: Audio Enhancement
- **Boundary**: Settings UI (persisted DB) → runtime enhancement path
- **Location**: `auralis-web/frontend/src/components/settings/EnhancementSettingsPanel.tsx:33-81` → `auralis-web/backend/routers/settings.py:77-79` → `auralis-web/backend/config/globals.py:165-169`
- **Status**: NEW
- **Description**: The Settings > Enhancement panel persists `default_preset`, `auto_enhance`, `enhancement_intensity` into `UserSettings`, but nothing reads them back into the live audio path. The runtime `enhancement_settings` dict is hardcoded at process start to `{enabled:True, preset:"adaptive", intensity:1.0}` (`config/globals.py:165-169`, `main.py:110-114`), with no startup seed from the settings repo (grep finds zero consumers of those keys outside the settings schema/repo).
- **Evidence**: `useSettingsDialog.ts:51` routes these keys only to `settingsService.updateSettings`. Play paths use literals (`Player.tsx:107,131`, `PlayerEnhancementPanel.tsx:157` call `playEnhanced(id,'adaptive',1.0)`; `EnhancementPane.tsx:75` inits `useState(1.0)`).
- **Impact**: A user who sets default preset "warm", 60% intensity, auto-enhance on hears none of it — playback always starts adaptive/1.0/enabled. User-facing "settings that do nothing."
- **Suggested Fix**: On backend startup, seed `enhancement_settings` from `settings_repository.get_settings()`, and/or source `playEnhanced` args from persisted settings. If the runtime dict is intended as the source of truth, remove the dead panel controls.
- **Related**: F3-02 (same "preset/intensity ignored" theme), F3-04 (missing validation on `default_preset`).

#### F3-02: Player Next/Previous discards the user's current preset & intensity (resets to adaptive/1.0)
- **Severity**: MEDIUM
- **Flow**: Audio Enhancement
- **Boundary**: Player transport UI → WS `play_enhanced` → ChunkedAudioProcessor
- **Location**: `auralis-web/frontend/src/components/player/Player.tsx:107,131` (also `PlayerEnhancementPanel.tsx:157`) → `auralis-web/backend/core/chunked_processor.py:209-215`
- **Status**: NEW
- **Description**: `handleNext`/`handlePrevious` call `playEnhanced(id, 'adaptive', 1.0)` with literals instead of the current selection available via `useEnhancementControl().preset/intensity`. `ChunkedAudioProcessor` binds preset/intensity at construction, so the next track is processed adaptive/full.
- **Evidence**: `Player.tsx:107,131` pass literal `'adaptive', 1.0`. `useEnhancementControl` holds the true current values (from `/api/player/enhancement/status` + `enhancement_settings_changed`) but `Player.tsx` never reads them.
- **Impact**: User picks "warm" at 50%, hits Next → next track plays adaptive at 100%; the on-screen enhancement state diverges from the rendered audio. Lost on every manual track change.
- **Suggested Fix**: Source `preset`/`intensity` from `useEnhancementControl()` (or streaming Redux state) in Next/Previous/PlayerEnhancementPanel.

#### F4-01: Scan progress percentage is always ~100% — progress bar is meaningless
- **Severity**: MEDIUM
- **Flow**: Library Scanning
- **Boundary**: engine → backend → frontend
- **Location**: `auralis/library/scanner/scanner.py:175-197` → `auralis-web/backend/routers/library_scan.py:69-88` → `auralis-web/frontend/src/components/settings/ScanStatusCard.tsx:72,76-77`
- **Status**: NEW
- **Description**: The streaming-batch model (#2160) interleaves discovery and processing: a batch is processed as soon as `pending_batch` reaches `batch_size`, and `files_found` is incremented for exactly those files just before. So at every checkpoint `files_processed == files_found`, and `percentage = processed/total_found*100` is always ~100 with `current == total`.
- **Evidence**: `scanner.py:191-195` increments `files_found` then processes inline; report uses equal `files_processed`/`files_found`. `library_scan.py:72-74` computes the ratio; `ScanStatusCard.tsx:72,76-77` renders "N / N" and a determinate bar pinned at 100%.
- **Impact**: The determinate bar conveys no progress on large scans; only the raw climbing count is meaningful. Cosmetic/UX.
- **Suggested Fix**: Either count discovered files up front (cheap fs walk) for a true fraction, or use an indeterminate bar + `current` count during processing. Apply the same in the auto-scanner path.
- **Related**: F4-04 (the two emitters already diverge).

#### F4-02: Failed/skipped file counts are never surfaced to the user
- **Severity**: MEDIUM
- **Flow**: Library Scanning
- **Boundary**: backend → frontend
- **Location**: `auralis-web/backend/routers/library_scan.py:143-152,164-172` → `auralis-web/frontend/src/hooks/library/useLibraryScan.ts:82-85`, `useScanProgress.ts:83-89`
- **Status**: NEW
- **Description**: `BatchProcessor` counts unreadable/undecodable files as `files_failed` and continues (good), and the backend broadcasts `files_failed`/`files_skipped` in `scan_complete` and the REST `ScanResultResponse`. But no frontend consumer reads them — `ScanCompleteMessage` doesn't declare `files_failed`, `useScanProgress` reads only `files_added`+`duration`, and the toast is hardcoded to `Added ${files_added} tracks`.
- **Evidence**: `library_scan.py:148` emits `files_failed`; `types/ws/library.ts:108-115` omits it; `grep files_failed|filesFailed frontend/src` → zero non-test hits. A folder of undecodable files reports "Scan complete! Added 0 tracks" with no error.
- **Impact**: Silent partial failure; user gets a success toast and no clue why nothing was added. Errors logged server-side only.
- **Suggested Fix**: Add `files_failed`/`files_skipped` to `ScanCompleteMessage` and the toast (e.g. "Added N, M failed"); optionally a warning affordance in `ScanStatusCard`.

#### F4-03: Manual scan timeout leaves the WS-driven scan UI stuck on "Scanning…"
- **Severity**: MEDIUM
- **Flow**: Library Scanning
- **Boundary**: backend → frontend
- **Location**: `auralis-web/backend/routers/library_scan.py:52-56,108-119,174-179` → `auralis-web/frontend/src/hooks/library/useScanProgress.ts:61-95`
- **Status**: NEW
- **Description**: The manual endpoint broadcasts `library_scan_started` up front (sets `isScanning=true`). On timeout it calls `stop_scan()` and raises `HTTPException(504)` but never broadcasts a terminal `scan_complete`/`library_scan_error`. `useScanProgress` clears `isScanning` only on those terminal messages, so bound components stay in the scanning state. The auto-scanner path does emit `library_scan_error` on failure; the manual path has no equivalent for its timeout/exception exits.
- **Evidence**: `library_scan.py:110-119,174-175` raise 504 with no broadcast; only success emits a terminal WS message (`141-152`). `useScanProgress.ts:79-95` resets only on `scan_complete`/`library_scan_error`. The local flag in `useLibraryScan` self-heals via `finally`, but the WS hook does not.
- **Impact**: After a scan exceeding `AURALIS_SCAN_TIMEOUT` (default 3600s) or a generic 500, the settings scan card is stuck "Scanning…" until another scan completes or reload. Conditional → MEDIUM.
- **Suggested Fix**: Broadcast `library_scan_error` (class-name-only, matching the auto-scanner's #3543 redaction) in the manual endpoint's timeout and generic-exception branches before raising.

#### F1-01: Streaming progress counts binary sub-frames as chunks — progress bar hits ~100% during the first chunk
- **Severity**: MEDIUM
- **Flow**: Track Playback
- **Boundary**: backend WS PCM framing → frontend streaming core (progress state)
- **Location**: `auralis-web/backend/core/stream_protocol.py:190-224` → `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts:226,229`
- **Status**: NEW
- **Description**: `send_pcm_chunk` splits every processed content chunk into multiple ~300 KB binary frames (`samples_per_frame = 300*1024//4 = 76800`), each delivered as a separate `audio_chunk` message. `handleChunk` does `processedChunks++` once per message (i.e. per frame) but divides by `totalChunks` = the CONTENT chunk count from `audio_stream_start`. A 15s stereo 44.1kHz chunk ≈ 18 frames, a 10s chunk ≈ 12 frames, so the numerator advances ~12-18× too fast.
- **Evidence**: Backend loops `for frame_idx in range(num_frames)` queuing a meta+pcm pair per frame. Frontend `useAudioStreamingCore.ts:226` `processedChunks++`, `:229` `progress = processedChunks/totalChunks*100`. `frameIndex`/`frameCount` are in scope (used only for a debug log) but don't gate the increment.
- **Impact**: The buffering progress bar reaches 100% after roughly the first content chunk. Playback is unaffected (completion driven by `audio_stream_end`; `bufferedSamples` is correct) — only the visible progress is wrong.
- **Suggested Fix**: Frontend. Increment only on the last frame (`metadata.frameIndex === metadata.frameCount - 1`) or derive progress from distinct `chunk_index`.

#### F6-01: `/similarity/.../explain/...` returns unconditional 500 — Pydantic model rejects engine payload
- **Severity**: MEDIUM
- **Flow**: Fingerprint & Similarity
- **Boundary**: engine → router response model
- **Location**: `auralis/analysis/fingerprint/similarity.py:262-266` → `auralis-web/backend/routers/similarity.py:89` (`top_differences: list[dict[str, float]]`), `:305` (`SimilarityExplanation(**explanation)`)
- **Status**: NEW
- **Description**: The engine returns `top_differences` items shaped `{'dimension': <str>, 'contribution': <float>}`. The router model declares `list[dict[str, float]]`, requiring every value to be float-coercible; the string `'dimension'` value fails, raising `ValidationError` at model construction, converted to HTTP 500.
- **Evidence**: Reproduced: `ValidationError … top_differences.0.dimension … unable to parse string as a number [input_value='lufs']`. Endpoint registered at `config/routes.py:252-258`, reachable at `GET /api/similarity/tracks/{id1}/explain/{id2}`.
- **Impact**: The explain endpoint fails for every valid request. Its only consumer (`SimilarityVisualization.tsx:58`) is exported but not mounted, so no live impact today — hence MEDIUM. Any future mount or direct caller gets a hard 500.
- **Suggested Fix**: Model `top_differences` with an explicit `DimensionContribution` submodel (`dimension: str`, `contribution: float`, + optional `value1/value2/difference`) or `list[dict[str, str | float]]`. Fix F6-02's companion gaps at the same time.
- **Related**: F6-02, F6-03 (same `/explain` + `/compare` unmounted-surface cluster).

#### F6-02: explain response contract diverges from FE type (missing `all_contributions`, `value1/value2`; dict-vs-array)
- **Severity**: MEDIUM
- **Flow**: Fingerprint & Similarity
- **Boundary**: router response model → FE service type / discovery components
- **Location**: `auralis-web/backend/routers/similarity.py:83-89` → `auralis-web/frontend/src/services/similarityService.ts:47-54`, consumed at `SimilarityTopDifferences.tsx:67-70`, `SimilarityAllDimensions.tsx:52-54`
- **Status**: NEW
- **Description**: Even with F6-01 fixed, three shape mismatches remain: (1) the router model has no `all_contributions` field, so FastAPI strips it; (2) the engine emits `all_contributions` as a **dict** but the FE types it `DimensionContribution[]` and calls `.sort()` on it → `TypeError` if it ever arrived; (3) engine `top_differences` items carry only `{dimension, contribution}` but the FE renders `diff.value1`/`diff.value2` → `undefined`.
- **Evidence**: Router model fields = `{track_id1, track_id2, distance, similarity_score, top_differences}` only; engine payload (`similarity.py:257-267`) provides a dict `all_contributions` and two-key `top_differences`; FE type declares both as arrays.
- **Impact**: Latent — masked by F6-01 and the unmounted consumer. Would crash or render blanks if explain is fixed/mounted without reconciling shapes.
- **Suggested Fix**: Add `all_contributions` to the router model as a list of `DimensionContribution` (with `value1/value2/difference`), or change the FE to consume a dict.

#### F6-03: `/compare/` returns `SimilarTrack`, but FE `ComparisonResult` expects `track_id1`/`track_id2`
- **Severity**: MEDIUM
- **Flow**: Fingerprint & Similarity
- **Boundary**: router → FE service type
- **Location**: `auralis-web/backend/routers/similarity.py:221,265-273` → `auralis-web/frontend/src/services/similarityService.ts:32-37,119-124`
- **Status**: NEW
- **Description**: `GET /api/similarity/tracks/{id1}/compare/{id2}` is declared `response_model=SimilarTrack` and returns a single `track_id`. The FE `ComparisonResult` type expects `track_id1`/`track_id2`, which the backend never emits → always `undefined`.
- **Evidence**: Backend object at `similarity.py:265-273` has `track_id` only; FE interface at `similarityService.ts:32-37`. `distance`/`similarity_score` line up; only the id pair is broken.
- **Impact**: Latent — `compareTracks` has no mounted caller. Surfaces as `undefined` ids the moment any caller uses it.
- **Suggested Fix**: Give `compare_tracks` a dedicated response model echoing both ids, or change the FE type to match `SimilarTrack`.

#### F2-02: Incomplete inline snake→camel mapper in `useLibraryQuery` duplicates and diverges from canonical transformers
- **Severity**: MEDIUM
- **Flow**: Library Browsing
- **Boundary**: backend JSON (snake_case) → frontend domain model (camelCase)
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts:201-217` vs canonical `auralis-web/frontend/src/api/transformers/albumTransformer.ts:26-37`, `artistTransformer.ts:25-34`
- **Status**: NEW
- **Description**: Two parallel mappers for the same album/artist payloads. The canonical `api/transformers/*` maps every field including `artworkUrl`. The inline `extractItemsFromResponse` spreads the raw snake_case object and patches only `trackCount`/`totalDuration` (albums) or `trackCount`/`albumCount` (artists) — so results carry both `artwork_url` and no `artworkUrl`, stale snake keys leak, and `artworkUrl`/`artistId`/`dateAdded` are never produced. DRY / No-variants violation.
- **Evidence**: `useLibraryQuery.ts:202-208,211-217` have no `artworkUrl` line; canonical `albumTransformer.ts:33` / `artistTransformer.ts:29` map it. Backend does send it (`serializers.py:191-194`, `artists.py:147`).
- **Impact**: Latent — current consumers render no artwork; but any future component binding `album.artworkUrl` off `useAlbumsQuery`/`useArtistsQuery` gets `undefined`, and dual snake/camel keys are a foot-gun.
- **Suggested Fix**: Delete the inline mapper; call `transformAlbums`/`transformArtists` from `@/api/transformers` in `extractItemsFromResponse`.
- **Related**: F2-03.

#### F7-02: Downloaded images always saved with `.jpg` extension regardless of bytes — wrong Content-Type once served
- **Severity**: MEDIUM
- **Flow**: Artwork
- **Boundary**: download service → serving endpoint → browser
- **Location**: `auralis-web/backend/services/artwork_downloader.py:223,292,298-319` → `auralis-web/backend/routers/artwork.py:113-114`
- **Status**: NEW
- **Description**: `_try_musicbrainz` and `_try_itunes` both call `_save_artwork(data, id, "jpg")` with a hardcoded extension, never inspecting bytes. Cover Art Archive/iTunes can return PNG/WebP. The GET endpoint prefers extension-based detection (`mimetypes.guess_type` → `image/jpeg` for `.jpg`); magic-byte sniffing only runs when the extension is *not* an image type, so a PNG saved `.jpg` is served `image/jpeg`.
- **Evidence**: `artwork_downloader.py:223,292` pass literal `"jpg"`; `artwork.py:113-114` trusts `guess_type`. Contrast the embedded extractor (`auralis/library/artwork.py:251-260`), which picks the extension from MIME.
- **Impact**: Mislabeled Content-Type for PNG/WebP downloads. Latent behind F7-01 today; becomes live once F7-01 is fixed.
- **Suggested Fix**: Detect format from magic bytes in `_save_artwork` and choose the extension accordingly, mirroring the extractor.

### LOW

#### F5-02: Queue-history undo broadcasts `queue_updated`, a type no frontend hook subscribes to
- **Severity**: LOW
- **Flow**: WebSocket Lifecycle
- **Boundary**: backend REST handler broadcast → frontend queue hook (no subscriber)
- **Location**: `auralis-web/backend/routers/player.py:577` → `auralis-web/frontend/src/hooks/player/usePlaybackQueue.ts:208`
- **Status**: NEW
- **Description**: `queue_service` broadcasts `queue_changed` (a rename that "fixes #3492 — was `queue_updated` which the frontend never subscribed to"). The undo endpoint was missed and still emits `queue_updated`; no hook subscribes to it (`usePlaybackQueue` subscribes to `queue_changed`/`queue_shuffled`/`repeat_mode_changed`).
- **Evidence**: `grep queue_updated frontend/src` → type/guard/mock only. The undo path also broadcasts a full `player_state` whose `queue` IS applied via `usePlayerStateSync.ts:143-152`, so the normal path still updates.
- **Impact**: None normally. In the degraded undo branch (audio player unavailable) the dedicated queue broadcast is dropped, leaving the panel stale until the next event.
- **Suggested Fix**: Emit `queue_changed` in `player.py:577-580` for parity, or drop the redundant broadcast.

#### F5-03: Dead bidirectional protocol surface — `processing_settings_update`/`applied`, `ab_track_loaded`/`ready`
- **Severity**: LOW
- **Flow**: WebSocket Lifecycle
- **Boundary**: backend receive handlers + broadcasts ↔ frontend (neither sends nor handles)
- **Location**: `auralis-web/backend/ws_handlers/messages.py:43,49`; `auralis-web/backend/schemas.py:216-219`
- **Status**: NEW (enum-doc aspect overlaps open #3873)
- **Description**: The dispatch table handles inbound `processing_settings_update` (→ `processing_settings_applied`) and `ab_track_loaded` (→ `ab_track_ready`). The frontend never sends the inbound types and never subscribes to the outbound ones; all four are absent from the FE registry. Nominally MEDIUM under "handled-but-never-sent" but zero runtime impact → LOW tech-debt.
- **Evidence**: `grep` for all four over `frontend/src` (excl. tests) → no matches; backend senders exist only inside the never-triggered handlers.
- **Impact**: None (fully dead both directions). Raises protocol cognitive surface.
- **Suggested Fix**: Remove the handlers + broadcasts + unused enum members, or wire the frontend if an A/B feature is planned.

#### F2-03: Duplicate track-list fetch stacks (`useTracksQuery` vs `useLibraryPagination`) with divergent `hasMore` correctness
- **Severity**: LOW
- **Flow**: Library Browsing
- **Boundary**: frontend hook ↔ frontend hook (same `/api/library/tracks`)
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts:403-405` vs `useLibraryPagination.ts:24-182`
- **Status**: NEW
- **Description**: Two independent hooks paginate the same endpoint and disagree on the `hasMore` contract — `useLibraryPagination` reads backend `data.has_more` correctly (`:86`), `useLibraryQuery` recomputes it incorrectly (F2-01). This duplication is the root that lets F2-01 exist in only one stack.
- **Impact**: Maintenance burden; inconsistent behavior; the incorrect one truncates large libraries.
- **Suggested Fix**: Converge on one track-pagination hook (backend-`has_more` contract).
- **Related**: F2-01.

#### F2-04: `GET /api/playlists` has no pagination — response shape diverges from every other list endpoint
- **Severity**: LOW
- **Flow**: Library Browsing
- **Boundary**: backend router → frontend service
- **Location**: `auralis-web/backend/routers/playlists.py:69-86` → `auralis-web/frontend/src/services/playlistService.ts:62-71`
- **Status**: Existing: #3892
- **Description**: `get_playlists` returns `{playlists, total}` with no `offset`/`limit`/`has_more`, unlike the `{items, total, offset, limit, has_more}` shape elsewhere, and `getPlaylists()` fetches the whole set. Ad-hoc-shape case already catalogued by #3892.
- **Impact**: Unbounded fetch of all playlists + track relationships. Minor (desktop, small counts).
- **Suggested Fix**: Track under #3892; add standard pagination or document as intentionally unpaginated.

#### F2-05: `PaginatedResponse` model in `pagination.py` is dead; every list endpoint hand-rolls the dict
- **Severity**: LOW
- **Flow**: Library Browsing
- **Boundary**: backend schema (unused) vs backend routers (ad-hoc)
- **Location**: `auralis-web/backend/routers/pagination.py:20-92` vs `albums.py:79-85`, `tracks.py:59-65`, `artists.py:153-159`
- **Status**: Existing: #3892
- **Description**: `PaginatedResponse.create()` (correct `has_more`) is imported by no router; albums/tracks return raw dicts, artists a bespoke model, each re-deriving `has_more` inline. Same root cause as #3892.
- **Impact**: Consistency debt (inline copies currently correct); door open for drift.
- **Suggested Fix**: Route list endpoints through `PaginatedResponse.create()` (also overlaps #3838's `response_model` gap), or delete the model. Covered by #3892.

#### F2-06: `GET /api/albums/{id}` returns snake_case `track_count` with no camelCase transform, and is orphaned
- **Severity**: LOW
- **Flow**: Library Browsing
- **Boundary**: backend router → (no) frontend consumer
- **Location**: `auralis-web/backend/routers/albums.py:108-119,148-156`, `serializers.py:186-217`
- **Status**: NEW
- **Description**: Album-detail (`{id}`) and `{id}/tracks` return snake_case (`track_count`, `album_id`, `album_title`, `total_tracks`) with no transform, and neither has a client consumer (`config/api.ts` defines no `ALBUM(id)` endpoint). Latent camelCase mismatch on a dead surface.
- **Impact**: None currently (unconsumed).
- **Suggested Fix**: Route through a transformer if album-detail nav is planned; otherwise include in dead-endpoint cleanup.

#### F3-03: Offline processing endpoint accepts EQ/dynamics/level_matching/genre_override but silently ignores them
- **Severity**: LOW
- **Flow**: Audio Enhancement
- **Boundary**: processingService (offline) → processing_api → ProcessingEngine
- **Location**: `auralis-web/frontend/src/services/processingService.ts:21-62` → `auralis-web/backend/core/processing_engine.py:357-423`
- **Status**: Existing: #3490 (documented in-code)
- **Description**: `ProcessingSettings` carries `eq`/`dynamics`/`level_matching`/`genre_override`; `_create_processor_config` consumes only the mode and logs-and-drops the rest (HybridProcessor drives these from its own fingerprint analysis). Intentional and documented. No live UI drives this flow (`processingService` has no component consumers).
- **Impact**: Dormant; sliders would appear responsive while changing nothing if the offline UI is re-surfaced.
- **Suggested Fix**: Track under #3490; hide the controls or drop the unused fields until the engine reads them.

#### F3-04: `default_preset` in `PUT /api/settings` has no enum validation
- **Severity**: LOW
- **Flow**: Audio Enhancement
- **Boundary**: settingsService → `settings.py` SettingsUpdateRequest
- **Location**: `auralis-web/backend/routers/settings.py:77`
- **Status**: NEW
- **Description**: `enhancement_intensity` is bounded (`Field(ge=0,le=1)`) but `default_preset: str | None` accepts any string, inconsistent with the enhancement router's strict `Literal`. An invalid value would silently fall back to adaptive (`continuous_space.py:148`, `preset_profiles.py:296-297`) if consumed.
- **Impact**: Minor today (field not consumed — F3-01). Localhost, no untrusted input.
- **Suggested Fix**: Constrain `default_preset` to the shared `EnhancementPreset` Literal so invalid values 422 at the boundary.

#### F3-05: Mid-playback preset/intensity change tears down and reissues the stream (re-buffer gap)
- **Severity**: LOW
- **Flow**: Audio Enhancement
- **Boundary**: `useEnhancementControl` setters → `reissueActiveStreamAs` → stream restart
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancementControl.ts:296-372`
- **Status**: NEW (design-acknowledged)
- **Description**: `ChunkedAudioProcessor` binds preset/intensity at construction, so setters reissue the stream from the resume position. Unlike the enable-toggle path (which pre-warms via `_preprocess_upcoming_chunks`), the preset/intensity setters don't warm the new cache key, so chunks are processed on demand; each intensity step is a distinct cache key (thrash on rapid drags).
- **Impact**: Brief audible re-buffer gap on preset/intensity change mid-playback; cache thrash on slider drags.
- **Suggested Fix**: Debounce the intensity setter and launch the same pre-warm the enable-toggle path uses.

#### F4-04: Auto-scanner `scan_progress` diverges from the manual emitter (no `phase`, never null percentage)
- **Severity**: LOW
- **Flow**: Library Scanning
- **Boundary**: backend auto-scanner → frontend
- **Location**: `auralis-web/backend/services/library_auto_scanner.py:210-226` vs `auralis-web/backend/routers/library_scan.py:69-88`
- **Status**: NEW
- **Description**: The two `scan_progress` emitters are inconsistent: the manual path sets `phase` and sends `percentage=None` during discovery; the auto-scanner omits `phase` and always sends a numeric percentage (0 during discovery). The FE falls back to `phase ?? 'processing'`, so auto-scans always label "processing" and show a determinate 0% bar during discovery. Also folds `directory` into `current_file` differently.
- **Impact**: Minor UI inconsistency between auto and manual scans; DRY/no-variants smell.
- **Suggested Fix**: Extract one shared `scan_progress`-payload builder used by both emitters.
- **Related**: F4-01.

#### F6-04: `/tracks/{id}/fingerprint` emits `loudness_variation_std`; FE type expects `loudness_variation`
- **Severity**: LOW
- **Flow**: Fingerprint & Similarity
- **Boundary**: router → FE `AudioFingerprint` type
- **Location**: `auralis-web/backend/routers/fingerprint_status.py:152` → `auralis-web/frontend/src/utils/fingerprintToGradient.ts:51`
- **Status**: NEW
- **Description**: Payload key `loudness_variation_std` vs FE optional field `loudness_variation` → always `undefined`. All other 24 keys reconcile.
- **Impact**: Cosmetic; field marked "not used for gradients", optional.
- **Suggested Fix**: Rename the FE field to `loudness_variation_std` (or alias the backend key).

#### F1-02: `audio_stream_start.total_duration` diverges between enhanced and normal seek paths (and is otherwise unused)
- **Severity**: LOW
- **Flow**: Track Playback
- **Boundary**: backend stream-start message → frontend `handleStreamStart`
- **Location**: `auralis-web/backend/core/stream_seek.py:164` (enhanced) / `stream_normal.py:194` (normal) → `usePlayEnhanced.ts:236`, `usePlayNormal.ts:162`
- **Status**: NEW
- **Description**: On seek/resume the enhanced path sends full `processor.duration` while the normal path sends a reduced `duration - (start_chunk * chunk_duration)`. The FE consumes the field only inside a `DEBUG && console.log`; it's never stored or used for the scrubber.
- **Impact**: None functional today. Latent: enhanced vs normal would disagree if a future change trusts it as the seekbar max.
- **Suggested Fix**: Make both paths send the same semantics (prefer full duration), or drop the reduced computation.

#### F1-03: No frontend timeout while waiting for `audio_stream_start` after a play command
- **Severity**: LOW
- **Flow**: Track Playback
- **Boundary**: frontend play command → backend stream start (timeout asymmetry)
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:459-476` vs `auralis-web/backend/core/stream_enhanced.py:104-120`
- **Status**: NEW
- **Description**: After dispatching `buffering` and sending `play_enhanced`, there is no client-side watchdog for the first `audio_stream_start`/`audio_chunk`. The backend bounds its own work and emits `audio_stream_error` on failure (handled), but a hung worker before any error leaves the UI in `buffering` indefinitely; the duplicate-play guard suppresses a naive retry.
- **Impact**: Rare stuck-`buffering` UI with no error surfaced. Low given desktop reliability + backend timeouts.
- **Suggested Fix**: Add a bounded watchdog armed on send, cleared on first stream message; on expiry dispatch `setStreamingError`.

#### F1-04: `wav_streaming.py` REST/MSE chunk surface is not used by the production playback flow
- **Severity**: LOW
- **Flow**: Track Playback (adjacent surface)
- **Boundary**: backend REST streaming router → frontend (no production consumer)
- **Location**: `auralis-web/backend/routers/wav_streaming.py:246,338` → referenced only in `auralis-web/frontend/src/test/mocks/handlers.ts`
- **Status**: NEW
- **Description**: Live playback is entirely WebSocket-based; the REST/MSE chunk endpoints (`/api/stream/{track_id}/…`) are referenced only by MSW test mocks, not any production service/hook — consistent with the project note that the app doesn't use MSE. Parallel dead cross-layer surface.
- **Impact**: No runtime impact; maintenance/attack-surface cost of a live-but-unused router.
- **Suggested Fix**: Confirm intent; if unused, retire it (aligns with the No-variants streamlining effort); if supported, document it.

#### F7-03: `MediaCardArtwork` `<img>` has no `onError` fallback — failed loads show a broken-image icon (track cards)
- **Severity**: LOW
- **Flow**: Artwork
- **Boundary**: serving endpoint → frontend render
- **Location**: `auralis-web/frontend/src/components/shared/MediaCard/MediaCardArtwork.tsx:98-113`
- **Status**: NEW
- **Description**: `<Box component="img" src={artworkUrl}>` has no `onError`; the gradient placeholder is used only when `artworkUrl` is falsy. If the URL is set but the request fails (403 per F7-01, 404, 5xx), the browser shows a broken-image glyph. `TrackCard` passes through this path. The album path (`AlbumCard`/`AlbumArt` via `ProgressiveImage`) already handles `onError`.
- **Impact**: Cosmetic broken-image icon on track cards.
- **Suggested Fix**: Add an `onError` that falls back to `getPlaceholderGradient(...)`, or route track artwork through `ProgressiveImage`.

#### F7-04: No dimension bound on served artwork — arbitrarily large embedded/folder images streamed to the client
- **Severity**: LOW
- **Flow**: Artwork
- **Boundary**: serving endpoint → frontend render
- **Location**: `auralis-web/backend/routers/artwork.py:152-159`; extractor `auralis/library/artwork.py` (no resize)
- **Status**: NEW
- **Description**: The GET endpoint streams artwork as-is via `FileResponse` with no resizing. Online downloads are byte-capped at 5 MB, but embedded-tag/folder extraction applies no size or pixel limit, so a large embedded cover is served at full resolution. Server memory is bounded (streams from disk); cost is client-side bandwidth/decode for oversized thumbnails.
- **Impact**: Oversized images decoded for small card thumbnails; minor client CPU/bandwidth. Localhost.
- **Suggested Fix**: Optional — generate a bounded thumbnail (≤512px) at extract time for grid views, or cap extracted-artwork byte size.

---

## Relationships & Shared Root Causes

- **Duplicated/divergent implementations (No-variants violations).** F2-01/F2-03 (two library-pagination hooks; only one gets `hasMore` right), F2-02 (two snake→camel mappers; inline copy incomplete), F4-04 (two `scan_progress` emitters with different payload shapes), F2-04/F2-05 (#3892 — three coexisting pagination shapes + an unused canonical model). In each pair the correct sibling is what makes the buggy one diagnosable. Converging each pair onto its correct implementation eliminates the bug and prevents future drift.

- **Progress computed against the wrong denominator.** F1-01 (streaming: sub-frames ÷ content-chunks) and F4-01 (scan: processed ÷ found, always equal). Both surface as bars pinned near 100%. Independent code but identical failure signature — worth fixing together for a consistent "progress means something" pass.

- **Persisted-but-not-applied enhancement state.** F3-01 (settings dict never seeded from DB) and F3-02 (Next/Previous hardcodes adaptive/1.0). Both make the enhancement UI diverge from rendered audio; F3-04 (missing `default_preset` validation) is defense-in-depth on the same surface.

- **Latent contract breaks behind unmounted consumers.** F6-01/02/03 (`/explain`, `/compare` discovery components not mounted), F2-02/F2-06 (album/artist detail transforms with no live binder), F3-03 (`processingService` unused), F1-04 and F5-03 (dead REST/WS surfaces), F7-02 (masked behind F7-01). These are correctness time-bombs, not present-day bugs — but they also inflate the API/protocol surface and mask real mismatches. A dead-surface cleanup pass would retire many at once.

- **Terminal-state / lifecycle gaps.** F5-01 (heartbeat never resolves → forced close), F4-03 (manual scan timeout emits no terminal WS message → stuck UI), F1-03 (no client watchdog for stream start). All are "the happy path resolves but a failure path leaves a peer hung."

- **WS protocol rename stragglers.** F5-02 (`queue_updated` missed by the #3492 rename to `queue_changed`) — a symptom of manual, per-call-site event naming rather than a single broadcast helper.

---

## Prioritized Fix Order

1. **F5-01 (HIGH)** — WS force-closed every ~60s, disrupting playback all session. Highest present-day impact; small, well-scoped fix (send `pong` on `ping`). Fix first.
2. **F7-01 (HIGH)** — online artwork download 100% broken and hides its own retry path. One-line directory fix + a cross-layer test. Bundle F7-02 (extension/MIME) since it goes live the moment F7-01 is fixed.
3. **F2-01 (HIGH)** — ~half of large libraries silently un-browsable. Fix the `hasMore` computation; then converge F2-03's duplicate stack so it can't regress.
4. **F3-01 + F3-02 (MEDIUM)** — user-facing "enhancement settings that do nothing" / preset reset on skip. High perceived-quality payoff; add F3-04 validation in the same change.
5. **F4-02 + F4-03 (MEDIUM)** — silent scan failures and stuck "Scanning…" UI. Surface `files_failed` and emit a terminal WS error on the manual timeout path.
6. **Progress-bar pass — F4-01 + F1-01 (MEDIUM)** — make both progress bars meaningful; low risk, visible polish.
7. **Similarity contract cluster — F6-01/02/03 (MEDIUM)** — fix the `/explain` and `/compare` response models together (they share the discovery-surface consumer). Latent today; do before those components are mounted.
8. **LOW cleanup pass** — dead-surface retirement (F1-04, F2-06, F5-03), duplicate-mapper/hook convergence (F2-02, F2-03, F4-04), pagination consolidation (#3892: F2-04/F2-05), and cosmetic hardening (F6-04, F7-03, F7-04, F1-02, F1-03, F3-05, F5-02).

---

## Verified-Clean Boundaries (no findings)

- **Audio integrity**: sample-rate propagation file→AudioContext (no implicit resample/pitch shift); chunk-boundary sample continuity (no dropped/duplicated samples at 15s/10s edges; server crossfade a deliberate no-op with `crossfade_samples=0`); binary WS frame format (native LE float32, meta+binary pairing, matching `sample_count`); three-layer backpressure (send-queue cap 4, `buffer_full`/`buffer_ready` at 75%/50%, drop-on-full within 100 MB).
- **Library**: backend eager-loading via `selectinload`/`joinedload` for exactly the relationships routers traverse (no N+1); backend pagination arithmetic correct and consistent.
- **Enhancement**: intensity clamped [0,1] on both sides; preset strict-`Literal` validated; realtime↔offline config coherent (`ProcessorFactory` → `UnifiedConfig.mastering_profile` → `continuous_mode`).
- **Scanning**: WS field-name schemas match; per-file decode errors skip-and-continue; rescan idempotent (`skip_existing` + `filepath unique=True`); scan runs off the event loop (`to_thread`); path-traversal validation present.
- **WebSocket**: binary/text framing safe (`binaryType='arraybuffer'`); backpressure fully matched; reconnect state recovery (re-push `enhancement_settings_changed`+`player_state`, re-issue last play command); `seq` monotonic per stream.
- **Fingerprint**: 25-D dimensionality/order consistent across schema/distance/normalizer/model (`len==25` assert); 0-1 similarity-score contract with no inversion; missing-fingerprint 404 fallback + background enqueue.
