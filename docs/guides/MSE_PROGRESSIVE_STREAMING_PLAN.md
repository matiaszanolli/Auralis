# MSE Progressive Streaming Implementation Plan

**Goal**: Eliminate the 17-18 second first-playback delay by streaming audio chunks progressively as they're processed.

**Status**: 📋 Planning Phase
**Estimated Time**: 1-2 days
**Complexity**: High (requires significant frontend changes)

---

## 🎯 Objective

**Current Problem**:
- First playback takes 17-18s while all chunks are processed
- Browser needs complete file before playback starts
- User sees long delay before hearing audio

**Desired Solution**:
- Start playback within 1-2 seconds (first chunk only)
- Stream remaining chunks progressively
- Seamless playback while background processes

---

## 🔧 Technical Approach: Media Source Extensions (MSE)

### What is MSE?

Media Source Extensions is a Web API that allows JavaScript to feed media data to HTML5 media elements progressively.

**Key Features**:
- ✅ Progressive streaming (feed chunks as ready)
- ✅ Adaptive bitrate possible
- ✅ Full control over buffering
- ✅ Supported by modern browsers

**Browser Support**:
- ✅ Chrome/Edge (full support)
- ✅ Firefox (full support)
- ✅ Safari (partial support)
- ❌ iOS Safari (limited support)

---

## 📐 Architecture Design

### High-Level Flow

```
User clicks play
    ↓
Process ONLY first chunk (~1s)
    ↓
Start MSE playback immediately
    ↓
User hears audio (1-2 SECONDS)
    ↓
Background: Stream next chunks as processed
    ↓
Append to MediaSource buffer
    ↓
Seamless continuous playback
```

### Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      FRONTEND (React)                       │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  MSEAudioPlayer Component                          │    │
│  │  - MediaSource API                                 │    │
│  │  - SourceBuffer management                         │    │
│  │  - Chunk appending logic                           │    │
│  │  - Progress tracking                               │    │
│  └────────────────────────────────────────────────────┘    │
│                          ↓                                   │
│                  Fetch chunks progressively                  │
│                          ↓                                   │
└──────────────────────────┼──────────────────────────────────┘
                           │
                           ↓ WebSocket or HTTP/2
┌──────────────────────────┼──────────────────────────────────┐
│                      BACKEND (Python)                       │
│                          │                                   │
│  ┌───────────────────────┴──────────────────────────────┐  │
│  │  Progressive Chunk Endpoint                          │  │
│  │  /api/player/stream_chunk/{track_id}/{chunk_index}   │  │
│  │                                                        │  │
│  │  - Process chunk on-demand                           │  │
│  │  - Return raw WAV/WebM chunk                         │  │
│  │  - Cache processed chunks                            │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  ChunkedAudioProcessor (Enhanced)                     │  │
│  │  - Process chunks independently                      │  │
│  │  - Align chunk boundaries for MSE                    │  │
│  │  - Maintain processing context                       │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 🔨 Implementation Steps

### Phase 1: Backend Changes (4-6 hours)

#### 1.1 Create Chunk Streaming Endpoint
```python
@app.get("/api/player/stream_chunk/{track_id}/{chunk_index}")
async def stream_chunk(
    track_id: int,
    chunk_index: int,
    enhanced: bool = False,
    preset: str = "adaptive",
    intensity: float = 1.0
):
    """
    Stream a single processed chunk.

    Returns raw audio chunk in format suitable for MSE (WebM or MP4).
    """
    processor = ChunkedAudioProcessor(track_id, filepath, preset, intensity)

    # Check cache
    cache_key = processor._get_cache_key(chunk_index)
    cached_chunk = chunk_cache.get(cache_key)

    if cached_chunk and Path(cached_chunk).exists():
        # Return cached chunk
        return FileResponse(cached_chunk, media_type="audio/webm")

    # Process chunk on-demand
    chunk_path = processor.process_chunk(chunk_index)

    # Convert to WebM for MSE compatibility
    webm_path = convert_to_webm(chunk_path)

    return FileResponse(webm_path, media_type="audio/webm")
```

#### 1.2 Update ChunkedAudioProcessor
- Add WebM/MP4 output support (MSE requires specific formats)
- Ensure chunk boundaries align with codec requirements
- Add chunk metadata (duration, timestamp, etc.)

#### 1.3 Add Format Conversion
```python
def convert_to_webm(wav_path: str) -> str:
    """Convert WAV chunk to WebM for MSE compatibility"""
    import subprocess

    webm_path = wav_path.replace('.wav', '.webm')

    # Use ffmpeg to convert
    subprocess.run([
        'ffmpeg', '-i', wav_path,
        '-c:a', 'libopus',  # Opus codec for WebM
        '-b:a', '192k',
        webm_path
    ], check=True)

    return webm_path
```

### Phase 2: Frontend Changes (6-8 hours)

#### 2.1 Create MSEAudioPlayer Component

```typescript
// auralis-web/frontend/src/components/player/MSEAudioPlayer.tsx

import React, { useRef, useEffect, useState } from 'react';

interface MSEAudioPlayerProps {
  trackId: number;
  enhanced: boolean;
  preset: string;
  intensity: number;
  onReady?: () => void;
  onError?: (error: Error) => void;
}

export const MSEAudioPlayer: React.FC<MSEAudioPlayerProps> = ({
  trackId,
  enhanced,
  preset,
  intensity,
  onReady,
  onError
}) => {
  const audioRef = useRef<HTMLAudioElement>(null);
  const mediaSourceRef = useRef<MediaSource | null>(null);
  const sourceBufferRef = useRef<SourceBuffer | null>(null);

  const [isReady, setIsReady] = useState(false);
  const [buffering, setBuffering] = useState(false);
  const [currentChunk, setCurrentChunk] = useState(0);

  useEffect(() => {
    initializeMediaSource();
    return () => cleanup();
  }, [trackId, enhanced, preset, intensity]);

  const initializeMediaSource = async () => {
    if (!audioRef.current) return;

    // Create MediaSource
    const mediaSource = new MediaSource();
    mediaSourceRef.current = mediaSource;

    // Attach to audio element
    audioRef.current.src = URL.createObjectURL(mediaSource);

    // Wait for MediaSource to open
    mediaSource.addEventListener('sourceopen', async () => {
      try {
        // Create SourceBuffer
        const sourceBuffer = mediaSource.addSourceBuffer('audio/webm; codecs="opus"');
        sourceBufferRef.current = sourceBuffer;

        // Fetch and append first chunk
        await fetchAndAppendChunk(0);

        setIsReady(true);
        onReady?.();

        // Start fetching remaining chunks in background
        fetchRemainingChunks();

      } catch (error) {
        console.error('Failed to initialize MSE:', error);
        onError?.(error as Error);
      }
    });
  };

  const fetchAndAppendChunk = async (chunkIndex: number) => {
    const sourceBuffer = sourceBufferRef.current;
    if (!sourceBuffer) return;

    setBuffering(true);

    try {
      // Fetch chunk from backend
      const response = await fetch(
        `/api/player/stream_chunk/${trackId}/${chunkIndex}?` +
        `enhanced=${enhanced}&preset=${preset}&intensity=${intensity}`
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch chunk ${chunkIndex}`);
      }

      const chunkData = await response.arrayBuffer();

      // Wait for previous append to finish
      await waitForSourceBuffer(sourceBuffer);

      // Append chunk to buffer
      sourceBuffer.appendBuffer(chunkData);

      setCurrentChunk(chunkIndex);
      console.log(`Chunk ${chunkIndex} appended successfully`);

    } catch (error) {
      console.error(`Failed to fetch/append chunk ${chunkIndex}:`, error);
      onError?.(error as Error);
    } finally {
      setBuffering(false);
    }
  };

  const waitForSourceBuffer = (sourceBuffer: SourceBuffer): Promise<void> => {
    return new Promise((resolve) => {
      if (!sourceBuffer.updating) {
        resolve();
      } else {
        sourceBuffer.addEventListener('updateend', () => resolve(), { once: true });
      }
    });
  };

  const fetchRemainingChunks = async () => {
    // Determine total chunks (get from metadata or calculate)
    const totalChunks = await getTotalChunks();

    for (let i = 1; i < totalChunks; i++) {
      // Fetch next chunk
      await fetchAndAppendChunk(i);

      // Check if we're getting ahead of playback
      // Wait if buffer is full enough
      await waitForBufferSpace();
    }

    // Close MediaSource when all chunks loaded
    if (mediaSourceRef.current?.readyState === 'open') {
      mediaSourceRef.current.endOfStream();
    }
  };

  const waitForBufferSpace = async () => {
    const audio = audioRef.current;
    const sourceBuffer = sourceBufferRef.current;

    if (!audio || !sourceBuffer) return;

    // Wait if we have > 60s of buffer ahead
    while (true) {
      const buffered = sourceBuffer.buffered;
      if (buffered.length === 0) break;

      const bufferEnd = buffered.end(buffered.length - 1);
      const currentTime = audio.currentTime;

      if (bufferEnd - currentTime < 60) {
        break; // Need more buffer
      }

      // Wait a bit before checking again
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  };

  const getTotalChunks = async (): Promise<number> => {
    // Fetch metadata from backend
    const response = await fetch(`/api/library/tracks/${trackId}`);
    const track = await response.json();
    const duration = track.duration;

    return Math.ceil(duration / 30); // 30s chunks
  };

  const cleanup = () => {
    if (mediaSourceRef.current?.readyState === 'open') {
      mediaSourceRef.current.endOfStream();
    }
    if (audioRef.current?.src) {
      URL.revokeObjectURL(audioRef.current.src);
    }
  };

  return (
    <div>
      <audio
        ref={audioRef}
        controls
        onWaiting={() => setBuffering(true)}
        onCanPlay={() => setBuffering(false)}
      />
      {buffering && <div>Loading chunk {currentChunk}...</div>}
    </div>
  );
};
```

#### 2.2 Integrate MSEAudioPlayer with BottomPlayerBar

```typescript
// Update BottomPlayerBarConnected to use MSE when enhanced is true

const audioElement = enhancementSettings.enabled ? (
  <MSEAudioPlayer
    trackId={currentTrack.id}
    enhanced={enhancementSettings.enabled}
    preset={enhancementSettings.preset}
    intensity={enhancementSettings.intensity}
    onReady={() => setIsReady(true)}
    onError={(err) => showError(err.message)}
  />
) : (
  <audio ref={audioRef} src={...} />
);
```

#### 2.3 Add Fallback for Unsupported Browsers

```typescript
const supportsMediaSource = typeof MediaSource !== 'undefined';

if (!supportsMediaSource) {
  // Fall back to current FileResponse approach
  console.warn('MSE not supported, using fallback');
  return <audio ref={audioRef} src={originalStreamUrl} />;
}
```

### Phase 3: Testing & Optimization (2-4 hours)

#### 3.1 Test Scenarios
- ✅ First playback starts quickly (1-2s)
- ✅ Chunks stream progressively
- ✅ No gaps between chunks
- ✅ Seeking works correctly
- ✅ Preset/intensity changes work
- ✅ Fallback to non-MSE works

#### 3.2 Optimization
- Buffer management (prevent memory bloat)
- Chunk prefetching strategy
- Error recovery (retry failed chunks)
- Progress indicators

#### 3.3 Browser Compatibility Testing
- Chrome/Edge
- Firefox
- Safari (desktop)
- Mobile browsers

---

## 🚧 Challenges & Solutions

### Challenge 1: MSE Format Requirements
**Problem**: MSE requires specific container formats (WebM, MP4)
**Solution**: Convert WAV chunks to WebM with Opus codec using ffmpeg

### Challenge 2: Chunk Alignment
**Problem**: Audio codec requires aligned chunk boundaries
**Solution**: Ensure chunks start on codec frame boundaries

### Challenge 3: Seeking with Progressive Loading
**Problem**: User seeks to timestamp that hasn't loaded yet
**Solution**:
- Pause playback
- Fetch target chunk immediately
- Resume from new position

### Challenge 4: Safari/iOS Limitations
**Problem**: Safari has limited MSE support
**Solution**: Detect browser, fall back to current approach

### Challenge 5: Memory Management
**Problem**: Buffering entire song uses lots of RAM
**Solution**: Remove old chunks from buffer as playback progresses

---

## 📊 Expected Performance

### First Playback (MSE)
- Process first chunk: ~1 second
- Start playback: ~1-2 seconds total
- Remaining chunks: Stream in background
- **User Experience**: Near-instant playback!

### Second Playback (Cached)
- All chunks cached: Instant (0s)
- Same as current implementation

### Comparison

| Metric | Current | MSE | Improvement |
|--------|---------|-----|-------------|
| First playback | 17-18s | 1-2s | **89% faster** |
| Cached playback | 0s | 0s | Same |
| Complexity | Low | High | - |
| Browser support | 100% | 95% | - |

---

## 🛠️ Prerequisites

### Backend
- ✅ ffmpeg installed
- ✅ WebM/Opus encoding support
- ✅ FastAPI async endpoints

### Frontend
- ✅ Modern browser (Chrome/Firefox/Safari)
- ✅ MediaSource API support
- ✅ React hooks for state management

---

## 📝 Implementation Checklist

### Backend
- [ ] Create `/api/player/stream_chunk/{track_id}/{chunk_index}` endpoint
- [ ] Add WebM conversion function
- [ ] Update ChunkedAudioProcessor for MSE compatibility
- [ ] Add chunk metadata endpoint
- [ ] Test chunk boundary alignment

### Frontend
- [ ] Create MSEAudioPlayer component
- [ ] Implement MediaSource initialization
- [ ] Implement SourceBuffer management
- [ ] Add progressive chunk fetching
- [ ] Add buffer management (remove old chunks)
- [ ] Implement seeking with MSE
- [ ] Add fallback for unsupported browsers
- [ ] Integrate with BottomPlayerBar
- [ ] Add loading/buffering indicators

### Testing
- [ ] Test first playback (1-2s target)
- [ ] Test cached playback (instant)
- [ ] Test seeking
- [ ] Test preset/intensity changes
- [ ] Test on Chrome
- [ ] Test on Firefox
- [ ] Test on Safari
- [ ] Test fallback mode

### Documentation
- [ ] Update CLAUDE.md with MSE info
- [ ] Add user guide for browser requirements
- [ ] Document MSE vs fallback behavior

---

## 🎯 Success Criteria

1. ✅ **First playback < 3 seconds** (target: 1-2s)
2. ✅ **No audible gaps** between chunks
3. ✅ **Seeking works** at any position
4. ✅ **90%+ browser compatibility** (with fallback)
5. ✅ **Memory usage < 200MB** during playback
6. ✅ **Cached playback still instant**

---

## 🚀 Deployment Strategy

### Phase 1: Feature Flag
```typescript
const USE_MSE_STREAMING = process.env.REACT_APP_USE_MSE === 'true';
```

### Phase 2: Gradual Rollout
- Enable for 10% of users
- Monitor error rates
- Collect performance metrics
- Increase to 50%, then 100%

### Phase 3: Make Default
- MSE becomes primary method
- Fallback still available
- Remove feature flag

---

## 📈 Estimated Timeline

| Phase | Task | Time | Dependencies |
|-------|------|------|--------------|
| 1 | Backend chunk endpoint | 2h | ffmpeg |
| 2 | WebM conversion | 1h | - |
| 3 | MSEAudioPlayer component | 4h | - |
| 4 | Integration with UI | 2h | Phase 3 |
| 5 | Testing & debugging | 3h | All above |
| 6 | Browser compatibility | 2h | Phase 5 |
| 7 | Documentation | 1h | - |
| **Total** | | **15h** | **~2 days** |

---

## 🎯 Next Steps

1. **Review this plan** - Ensure approach is sound
2. **Install ffmpeg** - Ensure WebM encoding available
3. **Test MSE basics** - Create minimal MSE example
4. **Start Phase 1** - Backend chunk endpoint
5. **Iterate** - Build incrementally with testing

---

**Status**: 📋 **Planning Complete - Ready to Implement**
**Recommendation**: Start with minimal MSE prototype to validate approach

**Created**: October 22, 2025
**Estimated Start**: When ready to proceed
