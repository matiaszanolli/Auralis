# Beta.7 - MSE Frontend Migration Plan

**Date**: October 30, 2025
**Status**: 🚧 In Progress
**Priority**: P0 - Critical for instant preset switching

---

## 🎯 **Objective**

Complete the MSE (Media Source Extensions) frontend migration to unlock instant preset switching and eliminate the 2-5 second delay when changing presets.

---

## 📊 **Current State (Beta.7)**

### ✅ **Backend - READY**
- MSE streaming endpoints: `/api/mse_streaming/chunk/{track_id}/{chunk_idx}`
- Unified streaming: `/api/unified_streaming/chunk/`
- Multi-tier buffer system (L1/L2/L3) with 99 MB total cache
- Branch predictor for learning user patterns
- ChunkedAudioProcessor: 30s chunks with 3s crossfade
- WebM/Opus encoding pipeline

### ❌ **Frontend - INCOMPLETE**
- Still using HTML5 `<audio>` element with `src` attribute
- Calls `/api/player/stream/{track_id}` which returns **full files**
- Every preset change = reload entire file (2-5 seconds)
- No progressive chunk loading
- Multi-tier buffer system **completely bypassed**

### 🐛 **The Problem**
1. User plays track with "adaptive" preset
2. User switches to "warm" preset
3. Frontend reloads URL: `/api/player/stream/{track_id}?enhanced=true&preset=warm&intensity=1`
4. Backend processes **ALL chunks** (9 chunks × 30s = 270s of audio)
5. User waits 2-5 seconds for processing
6. **Multi-tier buffer is never consulted**

---

## 🔧 **The Solution: MSE Migration**

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React)                          │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ BottomPlayerBarConnected.tsx                       │    │
│  │                                                     │    │
│  │  [MSE Controller]                                  │    │
│  │    ↓                                              │    │
│  │  MediaSource API                                   │    │
│  │    ↓                                              │    │
│  │  SourceBuffer (WebM/Opus)                         │    │
│  │    ↓                                              │    │
│  │  <audio> element (plays from buffer)              │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↕                                    │
│                    HTTP Fetch                               │
└─────────────────────────────────────────────────────────────┘
                          ↕
┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│                                                              │
│  GET /api/mse_streaming/chunk/{track_id}/{chunk_idx}       │
│    ?preset=warm&intensity=1                                 │
│                         ↓                                    │
│  [Multi-Tier Buffer Check]                                  │
│    ↓                                                        │
│  L1 Cache (18 MB) - Current + next chunk, high-prob presets│
│    ↓ (miss)                                                │
│  L2 Cache (36 MB) - Branch scenarios, predicted switches   │
│    ↓ (miss)                                                │
│  L3 Cache (45 MB) - Long-term section cache                │
│    ↓ (miss)                                                │
│  [ChunkedAudioProcessor] - Process on-demand                │
│    ↓                                                        │
│  Return WebM/Opus chunk (< 100ms)                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 📝 **Implementation Tasks**

### Phase 1: MSE Setup in Frontend (4-6 hours)

**File**: `auralis-web/frontend/src/components/BottomPlayerBarConnected.tsx`

#### 1.1 Create MSE Controller Hook
```typescript
// New file: auralis-web/frontend/src/hooks/useMSEController.ts
export function useMSEController() {
  const [mediaSource, setMediaSource] = useState<MediaSource | null>(null);
  const [sourceBuffer, setSourceBuffer] = useState<SourceBuffer | null>(null);
  const [isReady, setIsReady] = useState(false);

  // Initialize MediaSource
  useEffect(() => {
    const ms = new MediaSource();
    const objectUrl = URL.createObjectURL(ms);

    ms.addEventListener('sourceopen', () => {
      const sb = ms.addSourceBuffer('audio/webm; codecs="opus"');
      setSourceBuffer(sb);
      setIsReady(true);
    });

    setMediaSource(ms);
    return () => URL.revokeObjectURL(objectUrl);
  }, []);

  return { mediaSource, sourceBuffer, isReady };
}
```

#### 1.2 Update Audio Element
```typescript
// Replace current <audio src={streamUrl}>
const { mediaSource, sourceBuffer, isReady } = useMSEController();

<audio
  ref={audioRef}
  src={mediaSource ? URL.createObjectURL(mediaSource) : undefined}
  // ... other props
/>
```

#### 1.3 Chunk Loading Logic
```typescript
async function loadChunk(trackId: number, chunkIdx: number, preset: string, intensity: number) {
  const response = await fetch(
    `/api/mse_streaming/chunk/${trackId}/${chunkIdx}?preset=${preset}&intensity=${intensity}`
  );

  const arrayBuffer = await response.arrayBuffer();

  if (sourceBuffer && !sourceBuffer.updating) {
    sourceBuffer.appendBuffer(arrayBuffer);
  }
}
```

---

### Phase 2: Progressive Loading (4-6 hours)

#### 2.1 Initial Playback
```typescript
async function startPlayback(trackId: number, preset: string) {
  // Load first chunk immediately
  await loadChunk(trackId, 0, preset, 1.0);

  // Start playback as soon as first chunk loads
  audioRef.current?.play();

  // Prefetch next 2 chunks in background
  Promise.all([
    loadChunk(trackId, 1, preset, 1.0),
    loadChunk(trackId, 2, preset, 1.0)
  ]);
}
```

#### 2.2 Continuous Buffering
```typescript
// Monitor playback position
audioRef.current.addEventListener('timeupdate', () => {
  const currentTime = audioRef.current.currentTime;
  const currentChunk = Math.floor(currentTime / CHUNK_DURATION);

  // Prefetch next chunk if needed
  if (!isChunkLoaded(currentChunk + 1)) {
    loadChunk(trackId, currentChunk + 1, currentPreset, 1.0);
  }
});
```

---

### Phase 3: Preset Switching (4-6 hours)

#### 3.1 Instant Preset Switch
```typescript
async function switchPreset(newPreset: string) {
  const currentTime = audioRef.current.currentTime;
  const currentChunk = Math.floor(currentTime / CHUNK_DURATION);

  // Clear source buffer
  if (sourceBuffer && !sourceBuffer.updating) {
    sourceBuffer.remove(0, sourceBuffer.buffered.end(0));
  }

  // Load new preset chunk at current position
  await loadChunk(trackId, currentChunk, newPreset, 1.0);

  // Resume playback at same position
  audioRef.current.currentTime = currentTime;
  audioRef.current.play();

  // Prefetch next chunks with new preset
  loadChunk(trackId, currentChunk + 1, newPreset, 1.0);
}
```

#### 3.2 Multi-Tier Buffer Integration
The backend will automatically:
- Check L1 cache for high-probability presets (instant if cached)
- Check L2 cache for predicted switches (100-200ms if cached)
- Process on-demand if not cached (500ms-2s)
- Learn patterns via branch predictor for future pre-caching

---

### Phase 4: Error Handling & Edge Cases (2-4 hours)

#### 4.1 Buffer State Management
```typescript
sourceBuffer.addEventListener('updateend', () => {
  // Buffer update complete, safe to append more data
  if (pendingChunks.length > 0) {
    const nextChunk = pendingChunks.shift();
    sourceBuffer.appendBuffer(nextChunk);
  }
});
```

#### 4.2 Seek Handling
```typescript
function handleSeek(newTime: number) {
  const targetChunk = Math.floor(newTime / CHUNK_DURATION);

  // Clear buffer
  sourceBuffer.remove(0, sourceBuffer.buffered.end(0));

  // Load chunk at seek position
  loadChunk(trackId, targetChunk, currentPreset, 1.0);

  // Update audio element time
  audioRef.current.currentTime = newTime;
}
```

#### 4.3 Network Errors
```typescript
try {
  await loadChunk(trackId, chunkIdx, preset, 1.0);
} catch (error) {
  console.error(`Failed to load chunk ${chunkIdx}:`, error);

  // Retry with exponential backoff
  await retryWithBackoff(() => loadChunk(trackId, chunkIdx, preset, 1.0));
}
```

---

### Phase 5: Testing & Validation (2-4 hours)

#### 5.1 Unit Tests
```typescript
describe('MSE Controller', () => {
  it('initializes MediaSource and SourceBuffer', () => {
    // Test MSE setup
  });

  it('loads chunks progressively', async () => {
    // Test chunk loading
  });

  it('switches presets instantly', async () => {
    // Test preset switching < 100ms
  });
});
```

#### 5.2 Integration Tests
- Test with real backend endpoints
- Verify multi-tier buffer cache hits
- Measure preset switch latency

#### 5.3 Performance Benchmarks
- Initial playback start: < 100ms (target)
- Preset switch (cached): < 100ms (target)
- Preset switch (uncached): < 500ms (target)
- Chunk buffering: Stay 2-3 chunks ahead

---

## 📊 **Success Metrics**

### Before (Current HTML5 Audio)
- ❌ Preset switch: 2-5 seconds (full file processing)
- ❌ Multi-tier buffer: Not used
- ❌ Branch predictor: Not learning

### After (MSE Migration)
- ✅ Preset switch (L1 cached): < 100ms
- ✅ Preset switch (L2 cached): 100-200ms
- ✅ Preset switch (uncached): 500ms-2s
- ✅ Multi-tier buffer: Active and learning
- ✅ Playback start: < 100ms (first chunk only)

---

## 🛠️ **Development Timeline**

**Total Estimate**: 16-24 hours

| Phase | Task | Hours | Status |
|-------|------|-------|--------|
| 1 | MSE Setup | 4-6 | ⏳ Pending |
| 2 | Progressive Loading | 4-6 | ⏳ Pending |
| 3 | Preset Switching | 4-6 | ⏳ Pending |
| 4 | Error Handling | 2-4 | ⏳ Pending |
| 5 | Testing | 2-4 | ⏳ Pending |

---

## 🚀 **Quick Start Guide**

### Step 1: Verify Backend is Ready
```bash
# Check MSE endpoints exist
curl http://localhost:8765/api/mse_streaming/chunk/1/0?preset=adaptive&intensity=1

# Should return WebM/Opus chunk
```

### Step 2: Create MSE Hook
```bash
cd auralis-web/frontend/src/hooks
# Create useMSEController.ts
```

### Step 3: Update Player Component
```bash
# Modify BottomPlayerBarConnected.tsx
# Replace <audio src={url}> with MSE implementation
```

### Step 4: Test Locally
```bash
python launch-auralis-web.py --dev
# Open http://localhost:3000
# Test preset switching
```

---

## 📚 **References**

### Backend Components (Already Complete)
- `auralis-web/backend/routers/mse_streaming.py` - MSE chunk serving
- `auralis-web/backend/routers/unified_streaming.py` - Unified streaming router
- `auralis-web/backend/multi_tier_buffer.py` - L1/L2/L3 caching (765 lines)
- `auralis-web/backend/multi_tier_worker.py` - Background worker
- `auralis/player/chunked_processor.py` - Chunk processing

### Frontend Files to Modify
- `auralis-web/frontend/src/components/BottomPlayerBarConnected.tsx` (current player)
- `auralis-web/frontend/src/hooks/` (new: useMSEController.ts)
- `auralis-web/frontend/src/services/` (new: mseStreamingService.ts)

### Documentation
- [MDN: Media Source Extensions](https://developer.mozilla.org/en-US/docs/Web/API/Media_Source_Extensions_API)
- [WebM Container Format](https://www.webmproject.org/docs/container/)
- Beta.4 Implementation: `docs/sessions/oct27_mse_integration/`

---

## ⚠️ **Known Challenges**

1. **Browser Compatibility**: MSE requires modern browsers (Chrome 23+, Firefox 42+, Safari 8+)
2. **Memory Management**: Need to clear old buffer chunks to avoid memory leaks
3. **Codec Support**: WebM/Opus not supported in all browsers (Safari needs MP4/AAC fallback)
4. **Seek Accuracy**: Chunk boundaries may not align perfectly with seek positions

**Mitigations**:
- Feature detection: Fallback to HTML5 audio if MSE not supported
- Buffer cleanup: Remove chunks > 5 minutes behind playback position
- Codec fallback: Serve MP4/AAC for Safari (future enhancement)
- Seek alignment: Use chunk boundaries (30s intervals) for instant seeking

---

## 🎯 **Next Steps**

1. ✅ Document current state (this file)
2. ⏳ Create `useMSEController.ts` hook
3. ⏳ Update `BottomPlayerBarConnected.tsx`
4. ⏳ Test with backend MSE endpoints
5. ⏳ Measure performance vs. targets
6. ⏳ Document results in Beta.7 release notes

---

**Status**: Ready to begin Phase 1 implementation.
