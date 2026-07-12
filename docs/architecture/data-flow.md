# Architecture: Data Flow

This page traces the **three flows** that matter most, end to end, with the file where each
step lives. Read [overview.md](overview.md) first for the layer model.

---

## Flow 1 — Enhanced playback (the hot path)

What happens when a user hits play with enhancement on.

```
┌── FRONTEND ────────────────────────────────────────────────────────────────┐
│ usePlayEnhanced.playEnhanced(trackId, preset, intensity)                    │
│   1. REST GET /api/library/tracks/{id}   → set currentTrack in Redux        │
│   2. ws.send({ type: 'play_enhanced', data:{ track_id, preset, intensity }})│
└──────────────────────────────────────┬─────────────────────────────────────┘
                                        │  WebSocket /ws
┌── BACKEND ─────────────────────────────▼───────────────────────────────────┐
│ ws_handlers dispatch → handle_play_enhanced                                 │
│   → spawn stream_audio task → AudioStreamController.stream_enhanced_audio   │
│   for each chunk N in content_chunk_count(duration):                        │
│     ChunkedAudioProcessor.process_chunk_safe(N)                             │
│       → asyncio.to_thread(_process_chunk_locked)         (frees event loop) │
│         → ProcessorFactory.get_or_create(track,preset,intensity)           │
│           → HybridProcessor.process_realtime_chunk / process()              │
│     → send audio_chunk_meta (JSON)  +  binary PCM frame                     │
└──────────────────────────────────────┬─────────────────────────────────────┘
                                        │  WebSocket frames
┌── FRONTEND ────────────────────────────▼───────────────────────────────────┐
│ WebSocketContext merges pcm_binary into meta → synthetic 'audio_chunk'      │
│   → decodeAudioChunkMessage (Int16 → Float32)                               │
│   → PCMStreamBuffer.write (circular Float32Array, crossfade at boundaries)  │
│   → AudioPlaybackEngine (AudioWorkletNode → gain → analyser → destination)  │
└─────────────────────────────────────────────────────────────────────────────┘
```

Key properties:

- **CPU DSP never blocks the event loop** — every `HybridProcessor.process()` call is wrapped
  in `asyncio.to_thread`, long ones additionally in `asyncio.wait_for(..., timeout)`.
- **One `HybridProcessor` instance per `(track, preset, intensity)`** persists across all
  chunks (via `ProcessorFactory`) so compressor/EQ state doesn't reset at boundaries.
- **Crossfade** uses equal-power sin²/cos² curves; see
  [subsystems/dsp-engine.md §6](../subsystems/dsp-engine.md#6-chunked-streaming-auralis-webbackendcore).
- **The frontend never touches MSE** — it's Web Audio all the way; see
  [subsystems/frontend.md §8](../subsystems/frontend.md#8-browser-audio-pipeline-the-real-one).

---

## Flow 2 — Library scan & fingerprinting (background)

What happens when a folder is scanned.

```
POST /api/library/scan
  → LibraryAutoScanner / scanner walks folders
  → TrackRepository upserts track rows (SQLite, ~/.auralis/library.db)
  → WS broadcast scan_progress → frontend useScanProgress

Meanwhile, background workers (FingerprintExtractionQueue, N daemon threads):
  worker loop:
    Phase 1: claim_next_unfingerprinted_track   (atomic, lufs=-100 sentinel row)
    Phase 2: claim_next_outdated_fingerprint     (version bump → re-extract)
      → FingerprintExtractor.extract_and_store(track):
          1. valid .25d sidecar?          → use it (instant)
          2. Rust gRPC server (port 8766) → native 25D  (primary)
          3. Python analyzer (≤300 MB)    → fallback
      → store TrackFingerprint row + write .25d sidecar
      → (drain) refresh reference cloud, rebuild kNN similarity graph
```

See [subsystems/fingerprinting.md](../subsystems/fingerprinting.md) for the 25 dimensions,
storage formats, and the similarity stack.

---

## Flow 3 — REST browse (the common request)

The everyday "list tracks / open album" path.

```
Frontend hook (useLibraryQuery / useAlbumsQuery, TanStack Query)
  → GET /api/library/tracks  (or /api/albums/{id} …)
  → [middleware] CORS → SecurityHeaders → NoCache → RateLimit
  → router handler (async def)
      → get_repository_factory()()          (DI via get_component lambda)
      → asyncio.to_thread(repos.track.get_page, ...)   (SQLite, selectinload — no N+1)
      → serialize (via response_model where present)
  → JSON → TanStack Query cache → component render
```

Mutations (play, enqueue, toggle enhancement, rename playlist, scan) also **fan out over
WebSocket** via `ConnectionManager.broadcast()`, so every connected client's Redux stays in
sync. This is why the frontend treats `player_state` as authoritative and re-syncs on every
reconnect.

---

## The two state-sync directions

Auralis keeps client and server in sync in **both** directions — understanding which is which
prevents whole classes of bugs:

| Direction | Mechanism | Example |
|-----------|-----------|---------|
| **Client → Server** | REST calls + WS commands | `play_enhanced`, `seek`, `POST /api/playlists` |
| **Server → Client** | WS broadcasts | `player_state`, `position_changed`, `scan_progress`, `job_progress` |

> **Rule of thumb:** the backend is authoritative for playback/queue state. The frontend
> optimistically updates for responsiveness (enhancement toggle, #optimistic rollback) but
> always reconciles to the `player_state` snapshot the backend pushes — including on every
> WebSocket (re)connect.

---

## Related

- [overview.md](overview.md) — the layer model and invariants
- [module-map.md](module-map.md) — where each of these steps lives on disk
- Trace any action yourself with the `trace-flow` skill
