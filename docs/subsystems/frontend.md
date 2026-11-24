# Subsystem: React Frontend

[`auralis-web/frontend/`](../../auralis-web/frontend/) is the Auralis desktop renderer:
React 18, TypeScript 5.9, Vite 8, Redux Toolkit, MUI 9 and TanStack Query. It renders the
library, drives playback over a WebSocket, and plays streamed PCM audio in the Electron
Chromium process through the Web Audio API. The `@` alias maps to `./src`.

Electron is the only supported interface platform. Vite can serve the same bundle to a browser
for development; in a browser the app shows a "Browser preview" banner
(`src/components/platform/DesktopPlatformNotice.tsx`) and browser, PWA and mobile use is
unsupported.

Scope: app shell, state, hooks, API and WebSocket clients, the design system, and the renderer
audio pipeline. The server it talks to is described in [backend-api.md](backend-api.md); the
wire protocol is in [WEBSOCKET_API.md](../../auralis-web/backend/WEBSOCKET_API.md).

---

## 1. App shell

`src/index.tsx` is the only entry. It pre-imports MUI and Emotion with `Promise.all` before
importing any component that calls `styled(...)` (so Emotion is initialised first), then renders
`ErrorBoundary` → `CssBaseline` + global styles → `App` under `StrictMode`. An init failure
renders a static fatal screen instead of a blank page.

Provider tree (`src/App.tsx`):

```
Redux Provider
└ QueryClientProvider            staleTime 5 min, status-aware retry (utils/queryRetry.ts)
  └ ThemeProvider                MUI theme + --app-* CSS variables, mode persisted in localStorage
    ├ StarfieldBackground        only while the "Show visualizations" setting is on
    └ ToastProvider
      └ WebSocketProvider
        ├ PlayerStateSync        renders null; mounts usePlayerStateSync, useWebSocketErrors,
        │                        useServerRestartNotice, useLibraryChangeSync
        └ PlaybackSessionProvider  the single enhanced-audio session (see section 8)
          └ ComfortableApp
```

There is no router. `src/ComfortableApp.tsx` is the shell and switches views with `useAppNavigation`
local state: `currentView` is `songs`, `albums`, `artists`, `favourites`, or `playlist-<id>` for a
playlist picked in the sidebar. Layout, top to bottom:

- `AppContainer` (wraps the `@hello-pangea/dnd` `DragDropContext`; `useAppDragDrop` handles drops
  onto the queue and playlists) holding `AppSidebar` and a column of `AppTopBar` plus
  `AppMainContent`, which hosts the lazy-loaded `CozyLibraryView`.
- Lazy `SettingsDialog` and `KeyboardShortcutsHelp` dialogs.
- `Player`, the fixed bottom bar, outside the flex layout.

The right-hand `AlbumCharacterPane` is not mounted by the shell. `CozyLibraryView` (Songs and
Favourites) and `LibraryViewRouter` (Albums) pass it to `ViewContainer` as `rightPane`. Artist
and detail views have no pane.

Each region has its own `ErrorBoundary` with a `RegionErrorFallback` (library, settings dialog,
shortcuts dialog, player, and the queue panel inside the player), so one render crash leaves the
rest usable. Boundaries reset on view change (library) or track change (player). Heavy modules
load through `lazyWithRetry` so a failed chunk load can be retried.

Below 900 px (`md`) `AppSidebar` renders `MobileSidebarDrawer` instead of the fixed sidebar;
`useAppLayout` owns the collapse state.

---

## 2. State management

`configureStore` in `src/store/index.ts` registers four slices (`src/store/slices/`). In
development it adds `loggerMiddleware`; `errorTrackingMiddleware` runs in every build.

| Slice | Holds |
|-------|-------|
| `player` | `isPlaying`, `currentTrack`, `currentTime`, `duration`, `volume` (0-100, default 80), `isMuted`, `preset`, and `streaming: { normal, enhanced }`, each a `StreamingInfo` (`state`, `trackId`, `progress`, buffered/processed/total chunks, `error`, `stalled`) |
| `queue` | `tracks`, `currentIndex`, `isShuffled`, `repeatMode` |
| `connection` | `wsConnected`, `apiConnected`, `backendDegraded`, `latency`, reconnect counters, `lastError` |
| `cache` | cache `stats` and `health` |

Selectors live in `src/store/selectors/` (`playerSelectors`, queue selectors).

Responsibilities:

- **Redux** is the single source of truth for playback, queue, connection and cache state. The
  backend's `player_state` snapshot reaches it through `usePlayerStateSync`.
- **React context** carries the theme (`ThemeContext`), the WebSocket connection
  (`WebSocketContext`), toasts, and the playback session (`PlaybackSessionContext`).
- **TanStack Query** caches infinite album pages, fingerprints and cache stats. Track lists use
  the `useLibraryQuery` hook family instead.
- **Local `useState`** holds view mode, search query, dialog flags and sidebar collapse.

Mutating reducers use the `{ reducer, prepare }` form so `meta.timestamp` is stamped once at
dispatch. `setCurrentTime` clamps to `duration`, and `setDuration` re-clamps `currentTime`. The
`streaming` reducers live in `playerStreamingReducers.ts`, so a `player_state` update never
overwrites client-tracked stream progress.

---

## 3. Hooks

Business logic and Redux/WebSocket wiring sit in domain-grouped hooks under
[`src/hooks/`](../../auralis-web/frontend/src/hooks/); components stay presentational.

| Domain | Representative hooks |
|--------|---------------------|
| `player/` | `usePlayerStateSync` (WebSocket to Redux bridge), `usePlayTrack`, `usePlaybackQueue`, `useQueueMutations`, `useServerRestartNotice` |
| `enhancement/` | `usePlayEnhanced` (stream composition), `useAudioStreamingCore`, `useEnhancedStreamStart`, `useEnhancedSeek`, `useEnhancementControl` (optimistic updates with rollback) |
| `library/` | `useLibraryQuery`, `useInfiniteAlbums`, `useLibraryScan`, `useScanProgress`, `useLibraryChangeSync`, `useLibraryWithStats`, `useFingerprintCoverage` |
| `websocket/` | `useWebSocketConnection`, `useWebSocketMessages` (+ `createSharedSubscription`), `useWebSocketErrors`, `useReconnected` |
| `api/` | `useRestAPI` |
| `app/` | `useAppLayout`, `useAppNavigation`, `useAppKeyboard`, `useAppShortcuts`, `useKeyboardShortcuts`, `useAppDragDrop`, `useArtworkPalette` |
| `fingerprint/` | `useTrackFingerprint`, `useAlbumFingerprint`, `useSimilarTracks` |
| `audio/` | `useAudioVisualization` |
| `shared/` | `useAbortableResource`, `useAPIHealthPoll`, `useDialogAccessibility`, `useLatest`, `useShowVisualizations` |

---

## 4. REST layer

Every REST call goes through `src/utils/apiRequest.ts` (`get`, `post`, `put`, `patch`, `del`,
`getOrNullOn404`): a composed `AbortController` with caller-signal forwarding, a 30 s default
timeout, backend `detail` extraction into `APIRequestError`, and optional `validate` shape guards
at the boundary. `src/hooks/api/useRestAPI.ts` wraps it for hooks that need a counter-based
`isLoading`, per-URL sequence numbers that discard stale GET responses, and abort-on-unmount.

Domain modules in `src/services/` (`libraryService`, `playlistService`, `queueService`,
`settingsService`, `artworkService`, `keyboardShortcutsService`, `scanRequestTimeout`) wrap the
endpoints; `src/services/api/cacheShapeGuards.ts` holds the cache-stats types and guards.

`src/config/api.ts`: `API_BASE_URL` is empty (relative URLs) in both modes, served through the
Vite proxy in development and by the backend's own origin in production. `WS_BASE_URL` is the
page's own origin in production and `ws://localhost:<VITE_BACKEND_PORT>` (default 8765) under
`vite dev`, because the Vite WebSocket proxy is unreliable. `VITE_API_URL` and `VITE_WS_URL`
override both. Library-scan requests use `SCAN_TIMEOUT_MS`, not the 30 s default, because
aborting the request stops the scan.

---

## 5. WebSocket client

One connection serves the whole app. The connection state (manager, ref count, last stream
command, pending chunk metadata) is module-level in
`src/hooks/websocket/websocketConnectionState.ts`, and the subscription maps are module-level in
`src/contexts/WebSocketContext.tsx`, so both survive StrictMode double-mounts and provider
remounts. `resetWebSocketSingletons()` clears them for tests.

- **Binary audio frames.** The backend sends an `audio_chunk_meta` JSON frame followed by a raw
  PCM binary frame. `src/hooks/websocket/socketFrameParser.ts` merges the two into one synthetic
  `audio_chunk` message with `pcm_binary`; `audio_chunk_meta` is never dispatched on its own. A
  gap in `audio_chunk_meta.seq` is logged as a desync.
- **Reconnection** is `WebSocketManager` in `src/utils/errorHandling.ts`: delay
  `1000 ms x 2^n` capped at 30 s. The attempt budget is `DEFAULT_MAX_RECONNECT_ATTEMPTS` (10) in
  production and `DEV_MAX_RECONNECT_ATTEMPTS` (3) under `vite dev`, both in
  `src/config/timing.ts`. When the budget is exhausted the manager is retired and
  `connectionStatus` becomes `error`.
- **Stream resumption.** The last `play_enhanced` / `play_normal` command is kept while its
  stream is live and re-sent after a reconnect with `start_position` taken from the resume getter
  the playback hook registers. `reissueActiveStreamAs` re-sends it with new preset or intensity
  when enhancement settings change.
- **Commands** are the `OutgoingCommand` union in `src/types/ws/commands.ts`: `play_enhanced`,
  `play_normal`, `seek`, and the payload-free `pause`, `stop`, `resume`, `buffer_full`,
  `buffer_ready`.
- **Message types** are the `WebSocketMessageType` union in `src/types/ws/registry.ts` (33
  types). A compile-time assertion fails the build if `ALL_MESSAGE_TYPES` omits a member.
  Frontend types must match the backend `schemas/` package.
- **WebSocket to Redux.** `usePlayerStateSync` applies the authoritative `player_state` snapshot
  and discrete events (`position_changed`, `playback_*`, `volume_changed`, `track_changed`) to the
  player and queue slices, guarded so a partial message cannot write `undefined` or `NaN`.

---

## 6. Design system and theming

`src/design-system/tokens/` is the source of truth for design values, merged by
`src/design-system/tokens.ts` into one object and imported as
`import { tokens } from '@/design-system'`. Its categories: `colors`, `typography`, `spacing`,
`borderRadius`, `shadows`, `transitions`, `zIndex`, `breakpoints`, `components`, `gradients`,
`glass`, `animations`. [UI_STYLE_GUIDE.md](../UI_STYLE_GUIDE.md) owns the design rules and token
values; this section covers structure only.

Ten primitives in `src/design-system/primitives/` (`Button`, `IconButton`, `Card`, `Slider`,
`SegmentedControl`, `Chip`, `CircularProgress`, `List`, `Alert`, `Tooltip`) are re-exported from
`@/design-system`. Layout and text use `@mui/material` directly.

Theme-dependent colour goes through `src/theme/semanticTheme.ts`. It maps the dark and light
palettes to one `--app-*` CSS-variable contract. `ThemeProvider` writes the variables on
`document.documentElement`, so MUI, Emotion and plain DOM controls follow the same mode. Components
read `themeVars` (surfaces, text, borders, status) and use `tokens` for spacing, typography,
motion, radii and the fixed audio-semantic colours. The raw `tokens.colors.*` palette is dark-mode
only and is not for direct use in themed surfaces. The theme is chosen in Settings → Interface.

Rules: no hardcoded hex or rgb in components, and `@/` absolute imports only. Guard tests in
`src/theme/__tests__/` and `src/design-system/__tests__/` check theme derivation, that every CSS
custom property a stylesheet reads has a producer, and that no token goes unread; run
`pnpm exec vitest run src/design-system` after deleting components or styles.

---

## 7. Components

Under `src/components/`, grouped by domain: `core/` (shell pieces: `AppContainer`, `AppSidebar`,
`AppTopBar`, `AppMainContent`, `ErrorBoundary`), `layouts/Sidebar/`, `library/` (`CozyLibraryView`,
`Views/`, `Details/`, `Items/`, `Controls/`, `AlbumCharacterPane/`), `player/` (including
`QueuePanel/`), `playlist/`, `settings/`, `shared/` (toasts, context menu, drop zone, dialogs,
`EnhancementToggle`), `navigation/`, `album/`, `track/`, `background/` (`StarfieldBackground`),
`platform/`. Co-located `.styles.ts` files keep JSX small. Keep components under about 300 lines.

---

## 8. Renderer audio pipeline

Playback uses the Web Audio API. There is no `MediaSource` path. `PlaybackSessionProvider`
(`src/contexts/PlaybackSessionContext.tsx`) calls `usePlayEnhanced()` exactly once, so the player
bar, the global keyboard shortcuts and the Album Character pane share one `AudioContext`, buffer
and engine. It exposes two contexts: `usePlaybackControls()` (low frequency: play/pause,
next/previous, seek, volume, mute) and `usePlaybackProgress()` (the position tick).

```
startTrack(trackId)
  enhancement enabled  -> playEnhanced(trackId, preset, intensity)  -> ws.send play_enhanced
  enhancement disabled -> playNormal(trackId)                      -> ws.send play_normal
  (the track row is also fetched over REST in the background so currentTrack is set early)

backend replies
  audio_stream_start -> size a PCMStreamBuffer from the stream length, create an AudioContext
                        at the stream's sample rate, build an AudioPlaybackEngine,
                        dispatch startStreaming
  audio_chunk        -> float32 PCM -> buffer.append -> engine.startPlayback once ~1 s is buffered
  audio_stream_end   -> mark the stream complete; the engine plays out the buffered tail
```

`usePlayEnhanced` composes `useAudioStreamingCore` (buffer, engine and chunk plumbing, including
`audioChunkIngest.ts`), `useEnhancedStreamStart`, `useEnhancedSeek` and `useEnhancedPlayCommand`.
A start watchdog (`useStreamStartWatchdog`) reports a stream that never starts.

- **Wire format.** PCM arrives as raw float32 binary frames, read as a `Float32Array` view
  (`src/utils/audio/pcmDecoding.ts`), interleaved. The backend sends non-overlapping 10 s
  segments, so chunks tile with no crossfade.
- **`PCMStreamBuffer`** (`src/services/audio/PCMStreamBuffer.ts`, ring maths in `pcmRingOps.ts`)
  is a circular `Float32Array` sized from the stream (1.5x the stream's bytes, clamped to 1 MB
  to 100 MB). On overflow it drops new data rather than unplayed audio.
- **Flow control.** `audioChunkIngest.ts` asks the backend to stop sending (`buffer_full`) when the
  ring is above 75 % full and to resume (`buffer_ready`) below 50 %. `flowDrainWatch.ts` sends the
  resume from a timer while paused, because the server sends nothing until told.
- **`AudioPlaybackEngine`** (`src/services/audio/AudioPlaybackEngine.ts`) owns the gain node and
  the global analyser, and delegates to `BufferScheduler` (feeding and buffer health) and
  `PlaybackPositionTracker` (state and position). `BufferScheduler` prefers an `AudioWorkletNode`
  running `public/audio-worklet-processor.js` (`WorkletOutput.ts`) and falls back to a
  `ScriptProcessorNode`. Chain: `worklet -> gainNode -> AnalyserNode -> destination`. The analyser and
  context are published as `window.__auralisAnalyser` and `window.__auralisAudioContext` for
  `useAudioVisualization`.
- **Water marks.** Playback starts after `minBufferSeconds` (1 s), pauses below
  `lowWaterMarkSeconds` (5 s) and resumes above `highWaterMarkSeconds` (8 s). The worklet queue is
  topped up to `workletLookaheadSeconds` (3 s) rather than filled. The low mark stays below the
  backend's 10 s chunk interval, so one late chunk does not stall playback. All constants are in
  `src/services/audio/audioConstants.ts`, and `BACKEND_STREAM_TIMING` there mirrors backend
  values a test keeps in sync.
- **Sample rate.** The `AudioContext` is created at the stream's sample rate and recreated when it
  changes. A mismatch speeds playback up or down and causes underruns.
- **Seek.** `useEnhancedSeek` stops the engine, clears the buffer and sends `seek`; the backend
  restarts streaming from the target with a new `audio_stream_start`. A rejected seek clears
  `isSeeking`, and a rate-limited one is re-sent once. Keyboard seeks on the progress bar are coalesced
  (`useKeyboardSeek`).
- **Cleanup.** Dispose the old buffer before replacing the ref, close the `AudioContext` on
  unmount, and clear timers.

---

## 9. Testing

Vitest 4 with jsdom. Commands, the CI gates and the baselines are in
[TESTING_COMMANDS.md](../frontend/testing/TESTING_COMMANDS.md); `src/test/README.md` covers
writing tests.

- `src/test/setup.ts` mocks `WebSocketContext` globally (a fake connected context). A test that
  needs the real one calls `vi.unmock('../contexts/WebSocketContext')`. It also stubs `matchMedia`
  (desktop viewport by default) and `IntersectionObserver`, swaps jsdom's `Blob` for Node's, runs an
  MSW server, and calls `global.gc()` after each test. A request to `/api/` with no MSW handler fails
  the test.
- `src/test/test-utils.tsx` exports a `render` that wraps Redux (fresh store per test), TanStack
  Query (retries off), `ThemeProvider`, `ToastProvider` and `PlaybackSessionProvider`, with no
  router. `createTestStore(preloadedState)` seeds the four slices from the production reducer map.
- MSW handlers and fixtures: `src/test/mocks/` (`server.ts`, `handlers.ts`, `mockData.ts`).

---

## 10. Conventions

- `@/` absolute imports only.
- Colours and spacing come from `tokens` and `themeVars`.
- Redux is the single source of truth for playback and queue; do not add a second WebSocket-fed
  copy of that state.
- Singletons such as the WebSocket manager are module-level and ref-counted, and WebSocket-derived
  Redux writes are idempotent, so StrictMode double-mounts are safe.
- A new keyboard shortcut goes in `useAppShortcuts`; show a hint only for a key that has a handler there.

Related: [backend-api.md](backend-api.md), [player.md](player.md), [dsp-engine.md](dsp-engine.md),
[../architecture/data-flow.md](../architecture/data-flow.md).
