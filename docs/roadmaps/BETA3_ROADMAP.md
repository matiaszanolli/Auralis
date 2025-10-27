# Beta.3 Development Roadmap

**Target Release**: TBD
**Focus**: Seamless UX & Performance

---

## 🎯 P0 Critical Issues (Must Fix)

### 1. MSE-Based Progressive Streaming - **MAXIMUM PRIORITY**

**Status**: 🚨 **CRITICAL UX ISSUE** - Blocking smooth user experience

**Problem**:
Current architecture forces 2-5 second buffering pause every time user changes enhancement presets during playback. This severely impacts the user experience when experimenting with different sound profiles.

**User Impact**:
- **HIGH** - Affects every preset change during playback
- Users frustrated by constant buffering delays
- Makes preset experimentation painful
- Diminishes value of having multiple presets

**Current Behavior**:
```
User clicks "Punchy" preset:
  1. Audio pauses ⏸️
  2. Frontend loads new stream URL
  3. Backend processes entire track (2-5 seconds) ⏳
  4. User waits... and waits... 😤
  5. Playback finally resumes ▶️
```

**Target Behavior**:
```
User clicks "Punchy" preset:
  1. Audio switches instantly ⚡
  2. Multi-tier buffer serves pre-processed chunk
  3. Seamless transition (< 100ms) ✨
  4. User happy! 😊
```

**Technical Solution**: Implement Media Source Extensions (MSE) based progressive streaming

**Implementation Details**:

### Phase 1: Backend Chunk Streaming API (2-3 days)

**New Endpoint**: `GET /api/player/stream/{track_id}/chunk/{chunk_idx}`

```python
@router.get("/api/player/stream/{track_id}/chunk/{chunk_idx}")
async def stream_chunk(
    track_id: int,
    chunk_idx: int,
    preset: str = "adaptive",
    intensity: float = 1.0
):
    """
    Stream a single processed audio chunk.

    Utilizes multi-tier buffer for instant delivery:
    - L1 Cache: 0ms latency (current + next chunk)
    - L2 Cache: 100-200ms latency (predicted presets)
    - L3 Cache: 500ms-2s latency (long-term buffer)
    """
    # Check multi-tier buffer
    chunk_data = await multi_tier_buffer.get_chunk(
        track_id=track_id,
        preset=preset,
        chunk_idx=chunk_idx,
        intensity=intensity
    )

    if chunk_data:
        # Cache hit - instant delivery!
        logger.info(f"Cache hit: L{chunk_data.tier} cache ({chunk_data.latency}ms)")
        return Response(
            content=chunk_data.audio_bytes,
            media_type="audio/wav",
            headers={
                "X-Cache-Tier": f"L{chunk_data.tier}",
                "X-Latency-Ms": str(chunk_data.latency),
                "Content-Length": str(len(chunk_data.audio_bytes))
            }
        )
    else:
        # Cache miss - process on demand
        chunk_data = await chunked_processor.process_chunk(
            track_id=track_id,
            chunk_idx=chunk_idx,
            preset=preset,
            intensity=intensity
        )
        return Response(content=chunk_data, media_type="audio/wav")
```

**Metadata Endpoint**: `GET /api/player/stream/{track_id}/metadata`

```python
@router.get("/api/player/stream/{track_id}/metadata")
async def get_stream_metadata(track_id: int):
    """
    Return stream metadata for MSE initialization.
    """
    track = library_manager.get_track(track_id)

    return {
        "track_id": track_id,
        "duration": track.duration,
        "sample_rate": 44100,
        "channels": 2,
        "chunk_duration": 30,
        "total_chunks": math.ceil(track.duration / 30),
        "mime_type": "audio/wav; codecs=pcm"
    }
```

### Phase 2: Frontend MSE Integration (3-4 days)

**Replace HTML5 Audio Element with MSE**:

```typescript
// New MSEPlayer class
class MSEPlayer {
    private mediaSource: MediaSource;
    private sourceBuffer: SourceBuffer;
    private audioElement: HTMLAudioElement;
    private currentTrackId: number;
    private currentPreset: string;
    private currentChunk: number = 0;

    async initialize(trackId: number, preset: string) {
        // Create MediaSource
        this.mediaSource = new MediaSource();
        this.audioElement.src = URL.createObjectURL(this.mediaSource);

        // Wait for source to open
        await new Promise(resolve => {
            this.mediaSource.addEventListener('sourceopen', resolve, { once: true });
        });

        // Create SourceBuffer
        this.sourceBuffer = this.mediaSource.addSourceBuffer('audio/wav; codecs=pcm');

        // Fetch metadata
        const metadata = await fetch(`/api/player/stream/${trackId}/metadata`);

        // Start streaming chunks
        this.startChunkStream(trackId, preset);
    }

    async startChunkStream(trackId: number, preset: string) {
        while (this.currentChunk < this.totalChunks) {
            // Fetch next chunk
            const response = await fetch(
                `/api/player/stream/${trackId}/chunk/${this.currentChunk}?preset=${preset}`
            );
            const chunkData = await response.arrayBuffer();

            // Append to SourceBuffer
            await this.appendChunk(chunkData);

            this.currentChunk++;
        }
    }

    async changePreset(newPreset: string) {
        // THIS IS THE MAGIC - No reload needed!
        this.currentPreset = newPreset;

        // Continue fetching chunks with new preset
        // Multi-tier buffer serves instantly from cache
        // User experiences seamless transition! ✨
    }

    private async appendChunk(chunkData: ArrayBuffer) {
        // Wait for SourceBuffer to be ready
        while (this.sourceBuffer.updating) {
            await new Promise(resolve => setTimeout(resolve, 10));
        }

        // Append chunk
        this.sourceBuffer.appendBuffer(chunkData);

        // Wait for append to complete
        await new Promise(resolve => {
            this.sourceBuffer.addEventListener('updateend', resolve, { once: true });
        });
    }
}
```

**Preset Switching Logic**:

```typescript
// When user clicks preset button
async function onPresetChange(newPreset: string) {
    const currentTime = player.currentTime;
    const currentChunk = Math.floor(currentTime / 30);

    // Update preset (no reload!)
    player.currentPreset = newPreset;

    // Continue streaming from current position with new preset
    // Multi-tier buffer has already pre-processed chunks for this preset
    // L1/L2 cache delivers instantly (0-200ms latency)

    // User doesn't even notice the switch! ⚡
}
```

### Phase 3: Multi-Tier Buffer Integration (1 day)

**Ensure buffer is triggered on playback start**:

```python
@router.post("/api/player/play")
async def play_audio():
    # Get current track
    track_id = player_state.current_track_id
    preset = player_state.current_preset
    current_chunk = player_state.current_chunk

    # Trigger multi-tier buffer update
    await multi_tier_buffer.update_on_playback(
        track_id=track_id,
        current_chunk=current_chunk,
        preset=preset
    )

    # This pre-processes:
    # - L1: Current + next chunk for current preset + high-probability presets
    # - L2: Branch scenarios (likely preset switches)
    # - L3: Long-term buffer for current preset

    return {"status": "playing"}
```

### Phase 4: Testing & Optimization (2-3 days)

**Browser Compatibility Testing**:
- Chrome/Chromium (primary)
- Firefox
- Safari (may have MSE limitations)
- Edge

**Performance Testing**:
- Measure preset switch latency (target: < 100ms)
- Test with different library sizes
- Memory usage profiling
- Network performance under different conditions

**Edge Cases**:
- Seeking during playback
- Rapid preset switching
- Network errors / chunk loading failures
- Browser tab backgrounding
- Very long tracks (>1 hour)

**Fallback Implementation**:
- Detect MSE support
- Fall back to current file-based streaming if MSE unavailable
- Progressive enhancement approach

---

## 📊 Expected Results

### Performance Metrics

| Metric | Before (Beta.2) | After (Beta.3) | Improvement |
|--------|-----------------|----------------|-------------|
| Preset switch latency | 2-5 seconds | < 100ms | **20-50x faster** |
| Initial playback start | ~2 seconds | ~500ms | **4x faster** |
| Memory usage | High (full files) | Low (chunks only) | **60-80% reduction** |
| Cache hit rate | 0% (no cache) | 80-90% (L1/L2) | **Huge win** |

### User Experience Impact

**Before (Beta.2)**:
- 😤 Frustrating preset switching
- 🐌 Long waits for buffering
- ⚠️ Disrupted listening experience
- 🤔 Users avoid changing presets

**After (Beta.3)**:
- ⚡ Instant preset switching
- ✨ Seamless transitions
- 🎵 Uninterrupted playback
- 😊 Users freely experiment with presets

---

## 🎯 Implementation Timeline

**Total Effort**: 8-12 days of focused development

**Week 1 (Days 1-5)**:
- ✅ Backend chunk streaming API (Days 1-2)
- ✅ MSE integration research & prototyping (Day 3)
- ✅ Frontend MSEPlayer implementation (Days 4-5)

**Week 2 (Days 6-10)**:
- ✅ Multi-tier buffer integration (Day 6)
- ✅ Browser compatibility testing (Days 7-8)
- ✅ Performance optimization (Days 9-10)

**Week 3 (Days 11-12)** (if needed):
- ✅ Bug fixes and edge cases
- ✅ Documentation
- ✅ Release preparation

**Target Release**: 2-3 weeks after Beta.2

---

## 🚨 Why This Is P0 (Maximum Priority)

**User Impact**: CRITICAL
- Affects core listening experience
- Makes preset feature nearly unusable
- Frustrates users during every session
- Diminishes product value

**Technical Readiness**: HIGH
- Multi-tier buffer already implemented
- Chunked processor ready
- Just need MSE glue layer

**Effort**: MEDIUM
- 2-3 weeks focused work
- Well-understood technology (MSE)
- Clear implementation path

**Business Impact**: HIGH
- Major UX improvement
- Differentiating feature (instant preset switching)
- Showcases technical sophistication
- Increases user satisfaction

---

## 📋 Other Beta.3 Priorities

### P1: High Priority

**2. Desktop Binary Build System**
- Fix electron-builder configuration issues
- Automate Beta.3 builds
- Ensure all platforms (Windows, Linux, macOS)

**3. UI/UX Polish**
- Album artwork display improvements
- Player controls refinement
- Loading states optimization

**4. Documentation**
- User guide
- Developer documentation
- API reference

### P2: Medium Priority

**5. Additional Presets**
- Add more enhancement profiles
- User-customizable presets
- Preset import/export

**6. Performance Optimization**
- Artist pagination further optimization
- Database query improvements
- Frontend bundle size reduction

### P3: Nice to Have

**7. Advanced Features**
- Playlist smart shuffle
- Lyrics display
- Audio visualization

---

## 📝 Success Criteria for Beta.3

**Must Have (P0)**:
- ✅ MSE-based streaming implemented
- ✅ Preset switching < 100ms latency
- ✅ Multi-tier buffer fully utilized
- ✅ Works on Chrome/Firefox/Edge
- ✅ No regressions in existing features

**Should Have (P1)**:
- ✅ Desktop binaries building correctly
- ✅ UI polish complete
- ✅ Documentation updated

**Nice to Have (P2/P3)**:
- Additional presets
- Further performance gains
- Advanced features

---

## 🎯 Release Criteria

Beta.3 can be released when:
1. ✅ MSE streaming working and tested
2. ✅ Preset switching is instant (< 100ms)
3. ✅ No critical bugs
4. ✅ All Beta.2 features still working
5. ✅ Desktop binaries built for all platforms
6. ✅ Documentation complete

---

## 📚 References

**Technical Documentation**:
- [PRESET_SWITCHING_LIMITATION.md](PRESET_SWITCHING_LIMITATION.md) - Problem analysis
- [docs/guides/MSE_PROGRESSIVE_STREAMING_PLAN.md](docs/guides/MSE_PROGRESSIVE_STREAMING_PLAN.md) - Implementation guide
- [auralis-web/backend/multi_tier_buffer.py](auralis-web/backend/multi_tier_buffer.py) - Buffer system

**MSE Resources**:
- [MDN: Media Source Extensions API](https://developer.mozilla.org/en-US/docs/Web/API/Media_Source_Extensions_API)
- [MSE Byte Stream Format: WAV](https://www.w3.org/2013/12/byte-stream-format-registry/isobmff-byte-stream-format.html)

---

**Last Updated**: October 26, 2025
**Status**: PLANNING - Ready for implementation
**Priority**: 🚨 **P0 - MAXIMUM PRIORITY** 🚨
**Target**: Beta.3 Release (2-3 weeks after Beta.2)

