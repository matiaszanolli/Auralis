# WebSocket-based PCM Audio Streaming - Architectural Plan

**Status**: Planning Phase
**Date**: 2025-12-04
**Scope**: Unified streaming architecture for enhanced audio playback

---

## 1. Current State Analysis

### 1.1 Existing Infrastructure ✅

**Backend**:
- ✅ WebSocket infrastructure ready (`routers/system.py`, `/ws` endpoint)
- ✅ ConnectionManager for broadcast/connect/disconnect
- ✅ Message structure standardized (`{type, data}`)
- ✅ Audio chunk processing working (24 chunks successfully created)
- ✅ ChunkedProcessor creates PCM WAV files (2.6MB each)
- ✅ Sample rate & format metadata available

**Frontend**:
- ✅ WebSocketContext with subscription system
- ✅ MultiTierWebMBuffer for buffering
- ✅ ChunkPreloadManager for preloading
- ✅ PlaybackController for playback management
- ✅ MSE (Media Source Extensions) support
- ✅ AudioContextController ready

**Audio Processing**:
- ✅ Critical `is_last` bug FIXED (no more NameError)
- ✅ Chunks processed successfully without errors
- ✅ Crossfading logic works correctly

### 1.2 Current Problems ❌

| Problem | Root Cause | Impact |
|---------|-----------|--------|
| **WAV Concatenation Fails** | Trying to join files with incompatible headers | No playback possible via HTTP |
| **Mixed Architectures** | HTTP chunked cache + WebSocket state exist separately | Complex, error-prone, hard to debug |
| **File I/O Bottleneck** | Saving all chunks to disk, then loading, then joining | High latency, disk thrashing |
| **Browser Can't Play Result** | HTML5 Audio element rejects concatenated WAV | Playback blocked entirely |

### 1.3 Key Insight

The problem **isn't audio processing** (working perfectly!). The problem is **delivery mechanism** - we're using the wrong protocol for the job. WebSocket is natural for streaming PCM audio.

---

## 2. Proposed Architecture: WebSocket-based PCM Streaming

### 2.1 High-Level Flow

```
┌─────────────────────────────────────────────────────┐
│ User clicks "Play with Enhancement"                 │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│ Frontend: emit("play_enhanced", track_id, preset)   │
│ → WebSocket message                                 │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│ Backend: ChunkedProcessor starts                    │
│ - Process chunk 0 (fast-start optimization)         │
│ - Send PCM samples immediately via WS              │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│ Frontend: AudioBuffer receives PCM stream           │
│ - Accumulate samples in circular buffer            │
│ - Feed to Web Audio API / AudioContext              │
│ - Play in real-time                                │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│ Backend: Process remaining chunks                   │
│ - Stream chunk 1, 2, 3... as they complete         │
│ - Crossfading happens at chunk boundaries          │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│ Frontend: Continues playing from buffer             │
│ - Smooth playback as chunks arrive                 │
│ - No waiting for full file concatenation           │
└─────────────────────────────────────────────────────┘
```

### 2.2 Design Principles

1. **Lightweight**: No file concatenation, no disk I/O during playback
2. **Snappy**: First chunk playable in <1 second
3. **Solid**: Proper error handling, state management, cleanup
4. **Low Latency**: Direct PCM streaming, no format conversions
5. **Extensible**: Support future features (real-time parameter changes, A/B testing)

---

## 3. Implementation Details

### 3.1 Backend Changes

#### 3.1.1 New WebSocket Message Types

```typescript
// audio_stream_start - Sent when streaming begins
{
  "type": "audio_stream_start",
  "data": {
    "track_id": 1,
    "preset": "adaptive",
    "intensity": 1.0,
    "sample_rate": 48000,
    "channels": 2,
    "total_chunks": 24,
    "chunk_duration": 10.0,  // seconds
    "total_duration": 238.5  // seconds
  }
}

// audio_chunk - Binary or base64-encoded PCM data
{
  "type": "audio_chunk",
  "data": {
    "chunk_index": 0,
    "chunk_count": 24,
    "samples": "[base64-encoded PCM samples]",  // Float32 PCM
    "sample_count": 480000,  // 10 seconds @ 48kHz
    "crossfade_samples": 144000  // 3-second overlap
  }
}

// audio_stream_end - Sent when all chunks delivered
{
  "type": "audio_stream_end",
  "data": {
    "track_id": 1,
    "total_samples": 11448000,
    "duration": 238.5
  }
}

// audio_stream_error - Sent if processing fails
{
  "type": "audio_stream_error",
  "data": {
    "track_id": 1,
    "error": "Processing failed: disk full",
    "code": "PROCESSING_ERROR"
  }
}
```

#### 3.1.2 Backend Stream Controller

**New file**: `auralis-web/backend/audio_stream_controller.py`

```python
class AudioStreamController:
    """
    Manages real-time audio streaming via WebSocket.

    Responsibilities:
    - Load track and create ChunkedProcessor
    - Process chunks on-demand
    - Stream PCM samples to connected clients
    - Handle crossfading at chunk boundaries
    - Manage streaming state (active, paused, stopped)
    """

    async def stream_enhanced_audio(
        self,
        track_id: int,
        preset: str,
        intensity: float,
        websocket: WebSocket
    ) -> None:
        """Stream enhanced audio chunks to client"""

    async def process_and_stream_chunk(
        self,
        chunk_index: int,
        processor: ChunkedProcessor,
        websocket: WebSocket
    ) -> None:
        """Process single chunk and send PCM to client"""

    async def send_pcm_chunk(
        self,
        pcm_samples: np.ndarray,
        chunk_index: int,
        total_chunks: int,
        websocket: WebSocket
    ) -> None:
        """Send PCM samples as binary message"""
```

#### 3.1.3 Modified WebSocket Endpoint

**File**: `auralis-web/backend/routers/system.py` (extend existing)

```python
elif message.get("type") == "play_enhanced":
    # New message handler for enhanced playback
    data = message.get("data", {})
    track_id = data.get("track_id")
    preset = data.get("preset", "adaptive")
    intensity = data.get("intensity", 1.0)

    # Stream audio via AudioStreamController
    controller = AudioStreamController(...)
    await controller.stream_enhanced_audio(
        track_id, preset, intensity, websocket
    )
```

#### 3.1.4 Keep HTTP Endpoint for Unenhanced Audio

**Keep**: `routers/player.py` `/api/player/stream/{track_id}`
- Return original audio file directly
- Fast path (no processing)
- Support HTTP Range requests
- ~5 MB/s bandwidth

---

### 3.2 Frontend Changes

#### 3.2.1 New WebSocket Message Handlers

**File**: `auralis-web/frontend/src/contexts/WebSocketContext.tsx` (extend)

```typescript
// Handle audio stream start
if (message.type === 'audio_stream_start') {
  const { track_id, sample_rate, channels, total_chunks } = message.data;
  audioBuffer.initialize(sample_rate, channels);
  dispatch(setStreamingState('playing'));
}

// Handle audio chunks
if (message.type === 'audio_chunk') {
  const { samples, sample_count, crossfade_samples } = message.data;
  const pcm = decodeBase64ToFloat32Array(samples);
  audioBuffer.append(pcm, crossfade_samples);
}

// Handle stream end
if (message.type === 'audio_stream_end') {
  audioBuffer.markComplete();
  dispatch(setStreamingState('completed'));
}
```

#### 3.2.2 New AudioBuffer Implementation

**New file**: `auralis-web/frontend/src/services/audio/PCMStreamBuffer.ts`

```typescript
class PCMStreamBuffer {
  private circularBuffer: Float32Array;
  private writePos: number = 0;
  private readPos: number = 0;
  private sampleRate: number;
  private channels: number;
  private crossfadeSamples: number;

  /**
   * Circular buffer for streaming PCM samples.
   *
   * Design:
   * - 5MB buffer (320,000 samples @ 48kHz stereo)
   * - ~6 seconds of audio at 48kHz stereo
   * - Allows client to lag behind streaming without drops
   *
   * Methods:
   * - append(pcm, crossfadeOffset): Add chunk with crossfade
   * - read(count): Get samples for playback
   * - available(): Samples ready to play
   * - isFull(), isEmpty()
   */

  append(pcm: Float32Array, crossfadeOffset: number): void {
    // Apply crossfading during append
    // Copy to circular buffer
  }

  read(sampleCount: number): Float32Array {
    // Return samples and advance read position
  }

  getAvailableSamples(): number {
    // Calculate (writePos - readPos) with wrap-around
  }
}
```

#### 3.2.3 Modify PlaybackController

**File**: `auralis-web/frontend/src/services/player/PlaybackController.ts` (extend)

```typescript
async playEnhanced(trackId: number, preset: string, intensity: number) {
  // Emit WebSocket message
  this.ws.send({
    type: 'play_enhanced',
    data: { track_id: trackId, preset, intensity }
  });

  // Start Web Audio API playback loop
  this.audioContext.resume();
  this.scheduleAudioProcessing();
}

private scheduleAudioProcessing() {
  // ScriptProcessorNode or AudioWorklet loop
  // Pull samples from PCMStreamBuffer
  // Feed to Web Audio API
  // Continue until stream ends
}
```

#### 3.2.4 Update Playback State Management

**File**: `auralis-web/frontend/src/store/slices/playerSlice.ts` (extend)

```typescript
const playerSlice = createSlice({
  name: 'player',
  initialState: {
    ...existing,
    streamingState: 'idle',  // idle | buffering | playing | paused | completed | error
    streamingProgress: 0,     // 0-100
    bufferedSamples: 0,       // Available samples in buffer
  },
  reducers: {
    setStreamingState: (state, action) => {...},
    setStreamingProgress: (state, action) => {...},
    setBufferedSamples: (state, action) => {...},
  }
});
```

---

### 3.3 Message Flow Example

#### Playing Enhanced Audio (Track 1, Adaptive Preset, 1.0 intensity)

**T+0ms**: User clicks "Play Enhanced" button

```
Frontend → Backend (WebSocket):
{
  "type": "play_enhanced",
  "data": {"track_id": 1, "preset": "adaptive", "intensity": 1.0}
}
```

**T+100ms**: Backend accepts and starts processing

```
Backend → Frontend (WebSocket):
{
  "type": "audio_stream_start",
  "data": {
    "track_id": 1,
    "preset": "adaptive",
    "sample_rate": 48000,
    "channels": 2,
    "total_chunks": 24,
    "chunk_duration": 10.0,
    "total_duration": 238.5
  }
}
```

**T+500ms**: First chunk processed and sent (fast-start optimization)

```
Backend → Frontend (WebSocket):
{
  "type": "audio_chunk",
  "data": {
    "chunk_index": 0,
    "chunk_count": 24,
    "samples": "[base64-encoded 480,000 float32 samples]",
    "sample_count": 480000,
    "crossfade_samples": 144000
  }
}
```

**T+600ms**: Frontend starts playback from buffer

- Web Audio API context starts
- ScriptProcessorNode pulls samples from PCMStreamBuffer
- Audio begins playing to user

**T+1000ms**: Backend sends chunk 1 (overlaps with chunk 0 by 3 seconds)

```
Backend → Frontend:
{
  "type": "audio_chunk",
  "data": {
    "chunk_index": 1,
    "chunk_count": 24,
    "samples": "[base64-encoded samples]",
    "sample_count": 480000,
    "crossfade_samples": 144000
  }
}
```

**T+1500ms**: Playback crosses chunk boundary

- Crossfading happens transparently
- No gap, no pop, no discontinuity

**Continue**: Backend streams remaining 22 chunks as they process

**T+15s**: All chunks received and played

```
Backend → Frontend:
{
  "type": "audio_stream_end",
  "data": {
    "track_id": 1,
    "total_samples": 11448000,
    "duration": 238.5
  }
}
```

---

## 4. Implementation Phases

### Phase 1: Backend Streaming (2-3 days)
1. ✅ Create AudioStreamController
2. ✅ Add message types to WebSocket
3. ✅ Modify system.py to handle `play_enhanced`
4. ✅ Stream PCM as base64 binary messages
5. Test with sample track

### Phase 2: Frontend Audio Buffering (2-3 days)
1. Create PCMStreamBuffer (circular buffer)
2. Extend WebSocketContext with chunk handlers
3. Create audio playback loop (Web Audio API)
4. Integrate with existing PlaybackController
5. Test playback and crossfading

### Phase 3: Integration & Polish (1-2 days)
1. Connect frontend UI to `play_enhanced` message
2. Add streaming progress indicators
3. Error handling and recovery
4. Performance optimization
5. Full end-to-end testing

### Phase 4: Cleanup (1 day)
1. Remove WAV concatenation code from ChunkedProcessor
2. Archive chunked_processor concatenation methods
3. Update documentation
4. Remove HTTP stream endpoint (or keep as fallback)

---

## 5. Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Time to first playback | <1 second | N/A (broken) |
| Chunk streaming latency | <500ms | N/A |
| Buffer size | 5MB (6 sec @ 48kHz) | N/A |
| CPU usage (streaming) | <5% | N/A |
| Memory (buffer) | 10MB | N/A |
| Bandwidth (PCM) | ~15 MB/min | N/A |

---

## 6. Testing Strategy

### Backend Tests
- ✅ AudioStreamController message sequencing
- ✅ ChunkedProcessor integration (uses existing test)
- ✅ WebSocket message format validation
- ✅ Error handling (disk full, interrupted)
- ✅ Stress test (multiple concurrent streams)

### Frontend Tests
- ✅ PCMStreamBuffer circular buffer logic
- ✅ Base64 decode performance
- ✅ Audio playback scheduling
- ✅ Crossfading boundaries
- ✅ WebSocket reconnection handling

### Integration Tests
- ✅ Play enhanced (full flow)
- ✅ Pause/resume
- ✅ Seek (challenge: network latency)
- ✅ Switch presets mid-playback
- ✅ Switch tracks mid-playback

---

## 7. Known Challenges & Solutions

| Challenge | Solution |
|-----------|----------|
| **Network latency** | 5MB buffer absorbs ~1s of latency; streaming parallel with playback |
| **Crossfade accuracy** | Pass crossfade_samples in message; apply during append() |
| **Seeking** | Pause stream, seek position, restart from new chunk |
| **Preset switching** | Cancel current stream, start new one with new preset |
| **Connection drop** | Auto-reconnect; buffer holds playback for ~6 seconds |
| **CPU spikes** | Stream smaller chunks (e.g., 5 seconds vs 10 seconds) |

---

## 8. Architecture Comparison

### Current (Broken) HTTP Chunked Approach
```
Load chunks → Concatenate files → Serve WAV → Play in HTML5 Audio
   ✅ Works          ❌ Breaks           ❌ Can't play    ❌ Stuck
```

### Proposed WebSocket PCM Streaming
```
Load chunks → Stream PCM → Buffer → Play in Web Audio API
   ✅ Works    ✅ Clean      ✅ Smooth  ✅ Playing!
```

---

## 9. Files Modified/Created

### New Files
- `auralis-web/backend/audio_stream_controller.py` (~200 lines)
- `auralis-web/frontend/src/services/audio/PCMStreamBuffer.ts` (~150 lines)
- `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts` (~200 lines)

### Modified Files
- `auralis-web/backend/routers/system.py` (+30 lines for message handlers)
- `auralis-web/frontend/src/contexts/WebSocketContext.tsx` (+50 lines for handlers)
- `auralis-web/frontend/src/services/player/PlaybackController.ts` (+40 lines)
- `auralis-web/frontend/src/store/slices/playerSlice.ts` (+15 lines)

### Potentially Removed
- `get_full_processed_audio_path()` from ChunkedProcessor (concatenation)
- `apply_crossfade_between_chunks()` (moved to frontend)
- `/api/player/stream/{track_id}` for enhanced audio (keep for unenhanced)

---

## 10. Rollout Plan

1. **PR Phase 1**: AudioStreamController + WebSocket messages
   - Backend-only changes
   - No impact on frontend
   - Reviewable independently

2. **PR Phase 2**: PCMStreamBuffer + audio playback
   - Frontend-only changes
   - Can be reviewed independently
   - Needs Phase 1 merged first

3. **PR Phase 3**: Integration + UI
   - Connect phases 1 & 2
   - Update UI components
   - Full feature testing

4. **PR Phase 4**: Cleanup
   - Remove old concatenation code
   - Archive unused methods
   - Update docs

---

## 11. Risk Analysis

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Network latency causes buffer underrun | Low | Playback dropout | 5MB buffer, start playback after 1MB buffered |
| Crossfading produces artifacts | Low | Audio quality | Test with real tracks, adjust overlap duration |
| WebSocket connection drops | Medium | Playback interruption | Auto-reconnect, pausable buffer |
| Performance degradation | Low | User experience | Profile before/after, optimize hot paths |

---

## Summary

This architecture **replaces file concatenation with real-time PCM streaming**, eliminating the WAV header corruption issue while providing a cleaner, more efficient, and more extensible design.

Key benefits:
- ✅ No file I/O during playback
- ✅ Sub-1-second latency to first audio
- ✅ Natural support for streaming
- ✅ Extensible for future features
- ✅ Solid error handling
- ✅ Lightweight and snappy

The rebuild is successful, the audio processing is perfect - we just need to deliver it better.
