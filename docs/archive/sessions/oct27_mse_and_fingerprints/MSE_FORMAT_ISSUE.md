# MSE Audio Format Issue - Critical Finding

**Date**: October 27, 2025
**Severity**: 🔴 **CRITICAL BLOCKER**
**Status**: Requires format encoding implementation

---

## 🚨 The Problem

**Browser Error**: `MediaSource.addSourceBuffer: Can't play type`

**Root Cause**: MSE (Media Source Extensions) **does not support raw WAV files**. WAV is a PCM audio format without proper containerization that MSE's SourceBuffer API requires.

### What We Tried
```javascript
// This FAILS:
const mimeType = `audio/wav; codecs="pcm"`;
sourceBuffer = mediaSource.addSourceBuffer(mimeType);
// Error: Can't play type
```

### Why WAV Doesn't Work

WAV files are:
- ❌ Raw PCM audio with minimal container
- ❌ Not designed for streaming
- ❌ No proper fragmentation support
- ❌ Not supported by MSE SourceBuffer

MSE requires:
- ✅ Proper containerized formats (WebM, MP4, MP3)
- ✅ Fragmented/chunked container structure
- ✅ Codec information in container headers
- ✅ Seeking/duration metadata

---

## 🎯 Solution Options

### Option 1: WebM with Opus Codec (RECOMMENDED)

**Pros**:
- ✅ Excellent browser support (97%+)
- ✅ Open source, royalty-free
- ✅ Good compression (~128-192 kbps for high quality)
- ✅ Low latency encoding
- ✅ MSE fully supports WebM

**Cons**:
- ⚠️ Requires encoding step (adds latency)
- ⚠️ Lossy compression (quality trade-off)
- ⚠️ Need ffmpeg or similar encoder

**Implementation**:
```python
# After processing audio chunk with Auralis
processed_audio, sr = processor.process_chunk(...)

# Encode to WebM/Opus
webm_bytes = encode_to_webm_opus(
    processed_audio,
    sample_rate=sr,
    bitrate=192  # kbps
)

# Serve with proper MIME type
return Response(
    content=webm_bytes,
    media_type="audio/webm; codecs=opus"
)
```

**Browser Support**:
- Chrome: ✅ Full support
- Firefox: ✅ Full support
- Safari: ✅ Full support (macOS 14.1+)
- Edge: ✅ Full support

---

### Option 2: MP4 with AAC Codec

**Pros**:
- ✅ Universal browser support (99%+)
- ✅ Mature ecosystem
- ✅ Good quality at moderate bitrates
- ✅ MSE fully supports fMP4 (fragmented MP4)

**Cons**:
- ⚠️ Patent-encumbered (may have licensing implications)
- ⚠️ Requires encoding step
- ⚠️ Lossy compression
- ⚠️ Need ffmpeg or similar encoder

**Implementation**:
```python
# After processing
mp4_bytes = encode_to_mp4_aac(
    processed_audio,
    sample_rate=sr,
    bitrate=256  # kbps
)

return Response(
    content=mp4_bytes,
    media_type="audio/mp4; codecs=mp4a.40.2"  # AAC-LC
)
```

---

### Option 3: MP3 Format

**Pros**:
- ✅ Universal support (100%)
- ✅ Simple format
- ✅ Smaller file sizes
- ✅ Well-understood codec

**Cons**:
- ⚠️ Patent issues (expired in most countries, but complex)
- ⚠️ Lower quality than Opus/AAC at same bitrate
- ⚠️ Higher latency encoding
- ⚠️ Not ideal for MSE (lacks proper fragmentation)

**Not Recommended**: MP3 works but is suboptimal for streaming use cases.

---

### Option 4: FLAC in MP4 Container (Lossless)

**Pros**:
- ✅ Lossless compression
- ✅ No quality loss
- ✅ Can be containerized in MP4

**Cons**:
- ❌ Poor browser support for MSE (Safari only)
- ❌ Large file sizes
- ❌ Higher bandwidth requirements
- ❌ Encoding overhead

**Not Recommended**: Browser support is insufficient.

---

## 📊 Comparison Matrix

| Format | Browser Support | Quality | File Size | Encoding Speed | MSE Support | Recommendation |
|--------|----------------|---------|-----------|----------------|-------------|----------------|
| **WebM/Opus** | 97% | Excellent | Small | Fast | ✅ Full | **⭐ BEST** |
| **MP4/AAC** | 99% | Very Good | Medium | Medium | ✅ Full | ✅ Good |
| MP3 | 100% | Good | Small | Slow | ⚠️ Limited | ⚠️ Fallback |
| FLAC/MP4 | 30% | Perfect | Large | Medium | ❌ Poor | ❌ No |
| **WAV** | N/A | Perfect | Huge | Instant | ❌ None | ❌ **BROKEN** |

---

## 🎯 Recommended Solution: WebM/Opus

### Why WebM/Opus?

1. **Best quality-to-size ratio**: Opus is technically superior to AAC
2. **Open source**: No licensing concerns
3. **Fast encoding**: Low CPU overhead
4. **Low latency**: Designed for real-time streaming
5. **Excellent browser support**: 97% coverage (Chrome, Firefox, Edge, Safari 14.1+)

### Implementation Plan

#### Phase 1: Add Encoding Pipeline
```python
# New file: auralis-web/backend/encoding/webm_encoder.py

import subprocess
import tempfile
from pathlib import Path

def encode_to_webm_opus(audio_array: np.ndarray, sample_rate: int, bitrate: int = 192) -> bytes:
    """
    Encode numpy audio array to WebM with Opus codec.

    Args:
        audio_array: (channels, samples) or (samples,) numpy array
        sample_rate: Audio sample rate
        bitrate: Target bitrate in kbps (default: 192)

    Returns:
        WebM file bytes
    """
    # Write audio to temporary WAV file
    temp_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    sf.write(temp_wav.name, audio_array.T, sample_rate)

    # Encode to WebM using ffmpeg
    temp_webm = tempfile.NamedTemporaryFile(suffix='.webm', delete=False)

    cmd = [
        'ffmpeg',
        '-i', temp_wav.name,
        '-c:a', 'libopus',
        '-b:a', f'{bitrate}k',
        '-vbr', 'on',  # Variable bitrate
        '-compression_level', '10',  # Best quality
        '-frame_duration', '20',  # 20ms frames (low latency)
        '-application', 'audio',  # Optimized for music
        '-y',  # Overwrite
        temp_webm.name
    ]

    subprocess.run(cmd, check=True, capture_output=True)

    # Read WebM bytes
    with open(temp_webm.name, 'rb') as f:
        webm_bytes = f.read()

    # Cleanup
    Path(temp_wav.name).unlink()
    Path(temp_webm.name).unlink()

    return webm_bytes
```

#### Phase 2: Update ChunkedAudioProcessor
```python
# Modify: auralis-web/backend/chunked_processor.py

from encoding.webm_encoder import encode_to_webm_opus

class ChunkedAudioProcessor:
    def process_chunk(self, chunk_idx: int, format: str = 'webm') -> Path:
        # ... existing processing ...

        if format == 'webm':
            # Encode to WebM
            webm_bytes = encode_to_webm_opus(processed_audio, self.sample_rate)
            chunk_path = self.chunk_dir / f"track_{self.track_id}_{hash}_{preset}_{intensity}_chunk_{chunk_idx}.webm"
            chunk_path.write_bytes(webm_bytes)
        else:
            # Fallback: WAV (for non-MSE endpoints)
            # ... existing WAV save ...

        return chunk_path
```

#### Phase 3: Update MSE Router
```python
# Modify: auralis-web/backend/routers/mse_streaming.py

class StreamMetadata(BaseModel):
    mime_type: str = "audio/webm"
    codecs: str = "opus"

@router.get("/api/mse/stream/{track_id}/chunk/{chunk_idx}")
async def stream_chunk(...):
    # Process chunk with format='webm'
    chunk_path = processor.process_chunk(chunk_idx, format='webm')

    # Read WebM bytes
    with open(chunk_path, 'rb') as f:
        webm_bytes = f.read()

    return Response(
        content=webm_bytes,
        media_type="audio/webm; codecs=opus",
        headers={
            "Accept-Ranges": "bytes",
            "X-Content-Duration": str(chunk_duration),
            ...
        }
    )
```

#### Phase 4: Update Frontend Test Page
```javascript
// In mse-test.html, the MIME type will now be:
const mimeType = `audio/webm; codecs=opus`;
sourceBuffer = mediaSource.addSourceBuffer(mimeType);
// This WILL WORK! ✅
```

---

## ⏱️ Performance Impact

### Encoding Overhead

**Opus Encoding Speed** (typical hardware):
- Real-time factor: **50-100x** (process 30s in 0.3-0.6s)
- CPU usage: Low (single core ~30%)

**Combined Pipeline**:
```
Auralis Processing: 5.7s (for 30s chunk)
+ Opus Encoding:    0.5s
= Total:            6.2s (first request)

Cached:            59ms (file cache)
```

**Impact on Preset Switching**:
- First switch: 6.2s (was 5.7s) - **+0.5s overhead**
- Cached switches: 59ms (no change) - **Still fast!**

**Conclusion**: **+9% latency on cold requests, zero impact on cached requests**

### File Size Comparison

**30-second chunk**:
```
WAV (stereo 44.1kHz 16-bit):     5.3 MB
WebM/Opus (192 kbps):            ~720 KB  (86% smaller!)
WebM/Opus (128 kbps):            ~480 KB  (91% smaller!)
```

**Benefits**:
- **86-91% bandwidth reduction**
- **Faster chunk loading over network**
- **Better cache efficiency** (more chunks fit in cache)

---

## 🚀 Implementation Timeline

### Phase 1: Encoding Foundation (Day 1 - 4 hours)
- [ ] Install/verify ffmpeg dependency
- [ ] Create WebM encoder module
- [ ] Write unit tests for encoder
- [ ] Benchmark encoding performance

### Phase 2: Backend Integration (Day 1 - 2 hours)
- [ ] Update ChunkedAudioProcessor
- [ ] Update MSE streaming router
- [ ] Update metadata models
- [ ] Test encoding pipeline

### Phase 3: Frontend Update (Day 1 - 1 hour)
- [ ] Update test page MIME type
- [ ] Test MSE playback with WebM
- [ ] Verify preset switching

### Phase 4: Testing & Validation (Day 2 - 4 hours)
- [ ] Cross-browser testing
- [ ] Performance benchmarks
- [ ] Audio quality validation
- [ ] Memory usage profiling

**Total Time**: 1-2 days (11 hours of work)

---

## 🎯 Success Criteria

After implementing WebM/Opus encoding:

1. ✅ `sourceBuffer.addSourceBuffer()` succeeds
2. ✅ Audio plays smoothly in browser
3. ✅ Preset switching works with <100ms latency (cached)
4. ✅ File sizes reduced by 86%+
5. ✅ Works on Chrome, Firefox, Edge, Safari 14.1+
6. ✅ Audio quality is indistinguishable from original

---

## 📝 Alternative: Simpler Approach

If ffmpeg integration is complex, consider:

### Using `pydub` with ffmpeg wrapper
```python
from pydub import AudioSegment

def encode_to_webm(audio_array, sr):
    # Convert to AudioSegment
    audio = AudioSegment(
        audio_array.tobytes(),
        frame_rate=sr,
        sample_width=2,
        channels=2
    )

    # Export to WebM
    webm_io = io.BytesIO()
    audio.export(webm_io, format='webm', codec='libopus', bitrate='192k')
    return webm_io.getvalue()
```

This is simpler but still requires ffmpeg to be installed.

---

## 🔄 Backward Compatibility

**For non-MSE endpoints** (existing player):
- Keep WAV format for direct playback
- Only use WebM for MSE streaming endpoints
- No breaking changes to existing functionality

**Routing logic**:
```python
if request.path.startswith('/api/mse/'):
    # Use WebM for MSE
    format = 'webm'
else:
    # Use WAV for legacy endpoints
    format = 'wav'
```

---

## 📋 Next Steps

### Immediate (This Session)
1. Document this issue in roadmap
2. Update MSE implementation status
3. Plan encoding integration

### Short Term (1-2 Days)
1. Implement WebM encoding pipeline
2. Update MSE router for WebM
3. Test preset switching with proper format
4. Validate cross-browser

### Medium Term (Beta.3)
1. Optimize encoding performance
2. Add bitrate quality settings
3. Implement adaptive bitrate (optional)
4. Production testing

---

## 🏆 Key Takeaway

**MSE requires proper containerized audio formats (WebM/MP4), not raw WAV.**

This is a critical architectural decision that affects:
- File sizes (86% reduction with Opus!)
- Browser compatibility
- Streaming performance
- Implementation complexity

**Recommended**: Implement WebM/Opus encoding (~1-2 days work) for production-quality MSE streaming.

---

**Status**: Blocked until encoding pipeline implemented
**Priority**: P0 (Critical for MSE functionality)
**Estimated Work**: 1-2 days (11 hours)
