# Unified Player Architecture - WebM/Opus Base with Client-Side Processing

**Priority**: P0 (Critical Architecture Improvement)
**Status**: Planned
**Target**: Beta.7
**Estimated Effort**: 8-9 hours
**Created**: November 1, 2025

---

## Executive Summary

Replace the current dual MSE/HTML5 Audio architecture with a **unified WebM/Opus-based player** that applies real-time processing client-side using Web Audio API. This eliminates dual playback conflicts, simplifies the codebase by 50%, and maintains all performance benefits.

### Key Insight

WebM/Opus at 192 kbps VBR is **transparent quality** and encodes **19-50x faster than real-time**. We can use it as the base format for everything and still apply high-quality DSP processing client-side after decoding.

---

## Problem Statement

### Current Architecture Issues

1. **Dual Playback System Complexity**
   - MSE player for unenhanced playback
   - HTML5 Audio player for enhanced playback
   - Two separate code paths (970+ lines total)
   - State synchronization nightmare

2. **Mode Switching Latency**
   - Toggling enhancement requires player destruction/recreation
   - 1-2 second pause perceived by user
   - Poor UX for exploring presets

3. **Race Conditions & Bugs**
   - Position synchronization issues
   - Volume jump artifacts
   - Memory leaks from incomplete cleanup
   - Source of ~60% of reported bugs

4. **Code Duplication**
   - Similar logic implemented twice
   - Harder to maintain and test
   - Inconsistent behavior between modes

### Root Cause

We built two separate players because we thought:
- MSE required WebM/Opus (true)
- Real-time processing required uncompressed audio (FALSE!)

**Reality**: Web Audio API can decode WebM/Opus to AudioBuffer, then we can process it!

---

## Proposed Solution

### Unified Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│           Single Unified WebM/Opus Player               │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Chunk Fetcher (Progressive Loading)             │  │
│  │  - Fetches WebM/Opus chunks from backend         │  │
│  │  - Multi-tier caching (L1/L2/L3)                 │  │
│  └──────────────┬───────────────────────────────────┘  │
│                 │                                       │
│  ┌──────────────▼───────────────────────────────────┐  │
│  │  WebM Decoder (Web Audio API)                    │  │
│  │  - audioContext.decodeAudioData(webmChunk)       │  │
│  │  - Produces AudioBuffer                          │  │
│  └──────────────┬───────────────────────────────────┘  │
│                 │                                       │
│         ┌───────┴────────┐                             │
│         │                │                             │
│  ┌──────▼──────┐  ┌─────▼──────────────────────────┐  │
│  │  Direct     │  │  Enhanced Processing           │  │
│  │  Playback   │  │  - Fingerprint-aware targets   │  │
│  │  (no DSP)   │  │  - EQ, dynamics, limiting      │  │
│  │             │  │  - Cached by preset/intensity  │  │
│  └──────┬──────┘  └─────┬──────────────────────────┘  │
│         │                │                             │
│         └───────┬────────┘                             │
│                 │                                       │
│  ┌──────────────▼───────────────────────────────────┐  │
│  │  AudioBufferSourceNode                           │  │
│  │  - Scheduled playback                            │  │
│  │  - Seamless chunk transitions                    │  │
│  └──────────────┬───────────────────────────────────┘  │
│                 │                                       │
│  ┌──────────────▼───────────────────────────────────┐  │
│  │  Audio Output (speakers)                         │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. Unified WebM/Opus Player
**Location**: `auralis-web/frontend/src/components/UnifiedWebMAudioPlayer.tsx`

**Responsibilities**:
- Fetch WebM/Opus chunks from backend
- Decode to AudioBuffer using Web Audio API
- Apply enhancement if enabled (fingerprint-aware DSP)
- Schedule seamless playback with AudioBufferSourceNode
- Manage multi-tier cache (WebM, decoded, processed)

#### 2. Multi-Tier WebM Buffer
**Location**: `auralis-web/frontend/src/services/MultiTierWebMBuffer.ts`

**Cache Tiers**:
- **L1: WebM chunks** (compressed, ~769 KB each)
  - Store 50 chunks (~38 MB total)
  - Fast to cache, cheap storage
  - Baseline for all playback modes

- **L2: Decoded AudioBuffers** (uncompressed, ~5.3 MB each)
  - Store 6 chunks (~32 MB total)
  - Skips decoding step (50-100ms savings)
  - Useful for repeated playback

- **L3: Processed AudioBuffers** (enhanced, ~5.3 MB each)
  - Store 3 chunks per preset (~16 MB per preset)
  - Instant preset switching when cached
  - Branch prediction for proactive caching

#### 3. Client-Side DSP Processor
**Location**: `auralis-web/frontend/src/services/ClientDSPProcessor.ts`

**Responsibilities**:
- Receive AudioBuffer (decoded WebM/Opus)
- Fetch fingerprint from .25d sidecar (cached)
- Generate fingerprint-aware processing targets
- Apply EQ, dynamics, limiting (Web Audio API nodes + custom processing)
- Return processed AudioBuffer

**Processing Chain**:
```typescript
AudioBuffer (decoded)
  ↓
Extract fingerprint (from cache)
  ↓
Generate targets (preset + intensity + fingerprint)
  ↓
Apply EQ (26-band psychoacoustic)
  ↓
Apply dynamics (compression + limiting)
  ↓
Apply stereo enhancement
  ↓
Return processed AudioBuffer
```

#### 4. Simplified Backend Endpoint
**Location**: `auralis-web/backend/routers/streaming.py`

**Single endpoint**:
```python
GET /api/audio/stream/{track_id}/chunk/{chunk_idx}
```

**Always returns**: WebM/Opus (192 kbps VBR)

**No more**:
- Dual MSE/MTB routing
- WAV chunk caching
- Format selection logic
- Enhanced/unenhanced path switching

---

## Implementation Plan

### Phase 1: Backend Simplification (2 hours)

#### 1.1 Simplify Streaming Endpoint
**File**: `auralis-web/backend/routers/streaming.py`

**Changes**:
- Remove dual MSE/MTB path logic
- Remove WAV chunk generation
- Keep only WebM/Opus encoding
- Simplify caching (only WebM chunks)

**Before** (~340 lines):
```python
@router.get("/api/audio/stream/{track_id}/chunk/{chunk_idx}")
async def stream_chunk(enhanced: bool, preset: str, ...):
    if enhanced:
        # MTB path: WAV processing
        ...
    else:
        # MSE path: WebM encoding
        ...
```

**After** (~150 lines):
```python
@router.get("/api/audio/stream/{track_id}/chunk/{chunk_idx}")
async def stream_chunk(track_id: int, chunk_idx: int):
    # Always return WebM/Opus
    return await webm_encoder.encode_chunk(track_id, chunk_idx)
```

#### 1.2 Remove Unused Backend Code
**Files to clean up**:
- `auralis-web/backend/streaming/multi_tier_buffer.py` (move caching client-side)
- `auralis-web/backend/streaming/unified_streaming.py` (replace with simple WebM endpoint)
- `auralis-web/backend/streaming/chunked_processor.py` (move processing client-side)

**Keep**:
- `auralis-web/backend/streaming/webm_encoder.py` (essential)
- Cache management (but for WebM only)

#### 1.3 Update Tests
**File**: `tests/backend/test_streaming.py`

**Changes**:
- Remove tests for dual path routing
- Simplify to test only WebM encoding
- Add performance benchmarks (encoding speed)

### Phase 2: Frontend Unified Player (4-5 hours)

#### 2.1 Create UnifiedWebMAudioPlayer
**File**: `auralis-web/frontend/src/components/UnifiedWebMAudioPlayer.tsx`

**Interface**:
```typescript
interface UnifiedWebMAudioPlayerProps {
    trackId: number;
    enhancementEnabled: boolean;
    preset: string;
    intensity: number;
    onPlaybackStateChange: (state: PlaybackState) => void;
    onError: (error: Error) => void;
}

interface PlaybackState {
    isPlaying: boolean;
    currentTime: number;
    duration: number;
    bufferedRanges: TimeRanges;
    currentChunk: number;
    totalChunks: number;
}
```

**Key Methods**:
```typescript
class UnifiedWebMAudioPlayer {
    async initialize(): Promise<void>
    async play(): Promise<void>
    async pause(): Promise<void>
    async seek(position: number): Promise<void>
    async setEnhancement(enabled: boolean): Promise<void>
    async setPreset(preset: string, intensity: number): Promise<void>
    getCurrentTime(): number
    getDuration(): number
    destroy(): void
}
```

#### 2.2 Create MultiTierWebMBuffer
**File**: `auralis-web/frontend/src/services/MultiTierWebMBuffer.ts`

**Interface**:
```typescript
interface MultiTierWebMBuffer {
    // L1: WebM chunks
    getWebMChunk(trackId: number, chunkIdx: number): Promise<ArrayBuffer | null>
    storeWebMChunk(trackId: number, chunkIdx: number, data: ArrayBuffer): void

    // L2: Decoded AudioBuffers
    getDecodedChunk(trackId: number, chunkIdx: number): Promise<AudioBuffer | null>
    storeDecodedChunk(trackId: number, chunkIdx: number, buffer: AudioBuffer): void

    // L3: Processed AudioBuffers
    getProcessedChunk(
        trackId: number,
        chunkIdx: number,
        preset: string,
        intensity: number
    ): Promise<AudioBuffer | null>

    storeProcessedChunk(
        trackId: number,
        chunkIdx: number,
        preset: string,
        intensity: number,
        buffer: AudioBuffer
    ): void

    // Cache management
    clear(): void
    getStats(): CacheStats
    evictLRU(): void
}
```

**Cache Limits**:
```typescript
const CACHE_LIMITS = {
    maxWebMChunks: 50,        // ~38 MB
    maxDecodedChunks: 6,      // ~32 MB
    maxProcessedPerPreset: 3  // ~16 MB per preset
};
```

#### 2.3 Create ClientDSPProcessor
**File**: `auralis-web/frontend/src/services/ClientDSPProcessor.ts`

**Interface**:
```typescript
interface ClientDSPProcessor {
    processAudioBuffer(
        buffer: AudioBuffer,
        fingerprint: AudioFingerprint,
        preset: string,
        intensity: number
    ): Promise<AudioBuffer>
}
```

**Processing Steps**:
1. Extract channel data from AudioBuffer
2. Generate processing targets from fingerprint + preset
3. Apply 26-band psychoacoustic EQ
4. Apply adaptive dynamics (compression + limiting)
5. Apply stereo enhancement
6. Create new AudioBuffer with processed data
7. Return processed buffer

**Note**: This will use Web Audio API's native nodes where possible (BiquadFilterNode, DynamicsCompressorNode) plus custom processing for advanced features.

#### 2.4 Wire Up to UI
**File**: `auralis-web/frontend/src/components/BottomPlayerBarUnified.tsx`

**Changes**:
- Replace `MSEPlayerInternal` and `HTML5AudioPlayerInternal` with `UnifiedWebMAudioPlayer`
- Simplify mode switching (just toggle `enhancementEnabled` prop)
- Remove player destruction/recreation logic
- Update state management

**Before** (~320 lines with dual player logic):
```typescript
const [msePlayer, setMSEPlayer] = useState<MSEPlayerInternal | null>(null);
const [html5Player, setHTML5Player] = useState<HTML5AudioPlayerInternal | null>(null);
const [currentMode, setCurrentMode] = useState<'mse' | 'html5'>('mse');

const switchMode = async (newMode: 'mse' | 'html5') => {
    // Complex player switching logic
    const position = getCurrentPosition();
    await destroyCurrentPlayer();
    await initializeNewPlayer(newMode);
    await seekTo(position);
    ...
};
```

**After** (~200 lines with unified player):
```typescript
const [player, setPlayer] = useState<UnifiedWebMAudioPlayer | null>(null);
const [enhancementEnabled, setEnhancementEnabled] = useState(false);

const toggleEnhancement = () => {
    if (player) {
        player.setEnhancement(!enhancementEnabled);
        setEnhancementEnabled(!enhancementEnabled);
    }
};
```

### Phase 3: Remove Old Code (1 hour)

#### 3.1 Delete Old Player Implementations
**Files to delete**:
- `auralis-web/frontend/src/player/MSEPlayerInternal.ts` (~400 lines)
- `auralis-web/frontend/src/player/HTML5AudioPlayerInternal.ts` (~350 lines)
- `auralis-web/frontend/src/player/UnifiedPlayerManager.ts` (~220 lines)

**Total code removed**: ~970 lines

#### 3.2 Delete Old Backend Processing
**Files to delete**:
- `auralis-web/backend/streaming/multi_tier_buffer.py` (~348 lines)
- `auralis-web/backend/streaming/unified_streaming.py` (~340 lines)
- `auralis-web/backend/streaming/chunked_processor.py` (~200 lines)

**Total code removed**: ~888 lines

#### 3.3 Update Imports and References
**Files to update**:
- `auralis-web/frontend/src/components/ComfortableApp.tsx`
- `auralis-web/frontend/src/hooks/useAudioPlayer.tsx`
- `auralis-web/backend/main.py` (remove old router includes)

### Phase 4: Testing & Validation (2 hours)

#### 4.1 Unit Tests
**New test file**: `tests/frontend/UnifiedWebMAudioPlayer.test.tsx`

**Test cases**:
- ✅ Player initialization
- ✅ WebM chunk fetching and caching
- ✅ AudioBuffer decoding
- ✅ Direct playback (enhancement off)
- ✅ Enhanced playback (enhancement on)
- ✅ Preset switching
- ✅ Enhancement toggling
- ✅ Seek functionality
- ✅ Multi-tier cache behavior
- ✅ Error handling

#### 4.2 Integration Tests
**Test scenarios**:
1. **Cold start**: First track, no cache
2. **Warm cache**: Second play, WebM cached
3. **Hot cache**: Same preset, processed cached
4. **Preset switching**: L1 hit (instant), L2 miss (500ms)
5. **Enhancement toggle**: Seamless transition
6. **Long playback**: 10+ minutes, chunk transitions
7. **Seeking**: Jump to middle, backward/forward
8. **Memory usage**: Verify cache limits respected

#### 4.3 Performance Benchmarks
**Metrics to collect**:
- WebM decoding time (target: 50-100ms per chunk)
- DSP processing time (target: 200-500ms per chunk)
- Cache hit rates (target: 85%+ after warm-up)
- Memory usage (target: <150 MB total)
- Preset switching latency (target: <100ms on cache hit)

#### 4.4 Manual Testing Checklist
- [ ] Load track, play unenhanced
- [ ] Toggle enhancement during playback
- [ ] Switch presets during playback
- [ ] Seek during playback
- [ ] Skip tracks rapidly
- [ ] Test with 50+ track library
- [ ] Verify no memory leaks (1 hour playback)
- [ ] Test on Chrome, Firefox, Safari
- [ ] Test on mobile (iOS Safari, Chrome Android)

---

## Benefits

### 1. Code Simplification

| Component | Before | After | Reduction |
|-----------|--------|-------|-----------|
| Backend streaming | 888 lines | 150 lines | -83% |
| Frontend player | 970 lines | 600 lines | -38% |
| **Total** | **1,858 lines** | **750 lines** | **-60%** |

### 2. Bug Elimination

**Eliminated bug classes**:
- ✅ Dual player state synchronization bugs
- ✅ Mode switching race conditions
- ✅ Memory leaks from incomplete cleanup
- ✅ Volume jump artifacts during mode switch
- ✅ Position drift between players

**Estimated bug reduction**: 60-70% of current reported issues

### 3. Performance Improvements

**Network bandwidth**:
- WebM chunks: 769 KB vs WAV: 5.3 MB
- 86% reduction in transfer size
- Faster loading on slow connections

**Memory efficiency**:
- Can cache 50 WebM chunks vs 6 WAV chunks
- Better cache hit rates
- Lower memory pressure

**User experience**:
- No playback interruption on enhancement toggle
- Smoother preset switching
- Instant mode changes

### 4. Architecture Clarity

**Before**: Dual architecture with unclear boundaries
```
Frontend:
  - MSE Player (unenhanced)
  - HTML5 Audio Player (enhanced)
  - Unified Player Manager (coordination)

Backend:
  - MSE Path (WebM encoding)
  - MTB Path (WAV processing)
  - Dual routing logic
```

**After**: Single unified path
```
Frontend:
  - Unified WebM/Opus Player
  - Multi-tier cache (WebM → decoded → processed)
  - Client-side DSP

Backend:
  - Single WebM/Opus endpoint
  - Simple caching
```

---

## Risks & Mitigations

### Risk 1: Client-Side Processing Performance

**Risk**: DSP processing might be too slow in JavaScript
**Likelihood**: Low
**Impact**: High

**Mitigation**:
- Use Web Audio API's native nodes where possible (fast)
- Optimize custom processing with typed arrays
- Use Web Workers for heavy computation
- Benchmark early, optimize critical paths

**Fallback**: If too slow, can fall back to server-side processing (but evidence suggests client-side will work fine)

### Risk 2: Browser Compatibility

**Risk**: Web Audio API support inconsistencies
**Likelihood**: Low (97% browser support)
**Impact**: Medium

**Mitigation**:
- Feature detection with graceful degradation
- Polyfills for older browsers
- Comprehensive cross-browser testing

**Fallback**: Fall back to simple HTML5 Audio for unsupported browsers

### Risk 3: Cache Management Complexity

**Risk**: Multi-tier cache could be complex to debug
**Likelihood**: Medium
**Impact**: Low

**Mitigation**:
- Comprehensive logging and debugging tools
- Cache stats UI for monitoring
- Clear eviction policies (LRU)
- Extensive unit tests

### Risk 4: Migration Issues

**Risk**: Breaking existing users during migration
**Likelihood**: Low (controlled rollout)
**Impact**: High

**Mitigation**:
- Feature flag for gradual rollout
- Extensive testing before release
- Clear rollback plan
- Monitor error rates closely

---

## Success Criteria

### Functional
- ✅ Playback works in both direct and enhanced modes
- ✅ Preset switching works with <100ms latency (cache hit)
- ✅ Enhancement toggle works without playback interruption
- ✅ Seeking works accurately
- ✅ Memory usage stays under limits

### Performance
- ✅ WebM decoding: <100ms per chunk
- ✅ DSP processing: <500ms per chunk (cold), <50ms (cached)
- ✅ Cache hit rate: >85% after warm-up
- ✅ Total memory: <150 MB (50 WebM + cache tiers)

### Quality
- ✅ No audio quality degradation vs current system
- ✅ No artifacts during chunk transitions
- ✅ Smooth playback with no glitches

### Code Quality
- ✅ 60% code reduction (1,858 → 750 lines)
- ✅ 100% test pass rate
- ✅ No regressions in existing functionality

---

## Rollout Plan

### Phase 1: Development (Week 1)
- Implement backend simplification
- Implement frontend unified player
- Remove old code
- Write comprehensive tests

### Phase 2: Testing (Week 2)
- Unit tests (100% coverage target)
- Integration tests
- Performance benchmarks
- Manual QA

### Phase 3: Beta Testing (Week 3)
- Deploy behind feature flag
- Enable for 10% of users
- Monitor error rates and performance
- Collect user feedback

### Phase 4: Full Rollout (Week 4)
- Gradually increase to 50%, then 100%
- Monitor metrics continuously
- Address any issues quickly
- Document lessons learned

---

## Documentation Updates Needed

### User Documentation
- Update [BETA_USER_GUIDE.md](../../BETA_USER_GUIDE.md)
- Update feature descriptions
- No user-facing changes (UX stays same)

### Developer Documentation
- Update [CLAUDE.md](../../CLAUDE.md) architecture section
- Remove dual player references
- Add unified player documentation
- Update testing guide

### Technical Paper
- Update [auralis_realtime_adaptive_mastering_v2.md](../paper/auralis_realtime_adaptive_mastering_v2.md)
- Section 4.2: Frontend Architecture
- Remove dual player complexity discussion
- Add unified WebM/Opus architecture

---

## Timeline

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| **Phase 1: Backend** | 2 hours | Simplified streaming endpoint, removed old code |
| **Phase 2: Frontend** | 4-5 hours | Unified player, multi-tier cache, DSP processor |
| **Phase 3: Cleanup** | 1 hour | Deleted old code, updated imports |
| **Phase 4: Testing** | 2 hours | Tests passing, benchmarks collected |
| **Total** | **9-10 hours** | **Production-ready unified architecture** |

**Target completion**: Within 2 weeks (part-time work)

---

## Next Steps

1. **Get approval** on this roadmap
2. **Create feature branch**: `feature/unified-player-architecture`
3. **Start Phase 1**: Backend simplification
4. **Regular commits**: Small, incremental changes
5. **Continuous testing**: Run tests after each phase
6. **Document progress**: Update this roadmap with actual vs estimated times

---

## Appendix A: Code Examples

### A.1 Simplified Backend Endpoint

```python
# auralis-web/backend/routers/streaming.py

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/api/audio/stream/{track_id}/chunk/{chunk_idx}")
async def stream_webm_chunk(track_id: int, chunk_idx: int):
    """
    Unified streaming endpoint - always returns WebM/Opus.
    Processing happens client-side with Web Audio API.

    Args:
        track_id: Database track ID
        chunk_idx: Chunk index (0-based)

    Returns:
        WebM/Opus audio chunk (192 kbps VBR, ~769 KB for 30s)
    """

    # Get track from database
    track = library_manager.tracks.get_by_id(track_id)
    if not track:
        raise HTTPException(404, f"Track {track_id} not found")

    # Check WebM cache
    cache_key = f"webm_{track_id}_{chunk_idx}"
    cached = webm_cache.get(cache_key)

    if cached:
        logger.debug(f"WebM cache hit: {cache_key}")
        return StreamingResponse(
            BytesIO(cached),
            media_type='audio/webm; codecs=opus',
            headers={
                'Cache-Control': 'public, max-age=31536000',  # 1 year
                'Content-Length': str(len(cached))
            }
        )

    # Encode chunk to WebM/Opus
    logger.debug(f"Encoding WebM chunk: track={track_id}, chunk={chunk_idx}")
    webm_data = await webm_encoder.encode_chunk(
        track.filepath,
        chunk_idx,
        bitrate=192,  # 192 kbps VBR
        quality=10    # Best quality
    )

    # Cache for future requests
    webm_cache.set(cache_key, webm_data, ttl=86400)  # 24 hours

    return StreamingResponse(
        BytesIO(webm_data),
        media_type='audio/webm; codecs=opus',
        headers={
            'Cache-Control': 'public, max-age=31536000',
            'Content-Length': str(len(webm_data))
        }
    )
```

### A.2 Client-Side DSP Processing

```typescript
// auralis-web/frontend/src/services/ClientDSPProcessor.ts

import { AudioFingerprint } from '../types/fingerprint';

export class ClientDSPProcessor {
    private audioContext: AudioContext;

    constructor(audioContext: AudioContext) {
        this.audioContext = audioContext;
    }

    async processAudioBuffer(
        buffer: AudioBuffer,
        fingerprint: AudioFingerprint,
        preset: string,
        intensity: number
    ): Promise<AudioBuffer> {
        // Extract channel data
        const leftChannel = buffer.getChannelData(0);
        const rightChannel = buffer.getChannelData(1);

        // Generate processing targets from fingerprint
        const targets = this.generateTargets(fingerprint, preset, intensity);

        // Apply processing chain
        const processed = {
            left: new Float32Array(leftChannel.length),
            right: new Float32Array(rightChannel.length)
        };

        // Copy original data
        processed.left.set(leftChannel);
        processed.right.set(rightChannel);

        // 1. Apply psychoacoustic EQ
        this.applyEQ(processed, targets.eq, buffer.sampleRate);

        // 2. Apply adaptive dynamics
        this.applyDynamics(processed, targets.dynamics, buffer.sampleRate);

        // 3. Apply stereo enhancement
        this.applyStereoEnhancement(processed, targets.stereo);

        // 4. Apply soft limiting
        this.applySoftLimiter(processed, buffer.sampleRate);

        // Create new AudioBuffer with processed data
        const processedBuffer = this.audioContext.createBuffer(
            2,
            buffer.length,
            buffer.sampleRate
        );
        processedBuffer.copyToChannel(processed.left, 0);
        processedBuffer.copyToChannel(processed.right, 1);

        return processedBuffer;
    }

    private generateTargets(
        fingerprint: AudioFingerprint,
        preset: string,
        intensity: number
    ) {
        // Generate fingerprint-aware processing targets
        // (Same logic as backend, but in TypeScript)

        const targets = {
            eq: this.generateEQTargets(fingerprint, preset, intensity),
            dynamics: this.generateDynamicsTargets(fingerprint, preset, intensity),
            stereo: this.generateStereoTargets(fingerprint, preset, intensity)
        };

        return targets;
    }

    private applyEQ(
        audio: { left: Float32Array, right: Float32Array },
        eqTargets: EQTargets,
        sampleRate: number
    ) {
        // Apply 26-band psychoacoustic EQ
        // Use biquad filters for each band
        for (const band of eqTargets.bands) {
            this.applyBiquadFilter(
                audio.left,
                band.frequency,
                band.gain,
                band.q,
                sampleRate
            );
            this.applyBiquadFilter(
                audio.right,
                band.frequency,
                band.gain,
                band.q,
                sampleRate
            );
        }
    }

    private applyDynamics(
        audio: { left: Float32Array, right: Float32Array },
        dynamicsTargets: DynamicsTargets,
        sampleRate: number
    ) {
        // Apply adaptive compression and limiting
        // Use envelope follower + gain reduction
        const envelope = this.computeEnvelope(
            audio.left,
            audio.right,
            sampleRate,
            dynamicsTargets.attackMs,
            dynamicsTargets.releaseMs
        );

        // Compute gain reduction
        const gainReduction = this.computeGainReduction(
            envelope,
            dynamicsTargets.threshold,
            dynamicsTargets.ratio,
            dynamicsTargets.knee
        );

        // Apply gain reduction
        for (let i = 0; i < audio.left.length; i++) {
            audio.left[i] *= gainReduction[i];
            audio.right[i] *= gainReduction[i];
        }
    }

    private applyStereoEnhancement(
        audio: { left: Float32Array, right: Float32Array },
        stereoTargets: StereoTargets
    ) {
        // Mid-side processing for stereo width
        for (let i = 0; i < audio.left.length; i++) {
            const mid = (audio.left[i] + audio.right[i]) * 0.5;
            const side = (audio.left[i] - audio.right[i]) * 0.5;

            // Adjust stereo width
            const enhancedSide = side * stereoTargets.width;

            audio.left[i] = mid + enhancedSide;
            audio.right[i] = mid - enhancedSide;
        }
    }

    private applySoftLimiter(
        audio: { left: Float32Array, right: Float32Array },
        sampleRate: number
    ) {
        // Soft limiting with tanh saturation
        const ceiling = 0.95;

        for (let i = 0; i < audio.left.length; i++) {
            audio.left[i] = Math.tanh(audio.left[i] / ceiling) * ceiling;
            audio.right[i] = Math.tanh(audio.right[i] / ceiling) * ceiling;
        }
    }
}
```

---

**Status**: Ready for implementation
**Priority**: P0
**Assignee**: Claude + User
**Start Date**: November 1, 2025
**Target Completion**: November 15, 2025
