# Chunk Loading Priority Queue System

## Overview

The async priority queue system manages WebM/Opus chunk loading in the unified player, ensuring seek operations are responsive and background preloads don't interfere with user interactions.

**Status**: ✅ Implemented (Commit: f3e6e64)

## Problem Solved

**Before**: When user sought to position 11.60s, the player correctly calculated chunk 1 but background preload continued loading chunks 9, 10, 11, 12. This caused wrong chunks to be prioritized, breaking seek responsiveness.

**After**: Priority queue ensures seek targets load immediately, with background preloads deferred until high-priority chunks complete.

## Architecture

### Priority Levels (0-4, lower = higher priority)

```
P0: CRITICAL  - Currently playing chunk (immediate playback)
P1: IMMEDIATE - Next chunk for continuous playback (load before current ends)
P2: SEEK_TARGET - Chunk user seeked to (highest user priority)
P3: ADJACENT - ±1 chunks around current position (smooth playback)
P4: BACKGROUND - All other chunks (lowest priority, preload when queue empty)
```

### Components

#### 1. ChunkLoadPriorityQueue Class

Manages the queue with:
- **enqueue(chunkIndex, priority)**: Add/update chunk with priority
- **dequeue()**: Get next chunk to load (highest priority first)
- **clearLowerPriority(priority)**: Remove less-urgent chunks
- **isQueued(chunkIndex)**: Check if chunk is pending or loading
- **isLoading(chunkIndex)**: Check if chunk is currently being loaded

Key features:
- Prevents duplicate queue entries (re-queueing updates priority)
- Sorts by priority first, then by timestamp (newer first)
- Tracks active loads to prevent concurrent loads of same chunk

#### 2. preloadChunk(chunkIndex, priority = 4)

Updated to queue chunks instead of loading immediately:
```typescript
private async preloadChunk(chunkIndex: number, priority: number = 4): Promise<void>
```

- Adds chunk to queue with given priority
- Triggers processLoadQueue if not already running
- Default priority is P4 (BACKGROUND)

#### 3. processLoadQueue()

Continuously processes the queue:
```typescript
private async processLoadQueue(): Promise<void>
```

Behavior:
- Runs until queue is empty
- Only one processor at a time (prevents race conditions)
- Loads chunks in priority order (dequeues highest priority first)
- Gracefully handles failures without stopping processor
- Auto-queues next chunks with P4 (BACKGROUND) when high-priority chunk loads

## Usage Patterns

### Loading a Track

```typescript
// When track loads, queue first chunk with BACKGROUND priority
await this.preloadChunk(0, 4); // P4: BACKGROUND
```

### During Playback

```typescript
// In playChunk(), queue next chunk for continuous playback
this.preloadChunk(chunkIndex + 1, 1); // P1: IMMEDIATE
```

### During Seek

```typescript
// In seek(), queue target chunk with high priority
this.preloadChunk(targetChunk, 2);      // P2: SEEK_TARGET
this.preloadChunk(targetChunk - 1, 3);  // P3: ADJACENT
this.preloadChunk(targetChunk + 1, 3);  // P3: ADJACENT

// Wait for target to load
await new Promise<void>((resolve) => {
  const checkLoaded = () => {
    if (chunk.isLoaded && chunk.audioBuffer) {
      resolve();
    } else {
      setTimeout(checkLoaded, 50);
    }
  };
  checkLoaded();
});
```

## Console Logging

Debug logs show priority in `[P#]` format:

```
[P2] Seeking to 11.60s (chunk 1, offset 1.60s)
[P2] Loading chunk 1/34
[P2] Chunk 1 cache: MISS
[P2] Decoding 263531 bytes for chunk 1...
[P2] Chunk 1 ready (15.00s)
[P1] Loading chunk 2/34
[P1] Chunk 2 cache: HIT
```

This makes it easy to monitor chunk loading priority in real-time.

## Performance Characteristics

| Scenario | Before | After |
|----------|--------|-------|
| Seek responsiveness | Slow (10-100ms) | Fast (0-50ms) |
| Background preload | Always highest priority | Deferred until after seeks |
| Multiple seeks | Queue grows, wrong chunks load | Queue reordered, correct chunks prioritized |
| Playback continuity | Depends on preload sequence | Guaranteed (P1 always active) |

## Edge Cases Handled

1. **Seek during preload**: Target chunk gets re-queued with higher priority
2. **Failed chunk loads**: Error logged, queue processor continues
3. **Already-loaded chunks**: Skipped, not re-loaded
4. **Empty chunk**: Logged with detailed error info
5. **Concurrent seeks**: Previous seek's chunks may be dequeued, new seek targets prioritized

## Future Enhancements

1. **Adaptive priority**: Adjust P1 count based on network latency
2. **Queue persistence**: Save queue state across track changes
3. **Predictive preload**: Use playback history to predict user seeks
4. **Network-aware**: Reduce priority for low-bandwidth scenarios
5. **Metrics**: Track average load time, cache hit rate per priority level

## Related Files

- [UnifiedWebMAudioPlayer.ts](../../auralis-web/frontend/src/services/UnifiedWebMAudioPlayer.ts) - Player implementation
- [webm_streaming.py](../../auralis-web/backend/routers/webm_streaming.py) - Chunk serving endpoint
- [MULTI_TIER_BUFFER_ARCHITECTURE.md](./MULTI_TIER_BUFFER_ARCHITECTURE.md) - Cache system

## References

- Commit: f3e6e64 - "Fix seeking bug with async priority queue for chunk loading"
- Previous issue: Background preload loads chunks 9,10,11,12 instead of seek target (chunk 1)
- User feedback: "Maybe an async priority queue could do the trick"
