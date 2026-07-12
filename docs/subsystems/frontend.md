# Subsystem: React Frontend

[`auralis-web/frontend/`](../../auralis-web/frontend/) is the Auralis UI: **React 18 +
TypeScript 5.9 + Vite 7 + Redux Toolkit + MUI 9 + TanStack Query**, ~805 `.ts`/`.tsx` files.
It renders the library, drives playback over WebSocket, and plays streamed PCM audio in the
browser via the Web Audio API. The `@` alias maps to `./src`.

> **Scope.** App shell, state, hooks, API + WebSocket clients, the design system, and the
> browser audio pipeline. For the server it talks to, see [backend-api.md](backend-api.md).

> ⚠️ **Two corrections to older docs (verified against code):**
> 1. **There is no `EnhancementContext`.** Enhancement state lives in hooks
>    (`hooks/enhancement/useEnhancementControl.ts`), not a React context. `src/test/setup.ts`
>    globally mocks **only** `WebSocketContext`. Any claim that "EnhancementContext is
>    auto-mocked" is stale.
> 2. **MSE / `MediaSource` is not used.** The shipped player is the **Web Audio API** with a
>    circular `Float32Array` PCM buffer + `AudioWorkletNode`. The `MSE_*` and
>    `MULTI_TIER_BUFFER_*` guides describe an aspirational design, not the shipped code.

---

## 1. App shell & entry

- **Entry is `src/index.tsx`** (referenced by `index.html`). `src/main.tsx` is a **stale
  duplicate** not referenced anywhere — don't edit it expecting an effect.
- Boot uses an **async IIFE** that pre-imports MUI/emotion via `Promise.all` before importing
  components that use `styled(...)` — a deliberate ordering fix to avoid emotion init crashes.
  Renders under `StrictMode`.
- **Provider tree** ([`App.tsx`](../../auralis-web/frontend/src/App.tsx)):
  `Redux Provider` → `QueryClientProvider` → `ThemeProvider` → `AudioReactiveStarfield` →
  `ToastProvider` → `WebSocketProvider` → `PlayerStateSync` + `ComfortableApp`.
- **No React Router routing in the app shell.** `react-router-dom` is a dependency but
  [`ComfortableApp.tsx`](../../auralis-web/frontend/src/ComfortableApp.tsx) switches views with
  local `useState` (`currentView`: songs/albums/artists/playlists). `BrowserRouter` appears only
  in the test wrapper.
- `ComfortableApp.tsx` is the real shell: `AppContainer`/`AppSidebar`/`AppTopBar`/
  `AppMainContent` layout, lazy-loaded views via `React.lazy` + `Suspense` (#2811), and Library
  and Player each wrapped in their own `ErrorBoundary` (#3583/#3115) so one crash doesn't kill
  the app.

---

## 2. State management

`configureStore` with **four reducers** ([`store/index.ts`](../../auralis-web/frontend/src/store/index.ts)):

| Slice | Holds |
|-------|-------|
| `player` | Playback (`isPlaying`, `currentTrack`, `currentTime`, `duration`, `volume` default 80, `preset`, …) plus nested `streaming: { normal, enhanced }` for A/B |
| `queue` | `tracks`, `currentIndex`, `isShuffled`, `repeatMode` |
| `connection` | `wsConnected`, `apiConnected`, `latency`, `reconnectAttempts` |
| `cache` | Cache stats / health |

**Division of responsibility:**

- **Redux** = playback/queue/cache/connection domain state — the *single source of truth*.
  (`usePlaybackState` was deleted in #3126 to kill a parallel WS-shadow state; don't
  reintroduce one.)
- **React Context** = theme, toasts, and the WebSocket connection (`WebSocketContext`).
- **TanStack Query** = server cache (library/albums fetching), staleTime 5 min.
- **Local `useState`** = view mode, search query, dialog flags, sidebar collapse.

Mutating reducers use the `{reducer, prepare}` form to stamp `meta.timestamp`.
`updatePlaybackState` **deep-merges** `streaming` to avoid clobbering client-tracked progress
(#2352/#3025) and re-clamps `currentTime ≤ duration` (#4191). The slice/selector shape is a
contract — add fields in both places.

---

## 3. Hooks architecture

Business logic and Redux/WS wiring live in domain-grouped hooks under
[`src/hooks/`](../../auralis-web/frontend/src/hooks/); components stay presentational. Each
domain has a barrel `index.ts`.

| Domain | Representative hooks |
|--------|---------------------|
| `player/` | `usePlaybackControl`, `usePlayTrack`, `usePlayerControls`, `usePlayerStateSync` (WS→Redux bridge) |
| `enhancement/` | `usePlayEnhanced`, `usePlayNormal`, `useAudioStreamingCore` (shared core, #4019), `useEnhancementControl` (optimistic UI + rollback), `useMasteringRecommendation` |
| `library/` | `useLibraryQuery`, `useAlbumsQuery`, `useInfiniteAlbums`, `useLibraryScan`, `useScanProgress` (TanStack Query-backed) |
| `websocket/` | `useWebSocketSubscription`, `useWebSocketErrors` (#2874) |
| `api/` | `useRestAPI` + `useQuery`/`useMutation` wrappers |
| `app/` | `useAppLayout`, `useKeyboardShortcuts`, `useArtworkPalette` |
| `fingerprint/` | `useTrackFingerprint`, `useSimilarTracks`, `useFingerprintCache` |
| `shared/` | `useOptimisticUpdate`, `useReduxState`, `useAPIHealthPoll`, `useDialogAccessibility` |

---

## 4. API layer

Two REST paths coexist:

1. **`hooks/api/useRestAPI.ts`** — what most components use. Per-method `get/post/put/…`, 30 s
   timeout via `AbortController`, **counter-based `isLoading`** (`inflightCount`, #2489),
   per-endpoint **sequence counters** to discard stale responses (#2439/#3055), and aborts all
   in-flight requests on unmount (#2467).
2. **`services/api/standardizedAPIClient.ts`** — class-based client for the standardized
   `{status, data, message, cache_source, processing_time_ms}` envelope. Type guards
   (`isSuccessResponse`/…), an LRU response cache (200 entries / 60 s TTL), and **retries only
   idempotent (GET) methods** by default. Singleton via `getAPIClient()`.

Domain service modules (`libraryService`, `playlistService`, `queueService`,
`processingService`, `similarityService`, `artworkService`, …) wrap the endpoints.
[`src/config/api.ts`](../../auralis-web/frontend/src/config/api.ts): `API_BASE_URL` is `''` in
dev (Vite proxy) else `http://localhost:8765`; `WS_BASE_URL` is always
`ws://localhost:8765`.

---

## 5. WebSocket client (`contexts/WebSocketContext.tsx`)

A **single shared connection** built on **module-level singletons** (`singletonWSManager`,
`singletonRefCount`, `singletonSubscriptions`, …) so it survives StrictMode double-mount and
provider remounts. `resetWebSocketSingletons()` exists for tests.

- **Binary audio protocol:** the backend sends an `audio_chunk_meta` JSON text frame (stashed
  in `pendingAudioChunkMeta`), then a raw PCM **binary** frame. The manager merges `pcm_binary`
  into the meta and dispatches a *synthetic* `audio_chunk` message so subscribers see one
  unified message. `audio_chunk_meta` is never dispatched on its own (#3944/#4167).
- **Reconnection** is delegated to `WebSocketManager`
  ([`utils/errorHandling.ts`](../../auralis-web/frontend/src/utils/errorHandling.ts)):
  exponential backoff `1000 × 2^n` capped at 30 s; `maxReconnectAttempts` = 3 in dev, 10 in
  prod. An intentional `disconnect()` nulls `onclose` first to prevent auto-reconnect.
- **Stream resumption:** `singletonLastStreamCommand` (last `play_enhanced`/`play_normal`) is
  re-issued after reconnect with an injected `start_position` (#2385/#3185). Explicit
  `stop`/`pause` clears the saved command so a reconnect doesn't restart stopped playback.
- **WS→Redux bridge:** `usePlayerStateSync` subscribes to the authoritative `player_state`
  snapshot plus discrete events (`position_changed`, `playback_*`, `volume_changed`,
  `track_changed`, #4144) and dispatches to the player + queue slices. Writes are guarded with
  `in`-checks so partial messages can't write `undefined`/`NaN`.
- **Message type registry** ([`types/ws/registry.ts`](../../auralis-web/frontend/src/types/ws/registry.ts)):
  the `WebSocketMessageType` union (34 types) has a **compile-time exhaustiveness assert**.
  Frontend WS types must match backend `schemas.py`.

---

## 6. Design system (`design-system/`)

`tokens` is the **single source of truth**, imported as
`import { tokens } from '@/design-system'`. The former monolith was split into `tokens/*`
(colors, typography, layout, effects, surfaces, semantics) and re-merged in a barrel (#4079).
The palette is a deep blue-black aurora theme (`bg.level0 #0B1020`… accents `primary #7366F0`,
`secondary #47D6FF`); spacing is an 8px grid.

The system ships ~20 primitive components (`design-system/primitives/`: Button, Card, Slider,
Modal, …) re-exported from `design-system/index.ts`.

> **Rule:** no hardcoded hex/rgb — colors and spacing come from `tokens`. **Compliance is
> imperfect:** ~105 literals remain in `components/**` (mostly gradient/visualization values),
> and there's an open convention decision (#4203) on `semantics.ts` token composition. Token
> parity is guarded by `design-system/__tests__/cssVariablesTokenParity.test.ts`.

---

## 7. Components (`components/`)

265 non-test `.tsx` files, domain-grouped: `player/`, `library/` (+ `CozyLibraryView`,
`AlbumCharacterPane`), `enhancement/` + `enhancement-pane/`, `playlist/`, `track/`, `album/`,
`navigation/`, `settings/`, `shared/`, `background/` (AudioReactiveStarfield), `core/` (app
shell: `AppContainer`/`AppSidebar`/`AppTopBar`/`AppMainContent`/`ErrorBoundary`).

Many components use co-located `.styles.ts` files to keep JSX lean.

> **The `<300` line rule is a target, not enforced:** ~10 components exceed it (e.g.
> `Items/albums/CozyAlbumGrid.tsx` at 390, `library/TrackList.tsx` at 388). When you touch an
> oversized component, splitting it into subcomponents + `.styles.ts` is a welcome cleanup.

---

## 8. Browser audio pipeline (the real one)

Playback is **Web Audio API**, not MSE. Flow for enhanced playback
([`hooks/enhancement/usePlayEnhanced.ts`](../../auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts)):

```
playEnhanced(trackId, preset, intensity)
  → REST GET /api/library/tracks/{id}   (set currentTrack, #2258)
  → ws.send({type:'play_enhanced', data:{track_id, preset, intensity}})

backend replies:
  audio_stream_start  → create PCMStreamBuffer + AudioContext (matched to stream sample rate!)
                        + AudioPlaybackEngine; dispatch startStreaming
  audio_chunk (merged binary)  → decodeAudioChunkMessage (Int16→Float32) → append w/ crossfade
  audio_stream_end
```

- **`PCMStreamBuffer`** ([`services/audio/PCMStreamBuffer.ts`](../../auralis-web/frontend/src/services/audio/PCMStreamBuffer.ts))
  — a circular `Float32Array`, default **100 MB** (~5 min @ 44.1k stereo). On overflow it
  **drops new data** rather than discarding unplayed audio (avoids position jumps). Applies a
  linear crossfade blend at chunk boundaries.
- **`AudioPlaybackEngine`** ([`services/audio/AudioPlaybackEngine.ts`](../../auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts))
  — feeds Web Audio, preferring an **`AudioWorkletNode`** (`/audio-worklet-processor.js`,
  off-main-thread) and falling back to `ScriptProcessorNode`. Chain:
  `worklet/script → gainNode → global AnalyserNode → destination`. The analyser and context are
  stashed on `window.__auralisAnalyser` / `window.__auralisAudioContext` for
  `useAudioVisualization`. **Water-mark buffering:** pauses feeding below ~5 s, resumes above
  ~8 s — staying under the backend's 10 s `CHUNK_INTERVAL` so one late chunk doesn't stall.
  Thresholds are centralized in `services/audio/audioConstants.ts` (#4031).

> **Match the AudioContext sample rate to the stream** — a mismatch causes a ~9 % speed error
> and underruns.

**Cleanup discipline (memory):** dispose the ~100 MB buffer before replacing refs (#4147),
`AudioContext.close()` on unmount (#2294), clear fingerprint timers (#2353).

---

## 9. Testing

- **Vitest** (not Jest). Use `npm run test:memory` (2 GB heap) — the full suite OOMs otherwise.
- **`src/test/setup.ts`** globally mocks `WebSocketContext` (a fake connected context). Tests
  needing the real implementation must `vi.unmock('../contexts/WebSocketContext')`. Setup also
  mocks `matchMedia` (defaulting to **desktop** viewport), `IntersectionObserver`, and swaps
  jsdom's incomplete `Blob` for Node's (#3793); it flushes React work and calls `global.gc()`
  per test for memory hygiene.
- **`src/test/test-utils.tsx`** exports `render` wrapping in fresh Redux store /
  QueryClientProvider (retries off) / BrowserRouter / ThemeProvider / ToastProvider.
  `createTestStore(preloadedState)` seeds the four slices. It does **not** wrap any
  EnhancementContext (none exists).

---

## 10. Conventions & gotchas

- **`@/` absolute imports only** — no `../../../`.
- **Colors/spacing from `tokens`** — the ~105 stray literals are debt, not the norm.
- **Redux is the single source of truth** for playback/queue — don't reintroduce WS-shadow
  state (`usePlaybackState` #3126, `usePlayerStreaming` #3776 were deleted).
- **StrictMode double-mount safety** — singletons (like the WS manager) must be module-level and
  ref-counted; WS-derived Redux writes must be idempotent.
- **`main.tsx` is stale drift** — only `index.tsx` is live.
- **Version drift** — `window.__AURALIS_DEBUG__.version` hardcodes an old string; the source of
  truth is [`auralis/version.py`](../../auralis/version.py).
- **Dev WS bypasses the Vite proxy** and hits `ws://localhost:8765/ws` directly; dev REST uses
  relative URLs through the proxy.

**Related:** [backend-api.md](backend-api.md) · [dsp-engine.md](dsp-engine.md) ·
[../architecture/data-flow.md](../architecture/data-flow.md)
