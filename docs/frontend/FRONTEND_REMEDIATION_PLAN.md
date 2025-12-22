# Frontend Remediation Plan

**Date**: 2025-12-20
**Status**: Planning Complete
**Priority**: Critical - Blocking production readiness

---

## Executive Summary

A comprehensive audit of the Auralis frontend identified **47 issues** across three major areas:
- **Infinite Scroll**: 11 issues (4 critical, 3 high, 4 medium)
- **Streaming/Buffering**: 17 issues (5 critical, 4 high, 4 medium, 4 low)
- **Styling/CSS**: 14+ issues (2 critical, 5 high, 7 medium)

**Root causes**:
1. Hook API inconsistencies across components
2. Missing subscription cleanup and race conditions
3. Three competing design systems with conflicting values
4. Mixed styling approaches (inline, styled-components, CSS modules)

---

## Phase 1: Critical Infinite Scroll Fixes

**Estimated effort**: 4-6 hours
**Files affected**: 5

### Issue 1.1: Hook API Mismatch (CRITICAL)

**Problem**: `useInfiniteScroll` is called with different parameter names in different components:
- `CozyAlbumGrid.tsx`: passes `ref` (not accepted)
- `TrackListView.tsx`: passes `loadMoreRef`, `isLoadingMore` (not accepted)
- `CozyArtistList.tsx`: correct usage

**Files**:
- [useInfiniteScroll.ts](auralis-web/frontend/src/hooks/shared/useInfiniteScroll.ts)
- [TrackListView.tsx](auralis-web/frontend/src/components/library/Views/TrackListView.tsx)
- [CozyAlbumGrid.tsx](auralis-web/frontend/src/components/library/Items/albums/CozyAlbumGrid.tsx)

**Fix**:
```typescript
// Option A: Update hook to accept external ref
interface UseInfiniteScrollOptions {
  ref?: React.RefObject<HTMLDivElement>;  // NEW: Accept external ref
  threshold?: number;
  rootMargin?: string;
  onLoadMore: () => Promise<void>;
  hasMore: boolean;
  isLoading: boolean;
}

// Option B: Fix all callers to use correct API
// Prefer Option A for backwards compatibility
```

### Issue 1.2: Race Condition in fetchMore (CRITICAL)

**Problem**: `useLibraryQuery.fetchMore` lacks request deduplication, allowing parallel calls.

**File**: [useLibraryQuery.ts](auralis-web/frontend/src/hooks/library/useLibraryQuery.ts) (lines 264-290)

**Fix**:
```typescript
const fetchMore = useCallback(async (): Promise<void> => {
  // Add deduplication check
  if (!hasMore || isLoading || isFetchingRef.current) return;
  isFetchingRef.current = true;

  try {
    const nextOffset = offset + limit;
    // ... existing logic
  } finally {
    isFetchingRef.current = false;
  }
}, [...]);
```

### Issue 1.3: Observer Target Never Connected (HIGH)

**Problem**: `TrackListView.tsx` passes `loadMoreRef` but hook creates internal `observerTarget`.

**Fix**: Use the `observerTarget` returned from hook, not a separate ref.

### Issue 1.4: Unstable Callback Dependencies (MEDIUM)

**Problem**: `handleLoadMore` recreated on every render due to unstable `onLoadMore` prop.

**Fix**: Add memoization requirements in hook docs, or accept stable callback only.

---

## Phase 2: Critical Streaming/Buffering Fixes

**Estimated effort**: 6-8 hours
**Files affected**: 6

### Issue 2.1: Subscription Accumulation (CRITICAL)

**Problem**: `playEnhanced()` subscribes without unsubscribing first, causing handler accumulation.

**Files**:
- [usePlayEnhanced.ts](auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts) (lines 407-427)
- [usePlayNormal.ts](auralis-web/frontend/src/hooks/enhancement/usePlayNormal.ts) (lines 362-379)

**Fix**:
```typescript
const playEnhanced = useCallback(async (trackId: number, options) => {
  // Clean up existing subscriptions BEFORE creating new ones
  unsubscribeStreamStartRef.current?.();
  unsubscribeChunkRef.current?.();
  unsubscribeStreamEndRef.current?.();
  unsubscribeErrorRef.current?.();

  // Now subscribe fresh
  unsubscribeStreamStartRef.current = wsContext.subscribe(
    'audio_stream_start',
    handleStreamStart
  );
  // ... etc
}, [/* deps */]);
```

### Issue 2.2: Stream Start Race Condition (CRITICAL)

**Problem**: `audio_chunk` may arrive before `audio_stream_start`, causing data loss.

**File**: [usePlayEnhanced.ts](auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts) (lines 280-330)

**Fix**:
```typescript
// Add chunk queue for chunks arriving before initialization
const pendingChunksRef = useRef<AudioChunkMessage[]>([]);

const handleChunk = useCallback((message: AudioChunkMessage) => {
  if (!pcmBufferRef.current || !streamingMetadataRef.current) {
    // Queue chunk instead of dropping
    pendingChunksRef.current.push(message);
    console.log('[usePlayEnhanced] Queued chunk until stream initialized');
    return;
  }
  // Process chunk...
}, []);

const handleStreamStart = useCallback((message: AudioStreamStartMessage) => {
  // Initialize buffer...

  // Drain pending chunks
  while (pendingChunksRef.current.length > 0) {
    const queued = pendingChunksRef.current.shift()!;
    handleChunk(queued);
  }
}, [handleChunk]);
```

### Issue 2.3: Connection State Validation (HIGH)

**Problem**: `wsContext.send()` called without checking connection state.

**Fix**:
```typescript
if (!wsContext.isConnected) {
  dispatch(setStreamingError('WebSocket not connected'));
  return;
}
wsContext.send({...});
```

### Issue 2.4: AudioContext Resume Bug (HIGH)

**Problem**: `AudioPlaybackEngine.play()` returns early after resume without starting playback.

**File**: [AudioPlaybackEngine.ts](auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts) (lines 85-91)

**Fix**:
```typescript
async play(): Promise<void> {
  if (this.audioContext.state === 'suspended') {
    try {
      await this.audioContext.resume();
      // DON'T return - continue to start playback
    } catch (err) {
      console.error('Failed to resume AudioContext:', err);
      this.setState('error');
      return;
    }
  }
  // Continue to start playback...
}
```

### Issue 2.5: Disconnect Cleanup (HIGH)

**Problem**: No cleanup when WebSocket disconnects mid-stream.

**Fix**: Subscribe to WebSocket close event and reset state.

### Issue 2.6: Hardcoded localhost URL (LOW - but blocks production)

**Files**:
- [usePlayEnhanced.ts](auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts) (line 392)
- [usePlayNormal.ts](auralis-web/frontend/src/hooks/enhancement/usePlayNormal.ts) (line 349)

**Fix**:
```typescript
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8765';
const response = await fetch(`${API_BASE}/api/library/tracks`);
```

---

## Phase 3: Design System Consolidation

**Estimated effort**: 8-12 hours
**Files affected**: 50+

### Issue 3.1: Three Competing Design Systems (CRITICAL)

**Problem**: Three files define conflicting design values:
1. `/design-system/tokens.ts` - Modern, comprehensive (KEEP)
2. `/theme/designSystem.ts` - Older, conflicts (DEPRECATE)
3. `/styles/globalStyles.ts` - Legacy duplicate (DEPRECATE)

**Action Plan**:

#### Step 3.1.1: Audit all imports
```bash
grep -r "from.*designSystem" src/components --include="*.tsx"
grep -r "from.*globalStyles" src/components --include="*.tsx"
```

#### Step 3.1.2: Create migration shim
```typescript
// theme/designSystem.ts - Add deprecation
/** @deprecated Use @/design-system/tokens instead */
import { tokens } from '@/design-system';
export const designSystem = tokens; // Re-export tokens
```

#### Step 3.1.3: Update components one-by-one
Priority order:
1. Player components (most visible)
2. Library components (main content)
3. Enhancement components
4. Shared components

#### Step 3.1.4: Delete legacy files
After all components migrated, remove:
- `/theme/designSystem.ts`
- `/styles/globalStyles.ts`

### Issue 3.2: ShuffleModeSelector Wrong Theme (CRITICAL)

**File**: [ShuffleModeSelector.module.css](auralis-web/frontend/src/components/player/ShuffleModeSelector.module.css)

**Problem**: Uses light theme colors (`#f5f5f5`, `#333`, `#0066cc`) on dark theme app.

**Fix**: Replace CSS file with styled-components using tokens:
```typescript
// ShuffleModeSelector.styles.ts
import styled from 'styled-components';
import { tokens } from '@/design-system';

export const SelectorContainer = styled.div`
  background: ${tokens.colors.bg.level1};
  color: ${tokens.colors.text.primary};
  // ... etc
`;
```

### Issue 3.3: Font Family Conflicts (HIGH)

**Current State**:
- `index.css`: Montserrat, Inter
- `tokens.ts`: Inter, Plus Jakarta Sans
- `designSystem.ts`: Montserrat, Fira Code

**Decision Required**: Choose ONE font stack. Recommendation:
```typescript
fontFamily: {
  primary: 'Inter, "Segoe UI", sans-serif',
  display: 'Plus Jakarta Sans, Arial, sans-serif',
  mono: 'JetBrains Mono, Consolas, monospace',
}
```

### Issue 3.4: Z-Index Unification (MEDIUM)

**Fix**: Delete z-index from `designSystem.ts`, use only `tokens.zIndex`.

### Issue 3.5: Spacing/Shadow/Radius Type Mismatches (MEDIUM)

**Problem**: `tokens.ts` uses strings ('8px'), `designSystem.ts` uses numbers (8).

**Fix**: Standardize on strings for CSS compatibility:
```typescript
spacing: {
  xs: '4px',  // Always strings
  sm: '8px',
  md: '16px',
  lg: '24px',
}
```

---

## Phase 4: Component Styling Cleanup

**Estimated effort**: 6-8 hours
**Files affected**: 30+

### Issue 4.1: Hardcoded Colors in Components (HIGH)

**Identified files with hardcoded values**:
1. `PlayerBar.tsx` - rgba(13, 17, 26, 0.92)
2. `ProgressBar.tsx` - rgba(0, 0, 0, 0.2)
3. `AppTopBar.styles.ts` - var(--midnight-blue)
4. Multiple components with box-shadow rgba values

**Fix**: Replace all with token references:
```typescript
// Before
backgroundColor: 'rgba(13, 17, 26, 0.92)'

// After
backgroundColor: tokens.colors.bg.level1,
backdropFilter: 'blur(12px)',
```

### Issue 4.2: Mixed Styling Approaches (HIGH)

**Current State**:
- Inline styles: VolumeControl, PlaybackControls, PlayerBar
- Styled-components: KeyboardShortcutsHelp, EnhancementPane
- CSS Modules: ShuffleModeSelector

**Target State**: Styled-components only (except index.css for globals)

**Migration Priority**:
1. VolumeControl.tsx → VolumeControl.styles.ts
2. PlaybackControls.tsx → PlaybackControls.styles.ts
3. PlayerBar.tsx → PlayerBar.styles.ts
4. Remove ShuffleModeSelector.module.css

### Issue 4.3: Invalid CSS Properties (MEDIUM)

**File**: [SearchBar.tsx](auralis-web/frontend/src/components/library/SearchBar.tsx) (line 235)

**Problem**: `paddingX` is not valid CSS
**Fix**: `paddingLeft: tokens.spacing.sm, paddingRight: tokens.spacing.sm`

### Issue 4.4: Missing Responsive Breakpoints (MEDIUM)

**Problem**: No unified breakpoint system defined in tokens.

**Fix**: Add to tokens.ts:
```typescript
breakpoints: {
  xs: '0px',
  sm: '600px',
  md: '900px',
  lg: '1200px',
  xl: '1536px',
}
```

### Issue 4.5: Inconsistent Focus/Hover States (MEDIUM)

**Problem**: Components define their own focus styles instead of using tokens.

**Fix**: Add to tokens.ts:
```typescript
focus: {
  ring: `0 0 0 2px ${colors.accent.primary}40`,
  outline: `2px solid ${colors.accent.primary}`,
}
```

---

## Implementation Order

### Week 1: Critical Fixes (Blocking Issues)

| Day | Task | Effort |
|-----|------|--------|
| 1 | Fix useInfiniteScroll hook API (Issue 1.1) | 2h |
| 1 | Fix subscription cleanup (Issue 2.1) | 2h |
| 2 | Fix stream start race condition (Issue 2.2) | 3h |
| 2 | Fix fetchMore deduplication (Issue 1.2) | 1h |
| 3 | Fix AudioContext resume (Issue 2.4) | 1h |
| 3 | Fix hardcoded localhost (Issue 2.6) | 0.5h |
| 3 | Fix connection validation (Issue 2.3) | 1h |
| 4 | Test all critical fixes end-to-end | 4h |

### Week 2: Design System Consolidation

| Day | Task | Effort |
|-----|------|--------|
| 1-2 | Audit all design system imports | 4h |
| 2-3 | Create migration shim for designSystem.ts | 2h |
| 3-4 | Migrate player components to tokens.ts | 6h |
| 4-5 | Migrate library components | 6h |
| 5 | Fix ShuffleModeSelector (Issue 3.2) | 2h |

### Week 3: Component Styling Cleanup

| Day | Task | Effort |
|-----|------|--------|
| 1-2 | Convert inline styles to styled-components | 8h |
| 3 | Fix invalid CSS properties | 2h |
| 4 | Add responsive breakpoints | 3h |
| 5 | Unify focus/hover states | 3h |
| 5 | Delete legacy design system files | 1h |

---

## Verification Checklist

### After Phase 1 (Infinite Scroll)
- [ ] All library views (Track, Album, Artist) scroll without flickering
- [ ] No duplicate items on scroll
- [ ] No infinite loop API calls
- [ ] useInfiniteScroll tests pass

### After Phase 2 (Streaming)
- [ ] Enhanced playback starts without delay
- [ ] No buffer overflow warnings in console
- [ ] Playback resumes after page reload
- [ ] WebSocket disconnect shows error UI
- [ ] Works in production (non-localhost)

### After Phase 3 (Design System)
- [ ] `designSystem.ts` and `globalStyles.ts` deleted
- [ ] All components import from `@/design-system`
- [ ] No TypeScript errors from token types
- [ ] Visual consistency across all views

### After Phase 4 (Component Styling)
- [ ] No inline styles in player components
- [ ] All colors come from tokens
- [ ] Responsive design works on mobile
- [ ] Focus states visible for accessibility

---

## Files Summary

### Must Modify (Critical)
1. `auralis-web/frontend/src/hooks/shared/useInfiniteScroll.ts`
2. `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts`
3. `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts`
4. `auralis-web/frontend/src/hooks/enhancement/usePlayNormal.ts`
5. `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts`

### Must Modify (High Priority)
6. `auralis-web/frontend/src/components/library/Views/TrackListView.tsx`
7. `auralis-web/frontend/src/components/library/Items/albums/CozyAlbumGrid.tsx`
8. `auralis-web/frontend/src/components/player/ShuffleModeSelector.module.css` → DELETE
9. `auralis-web/frontend/src/design-system/tokens.ts` (add breakpoints, focus)

### Must Delete (After Migration)
10. `auralis-web/frontend/src/theme/designSystem.ts`
11. `auralis-web/frontend/src/styles/globalStyles.ts`

### Should Refactor (Medium Priority)
- All player components with inline styles (5-8 files)
- All library components with hardcoded colors (10-15 files)

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Breaking existing functionality | Medium | High | Write tests before refactoring |
| Design token migration errors | Low | Medium | Use TypeScript for type safety |
| Performance regression | Low | Medium | Profile before/after changes |
| Merge conflicts during refactor | Medium | Low | Work in small, focused PRs |

---

## Success Metrics

1. **Infinite scroll**: 0 flickering reports, 0 duplicate items
2. **Streaming**: <2s playback start time, 0 buffer overflows
3. **Design consistency**: 100% token usage, 0 hardcoded colors
4. **Code quality**: All styling tests pass, no TypeScript errors
