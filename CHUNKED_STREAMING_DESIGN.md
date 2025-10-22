# Chunked Streaming Design for Real-Time Enhancement

**Problem**: Current implementation processes the entire audio file before streaming, causing 5-10 second delays.

**Solution**: Process audio in 30-second chunks with crossfade overlap to avoid audible jumps.

---

## 🎯 Design Goals

1. **Start playing within 1-2 seconds** (process only first chunk)
2. **No audible gaps** between chunks (crossfade overlap)
3. **Background processing** of remaining chunks
4. **Smart caching** of processed chunks
5. **Efficient memory usage** (don't load entire file)

---

## 📐 Architecture

### Current Flow (Slow):
```
User clicks play
    ↓
Load entire audio file (385s = ~65MB)
    ↓
Process entire file with HybridProcessor (~5-10s)
    ↓
Save entire processed file to disk
    ↓
Start streaming
    ↓
User hears audio (AFTER 5-10 SECONDS)
```

### New Chunked Flow (Fast):
```
User clicks play
    ↓
Load ONLY first 30s chunk (~3.3MB)
    ↓
Process first chunk (~500ms)
    ↓
Start streaming first chunk immediately
    ↓
User hears audio (WITHIN 1-2 SECONDS)
    ↓
Background: Process remaining chunks asynchronously
```

---

## 🔧 Implementation Strategy

### 1. Chunk Configuration
```python
CHUNK_DURATION = 30  # seconds
OVERLAP_DURATION = 1  # seconds for crossfade
SAMPLE_RATE = 44100

CHUNK_SAMPLES = CHUNK_DURATION * SAMPLE_RATE  # 1,323,000 samples
OVERLAP_SAMPLES = OVERLAP_DURATION * SAMPLE_RATE  # 44,100 samples
```

### 2. Chunk Processing

#### Chunk Structure:
```
Chunk 0: [0s ─────────── 30s] + [30s-31s overlap]
Chunk 1:     [29s-30s overlap] + [30s ──────── 60s] + [60s-61s overlap]
Chunk 2:                            [59s-60s overlap] + [60s ──────── 90s]
```

#### Crossfade Zones:
```
            Chunk 0                    Chunk 1
  ┌─────────────────────┬──┐    ┌──┬─────────────────────┬──┐
  │                     │OL│    │OL│                     │OL│
  │      Main Audio     │AP│    │AP│     Main Audio      │AP│
  │                     │  │    │  │                     │  │
  └─────────────────────┴──┘    └──┴─────────────────────┴──┘
                        └──┬──┬──┘
                         Fade  Fade
                         Out   In
```

### 3. Processing Pipeline

```python
class ChunkedAudioProcessor:
    def __init__(self, track_id, preset, intensity):
        self.track_id = track_id
        self.preset = preset
        self.intensity = intensity
        self.chunk_cache = {}  # {chunk_index: processed_audio_path}

    async def process_chunk(self, chunk_index, audio_chunk, sample_rate):
        """Process a single chunk with overlap for crossfading"""
        # Process with HybridProcessor
        processor = HybridProcessor(config)
        processed_chunk = processor.process(audio_chunk)

        # Apply crossfade at boundaries
        if chunk_index > 0:
            processed_chunk = apply_fade_in(processed_chunk, OVERLAP_SAMPLES)

        if not is_last_chunk:
            processed_chunk = apply_fade_out(processed_chunk, OVERLAP_SAMPLES)

        # Save to cache
        chunk_path = save_chunk(processed_chunk, chunk_index)
        self.chunk_cache[chunk_index] = chunk_path

        return chunk_path

    async def process_all_chunks_async(self):
        """Background task to process remaining chunks"""
        for chunk_idx in range(1, total_chunks):
            chunk = load_chunk(chunk_idx)
            await self.process_chunk(chunk_idx, chunk, sample_rate)
```

### 4. Streaming Endpoint Changes

```python
@app.get("/api/player/stream/{track_id}")
async def stream_audio_chunked(
    track_id: int,
    enhanced: bool = False,
    preset: str = "adaptive",
    intensity: float = 1.0,
    background_tasks: BackgroundTasks
):
    if not enhanced:
        # Original file - stream directly
        return FileResponse(track.filepath)

    # Enhanced mode - use chunked processing
    processor = ChunkedAudioProcessor(track_id, preset, intensity)

    # Check if first chunk is cached
    cache_key = f"{track_id}_{preset}_{intensity}_chunk_0"
    first_chunk_path = chunk_cache.get(cache_key)

    if not first_chunk_path:
        # Process ONLY the first chunk
        first_chunk = load_chunk(track.filepath, chunk_index=0)
        first_chunk_path = await processor.process_chunk(0, first_chunk, sample_rate)
        chunk_cache[cache_key] = first_chunk_path

        # Start background processing of remaining chunks
        background_tasks.add_task(processor.process_all_chunks_async)

    # Stream the concatenated chunks
    return StreamingResponse(
        chunk_generator(processor),
        media_type="audio/wav"
    )

async def chunk_generator(processor):
    """Yield processed chunks as they become available"""
    chunk_idx = 0
    while chunk_idx < processor.total_chunks:
        # Wait for chunk to be processed (if not ready yet)
        chunk_path = await processor.wait_for_chunk(chunk_idx)

        # Stream the chunk
        with open(chunk_path, 'rb') as f:
            yield f.read()

        chunk_idx += 1
```

---

## 🎵 Crossfade Algorithm

To avoid audible jumps between chunks, we apply a 1-second crossfade:

```python
def apply_crossfade(chunk1, chunk2, overlap_samples=44100):
    """
    Crossfade between two chunks

    Args:
        chunk1: Last `overlap_samples` of chunk 1
        chunk2: First `overlap_samples` of chunk 2
        overlap_samples: Number of samples to crossfade (default 1 second @ 44.1kHz)

    Returns:
        Crossfaded overlap region
    """
    # Create fade curves
    fade_out = np.linspace(1.0, 0.0, overlap_samples)
    fade_in = np.linspace(0.0, 1.0, overlap_samples)

    # Apply fades
    chunk1_tail = chunk1[-overlap_samples:] * fade_out[:, np.newaxis]
    chunk2_head = chunk2[:overlap_samples] * fade_in[:, np.newaxis]

    # Mix
    crossfade = chunk1_tail + chunk2_head

    return crossfade
```

### Processing Considerations:

The HybridProcessor needs **context** for proper mastering:
- **Solution**: Include 5-second pre/post buffers when processing chunks
- Process chunk with extra context, then trim to actual chunk boundaries

```python
def load_chunk_with_context(filepath, chunk_idx, context_duration=5):
    """
    Load chunk with context for better processing quality

    Chunk 1 example:
    [25s ─── 30s ───── 60s ─── 65s]
      ↑      ↑        ↑       ↑
     pre   start     end    post
    context         context
    """
    start = max(0, chunk_idx * CHUNK_DURATION - context_duration)
    end = (chunk_idx + 1) * CHUNK_DURATION + context_duration

    audio, sr = load_audio(filepath, start=start, end=end)

    # Process with full context
    processed = processor.process(audio)

    # Trim to actual chunk boundaries
    if chunk_idx > 0:
        processed = processed[context_duration * sr:]

    return processed
```

---

## 💾 Caching Strategy

### Chunk Cache Structure:
```python
chunk_cache = {
    "track_13_warm_1.0_chunk_0": "/tmp/auralis/chunks/13_warm_1.0_chunk_0.wav",
    "track_13_warm_1.0_chunk_1": "/tmp/auralis/chunks/13_warm_1.0_chunk_1.wav",
    "track_13_warm_1.0_chunk_2": "/tmp/auralis/chunks/13_warm_1.0_chunk_2.wav",
    # ...
}
```

### Cache Management:
- **LRU eviction**: Remove least recently used chunks when cache > 1GB
- **Chunk priority**: Keep first chunk always cached (fast playback start)
- **Background cleanup**: Async task to clean old chunks

---

## 📊 Performance Estimates

### Before (Current):
- **Time to first byte**: 5-10 seconds (process entire file)
- **Memory usage**: ~200MB (full file in memory)
- **User experience**: Long wait, then smooth playback

### After (Chunked):
- **Time to first byte**: 0.5-1 second (process only first 30s chunk)
- **Memory usage**: ~15MB peak (one chunk at a time)
- **User experience**: Near-instant playback, background processing

### Chunk Processing Times:
- **30s chunk @ 44.1kHz stereo**: ~3.3MB
- **Processing time**: ~500ms (based on 52.8x real-time factor)
- **Chunks for 6min song**: 12 chunks
- **Total background processing**: ~6 seconds (all chunks)

---

## 🚀 Implementation Plan

### Phase 1: Core Chunking (2-3 hours)
1. ✅ Create `ChunkedAudioProcessor` class
2. ✅ Implement `load_chunk_with_context()` function
3. ✅ Implement crossfade algorithm
4. ✅ Update stream endpoint to use chunked processing
5. ✅ Add background task for remaining chunks

### Phase 2: Optimization (1-2 hours)
1. ✅ Implement chunk caching
2. ✅ Add cache management (LRU eviction)
3. ✅ Optimize memory usage
4. ✅ Add progress tracking

### Phase 3: Testing (1 hour)
1. ✅ Test with various file sizes
2. ✅ Verify no audible gaps
3. ✅ Test seek functionality
4. ✅ Performance profiling

**Total Estimated Time**: 4-6 hours

---

## 🔍 Alternative Approaches Considered

### 1. Pre-process entire file (current approach)
- ❌ Slow time to first byte
- ✅ No complexity
- ✅ No gaps

### 2. Stream raw audio, process in frontend
- ❌ Impossible (JavaScript can't run HybridProcessor)
- ❌ No Web Audio API equivalent

### 3. Chunk without overlap
- ❌ Audible clicks/pops at boundaries
- ❌ Processing artifacts at edges

### 4. Adaptive chunk size
- ✅ Could optimize for file length
- ❌ More complexity
- 💡 Future enhancement

### 5. Streaming via WebSocket chunks
- ✅ Real-time streaming possible
- ❌ More complex than HTTP streaming
- ❌ Browser audio handling harder
- 💡 Future enhancement

---

## ✅ Chosen Solution: Chunked HTTP Streaming with Crossfade

**Best balance of**:
- ⚡ Fast time to first byte
- 🎵 No audible artifacts
- 💻 Reasonable complexity
- 📦 Uses existing HTTP streaming infrastructure
- 🔄 Background processing for remaining chunks

---

## 📝 Next Steps

1. Implement `ChunkedAudioProcessor` class in new file
2. Create chunk loading utilities with context
3. Add crossfade functions
4. Update streaming endpoint
5. Test with real audio files
6. Measure performance improvements

**Ready to implement?** 🚀
