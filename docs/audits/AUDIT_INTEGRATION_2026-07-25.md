# Integration Audit — Backend / Frontend / Engine Boundaries

**Date**: 2026-07-25
**Scope**: All 7 critical data flows across the audio engine (`auralis/`), the FastAPI backend (`auralis-web/backend/`), and the React frontend (`auralis-web/frontend/`)
**Depth**: deep (full data-path tracing)
**Baseline**: 159 open GitHub issues (fetched at audit start), plus prior reports in `docs/audits/` and local snapshots in `.claude/issues/`
**Method**: Fresh read of current source only. Prior reports were consulted *for deduplication only* — no finding in this report is carried over from an earlier audit.

---

## Executive Summary

**33 findings: 0 CRITICAL · 5 HIGH · 17 MEDIUM · 11 LOW.**

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 5 |
| MEDIUM | 17 |
| LOW | 11 |
| **Total** | **33** |

No CRITICAL findings. Audio-sample integrity across the engine→backend→frontend boundary held up under tracing: sample rate and channel count propagate correctly from file metadata into the `AudioContext`, chunk geometry is non-overlapping by design, the binary PCM wire format agrees on both sides, and the streaming backpressure loop is genuinely connected end-to-end. The chunk-boundary crossfade, the flow-control events, and the `seq` monotonicity guard were each traced and found correct.

The damage is elsewhere, and it has one dominant shape: **features that are fully wired on each side individually but not actually connected to each other.** Three of the five HIGH findings are complete features that cannot work at all in the shipped app — not intermittently, but 100% of the time — because the two halves were built against different control planes. This is a class of bug that unit tests and type checks cannot catch, because each side is internally consistent and correctly typed.

**Most impactful boundary mismatches:**

1. **Two uncoordinated playback control planes** (INT-F1-1). The global keyboard shortcuts drive a legacy REST/`play_normal` plane while the actual player drives a WS `play_enhanced` plane. Pressing the spacebar during playback cancels the user's own audio stream server-side and replaces it with one nobody is listening to — silently, with no error surfaced.
2. **The mastering-recommendation feature is inert** (INT-F3-2). Its only trigger is `POST /api/player/load`, an endpoint the frontend never calls. The panel shows a spinner for exactly 10 seconds and then times out, on every track, in every session.
3. **A duplicated globals dictionary silently disables a DSP fast path** (INT-F3-3). `main.py` and `config/globals.py` each build their own globals dict; startup populates one, `ChunkedAudioProcessor` reads the other. Tier-1 database fingerprint lookup returns `None` on every chunk of every enhanced playback, and the failure is indistinguishable from the intended "not initialised yet" case, so nothing logs.
4. **Two library-browsing endpoints scale with library size** (INT-F2-4, INT-F2-5). `GET /api/artists` eager-loads two relation trees it never reads; `GET /api/playlists` has no pagination mechanism at all.
5. **The snake_case→camelCase boundary transform is applied to albums and artists but not tracks** (INT-F2-1, INT-F2-2), even though `transformTracks` already exists — with zero production callers.

**Key themes** (detailed in [Relationships](#relationships)): duplicated parallel implementations that miss each other's fixes; a half-applied case-conversion convention; wire fields declared on one side and consumed by neither; error detail and terminal state lost at the boundary; runtime state seeded once at startup and never re-synced.

---

## Flow Coverage Matrix

| # | Flow | Schema match | Error handling | Timeouts | Data types | Null handling | Case conversion | Findings |
|---|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | Track Playback | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ | 2 |
| 2 | Library Browsing | ❌ | ⚠️ | ✅ | ✅ | ✅ | ❌ | 6 |
| 3 | Audio Enhancement | ⚠️ | ⚠️ | ✅ | ⚠️ | ✅ | ✅ | 6 |
| 4 | Library Scanning | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | 5 |
| 5 | WebSocket Lifecycle | ⚠️ | ⚠️ | ✅ | ✅ | ✅ | ✅ | 4 |
| 6 | Fingerprint & Similarity | ⚠️ | ❌ | ✅ | ✅ | ⚠️ | ⚠️ | 5 |
| 7 | Artwork | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | 5 |

✅ verified consistent · ⚠️ gap found (MEDIUM/LOW) · ❌ significant mismatch (HIGH, or multiple MEDIUM)

**Notable verifications that passed** (hypotheses tested and disproved — recorded so they are not re-investigated):

- **Flow 1** — chunk-overlap math is non-overlapping by design (crossfade is an intentional post-#3514 no-op); client stream watchdog (45 s) safely exceeds backend chunk timeout (30 s + 5 s semaphore); `AudioContext` is created at the file's real sample rate.
- **Flow 3** — the #4409/#4410 fixes are present and holding (`playEnhanced` requires explicit preset/intensity); the WS `play_enhanced` handler independently validates preset and clamps intensity; UnifiedConfig and legacy `auralis/core/config.py` have no overlapping preset/intensity field to diverge on; preset names are identical across all 5 frontend copies, the backend literal, and the engine profiles.
- **Flow 4** — `try_acquire_scan_slot()` is a genuine global guard, so the 409 path really fires; `scan_time`→`duration` REST/WS key divergence is already reconciled.
- **Flow 5** — the backpressure `flow_events` dict is shared by reference (not a divergent copy); stale `pendingMeta` cannot mis-pair across a reconnect; all three WS findings from `docs/audits/AUDIT_INTEGRATION_2026-07-12.md` are confirmed fixed (#4406, #4420, #4421).
- **Flow 6** — similarity scores are clipped to `[0,1]` so the Pydantic `ge/le` constraint cannot 500; graph and real-time paths share one score formula; `SimilarityGraph.to_dict()` emits both `track_id` and `similar_track_id`, so the router's indexing is correct (only its docstring is wrong).
- **Flow 7** — `Cache-Control: no-cache` + stat-derived ETag means components that omit the artwork revision still get fresh images; artwork requests are not rate-limited; `extractArtworkColors` is not canvas-tainted (same-origin + `crossOrigin`).

---

## Findings

### HIGH

---

### INT-F1-1: Global playback controls drive a legacy control plane fully disconnected from the live streaming session

- **Severity**: HIGH
- **Flow**: 1 — Track Playback
- **Boundary**: Frontend (global controls) → Backend (WS/REST) → Frontend (main Player)
- **Location**: `auralis-web/frontend/src/ComfortableApp.tsx:59-72` → `auralis-web/frontend/src/hooks/player/usePlaybackControl.ts:136-256` → `auralis-web/backend/ws_handlers/playback_commands.py:143-190` → `auralis-web/frontend/src/components/player/Player.tsx:56-93`
- **Status**: NEW
- **Description**: There are two entirely separate, uncoordinated ways to control playback, and the one wired to global keyboard shortcuts operates on state and commands the live streaming engine never produces or listens for.

  **Play/Pause (Space)** — `ComfortableApp`'s `togglePlayPause` branches on Redux `state.player.isPlaying`. That flag is written *only* by the legacy `PlaybackService`/`PlayerStateManager` REST plane. The actual Flow-1 playback path (`Player.tsx` → `usePlayEnhanced()` → `play_enhanced` → `stream_enhanced_audio`) never touches `PlayerStateManager` and never dispatches `setIsPlaying`; `Player.tsx`'s own pause button only sets a *local* `isPaused` ref. So `isPlaying` stays `false` for the entire lifetime of a normal play session, and the first Space press calls `playback.play()`, which sends **`play_normal`** — not `play_enhanced`.

  Backend `handle_play_normal` calls `_cancel_prior_task`, killing the in-flight `stream_enhanced_audio` task, and starts `stream_normal_audio` tagged `"stream_type": "normal"`. Nothing mounted has a live `usePlayNormal()` subscriber — the only consumers (`PlayerEnhancementPanel.tsx`, `EnhancementPane.tsx`) are unreferenced by any rendered parent, confirmed both by grep and by `ComfortableApp.tsx`'s own comment ("AlbumCharacterPane replaces EnhancementPane globally"). `Player.tsx`'s enhanced instance explicitly drops any message where `stream_type !== 'enhanced'`.

  **Siblings** — Next/Previous (Arrow keys) POST to `/api/player/next`/`previous`, which only advance the queue index and broadcast `track_changed`; they never send `play_enhanced`/`play_normal`, unlike `Player.tsx`'s own Next/Previous buttons which explicitly call `stopPlayback()` + `playEnhanced(...)`. Volume/Mute (`ArrowUp`/`ArrowDown`/`m`) only POST `/api/player/volume`, never touching the live `AudioPlaybackEngine.setVolume()` gain node.
- **Evidence**:
  ```ts
  // ComfortableApp.tsx:59-72 — reads a flag the play_enhanced path never sets
  const isPlaying = useSelector(selectIsPlaying);
  const togglePlayPause = useCallback(async () => {
    if (isPlaying) { await playback.pause(); } else { await playback.play(); }
  }, [isPlaying, playback]);
  ```
  ```ts
  // usePlaybackControl.ts:136-152 — "resume" actually sends play_normal
  send({ type: 'play_normal', data: { track_id: trackId } });
  ```
  ```ts
  // useAudioStreamingCore.ts:211-214 — the enhanced hook drops anything not tagged 'enhanced'
  if (message.data.stream_type && message.data.stream_type !== streamType) return;
  ```
  ```py
  # playback_commands.py:158-190 — play_normal unconditionally cancels the running task
  await _cancel_prior_task(ws_id, state)
  task = asyncio.create_task(deps.stream_normal(...))
  ```
- **Impact**: Any user who plays a track from the library (the only reachable playback entry point) and then presses the spacebar — the most natural playback shortcut, and one documented in `KeyboardShortcutsHelp` — kills their own audio within seconds, with no error message. Because the enhanced task is *cancelled* rather than *errored*, no `audio_stream_error` is emitted: the UI shows no error state, buffered audio drains, and playback simply stops dead. Arrow keys silently desync the "now playing" display from the actual audio; volume shortcuts are non-functional. All four are registered via `useKeyboardShortcuts`, unconditionally mounted in `ComfortableApp` — this is live in the shipped app, not a dead path.
- **Suggested Fix**: `usePlaybackControl` (and anything driving global shortcuts) must operate against the *same* streaming session as `Player.tsx`. Either (a) route the shortcut handlers through the shared `usePlayEnhanced` instance's `pausePlayback`/`resumePlayback`/`seekTo`/`setVolume` and queue-aware next/previous — e.g. lift `Player.tsx`'s handlers into a context — or (b) make `Player.tsx` dispatch `setIsPlaying`/queue-index changes into Redux on every transition so the legacy plane stays authoritative and `play()` resumes via `play_enhanced` with the correct preset/intensity. Either way, `usePlaybackControl.play()` must never be the mechanism used to resume an enhanced session.

---

### INT-F2-4: `GET /api/artists` eager-loads relations it never uses, scaling with tracks-per-artist on every page

- **Severity**: HIGH
- **Flow**: 2 — Library Browsing
- **Boundary**: Engine → Backend
- **Location**: `auralis/library/repositories/artist_repository.py:102-117` → `auralis-web/backend/routers/artists.py:127-149`
- **Status**: NEW
- **Description**: `ArtistRepository.get_all()` — called on every `GET /api/artists?limit=50&offset=…` page load — eager-loads, for the 50 artists on the page: `Artist.tracks` + `Track.genres` (used), `Artist.tracks` + `Track.album` (loaded, never read), and `Artist.albums` + `Album.tracks` (loaded, never read — only `len(artist.albums)` is used). The router's serialization loop only computes counts and a genre-name set; it never touches `track.album` or `album.tracks`.
- **Evidence**:
  ```python
  # artist_repository.py:105-117 (get_all)
  artists = session.execute(
      select(Artist).options(
          selectinload(Artist.tracks).selectinload(Track.genres),
          selectinload(Artist.tracks).selectinload(Track.album),   # never read below
          selectinload(Artist.albums).selectinload(Album.tracks)   # never read below
      ).order_by(order_column).limit(limit).offset(offset)
  ).scalars().all()
  ```
  ```python
  # artists.py:129-149 — only .genres and len() are consumed
  for artist in artists:
      genres = set()
      for track in artist.tracks:
          if hasattr(track, 'genres') and track.genres:
              for genre in track.genres:
                  genres.add(genre.name)
      artist_responses.append(ArtistResponse(
          ..., album_count=len(artist.albums) if artist.albums else 0,
          track_count=len(artist.tracks) if artist.tracks else 0, ...))
  ```
- **Impact**: For prolific artists (podcasts-as-artists, classical composers, or any artist with hundreds/thousands of tracks), every `/api/artists` page load pulls the full `Track` + `Album` row set for all 50 artists on the page *twice over* — once via `Artist.tracks→Track.album`, once via `Artist.albums→Album.tracks` — purely to discard it after computing a count. Response latency for artist browsing grows with total tracks-per-artist-on-page, not with the page size.
- **Suggested Fix**: Drop the two unused `selectinload` chains from `get_all()`/`search()` so the eager-load matches what is actually consumed, and compute `track_count`/`album_count` via SQL `COUNT` — the same correlated-subquery pattern already used a few lines above for `order_by='track_count'`/`'album_count'` — instead of loading full rows just to call `len()`.

---

### INT-F2-5: `GET /api/playlists` has no pagination at all — unbounded fetch of every playlist and every one of its tracks

- **Severity**: HIGH
- **Flow**: 2 — Library Browsing
- **Boundary**: Engine → Backend → Frontend
- **Location**: `auralis/library/repositories/playlist_repository.py:142-160` → `auralis-web/backend/routers/playlists.py:71-88` → `auralis-web/frontend/src/services/playlistService.ts:62-71`
- **Status**: NEW (distinct from #3892, which is a LOW finding about pagination response-*shape* naming; this is the absence of any pagination mechanism)
- **Description**: Unlike `/api/albums`, `/api/artists`, and `/api/library/tracks` (all `limit`/`offset`-bounded and capped at 200), `PlaylistRepository.get_all()` takes no pagination arguments and unconditionally `selectinload`s every playlist's full `tracks` collection. The router calls it with no limit and returns `total: len(playlists)` — i.e. always the entire playlist table, tracks included.
- **Evidence**:
  ```python
  # playlist_repository.py:142-150
  def get_all(self) -> list[Playlist]:
      playlists = session.execute(
          select(Playlist).options(selectinload(Playlist.tracks)).order_by(Playlist.name)
      ).scalars().all()
  ```
  ```python
  # playlists.py:83-88
  playlists = await asyncio.to_thread(repos.playlists.get_all)
  return {"playlists": serialize_playlists(playlists), "total": len(playlists)}
  ```
  `serialize_playlist` → `Playlist.to_dict()` additionally computes `track_count=len(self.tracks)` and `total_duration=sum(track.duration for track in self.tracks)` per playlist, so every playlist's full track set is also walked in Python on every list call.
- **Impact**: A library with many playlists turns "list playlists" — issued whenever the Playlists view is opened — into an unbounded read of the entire playlist↔track association table, with cost scaling in both playlist count and tracks-per-playlist. There is no server-side or client-side bound; `getPlaylists()` never sends `limit`/`offset` because the endpoint does not accept them.
- **Suggested Fix**: Add `limit`/`offset` query params matching the `PaginationParams` convention used elsewhere, thread them into `PlaylistRepository.get_all()`, and compute `track_count`/`total_duration` via SQL aggregates instead of loading full `tracks` collections for a list view.

---

### INT-F3-2: Mastering-recommendation feature is fully dead — its only trigger point is never called by the frontend

- **Severity**: HIGH
- **Flow**: 3 — Audio Enhancement
- **Boundary**: Backend (WS broadcast trigger) → Frontend (WS subscriber) — trigger endpoint itself is orphaned
- **Location**: `auralis-web/frontend/src/config/api.ts:76` → `auralis-web/backend/routers/player.py:389-396` → `auralis-web/backend/services/recommendation_service.py:98-106` → `auralis-web/frontend/src/hooks/enhancement/useMasteringRecommendation.ts:25,79-82`
- **Status**: NEW
- **Description**: `RecommendationService.generate_and_broadcast_recommendation` (which computes and broadcasts `mastering_recommendation`) is only ever scheduled as a `BackgroundTask` from inside `POST /api/player/load`. The frontend's real playback path is the WebSocket `play_enhanced`/`play_normal` messages, routed through `useEnhancedPlayCommand`/`usePlayNormal` — neither calls `/api/player/load`. Grepping the entire frontend `src/` tree, the `PLAYER_LOAD` constant has exactly one occurrence: its own definition. The companion REST endpoint `GET /api/player/mastering/recommendation/{track_id}` is likewise never called from the frontend. `useMasteringRecommendation()` has no REST fallback — it only subscribes to the WS message and flips `isTimedOut` after 10 s.
- **Evidence**:
  ```python
  # routers/player.py:389-396 (inside POST /api/player/load) — the only trigger site
  background_tasks.add_task(
      service.generate_and_broadcast_recommendation,
      track_id=track.id, track_path=track.filepath)
  ```
  ```typescript
  // config/api.ts:76 — only occurrence of PLAYER_LOAD in the entire src/ tree
  PLAYER_LOAD: '/api/player/load',
  ```
  ```typescript
  // useMasteringRecommendation.ts:25,79-82 — no fallback, only a WS subscription + timeout
  const RECOMMENDATION_TIMEOUT_MS = 10_000;
  timeoutRef.current = setTimeout(() => { setIsLoading(false); setIsTimedOut(true); }, RECOMMENDATION_TIMEOUT_MS);
  ```
- **Impact**: The mastering-recommendation panel (`Expanded.tsx`) never receives real data: every mount shows a loading state for exactly 10 seconds, then flips to timed-out/empty, for every track, every session — 100% of the time, not intermittently. A fully broken cross-boundary feature, not a partial degradation.
- **Suggested Fix**: Either (a) call `generate_and_broadcast_recommendation` from the actual track-load path (`handle_play_enhanced`/`handle_play_normal`, as a `spawn_background_task`, matching the pattern already used for `_preprocess_upcoming_chunks`), or (b) have `useMasteringRecommendation` fall back to the REST endpoint on timeout/mount. Given #4425's "no untargeted rebuild" constraint, (a) is the smaller fix.

---

### INT-F3-3: Two separate `globals_dict` objects — `ChunkedAudioProcessor`'s Tier-1 DB fingerprint lookup reads the one startup never populates

- **Severity**: HIGH
- **Flow**: 3 — Audio Enhancement (also affects Flows 1 and 6)
- **Boundary**: Backend (app wiring / startup) → Engine (chunked processor fingerprint tier)
- **Location**: `auralis-web/backend/main.py:97-115` and `auralis-web/backend/config/globals.py:155,191` → `auralis-web/backend/core/chunked_processor.py:71-88`; populated-instead-at `auralis-web/backend/config/startup.py:169,217-218`
- **Status**: NEW
- **Description**: The backend has **two** independently-constructed globals dictionaries with overlapping keys. `main.py:97-115` builds one as a plain dict literal and passes it as `deps['globals']`; `startup.py:169` (`globals_dict = deps.get('globals', {})`) resolves to this object, so every runtime component — `library_manager`, `repository_factory`, `settings_repository`, `enhancement_settings` — is written here. Separately, `config/globals.py:191` calls `create_globals_dict()` at import time, producing a second dict with the same key set (including its own duplicated `enhancement_settings` literal). A repo-wide grep shows `create_globals_dict` is called exactly once and **nothing ever assigns into the resulting dict** — the only `globals_dict[...] =` writes in the whole backend live in `config/startup.py`, operating on main.py's object.

  `chunked_processor._default_get_fingerprints_repository()` is the sole consumer of `config.globals.globals_dict`. It reads `globals_dict.get("repository_factory")` and, per its own docstring, returns `None` to "silently skip" Tier-1 "when globals aren't initialised yet — e.g. in unit tests". In production they are never initialised *in that dict*, so the guard fires on every call, forever.
- **Evidence**:
  ```python
  # main.py:97-125 — dict literal #1, the one startup populates via deps['globals']
  globals_dict = { 'repository_factory': None, ..., 'enhancement_settings': {...} }
  deps = { ..., 'globals': globals_dict, 'enhancement_settings': globals_dict['enhancement_settings'] }
  ```
  ```python
  # config/globals.py:191 — dict literal #2, never written to
  globals_dict = create_globals_dict()
  ```
  ```python
  # core/chunked_processor.py:81-88 — reads dict #2
  from config.globals import globals_dict
  factory = globals_dict.get("repository_factory")
  if factory is None:
      return None          # always taken in production
  return factory.fingerprints
  ```
  ```
  $ grep -rn "globals_dict\[" auralis-web/backend --include='*.py' | grep -v config/startup.py
  auralis-web/backend/main.py:125:    'enhancement_settings': globals_dict['enhancement_settings'],
  $ grep -rn "create_globals_dict" auralis-web/backend --include='*.py'
  auralis-web/backend/config/globals.py:155:def create_globals_dict() -> dict[str, Any]:
  auralis-web/backend/config/globals.py:191:globals_dict = create_globals_dict()
  ```
- **Impact**: Every `ChunkedAudioProcessor` construction — the streaming controller, the recommendation service, the cache warmer, and the enhancement route's `_preprocess_upcoming_chunks` — silently loses its Tier-1 (database) fingerprint lookup and falls through to slower tiers on every chunk of every enhanced playback. The failure is invisible by design: the `except Exception` and the `None` return are both "expected", so nothing logs and nothing errors; the only symptom is a documented fast path that never engages. The #3836 fix that introduced this accessor is therefore inert in production. The duplicated `enhancement_settings` literal in `config/globals.py` is a live second copy of the same defaults, so any future consumer reaching for `config.globals` inherits an unseeded, never-mutated view of the user's settings — the same bug class, one import away.
- **Suggested Fix**: Delete one of the two dictionaries. Cleanest is to make `main.py` call `create_globals_dict()` instead of re-declaring the literal, so `config.globals.globals_dict` *is* the object startup populates. Add a startup log line confirming `repository_factory` is reachable through the accessor so a regression is loud rather than silent.

---

### MEDIUM

---

### INT-F2-1: `useLibraryQuery`/`useTracksQuery` skip the camelCase transform that albums and artists get

- **Severity**: MEDIUM
- **Flow**: 2 — Library Browsing
- **Boundary**: Backend → Frontend
- **Location**: `auralis-web/backend/routers/tracks.py:59-65` → `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts:216-229`
- **Status**: NEW
- **Description**: `extractItemsFromResponse` runs the `albums` and `artists` cases through the canonical `transformAlbums`/`transformArtists` (added for #4418), but the `tracks` case returns the raw backend payload unchanged and casts it to `T` — which callers instantiate as the camelCase `Track` domain type.
- **Evidence**:
  ```ts
  // useLibraryQuery.ts:216-229
  case 'tracks':
    return ((response.tracks ?? response.items) as T[]) || [];
  case 'albums':
    return transformAlbums((response.albums ?? response.items ?? []) as AlbumApiResponse[]) as T[];
  case 'artists':
    return transformArtists((response.artists ?? response.items ?? []) as ArtistApiResponse[]) as T[];
  ```
  Backend `GET /api/library/tracks` returns `serialize_tracks(tracks)` — dicts keyed by `DEFAULT_TRACK_FIELDS` (snake_case: `artwork_url`, `sample_rate`, `bit_depth`, `date_added`, `album_id`, `track_number`, `disc_number`) per `auralis-web/backend/routers/serializers.py:18-42`. The `Track` domain type declares only the camelCase equivalents. The hook's own test suite proves the asymmetry: `useLibraryQuery.test.ts:1049-1089` asserts album/artist snake→camel mapping "(#4418)" with no equivalent assertion for tracks.
- **Impact**: Any consumer of `useTracksQuery`/`useLibraryQuery('tracks', …)` reading `track.artworkUrl`, `track.sampleRate`, `track.bitDepth`, `track.dateAdded`, `track.albumId`, `track.trackNumber`, or `track.discNumber` gets `undefined` despite TypeScript guaranteeing them. Currently masked because the sole non-test consumer, `TrackList.tsx`, reads only fields whose names match on both sides — but the type contract is false today and will silently break the next feature added to that list.
- **Siblings**: INT-F2-2 (same root cause, different endpoint).
- **Suggested Fix**: Add a `transformTracks` call in the `tracks` branch, mirroring the albums/artists branches, and extend the existing snake→camel test block to cover tracks.

---

### INT-F2-2: Album-detail track list is snake_case but `useAlbumDetails.ts` reads camelCase keys

- **Severity**: MEDIUM
- **Flow**: 2 — Library Browsing
- **Boundary**: Backend → Frontend
- **Location**: `auralis-web/backend/routers/albums.py:136-150` → `auralis-web/frontend/src/components/library/Details/useAlbumDetails.ts:63-77`
- **Status**: NEW
- **Description**: `GET /api/albums/{id}/tracks` serializes with `serialize_tracks()` (all snake_case). `useAlbumDetails.ts` maps the raw JSON directly into `DetailTrack[]` and reads `t.artworkUrl`, `t.trackNumber`, `t.discNumber`, `t.albumId` — camelCase keys that do not exist on the response.
- **Evidence**:
  ```python
  # albums.py:136-140
  tracks_data = serialize_tracks(album.tracks if hasattr(album, 'tracks') else [])
  tracks_data.sort(key=lambda t: (t.get('disc_number', 1) or 1, t.get('track_number', 0) or 0))
  ```
  ```ts
  // useAlbumDetails.ts:63-77
  artworkUrl: t.artworkUrl ?? null,     // backend key is artwork_url
  trackNumber: t.trackNumber ?? null,   // backend key is track_number
  discNumber: t.discNumber ?? null,     // backend key is disc_number
  albumId: t.albumId ?? null,           // backend key is album_id
  ```
  `serialize_album_detail`'s docstring even documents the asymmetry ("the sibling `{id}/tracks` endpoint intentionally stays snake_case for its existing consumer") — but that consumer was written assuming camelCase. The backend's own sort already ran server-side using the correct snake_case keys, so track *order* is right; only the per-track values come back `null`.
- **Impact**: Every track in the Album Detail view has `trackNumber`, `discNumber`, `albumId`, and `artworkUrl` permanently `null` regardless of DB contents. Low-visible today because `AlbumTrackTable.tsx` numbers rows by array index and renders no per-track artwork — but multi-disc badges, per-track artwork, and "go to album" from a track are all silently broken.
- **Siblings**: INT-F2-1.
- **Suggested Fix**: Route the `{id}/tracks` response through `transformTrack`/`transformTracks` in `useAlbumDetails.ts`, or change the field reads to snake_case if the endpoint is meant to stay snake_case as documented.

---

### INT-F2-3: `filepath` missing from artist and playlist queue-population track payloads

- **Severity**: MEDIUM
- **Flow**: 2 — Library Browsing
- **Boundary**: Backend → Frontend
- **Location**: `auralis-web/backend/routers/artists.py:43-51,216-226` and `auralis-web/backend/routers/playlists.py:110-114` → `auralis-web/frontend/src/components/library/Items/artists/useContextMenuActions.ts:45-51,74-80` and `auralis-web/frontend/src/components/playlist/usePlaylistContextActions.ts:39-47`
- **Status**: NEW
- **Description**: Two of the endpoints that populate the playback queue from a browse action never include `filepath`. `TrackInArtist` has no `filepath` field at all. `GET /api/playlists/{id}` serializes tracks with the ORM's `Track.to_dict()` rather than `serializers.serialize_track`, and `Track.to_dict()` (`auralis/library/models/core.py:122-155`) also omits `filepath` (plus `loudness`, `crest_factor`, `centroid`, `date_added`/`date_modified` that `TrackApiResponse` declares). Both frontend consumers pass these track objects into the queue, while the `Track`/`TrackApiResponse` contracts declare `filepath: string` as required.
- **Evidence**:
  ```python
  # artists.py:43-51
  class TrackInArtist(BaseModel):
      id: int; title: str; album: str; album_id: int; duration: float
      track_number: int | None = None
      disc_number: int | None = None   # no filepath
  ```
  ```python
  # core.py:122-155 (Track.to_dict) — no 'filepath' key emitted
  return {'id': self.id, 'title': self.title, 'duration': self.duration, ...}
  ```
  ```ts
  // utils/queue/queue_recommender.ts:114-115 and queue_statistics.ts:108 both dereference it
  const format1 = this.extractFormat(track1.filepath);
  ```
- **Impact**: Tracks queued via "Play All"/"Add to Queue" on an artist, or "Play" on a playlist, silently get `filepath: undefined`. Playback itself is unaffected (driven by `track_id` over the WebSocket), but format-aware queue recommendations and format statistics silently degrade for every track queued through these two paths, while tracks queued from the main library/album list work correctly.
- **Suggested Fix**: Add `filepath` to `TrackInArtist` and switch `playlists.py`'s `get_playlist` to `serializers.serialize_track(s)` (or extend `Track.to_dict()`), so all queue-population paths return a consistent track shape.

---

### INT-F3-1: Settings-dialog enhancement defaults never reach the live session (bidirectional desync)

- **Severity**: MEDIUM
- **Flow**: 3 — Audio Enhancement
- **Boundary**: Frontend (Settings dialog) → Backend (persisted `UserSettings`) → Backend (runtime `enhancement_settings` dict)
- **Location**: `auralis-web/frontend/src/components/settings/useSettingsDialog.ts:55-78` → `auralis-web/backend/routers/settings.py:178-193` → `auralis-web/backend/config/startup.py:266-281`
- **Status**: NEW (related to the now-fixed #4409, which addressed the *startup* seed gap; this is the *live-update* gap that remains)
- **Description**: `helpers.seed_enhancement_settings()` copies `default_preset`/`enhancement_intensity`/`auto_enhance` from `UserSettings` into the shared runtime dict, but is invoked only once, inside the lifespan startup handler. `PUT /api/settings` writes the same three fields to the DB but never re-invokes it, never mutates the live dict, and never broadcasts `enhancement_settings_changed`. `useEnhancementControl()` — the documented live source of truth — has no subscription to `/api/settings` at all.

  **The reverse direction is also broken**: `POST /api/player/enhancement/{toggle,preset,intensity}` mutate the runtime dict and broadcast, but never write to a repository — `create_enhancement_router` is not even given a settings repository. A preset chosen in the Enhancement Panel is discarded at process exit, and startup re-seeds from the untouched row, silently reverting it.
- **Evidence**:
  ```python
  # config/startup.py:272-281 — the only DB → runtime sync, once per process
  seed_enhancement_settings(globals_dict['enhancement_settings'], _user_settings)
  ```
  ```python
  # routers/settings.py:178-193 — never touches the live dict or broadcasts
  settings = await asyncio.to_thread(_repo().update_settings, payload)
  await _notify_scanner()
  return {"message": "Settings updated", "settings": settings.to_dict()}
  ```
  ```python
  # routers/enhancement.py:260-262 — runtime-only mutation, no persistence counterpart
  enhancement_settings["preset"] = preset
  ```
- **Impact**: Two concrete desyncs. (1) A user changes Default Preset to "warm" in Settings and saves; the dialog closes with no error, but playback for the rest of the session keeps the previously live values — the change takes effect only at the next backend start. (2) A user who changes preset/intensity in the Enhancement Panel loses that choice on the next launch. The two surfaces can disagree simultaneously, with zero UI feedback either way.
- **Suggested Fix**: Have `update_settings()` call `seed_enhancement_settings(...)` after a successful DB write and broadcast `enhancement_settings_changed`. Symmetrically, give the enhancement endpoints a `SettingsRepository` handle so their mutations persist.

---

### INT-F3-4: The same intensity value is silently clamped by one endpoint and rejected with 422 by the other

- **Severity**: MEDIUM
- **Flow**: 3 — Audio Enhancement
- **Boundary**: Frontend → Backend (two validation contracts for one value)
- **Location**: `auralis-web/backend/routers/enhancement.py:67-73` vs `auralis-web/backend/routers/settings.py:84` → `auralis-web/frontend/src/hooks/enhancement/useEnhancementControl.ts:374`
- **Status**: NEW
- **Description**: `POST /api/player/enhancement/intensity` accepts any float and silently clamps it, returning `200` with a value the caller did not send. `PUT /api/settings` validates the same quantity with a Pydantic range constraint and returns `422` outside `[0.0, 1.0]`. The frontend adds a third layer, clamping locally. The silent-clamp path gives a client no way to learn its value was altered — the `200` body carries the clamped number, but the hook writes its *own* locally-clamped value into state rather than reading the server echo.
- **Evidence**:
  ```python
  # routers/enhancement.py:70-73 — silent coercion, always 200
  @field_validator('intensity')
  @classmethod
  def clamp_intensity(cls, v: float) -> float:
      return max(0.0, min(1.0, v))
  ```
  ```python
  # routers/settings.py:84 — hard rejection, 422
  enhancement_intensity: float | None = Field(default=None, ge=0.0, le=1.0)
  ```
  The preset field shows the opposite (correct) pattern: both routers converge on `EnhancementPresetLiteral`, documented as the single source of truth "so the definitions cannot drift apart" (`auralis-web/backend/schemas.py:25-28`).
- **Impact**: Inconsistent error contract for one setting. A non-React consumer (the Electron main process, a test harness) sending `intensity: 1.5` gets a success from one endpoint and a validation failure from the other. `NaN` is sharper: `max(0.0, min(1.0, nan))` returns `nan` in Python, so the clamp validator does **not** reject it — a `NaN` intensity would be stored in the runtime dict and handed to `ChunkedAudioProcessor`, whereas `ge`/`le` on the settings route rejects it outright.
- **Suggested Fix**: Use `Field(ge=0.0, le=1.0)` on `SetIntensityRequest.intensity` so both endpoints share one contract and `NaN`/out-of-range is a `422`.

---

### INT-F3-5: `/api/processing/parameters` keys the content profile off the REST global preset, not the streaming preset

- **Severity**: MEDIUM
- **Flow**: 3 — Audio Enhancement
- **Boundary**: Backend (WS streaming preset) → Backend (visualizer endpoint) → Frontend
- **Location**: `auralis-web/backend/ws_handlers/playback_commands.py:70-82` → `auralis-web/backend/core/chunked_processor.py:91-97` → `auralis-web/backend/routers/enhancement.py:477-483`
- **Status**: NEW
- **Description**: `handle_play_enhanced` treats the WS payload as authoritative and only falls back to the stored setting when the payload omits or fails to validate it; it never writes the payload preset back into `enhancement_settings`. The processing-parameters endpoint resolves the profile purely from the REST global. `_last_content_profiles` is a `preset → profile` map written by the running `ChunkedAudioProcessor`, i.e. keyed by the *stream's* preset. When the two disagree, the endpoint looks up a key the current stream is not writing and falls into the `profile is None` branch, returning hardcoded `is_default: True` values as though no processing had happened.
- **Evidence**:
  ```python
  # ws_handlers/playback_commands.py:70-82 — payload wins; the global is only a fallback, never updated
  preset = raw_preset.lower() if (raw_preset and ... and raw_preset.lower() in VALID_PRESETS) else None
  if preset is None:
      preset = settings.get("preset", "adaptive")
  ```
  ```python
  # routers/enhancement.py:480-483 — reads the global, not the stream
  preset = get_enhancement_settings().get("preset", "adaptive")
  profile = get_last_content_profile(preset)
  if profile is None:
      return {"is_default": True, "spectral_balance": 0.5, ...}
  ```
- **Impact**: The auto-mastering visualiser silently shows placeholder values instead of real measurements whenever the streaming preset differs from the stored one. The normal UI path keeps them aligned only by convention (`setPreset` POSTs before re-issuing the stream), so this is a latent coupling rather than a constant failure — but it goes live for any caller sending `play_enhanced` with an explicit preset without the REST round-trip, including the `force` path (#3773) that exists precisely to bypass the stored-settings gate. The same stale-global problem affects `_preprocess_upcoming_chunks`, which pre-warms cache entries for the global preset/intensity rather than the streaming ones.
- **Suggested Fix**: Track the preset/intensity actually in flight (streaming state already keys per-`ws_id` state) and resolve the profile from that — or have `handle_play_enhanced` write the accepted values back into `enhancement_settings`.

---

### INT-F4-1: `library_scan_started` is broadcast before the rejection check, so a 409'd scan wipes the running scan's progress UI

- **Severity**: MEDIUM
- **Flow**: 4 — Library Scanning
- **Boundary**: Backend (scan router) → Frontend (`useScanProgress`)
- **Location**: `auralis-web/backend/routers/library_scan.py:52-57` and `:121-123` → `auralis-web/frontend/src/hooks/library/useScanProgress.ts:65-71`
- **Status**: NEW
- **Description**: The router broadcasts `library_scan_started` unconditionally on entry — before `scanner.scan_directories()` runs and long before `result.rejected` is known. When a second scan is requested while one is in flight, the concurrency guard (`auralis/library/scanner/scanner.py:136-142`) or the per-directory dedup guard (`:145-161`) sets `rejected` and the router returns 409. But the start frame has already gone out, and `useScanProgress` responds by resetting to `INITIAL_STATE` with `isScanning: true`, destroying the live counters of the scan that is *actually* running. The 409 then raises through `except HTTPException: raise`, whose comment explicitly declines to emit a terminal frame ("another scan owns the UI state") — reasoning that holds for the terminal frame but not for the start frame already sent.
- **Evidence**:
  ```python
  # routers/library_scan.py:52-57 — fires before any rejection is possible
  await connection_manager.broadcast({
      "type": "library_scan_started", "data": {"directories": request.directories}})
  ...
  # :121-123 — rejection only discovered after the scan call returns
  if result.rejected:
      raise HTTPException(status_code=409, detail="Scan already in progress")
  ```
  ```ts
  // useScanProgress.ts:65-71 — the start frame hard-resets all live progress
  if (message.type === 'library_scan_started') {
    setState((prev) => ({ ...INITIAL_STATE, lastResult: prev.lastResult, isScanning: true }));
  }
  ```
- **Impact**: A user who clicks "Scan" a second time — or whose click races the background auto-scanner, which emits the same frame at `auralis-web/backend/services/library_auto_scanner.py:198-200` — sees the progress display jump back to "0 files" and stay there until the original scan finishes. The toast says "Scan already in progress" while the panel claims a scan just started. On a large library this is minutes of misleading UI.
- **Suggested Fix**: Broadcast `library_scan_started` only once the scan slot is actually acquired — either report a `stage: 'started'` progress event through the existing callback, or split slot acquisition out of `scan_directories` so the router can check before broadcasting.

---

### INT-F4-2: Cancellation exits the scan handler with no terminal WebSocket frame, leaving the UI stuck on "Scanning…"

- **Severity**: MEDIUM
- **Flow**: 4 — Library Scanning
- **Boundary**: Frontend (`AbortController`) → Backend (scan router) → Frontend (`useScanProgress`)
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryScan.ts:37-40,70-72` → `auralis-web/backend/routers/library_scan.py:108-119,174-197` → `auralis-web/frontend/src/hooks/library/useScanProgress.ts:96-101`
- **Status**: NEW
- **Description**: Every other exit from `scan_library` emits a terminal frame so the UI can leave the scanning state — exactly what #4413 added (`library_scan_error` on timeout and on generic failure). The `asyncio.CancelledError` path is the one exit that does not. At `:110` the handler catches `(asyncio.TimeoutError, asyncio.CancelledError)`, calls `scanner.stop_scan()`, and bare-`raise`s. A re-raised `TimeoutError` is caught by the outer `except asyncio.TimeoutError` at `:174` and does broadcast. A re-raised `CancelledError` is not: since Python 3.8 it derives from `BaseException`, so `except Exception as e` at `:189` does not catch it, and there is no `except asyncio.CancelledError` clause. Meanwhile the frontend has two triggers for cancelling that request — a new scan supersedes the old one, and unmount aborts it — while `useScanProgress` clears `isScanning` only on `scan_complete` or `library_scan_error`.
- **Evidence**:
  ```python
  # routers/library_scan.py:110-119
  except (asyncio.TimeoutError, asyncio.CancelledError):
      scanner.stop_scan()
      raise            # CancelledError escapes all outer handlers
  ...
  except Exception as e:                      # :189 — BaseException not covered
      await connection_manager.broadcast({"type": "library_scan_error", ...})
  ```
  ```ts
  // useLibraryScan.ts:37-40 — unmount cancels the in-flight scan request
  return () => { mountedRef.current = false; scanAbortRef.current?.abort(); };
  ```
- **Impact**: Whenever the request coroutine is cancelled (server shutdown, superseded request, or client disconnect if the ASGI server propagates it), the scan halts mid-way — with tracks partially imported — and the scan panel remains "Scanning…" for the rest of the session with no progress and no clean way to start another scan. Only a reload recovers. Same class of stuck state that #4413 fixed for the other two exits.
- **Suggested Fix**: Add an explicit `except asyncio.CancelledError:` clause that broadcasts `library_scan_error` (or a dedicated cancelled frame) before re-raising, mirroring the timeout handler — or wrap the terminal broadcast in a `finally` that fires unless one was already sent.

---

### INT-F4-3: `scan_progress.percentage` is structurally always `null` — the determinate-progress contract is unreachable

- **Severity**: MEDIUM
- **Flow**: 4 — Library Scanning
- **Boundary**: Engine (scanner progress payload) → Backend (progress bridge) → Frontend (progress UI)
- **Location**: `auralis/library/scanner/scanner.py:190-197,214-218,356-359` → `auralis-web/backend/helpers.py:614-626` → `auralis-web/frontend/src/types/ws/library.ts` / `auralis-web/frontend/src/hooks/library/useScanProgress.ts:20-22,79`
- **Status**: NEW (distinct from #4427, which is about divergence *between* the two emitters; this is that neither can ever produce a number)
- **Description**: `scan_progress_percentage()` returns a number only when the scanner supplies a `progress` fraction. The scanner never supplies one: a repo-wide grep for `'progress'` across `auralis/library/scanner/` and `auralis-web/backend/services/library_auto_scanner.py` returns **zero** hits — the three `_report_progress` payloads emit `stage`/`processed`/`added`/`failed`/`total_found`/`current_file`/`directory`/`fingerprints_enqueued` and nothing else. Both the manual bridge and the auto-scanner bridge call the same helper, so `percentage` is `null` on every frame from every path, in every phase.
- **Evidence**:
  ```python
  # helpers.py:625-626 — the only way to get a number
  frac = progress_data.get('progress', 0)
  return round(frac * 100) if frac else None
  ```
  ```python
  # auralis/library/scanner/scanner.py:190-197 — no 'progress' key (nor at :214 or :356)
  self._report_progress({'stage': 'processing', 'processed': ..., 'added': ...,
                         'failed': ..., 'total_found': ..., 'current_file': ...})
  ```
  ```ts
  // useScanProgress.ts:20-22 — contract claims a number during processing
  /** 0-100 during processing; null during discovery (show indeterminate indicator) */
  percentage: number | null;
  ```
- **Impact**: The frontend type, its JSDoc, and any UI branch keyed on `percentage !== null` describe behaviour that cannot occur. Users get an indeterminate indicator for the entire scan including the processing phase, where a real fraction *is* computable (`processed` against batches already discovered). `INITIAL_STATE.percentage` is `0`, so the value also flips `0 → null` on the first frame.
- **Suggested Fix**: Have the processing-phase `_report_progress` emit a `progress` fraction (it already holds `processed` and `total_found`) so the helper produces a real percentage — or delete the `number` half of the contract and the dead determinate branch.

---

### INT-F5-1: `cache_cleared` broadcast has no frontend type, subscriber, or handler

- **Severity**: MEDIUM
- **Flow**: 5 — WebSocket Lifecycle
- **Boundary**: Backend (`routers/cache_streamlined.py`) → Frontend (`types/ws/registry.ts`, `WebSocketContext.tsx`)
- **Location**: `auralis-web/backend/routers/cache_streamlined.py:160-164` → `auralis-web/frontend/src/types/ws/registry.ts:67-156` (no entry), `auralis-web/frontend/src/contexts/WebSocketContext.tsx:168-179` (silent no-op dispatch)
- **Status**: NEW
- **Description**: `POST /api/cache/clear` broadcasts `{"type": "cache_cleared", ...}` to every connected WS client. The frontend's `WebSocketMessageType` union, `AnyWebSocketMessage` union, and the exhaustiveness-checked `ALL_MESSAGE_TYPES` array have no `'cache_cleared'` entry — confirmed via full-repo grep, zero hits outside the backend. `WebSocketContext.dispatchMessage` looks up `subscriptionsRef.current.get(message.type)`; when no key exists it silently does nothing — no console warning, no unknown-type log.
- **Evidence**:
  ```python
  # cache_streamlined.py:160-164
  if broadcast_manager:
      await broadcast_manager.broadcast({
          "type": "cache_cleared", "data": {"message": "All caches cleared"}})
  ```
  `grep -rn "cache_cleared" auralis-web/frontend/src/` returns nothing.
- **Impact**: Any WS client other than the one that issued the POST (a second Electron window, or a dev-mode browser tab on the same backend) never learns the cache was cleared. `CacheManagementPanel.tsx` has no periodic refresh (its `refreshInterval` prop is accepted but unused) and the initiating client already calls `refetchStats()` directly, so this is purely a stale-state gap for other simultaneously open clients — MEDIUM by the "stale frontend state after a backend event" rule, downgraded in practice by the single-window norm.
- **Suggested Fix**: Add `'cache_cleared'` to the message-type union and `ALL_MESSAGE_TYPES`, and give `CacheManagementPanel` (or a shared cache-stats hook) a `useWebSocketMessages(['cache_cleared'], () => refetchStats())` subscriber.

---

### INT-F6-1: Two live, divergent client implementations of `/tracks/{id}/similar`, exporting two incompatible types both named `SimilarTrack`

- **Severity**: MEDIUM
- **Flow**: 6 — Fingerprint & Similarity
- **Boundary**: Backend (similarity router) → Frontend (two independent clients)
- **Location**: `auralis-web/backend/routers/similarity.py:104-202` → `auralis-web/frontend/src/hooks/fingerprint/useSimilarTracks.ts:32-47,174-211` **and** `auralis-web/frontend/src/services/similarityService.ts:21-30,92,109-115`
- **Status**: NEW
- **Description**: The same endpoint has two unrelated frontend clients, both wired into production UI, each exporting a type named `SimilarTrack` with an incompatible shape:
  - `hooks/fingerprint/useSimilarTracks.ts` — raw `fetch`, sends `limit` + `use_graph` + `include_details`, maps snake→camel by hand, has an LRU cache and an `AbortController`. Consumed by `auralis-web/frontend/src/components/shared/SimilarTracksModal/SimilarTracksModal.tsx:45,75`.
  - `services/similarityService.ts` — `createCrudService`, sends only `limit` + `use_graph`, keeps snake_case, **no cache, no abort**. Consumed by `auralis-web/frontend/src/components/features/discovery/useSimilarTracksLoader.ts:2,29`, with `SimilarTracksList.tsx:4` and `SimilarTracksListItem.tsx:11` importing that variant's type.

  Critically, the race-condition and cancellation fixes landed on only one of them. `useSimilarTracks` carries explicit remediation for #3616/#3646 and #4162. `useSimilarTracksLoader` has none of it: no `AbortController`, no request-identity guard, and an effect that refires whenever `trackId`/`limit`/`useGraph` change while unconditionally calling `setSimilarTracks(tracks)` on whichever response returns last.
- **Evidence**:
  ```ts
  // hooks/fingerprint/useSimilarTracks.ts:32-38 — camelCase
  export interface SimilarTrack { trackId: number; distance: number; similarityScore: number; ... }
  ```
  ```ts
  // services/similarityService.ts:21-30 — snake_case, same name, same endpoint
  export interface SimilarTrack { track_id: number; distance: number; similarity_score: number; ... }
  ```
  ```ts
  // useSimilarTracksLoader.ts — no abort, no request-identity guard
  const tracks = await similarityService.findSimilar(trackId, limit, useGraph);
  setSimilarTracks(tracks);
  useEffect(() => { loadSimilarTracks(); }, [trackId, limit, useGraph, loadSimilarTracks]);
  ```
- **Impact**: The discovery-panel path re-introduces the exact bugs already fixed in the modal path: switching tracks quickly can render an older track's list (last-response-wins), and unmounting mid-search leaves the request running and can `setState` after teardown. Any future backend response change must be applied in two places under two naming conventions, and the duplicated type name lets a wrong import type-check in some positions. Also violates the project's DRY / no-variants rules.
- **Suggested Fix**: Collapse to one client. Keep `services/similarityService.ts` as the transport, add abort + request-identity handling and the LRU cache there, and re-express `useSimilarTracks` as a thin hook over it. Export exactly one `SimilarTrack` type.

---

### INT-F6-2: Every fingerprint/similarity fetch discards the backend's `detail` body, collapsing three distinct states into one opaque error

- **Severity**: MEDIUM
- **Flow**: 6 — Fingerprint & Similarity
- **Boundary**: Backend (error contract) → Frontend (error surface)
- **Location**: `auralis-web/backend/routers/similarity.py:146-149,176-179,240-241,277-278` → `auralis-web/frontend/src/hooks/fingerprint/useSimilarTracks.ts:185-189`, `auralis-web/frontend/src/hooks/fingerprint/useTrackFingerprint.ts:33-38`, `auralis-web/frontend/src/hooks/fingerprint/useAlbumFingerprint.ts:33-38`
- **Status**: NEW
- **Description**: The similarity router deliberately encodes actionable information in `HTTPException.detail`. Three reachable states are semantically distinct: (1) `404` — the track does not exist; (2) `404` — the track exists but has no fingerprint yet, and the router **enqueues it for background fingerprinting** and says so; (3) `503` — the similarity system is not yet initialised. All three frontend hooks throw on `!response.ok` using only `response.status`/`response.statusText` and never read the JSON body, so the two 404s are indistinguishable and the transient 503 renders as terminal.
- **Evidence**:
  ```python
  # routers/similarity.py:146-149 — the detail is the whole point of this branch
  raise HTTPException(status_code=404,
      detail=f"Track {track_id} does not have a fingerprint. Queued for background processing.")
  ```
  ```ts
  // useSimilarTracks.ts:185-189 — body never parsed
  if (!response.ok) {
    throw new Error(`Similarity search failed: ${response.status} ${response.statusText}`);
  }
  ```
- **Siblings**: same pattern at `useTrackFingerprint.ts:38` and `useAlbumFingerprint.ts:38`.
- **Impact**: The most common first-run experience — opening "Similar Tracks" on a not-yet-fingerprinted track — shows a hard error instead of "analysing, check back shortly", even though the backend has queued the work and a retry seconds later succeeds. Users cannot distinguish "will fix itself", "wait for initialisation", and "this track is gone". `statusText` is empty over HTTP/2, so the message can degrade to `"Similarity search failed: 404 "`.
- **Suggested Fix**: Parse the error body and surface `detail` in all three hooks — ideally by routing them through the shared `ApiErrorHandler` in `auralis-web/frontend/src/types/api.ts`, which already preserves status and exposes `isNotFound()`/`isServerError()`. Better still, give the "queued for fingerprinting" case its own status (`202`) or error code so the UI can render a distinct pending state.

---

### INT-F6-3: `useSimilarTracks`'s cache key omits `use_graph`, so graph and real-time results alias each other

- **Severity**: MEDIUM
- **Flow**: 6 — Fingerprint & Similarity
- **Boundary**: Frontend (client cache) → Backend (two distinct result sources)
- **Location**: `auralis-web/frontend/src/hooks/fingerprint/useSimilarTracks.ts:88-90,144-154` → `auralis-web/backend/routers/similarity.py:109,153-189`
- **Status**: NEW
- **Description**: `use_graph` is a result-changing parameter: `true` reads pre-computed edges from `similarity_graph` via `KNNGraphBuilder.get_neighbors`, `false` (or an empty graph) recomputes against the fitted model. The two produce different neighbour sets whenever the stored graph is stale, and derive `rank` differently (stored column vs `enumerate(..., start=1)`). The hook's cache key is `` `${trackId}:${limit}:${includeDetails}` `` — `useGraph` is absent, despite being a public option on `findSimilar`.
- **Evidence**:
  ```ts
  // useSimilarTracks.ts:88-90 — useGraph is absent from the key
  function getCacheKey(trackId: number, limit: number, includeDetails: boolean): string {
    return `${trackId}:${limit}:${includeDetails}`;
  }
  ```
  ```python
  # routers/similarity.py:153-189 — the two sources the flag selects between
  graph_builder = get_graph_builder() if use_graph else None
  if graph_builder is not None: neighbors = ... graph_builder.get_neighbors(...)
  if graph_builder is None:     similarity_results = ... similarity.find_similar(...)
  ```
- **Impact**: A caller asking for `useGraph: false` — the explicit "give me fresh, non-cached-graph results" escape hatch — silently receives the earlier graph-backed answer, and vice versa. The cache is module-level and session-lived, so the aliasing persists until 50 other keys evict it. The escape hatch is unusable exactly when it matters most: right after new tracks are fingerprinted and the stored graph is stale.
- **Suggested Fix**: Include `useGraph` in `getCacheKey`. Consider also invalidating `similarityCache` when the graph is rebuilt or the system is re-fitted.

---

### INT-F6-4: `explain_similarity` skips the existence/fingerprint preconditions its sibling `compare_tracks` enforces

- **Severity**: MEDIUM
- **Flow**: 6 — Fingerprint & Similarity
- **Boundary**: Frontend (explain request) → Backend (similarity router) → Engine
- **Location**: `auralis-web/backend/routers/similarity.py:255-285` vs sibling `:204-253` → `auralis-web/frontend/src/components/features/discovery/SimilarityVisualization.tsx:58`
- **Status**: NEW
- **Description**: `compare_tracks` validates both track IDs against the repository and both fingerprints via `repos.fingerprints.exists`, raising precise 404s. `explain_similarity` — the same conceptual operation on the same two IDs, one route down — performs none of those checks; it goes straight to the engine and folds every possible cause (nonexistent track, missing fingerprint on either side, engine failure) into a single `NotFoundError("Explanation", detail="Could not generate explanation")`. Unlike `/similar`, it also does not enqueue a missing fingerprint, so the explain path never self-heals.
- **Evidence**:
  ```python
  # :232-235 — compare_tracks validates
  if not await asyncio.to_thread(repos.fingerprints.exists, track_id1):
      raise NotFoundError("Track", detail=f"Track {track_id1} missing fingerprint")
  ```
  ```python
  # :275-283 — explain_similarity does not; every cause collapses to one message
  explanation = await asyncio.to_thread(similarity.get_similarity_explanation, track_id1, track_id2, top_n=top_n)
  if not explanation:
      raise NotFoundError("Explanation", detail="Could not generate explanation")
  ```
  Secondarily, `top_n: int = Query(5, ge=1, le=25, ...)` hard-codes the upper bound to today's fingerprint dimension count, with nothing linking it to the vector definition in `auralis/library/models/fingerprint.py`.
- **Impact**: `SimilarityVisualization.tsx` shows one generic failure for four different causes, three of which are user-actionable in different ways. Because no fingerprint is enqueued, a user who opens the explanation view on an un-fingerprinted track gets a permanent failure, while the same track opened in "Similar Tracks" would have been queued and fixed itself.
- **Suggested Fix**: Extract the precondition block from `compare_tracks` into `auralis-web/backend/routers/similarity_common.py` and apply it in `explain_similarity` (enqueueing on a missing fingerprint, matching `/similar`). Derive `top_n`'s upper bound from the fingerprint dimension count rather than the literal `25`.

---

### INT-F7-1: Artist artwork is an external URL served under a CSP that only allows `img-src 'self' data: blob:`

- **Severity**: MEDIUM
- **Flow**: 7 — Artwork
- **Boundary**: Engine (DB model) → Backend (artists router + security headers) → Frontend (`<img>`)
- **Location**: `auralis/library/models/core.py:240-241` → `auralis-web/backend/routers/artists.py:147-148` → `auralis-web/frontend/src/components/library/Details/ArtistHeader.tsx:40-44`, contradicted by `auralis-web/backend/config/middleware.py:85`
- **Status**: NEW
- **Description**: Album artwork is deliberately proxied — both `Album.to_dict()` and `serialize_album()` rewrite the filesystem path into `/api/albums/{id}/artwork` "so internal paths are never leaked". Artist artwork took the opposite route: `Artist.artwork_url` is stored as a raw **external** URL (sourced from `'musicbrainz' | 'discogs' | 'lastfm'`), passed through `artists.py` unmodified, mapped to `artworkUrl` by `artistTransformer.ts:29`, and rendered directly as an `<img src>`. There is no `/api/artists/{id}/artwork` proxy anywhere in the router set, and the backend's own `SecurityHeadersMiddleware` emits `img-src 'self' data: blob:`, which permits no remote host.
- **Evidence**:
  ```python
  # auralis/library/models/core.py:240
  artwork_url: Mapped[str | None] = mapped_column(Text)  # External URL to artist image
  ```
  ```python
  # auralis-web/backend/config/middleware.py:85
  "img-src 'self' data: blob:; "
  ```
  ```tsx
  // ArtistHeader.tsx:40-44
  artist.artworkUrl ? ( <... src={artist.artworkUrl} ...
  ```
- **Impact**: Artist header images are blocked by the browser wherever the CSP header is honoured, so the artist detail page silently shows the no-artwork fallback for every artist that *does* have artwork. Secondarily, one field name (`artwork_url`) now carries two incompatible value kinds — API path for album/track, absolute external URL for artist — so `withArtworkSize()`, which appends `?size=` to anything containing `/artwork`, would mangle an artist URL if one were ever passed through it.
- **Suggested Fix**: Pick one convention. Either add an `/api/artists/{id}/artwork` proxy that caches the remote image server-side (matching the album flow and keeping the CSP tight), or explicitly widen `img-src` to the artwork CDN hosts. The proxy is preferable — it also removes a per-render outbound third-party request from a desktop app.

---

### INT-F7-2: Concurrent thumbnail generation races on a shared `.tmp` filename, and the corrupt result is cached permanently

- **Severity**: MEDIUM
- **Flow**: 7 — Artwork
- **Boundary**: Frontend (many concurrent `<img>` requests) → Backend (thumbnail cache)
- **Location**: `auralis-web/frontend/src/components/album/AlbumArt.tsx:104-106` / `auralis-web/frontend/src/components/album/AlbumCard/AlbumCard.tsx:71` → `auralis-web/backend/routers/artwork.py:81-93`
- **Status**: NEW
- **Description**: `_get_or_create_thumbnail` writes to `dst.with_suffix(dst.suffix + ".tmp")` — a name derived only from the cache key, not from the writer. The cache key is identical for every concurrent request for the same album at the same size bucket. Each request runs the function on its own thread via `asyncio.to_thread`, so N simultaneous requests open and `image.save()` into the *same* temp path concurrently, interleaving bytes, then each `tmp.replace(dst)` promotes whatever the file ended up containing. The in-code comment asserts the opposite ("Write atomically-ish… so a concurrent request never reads a half-written file") — the rename does protect *readers* of `dst`, but nothing protects the temp file from concurrent *writers*.
- **Evidence**:
  ```python
  # auralis-web/backend/routers/artwork.py:78-93
  key = f"{path_hash}_{bucket}_{stat.st_mtime_ns:x}_{stat.st_size:x}{ext}"
  dst = thumb_dir / key
  if not dst.exists():
      tmp = dst.with_suffix(dst.suffix + ".tmp")   # same name for every concurrent writer
      image.save(tmp, format=pil_fmt)
      tmp.replace(dst)
  ```
  Concurrency is the normal case: a grid renders many `AlbumArt`/`AlbumCard` at once, and the same album routinely appears in more than one mounted view (grid + player bar + detail hero).
- **Impact**: A corrupted/truncated thumbnail can be promoted into the cache. Because the key is content-addressed on the *source* file's mtime+size, the bad thumbnail is served for every subsequent request at that bucket and is never regenerated — the artwork stays visibly broken until the source file is touched or the thumbnail directory is manually cleared. The `except Exception → return None` fallback does not cover this: it only fires for the writer that errors, not for the one that promotes bad bytes.
- **Suggested Fix**: Make the temp name unique per writer (`tempfile.mkstemp(dir=thumb_dir)`, or append `os.getpid()`/`uuid4().hex`) before `replace()`. Optionally add a per-key in-process lock so N requests for the same bucket collapse into one render.

---

### INT-F7-3: `useArtworkPalette`'s module-level palette cache is never invalidated by `artwork_updated`

- **Severity**: MEDIUM
- **Flow**: 7 — Artwork
- **Boundary**: Backend (WebSocket broadcast) → Frontend (derived UI state)
- **Location**: `auralis-web/backend/routers/artwork.py:286-293` → `auralis-web/frontend/src/hooks/app/useArtworkPalette.ts:85-91,105,115`
- **Status**: NEW
- **Description**: Every other artwork consumer subscribes to `artwork_updated` via `useArtworkRevision()` and folds the revision into the URL (`AlbumArt.tsx:100-106`, `AlbumCard.tsx:67-71`). `useArtworkPalette` does not: it builds its URL with `getArtworkUrl(albumId, { size: 64 })` — no `revision` — and short-circuits on a module-level `paletteCache.get(albumId)` that has no invalidation path at all. The hook is the sole source of the extracted colours driving `gradient`, `glow`, and `accentColor`.
- **Evidence**:
  ```python
  # backend broadcasts on extract / download / delete
  await connection_manager.broadcast({"type": "artwork_updated", "data": {"action": "extracted", "album_id": album_id, ...}})
  ```
  ```ts
  // useArtworkPalette.ts:85-91 — cache hit returns before any WS state is consulted
  const cached = paletteCache.get(albumId);
  if (cached) { setPalette(cached); setLoading(false); setError(null); return; }
  // :105 — no `revision` passed, unlike every other call site
  const artworkUrl = getArtworkUrl(albumId, { size: 64 });
  ```
- **Impact**: After a user extracts or downloads new artwork (or deletes it), the album's `<img>` updates but the artwork-derived theming — background gradient, glow, accent colour — keeps rendering the *previous* artwork's palette for the rest of the session. If the artwork was deleted the palette persists with no image at all. Visible mismatch, fixed only by an app restart.
- **Suggested Fix**: Call `useArtworkRevision(albumId)` in the hook, key `paletteCache` on `${albumId}:${revision}` (or evict on revision advance), and pass `revision` into `getArtworkUrl` so the fetch itself is cache-busted.

---

### LOW

---

### INT-F1-2: `crossfade_samples` is structurally always 0 on the wire — the frontend's crossfade path can never execute

- **Severity**: LOW
- **Flow**: 1 — Track Playback
- **Boundary**: Backend → Frontend (WS `audio_chunk_meta` field)
- **Location**: `auralis-web/backend/core/stream_chunk_ops.py:236-244`, `auralis-web/backend/core/stream_normal.py:278-284` → `auralis-web/frontend/src/services/audio/PCMStreamBuffer.ts:96-130,248-273`
- **Status**: NEW
- **Description**: Every streaming path (enhanced, seek, normal) always sends `crossfade_samples: 0`. This is *correct* — `ChunkOperations.extract_chunk_segment` already trims each processed chunk to its non-overlapping `CHUNK_INTERVAL` segment before it reaches the streaming layer, so there is no overlap left to blend, and `apply_boundary_crossfade` is intentionally a no-op. But the frontend's `PCMStreamBuffer.applyCrossfade()` — a full linear-fade implementation — is therefore permanently unreachable on the live wire contract, and the comment in `stream_chunk_ops.py` ("Server already applied the boundary crossfade above") is actively misleading about what that function currently does.
- **Evidence**:
  ```py
  # stream_chunk_ops.py:236-244
  # Server already applied the boundary crossfade above; send 0 so the
  # client does not double-apply it (fixes #2188: double crossfade).
  await controller._send_pcm_chunk(..., crossfade_samples=0)
  ```
  ```ts
  // PCMStreamBuffer.ts:117-120 — never reached in production
  if (crossfadeSamples > 0 && this.lastChunkEnd !== null) {
    dataToWrite = this.applyCrossfade(pcm, crossfadeSamples);
  }
  ```
- **Impact**: No functional playback impact — the chunk geometry is confirmed non-overlapping. Purely a maintenance hazard: a contributor reading the comment could reasonably conclude the server performs real crossfade mixing, and the dead client path adds ~40 lines of untested logic that will silently rot.
- **Suggested Fix**: Either remove `PCMStreamBuffer.applyCrossfade()` and the `crossfadeSamples` parameter, or fix the comment to state that `apply_boundary_crossfade` is a no-op by design (matching its own docstring).

---

### INT-F2-6: `useAlbumDetails.ts` collapses all fetch failures to one generic message, losing the 404 vs 5xx distinction

- **Severity**: LOW
- **Flow**: 2 — Library Browsing
- **Boundary**: Backend → Frontend
- **Location**: `auralis-web/backend/routers/albums.py:107-108` → `auralis-web/frontend/src/components/library/Details/useAlbumDetails.ts:44-46`
- **Status**: NEW
- **Description**: Every other library-browsing data path goes through `utils/apiRequest`'s `get()` + `ApiErrorHandler`, which preserves the HTTP status and exposes `isNotFound()`/`isServerError()`. `useAlbumDetails.ts` instead calls `fetch()` directly and, on any non-OK response, throws a bare `Error('Failed to fetch album details')` with no status attached.
- **Evidence**:
  ```ts
  // useAlbumDetails.ts:42-47
  const response = await fetch(`/api/albums/${albumId}/tracks`, { signal: controller.signal });
  if (!response.ok) { throw new Error('Failed to fetch album details'); }
  ```
  The backend returns a distinguishable 404 (`raise NotFoundError("Album", album_id)`) for a deleted album vs a 500 for a real server error; both collapse to the same string.
- **Impact**: Navigating to a stale/deleted album link (404 — recoverable, "go back to library") and a genuine backend failure (500 — possibly transient, "retry") render identically, so users cannot tell which they are in and the UI cannot offer a differentiated recovery action.
- **Suggested Fix**: Route this fetch through the shared `get()`/`ApiErrorHandler` used by the rest of the library hooks so the status survives.

---

### INT-F3-6: Settings/enhancement response types are looser than their request types

- **Severity**: LOW
- **Flow**: 3 — Audio Enhancement
- **Boundary**: Backend (settings schemas) → Frontend
- **Location**: `auralis-web/backend/routers/settings.py:82-84` (request) vs `:117-119` (response) → `auralis-web/backend/schemas.py:25-28`
- **Status**: NEW
- **Description**: The settings request model constrains the enhancement fields properly (`default_preset: EnhancementPresetLiteral | None`, `enhancement_intensity: float | None = Field(ge=0.0, le=1.0)`), but the response model for the same fields degrades to unconstrained `str | None` / `float | None`. `EnhancementSettings.preset` in `auralis-web/backend/routers/enhancement.py:79` shows the same asymmetry — a bare `str` where the request uses the literal.
- **Evidence**:
  ```python
  # routers/settings.py:82-84 — request: constrained
  default_preset: EnhancementPresetLiteral | None = None
  enhancement_intensity: float | None = Field(default=None, ge=0.0, le=1.0)
  # routers/settings.py:117-119 — response: unconstrained
  default_preset: str | None = None
  enhancement_intensity: float | None = None
  ```
- **Impact**: No runtime breakage — values reaching these models are validated on the way in. The cost is contract fidelity: generated OpenAPI advertises the preset enum on requests but a free-form string on responses, so a schema-generated client gets `string` where the frontend hand-declares the narrow union. A value written into `UserSettings` outside the API (a migration, a manual DB edit, a legacy row) would also flow out unflagged.
- **Suggested Fix**: Use `EnhancementPresetLiteral` in `SettingsResponse.default_preset` and `EnhancementSettings.preset`, and mirror the `ge/le` bound on the response intensity.

---

### INT-F4-4: `phase: 'fingerprinting'` is declared on both sides but its only emitter is dead code

- **Severity**: LOW
- **Flow**: 4 — Library Scanning
- **Boundary**: Engine (scanner) → Frontend (`ScanProgress.phase`)
- **Location**: `auralis/library/scanner/scanner.py:331-359` → `auralis-web/frontend/src/types/ws/library.ts` / `auralis-web/frontend/src/hooks/library/useScanProgress.ts:23`
- **Status**: NEW
- **Description**: The only place that emits `{'stage': 'fingerprinting'}` is `LibraryScanner._enqueue_fingerprints`, and a repo-wide grep across `auralis/`, `auralis-web/`, and `tests/` finds its definition and **no call sites at all**. Post-scan fingerprint enqueueing is done instead by the router via `get_fingerprint_queue()` (`auralis-web/backend/routers/library_scan.py:126-135`), which emits no progress frame. So the phase never reaches the frontend, yet it is a first-class member of the TS union.
- **Evidence**:
  ```
  $ grep -rn "_enqueue_fingerprints" auralis/ auralis-web/ tests/
  auralis/library/scanner/scanner.py:331:    async def _enqueue_fingerprints(self, track_records: list[Any]) -> None:
  ```
  Its payload also carries only `stage` and `fingerprints_enqueued` — no `processed`, `total_found`, or `current_file` — so if it were wired up the bridge would compute `current: 0, total: 0` and the UI would snap back to "0 of 0" after a completed scan.
- **Impact**: No breakage. The contract overstates what the backend sends, so an author may build a fingerprinting-phase UI that never renders. The dead `async` method is also a trap: it is `async` while `scan_directories` is fully synchronous and runs inside `asyncio.to_thread`, so wiring it back naively would raise `RuntimeError: no running event loop` — exactly the hazard documented at `scanner.py:186-187` for a different call.
- **Suggested Fix**: Delete `_enqueue_fingerprints` and drop `'fingerprinting'` from the TS union, or emit a real fingerprinting frame from the router's enqueue loop with proper `processed`/`total` values.

---

### INT-F4-5: `library_scan_started` broadcasts absolute filesystem paths that sibling frames deliberately redact

- **Severity**: LOW
- **Flow**: 4 — Library Scanning
- **Boundary**: Backend (scan router / auto-scanner) → Frontend (WS payload)
- **Location**: `auralis-web/backend/routers/library_scan.py:54-57`, `auralis-web/backend/services/library_auto_scanner.py:198-200` → `auralis-web/frontend/src/types/ws/library.ts`
- **Status**: NEW
- **Description**: The two `library_scan_error` emitters go out of their way to strip OS paths (`f"{type(e).__name__} during library scan"`, commented "no OS paths leak (#3543)"). The paired `library_scan_started` frame sends `request.directories` verbatim, and those strings have been rewritten by `LibraryScanRequest.validate_directory_paths` into fully-resolved absolute paths. `scan_progress.current_file` is in the same position. The frontend types the field and `useScanProgress` ignores it entirely.
- **Evidence**:
  ```python
  # library_scan.py:54-57 — full absolute paths on the wire
  "type": "library_scan_started", "data": {"directories": request.directories},
  # library_scan.py:193-196 — the deliberate contrast
  "data": {"error": f"{type(e).__name__} during library scan"},
  ```
- **Impact**: Low in practice — Auralis is a desktop app on localhost and the user picked the directory — but the WebSocket broadcasts to *all* connected clients, and the redaction policy applied to the error frames is inconsistent with the start/progress frames. Mostly a policy-consistency and log-hygiene gap.
- **Suggested Fix**: Send basenames or a directory count in `library_scan_started` (the frontend reads neither), or record the decision that scan paths are intentionally exposed and relax the #3543 redaction so one policy governs the whole frame family.

---

### INT-F5-2: `processingService.subscribeToJob` sends `job_id` outside the `data` envelope the backend requires

- **Severity**: LOW (dead code — no live caller)
- **Flow**: 5 — WebSocket Lifecycle
- **Boundary**: Frontend (`services/processingService.ts`) → Backend (`ws_handlers/messages.py`)
- **Location**: `auralis-web/frontend/src/services/processingService.ts:182-186` → `auralis-web/backend/ws_handlers/messages.py:43-53`
- **Status**: NEW
- **Description**: `subscribeToJob()` sends `{ type: 'subscribe_job_progress', job_id: jobId }` — `job_id` at the top level, not wrapped in `data`. `handle_subscribe_job_progress` reads `data = message.get("data", {})` then `job_id = data.get("job_id")`; `data` is absent, so `job_id` is always `None`, failing the `isinstance` check, and the server always replies `invalid_job_id`. `processingService` also opens its own independent `WebSocketManager` connection to `/ws` rather than reusing the app's singleton, violating the single-connection invariant the rest of the app maintains.
- **Evidence**:
  ```ts
  // processingService.ts:181-186
  this.wsManager.send(JSON.stringify({ type: 'subscribe_job_progress', job_id: jobId }));
  ```
  ```python
  # messages.py:46-53
  data = message.get("data", {})
  job_id = data.get("job_id")
  if not isinstance(job_id, str) or not job_id or len(job_id) > 64:
      await send_error_response(websocket, "invalid_job_id", ...)
  ```
- **Impact**: None today — `processingService` has zero live importers (already tracked as dead code in #4470). If ever re-wired into a live UI, job-progress subscription would silently fail 100% of the time.
- **Suggested Fix**: If revived, wrap `job_id` in `data: { job_id }` — or retire the file and its second WS connection in favour of routing job-progress through `WebSocketContext`/`useWebSocketMessages`.

---

### INT-F5-3: Normal-stream `audio_stream_start.preset` sends `"none"`, a value outside the frontend's `EnhancementPreset` union

- **Severity**: LOW
- **Flow**: 5 — WebSocket Lifecycle
- **Boundary**: Backend (`core/stream_normal.py`) → Frontend (`types/ws/streaming.ts`)
- **Location**: `auralis-web/backend/core/stream_normal.py:195-196` → `auralis-web/frontend/src/types/ws/streaming.ts:29-46`, `auralis-web/frontend/src/types/domain.ts:159-164`
- **Status**: NEW
- **Description**: `stream_normal.py`'s call to `_send_stream_start` hardcodes `preset="none"` for the unprocessed-playback path. `AudioStreamStartMessage.data.preset` is typed as `EnhancementPreset` (`'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy'`), which has no `"none"` member — so every `audio_stream_start` frame for a `play_normal` stream violates its own declared frontend type.
- **Evidence**:
  ```python
  # stream_normal.py:193-197
  if not await controller._send_stream_start(
      websocket, track_id=track_id, preset="none",  # No processing
      intensity=1.0,
  ```
  ```ts
  // domain.ts:159-164
  export type EnhancementPreset = 'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy';
  ```
- **Impact**: None currently — nothing reads `.data.preset` off `audio_stream_start`; the field is accepted, typed, and ignored. A type-accuracy gap that would surface as a real TS error the moment any consumer starts reading it.
- **Suggested Fix**: Widen `EnhancementPreset` to include `'none'` if that is a legitimate wire value, or add an explicit `preset: EnhancementPreset | 'none'` override for the normal-stream case.

---

### INT-F5-4: `audio_stream_error.recovery_position` is computed and sent but never read by the frontend's error handler

- **Severity**: LOW
- **Flow**: 5 — WebSocket Lifecycle
- **Boundary**: Backend (`core/stream_messages.py` / `audio_stream_controller.py`) → Frontend (`hooks/enhancement/useAudioStreamingCore.ts`)
- **Location**: `auralis-web/frontend/src/types/ws/streaming.ts:131-135` → `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts:348-358`
- **Status**: NEW (distinct from the closed #3547, which was about the field being *undeclared* on the frontend type — it is now declared but still unconsumed)
- **Description**: The frontend type explicitly documents `recovery_position` as existing "so the client can offer a 'retry from here'", but `handleStreamError` — the only subscriber of `audio_stream_error` — ignores it: it builds a generic error string, dispatches `setStreamingError`, and calls `cleanupStreaming()` unconditionally. No code path reads `message.data.recovery_position` anywhere in the frontend.
- **Evidence**:
  ```ts
  // useAudioStreamingCore.ts:348-358
  const errorMsg = `Streaming error: ${message.data.error} (${message.data.code})`;
  dispatch(setStreamingError({ streamType, error: errorMsg, trackId: message.data.track_id }));
  cleanupStreaming();
  ```
- **Impact**: On a mid-stream chunk failure the backend already knows a good resume offset, but the user gets a generic error and a full teardown (resetting the AudioContext and PCM buffer) with no "resume from here" affordance — strictly worse recovery UX than the wire protocol was designed to support.
- **Suggested Fix**: In `handleStreamError`, when `recovery_position` is present, offer (or auto-trigger) a re-issue via `reissueActiveStreamAs`/`start_position` seeded from that value.

---

### INT-F6-5: `SimilarTrack.duration` is declared and rendered on the frontend but never emitted by the backend model

- **Severity**: LOW
- **Flow**: 6 — Fingerprint & Similarity
- **Boundary**: Backend (`SimilarTrack` response model) → Frontend (list item)
- **Location**: `auralis-web/backend/routers/similarity.py:40-50` → `auralis-web/frontend/src/services/similarityService.ts:28`, `auralis-web/frontend/src/components/features/discovery/SimilarTracksListItem.tsx:94`
- **Status**: NEW
- **Description**: The backend `SimilarTrack` model declares exactly `track_id`, `distance`, `similarity_score`, `rank`, `title`, `artist`, `album`. The detail-enrichment block sets only `title`, `artist`, `album`; `duration` is neither declared nor populated, and `response_model=list[SimilarTrack]` strips anything extra. The frontend service type nevertheless declares `duration?: number` and the list item renders it.
- **Evidence**:
  ```tsx
  // SimilarTracksListItem.tsx:94 — guarded, so it silently never renders
  {track.duration && ` • ${formatDuration(track.duration)}`}
  ```
- **Impact**: No breakage — the `&&` guard means the duration segment is simply never rendered, so the discovery list permanently omits a field the UI was written to show. A silently-missing feature rather than a crash.
- **Suggested Fix**: Add `duration: float | None` to the backend model and populate it in the enrichment loop (the batch-fetched `Track` rows already carry it), or drop the field and the render.

---

### INT-F7-4: Thumbnail cache has no eviction, and `DELETE /artwork` does not purge derived thumbnails

- **Severity**: LOW
- **Flow**: 7 — Artwork
- **Boundary**: Backend (artwork lifecycle) → filesystem
- **Location**: `auralis-web/backend/routers/artwork.py:73-93` (create) vs `:301-335` (delete)
- **Status**: NEW
- **Description**: The cache key deliberately embeds the source `mtime_ns` and `st_size` so an artwork edit yields a fresh key. Nothing removes the superseded keys: `delete_album_artwork` calls `repos.albums.delete_artwork(album_id)` and broadcasts, but never touches the thumbnail directory; extract/download likewise leave the previous generation behind. A repo-wide grep confirms `thumbnails` appears only in `artwork.py` — no sweeper, TTL, or size cap exists anywhere.
- **Evidence**: `grep -rn "thumbnails" auralis-web/backend/ --include='*.py'` → only a comment at `routers/artwork.py:67` and the `thumb_dir` construction at `:222`. No eviction sibling in `auralis-web/backend/services/` or `auralis/services/artwork_service.py`.
- **Impact**: The thumbnail directory grows monotonically for the life of the install — up to 5 buckets per artwork *generation*, retained across every re-extract, re-download, and delete. Bounded per generation but unbounded over time; a slow, silent disk leak with no user-visible cleanup path.
- **Suggested Fix**: Purge `{path_hash}_*` entries in `delete_artwork`/`update_artwork_path`, or add a periodic sweeper in `auralis-web/backend/services/` that drops thumbnails whose source hash no longer maps to a live `Album.artwork_path`.

---

### INT-F7-5: `artwork_updated` payload is an untyped dict literal on the backend while the frontend has a typed contract

- **Severity**: LOW
- **Flow**: 7 — Artwork
- **Boundary**: Backend (WebSocket broadcast) → Frontend (typed WS registry)
- **Location**: `auralis-web/backend/routers/artwork.py:286-293,330-333,390-397` → `auralis-web/frontend/src/types/ws/enhancement.ts:72-76`, `auralis-web/frontend/src/types/ws/registry.ts:143`, `auralis-web/frontend/src/hooks/library/useArtworkUpdates.ts:68-75`
- **Status**: NEW
- **Description**: The frontend declares a precise contract for this message, registers it in the registry, and guards it in `types/ws/guards.ts:147`. The backend has no counterpart: the message is hand-built as a raw dict in three separate places in `artwork.py`. Separately, the `artwork_url` the backend takes care to include is dead weight — the only handler reads `msg.data.album_id` and nothing else.
- **Evidence**:
  ```ts
  // hooks/library/useArtworkUpdates.ts:72-74 — only album_id is read
  if (msg && msg.type === 'artwork_updated' && msg.data && typeof msg.data.album_id === 'number') {
    bumpRevision(msg.data.album_id);
  }
  ```
  `grep -rn "artwork_updated" auralis-web/backend/ --include='*.py'` → three hits, all raw literals in `routers/artwork.py`.
- **Impact**: No runtime breakage today. The shape is enforced only on the receiving side, so a field rename or a new `action` value drifts silently past both the type system and the guards; the three duplicated literals make partial drift the likely failure mode.
- **Suggested Fix**: Build the payload once from a small helper/`TypedDict` so the three call sites share one definition, and either drop `artwork_url` or mark it informational-only in the TS type.

---

## Relationships

Six themes cut across flows. Fixing the theme is generally cheaper than fixing the findings individually.

### R1 — Parallel implementations that miss each other's fixes (5 findings, incl. 3 HIGH)

`INT-F1-1`, `INT-F3-1`, `INT-F3-3`, `INT-F6-1`, and `INT-F5-2` are all the same failure: a second implementation of something that already existed, built against a different plane, which then did not receive the bug fixes applied to the first.

- Two playback control planes (`usePlaybackControl` REST/`play_normal` vs `usePlayEnhanced` WS) — INT-F1-1.
- Two globals dictionaries (`main.py` literal vs `config/globals.py::create_globals_dict()`) — INT-F3-3.
- Two write paths for enhancement settings (runtime dict vs `UserSettings`) that never converge — INT-F3-1.
- Two similarity clients (`useSimilarTracks` vs `similarityService`), where only the first received the abort/race fixes #3616/#3646/#4162 — INT-F6-1.
- A second, independent WebSocket connection in `processingService` — INT-F5-2.

This is the project's **"No variants"** principle (CLAUDE.md §Principles 3) failing in practice. It is the single highest-leverage theme in this report: three of five HIGH findings are instances of it, and in each case the *newer* code is correct while the *older* duplicate is what users actually hit.

### R2 — The case-conversion convention is half-applied (2 findings)

`INT-F2-1` and `INT-F2-2` share one root cause with a ready-made fix already sitting in the tree. `auralis-web/frontend/src/api/transformers/trackTransformer.ts` exports `transformTrack`, `transformTracks`, and `transformTracksResponse` — and a grep shows **zero production callers** outside the transformer package itself. The only real use of `transformTrack` is inside `playlistTransformer.ts`, which is itself orphaned per #4492.

So albums and artists go through their transformers, tracks do not, and the track transformer that would fix both findings is dead code. Wiring it into the two call sites resolves INT-F2-1 and INT-F2-2 together and removes the dead-code finding as a side effect.

### R3 — Wire fields declared on one side and consumed by neither (6 findings, all LOW)

`INT-F1-2` (`crossfade_samples`), `INT-F4-4` (`phase: 'fingerprinting'`), `INT-F5-3` (`preset: "none"`), `INT-F5-4` (`recovery_position`), `INT-F6-5` (`duration`), `INT-F7-5` (`artwork_url` in `artwork_updated`).

Each is individually harmless; collectively they mean the WS/REST type definitions are no longer a reliable description of what the system does. Three sub-shapes: (a) the backend sends a field nobody reads; (b) the frontend types a value the backend cannot produce; (c) the frontend types a value the backend produces but the handler ignores. A single contract-verification pass — the kind `/sync-contracts` is built for — would catch all six and prevent recurrence.

### R4 — Error detail and terminal state lost at the boundary (4 findings)

`INT-F4-2` (no terminal frame on `CancelledError` → UI stuck "Scanning…" forever), `INT-F6-2` (HTTP `detail` discarded across three hooks), `INT-F2-6` (status code discarded), `INT-F6-4` (four distinct causes collapsed into one 404).

The backend consistently produces *good* error information — precise status codes, actionable `detail` strings, a deliberate `recovery_position`. The frontend consistently throws it away at the `!response.ok` boundary. Standardising on the existing `ApiErrorHandler` (`auralis-web/frontend/src/types/api.ts`), which already preserves status and exposes `isNotFound()`/`isServerError()`, addresses three of the four; the fourth is a backend-side missing `except` clause.

### R5 — Runtime state seeded once and never re-synced (4 findings)

`INT-F3-1` (settings seeded at startup only), `INT-F3-3` (globals populated into the wrong dict), `INT-F5-1` (`cache_cleared` never reaches other clients), `INT-F7-3` (palette cache never invalidated).

All four are "the backend changed something and the other side never found out". The codebase already has the right mechanism for this — `useArtworkRevision`'s refcounted WS subscription driving a `useSyncExternalStore` revision counter is a genuinely good pattern — it is just not applied consistently.

### R6 — Unbounded growth (2 findings)

`INT-F2-5` (playlist endpoint has no pagination) and `INT-F7-4` (thumbnail cache has no eviction). Both scale silently with usage and have no user-visible symptom until they are already a problem.

---

## Prioritized Fix Order

Ordered by user-visible impact per unit of work, not strictly by severity.

| # | Finding(s) | Why first |
|---|-----------|-----------|
| 1 | **INT-F1-1** | The spacebar silently kills playback. It is the most-used shortcut in a music player, it is live in the shipped app, and the failure is silent (cancelled, not errored — so no error surfaces). Highest user-visible impact of anything in this report. |
| 2 | **INT-F3-3** | One-line-class fix (make `main.py` use `create_globals_dict()`), and it restores a DSP fast path that is currently dead on every chunk of every enhanced playback. Best impact-to-effort ratio in the report. Also closes the second-`enhancement_settings`-dict trap before anyone falls into it. |
| 3 | **INT-F3-2** | An entire user-facing feature that has never worked. Cheap fix (a) — move the existing `spawn_background_task` call into the real track-load path. |
| 4 | **INT-F2-4, INT-F2-5** | The two findings that degrade with library size. These get worse over time and are invisible on a developer's small test library — exactly the profile that ships broken. |
| 5 | **INT-F2-1, INT-F2-2** (via R2) | One shared fix (wire up the already-written `transformTracks`) closes two MEDIUMs, removes a dead-code liability, and makes the `Track` type contract honest before the next feature is built on top of the lie. |
| 6 | **INT-F6-1** | Retiring the duplicate similarity client removes an active race-condition regression and prevents the next fix from landing in only one of the two copies. |
| 7 | **INT-F4-2, INT-F4-1** | Both leave the scan UI in a wrong state that only a reload clears. `INT-F4-2` (add `except asyncio.CancelledError`) is small; `INT-F4-1` (move the start broadcast) is slightly larger. |
| 8 | **INT-F6-2, INT-F2-6** (via R4) | One shared change — route these four hooks through `ApiErrorHandler` — turns three opaque failures into actionable states, including the very common "track not fingerprinted yet" first-run case. |
| 9 | **INT-F7-2** | Rare but permanent when it hits: a corrupt thumbnail is cached forever. The fix (unique temp filename) is two lines. |
| 10 | **INT-F3-1, INT-F3-4, INT-F3-5, INT-F5-1, INT-F7-1, INT-F7-3, INT-F6-3, INT-F6-4, INT-F4-3** | Remaining MEDIUMs. `INT-F3-1` and `INT-F7-1` are the most user-visible of these (settings silently not applying; artist artwork never rendering). |
| 11 | **All 11 LOW findings** | Best handled as one contract-hygiene sweep (R3) plus opportunistic cleanup, rather than eleven separate changes. `/sync-contracts` covers most of R3 mechanically. |

---

## Deduplication Notes

All 33 findings were checked against the 159 open GitHub issues, `docs/audits/`, and `.claude/issues/`. Every finding above is **NEW**. No regressions of closed issues were found.

Confirmed-existing issues encountered during tracing and deliberately **not** re-reported: #4431 (`total_duration` divergence in seek paths), #3878 (equal-power vs equal-gain crossfade docstring), #3879 (dead crossfade/prefetch code), #3892 (pagination response-shape naming), #3893 (path-int params lack `ge=1`), #3894 (`domain.ts` `PlayerState` snake_case mix), #3838 (missing `response_model`), #3895 (camelCase in presets payload), #4425 (mid-playback preset change re-buffer gap), #4427 (auto-scanner progress divergence), #4429 (`loudness_variation_std` field name), #4470 (`processingService.ts` has no consumers), #4492 (orphaned `playlistTransformer.ts`), #3690, #4239, #4478, #4508, #4510.

Three WebSocket-lifecycle findings from `docs/audits/AUDIT_INTEGRATION_2026-07-12.md` were independently re-verified against current source and found **already fixed** (#4406, #4420, #4421); they are not carried forward.

---

## Next Step

```
/audit-publish docs/audits/AUDIT_INTEGRATION_2026-07-25.md
```
