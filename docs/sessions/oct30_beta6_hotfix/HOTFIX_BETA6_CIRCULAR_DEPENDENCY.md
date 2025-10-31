# Hotfix: Beta.6 Circular Dependency (Oct 30, 2025)

## Issue
After releasing Beta.6, a critical JavaScript initialization error was discovered:
```
ReferenceError: Cannot access 'oe' before initialization
```

This error prevented the application from loading in the browser.

## Root Cause
The `useKeyboardShortcuts` hook was creating a `shortcuts` array directly in the hook body (line 178), which was then passed as a dependency to `useCallback` (line 419). This caused Vite's minifier to detect a circular reference during the build process, resulting in a Temporal Dead Zone (TDZ) error in the bundled code.

## Fix Applied
**File**: `auralis-web/frontend/src/hooks/useKeyboardShortcuts.ts`

**Changes**:
1. Added `useMemo` to imports (line 24)
2. Wrapped the shortcuts array construction in `useMemo` with proper dependencies (lines 177-416)

**Before**:
```typescript
const shortcuts: KeyboardShortcut[] = [];
// ... array construction
const handleKeyDown = useCallback(..., [shortcuts, isEnabled, config.debug]);
```

**After**:
```typescript
const shortcuts = useMemo(() => {
  const result: KeyboardShortcut[] = [];
  // ... array construction
  return result;
}, [config.onPlayPause, config.onNext, /* ... all handlers */]);

const handleKeyDown = useCallback(..., [shortcuts, isEnabled, config.debug]);
```

## Additional Fix
**File**: `auralis-web/backend/routers/player.py`

Fixed missing import for `Optional` type (line 33):
```python
from typing import List, Optional
```

## Testing
- ✅ Frontend builds successfully (3.99s)
- ✅ Backend starts without errors
- ✅ Application loads in browser (http://localhost:3000)
- ✅ No console errors

## Impact
- Critical: Application was completely broken
- Severity: P0 (blocks all use)
- Affected versions: 1.0.0-beta.6 (initial release)

## Next Steps
1. Rebuild all packages with the fix
2. Update GitHub release with fixed packages
3. Document the hotfix in release notes
