# WebSocket API Documentation

**Last Updated**: October 24, 2025
**Status**: Phase 0.2 Complete - `playback_started` and `playback_paused` messages added

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
Broadcast every second during playback with complete player state.

**Trigger**: Automatic (1Hz during playback)

**Payload**:
```typescript
{
  "type": "player_state",
  "data": {
    "currentTrack": TrackInfo | null,
    "isPlaying": boolean,
    "volume": number,              // 0.0 - 1.0
    "position": number,             // Seconds
    "duration": number,             // Seconds
    "queue": TrackInfo[],
    "queueIndex": number,
    "gapless_enabled": boolean,
    "crossfade_enabled": boolean,
    "crossfade_duration": number    // Seconds
  }
}
```

#### `playback_started` ✨ NEW
Broadcast when playback starts.

**Trigger**: `POST /api/player/play`

**Payload**:
```typescript
{
  "type": "playback_started",
  "data": {
    "state": "playing"
  }
}
```

#### `playback_paused` ✨ NEW
Broadcast when playback is paused.

**Trigger**: `POST /api/player/pause`

**Payload**:
```typescript
{
  "type": "playback_paused",
  "data": {
    "state": "paused"
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
    "state": "stopped"
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
    "track_path": string
  }
}
```

#### `track_changed`
Broadcast when skipping to next/previous track.

**Trigger**: `POST /api/player/next` or `POST /api/player/previous`

**Payload**:
```typescript
{
  "type": "track_changed",
  "data": {
    "action": "next" | "previous"
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
    "position": number  // Seconds
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
    "volume": number  // 0.0 - 1.0
  }
}
```

---

### Queue Management Messages

#### `queue_updated`
Broadcast when the playback queue is modified.

**Triggers**:
- `POST /api/player/queue/add`
- `DELETE /api/player/queue/{index}`
- `PUT /api/player/queue/reorder`
- `POST /api/player/queue/clear`
- `POST /api/player/queue/shuffle`

**Payload**:
```typescript
{
  "type": "queue_updated",
  "data": {
    "action": "added" | "removed" | "reordered" | "cleared" | "shuffled",
    "track_path"?: string,        // For "added"
    "index"?: number,              // For "removed"
    "queue_size": number
  }
}
```

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

#### `metadata_updated` ✨ NEW
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

#### `metadata_batch_updated` ✨ NEW
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

#### `mastering_recommendation` ✨ NEW (Priority 4)
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

These four messages form the core audio streaming protocol. They are emitted in response to `play_enhanced` / `play_normal` WebSocket commands — not REST calls. See `core/audio_stream_controller.py` for the Python implementation and `src/types/websocket.ts:425-518` for the canonical TypeScript types.

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
    "total_chunks": number,    // Total 30-second chunks in the stream
    "chunk_duration": number,  // Seconds per chunk (typically 30)
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
    "chunk_index": number,      // Which 30-second chunk this frame belongs to (0-based)
    "chunk_count": number,      // Total chunks in stream (same as audio_stream_start.total_chunks)
    "frame_index": number,      // Frame index within the current chunk (0-based)
    "frame_count": number,      // Total frames in the current chunk
    "sample_count": number,     // Number of float32 samples in the following binary frame
    "crossfade_samples": number,// Overlap samples at the chunk boundary (used for gapless blending)
    "stream_type"?: "enhanced" | "normal"
  }
}
```

**Binary frame format**: `sample_count × 4` bytes of little-endian `float32` values, interleaved stereo if `channels == 2` (L0 R0 L1 R1 …).

**Frontend note**: `WebSocketContext` automatically fuses the `audio_chunk_meta` text frame and the following binary frame into a synthetic `audio_chunk` event (with `pcm_binary` populated) for downstream consumers.

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
Broadcast when library scan finishes.

**Trigger**: Scan completion

**Payload**:
```typescript
{
  "type": "scan_complete",
  "data": {
    "files_processed": number,
    "tracks_added": number,
    "duration": number  // Seconds
  }
}
```

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
    "preset"?: string,           // Optional. One of: adaptive, gentle, warm, bright, punchy.
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

---

## Frontend Usage

### TypeScript Interfaces

```typescript
// Core message type
interface WebSocketMessage {
  type: string;
  data: any;
}

// Player state
interface PlayerState {
  currentTrack: TrackInfo | null;
  isPlaying: boolean;
  volume: number;
  position: number;
  duration: number;
  queue: TrackInfo[];
  queueIndex: number;
  gapless_enabled: boolean;
  crossfade_enabled: boolean;
  crossfade_duration: number;
}

// Track info
interface TrackInfo {
  id: number;
  title: string;
  artist: string;
  album: string;
  duration: number;
  filepath: string;
  // ... other fields
}
```

### Subscription Example

```typescript
import { useWebSocketContext } from '../contexts/WebSocketContext';

function MyComponent() {
  const { subscribe } = useWebSocketContext();

  useEffect(() => {
    // Subscribe to specific message types
    const unsubscribe = subscribe(['playback_started', 'playback_paused'], (message) => {
      console.log(`Playback state changed: ${message.data.state}`);
    });

    // Cleanup on unmount
    return unsubscribe;
  }, [subscribe]);
}
```

---

## REST Endpoint → WebSocket Message Mapping

| REST Endpoint | WebSocket Message | Notes |
|--------------|-------------------|-------|
| `POST /api/player/play` | `playback_started` | ✅ Phase 0.2 |
| `POST /api/player/pause` | `playback_paused` | ✅ Phase 0.2 |
| `POST /api/player/stop` | `playback_stopped` | ✅ |
| `POST /api/player/load` | `track_loaded` | ✅ |
| `POST /api/player/seek` | `position_changed` | ✅ |
| `POST /api/player/volume` | `volume_changed` | ✅ |
| `POST /api/player/next` | `track_changed` | ✅ |
| `POST /api/player/previous` | `track_changed` | ✅ |
| `POST /api/player/queue/*` | `queue_updated` | ✅ |
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

## Phase 0.2 Completion Summary ✅

**What Was Added**:
- `playback_started` message when playback starts
- `playback_paused` message when playback is paused

**Files Modified**:
- [auralis-web/backend/routers/player.py](routers/player.py:315-318) - Added `playback_started` broadcast
- [auralis-web/backend/routers/player.py](routers/player.py:350-353) - Added `playback_paused` broadcast

**Result**:
- Frontend components can now reliably track all play/pause state changes
- Consistent with existing `playback_stopped` message
- No breaking changes (additive only)

---

## Future Work

### Phase 0.4: Message Structure Standardization (LOW PRIORITY - 1-2 days)

**Goal**: Ensure ALL WebSocket messages follow consistent structure:

```typescript
{
  "type": string,
  "data": object,
  "timestamp"?: number  // Unix timestamp (optional)
}
```

**Current Status**:
- Most messages already follow `{type, data}` pattern ✅
- Some may have additional top-level fields (to be audited)
- No timestamps currently included

**Scope**: ~40 broadcast locations across backend

**Benefit**: Improved type safety, easier debugging, future-proof structure

---

## Connection Manager Implementation

**Location**: [auralis-web/backend/config/globals.py](config/globals.py)

**Key Methods**:
- `connect(websocket)` - Register new WebSocket connection
- `disconnect(websocket)` - Remove WebSocket connection
- `broadcast(message)` - Send message to all connected clients
- `send_personal(message, websocket)` - Send to specific client

**Concurrency**: Thread-safe with asyncio locks

---

## Debugging Tips

### Enable WebSocket Logging

**Backend** (main.py):
```python
import logging
logging.getLogger("auralis.websocket").setLevel(logging.DEBUG)
```

**Frontend** (browser console):
```javascript
// WebSocketContext logs all messages when enabled
localStorage.setItem('debug_websocket', 'true');
```

### Monitor Messages

**Backend**:
```bash
# Watch backend logs
tail -f auralis-backend.log | grep "WS:"
```

**Frontend**:
```javascript
// Subscribe to all messages
const { subscribe } = useWebSocketContext();
subscribe('*', (msg) => console.log('[WS]', msg));
```

---

## TypeScript Type Definitions

Complete TypeScript types for all WebSocket messages are available in:

**Frontend**: [auralis-web/frontend/src/types/websocket.ts](../frontend/src/types/websocket.ts)

The canonical source of truth is [`auralis-web/frontend/src/types/websocket.ts`](../frontend/src/types/websocket.ts). The complete union (35 members as of v1.2) is reproduced here for quick reference:

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
  | 'queue_updated'
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
  | 'audio_chunk_meta'
  | 'audio_stream_error'
  // System messages
  | 'scan_progress'
  | 'scan_complete'
  | 'library_scan_started'
  | 'library_scan_error'
  | 'library_tracks_removed'
  // Error messages
  | 'error';
```

### Message Type Summary

| Category | Types |
|----------|-------|
| Player state | `player_state`, `playback_started`, `playback_paused`, `playback_resumed`, `playback_stopped`, `track_loaded`, `track_changed`, `position_changed`, `volume_changed` |
| Queue | `queue_updated`, `queue_changed`, `queue_shuffled`, `repeat_mode_changed` |
| Library | `library_updated`, `library_scan_started`, `library_scan_error`, `library_tracks_removed` |
| Metadata | `metadata_updated`, `metadata_batch_updated` |
| Playlists | `playlist_created`, `playlist_updated`, `playlist_deleted` |
| Enhancement | `enhancement_settings_changed`, `mastering_recommendation` |
| Artwork | `artwork_updated` |
| Fingerprint | `fingerprint_progress` |
| Seek | `seek_started` |
| Audio streaming | `audio_stream_start`, `audio_chunk_meta`, `audio_chunk`, `audio_stream_end`, `audio_stream_error` |
| Scan | `scan_progress`, `scan_complete` |
| Errors | `error` |

---

**For questions or updates, see**:
- [Architecture Overview](../../ARCHITECTURE.md)
- [Development Roadmap](../../docs/MASTER_ROADMAP.md)
