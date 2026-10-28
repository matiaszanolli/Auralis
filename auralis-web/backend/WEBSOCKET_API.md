# WebSocket API Documentation

## Overview

Auralis uses a single WebSocket connection for real-time communication between the backend and frontend. All WebSocket messages follow a consistent structure for easy parsing and type safety.

## Connection

**Endpoint**: `ws://localhost:8765/ws`

**Connection Management**:
- Single WebSocket connection shared across all frontend components
- Automatic reconnection with exponential backoff
- Message queueing during disconnection
- Managed by `WebSocketContext` provider (frontend)

## Message Structure

All WebSocket messages follow this standard structure:

```typescript
{
  "type": string,        // Message type identifier
  "data": object         // Message payload (type-specific)
}
```

## Message Types

### Player State Messages

#### `player_state`
Complete player state snapshot (`PlayerState` in `player_state.py`, typed as
`PlayerStatePayload` in `websocket/outbound_messages.py`).

**Trigger**: every `PlayerStateManager.update_state()`, and once on each
(re)connect. The 1 Hz position tick is the separate `position_changed` message.

**Payload**:
```typescript
{
  "type": "player_state",
  "data": {
    "seq": number,                  // Monotonic; drop snapshots older than the last applied
    "server_instance_id": string,   // Per backend process; a change means the backend
                                    // restarted and the in-memory session was lost (#5487)
    "state": "playing" | "paused" | "stopped" | "loading" | "error",
    "is_playing": boolean,
    "is_paused": boolean,
    "current_track": TrackInfo | null,
    "current_time": number,         // Seconds
    "duration": number,             // Seconds
    "volume": number,               // 0 - 100
    "is_muted": boolean,
    "queue": TrackInfo[],
    "queue_index": number,
    "queue_size": number,
    "shuffle_enabled": boolean,
    "repeat_mode": "off" | "one" | "all",
    "mastering_enabled": boolean,
    "current_preset": "adaptive",
    "analysis": object | null
  }
}
```

#### `playback_started`
Broadcast when playback starts.

**Trigger**: `POST /api/player/play`

**Payload**:
```typescript
{
  "type": "playback_started",
  "data": {
    "state": "playing",
    "seq": number  // monotonic ordering counter, see outbound_messages.py
  }
}
```

#### `playback_paused`
Broadcast when playback is paused.

**Trigger**: `POST /api/player/pause`

**Payload**:
```typescript
{
  "type": "playback_paused",
  "data": {
    "state": "paused",
    "seq": number
  }
}
```

#### `playback_stopped`
Broadcast when playback stops completely.

**Trigger**: `POST /api/player/stop`

**Payload**:
```typescript
{
  "type": "playback_stopped",
  "data": {
    "state": "stopped",
    "seq": number
  }
}
```

#### `track_loaded`
Broadcast when a new track is loaded into the player.

**Trigger**: `POST /api/player/load`

**Payload**:
```typescript
{
  "type": "track_loaded",
  "data": {
    "track_id": number
  }
}
```
<!-- #2479 replaced track_path (server filesystem path leak) with track_id;
     this spec wasn't updated to match at the time (#3809). -->

#### `track_changed`
Broadcast when skipping to next/previous track.

**Trigger**: `POST /api/player/next` or `POST /api/player/previous`

**Payload**:
```typescript
{
  "type": "track_changed",
  "data": {
    "action": "next" | "previous",
    "track_index": number,  // new queue position, so clients can sync immediately
    "seq": number
  }
}
```

#### `position_changed`
Broadcast when playback position is seeked.

**Trigger**: `POST /api/player/seek`

**Payload**:
```typescript
{
  "type": "position_changed",
  "data": {
    "position": number,  // Seconds
    "seq": number
  }
}
```

#### `volume_changed`
Broadcast when volume is adjusted.

**Trigger**: `POST /api/player/volume`

**Payload**:
```typescript
{
  "type": "volume_changed",
  "data": {
    "volume": number,  // 0-100 integer scale (NOT 0.0-1.0)
    "seq": number
  }
}
```

---

### Queue Management Messages

> **Removed: `queue_updated`.** #3492 deleted its emitter; the queue routes
> broadcast `queue_changed` instead. The frontend declarations lingered until
> #4680, and this document described it as live for longer still. Nothing in
> `auralis-web/backend/` emits it — `routers/player.py` and
> `services/queue_service.py` carry only the comments recording the removal.

---

### Library Management Messages

#### `library_updated`
Broadcast when library content changes (scan, import, etc.).

**Triggers**:
- Library scan completion
- Track import
- Metadata updates

**Payload**:
```typescript
{
  "type": "library_updated",
  "data": {
    "action": "scan" | "import" | "update",
    "track_count"?: number,
    "album_count"?: number,
    "artist_count"?: number
  }
}
```

---

### Metadata Messages

#### `metadata_updated`
Broadcast when track metadata is updated.

**Trigger**: `PUT /api/metadata/tracks/{id}`

**Payload**:
```typescript
{
  "type": "metadata_updated",
  "data": {
    "track_id": number,
    "updated_fields": string[]  // e.g., ["title", "artist", "album"]
  }
}
```

#### `metadata_batch_updated`
Broadcast when multiple tracks are updated in a batch operation.

**Trigger**: `POST /api/metadata/batch`

**Payload**:
```typescript
{
  "type": "metadata_batch_updated",
  "data": {
    "track_ids": number[],
    "count": number
  }
}
```

---

### Playlist Messages

#### `playlist_created`
Broadcast when a new playlist is created.

**Trigger**: `POST /api/playlists`

**Payload**:
```typescript
{
  "type": "playlist_created",
  "data": {
    "playlist_id": number,
    "name": string
  }
}
```

#### `playlist_updated`
Broadcast when a playlist is modified.

**Triggers**:
- `PUT /api/playlists/{id}`
- `POST /api/playlists/{id}/tracks`
- `DELETE /api/playlists/{id}/tracks/{track_id}`

**Payload**:
```typescript
{
  "type": "playlist_updated",
  "data": {
    "playlist_id": number,
    "action": "renamed" | "track_added" | "track_removed" | "reordered"
  }
}
```

#### `playlist_deleted`
Broadcast when a playlist is deleted.

**Trigger**: `DELETE /api/playlists/{id}`

**Payload**:
```typescript
{
  "type": "playlist_deleted",
  "data": {
    "playlist_id": number
  }
}
```

---

### Enhancement/Processing Messages

#### `enhancement_settings_changed`
Broadcast when audio enhancement settings are updated.

**Triggers**:
- `PUT /api/enhancement/settings`
- Preset change
- Intensity change

**Payload**:
```typescript
{
  "type": "enhancement_settings_changed",
  "data": {
    "enabled": boolean,
    "preset": string,
    "intensity": number  // 0.0 - 1.0
  }
}
```

#### `mastering_recommendation`
Broadcast when a mastering profile recommendation is generated for the current track.

This message contains weighted profile information for hybrid mastering scenarios.

**Trigger**: When track loads or `GET /api/player/mastering/recommendation/{track_id}` completes

**Payload**:
```typescript
{
  "type": "mastering_recommendation",
  "data": {
    "track_id": number,
    "primary_profile_id": string,
    "primary_profile_name": string,
    "confidence_score": number,          // 0.0 - 1.0
    "predicted_loudness_change": number, // dB
    "predicted_crest_change": number,    // dB
    "predicted_centroid_change": number, // Hz
    "weighted_profiles": [
      {
        "profile_id": string,
        "profile_name": string,
        "weight": number  // 0.0 - 1.0, sum of all weights = 1.0
      }
      // Only present if hybrid/blended recommendation
    ],
    "reasoning": string,
    "is_hybrid": boolean  // True if weighted_profiles present and non-empty
  }
}
```

**Example (Hybrid Mastering)**:
```json
{
  "type": "mastering_recommendation",
  "data": {
    "track_id": 42,
    "primary_profile_id": "bright-masters-spectral-v1",
    "primary_profile_name": "Bright Masters - High-Frequency Emphasis",
    "confidence_score": 0.21,
    "predicted_loudness_change": -1.06,
    "predicted_crest_change": 1.47,
    "predicted_centroid_change": 22.7,
    "weighted_profiles": [
      {
        "profile_id": "bright-masters-spectral-v1",
        "profile_name": "Bright Masters - High-Frequency Emphasis",
        "weight": 0.43
      },
      {
        "profile_id": "hires-masters-modernization-v1",
        "profile_name": "Hi-Res Masters - Modernization with Expansion",
        "weight": 0.31
      },
      {
        "profile_id": "damaged-studio-restoration-v1",
        "profile_name": "Damaged Studio - Restoration",
        "weight": 0.26
      }
    ],
    "reasoning": "Hybrid mastering detected (low single-profile confidence: 21%) → Blend: Bright Masters(43%) + Hi-Res Masters(31%) + Damaged Studio(26%)",
    "is_hybrid": true
  }
}
```

---

### Audio Streaming Messages (Server → Client)

These four messages form the core audio streaming protocol. They are emitted in response to `play_enhanced` / `play_normal` WebSocket commands — not REST calls. See `core/audio_stream_controller.py` for the Python implementation and `src/types/ws/streaming.ts` for the canonical TypeScript types.

#### `audio_stream_start`
Sent once at the beginning of every stream (including seeks/resumes).

**Triggers**: `play_enhanced` or `play_normal` WebSocket command; also emitted on seek/reconnect-resume with `is_seek: true`.

**Payload**:
```typescript
{
  "type": "audio_stream_start",
  "data": {
    "track_id": number,
    "preset": string,          // Enhancement preset name
    "intensity": number,       // 0.0 – 1.0
    "sample_rate": number,     // e.g. 44100
    "channels": number,        // 1 (mono) or 2 (stereo)
    "total_chunks": number,    // Total 15-second chunks in the stream (10s new-content interval, 5s crossfade overlap)
    "chunk_duration": number,  // Seconds per chunk (15.0 — see backend/core/chunk_boundaries.py CHUNK_DURATION, the source of truth)
    "total_duration": number,  // Track duration in seconds
    "stream_type"?: "enhanced" | "normal",
    // Seek/resume fields — only present when is_seek is true:
    "is_seek"?: boolean,
    "start_chunk"?: number,    // Index of first chunk being sent
    "seek_position"?: number,  // Absolute playback position (seconds)
    "seek_offset"?: number     // Offset within the starting chunk (seconds)
  }
}
```

**Client behaviour**: On `is_seek: true`, the client should preserve the existing `AudioContext` and `PCMStreamBuffer` rather than recreating them (seek/reconnect resume path).

---

#### `audio_chunk_meta`
Sent as a **text JSON frame** immediately before each binary PCM frame. The client pairs the two frames to reconstruct audio.

**Wire protocol**: for each audio frame the server sends:
1. `audio_chunk_meta` as a JSON text frame (this message)
2. A binary WebSocket frame containing little-endian `float32` PCM samples

**Payload**:
```typescript
{
  "type": "audio_chunk_meta",
  "data": {
    "seq": number,              // Monotonic per-stream counter (0-based). Increments by 1 per frame.
                                // Clients can detect dropped/reordered frames when seq jumps.
    "track_id"?: number,        // Owning track — lets a client drop late chunk-progress from a
                                // superseded track after a rapid skip.
    "stream_epoch"?: number,    // Owning stream epoch. A new stream (seek/track change) allocates a
                                // new epoch — `seq` is only comparable within the same epoch; see
                                // the desync note below.
    "chunk_index": number,      // Which 15-second chunk this frame belongs to (0-based)
    "chunk_count": number,      // Total chunks in stream (same as audio_stream_start.total_chunks)
    "frame_index": number,      // Frame index within the current chunk (0-based)
    "frame_count": number,      // Total frames in the current chunk
    "sample_count": number,     // Number of float32 samples in the following binary frame
    "stream_type"?: "enhanced" | "normal"
  }
}
```

**Binary frame format**: `sample_count × 4` bytes of little-endian `float32` values, interleaved stereo if `channels == 2` (L0 R0 L1 R1 …).

**Frontend note**: `WebSocketContext` automatically fuses the `audio_chunk_meta` text frame and the following binary frame into a synthetic `audio_chunk` event (with `pcm_binary` populated) for downstream consumers.

**Desync detection (#3774)**: `websocketConnectionCore.handleSocketFrame` tracks the expected `seq` per `stream_epoch`, resetting the counter whenever `stream_epoch` changes (a new stream — seek or track change — legitimately restarts `seq` at 0). A gap (skipped or reordered `seq` within the same epoch) logs a `console.warn` and dispatches a synthetic `audio_stream_error` (`code: "DESYNC"`) through the same handling path a server-detected stream error already goes through, so a dropped/reordered WS frame surfaces as a visible error + stream cleanup instead of silently pairing the wrong PCM with the wrong metadata.

---

#### `audio_stream_end`
Sent once when all chunks have been streamed.

**Payload**:
```typescript
{
  "type": "audio_stream_end",
  "data": {
    "track_id": number,
    "total_samples": number,  // Total float32 samples sent across the entire stream
    "duration": number,       // Actual streamed duration in seconds
    "stream_type"?: "enhanced" | "normal"
  }
}
```

---

#### `audio_stream_error`
Sent when the backend encounters an unrecoverable streaming error.

**Payload**:
```typescript
{
  "type": "audio_stream_error",
  "data": {
    "track_id": number,
    "error": string,           // Human-readable error description
    "code": string,            // Machine-readable code for frontend recovery logic
                               // Default: "STREAMING_ERROR"
    "stream_type"?: "enhanced" | "normal",
    "recovery_position"?: number  // Seconds offset at which the client may seek/retry.
                                  // Set when a specific chunk fails so the client can
                                  // offer a "retry from here" action.
  }
}
```

**Common error codes**: `STREAMING_ERROR`, `TRACK_NOT_FOUND`, `DSP_ERROR`, `ENCODING_ERROR`.

---

### Artwork Messages

#### `artwork_updated`
Broadcast when album/track artwork is updated.

**Triggers**:
- `POST /api/artwork/album/{id}`
- `POST /api/artwork/track/{id}`
- Automatic artwork fetch

**Payload**:
```typescript
{
  "type": "artwork_updated",
  "data": {
    "type": "album" | "track",
    "id": number,
    "artwork_url": string
  }
}
```

---

### System Messages

#### `scan_progress`
Broadcast during library scanning operations.

**Trigger**: Background scan task

**Payload**:
```typescript
{
  "type": "scan_progress",
  "data": {
    "current": number,      // Files processed
    "total": number,         // Total files
    "percentage": number,    // 0-100
    "current_file"?: string
  }
}
```

#### `scan_complete`
Broadcast when library scan finishes. A scan that aborted on an unexpected
error sends `library_scan_error` instead (#5877).

**Trigger**: Scan completion

**Payload** (`ScanCompletePayload` in `websocket/outbound/library.py`):
```typescript
{
  "type": "scan_complete",
  "data": {
    "files_processed": number,
    "files_added": number,
    "files_updated": number,
    "files_skipped": number,
    "files_failed": number,
    "failures": { "filename": string, "reason": string }[],          // capped
    "directory_errors": { "filename": string, "reason": string }[],  // unreadable folders (#5877)
    "duration": number,  // Seconds
    "directories_scanned": number
  }
}
```

---

### Additional Server → Client Messages

The following message types are also broadcast by the backend. Payload shapes
are the canonical frontend interfaces in `auralis-web/frontend/src/types/ws/`
(snake_case is emitted; some carry camelCase fallbacks for legacy consumers).

#### `playback_resumed`
Broadcast when playback resumes from pause. `{ "data": { "state": "playing" } }`

#### `seek_started`
Broadcast when a seek begins. `{ "data": { "position": number /* seconds */, "track_id?": number } }`

#### `queue_changed`
Broadcast when the queue is mutated. `{ "data": { "tracks": TrackInfo[], "current_index?": number, "action?": "added" | "removed" | "reordered" | "shuffled" | "unshuffled" | "cleared" | "undo" } }`

#### `queue_shuffled`
Broadcast when shuffle is toggled. `{ "data": { "is_shuffled?": boolean, "tracks?": TrackInfo[] /* reordered queue */ } }`

#### `repeat_mode_changed`
Broadcast when repeat mode changes. `{ "data": { "repeat_mode?": "off" | "all" | "one" } }`

#### `library_scan_started`
Broadcast when a library scan starts. `{ "data": { "directories": string[] } }`

#### `library_scan_error`
Broadcast when a library scan fails. `{ "data": { "error": string } }`

#### `library_tracks_removed`
Broadcast when tracks are removed from the library. `{ "data": { "count": number } }`

#### `cache_cleared`
Broadcast by `POST /api/cache/clear` (`routers/cache_streamlined.py`) after both
cache tiers are dropped. `{ "data": { "message": string } }`

#### `fingerprint_progress`
Broadcast by `audio_stream_controller.py` while computing a track fingerprint.
`{ "data": { "track_id": number, "status": "analyzing" | "complete" | "failed" | "error" | "cached" | "queued", "message": string, "stream_type?": "enhanced" | "normal" } }`

#### `audio_chunk`
Server → client audio chunk message on the streaming path (the metadata sibling
of the binary audio frames; see "Audio Streaming Messages" above).

#### `error`
Generic error envelope (top-level fields, not under `data`).
`{ "type": "error", "error": string /* e.g. "rate_limit_exceeded" */, "message": string, "timestamp?": string }`

---

## Client → Server Commands

These messages are sent **from the frontend to the backend** to control audio
streaming over the WebSocket.

#### `play_enhanced`

Request enhanced (auto-mastered) audio streaming for a track.

**Payload**:
```typescript
{
  "type": "play_enhanced",
  "data": {
    "track_id": number,          // Required. Positive integer.
    "preset"?: string,           // Optional. Only 'adaptive' is valid — see VALID_PRESETS in schemas/enhancement.py.
    "intensity"?: number,        // Optional. 0.0 - 1.0.
    "start_position"?: number,   // Optional. Resume offset in seconds (WS reconnect).
    "force"?: boolean            // Optional. Default false. See precedence below.
  }
}
```

**Precedence rules**:
- `preset` / `intensity`: **client-sent values are primary**; any missing or invalid
  value falls back to the stored enhancement settings (#2256).
- `enabled` (global auto-mastering toggle): the **stored** setting governs by default.
  If global enhancement is disabled, `play_enhanced` is rejected with an
  `audio_stream_error` whose `code` is `ENHANCEMENT_DISABLED`.
- `force: true` overrides the stored `enabled` gate — an explicit `play_enhanced`
  request is honored even when global enhancement is toggled off (#3773). Intended for
  programmatic / A-B / scripted flows. The UI leaves `force` unset, so the enhancement
  panel toggle still gates normal playback.

#### `play_normal`

Request unprocessed (original) audio streaming for a track. Always allowed regardless of
the stored `enabled` flag — it performs no DSP processing, so there is no enhancement
gate to apply.

**Payload**:
```typescript
{
  "type": "play_normal",
  "data": {
    "track_id": number,          // Required. Positive integer.
    "start_position"?: number    // Optional. Resume offset in seconds (WS reconnect).
  }
}
```

The remaining routed commands (`ws_handlers/connection.py` `dispatch_message`
is the authoritative router). Everything below takes **no `data` payload**
unless shown; every control frame is rate-limited like the play commands.

#### `pause`

Pause the active stream. Responds `playback_paused` with
`{ "state": "paused", "seq": number }`.

#### `resume`

Resume a paused stream. Responds `playback_resumed` with
`{ "state": "playing", "seq": number }`.

#### `stop`

Cancel the active streaming task and clear the connection's stream state.
Responds `playback_stopped` with `{ "state": "stopped", "seq": number }`
after the cancelled task has quiesced.

#### `seek`

Scrub the active stream to a new offset. Payload:

```typescript
{
  "type": "seek",
  "data": {
    "track_id": number,     // Required. Positive integer.
    "position": number,     // Required. Seconds, >= 0, finite.
    "preset"?: string,      // Optional. 'adaptive' only; invalid values fall back
                            // to the connection's stream settings, then the stored
                            // settings — seek degrades, it does not reject (#4600).
    "intensity"?: number    // Optional. 0.0 - 1.0. Same fallback order as preset.
  }
}
```

Acknowledges with `seek_started` `{ "track_id": number, "position": number }`,
then re-issues the stream frames from the new position (`audio_stream_start` →
chunks → `audio_stream_end`).

#### `buffer_full` / `buffer_ready`

Client-side flow control: `buffer_full` pauses the server's chunk delivery,
`buffer_ready` resumes it. No payload, no response frame.

#### `ping`

Client-initiated liveness probe. Responds `{ "type": "pong" }` and marks the
connection alive. Does **not** clear a server-issued pending ping (#3866) — use
`pong` for that.

#### `pong`

Answers a server-issued `ping`, clearing its pending-pong slot. No response.
The server force-closes the connection (~60 s) if a pending ping is never
cleared.

#### `heartbeat`

Liveness keepalive only. Marks the connection alive but, like `ping`, never
clears a pending server ping (#3866 / #4406).

---

## Frontend Usage

### TypeScript Interfaces

```typescript
// Core message type
interface WebSocketMessage {
  type: string;
  data: any;
}

// Player state and track shapes are deliberately NOT reproduced here: a
// hand-copied camelCase "PlayerState" used to live in this section and was
// fictitious — the wire payload is snake_case with `seq`/`state`/`current_time`
// and a 0-100 `volume` (#5476). Consume the canonical types instead, both
// re-exported through the src/types/websocket.ts barrel:
//   - RawPlayerStateData — src/types/ws/player.ts (matches PlayerStatePayload
//     in websocket/outbound_messages.py)
//   - TrackInfo          — src/types/ws/base.ts
```

### Subscription Example

`WebSocketContext.subscribe` takes a **single** message type and returns an
unsubscribe function; `subscribeAll` receives every message.

```typescript
import { useWebSocketContext } from '../contexts/WebSocketContext';

function MyComponent() {
  const { subscribe, subscribeAll } = useWebSocketContext();

  useEffect(() => {
    // Subscribe to one message type
    const unsubscribe = subscribe('playback_started', (message) => {
      console.log(`Playback started: ${message.data.state}`);
    });

    // Or tap every message (debugging, logging)
    const unsubscribeAll = subscribeAll((message) => {
      console.log('[WS]', message);
    });

    // Cleanup on unmount
    return () => { unsubscribe(); unsubscribeAll(); };
  }, [subscribe, subscribeAll]);
}
```

---

## REST Endpoint → WebSocket Message Mapping

| REST Endpoint | WebSocket Message | Notes |
|--------------|-------------------|-------|
| `POST /api/player/play` | `playback_started` |
| `POST /api/player/pause` | `playback_paused` |
| `POST /api/player/stop` | `playback_stopped` | ✅ |
| `POST /api/player/load` | `track_loaded` | ✅ |
| `POST /api/player/seek` | `position_changed` | ✅ |
| `POST /api/player/volume` | `volume_changed` | ✅ |
| `POST /api/player/next` | `track_changed` | ✅ |
| `POST /api/player/previous` | `track_changed` | ✅ |
| `POST /api/player/queue/*` | `queue_changed`, `queue_shuffled`, `repeat_mode_changed` | ✅ |
| `POST /api/playlists` | `playlist_created` | ✅ |
| `PUT /api/playlists/{id}` | `playlist_updated` | ✅ |
| `DELETE /api/playlists/{id}` | `playlist_deleted` | ✅ |
| `PUT /api/enhancement/settings` | `enhancement_settings_changed` | ✅ |
| `POST /api/artwork/*` | `artwork_updated` | ✅ |
| `POST /api/library/scan` | `scan_progress`, `scan_complete` | ✅ |
| WS: `play_enhanced` command | `audio_stream_start` → N×(`audio_chunk_meta` + binary) → `audio_stream_end` | Binary-frame protocol |
| WS: `play_normal` command | `audio_stream_start` → N×(`audio_chunk_meta` + binary) → `audio_stream_end` | Binary-frame protocol |
| WS: any streaming error | `audio_stream_error` | Optional `recovery_position` |

---

## Connection Manager Implementation

**Location**: [auralis-web/backend/config/globals.py](config/globals.py)

**Key Methods**:
- `connect(websocket)` - Register new WebSocket connection
- `disconnect(websocket)` - Remove WebSocket connection
- `broadcast(message)` - Send message to all connected clients

All backend→client traffic is broadcast-shaped; there is no per-client send
surface (a targeted delivery is a broadcast the other clients ignore).

**Concurrency**: Thread-safe with asyncio locks

---

## Debugging Tips

### Watch Every Message

**Frontend** (browser console or a scratch component):
```javascript
// subscribeAll receives every message, unlike subscribe (one type)
const { subscribeAll } = useWebSocketContext();
const unsubscribe = subscribeAll((msg) => console.log('[WS]', msg));
```

**Backend**: WebSocket lifecycle and dispatch log under the module loggers
(`ws_handlers.*`, `websocket.*`); turn up the root `auralis` logger to DEBUG
in `main.py` and watch the server's own stdout — there is no dedicated
websocket log file.

---

## TypeScript Type Definitions

Complete TypeScript types for all WebSocket messages are available in:

**Frontend**: [auralis-web/frontend/src/types/websocket.ts](../frontend/src/types/websocket.ts) — a barrel re-export (#4081); the canonical source is [`auralis-web/frontend/src/types/ws/registry.ts`](../frontend/src/types/ws/registry.ts)

The complete `WebSocketMessageType` union (34 members) is reproduced here for quick reference. This block is hand-maintained and has drifted from the real union before (#4991); `tests/backend/test_ws_type_registry_drift_4680.py` now checks it against both the backend's emitted literals and `registry.ts`, so a stale copy fails CI rather than misleading the next reader. Note `audio_chunk_meta` is intentionally excluded from this union — it's a JSON text frame fused with the following binary frame into a synthetic `audio_chunk` event by `WebSocketContext` before reaching consumers (see `ws/streaming.ts`):

```typescript
export type WebSocketMessageType =
  // Player state messages
  | 'player_state'
  | 'playback_started'
  | 'playback_paused'
  | 'playback_resumed'
  | 'playback_stopped'
  | 'track_loaded'
  | 'track_changed'
  | 'position_changed'
  | 'volume_changed'
  // Queue messages
  | 'queue_changed'
  | 'queue_shuffled'
  | 'repeat_mode_changed'
  // Library messages
  | 'library_updated'
  // Metadata messages
  | 'metadata_updated'
  | 'metadata_batch_updated'
  // Playlist messages
  | 'playlist_created'
  | 'playlist_updated'
  | 'playlist_deleted'
  // Enhancement messages
  | 'enhancement_settings_changed'
  | 'mastering_recommendation'
  // Artwork messages
  | 'artwork_updated'
  // Fingerprint messages
  | 'fingerprint_progress'
  // Seek acknowledgement
  | 'seek_started'
  // Audio stream lifecycle messages
  | 'audio_stream_start'
  | 'audio_stream_end'
  | 'audio_chunk'
  | 'audio_stream_error'
  // System messages
  | 'scan_progress'
  | 'scan_complete'
  | 'library_scan_started'
  | 'library_scan_error'
  | 'library_tracks_removed'
  | 'cache_cleared'
  // Error messages
  | 'error';
```

### Message Type Summary

| Category | Types |
|----------|-------|
| Player state | `player_state`, `playback_started`, `playback_paused`, `playback_resumed`, `playback_stopped`, `track_loaded`, `track_changed`, `position_changed`, `volume_changed` |
| Queue | `queue_changed`, `queue_shuffled`, `repeat_mode_changed` |
| Library | `library_updated`, `library_scan_started`, `library_scan_error`, `library_tracks_removed` |
| System | `cache_cleared` |
| Metadata | `metadata_updated`, `metadata_batch_updated` |
| Playlists | `playlist_created`, `playlist_updated`, `playlist_deleted` |
| Enhancement | `enhancement_settings_changed`, `mastering_recommendation` |
| Artwork | `artwork_updated` |
| Fingerprint | `fingerprint_progress` |
| Seek | `seek_started` |
| Audio streaming | `audio_stream_start`, `audio_chunk`, `audio_stream_end`, `audio_stream_error` (`audio_chunk_meta` is a wire-level text frame, not part of this TS union — see note above) |
| Scan | `scan_progress`, `scan_complete` |
| Errors | `error` |

---

**For questions or updates, see**:
- [Architecture Overview](../../ARCHITECTURE.md)
- [Development Roadmap](../../docs/MASTER_ROADMAP.md)
