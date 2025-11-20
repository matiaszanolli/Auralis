# Player Architecture Refactoring Plan

## Problem Statement

**Current Issue**: The player components and services have become monolithic and difficult to debug. The timing mismatch issue (progress bar displaying stale values) was extremely hard to trace through the current architecture.

**Monoliths Identified**:
1. **PlayerBarV2Connected.tsx** (191 lines) - Combines UI wiring, state management, and effect handling
2. **ProgressBar.tsx** (232 lines) - Combines time display, seeking, and crossfade visualization
3. **UnifiedWebMAudioPlayer.ts** (1098 lines) - Combines chunk management, audio context control, state synchronization, and timing
4. **useUnifiedWebMAudioPlayer.ts** - Hook bridging service state to React (requires analysis)

## Root Causes of Debugging Difficulty

1. **Mixed Concerns**: PlayerBarV2Connected handles track loading, enhancement syncing, error handling, AND volume management
2. **State Flow Ambiguity**: Timing data flows: Service → Hook → Component → UI, with staleness accumulating at each layer
3. **Interconnected State**: Changes in one area (like update interval) require tracing through all 4 layers
4. **Testing Difficulty**: Hard to test individual concerns in isolation
5. **Feature Parallelism**: Chunk loading and timing updates happen in parallel with unclear synchronization

## Refactoring Strategy

### Phase 1: PlayerBarV2Connected Decomposition
Break the single "Connected" component into focused concerns:

**Current Structure**:
```
PlayerBarV2Connected
├── Track Loading (useEffect)
├── Error Handling (useEffect)
├── Enhancement Sync (useEffect)
├── Play/Pause Callbacks
├── Volume Callbacks
├── Seek Callbacks
├── Navigation Callbacks
└── Pass to PlayerBarV2
```

**Target Structure**:
```
PlayerBarV2Connected (orchestrator only)
├── usePlayerTrackLoader (loading + error handling)
├── usePlayerEnhancementSync (enhancement settings sync)
├── usePlayerCallbacks (all event handlers)
├── <PlayerBarV2> (pure UI component)
```

**Benefits**:
- Each concern isolated in its own hook (easier to test)
- Clear dependency boundaries
- Single useEffect per concern
- Easier to add/modify features without touching other parts

### Phase 2: ProgressBar Decomposition
Break ProgressBar into smaller, focused sub-components:

**Current Structure**:
```
ProgressBar (232 lines)
├── TimeDisplay (left side)
├── Slider Container
│   ├── Crossfade Indicators
│   │   └── CrossfadeRegion (repeated)
│   └── StyledSlider
├── TimeDisplay (right side, duration)
└── Seek Logic
```

**Target Structure**:
```
ProgressBar (orchestrator, 60 lines)
├── <CurrentTimeDisplay> (30 lines)
├── <SeekSlider> (80 lines)
│   ├── <CrossfadeVisualization> (50 lines)
│   └── Slider + drag handlers
├── <DurationDisplay> (30 lines)
```

**Benefits**:
- Each sub-component <80 lines, focused purpose
- Crossfade visualization can be tested separately
- Seeking logic isolated from display logic
- Easier to modify styling per component

### Phase 3: UnifiedWebMAudioPlayer Decomposition
Break the 1098-line service into multiple focused services:

**Current Responsibilities**:
1. Chunk Management (loading, priority queue, decoding)
2. Audio Context Control (source creation, scheduling)
3. Timing & State (getCurrentTime, timeupdate events)
4. Playback Control (play, pause, seek)
5. Event Management (emit/on pattern)

**Target Structure**:
```
UnifiedWebMAudioPlayer (facade, ~200 lines)
├── ChunkPreloadManager (300 lines)
│   ├── Priority queue management
│   ├── Parallel chunk loading
│   └── Decoder state tracking
├── AudioContextController (250 lines)
│   ├── Source creation and scheduling
│   ├── Gain/volume control
│   └── Context state machine
├── TimingEngine (150 lines)
│   ├── Linear timing calculation
│   ├── TimeUpdate emission (50ms interval)
│   └── Debug info collection
└── PlaybackController (150 lines)
    ├── Play/pause logic
    ├── Seeking with chunk boundary handling
    └── State machine transitions
```

**Benefits**:
- Chunk loading can be debugged independently
- Timing issues isolated to TimingEngine
- Playback state clearly defined
- Each service <350 lines, single responsibility
- Easier to profile each service separately

### Phase 4: useUnifiedWebMAudioPlayer Hook Decomposition
Break hook into focused sub-hooks:

**Current Responsibilities**:
1. Service initialization
2. State subscription (timeupdate events)
3. Error state management
4. Loading state management
5. Lifecycle management (cleanup)

**Target Structure**:
```
useUnifiedWebMAudioPlayer (orchestrator hook, 40 lines)
├── usePlayerServiceInit (30 lines) - Create service instance
├── usePlayerStateSync (50 lines) - Subscribe to timeupdate
├── usePlayerErrorHandling (30 lines) - Error subscription
├── usePlayerLoadingState (20 lines) - Loading tracking
└── usePlayerCleanup (20 lines) - Lifecycle cleanup
```

**Benefits**:
- Each hook has single responsibility
- State subscriptions clearly visible
- Error handling isolated
- Easier to test each hook independently

## Implementation Order

1. **Phase 1**: PlayerBarV2Connected hooks (non-breaking, additive)
2. **Phase 2**: ProgressBar sub-components (isolated, no external impact)
3. **Phase 3**: UnifiedWebMAudioPlayer services (requires careful refactoring)
4. **Phase 4**: useUnifiedWebMAudioPlayer hooks (depends on Phase 3)
5. **Validation**: Run full test suite, verify timing fix works

## Benefits of This Refactoring

### Debugging Improvements
- **Before**: Timing issue required tracing through 4 files across 1100+ lines
- **After**: Timing issue isolated to TimingEngine (150 lines)
- **Benefit**: 7x reduction in code to examine per concern

### Testability
- **Before**: Hard to test chunk loading without full player setup
- **After**: Can test ChunkPreloadManager in isolation
- **Benefit**: More focused unit tests, fewer integration test dependencies

### Maintainability
- **Before**: Changing chunk priority logic requires understanding entire UnifiedWebMAudioPlayer
- **After**: Isolated to ChunkPreloadManager
- **Benefit**: Safer refactoring, easier onboarding for new developers

### Performance
- **Before**: Hard to profile which part consumes resources (chunk loading? timing? audio context?)
- **After**: Can profile each service independently
- **Benefit**: Easier to identify and fix performance bottlenecks

### Feature Development
- **Before**: Adding new timing feature requires modifying monolithic UnifiedWebMAudioPlayer
- **After**: Add to TimingEngine only
- **Benefit**: Safer feature additions, fewer side effects

## Key Architectural Principles

### Facade Pattern
- UnifiedWebMAudioPlayer remains the public API
- Internal services are private implementation details
- External code continues to work without changes
- Internal refactoring is invisible to consumers

### Separation of Concerns
- Each service has single, well-defined responsibility
- No cross-service state mutation (message passing only)
- Clear dependency hierarchy (no circular dependencies)

### Event-Driven Communication
- Services communicate via events (existing `emit/on` pattern)
- No direct method calls between services
- Makes services loosely coupled
- Easier to add logging/debugging at boundaries

## Testing Strategy

### Unit Tests (New)
```typescript
// Before: Hard to test chunk loading without full player
// After: Can test in isolation
describe('ChunkPreloadManager', () => {
  it('preloads next chunk with IMMEDIATE priority', () => {
    const manager = new ChunkPreloadManager()
    manager.queueChunk(1, 'IMMEDIATE')
    expect(manager.queue[0].priority).toBe('IMMEDIATE')
  })
})
```

### Integration Tests (Existing)
```typescript
// PlayerBarV2Connected still tests full integration
describe('PlayerBarV2Connected', () => {
  it('loads and plays track end-to-end', async () => {
    // Full test with all refactored components
  })
})
```

### Performance Tests (Improved)
```typescript
// Before: Can't isolate which part is slow
// After: Can benchmark each service
- ChunkPreloadManager: parallel load time
- TimingEngine: emission overhead
- AudioContextController: context update time
```

## Success Criteria

1. ✅ All existing tests pass without modification
2. ✅ Each file/class < 350 lines
3. ✅ Each method has single responsibility
4. ✅ No increase in overall lines of code (refactoring, not feature addition)
5. ✅ Timing fix (50ms interval) verified working
6. ✅ Chunk preloading continues working correctly
7. ✅ Zero new dependencies introduced
8. ✅ Public API (UnifiedWebMAudioPlayer) unchanged

## Timeline Estimate

- **Phase 1** (PlayerBarV2Connected hooks): 45 minutes
  - Extract usePlayerTrackLoader: 15 min
  - Extract usePlayerEnhancementSync: 15 min
  - Extract usePlayerCallbacks: 15 min

- **Phase 2** (ProgressBar sub-components): 30 minutes
  - Extract CurrentTimeDisplay: 10 min
  - Extract SeekSlider: 10 min
  - Extract DurationDisplay: 5 min
  - Extract CrossfadeVisualization: 5 min

- **Phase 3** (UnifiedWebMAudioPlayer services): 2-3 hours
  - ChunkPreloadManager: 45 min
  - AudioContextController: 45 min
  - TimingEngine: 30 min
  - PlaybackController: 30 min
  - Integration testing: 30 min

- **Phase 4** (useUnifiedWebMAudioPlayer hooks): 45 minutes
  - Sub-hooks extraction: 30 min
  - Testing: 15 min

- **Validation**: 30 minutes
  - Full test run: 15 min
  - Manual testing: 15 min

**Total**: ~4-5 hours for complete refactoring

## Rollback Plan

Each phase is independent and can be rolled back:
1. Phase 1: Hooks remain private, can be inlined if needed
2. Phase 2: Sub-components can be inlined back into ProgressBar
3. Phase 3: Services can be merged back into UnifiedWebMAudioPlayer
4. Phase 4: Hooks can be re-combined

No breaking changes to public API at any step.

## Next Steps

1. User approves or modifies this plan
2. Begin Phase 1: PlayerBarV2Connected hooks decomposition
3. Verify no test failures after each phase
4. Once refactoring complete: Verify timing fix works in new architecture
