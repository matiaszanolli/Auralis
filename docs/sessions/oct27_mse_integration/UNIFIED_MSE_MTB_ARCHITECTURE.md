# Unified MSE + Multi-Tier Buffer Architecture

**Date**: October 27, 2025
**Status**: 🔧 **IN PROGRESS**
**Strategy**: Option 1 - Unified Chunking System
**Goal**: Instant preset switching (<100ms) leveraging multi-tier buffer advantages

---

## 🎯 Vision

**Single unified streaming system** that provides:
- ✅ **Instant switching** via MSE in unenhanced mode
- ✅ **Multi-tier buffer intelligence** for enhanced mode
- ✅ **No dual playback conflicts**
- ✅ **Leverage existing cache infrastructure**
- ✅ **Single source of truth** for all audio streaming

---

## 📐 Architecture Design

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Player Manager                   │
│  ┌────────────────────┐         ┌─────────────────────────┐│
│  │  MSE Player        │         │  HTML5 Audio Player     ││
│  │  (unenhanced)      │         │  (enhanced)             ││
│  │  Instant switching │         │  Real-time processing   ││
│  └────────────────────┘         └─────────────────────────┘│
└────────────────────┬───────────────────────┬────────────────┘
                     │                       │
                     └───────────┬───────────┘
                                 │
                     ┌───────────▼───────────┐
                     │   Unified Streaming   │
                     │   API Endpoint        │
                     │ /api/audio/stream/... │
                     └───────────┬───────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
    ┌─────────▼────────┐  ┌─────▼──────┐  ┌───────▼────────┐
    │   Chunk Router   │  │  Enhanced? │  │  Format Check  │
    │  (Intelligence)  │  │   Mode?    │  │  WebM vs WAV   │
    └─────────┬────────┘  └────────────┘  └────────────────┘
              │
       ┌──────┴──────┐
       │             │
┌──────▼───────┐ ┌──▼─────────────────┐
│ MSE Path     │ │ Multi-Tier Buffer  │
│ (Unenhanced) │ │ Path (Enhanced)    │
│              │ │                    │
│ - Original   │ │ - L1: First chunk  │
│   audio      │ │ - L2: Full file    │
│ - WebM/Opus  │ │ - L3: Preset cache │
│ - <100ms     │ │ - WAV format       │
│   switching  │ │ - ~1s first play   │
└──────────────┘ └────────────────────┘
```

### Component Responsibilities

#### 1. Unified Streaming Endpoint
**Path**: `/api/audio/stream/{track_id}/chunk/{chunk_idx}`

**Query Parameters**:
- `enhanced`: `true` | `false` - Enhancement mode
- `preset`: `adaptive` | `warm` | `bright` | `punchy` | `gentle`
- `intensity`: `0.0` - `1.0` - Enhancement intensity

**Response**:
- **Unenhanced**: WebM/Opus chunk (MSE-compatible)
- **Enhanced**: WAV chunk from multi-tier buffer

**Intelligence**:
- Auto-detects client capabilities (MSE support)
- Routes to appropriate backend system
- Manages cache coordination

#### 2. Backend Chunk Router
**File**: `auralis-web/backend/routers/unified_streaming.py` (NEW)

**Responsibilities**:
- Parse request parameters (enhanced, preset, intensity)
- Route to MSE or MTB backend
- Coordinate cache systems
- Return appropriate format

**Decision Logic**:
```python
if enhanced:
    # Multi-Tier Buffer Path
    return await get_enhanced_chunk(track_id, chunk_idx, preset, intensity)
else:
    # MSE Path
    return await get_original_chunk_webm(track_id, chunk_idx)
```

#### 3. Frontend Unified Player Manager
**File**: `auralis-web/frontend/src/components/player/UnifiedPlayerManager.tsx` (NEW)

**Responsibilities**:
- Single audio element manager
- Detects enhancement mode changes
- Switches between MSE and HTML5 Audio
- Manages player state transitions
- Coordinates with backend streaming

**Mode Switching**:
```typescript
async switchMode(enhanced: boolean) {
  // Pause current player
  await this.pause();

  // Destroy old player
  if (enhanced && this.msePlayer) {
    this.msePlayer.destroy();
    this.msePlayer = null;
  } else if (!enhanced && this.html5Player) {
    this.html5Player.cleanup();
    this.html5Player = null;
  }

  // Initialize new player
  if (enhanced) {
    this.html5Player = new HTML5AudioPlayer();
    await this.html5Player.load(trackId, preset);
  } else {
    this.msePlayer = new MSEPlayer();
    await this.msePlayer.initialize(trackId);
  }

  // Resume playback at same position
  await this.seek(currentPosition);
  await this.play();
}
```

---

## 🔧 Implementation Plan

### Phase 1: Backend Unified Endpoint (4-5 hours)

#### 1.1 Create Unified Streaming Router
**File**: `auralis-web/backend/routers/unified_streaming.py`

```python
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
import asyncio

router = APIRouter(prefix="/api/audio/stream", tags=["streaming"])

@router.get("/{track_id}/metadata")
async def get_stream_metadata(
    track_id: int,
    enhanced: bool = Query(False),
    preset: str = Query("adaptive")
):
    """
    Get streaming metadata for unified player.
    Returns chunk count, duration, format, etc.
    """
    # Get track info from library
    track = await library_manager.get_track(track_id)
    if not track:
        raise HTTPException(404, "Track not found")

    # Determine total chunks based on mode
    chunk_duration = 30.0  # 30-second chunks
    total_chunks = math.ceil(track.duration / chunk_duration)

    return {
        "track_id": track_id,
        "duration": track.duration,
        "total_chunks": total_chunks,
        "chunk_duration": chunk_duration,
        "format": "audio/webm; codecs=opus" if not enhanced else "audio/wav",
        "enhanced": enhanced,
        "preset": preset,
        "supports_seeking": True
    }

@router.get("/{track_id}/chunk/{chunk_idx}")
async def get_audio_chunk(
    track_id: int,
    chunk_idx: int,
    enhanced: bool = Query(False),
    preset: str = Query("adaptive"),
    intensity: float = Query(1.0, ge=0.0, le=1.0)
):
    """
    Unified chunk endpoint - routes to MSE or MTB based on enhanced parameter.
    """
    try:
        if enhanced:
            # Multi-Tier Buffer path
            return await _get_enhanced_chunk(track_id, chunk_idx, preset, intensity)
        else:
            # MSE path - serve original as WebM
            return await _get_original_webm_chunk(track_id, chunk_idx)

    except Exception as e:
        logger.error(f"Error serving chunk {chunk_idx} for track {track_id}: {e}")
        raise HTTPException(500, f"Failed to serve chunk: {str(e)}")

async def _get_enhanced_chunk(track_id, chunk_idx, preset, intensity):
    """
    Serve enhanced chunk via multi-tier buffer system.
    """
    # Check multi-tier buffer cache
    cache_key = f"{track_id}_{preset}_{intensity}_chunk_{chunk_idx}"

    # Try L1 (chunk cache)
    chunk_path = await multi_tier_buffer.get_chunk(cache_key)
    if chunk_path:
        logger.info(f"L1 HIT: Serving chunk {chunk_idx} from cache")
        return StreamingResponse(
            open(chunk_path, 'rb'),
            media_type="audio/wav",
            headers={
                "X-Cache-Tier": "L1",
                "X-Chunk-Index": str(chunk_idx)
            }
        )

    # L1 MISS: Process chunk
    logger.info(f"L1 MISS: Processing chunk {chunk_idx}")
    processor = chunked_audio_processor.get_processor(track_id, preset, intensity)
    chunk_path = await processor.process_chunk(chunk_idx)

    # Store in L1 cache
    await multi_tier_buffer.store_chunk(cache_key, chunk_path)

    return StreamingResponse(
        open(chunk_path, 'rb'),
        media_type="audio/wav",
        headers={
            "X-Cache-Tier": "L1-NEW",
            "X-Chunk-Index": str(chunk_idx)
        }
    )

async def _get_original_webm_chunk(track_id, chunk_idx):
    """
    Serve original audio as WebM chunk for MSE player.
    """
    # Check WebM chunk cache
    cache_key = f"{track_id}_original_webm_chunk_{chunk_idx}"
    cached_path = await webm_cache.get(cache_key)

    if cached_path:
        logger.info(f"WebM CACHE HIT: chunk {chunk_idx}")
        return StreamingResponse(
            open(cached_path, 'rb'),
            media_type="audio/webm; codecs=opus"
        )

    # CACHE MISS: Load original and encode to WebM
    track = await library_manager.get_track(track_id)

    # Load audio chunk
    audio, sr = load_audio_chunk(track.file_path, chunk_idx * 30.0, 30.0)

    # Encode to WebM
    webm_path = await encode_to_webm(audio, sr, cache_key)

    # Cache for future requests
    await webm_cache.store(cache_key, webm_path)

    return StreamingResponse(
        open(webm_path, 'rb'),
        media_type="audio/webm; codecs=opus"
    )
```

#### 1.2 Integrate with Existing Multi-Tier Buffer
**Modification**: Use existing `multi_tier_buffer.py` infrastructure
**Key**: The multi-tier buffer already has L1/L2/L3 caching - we just expose it via the unified endpoint

#### 1.3 Add WebM Encoding Support
**File**: `auralis-web/backend/webm_encoder.py` (NEW)

```python
import subprocess
import tempfile
from pathlib import Path

async def encode_to_webm(audio: np.ndarray, sr: int, cache_key: str) -> Path:
    """
    Encode audio to WebM/Opus format for MSE streaming.
    """
    # Save audio to temp WAV
    temp_wav = Path(tempfile.gettempdir()) / f"{cache_key}_temp.wav"
    sf.write(str(temp_wav), audio, sr)

    # Output WebM path
    output_webm = Path(tempfile.gettempdir()) / f"{cache_key}.webm"

    # Use ffmpeg to encode to WebM/Opus
    cmd = [
        'ffmpeg',
        '-i', str(temp_wav),
        '-c:a', 'libopus',
        '-b:a', '128k',
        '-vbr', 'on',
        '-compression_level', '10',
        '-y',  # Overwrite output
        str(output_webm)
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    await proc.communicate()

    # Clean up temp WAV
    temp_wav.unlink()

    return output_webm
```

### Phase 2: Frontend Unified Player (5-6 hours)

#### 2.1 Create Unified Player Manager
**File**: `auralis-web/frontend/src/components/player/UnifiedPlayerManager.tsx`

```typescript
/**
 * Unified Player Manager
 *
 * Manages both MSE and HTML5 Audio players.
 * Switches between modes based on enhancement state.
 */

export class UnifiedPlayerManager {
  private msePlayer: MSEPlayer | null = null;
  private html5Player: HTML5AudioPlayer | null = null;
  private currentMode: 'mse' | 'html5' = 'mse';
  private currentTrackId: number | null = null;
  private currentPosition: number = 0;
  private isPlaying: boolean = false;

  async initialize(trackId: number, enhanced: boolean, preset: string) {
    this.currentTrackId = trackId;

    if (enhanced) {
      await this.initializeHTML5Player(trackId, preset);
    } else {
      await this.initializeMSEPlayer(trackId);
    }
  }

  private async initializeMSEPlayer(trackId: number) {
    // Clean up HTML5 if exists
    if (this.html5Player) {
      this.html5Player.destroy();
      this.html5Player = null;
    }

    // Create MSE player
    this.msePlayer = new MSEPlayer();
    await this.msePlayer.initialize(trackId);
    this.currentMode = 'mse';
  }

  private async initializeHTML5Player(trackId: number, preset: string) {
    // Clean up MSE if exists
    if (this.msePlayer) {
      this.msePlayer.destroy();
      this.msePlayer = null;
    }

    // Create HTML5 Audio player
    this.html5Player = new HTML5AudioPlayer();
    await this.html5Player.load(trackId, preset);
    this.currentMode = 'html5';
  }

  async switchEnhancementMode(enhanced: boolean, preset: string) {
    // Store current state
    const wasPlaying = this.isPlaying;
    this.currentPosition = this.getCurrentTime();

    // Pause before switching
    await this.pause();

    // Reinitialize with new mode
    if (this.currentTrackId) {
      await this.initialize(this.currentTrackId, enhanced, preset);

      // Restore position
      await this.seek(this.currentPosition);

      // Resume if was playing
      if (wasPlaying) {
        await this.play();
      }
    }
  }

  async play() {
    if (this.currentMode === 'mse' && this.msePlayer) {
      await this.msePlayer.play();
    } else if (this.currentMode === 'html5' && this.html5Player) {
      await this.html5Player.play();
    }
    this.isPlaying = true;
  }

  async pause() {
    if (this.currentMode === 'mse' && this.msePlayer) {
      await this.msePlayer.pause();
    } else if (this.currentMode === 'html5' && this.html5Player) {
      await this.html5Player.pause();
    }
    this.isPlaying = false;
  }

  getCurrentTime(): number {
    if (this.currentMode === 'mse' && this.msePlayer) {
      return this.msePlayer.getCurrentTime();
    } else if (this.currentMode === 'html5' && this.html5Player) {
      return this.html5Player.getCurrentTime();
    }
    return 0;
  }

  async seek(position: number) {
    if (this.currentMode === 'mse' && this.msePlayer) {
      await this.msePlayer.seek(position);
    } else if (this.currentMode === 'html5' && this.html5Player) {
      await this.html5Player.seek(position);
    }
    this.currentPosition = position;
  }

  destroy() {
    if (this.msePlayer) {
      this.msePlayer.destroy();
      this.msePlayer = null;
    }
    if (this.html5Player) {
      this.html5Player.destroy();
      this.html5Player = null;
    }
  }
}
```

#### 2.2 Update BottomPlayerBarConnected
**File**: `auralis-web/frontend/src/components/BottomPlayerBarConnected.tsx`

Replace dual player logic with UnifiedPlayerManager:

```typescript
import { UnifiedPlayerManager } from './player/UnifiedPlayerManager';

// Inside component:
const playerManager = useRef<UnifiedPlayerManager>(new UnifiedPlayerManager());

// On track change:
useEffect(() => {
  if (currentTrack) {
    playerManager.current.initialize(
      currentTrack.id,
      enhancementEnabled,
      currentPreset
    );
  }
}, [currentTrack]);

// On enhancement toggle:
const handleEnhancementToggle = async (enabled: boolean) => {
  await playerManager.current.switchEnhancementMode(enabled, currentPreset);
};

// On preset change:
const handlePresetChange = async (preset: string) => {
  if (enhancementEnabled) {
    // HTML5 mode - may have delay
    await playerManager.current.switchEnhancementMode(true, preset);
  } else {
    // MSE mode - instant!
    // No reload needed, just update backend parameter
    setCurrentPreset(preset);
  }
};
```

### Phase 3: MSE Player Enhancements (2-3 hours)

#### 3.1 Update MSE Player to Use Unified Endpoint
**File**: `auralis-web/frontend/src/components/player/MSEPlayer.ts`

```typescript
async initialize(trackId: number) {
  // Get metadata from unified endpoint
  const metadata = await fetch(
    `/api/audio/stream/${trackId}/metadata?enhanced=false`
  ).then(r => r.json());

  this.totalChunks = metadata.total_chunks;
  this.duration = metadata.duration;

  // Initialize MediaSource
  this.mediaSource = new MediaSource();
  this.audioElement.src = URL.createObjectURL(this.mediaSource);

  await new Promise((resolve) => {
    this.mediaSource.addEventListener('sourceopen', resolve, { once: true });
  });

  // Create SourceBuffer
  this.sourceBuffer = this.mediaSource.addSourceBuffer(metadata.format);

  // Start loading chunks
  await this.loadChunk(0);
}

private async loadChunk(chunkIdx: number) {
  const response = await fetch(
    `/api/audio/stream/${this.trackId}/chunk/${chunkIdx}?enhanced=false`
  );

  const arrayBuffer = await response.arrayBuffer();

  // Append to SourceBuffer
  this.sourceBuffer.appendBuffer(arrayBuffer);

  // Wait for append to complete
  await new Promise((resolve) => {
    this.sourceBuffer.addEventListener('updateend', resolve, { once: true });
  });

  // Load next chunk if available
  if (chunkIdx < this.totalChunks - 1) {
    await this.loadChunk(chunkIdx + 1);
  }
}
```

### Phase 4: Testing & Validation (2-3 hours)

#### Test Scenarios

1. **Unenhanced Playback (MSE)**:
   - [ ] Track plays instantly via MSE
   - [ ] Preset switching is instant (<100ms)
   - [ ] No buffering when switching presets
   - [ ] Seeking works smoothly

2. **Enhanced Playback (Multi-Tier Buffer)**:
   - [ ] First chunk plays in ~1s
   - [ ] Background chunks process correctly
   - [ ] L1/L2/L3 cache tiers work
   - [ ] Proactive preset buffering functional

3. **Mode Switching**:
   - [ ] Enhancement OFF → ON: Switches to HTML5, position preserved
   - [ ] Enhancement ON → OFF: Switches to MSE, instant preset switching enabled
   - [ ] No dual playback conflicts
   - [ ] Pause/play works correctly after switching

4. **Preset Switching**:
   - [ ] Unenhanced mode: Instant switching (no reload)
   - [ ] Enhanced mode: Cache hit is fast, cache miss ~1-2s

5. **Edge Cases**:
   - [ ] Rapid enhancement toggling
   - [ ] Preset change during playback
   - [ ] Seek while loading chunks
   - [ ] Next/previous track

---

## 📊 Expected Performance

### Unenhanced Mode (MSE)
- **Initial load**: ~300-500ms (first chunk)
- **Preset switching**: <100ms (instant, no reload)
- **Format**: WebM/Opus (efficient streaming)

### Enhanced Mode (Multi-Tier Buffer)
- **Initial load**: ~1s (L1 chunk processing)
- **Full file cache hit**: <200ms
- **Preset switching**:
  - L3 cache hit: ~200ms
  - Cache miss: ~1-2s
- **Format**: WAV (high quality)

---

## 🎯 Success Criteria

1. ✅ No dual playback conflicts
2. ✅ Instant preset switching in unenhanced mode
3. ✅ Multi-tier buffer advantages preserved
4. ✅ Single unified API endpoint
5. ✅ Smooth mode transitions
6. ✅ All existing tests pass

---

## 📝 Migration Path

1. **Backend First**: Create unified endpoint, test with Postman
2. **Frontend Integration**: Update player to use unified endpoint
3. **Mode Switching**: Implement enhancement toggle with player switching
4. **Testing**: Comprehensive testing of all scenarios
5. **Documentation**: Update API docs and user guide

---

## 🚀 Next Steps

1. Implement backend unified endpoint
2. Add WebM encoding support
3. Create frontend UnifiedPlayerManager
4. Update BottomPlayerBarConnected to use manager
5. Test all scenarios thoroughly
6. Document API changes

**Estimated Total Time**: 13-17 hours
**Priority**: P0 (Critical for Beta.4)
**Status**: Ready to implement
