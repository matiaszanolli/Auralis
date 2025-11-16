# Phase 3.6: UnifiedWebMAudioPlayer Facade Refactoring Guide

## Overview

In this phase, we refactor `UnifiedWebMAudioPlayer` to become a thin orchestrator facade that delegates to the services extracted in Phase 3.1-3.5.

**Key Principle**: No public API changes, all breaking changes are internal only.

---

## Current State

The original monolithic class has ~1098 lines with all logic tightly coupled:

```
UnifiedWebMAudioPlayer (1098 lines)
├── loadTrack()
├── play()
├── pause()
├── seek()
├── playChunk()      ← 250 lines, complex!
├── preloadChunk()   ← 28 lines
├── processLoadQueue() ← 110 lines
├── setEnhanced()
├── setVolume()
├── on/off/emit()
└── [dozens more methods and properties]
```

---

## Target Architecture

After Phase 3.6, UnifiedWebMAudioPlayer becomes a facade:

```
UnifiedWebMAudioPlayer (200-250 lines)
├── Services Injected:
│   ├── timingEngine: TimingEngine
│   ├── chunkPreloader: ChunkPreloadManager
│   ├── audioController: AudioContextController
│   ├── playbackController: PlaybackController
│   ├── buffer: MultiTierWebMBuffer
│   └── loadQueue: ChunkLoadPriorityQueue
│
├── Public API (Unchanged):
│   ├── loadTrack()
│   ├── play()
│   ├── pause()
│   ├── seek()
│   ├── setVolume()
│   ├── setEnhanced()
│   └── on/off/emit()
│
└── Internal Implementation:
    └── Delegates to services + wires events
```

---

## Refactoring Steps

### Step 1: Add Service Instances (15 min)

Replace complex internal logic with service instances:

```typescript
// Before: Individual properties scattered
private audioContext: AudioContext | null = null;
private currentSource: AudioBufferSource | null = null;
private gainNode: GainNode | null = null;
private chunks: ChunkInfo[] = [];
private buffer: MultiTierWebMBuffer = new MultiTierWebMBuffer();
private loadQueue: ChunkLoadPriorityQueue = new ChunkLoadPriorityQueue();
private queueProcessorRunning = false;
// ... 20 more properties

// After: Organized as services
private timingEngine: TimingEngine;
private chunkPreloader: ChunkPreloadManager;
private audioController: AudioContextController;
private playbackController: PlaybackController;
private buffer: MultiTierWebMBuffer;
private loadQueue: ChunkLoadPriorityQueue;
```

**In constructor**:
```typescript
constructor(config: PlayerConfig) {
  this.buffer = new MultiTierWebMBuffer();
  this.loadQueue = new ChunkLoadPriorityQueue();
  this.chunkPreloader = new ChunkPreloadManager(
    this.buffer,
    this.loadQueue,
    config,
    null, // audioContext set later
    this.debug.bind(this)
  );
  this.audioController = new AudioContextController(
    config.chunkDuration || 10,
    config.chunkInterval || 10,
    this.debug.bind(this)
  );
  this.playbackController = new PlaybackController(this.debug.bind(this));
  this.timingEngine = new TimingEngine(null, this.debug.bind(this));
}
```

---

### Step 2: Simplify loadTrack() (15 min)

**Before**:
```typescript
async loadTrack(trackId: number): Promise<void> {
  // 1. Stop current playback
  // 2. Clear buffer cache
  // 3. Fetch metadata
  // 4. Initialize chunks
  // 5. Set up state
  // 6. Emit events
  // ~50 lines of detailed logic
}
```

**After**:
```typescript
async loadTrack(trackId: number): Promise<void> {
  try {
    this.setState('loading');

    // Stop current playback
    this.stop();
    this.buffer.clear();

    // Fetch metadata (unchanged)
    const response = await fetch(
      `${this.config.apiBaseUrl}/api/stream/${trackId}/metadata`
    );
    if (!response.ok) {
      throw new Error(`Failed to fetch metadata: ${response.statusText}`);
    }

    const metadata = await response.json();

    // Store metadata
    this.metadata = metadata;
    this.trackId = trackId;

    // Initialize services with new metadata
    this.playbackController.setMetadata(metadata);
    this.playbackController.initChunks(metadata.chunks.length);
    this.chunkPreloader.initChunks(metadata.chunks.length);
    this.audioController.updateChunkTiming(
      metadata.chunk_duration,
      metadata.chunk_interval
    );

    // Emit event
    this.emit('metadata-loaded', { metadata });
    this.setState('ready');

  } catch (error: any) {
    this.setState('error');
    this.emit('error', error);
    throw error;
  }
}
```

---

### Step 3: Simplify play() (10 min)

**Before**:
```typescript
async play(): Promise<void> {
  // Complex logic with chunk calculation,
  // state checks, loading, error handling
  // ~40 lines
}
```

**After**:
```typescript
async play(): Promise<void> {
  if (!this.trackId || !this.metadata) {
    throw new Error('No track loaded');
  }

  // Delegate to services
  this.audioController.ensureAudioContext();
  await this.audioController.resumeAudioContext();
  await this.playbackController.play();

  // Start timing updates
  this.timingEngine.startTimeUpdates();
  this.emit('playing');
}
```

The complex logic moves to PlaybackController and services.

---

### Step 4: Simplify pause() (5 min)

**Before**:
```typescript
pause(): void {
  // Stop source, calculate position, update state
  // ~15 lines
}
```

**After**:
```typescript
pause(): void {
  this.playbackController.pause();
  this.audioController.stopCurrentSource();
  this.timingEngine.stopTimeUpdates();
  this.timingEngine.setPauseTime(this.playbackController.getCurrentPosition());
  this.emit('paused');
}
```

---

### Step 5: Simplify seek() (15 min)

**Before**:
```typescript
async seek(time: number): Promise<void> {
  // Complex chunk calculation, priority queuing, loading, state management
  // ~60 lines
}
```

**After**:
```typescript
async seek(time: number): Promise<void> {
  if (!this.metadata) {
    throw new Error('No track loaded');
  }

  const wasPlaying = this.playbackController.getState() === 'playing';

  // Let PlaybackController handle seeking
  await this.playbackController.seek(time);

  // Update timing reference for accurate position
  this.timingEngine.setPauseTime(time);
  if (this.audioController.getAudioContext()) {
    this.timingEngine.updateTimingReference(
      this.audioController.getAudioContext()!.currentTime,
      time
    );
  }

  // If was playing, resume
  if (wasPlaying) {
    await this.play();
  }

  this.emit('seeked');
}
```

---

### Step 6: Wire Service Events (20 min)

Services emit events, facade listens and routes them:

```typescript
private wireServiceEvents(): void {
  // ChunkPreloadManager events
  this.chunkPreloader.on('chunk-loaded', (e) => {
    this.debug(`Chunk ${e.chunkIndex} loaded`);
    // Trigger playback if waiting
    if (this.playbackController.getState() === 'playing') {
      this.attemptPlayback();
    }
  });

  this.chunkPreloader.on('chunk-error', (e) => {
    this.debug(`Chunk ${e.chunkIndex} error: ${e.error.message}`);
    this.emit('chunk-error', e);
  });

  // PlaybackController events
  this.playbackController.on('play-requested', async (e) => {
    try {
      await this.playChunkInternal(
        e.chunkIndex,
        e.offsetInChunk
      );
    } catch (error) {
      this.setState('error');
      this.emit('error', error);
    }
  });

  this.playbackController.on('seek-requested', (e) => {
    // Queue chunks with appropriate priorities
    this.chunkPreloader.queueChunk(e.targetChunk, 2); // SEEK_TARGET
    if (e.adjacentChunks.prev !== null) {
      this.chunkPreloader.queueChunk(e.adjacentChunks.prev, 3); // ADJACENT
    }
    if (e.adjacentChunks.next !== null) {
      this.chunkPreloader.queueChunk(e.adjacentChunks.next, 3); // ADJACENT
    }
  });

  this.playbackController.on('state-changed', (e) => {
    this.state = e.state;
    this.emit('state', { state: e.state });
  });

  // AudioContextController events
  this.audioController.on('schedule-next-chunk', (e) => {
    this.chunkPreloader.queueChunk(e.chunkIndex, 1); // IMMEDIATE
  });

  this.audioController.on('play-next-chunk', async (e) => {
    try {
      await this.playChunkInternal(e.chunkIndex, 0);
    } catch (error) {
      this.debug(`Error playing next chunk: ${error.message}`);
    }
  });

  this.audioController.on('track-ended', () => {
    this.playbackController.setState('idle');
    this.emit('ended');
  });

  // TimingEngine events
  this.timingEngine.on('timeupdate', (e) => {
    this.emit('timeupdate', e);
  });
}
```

---

### Step 7: Internal Helper Methods (15 min)

Keep only the minimal orchestration logic:

```typescript
/**
 * Internal: Play a specific chunk
 * Called by PlaybackController or when transitioning between chunks
 */
private async playChunkInternal(chunkIndex: number, offset: number): Promise<void> {
  const chunk = this.playbackController.getChunk(chunkIndex);
  if (!chunk || !chunk.audioBuffer) {
    throw new Error(`Chunk ${chunkIndex} not loaded`);
  }

  // Let AudioContextController handle playback
  await this.audioController.playChunk(
    chunkIndex,
    chunk.audioBuffer,
    offset,
    this.playbackController.getState() === 'playing',
    this.playbackController.getChunkCount(),
    this.metadata
  );

  // Update controller state
  this.playbackController.setCurrentChunkIndex(chunkIndex);
}

/**
 * Internal: Attempt to play if chunk is loaded
 */
private async attemptPlayback(): Promise<void> {
  const currentChunk = this.playbackController.getChunk(
    this.playbackController.getCurrentChunkIndex()
  );
  if (currentChunk?.isLoaded && currentChunk.audioBuffer) {
    await this.playChunkInternal(
      this.playbackController.getCurrentChunkIndex(),
      0
    );
  }
}
```

---

### Step 8: Remove Extracted Methods (30 min)

Delete these methods (now in services):

- ~~`ensureAudioContext()`~~ → AudioContextController.ensureAudioContext()
- ~~`playChunk()`~~ → AudioContextController.playChunk()
- ~~`preloadChunk()`~~ → ChunkPreloadManager.queueChunk()
- ~~`processLoadQueue()`~~ → Internal to ChunkPreloadManager
- ~~`getCurrentTime()`~~ → TimingEngine.getCurrentTime()
- ~~`startTimeUpdates()`~~ → TimingEngine.startTimeUpdates()
- ~~`stopTimeUpdates()`~~ → TimingEngine.stopTimeUpdates()

Leave only:
- Public methods: `play()`, `pause()`, `seek()`, `loadTrack()`, `setVolume()`, `setEnhanced()`, `on()`, `off()`, `emit()`
- Helper methods: Internal orchestration only
- State management: Current track, metadata, configuration

---

### Step 9: Keep Public API Unchanged (10 min)

Ensure backward compatibility:

```typescript
// Public API UNCHANGED
public async play(): Promise<void> { ... }
public pause(): void { ... }
public async seek(time: number): Promise<void> { ... }
public async loadTrack(trackId: number): Promise<void> { ... }
public setVolume(volume: number): void { ... }
public async setEnhanced(enabled: boolean, preset?: string): Promise<void> { ... }
public on(event: string, callback: EventCallback): void { ... }
public off(event: string, callback: EventCallback): void { ... }
public emit(event: string, data?: any): void { ... }

// New getter APIs for diagnostics
public getState(): PlaybackState { ... }
public getCurrentTime(): number { ... }
public getMetadata(): StreamMetadata | null { ... }
```

---

## Expected File Size Reduction

```
Before:
├── UnifiedWebMAudioPlayer.ts: 1098 lines
└── Total: 1098 lines in single file

After:
├── UnifiedWebMAudioPlayer.ts: 220 lines (facade)
├── services/player/
│   ├── types.ts: 67 lines
│   ├── TimingEngine.ts: 150 lines
│   ├── MultiTierWebMBuffer.ts: 70 lines
│   ├── ChunkLoadPriorityQueue.ts: 130 lines
│   ├── ChunkPreloadManager.ts: 280 lines
│   ├── AudioContextController.ts: 290 lines
│   └── PlaybackController.ts: 280 lines
└── Total: 1487 lines (but split into focused modules!)

Each module: < 300 lines
Each module: Single responsibility
Each module: Independently testable
```

---

## Testing the Facade

### Unit Tests (per service)
- Already testable in isolation

### Integration Tests
```typescript
describe('UnifiedWebMAudioPlayer (as Facade)', () => {
  it('maintains public API', async () => {
    // Test play/pause/seek work end-to-end
    // Verify events are emitted
    // Check timing is accurate
  });

  it('routes service events correctly', async () => {
    // Verify chunk loading triggers playback
    // Verify seeking interrupts background loads
    // Verify timing updates flow through facade
  });
});
```

### Manual Testing
1. Load a track
2. Play / Pause / Seek
3. Watch progress bar
4. Toggle enhancement mode
5. Check console for debug logging

---

## Rollback Plan

If facade refactoring breaks something:

1. **Revert file**: `git checkout UnifiedWebMAudioPlayer.ts`
2. **Keep services**: They're stable and useful independently
3. **Try again**: Services can be integrated gradually instead of all at once

---

## Time Estimate

| Step | Time |
|------|------|
| 1. Add service instances | 15 min |
| 2. Simplify loadTrack() | 15 min |
| 3. Simplify play() | 10 min |
| 4. Simplify pause() | 5 min |
| 5. Simplify seek() | 15 min |
| 6. Wire service events | 20 min |
| 7. Helper methods | 15 min |
| 8. Remove old methods | 30 min |
| 9. Keep public API | 10 min |
| **Total** | **2 hours** |

---

## Success Criteria

After facade refactoring:

- ✅ TypeScript compiles without errors
- ✅ No breaking changes to public API
- ✅ `npm run dev` works without changes
- ✅ All UI components still work
- ✅ Progress bar accurate and responsive
- ✅ Playback sounds correct
- ✅ Seeking works
- ✅ Enhancement switching works
- ✅ No console errors
- ✅ Each service < 300 lines
- ✅ Unified module is orchestrator only

---

## Key Implementation Tips

### 1. Order of Execution
Execute in this order to minimize breaking changes:
1. Create service instances ✓
2. Wire events ✓
3. Delegate methods ✓
4. Delete old code

### 2. Debugging
- Add console logs at each facade → service call
- Verify events flow through
- Check timing calculations

### 3. Gradual Migration
Can refactor one public method at a time:
1. `play()` → test
2. `pause()` → test
3. `seek()` → test
4. Continue...

### 4. Keep Configuration
Central `config` object should remain, but pass to services:
```typescript
// Services receive only what they need
this.chunkPreloader = new ChunkPreloadManager(
  this.buffer,
  this.loadQueue,
  {
    apiBaseUrl: config.apiBaseUrl,
    trackId,
    enhanced: config.enhanced,
    preset: config.preset,
    intensity: config.intensity,
    preloadChunks: config.preloadChunks
  }
);
```

---

## After Phase 3.6

Once facade refactoring is complete:

1. **Commit services** - All 7 service files
2. **Commit facade** - Simplified UnifiedWebMAudioPlayer
3. **Update documentation** - Document service architecture
4. **Phase 3.7** - Integration testing and verification

The monolithic player is now modular, testable, and maintainable!

---

Generated for Phase 3.6 of the refactoring initiative.
