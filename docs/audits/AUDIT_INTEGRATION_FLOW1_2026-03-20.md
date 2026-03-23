# Integration Audit — Flow 1: Track Playback (Full Pipeline)

**Date**: 2026-03-20
**Auditor**: Claude (Sonnet 4.6)
**Requested output**: `/tmp/audit/integration/flow_1.md` (filesystem full — written here instead)
**Scope**: End-to-end trace from user click → WebSocket → backend processing → PCM streaming → frontend decode → Web Audio API playback
**Prior audit**: 2026-03-05 (INT-11/INT-12 pre-existing known issues)
**Finding range**: INT-13+

---

## Trace Path Covered

1. `usePlayNormal.ts` / `usePlayEnhanced.ts` → WebSocket `play_normal` / `play_enhanced`
2. `WebSocketContext.tsx` message dispatch (JSON text + binary frame pairing)
3. `routers/system.py` WebSocket handler → `AudioStreamController`
4. `chunked_processor.py` (enhanced) / inline SoundFile reads (normal) → PCM NumPy array
5. `audio_stream_controller.py` `_send_pcm_chunk()` → `audio_chunk_meta` JSON + binary frame
6. `WebSocketContext.tsx` binary frame pairing → `audio_chunk` dispatch
7. `pcmDecoding.ts` `decodeAudioChunkMessage()` → `Float32Array`
8. `PCMStreamBuffer.ts` circular buffer → `AudioPlaybackEngine.ts` / `audio-worklet-processor.js`

---

## Findings

### INT-13: AudioWorklet hardcodes stereo — mono files play at half speed with pitch shift

- **Severity**: HIGH
- **Flow**: Track Playback
- **Boundary**: `AudioPlaybackEngine.ts:startFeeding()` → `audio-worklet-processor.js:process()`
- **Location**: `auralis-web/frontend/public/audio-worklet-processor.js:60` ← `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts:381`
- **Status**: NEW

**Description**: `AuralisPlaybackProcessor` hardcodes `samplesNeeded = framesNeeded * 2` unconditionally (line 60), assuming all audio is stereo interleaved. `AudioPlaybackEngine.startFeeding()` also hardcodes `feedChunkSize = this.bufferSize * 2` (line 381). For a mono audio file the backend sends `channels=1` in `audio_stream_start` and the PCM flat array has N elements (one per frame, no channel duplication). The worklet's `samplesNeeded = framesNeeded * 2` then attempts to consume twice as many samples per render quantum as actually exist, draining the buffer at double rate, producing audio at half speed with pitch one octave too low.

**Evidence**:

Backend sends `channels` accurately from the file:
```python
# auralis-web/backend/core/audio_stream_controller.py:763–764
sample_rate, channels, total_frames = await asyncio.to_thread(
    _get_audio_info, str(track.filepath)
)
# channels = 1 for mono files; sent verbatim in audio_stream_start
```

Worklet ignores channel count:
```javascript
// auralis-web/frontend/public/audio-worklet-processor.js:60
const samplesNeeded = framesNeeded * 2;  // HARDCODED stereo
```

Feed also ignores channel count:
```typescript
// auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts:381
const feedChunkSize = this.bufferSize * 2; // stereo interleaved — hardcoded
```

**Impact**: All mono audio files (spoken word, older recordings, podcasts) play at half speed with incorrect pitch. Buffer drains twice as fast per render quantum, causing frequent underruns after a few seconds. No error is thrown; the bug is silent.

**Suggested Fix**:

In `audio-worklet-processor.js`, accept channel count via port message and use it:
```javascript
this._channels = 2;
this.port.onmessage = (e) => {
  if (e.data.channels) this._channels = e.data.channels;
  // ...
};
// In process():
const samplesNeeded = framesNeeded * this._channels;
```

In `AudioPlaybackEngine.startFeeding()`, derive from buffer metadata:
```typescript
const channels = this.buffer.getMetadata().channels || 2;
const feedChunkSize = this.bufferSize * channels;
```

Send channel count to worklet after initialization:
```typescript
this.workletNode.port.postMessage({ channels: this.buffer.getMetadata().channels });
```

---

### INT-14: Blob binary frame race condition drops PCM frames on Safari / Firefox

- **Severity**: MEDIUM
- **Flow**: Track Playback
- **Boundary**: `WebSocketContext.tsx` Blob async handler → module-level `pendingAudioChunkMeta`
- **Location**: `auralis-web/frontend/src/contexts/WebSocketContext.tsx:276–290`
- **Status**: NEW

**Description**: On browsers that deliver WebSocket binary frames as `Blob` objects (Safari, some Firefox versions), the `arrayBuffer()` conversion is asynchronous. The handler captures `pendingAudioChunkMeta` by local reference synchronously (correct), but sets `pendingAudioChunkMeta = null` INSIDE the async `.then()` callback (incorrect). During the async resolution, a new `audio_chunk_meta` JSON message can arrive and overwrite `pendingAudioChunkMeta`. When a subsequent Blob's `.then()` resolves, it sets `pendingAudioChunkMeta = null` — destroying the newer entry. The next binary frame then finds `null` and is silently dropped.

**Evidence**:

```typescript
// auralis-web/frontend/src/contexts/WebSocketContext.tsx:275–290
if (event.data instanceof Blob) {
  const meta = pendingAudioChunkMeta;          // sync capture ✓
  event.data.arrayBuffer().then((buffer: ArrayBuffer) => {
    if (meta) {
      const combined = { type: 'audio_chunk', data: { ...(meta as any).data, pcm_binary: buffer } };
      pendingAudioChunkMeta = null;            // ← set INSIDE async callback — WRONG
      dispatchMessage(combined);
    }
  });
  return;  // pendingAudioChunkMeta not cleared here → next meta_B overwrites
}
```

Race sequence with two consecutive Blob frames:
1. `meta_A` (text) → `pendingAudioChunkMeta = A`
2. `Blob_A` → captures `A`, `arrayBuffer_A()` starts; `pendingAudioChunkMeta` still `A`
3. `meta_B` (text) → `pendingAudioChunkMeta = B`
4. `Blob_B` → captures `B`, `arrayBuffer_B()` starts
5. `meta_C` (text) → `pendingAudioChunkMeta = C`
6. `then_A` fires → dispatches A correctly; sets `pendingAudioChunkMeta = null` (harmless if B already resolved)
7. `then_B` fires → dispatches B correctly; sets `pendingAudioChunkMeta = null` — **DESTROYS C**
8. Binary/Blob for C arrives → `pendingAudioChunkMeta = null` → warning logged, **frame C dropped**

**Impact**: On Safari and mobile WebKit browsers, one or more PCM frames per chunk boundary are silently dropped. The audio buffer receives fewer samples than expected → audible pops, gaps, or buffer underruns. Proportional to stream rate; more frames per chunk = higher drop probability.

**Suggested Fix**: Clear `pendingAudioChunkMeta` synchronously before launching async work:

```typescript
if (event.data instanceof Blob) {
  const meta = pendingAudioChunkMeta;
  pendingAudioChunkMeta = null;  // ← clear synchronously, before async starts
  event.data.arrayBuffer().then((buffer: ArrayBuffer) => {
    if (meta) {
      const combined: any = {
        type: 'audio_chunk',
        data: { ...(meta as any).data, pcm_binary: buffer },
      };
      // pendingAudioChunkMeta already null — no need to clear again
      dispatchMessage(combined);
    }
  });
  return;
}
```

---

### INT-15: `usePlayNormal` missing WebSocket disconnect recovery — stale engine state or silent stream on reconnect

- **Severity**: MEDIUM
- **Flow**: Track Playback (Normal path)
- **Boundary**: `WebSocketContext.tsx` reconnect re-issue → `usePlayNormal.ts` subscription/engine state
- **Location**: `auralis-web/frontend/src/contexts/WebSocketContext.tsx:325–328` → `auralis-web/frontend/src/hooks/enhancement/usePlayNormal.ts:186–200`
- **Status**: NEW

**Description**: On WebSocket reconnect, `WebSocketContext` automatically re-issues the last streaming command (`singletonLastStreamCommand`), which for a `play_normal` session causes the backend to restart the stream. `usePlayEnhanced` handles this correctly with an explicit `wsContext.isConnected` watcher (lines 776–805) that stops the engine, clears all refs, and resets Redux state before the new stream starts. `usePlayNormal` has no such handler. After a mid-stream disconnect:

- The old `AudioPlaybackEngine` is left running (draining a now-empty buffer, causing underruns)
- The old `PCMStreamBuffer` is not reset
- When the backend re-issues the stream and `audio_stream_start` arrives, `handleStreamStart` is called with stale engine/buffer state. It creates a NEW `PCMStreamBuffer` and `AudioPlaybackEngine` (overwriting `pcmBufferRef` and `playbackEngineRef`) but the OLD engine instance is never stopped — it continues running concurrently, potentially outputting silence/artifacts through the old `GainNode` still connected to `AudioContext.destination`.

**Evidence**:

`usePlayEnhanced` has disconnect guard (lines 776–804):
```typescript
// auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:776
useEffect(() => {
  if (!wsContext.isConnected && playbackEngineRef.current) {
    playbackEngineRef.current.stopPlayback();
    playbackEngineRef.current = null;
    pcmBufferRef.current = null;
    streamingMetadataRef.current = null;
    pendingChunksRef.current = [];
    setCurrentTime(0);
    setIsPaused(false);
    dispatch(resetStreaming('enhanced'));
  }
}, [wsContext.isConnected, dispatch]);
```

`usePlayNormal` — no equivalent. Only cleanup on:
- Unmount (`stopPlayback` in useEffect cleanup, line 549–553)
- `handleStreamError` call (line 420)
- `stopPlayback` explicit call (line 503–508)

`handleStreamStart` in `usePlayNormal` (line 239): `playbackEngineRef.current = engine` — overwrites without stopping the old engine.

**Impact**: On reconnect after mid-stream disconnect during normal playback: old `AudioPlaybackEngine` and its `ScriptProcessorNode`/`AudioWorkletNode` continue running, outputting silence/static through `AudioContext.destination`. Both old and new engines concurrently process audio, causing a double-audio or artifact situation. On browsers that enforce exclusive audio node usage, this may also throw errors.

**Suggested Fix**: Add the same disconnect recovery hook to `usePlayNormal`:

```typescript
useEffect(() => {
  if (!wsContext.isConnected && playbackEngineRef.current) {
    playbackEngineRef.current.stopPlayback();
    playbackEngineRef.current = null;
    pcmBufferRef.current = null;
    streamingMetadataRef.current = null;
    pendingChunksRef.current = [];
    setCurrentTime(0);
    setIsPaused(false);
    dispatch(resetStreaming('normal'));
  }
}, [wsContext.isConnected, dispatch]);
```

---

### INT-16: Seek trim `chunk_interval` sourced from `getattr` fallback — not connected to `CHUNK_INTERVAL` constant

- **Severity**: LOW
- **Flow**: Track Playback (Seek path)
- **Boundary**: `audio_stream_controller.py` seek position calculation → `ChunkedAudioProcessor`
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:1511–1517`
- **Status**: NEW

**Description**: In `stream_enhanced_audio_from_position`, the chunk interval used to calculate which chunk to start from and how many samples to trim is obtained via:

```python
chunk_interval = getattr(processor, 'chunk_interval', 10.0)
```

`ChunkedAudioProcessor` has NO `chunk_interval` instance attribute or property. The module constant `CHUNK_INTERVAL = 10` is never exposed as an instance attribute. The `getattr` thus always returns the default `10.0` — which currently matches `CHUNK_INTERVAL`. However, this is a fragile implicit coupling: if `CHUNK_INTERVAL` is changed (e.g., to 8 or 12 seconds), the seek trim calculation silently uses the stale default `10.0`, causing the trim to cut at the wrong sample offset within the first seek chunk. The resulting audio either includes samples before the seek point (audible duplication) or skips past it (jumps forward).

**Evidence**:

```python
# auralis-web/backend/core/audio_stream_controller.py:1511
chunk_interval = getattr(processor, 'chunk_interval', 10.0)  # Default 10s interval
```

```python
# auralis-web/backend/core/chunked_processor.py:66
CHUNK_INTERVAL = 10  # module-level constant — no instance attribute
```

No `self.chunk_interval` assignment anywhere in `ChunkedAudioProcessor.__init__`.

**Impact**: Currently non-breaking (10.0 == CHUNK_INTERVAL). Silent regression if CHUNK_INTERVAL is tuned.

**Suggested Fix**: Add `chunk_interval` as a property to `ChunkedAudioProcessor` alongside the existing `chunk_duration` property:

```python
# auralis-web/backend/core/chunked_processor.py
@property
def chunk_interval(self) -> float:
    """Playback interval between chunk starts in seconds."""
    return float(CHUNK_INTERVAL)
```

---

### INT-17: Flow-control `buffer_full` / `buffer_ready` messages counted against WebSocket rate limit

- **Severity**: LOW
- **Flow**: Track Playback
- **Boundary**: `usePlayEnhanced.ts` / `usePlayNormal.ts` flow control send → `routers/system.py` rate limiter
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:448–453` → `auralis-web/backend/routers/system.py:174–178`
- **Status**: NEW

**Description**: The backend WebSocket handler applies `WebSocketRateLimiter(max_messages_per_second=10)` to ALL received messages before processing them (lines 174–178). The frontend sends `buffer_full` and `buffer_ready` messages as infrastructure flow-control signals (not user actions) whenever the PCMStreamBuffer fill level crosses 75% / 50% thresholds. While hysteresis limits this to one `buffer_full` and one `buffer_ready` per buffer oscillation, these signals still consume rate-limit budget alongside `ping`, `heartbeat`, and other control messages. If total message rate reaches 10/s (e.g., on a slow machine processing chunks slowly with many control messages), a `buffer_full` message may be rate-limited and dropped. The backend then continues sending chunks despite a full frontend buffer, causing `PCMStreamBuffer.writeToBuffer()` to drop incoming PCM data (logged: "Buffer full! Dropping N new samples").

**Evidence**:

Rate limiter applied to all messages:
```python
# auralis-web/backend/routers/system.py:174–178
allowed, error_msg = _rate_limiter.check_rate_limit(websocket)
if not allowed:
    await send_error_response(websocket, "rate_limit_exceeded", error_msg)
    continue  # buffer_full is silently dropped from backend's perspective
```

Flow control per chunk (hysteresis-gated):
```typescript
// auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:447–453
if (fillPct > 75 && !flowPausedRef.current) {
  flowPausedRef.current = true;
  wsSendRef.current({ type: 'buffer_full', data: {} });
}
```

**Impact**: Intermittent silent PCM frame drops when rate-limited flow-control messages are discarded, especially on resource-constrained machines. The bug is self-amplifying: dropped `buffer_full` → more chunks arrive → buffer overflows → more samples dropped → audible gaps.

**Suggested Fix**: Exempt flow-control messages from the rate limiter by checking message type before applying the limit:

```python
# auralis-web/backend/routers/system.py
# Before rate limit check:
if message.get("type") in ("buffer_full", "buffer_ready", "ping", "heartbeat"):
    pass  # infrastructure signals exempt from rate limiting
else:
    allowed, error_msg = _rate_limiter.check_rate_limit(websocket)
    if not allowed:
        await send_error_response(websocket, "rate_limit_exceeded", error_msg)
        continue
```

---

## Summary Table

| ID | Title | Severity | Boundary |
|----|-------|----------|----------|
| INT-13 | AudioWorklet hardcodes stereo — mono plays at half speed | HIGH | `AudioPlaybackEngine.ts:381` → `audio-worklet-processor.js:60` |
| INT-14 | Blob binary frame race condition drops PCM frames on Safari | MEDIUM | `WebSocketContext.tsx:285–287` (async null race) |
| INT-15 | `usePlayNormal` missing disconnect recovery — stale or dual engine | MEDIUM | `WebSocketContext.tsx:325` → `usePlayNormal.ts` (no disconnect effect) |
| INT-16 | Seek trim `chunk_interval` sourced from `getattr` fallback | LOW | `audio_stream_controller.py:1511` → `ChunkedAudioProcessor` |
| INT-17 | Flow-control messages counted against rate limiter budget | LOW | `usePlayEnhanced.ts:450` → `system.py:174` |

---

## Confirmed Clean (No Issues Found)

- **Sample rate consistency**: Backend sends `sample_rate` in `audio_stream_start`; frontend creates `AudioContext({ sampleRate: sourceSampleRate })`; PCMStreamBuffer stores it. Match confirmed for both enhanced and normal paths.
- **Binary frame format**: `_send_pcm_chunk` flattens to 1D float32, sends JSON metadata then raw bytes. Frontend `WebSocketContext` pairs `audio_chunk_meta` + next binary frame as `audio_chunk` with `pcm_binary: ArrayBuffer`. `decodeBinaryPCM` interprets as `Float32Array` (little-endian native). Consistent.
- **Chunk crossfade math**: Server-side equal-power crossfade (cos²/sin²) at 200ms. `crossfade_samples=0` sent to client prevents double-apply. Sum-to-unity verified.
- **Error propagation**: Chunk processing failure sends `audio_stream_error` with `recovery_position`; frontend `handleStreamError` dispatches `setStreamingError` and calls `cleanupStreaming`. Covered for both enhanced and normal paths.
- **Seek pause/flow events reset**: `system.py:641–648` resets both `_stream_pause_events` and `_stream_flow_events` before starting seek task, preventing stale paused state from blocking new stream.
- **Rapid skip race condition**: `_active_streaming_tasks_lock` ensures atomic cancel-of-old + create-of-new task under a single lock acquisition, preventing orphaned tasks.
- **`usePlayEnhanced` reconnect**: Mount-based subscriptions survive WS reconnect via `singletonSubscriptions` singleton; disconnect handler clears stale engine state before new stream starts.

## Notes on Known Issues (Not Re-Filed)

- **#2742** (seek path skips look-ahead pipeline): Confirmed still present in `stream_enhanced_audio_from_position`. Not re-filed per dedup rules.
- **#2734** (`overlap_duration` hardcoded to 5): Module constant confirmed. Not re-filed.
- **#2750** (`get_full_processed_audio_path` crossfade issue): Not encountered in this flow — streaming uses `_stream_processed_chunk`. Not re-filed.
