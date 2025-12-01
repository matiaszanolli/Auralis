# Phase 7 Architectural Fix - Stability Recovery

## Critical Issue Identified

**The Problem:**
Phase 7 hooks (useQueueSearch, useQueueStatistics, useQueueRecommendations) are designed for the **playback queue** (~100-500 tracks), not the **entire library** (54,756 tracks). When the application tries to apply these hooks to the full library, they cause:

1. **Memory explosion** - Each hook maintains arrays, filters, and recommendations for ALL tracks
2. **CPU overload** - Search, statistics, and similarity calculations run on massive datasets
3. **Browser crashes** - DOM rendering + memory usage exceeds available resources

**The Design Flaw:**
```
❌ BROKEN: Library View → Phase 7 Hooks → 54,756 Tracks
   (App loads 50 tracks in TrackList, but hooks initialize for ALL 54,756)

✅ CORRECT: Player Queue → Phase 7 Hooks → 100-500 Tracks
   (Only tracks in current queue get Phase 7 features)
```

## Architecture Clarification

### Phase 7 is Queue-Only, Not Library-Wide

**Phase 7 Hooks Scope:**
- ✅ `useQueueSearch` - Search WITHIN current playback queue
- ✅ `useQueueStatistics` - Analyze current playback queue
- ✅ `useQueueRecommendations` - Get recommendations based on queue
- ✅ `useQueueShuffler` - Shuffle current playback queue
- ❌ NOT for browsing library (54K+ tracks)
- ❌ NOT for search suggestions during browsing

**Library View Scope:**
- ✅ Infinite scroll pagination (50 tracks per page)
- ✅ Search input for filtering (API-side search)
- ✅ Browse albums/artists (paginated)
- ❌ Should NOT run Phase 7 hooks on full library

### Data Flow Separation

```
User Interface
├── Library View (Infinite Scroll)
│   ├── TrackList (50 tracks at a time)
│   ├── AlbumGrid (paginated)
│   └── ArtistList (paginated)
│   └→ useLibraryQuery hook → API with limit/offset
│
├── Enhancement Panel
│   └→ Enhanced audio processing
│
└── Player Control
    ├── Queue (100-500 tracks)
    ├── Phase 7 Hooks ← ONLY HERE
    │   ├── useQueueSearch (search within queue)
    │   ├── useQueueStatistics (analyze queue)
    │   ├── useQueueRecommendations (queue-based)
    │   └── useQueueShuffler (shuffle queue)
    └─→ ShuffleModeSelector
    └─→ QueueSearchPanel
    └─→ QueueStatisticsPanel
    └─→ QueueRecommendationsPanel
```

## Current Component Issues

### ❌ Problems in Current Code

1. **TrackListView.tsx** - May be running Phase 7 hooks on paginated tracks
2. **LibraryView.tsx** - Not clearly separating library view from queue control
3. **App initialization** - Hooks might be running for all 54K tracks on mount

### ✅ What Should Work

1. **Library browsing** - Fast, paginated (50/page), infinite scroll, NO Phase 7
2. **Player controls** - Phase 7 features on current queue ONLY
3. **Search** - Library search (API-side), Queue search (Phase 7 hook)

## Implementation Guidelines

### Rule 1: Queue vs Library

```typescript
// ❌ WRONG: Running Phase 7 on entire library
export const TrackListView = ({ tracks: ALL_LIBRARY_TRACKS }) => {
  const { filteredTracks } = useQueueSearch(ALL_LIBRARY_TRACKS);
  // ↑ This kills performance with 54K tracks
};

// ✅ RIGHT: Phase 7 only on playback queue
export const PlayerQueue = ({ queue: CURRENT_QUEUE }) => {
  const { filteredTracks } = useQueueSearch(CURRENT_QUEUE);
  // ↑ Safe with 100-500 tracks
};
```

### Rule 2: Memory Budgets

```typescript
// Maximum safe dataset sizes for Phase 7 hooks:
// - Individual hook: < 50MB memory
// - All hooks together: < 150MB memory
// - Recommended queue size: 100-500 tracks (safe)
// - Maximum queue size: < 1000 tracks (risky at high system load)
// - Never: Apply to entire library (54K+ tracks)

const queue = [/* 100-500 tracks */];  // ✅ Safe
const allTracks = [/* 54,756 tracks */];  // ❌ Never
```

### Rule 3: Hook Initialization

```typescript
// ✅ Safe: Initialize hooks with queue only
const MyPlayerUI = () => {
  const { queue } = usePlayer();

  // Only initialize Phase 7 hooks when player is active
  if (!queue || queue.length === 0) {
    return <EmptyState />;
  }

  const search = useQueueSearch(queue);  // Safe: < 500 tracks
  const stats = useQueueStatistics(queue);  // Safe
  const recs = useQueueRecommendations(queue);  // Safe

  return <QueueControls {...{ search, stats, recs }} />;
};
```

## Safety Checklist

Before deploying Phase 7 features:

- [ ] Hook only receives playback queue, NOT library
- [ ] Queue size is 100-500 tracks (small enough to be safe)
- [ ] All Phase 7 hooks are in `<Player>` component, not `<Library>`
- [ ] Library components use pagination (limit=50)
- [ ] Search in library uses API-side search, not Phase 7 hooks
- [ ] Memory profiling shows < 200MB for idle, < 500MB max
- [ ] Component tests verify performance with 500-track queue
- [ ] Integration tests confirm no phase 7 on 54K track load

## File Changes Needed

### 1. Document Hook Constraints

**File:** `src/hooks/player/useQueueSearch.ts`
- Add comments: "Queue must be 100-500 tracks max"
- Add JSDoc warning about library data
- Add runtime check: throw if queue.length > 1000

### 2. Separate Library from Player

**File:** `src/components/library/TrackListView.tsx`
- Remove ANY Phase 7 hook usage
- Use only pagination via `useLibraryQuery`
- Keep it simple: display paginated results

**File:** `src/components/player/PlayerQueue.tsx` (if exists)
- Place ALL Phase 7 hooks here
- Receive queue from Redux/Player context
- Export Phase 7 UI components

### 3. Add Guard Rails

**File:** `src/hooks/player/useQueueSearch.ts` (and other Phase 7 hooks)
```typescript
export function useQueueSearch(queue: Track[]) {
  // Guard: Warn if queue too large
  if (queue.length > 1000) {
    console.warn(
      `useQueueSearch: Queue size (${queue.length}) exceeds recommended maximum (500). ` +
      `This hook is designed for playback queues only, not entire libraries. ` +
      `Performance may degrade significantly.`
    );
  }

  // ... rest of implementation
}
```

## Recommended Timeline

1. **Immediate (Critical):** Add documentation and warnings
2. **This Week:** Verify no Phase 7 hooks in library views
3. **Next:** Add runtime guards to hooks
4. **Later:** Refactor UI to properly separate concerns

## Testing Phase 7 Safety

✅ **Safe Test Scenarios:**
```bash
# Phase 7 with small queue
npm run test:memory -- --grep "Phase 7.*50.*tracks"
npm run test:memory -- --grep "Phase 7.*500.*tracks"

# Library pagination works
npm run test:memory -- --grep "InfiniteScroll"
npm run test:memory -- --grep "Library.*pagination"
```

❌ **Dangerous Test Scenarios (NEVER RUN):**
```bash
npm run test:memory -- --grep "Phase 7.*54756"  # ❌ WILL CRASH
npm run test:memory -- src/hooks/player/__tests__/Phase7Integration.test.tsx  # Limited scope
```

## Summary

**Root Cause:** Phase 7 hooks applied to 54K track library instead of 100-500 track queue.

**Solution:** Strict architectural separation:
- Library view = pagination only (infinite scroll, no Phase 7)
- Player queue = Phase 7 features (search, stats, shuffle, recommendations)

**Safety Margin:** Phase 7 safe up to ~500 tracks, maximum ~1000, never library.

---

*Phase 7 Architectural Fix*
*Stability Recovery & Design Clarification*
*Priority: Critical for production readiness*
