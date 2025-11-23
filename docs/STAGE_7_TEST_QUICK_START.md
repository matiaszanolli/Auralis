# Stage 7 Test Suite - Quick Start Checklist

## Session 1: TrackRow Hooks (2-3 hours)

### Files to Create
- [ ] `src/components/library/Items/__tests__/useTrackRowHandlers.test.ts`
- [ ] `src/components/library/Items/__tests__/useTrackContextMenu.test.ts`
- [ ] `src/components/library/Items/__tests__/useTrackImage.test.ts`
- [ ] `src/components/library/Items/__tests__/useTrackFormatting.test.ts`

### Mocking Setup
```typescript
// No mocks needed for useTrackImage and useTrackFormatting
// For useTrackRowHandlers: mock click handlers (no external deps)
// For useTrackContextMenu:
vi.mock('../../../services/playlistService')
vi.mock('../../shared/ui/feedback') // useToast
```

### Test Focus
- Handler function behavior
- Event propagation
- Callback execution
- State updates
- Error handling

### Run Command
```bash
npm run test:memory -- Items/__tests__/use*.test.ts
```

---

## Session 2: SimilarTracks + CozyLibraryView Hooks (3-4 hours)

### Phase 2A: SimilarTracks Hooks (1 hour)
- [ ] `src/components/features/discovery/__tests__/useSimilarTracksLoader.test.ts`
- [ ] `src/components/features/discovery/__tests__/useSimilarTracksFormatting.test.ts`

**Mock**:
```typescript
vi.mock('../services/similarityService')
vi.mock('@/design-system/tokens')
```

### Phase 2B: CozyLibraryView Hooks (2-3 hours)
- [ ] `src/components/library/__tests__/usePlaybackState.test.ts`
- [ ] `src/components/library/__tests__/useNavigationState.test.ts`
- [ ] `src/components/library/__tests__/useMetadataEditing.test.ts`
- [ ] `src/components/library/__tests__/useBatchOperations.test.ts`

**Mock**:
```typescript
vi.mock('../../hooks/usePlayerAPI')
vi.mock('../shared/ui/feedback') // useToast
vi.mock('fetch') // for batch operations
```

### Test Focus
- Async operations
- API error handling
- State transitions
- Callback chains
- Toast notifications

---

## Session 3: UI Subcomponents (3-4 hours)

### Phase 3A: TrackRow Subcomponents (1 hour)
- [ ] `src/components/library/Items/__tests__/TrackRowPlayButton.test.tsx`
- [ ] `src/components/library/Items/__tests__/TrackRowAlbumArt.test.tsx`
- [ ] `src/components/library/Items/__tests__/TrackRowMetadata.test.tsx`

### Phase 3B: SimilarTracks Subcomponents (2 hours)
- [ ] `src/components/features/discovery/__tests__/SimilarTracksLoadingState.test.tsx`
- [ ] `src/components/features/discovery/__tests__/SimilarTracksErrorState.test.tsx`
- [ ] `src/components/features/discovery/__tests__/SimilarTracksEmptyState.test.tsx`
- [ ] `src/components/features/discovery/__tests__/SimilarTracksListItem.test.tsx`
- [ ] `src/components/features/discovery/__tests__/SimilarTracksHeader.test.tsx`
- [ ] `src/components/features/discovery/__tests__/SimilarTracksFooter.test.tsx`
- [ ] `src/components/features/discovery/__tests__/SimilarTracksList.test.tsx`

### Test Focus
- Props rendering
- Conditional rendering
- Icon/text display
- User interactions
- Styling application

### Run Command
```bash
npm run test:memory -- __tests__/*.test.tsx
```

---

## Session 4: Parent Component Tests (3-4 hours)

### Files to Update
- [ ] `src/components/library/__tests__/TrackRow.test.tsx`
- [ ] `src/components/library/__tests__/CozyLibraryView.test.tsx` (may not exist - might need create)
- [ ] `src/components/features/discovery/__tests__/SimilarTracks.test.tsx`

### Update Strategy
1. Add mocks for new hooks
2. Import new subcomponents
3. Add integration test cases
4. Verify backward compatibility
5. Test hook interactions

### Mock Patterns
```typescript
// Mock the extracted hooks
vi.mock('./useTrackRowHandlers')
vi.mock('./useTrackContextMenu')
vi.mock('./useTrackImage')
vi.mock('./useTrackFormatting')

// Return default implementations
useTrackRowHandlers.mockReturnValue({
  handlePlayClick: vi.fn(),
  handleRowClick: vi.fn(),
  handleRowDoubleClick: vi.fn(),
})
```

---

## Session 5: Integration & Final (2-3 hours)

### Integration Tests
- [ ] TrackRow full interaction flow
- [ ] SimilarTracks load → click → playback
- [ ] CozyLibraryView search → select → batch operation

### Final Checks
- [ ] Run full test suite: `npm run test:memory`
- [ ] Check coverage: `npm run test:coverage:memory`
- [ ] No console errors
- [ ] All tests passing
- [ ] Create final commit

---

## Testing Template

### Hook Test Template
```typescript
import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useMyHook } from '../useMyHook';

describe('useMyHook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should initialize with default values', () => {
    const { result } = renderHook(() => useMyHook());
    expect(result.current.value).toBe(defaultValue);
  });

  it('should update state when handler called', () => {
    const { result } = renderHook(() => useMyHook());
    act(() => {
      result.current.handler();
    });
    expect(result.current.value).toBe(expectedValue);
  });
});
```

### Component Test Template
```typescript
import { render, screen } from '@/test/test-utils';
import { describe, it, expect, vi } from 'vitest';
import MyComponent from '../MyComponent';

describe('MyComponent', () => {
  it('should render text', () => {
    render(<MyComponent text="hello" />);
    expect(screen.getByText('hello')).toBeInTheDocument();
  });

  it('should call onClick when clicked', async () => {
    const onClick = vi.fn();
    render(<MyComponent onClick={onClick} />);
    await screen.getByRole('button').click();
    expect(onClick).toHaveBeenCalled();
  });
});
```

---

## Common Assertions Checklist

- [ ] Component renders without errors
- [ ] Props are passed correctly
- [ ] Callbacks are triggered
- [ ] State updates happen
- [ ] Error handling works
- [ ] Conditional rendering works
- [ ] Styling applies correctly
- [ ] Accessibility attributes present
- [ ] Event handlers work
- [ ] Mocks are called correctly

---

## Debugging Tips

### Test Won't Run?
```bash
# Clear cache and reinstall
rm -rf node_modules/.vite
npm run test:memory -- --no-coverage
```

### Mock Not Working?
```typescript
// Check mock is before import
vi.mock('./path') // Must be at top of file

// Use full path
vi.mock('../../full/path/to/module')

// Verify mock return
console.log(vi.mocked(myFunction))
```

### State Not Updating?
```typescript
// Wrap updates in act()
import { act } from '@testing-library/react';
act(() => {
  result.current.handler();
});
```

### Async Test Failing?
```typescript
// Use waitFor for async operations
await waitFor(() => {
  expect(screen.getByText('loaded')).toBeInTheDocument();
});
```

---

## Performance Notes

- Run tests in order (hooks before components)
- Use `npm run test:memory` for full suite (2GB heap)
- Parallel test runs may cause memory issues
- Clear mocks between test files
- Use `beforeEach` for setup, not global setup

---

## Success Metrics

| Phase | Tests | Est. Coverage | Status |
|-------|-------|---------------|--------|
| Phase 1A | 4 | 95%+ | ⬜ Pending |
| Phase 1B | 2 | 90%+ | ⬜ Pending |
| Phase 1C | 4 | 90%+ | ⬜ Pending |
| Phase 2A | 3 | 85%+ | ⬜ Pending |
| Phase 2B | 7 | 85%+ | ⬜ Pending |
| Phase 3 | 3 | 80%+ | ⬜ Pending |
| Phase 4 | 3 | 85%+ | ⬜ Pending |
| **Total** | **26** | **87%+** | ⬜ Pending |

---

## Pre-Session Checklist

Before each session:
- [ ] Read relevant section of `STAGE_7_TEST_SUITE_PLAN.md`
- [ ] Ensure `npm install` completed
- [ ] Run `npm run test:memory` once to warm up cache
- [ ] Open test file template above
- [ ] Have existing test example open (reference pattern)
- [ ] Check design tokens for color values

---

## Post-Session Checklist

After each session:
- [ ] All new tests passing
- [ ] No console errors
- [ ] Coverage increased
- [ ] Commit changes: `git add . && git commit -m "test: Stage 7 Phase X tests"`
- [ ] Update status in checklist above

---

## Next Session Starting Point

**Last Completed**: Stage 7 refactoring (components + hooks)
**Next Step**: Session 1 - TrackRow hooks tests
**File**: `STAGE_7_TEST_SUITE_PLAN.md` - Phase 1A section
**Estimated Time**: 2-3 hours
**Priority**: HIGH (hooks are dependencies for component tests)

---

## Quick Commands

```bash
# Run specific test file
npm run test:memory -- Items/__tests__/useTrackRowHandlers.test.ts

# Run all new tests
npm run test:memory -- Items/__tests__/use*.test.ts

# Run with coverage
npm run test:coverage:memory -- Items/__tests__

# Watch mode (single file)
npm test -- Items/__tests__/useTrackRowHandlers.test.ts

# Watch with UI
npm run test:ui
```

---

**Updated**: November 23, 2025
**Status**: Ready for implementation
**Difficulty**: Medium (follows established patterns)
**Time Estimate**: 13-18 hours total (5 sessions)
