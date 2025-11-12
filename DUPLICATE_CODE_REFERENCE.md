# Duplicate Code Reference - Specific File Locations

## Pattern 1: Keyboard Shortcuts Hooks

### Files
- **V1 (DEPRECATED):** `/mnt/data/src/matchering/auralis-web/frontend/src/hooks/useKeyboardShortcuts.ts` (307 lines)
  - Lines 74-82: `isInputElement()` function
  - Lines 87-117: `formatShortcut()` function
  - Lines 127-266: Massive if/else chain for keyboard handling

- **V2 (RECOMMENDED):** `/mnt/data/src/matchering/auralis-web/frontend/src/hooks/useKeyboardShortcutsV2.ts` (79 lines)
  - Uses service pattern (better testability)
  - Smaller, cleaner implementation
  - Lines 76: `formatShortcut()` delegation to service

### Action Items
- [ ] Mark V1 as deprecated
- [ ] Migrate all consumers to V2
- [ ] Remove V1 after 1-2 releases
- [ ] Update tests to use V2 only

---

## Pattern 2: Format Time Function

### Files with Duplicate Implementation
1. `/mnt/data/src/matchering/auralis-web/frontend/src/components/player/ProgressBar.tsx` (lines 33-37)
   ```typescript
   function formatTime(seconds: number): string {
     const mins = Math.floor(seconds / 60);
     const secs = Math.floor(seconds % 60);
     return `${mins}:${secs.toString().padStart(2, '0')}`;
   }
   ```

2. `/mnt/data/src/matchering/auralis-web/frontend/src/components/player-bar-v2/ProgressBar.tsx` (lines 118-124)
   ```typescript
   function formatTime(seconds: number): string {
     if (!isFinite(seconds) || seconds < 0) return '0:00';
     const mins = Math.floor(seconds / 60);
     const secs = Math.floor(seconds % 60);
     return `${mins}:${secs.toString().padStart(2, '0')}`;
   }
   ```

3. `/mnt/data/src/matchering/auralis-web/frontend/src/components/library/TrackRow.tsx` (lines 237-241)
   ```typescript
   const formatDuration = (seconds: number): string => {
     const mins = Math.floor(seconds / 60);
     const secs = Math.floor(seconds % 60);
     return `${mins}:${secs.toString().padStart(2, '0')}`;
   };
   ```

### Action Items
- [ ] Create `/src/utils/timeFormat.ts` with:
  - `formatTime(seconds): string`
  - `formatDuration(seconds): string` (alias)
- [ ] Replace all 4+ implementations with import from utility
- [ ] Add unit tests for edge cases (negative, Infinity, zero)

---

## Pattern 3: API Error Handling

### Services with Repeated Pattern
- `/src/services/playlistService.ts` - 19+ occurrences
- `/src/services/queueService.ts` - 8+ occurrences
- `/src/services/settingsService.ts` - 5+ occurrences
- `/src/services/artworkService.ts` - 3 occurrences
- `/src/services/similarityService.ts` - 6+ occurrences
- `/src/services/processingService.ts` - 8+ occurrences

### Example Pattern (repeated 102+ times)
```typescript
const response = await fetch(`${API_BASE}/endpoint`, { method: 'POST' });
if (!response.ok) {
  const error = await response.json();
  throw new Error(error.detail || 'Failed to do something');
}
return response.json();
```

### Action Items
- [ ] Create `/src/services/apiClient.ts` with:
  ```typescript
  async function apiRequest<T>(
    endpoint: string,
    options?: RequestInit,
    context?: string
  ): Promise<T>
  ```
- [ ] Replace all 102+ occurrences with single function call
- [ ] Add centralized error logging/metrics
- [ ] Add retry logic (optional)

---

## Pattern 4: API Base Configuration

### Inconsistent Patterns
| Service | Pattern | Value |
|---------|---------|-------|
| artworkService.ts | Hardcoded | `'http://localhost:8765'` |
| settingsService.ts | Relative | `'/api'` |
| playlistService.ts | Relative | `'/api'` |
| queueService.ts | Relative | `'/api'` |
| similarityService.ts | Relative + suffix | `'/api/similarity'` |
| processingService.ts | Env var | `process.env.REACT_APP_API_URL` |
| mseStreamingService.ts | Constructor | Variable |

### Action Items
- [ ] Update `/src/config/api.ts` to export:
  ```typescript
  export const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8765';
  export const getApiUrl = (path: string) => `${API_BASE}${path}`;
  ```
- [ ] Update all services to use centralized config
- [ ] Fix artworkService.ts hardcoded localhost:8765

---

## Pattern 5: TrackInfo Component Variants

### Files
1. `/src/components/player/TrackInfo.tsx` (221 lines)
   - Uses AlbumArtComponent wrapper (lines 120-124)
   - Hardcoded colors: `#ffffff`, `#8b92b0`, `#e91e63`
   - Has lyrics button option (line 198-215)

2. `/src/components/player-bar-v2/TrackInfo.tsx` (183 lines)
   - Inline artwork display (lines 147-159)
   - Uses design tokens (line 14: `from '@/design-system/tokens'`)
   - No lyrics button

### Duplicate Sections
- Album artwork container styling (lines 19-26 player/ vs 36-58 player-bar-v2/)
- Track title styling (lines 138-148 player/ vs 96-105 player-bar-v2/)
- Track artist styling (lines 153-166 player/ vs 107-119 player-bar-v2/)
- Favorite button (lines 177-195 player/ vs 77-94 player-bar-v2/)
- No track fallback (lines 69-106 player/ vs 130-143 player-bar-v2/)

### Action Items
- [ ] Create `/src/components/shared/TrackInfoBase.tsx` with:
  - `TrackInfoDisplay` component (common layout)
  - Props for artwork source, show lyrics button, etc.
- [ ] Update both files to extend base component
- [ ] Consolidate to single design-system style

---

## Pattern 6: ProgressBar Component Variants

### Files
1. `/src/components/player/ProgressBar.tsx` (136 lines)
   - Simple slider + time display
   - Hardcoded colors: `#8b92b0`, `#5a5f7a`
   - Basic Time formatting

2. `/src/components/player-bar-v2/ProgressBar.tsx` (242 lines)
   - Includes crossfade visualization (lines 202-219)
   - Uses design tokens
   - Advanced time handling with preview

### Duplicate Code
- formatTime function (lines 33-37 vs 118-124)
- Slider styling (lines 71-91 vs 222-231)
- Time display (lines 94-131 vs 198-237)
- Container structure

### Action Items
- [ ] Extract `formatTime()` to `/src/utils/timeFormat.ts`
- [ ] Create slider styling in design-system
- [ ] Create parametrized ProgressBar that supports both modes
  - Base: `/src/components/shared/ProgressBar.tsx` (base)
  - V2 with crossfade: Optional feature flag

---

## Pattern 7: EnhancementToggle Component Variants

### Files
1. `/src/components/player-bar-v2/EnhancementToggle.tsx` (94 lines)
   - Icon button style (AutoAwesomeIcon)
   - Label below icon: "Enhanced" / "Original"
   - Compact style (40px button)

2. `/src/components/enhancement-pane-v2/EnhancementToggle.tsx` (94 lines)
   - Switch control style (FormControlLabel)
   - Description text below
   - Larger form control style

### Issues
- Two completely different UX patterns for same feature
- Users see inconsistent UI in different screens

### Action Items
- [ ] Decide: Which style is "official"?
- [ ] Create parametrized component supporting both modes
- [ ] Remove duplicate implementation
- [ ] Update documentation

---

## Pattern 8: EmptyState Component Variants

### Files
1. `/src/components/shared/EmptyState.tsx` (162 lines)
   - General-purpose empty state
   - Icon map, title, description, action button
   - Pre-built variants: EmptyLibrary, NoSearchResults, EmptyPlaylist, EmptyQueue

2. `/src/components/enhancement-pane-v2/EmptyState.tsx` (49 lines)
   - Minimal, enhancement-specific
   - No action button support
   - Single use case

### Action Items
- [ ] DELETE `/src/components/enhancement-pane-v2/EmptyState.tsx`
- [ ] Update enhancement-pane-v2 to import shared EmptyState
- [ ] No new code needed - just refactor import

---

## Pattern 9: TrackRow Wrapper Components

### Files
1. **Base:** `/src/components/library/TrackRow.tsx` (389 lines)
   - Complete track row implementation
   - Album art, title, artist, duration
   - Context menu handling
   - Play button, more menu

2. **Wrapper 1:** `/src/components/library/SelectableTrackRow.tsx` (149 lines)
   - Adds checkbox selection (lines 51-144)
   - Wraps TrackRow (line 132-142)
   - Props forwarding inconsistency

3. **Wrapper 2:** `/src/components/library/DraggableTrackRow.tsx` (120 lines)
   - Adds drag handle (lines 15-33)
   - Wraps TrackRow (lines 99-113)
   - Uses @hello-pangea/dnd

### Architecture Issue
- SelectableTrackRow already uses composition (line 132: `<TrackRow ... />`)
- DraggableTrackRow already uses composition (line 99: `<TrackRow ... />`)
- But both have inefficient wrapper logic and prop forwarding

### Props Interface Mismatch
- TrackRow: `onPlay`, `onPause`, `onDoubleClick`, etc.
- SelectableTrackRow: Missing some props, adds `onAddToQueue`, `onAddToPlaylist`
- DraggableTrackRow: Same as TrackRow but adds `draggableId`, `isDragDisabled`

### Action Items
- [ ] Create unified `TrackRowProps` interface
- [ ] Simplify SelectableTrackRow wrapper (just add checkbox)
- [ ] Simplify DraggableTrackRow wrapper (just add drag handle)
- [ ] Ensure all props are properly forwarded
- [ ] Reduce total lines from 658 to ~450

---

## Pattern 10: Styled Component Patterns

### Generic Container (appears 40+ times)
Locations where this pattern repeats:
- `/src/components/shared/EmptyState.tsx` (lines 16-24)
- `/src/components/enhancement-pane-v2/EmptyState.tsx` (lines 16-24)
- `/src/components/player-bar-v2/ProgressBar.tsx` (lines 24-29)
- `/src/components/shared/LoadingSpinner.tsx` (lines 91-99)
- Many more...

Pattern:
```typescript
const Container = styled(Box)({
  display: 'flex',
  flexDirection: 'column', // or 'row'
  alignItems: 'center',
  justifyContent: 'center',
  gap: tokens.spacing.md,
  padding: tokens.spacing.lg,
});
```

### Text Truncation (appears 25+ times)
Pattern:
```typescript
const TruncatedText = styled(Typography)({
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
});
```

### Icon Container (appears 30+ times)
Pattern:
```typescript
const IconContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '24px',
});
```

### Action Items
- [ ] Create `/src/design-system/compounds/` directory
- [ ] Add reusable styled components:
  - `CenteredContainer`, `CenteredFlex`, `CenteredColumn`
  - `TruncatedText`, `EllipsisTypography`
  - `IconBox`, `IconContainer`
  - `HoverScale`, `HoverBrightness` utilities
- [ ] Replace 100+ instances with imports
- [ ] Reduce total styled() definitions from 192 to ~60

---

## Implementation Checklist

- [ ] Create `/src/utils/timeFormat.ts`
- [ ] Create `/src/services/apiClient.ts`
- [ ] Update `/src/config/api.ts`
- [ ] Create `/src/components/shared/TrackInfoBase.tsx`
- [ ] Refactor TrackInfo variants to use base
- [ ] Refactor ProgressBar variants
- [ ] Consolidate EnhancementToggle
- [ ] Remove enhancement-pane-v2/EmptyState.tsx
- [ ] Simplify TrackRow wrapper components
- [ ] Create design-system compound components
- [ ] Update all imports in consuming components
- [ ] Run full test suite
- [ ] Update storybook examples (if using)
- [ ] Create migration guide for team
- [ ] Update code review guidelines

---

## Success Criteria

- [ ] All tests pass
- [ ] Bundle size reduced (target: 5-10% reduction)
- [ ] No breaking changes to component APIs
- [ ] Zero duplicate formatTime implementations
- [ ] Zero duplicate API error handling patterns
- [ ] All services use centralized API config
- [ ] Component prop interfaces unified
- [ ] Wrapper components simplified

