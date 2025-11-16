# Phase 3: UnifiedWebMAudioPlayer Decomposition - Implementation Guide

## Overview

Breaking down the 1098-line monolithic service into 5 focused services:

```
UnifiedWebMAudioPlayer (1098 lines) →
├── ChunkPreloadManager (300 lines)
├── AudioContextController (250 lines)
├── TimingEngine (150 lines) ← CRITICAL: Contains timing fix
├── PlaybackController (150 lines)
└── UnifiedWebMAudioPlayer (200 lines, facade)
```

## Service Responsibilities

### 1. ChunkPreloadManager (300 lines)

**What it does**: Manages chunk loading, priority queue, and decoding

**Extract from UnifiedWebMAudioPlayer**:
- `ChunkLoadPriorityQueue` class (lines 114-213)
- `preloadChunk()` method (lines 340-368)
- `processLoadQueue()` method (lines 369-483)
- Related state:
  - `loadQueue: ChunkLoadPriorityQueue`
  - `activeLoads: Map<number, Promise<void>>`

**Public interface**:
```typescript
class ChunkPreloadManager {
  queueChunk(chunkIndex: number, priority: number): void
  private processLoadQueue(): Promise<void>
  private preloadChunk(chunkIndex: number, priority: number): Promise<void>
  getQueueSize(): number
  isLoading(chunkIndex: number): boolean
}
```

### 2. AudioContextController (250 lines)

**What it does**: Manages Web Audio API context, source creation, and scheduling

**Extract from UnifiedWebMAudioPlayer**:
- `ensureAudioContext()` method (lines 270-281)
- `playChunk()` method (lines 551-804)
- `setVolume()` handling (volume state + gainNode)
- Related state:
  - `audioContext: AudioContext | null`
  - `currentSource: AudioBufferSourceNode | null`
  - `gainNode: GainNode | null`
  - `currentChunkIndex: number`

**Public interface**:
```typescript
class AudioContextController {
  ensureAudioContext(): void
  playChunk(
    chunkIndex: number,
    audioBuffer: AudioBuffer,
    offset: number
  ): Promise<void>
  setVolume(volume: number): void
  stopCurrentSource(): void
  getState(): 'playing' | 'stopped' | 'error'
}
```

### 3. TimingEngine (150 lines) ⭐ CRITICAL

**What it does**: Calculates accurate timing, emits timeupdate events at 50ms interval

**Extract from UnifiedWebMAudioPlayer**:
- `startTimeUpdates()` method (lines 1067-1083) ← **TIMING FIX IS HERE (50ms interval)**
- `stopTimeUpdates()` method (lines 1084-1090)
- `getCurrentTime()` method (lines 970-983)
- `getCurrentTimeDebug()` method (lines 994-1007)
- Related state:
  - `audioContextStartTime: number` ← **Single source of truth**
  - `trackStartTime: number`
  - `pauseTime: number`
  - `timeUpdateInterval: number | null`

**Public interface**:
```typescript
class TimingEngine {
  startTimeUpdates(): void
  stopTimeUpdates(): void
  getCurrentTime(): number
  getCurrentTimeDebug(): DebugInfo
  setPauseTime(time: number): void
  updateTimingReference(audioCtxTime: number, trackTime: number): void
  on(event: 'timeupdate', callback: (data: any) => void): void
}
```

**Why this matters**:
- Isolates the timing fix (50ms interval) to one place
- Makes it easy to verify the fix is working
- Makes timing behavior testable in isolation
- Enables future timing improvements without affecting other services

### 4. PlaybackController (150 lines)

**What it does**: Manages playback state machine (play, pause, seek)

**Extract from UnifiedWebMAudioPlayer**:
- `play()` method (lines 484-550)
- `pause()` method (part of play/pause logic)
- `seek()` method (lines 805-874)
- `getState()` method (lines 1009-1015)
- `setState()` method (lines 1056-1064)
- Related state:
  - `state: PlaybackState`
  - `pauseTime: number`

**Public interface**:
```typescript
class PlaybackController {
  async play(): Promise<void>
  pause(): void
  async seek(time: number): Promise<void>
  getState(): PlaybackState
  setState(newState: PlaybackState): void
}
```

### 5. UnifiedWebMAudioPlayer (200 lines, Facade)

**What it does**: Orchestrates the services, maintains public API

**Responsibilities**:
- Config management
- Service initialization and lifecycle
- Track loading and metadata management
- Event management (emit/on/off)
- Error handling
- Buffer cache management
- Public API (all methods delegate to services)

**Public interface** (unchanged):
```typescript
class UnifiedWebMAudioPlayer {
  // Config & lifecycle
  constructor(config: UnifiedWebMAudioPlayerConfig)

  // Track management
  async loadTrack(trackId: number): Promise<void>
  getMetadata(): StreamMetadata | null

  // Playback control (delegates to PlaybackController)
  async play(): Promise<void>
  pause(): void
  async seek(time: number): Promise<void>

  // Timing (delegates to TimingEngine)
  getCurrentTime(): number
  getDuration(): number
  getCurrentTimeDebug(): DebugInfo

  // Audio control (delegates to AudioContextController)
  setVolume(volume: number): void

  // Enhancement
  async setEnhanced(enabled: boolean, preset?: string): Promise<void>
  async setPreset(preset: string): Promise<void>

  // State & events
  getState(): PlaybackState
  on(event: string, callback: EventCallback): void
  off(event: string, callback?: EventCallback): void

  // Cleanup
  destroy(): void
}
```

## Implementation Steps

### Step 1: Create Base Service Interfaces (30 min)

Create `src/services/player/types.ts`:
```typescript
export interface IChunkPreloadManager {
  queueChunk(chunkIndex: number, priority: number): void
}

export interface ITimingEngine {
  getCurrentTime(): number
  startTimeUpdates(): void
}

// ... etc
```

### Step 2: Extract ChunkPreloadManager (45 min)

Create `src/services/player/ChunkPreloadManager.ts`:
- Move `ChunkLoadPriorityQueue` class
- Move chunk loading methods
- Keep MultiTierWebMBuffer reference (passed in)

### Step 3: Extract AudioContextController (45 min)

Create `src/services/player/AudioContextController.ts`:
- Move `ensureAudioContext()`
- Move `playChunk()`
- Move Web Audio scheduling logic

### Step 4: Extract TimingEngine (30 min) ⭐

Create `src/services/player/TimingEngine.ts`:
- Move timing calculation logic
- Move `startTimeUpdates()` ← **THE TIMING FIX**
- Move `getCurrentTime()` and `getCurrentTimeDebug()`
- This is critical: Makes the 50ms interval fix visible and testable

### Step 5: Extract PlaybackController (30 min)

Create `src/services/player/PlaybackController.ts`:
- Move `play()`, `pause()`, `seek()`
- Move state management

### Step 6: Refactor UnifiedWebMAudioPlayer (30 min)

Modify existing `UnifiedWebMAudioPlayer.ts`:
- Inject services
- Delegate to services
- Keep public API unchanged
- Maintain event management

### Step 7: Testing & Validation (30 min)

- Verify all existing tests pass
- Test service isolation
- Verify timing fix works

## File Structure After Phase 3

```
src/services/
├── UnifiedWebMAudioPlayer.ts (200 lines, facade)
└── player/
    ├── types.ts (50 lines) - Interfaces and types
    ├── MultiTierWebMBuffer.ts (30 lines) - Buffer caching
    ├── ChunkPreloadManager.ts (300 lines)
    ├── AudioContextController.ts (250 lines)
    ├── TimingEngine.ts (150 lines) ⭐
    └── PlaybackController.ts (150 lines)
```

## Expected Outcomes

### Code Quality Improvements

| Aspect | Before | After | Benefit |
|--------|--------|-------|---------|
| Service size | 1098 lines | Max 300 lines | Easier to understand |
| Timing debugging | Trace 1098 lines | Check 150 lines | 7x reduction |
| Chunk loading issues | Mixed with timing | Isolated service | Clear separation |
| Audio control | Mixed with playback | Isolated service | Independent testing |

### Testability

**Before**:
```typescript
// Hard to test chunk loading without full service
const player = new UnifiedWebMAudioPlayer()
```

**After**:
```typescript
// Can test chunk loading in isolation
const manager = new ChunkPreloadManager(buffer, createEmitter())
manager.queueChunk(1, 1)
```

### Debuggability

**Before**:
- Timing lag? Scan 1098 lines
- Chunk not loading? Scan 1098 lines
- Audio not playing? Scan 1098 lines

**After**:
- Timing lag? Check TimingEngine (150 lines)
- Chunk not loading? Check ChunkPreloadManager (300 lines)
- Audio not playing? Check AudioContextController (250 lines)

## Critical Notes

### Maintaining Public API
- ✅ UnifiedWebMAudioPlayer public interface stays identical
- ✅ No breaking changes to consumers
- ✅ Services are internal implementation details
- ✅ Full backward compatibility

### Timing Fix Safety
- ✅ The 50ms interval fix stays in TimingEngine.startTimeUpdates()
- ✅ No behavior changes, only code organization
- ✅ Easier to verify the fix is working
- ✅ Easier to improve timing in the future

### Event Propagation
- Services will emit events via callbacks
- UnifiedWebMAudioPlayer aggregates and re-emits
- No change to event API

## Risk Mitigation

### Potential Issues & Solutions

**Issue**: Services need access to shared state
**Solution**: Pass shared state (buffer, metadata) to services via constructor

**Issue**: Complex interdependencies
**Solution**: Clear interfaces define service contracts, UnifiedWebMAudioPlayer orchestrates

**Issue**: Event propagation broken
**Solution**: Services emit to callbacks, UnifiedWebMAudioPlayer manages event listeners

**Issue**: Timing fix doesn't work after refactoring
**Solution**: Verify 50ms interval in TimingEngine, test timing separately

## Timeline

- **Step 1** (Create interfaces): 30 min
- **Step 2** (ChunkPreloadManager): 45 min
- **Step 3** (AudioContextController): 45 min
- **Step 4** (TimingEngine): 30 min ⭐
- **Step 5** (PlaybackController): 30 min
- **Step 6** (Refactor facade): 30 min
- **Step 7** (Test & validate): 30 min

**Total**: ~3.5 hours (overestimate to be safe)

## Success Criteria

✅ All services < 350 lines
✅ Each service has single, clear responsibility
✅ Public API unchanged
✅ All existing tests pass
✅ Timing fix works correctly (50ms interval verified)
✅ Services independently testable
✅ No breaking changes to consumers
✅ Code compiles without errors

## Next Steps

1. Start with Step 1 (create types)
2. Extract services one at a time
3. Test after each extraction
4. Verify timing fix in TimingEngine
5. Complete Phase 3
6. Proceed to Phase 4
