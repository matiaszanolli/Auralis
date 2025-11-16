# Phase 3 Execution Strategy

## Current Status

✅ **Completed**:
- types.ts - Service interfaces
- TimingEngine.ts - Timing fix isolated (150 lines)

⏳ **Remaining**:
- ChunkPreloadManager.ts - Extract from lines 114-483
- AudioContextController.ts - Extract from lines 270-804
- PlaybackController.ts - Extract from play/pause/seek logic
- Refactor UnifiedWebMAudioPlayer as facade

## Challenge: UnifiedWebMAudioPlayer is Complex

The 1098-line service has **deeply interwoven responsibilities**:

```
audioContext           (Web Audio API)
  ↓ controls
currentSource          (Audio playback)
  ↓ scheduled by
playChunk()            (Lines 551-804, 250+ lines)
  ↓ uses
buffer (MultiTierWebMBuffer)
  ↓ stores
chunks (ChunkInfo[] array)
  ↓ loaded by
preloadChunk()         (Lines 340-368)
  ↓ queued by
ChunkLoadPriorityQueue (Lines 114-213)
  ↓ which emits to
loadQueue.processLoadQueue() (Lines 369-483)
  ↓ which affects
currentChunkIndex       (Playback position)
  ↓ which is used by
getCurrentTime()        (Lines 970-983, uses audioContext timing)
  ↓ which is emitted via
startTimeUpdates()      (Now in TimingEngine)
```

**Key insight**: These aren't independent—they're a state machine.

## Extraction Strategy: Bottom-Up

Instead of extracting services independently, we'll extract them in dependency order:

### Step 1: Extract MultiTierWebMBuffer (30 min)
**Why first**: Everything else depends on it

Create `src/services/player/MultiTierWebMBuffer.ts`:
- Move `MultiTierWebMBuffer` class (lines 79-111)
- Move `getCacheKey()` method
- This is stable and doesn't change

### Step 2: Extract ChunkLoadPriorityQueue (30 min)
**Why second**: ChunkPreloadManager will use it

Create `src/services/player/ChunkLoadPriorityQueue.ts`:
- Move `ChunkLoadPriorityQueue` class (lines 114-213)
- Dependencies: None (self-contained)

### Step 3: Extract ChunkPreloadManager (45 min)
**Why third**: Chunk loading can be independent

Create `src/services/player/ChunkPreloadManager.ts`:
- Move `preloadChunk()` (lines 340-368)
- Move `processLoadQueue()` (lines 369-483)
- Move `loadQueue` and `activeLoads` state
- Constructor: `constructor(buffer: MultiTierWebMBuffer, queue: ChunkLoadPriorityQueue)`
- Dependencies: MultiTierWebMBuffer, ChunkLoadPriorityQueue

### Step 4: Extract AudioContextController (45 min)
**Why fourth**: Audio control is separate concern

Create `src/services/player/AudioContextController.ts`:
- Move `ensureAudioContext()` (lines 270-281)
- Move `playChunk()` (lines 551-804) ← **LARGE!**
- Move audio-related state: audioContext, currentSource, gainNode, volume
- Constructor: `constructor(chunkDuration: number, chunkInterval: number)`
- Dependencies: None (uses AudioContext API)

### Step 5: Extract PlaybackController (30 min)
**Why fifth**: After audio is isolated

Create `src/services/player/PlaybackController.ts`:
- Move `play()` logic
- Move `pause()` logic
- Move `seek()` (lines 805-874)
- Move state machine: state, currentChunkIndex, pauseTime
- Constructor: `constructor()`
- Dependencies: Will call back to UnifiedWebMAudioPlayer for orchestration

### Step 6: Refactor UnifiedWebMAudioPlayer (30 min)
**Why last**: After services are extracted

Modify `src/services/UnifiedWebMAudioPlayer.ts`:
- Remove extracted code
- Inject services
- Keep public API unchanged
- Delegate to services
- Maintain event management

### Step 7: Integration (30 min)
- Wire services together
- Verify public API still works
- Test in browser

## Key Integration Points

### Message Passing Between Services

Services communicate via callbacks, not direct method calls:

```typescript
// ChunkPreloadManager needs to notify about load completion
chunkPreloadManager.on('chunkLoaded', (chunkIndex: number) => {
  // UnifiedWebMAudioPlayer can now schedule playback
});

// AudioContextController needs to notify about source end
audioContextController.on('sourceEnded', () => {
  // PlaybackController can queue next chunk
});

// TimingEngine emits timeupdate
timingEngine.on('timeupdate', (event: TimeUpdateEvent) => {
  // UnifiedWebMAudioPlayer re-emits to listeners
});
```

### Shared State

UnifiedWebMAudioPlayer maintains:
- `buffer: MultiTierWebMBuffer` - Shared with ChunkPreloadManager
- `metadata: StreamMetadata` - Read by all services
- `chunks: ChunkInfo[]` - Updated by ChunkPreloadManager, read by AudioContextController

## Risk Mitigation

### Risk 1: Services get out of sync
**Mitigation**: Clear contracts via interfaces (types.ts already defines them)

### Risk 2: Circular dependencies
**Mitigation**: Only UnifiedWebMAudioPlayer orchestrates; services don't know about each other

### Risk 3: Timing breaks during refactoring
**Mitigation**: TimingEngine is already isolated; test it first, then other services

### Risk 4: Public API changes
**Mitigation**: Keep UnifiedWebMAudioPlayer's public interface unchanged; all changes are internal

## Timeline Revised (Based on Complexity)

- Step 1 (MultiTierWebMBuffer): 30 min
- Step 2 (ChunkLoadPriorityQueue): 30 min
- Step 3 (ChunkPreloadManager): 45 min
- Step 4 (AudioContextController): 60 min ← **Larger than expected (playChunk is complex)**
- Step 5 (PlaybackController): 30 min
- Step 6 (Refactor facade): 45 min ← **More complex than estimated**
- Step 7 (Integration & testing): 45 min

**Revised total**: ~4.5 hours (was 3.5 hours estimate)

But this is still worth it because:
- ✅ Each service becomes independently testable
- ✅ playChunk() will be in AudioContextController (clear responsibility)
- ✅ Chunk loading isolated in ChunkPreloadManager
- ✅ Timing fix obvious in TimingEngine

## Success Criteria

After Phase 3 complete:

```
src/services/
├── UnifiedWebMAudioPlayer.ts (200 lines, facade)
└── player/
    ├── types.ts (50 lines)
    ├── MultiTierWebMBuffer.ts (40 lines)
    ├── ChunkLoadPriorityQueue.ts (100 lines)
    ├── ChunkPreloadManager.ts (150 lines)
    ├── AudioContextController.ts (250 lines)
    ├── TimingEngine.ts (150 lines)
    └── PlaybackController.ts (150 lines)
```

All files < 250 lines, except AudioContextController (playChunk is complex).

✅ Public API identical
✅ All tests pass
✅ Timing fix verified
✅ Services independently testable

## Execution Order

We'll do this step-by-step, committing after each major extraction (after step 3, after step 6).

Ready to start?
