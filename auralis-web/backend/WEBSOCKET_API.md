# WebSocket API

One WebSocket, `ws://localhost:8765/ws`, carries all real-time traffic: state
sync, library and playlist events, and the binary PCM audio stream. The
endpoint is `routers/system.py::websocket_endpoint`; per-type handling lives in
`ws_handlers/`. The REST surface is in
[backend-api.md](../../docs/subsystems/backend-api.md); runtime limits and
their environment overrides are in [CONFIG.md](CONFIG.md).

## Envelope

Every server frame is a JSON text frame `{ "type": string, "data": object }`,
except the `error` envelope (top-level fields) and the bare `ping` / `pong`
control frames. Client frames use the same `{type, data}` shape; `data` is
optional for commands that take none. `WebSocketMessageBase`
(`schemas/websocket.py`) allows extra top-level fields and rejects any `type`
that is not a `WebSocketMessageType` member.

All broadcasts go through `websocket/outbound_messages.py::broadcast_typed`,
whose overloads tie each type to one `TypedDict` in `websocket/outbound/`
(`player.py`, `queue.py`, `library.py`, `enhancement.py`). The matching
TypeScript types are in
[`src/types/ws/`](../frontend/src/types/ws/registry.ts).
`tests/backend/test_ws_type_registry_drift_4680.py` fails if the backend's
emitted types, the frontend registry, or the union reproduced at the end of
this file drift apart.

## Connection lifecycle

1. **Admission** (`websocket/connection_manager.py::ConnectionManager.connect`).
   - A non-empty `Origin` must be in `ALLOWED_WS_ORIGINS`: `http`, `https`,
     `ws`, `wss` over `localhost` and `127.0.0.1` at the backend port (plus the
     Vite dev ports 3000-3006 in dev mode only). Built once at import from
     `config/origins.py`, the same host/port matrix CORS uses.
   - An empty `Origin` is accepted only from a loopback peer address.
   - Rejection completes the handshake and closes with **1008** so the client
     sees a policy close rather than a bare 1006.
   - At most `WS_MAX_CONNECTIONS` (16) connections; the 17th is closed with
     **1013**.
2. **Initial sync.** Straight after accept the server sends
   `enhancement_settings_changed` and a `player_state` snapshot, so a
   reconnecting client resyncs without waiting for the next broadcast. Handle
   both idempotently.
3. **Heartbeat** (`ws_handlers/connection.py::run_heartbeat_loop`). The server
   sends `{"type":"ping"}` every 30 s. A pending ping not answered by `pong`
   within 10 s closes the socket with **1001** (`Heartbeat timeout`).
4. **Receive loop.** Every inbound frame is validated, rate-limited, then
   dispatched by `ws_handlers/connection.py::dispatch_message`. A handler
   exception is reported as an `internal_error` frame naming the command; the
   connection stays open.
5. **Broadcast delivery.** `ConnectionManager.broadcast` sends to all clients
   concurrently with a 2 s per-client timeout. A client that errors or times
   out is dropped and closed with **1013**; its reconnect resyncs through
   step 2. There is no per-client send surface: backend-to-client traffic is
   either a broadcast or a direct reply to the sender (marked below).

The frontend side is `WebSocketContext` (single shared connection,
reconnection with backoff, message queueing while disconnected).

## Inbound validation and limits

Applied in order by `routers/system.py::websocket_endpoint`; limits are in
`config/limits.py`.

| Check | Rule | On failure |
|---|---|---|
| Transport frame size | `WS_MAX_MESSAGE_SIZE` = 64 KiB (`ws_max_size` on uvicorn) | connection closed by the transport |
| Frame kind | text only | `error` / `unsupported_frame_type` |
| Message size | UTF-8 length at most 64 KiB | `error` / `message_too_large` |
| JSON nesting | at most 32 levels (`MAX_JSON_DEPTH`) | `error` / `message_too_complex` |
| JSON syntax | must parse | `error` / `invalid_json` |
| Schema | `type` must be a `WebSocketMessageType` member | `error` / `validation_error` |
| Per-connection rate | 10 messages per 1 s window | `error` / `rate_limit_exceeded`, `command` = the rejected type |
| Per-client-IP rate | 30 messages per 1 s window (3x per-connection), survives reconnects | same |
| `ping` | own budget, 5 per second | dropped silently |

- Exempt from the main rate limit: `pong`, `heartbeat`, `buffer_full`,
  `buffer_ready`. A rate-limited `pong` would let the heartbeat close a healthy
  connection; a dropped `buffer_ready` would park the stream.
- A frame rejected before dispatch is itself charged to the per-connection
  limiter; once that is exhausted the rejection is dropped with no reply, so a
  bad-frame flood cannot become a free request/response loop.
- `WebSocketMessageType` also lists some server-to-client types
  (`seek_started`, `playback_*`, `player_state`, ...). They pass validation if a
  client sends them and are then answered with `unknown_message_type`.
- Per-command `data` is not schema-validated; each handler checks its own
  fields (below).

### `error` frame

```typescript
{
  "type": "error",
  "error": string,        // code, see below
  "message": string,      // human-readable, never echoes client-controlled text
  "command": string | null, // type of the rejected client message, null if none was parsed
  "timestamp": string     // ISO-8601 UTC
}
```

Codes: `unsupported_frame_type`, `message_too_large`, `message_too_complex`,
`invalid_json`, `validation_error`, `rate_limit_exceeded`,
`unknown_message_type`, `internal_error`, and from the play/seek handlers
`invalid_track_id`, `invalid_start_position`, `invalid_force`,
`invalid_seek_position`, `invalid_preset`. A client uses `command` to roll back
optimistic state (for example a rejected `seek`).

## Client to server commands

Control commands take no `data` unless shown.

### `play_enhanced`

```typescript
{ "type": "play_enhanced", "data": {
    "track_id": number,        // required, positive integer
    "preset"?: string,         // only "adaptive" is valid (schemas/enhancement.py VALID_PRESETS)
    "intensity"?: number,      // 0.0 - 1.0, finite
    "start_position"?: number, // seconds; resume offset after a reconnect
    "force"?: boolean          // default false
} }
```

- `preset` / `intensity`: a valid client value wins; a missing or invalid one
  falls back to this connection's last stream settings, then the stored
  enhancement settings, then the defaults. Invalid values degrade, they do not
  reject.
- Accepted values are written back into the shared enhancement settings.
- If enhancement is disabled and `force` is not `true`, the reply is
  `audio_stream_error` with code `ENHANCEMENT_DISABLED`. `force: true` bypasses
  that gate for scripted and A/B flows; the UI leaves it unset.
- Any prior stream on the connection is cancelled first; the newest command
  always wins, including a re-issue for the same track.
- Starts a background task that emits the stream described under
  [Audio streaming](#audio-streaming).

### `play_normal`

```typescript
{ "type": "play_normal", "data": {
    "track_id": number,        // required, positive integer
    "start_position"?: number  // seconds
} }
```

Unprocessed audio. Never gated by the enhancement toggle.

### `seek`

```typescript
{ "type": "seek", "data": {
    "track_id": number,     // required, positive integer
    "position": number,     // required, seconds, finite and >= 0
    "preset"?: string,      // same fallback rules as play_enhanced
    "intensity"?: number
} }
```

Cancels the running stream, replies `seek_started`, then restarts the stream
from the new position (`audio_stream_start` with `is_seek: true`, chunks,
`audio_stream_end`). A position at or past the end is clamped back so audible
audio remains. A Settings change made after the stream began takes precedence
over the connection's older snapshot.

### `pause` / `resume` / `stop`

Direct replies to the sender (not broadcast):

| Command | Effect | Reply |
|---|---|---|
| `pause` | holds chunk delivery | `playback_paused` |
| `resume` | releases it | `playback_resumed` |
| `stop` | cancels the stream task, clears the connection's stream state, waits for the task to quiesce | `playback_stopped` |

Each reply is `{ "state": "paused" | "playing" | "stopped", "seq": number }`,
with `seq` drawn from the process-wide transport sequencer
(`services/playback_event_sequencer.py`).

### `buffer_full` / `buffer_ready`

Flow control. `buffer_full` stops the server delivering chunks;
`buffer_ready` resumes it. No reply. The server's wait for `buffer_ready` is
bounded to 30 s (`FLOW_GATE_TIMEOUT_S` in `core/stream_gates.py`): on timeout
it logs and sends one chunk in case the resume was lost, but holds again if the
client re-asserts `buffer_full` for that chunk.

### `ping` / `pong` / `heartbeat`

| Command | Effect |
|---|---|
| `ping` | marks the connection alive; replies `{ "type": "pong" }`. Does not clear a server-issued pending ping |
| `pong` | answers a server `ping` and clears its pending slot. No reply |
| `heartbeat` | liveness keepalive only; does not clear a pending server ping. No reply |

## Server to client messages

### Player state

| Type | Payload (`data`) | Emitted by |
|---|---|---|
| `player_state` | `PlayerStatePayload`, below | every `PlayerStateManager` state change, and once per connect |
| `position_changed` | `{ position: number /* s */, seq }` | 1 Hz position tick while playing (`core/position_ticker.py`); not a seek acknowledgement |
| `volume_changed` | `{ volume: number /* integer 0-100 */, seq }` | `POST /api/player/volume` |
| `track_loaded` | `{ track_id }` | `POST /api/player/load` |
| `track_changed` | `{ action: "next" \| "previous", track_index: number, seq }` | `POST /api/player/next`, `POST /api/player/previous` |
| `playback_started` | `{ state: "playing", seq }` | `PlaybackService.play()`; no registered route calls it today |
| `playback_paused` / `playback_stopped` / `playback_resumed` | `{ state, seq }` | WS `pause` / `stop` / `resume` (reply to the sender); `PlaybackService.pause()` / `stop()` also broadcast the first two, but no registered route calls them |
| `seek_started` | `{ track_id, position }` | reply to WS `seek` |

`seq` is a monotonic ordering counter; a client drops any event older than the
last one it applied.

```typescript
// player_state
{
  "seq": number,
  "server_instance_id": string,  // changes when the backend process restarts
  "state": "playing" | "paused" | "stopped" | "loading" | "error",
  "is_playing": boolean, "is_paused": boolean,
  "current_track": TrackInfo | null,
  "current_time": number,        // seconds
  "duration": number,            // seconds
  "volume": number,              // integer 0-100
  "is_muted": boolean,
  "queue": TrackInfo[], "queue_index": number, "queue_size": number,
  "shuffle_enabled": boolean,
  "repeat_mode": "off" | "all" | "one",
  "mastering_enabled": boolean,
  "current_preset": "adaptive",
  "analysis": object | null
}
```

`TrackInfo` (`TrackPayload`): `id`, `title`, `artists: string[]`, `artist`,
`album: string | null`, `duration`, `artwork_url: string | null`, `format`.
Server filesystem paths are never sent.

### Queue

| Type | Payload | Emitted by |
|---|---|---|
| `queue_changed` | `{ action: "added" \| "removed" \| "reordered" \| "shuffled" \| "unshuffled" \| "cleared", tracks?: TrackInfo[], current_index?, track_id?, position?, index?, queue_size?, from_index?, to_index? }` | `/api/player/queue*` routes. `tracks` is omitted when the queue could not be read consistently; do not treat a missing `tracks` as an empty queue |
| `queue_shuffled` | `{ is_shuffled: boolean }` | shuffle / unshuffle, and when a queue replacement turns shuffle off |
| `repeat_mode_changed` | `{ repeat_mode: "off" \| "all" \| "one" }` | `POST /api/player/queue/repeat` |

### Library, metadata, playlists, artwork

| Type | Payload | Emitted by |
|---|---|---|
| `library_updated` | `{ action: "scan" \| "import" \| "update", track_count?, album_count?, artist_count? }` | a scan that added, updated or removed tracks; scan-folder removal |
| `library_tracks_removed` | `{ count }` | missing-file prune after a scan; scan-folder removal |
| `library_scan_started` | `{ directories: string[] }` | the scanner, once it owns the scan slot |
| `scan_progress` | `{ current, total, percentage: number \| null, current_file: string \| null, phase: "discovering" \| "counting" \| "processing" }` | scan progress bridge. `percentage` is null until the counting pass fixes a total |
| `scan_complete` | `{ files_processed, files_added, files_updated, files_skipped, files_failed, failures: {filename, reason}[], directory_errors: {filename, reason}[], duration, directories_scanned }` | scan completion (manual and auto-scanner). `failures` is capped; `files_failed` is the exact count |
| `library_scan_error` | `{ error: string }` | a scan that aborted; sent instead of `scan_complete` |
| `metadata_updated` | `{ track_id, updated_fields: string[] }` | `PUT /api/metadata/tracks/{track_id}` |
| `metadata_batch_updated` | `{ track_ids: number[], count }` | `POST /api/metadata/batch` (only the tracks that succeeded) |
| `playlist_created` | `{ playlist_id, name }` | `POST /api/playlists` |
| `playlist_updated` | `{ playlist_id, action: "renamed" \| "track_added" \| "track_removed" \| "reordered" \| "cleared" }` | `PUT /api/playlists/{id}`, `POST .../tracks`, `POST .../tracks/add`, `PUT .../tracks/reorder`, `DELETE .../tracks/{track_id}`, `DELETE .../tracks` |
| `playlist_deleted` | `{ playlist_id }` | `DELETE /api/playlists/{id}` |
| `artwork_updated` | `{ action: "extracted" \| "downloaded" \| "deleted", album_id, artwork_url? }` | `POST /api/albums/{album_id}/artwork/extract`, `.../download`, `DELETE /api/albums/{album_id}/artwork`. `artwork_url` is absent for `deleted` |
| `cache_cleared` | `{ message }` | `POST /api/cache/clear` |

### Enhancement

`enhancement_settings_changed`: `{ enabled: boolean, preset: "adaptive",
intensity: number /* 0.0-1.0 */ }`. Sent on connect, and by
`POST /api/player/enhancement/toggle|preset|intensity` and `PUT /api/settings`
/ `POST /api/settings/reset` when they change enhancement settings.

## Audio streaming

`play_enhanced`, `play_normal` and `seek` produce this sequence on the
requesting socket only:

```
audio_stream_start
  -> ( audio_chunk_meta JSON text frame, then one binary PCM frame ) x N
  -> audio_stream_end            (or audio_stream_error)
```

Chunk geometry is owned by `core/chunk_boundaries.py` and described in
[CHUNK_AND_CACHE_ARCHITECTURE.md](../../docs/features/cache-system/CHUNK_AND_CACHE_ARCHITECTURE.md).
Send code is `core/stream_lifecycle.py`, `core/stream_notifications.py` and
`core/stream_protocol.py`.

### `audio_stream_start`

```typescript
{ "type": "audio_stream_start", "data": {
    "track_id": number,
    "preset": string, "intensity": number,
    "sample_rate": number, "channels": number,
    "total_chunks": number,
    "chunk_duration": number,     // CHUNK_DURATION, 15.0
    "total_duration": number,     // track duration, seconds
    "stream_type": "enhanced" | "normal",
    "stream_epoch": number,       // identifies this stream; frames from another epoch are stale
    // present only on a seek or reconnect resume:
    "is_seek"?: true,
    "start_chunk"?: number, "seek_position"?: number, "seek_offset"?: number
} }
```

On `is_seek: true` the client keeps its `AudioContext` and PCM buffer instead of
recreating them.

### `audio_chunk_meta` and the binary frame

```typescript
{ "type": "audio_chunk_meta", "data": {
    "seq": number,            // monotonic per stream, 0-based, +1 per frame, across chunk boundaries
    "track_id": number, "stream_epoch": number,
    "chunk_index": number, "chunk_count": number,
    "frame_index": number, "frame_count": number,
    "sample_count": number,   // float32 samples in the next binary frame
    "stream_type": "enhanced" | "normal"
} }
```

The next frame is binary: `sample_count x 4` bytes of little-endian `float32`,
interleaved when `channels == 2`. A new stream (seek, track change) allocates a
new `stream_epoch` and restarts `seq` at 0, so `seq` is comparable only within
an epoch.

The frontend (`hooks/websocket/socketFrameParser.ts`) fuses each meta frame and
its binary frame into a synthetic `audio_chunk` event, and checks `seq` per
epoch: a gap raises a local `audio_stream_error` with code `DESYNC`, which takes
the same recovery path as a server-sent error. `audio_chunk` is never on the
wire.

### `audio_stream_end`

```typescript
{ "type": "audio_stream_end", "data": {
    "track_id": number,
    "total_samples": number,   // float32 samples actually delivered
    "duration": number,        // seconds actually delivered
    "stream_type": "enhanced" | "normal",
    "reason": "completed" | "stopped" | "errored",
    "stream_epoch": number     // a stale epoch is ignored by the client
} }
```

Only `completed` means the track played to its end and may trigger
auto-advance. `stopped` is an early clean exit; `errored` means chunks were
skipped after errors.

### `audio_stream_error`

```typescript
{ "type": "audio_stream_error", "data": {
    "track_id": number,
    "error": string,                // user-safe text
    "code": string,
    "stream_type": "enhanced" | "normal",
    "stream_epoch": number,
    "recovery_position"?: number,   // seconds; where the client may retry after a chunk failure
    "continues"?: true              // the stream skipped this chunk and keeps sending
} }
```

Codes the backend sends: `STREAMING_ERROR` (default), `SEEK_ERROR`,
`ENHANCEMENT_DISABLED`, `PROCESSOR_UNAVAILABLE`. The client adds `DESYNC`.
Without `continues` the stream has stopped.

### `fingerprint_progress`

Sent while a track's fingerprint is computed before streaming:
`{ track_id, status: "analyzing" | "complete" | "failed" | "error" | "cached" | "queued", message, stream_type }`.

## Frontend usage

`WebSocketContext.subscribe(type, handler)` takes one type and returns an
unsubscribe function; `subscribeAll(handler)` receives every message.

```typescript
const { subscribe } = useWebSocketContext();
useEffect(() => subscribe('playlist_updated', (m) => refresh(m.data.playlist_id)), [subscribe]);
```

Do not hand-copy payload types. Import them from `@/types/websocket`
(re-exporting `src/types/ws/*`): `RawPlayerStateData` and `TrackInfo` for state,
`OutgoingCommand` (`src/types/ws/commands.ts`) for client commands.

## Type union

The complete `WebSocketMessageType` union (33 members) from
[`src/types/ws/registry.ts`](../frontend/src/types/ws/registry.ts), reproduced
here for the drift test. It excludes the bare `ping` / `pong` control frames and
the wire-level `audio_chunk_meta`.

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
