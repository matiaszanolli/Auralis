# Beta.6 - Keyboard Shortcuts Temporarily Disabled

## Issue Summary

Keyboard shortcuts feature was planned for Beta.6 but had to be disabled due to a critical JavaScript circular dependency error during Vite minification.

**Error**: `ReferenceError: Cannot access 'oe' before initialization`

**Impact**: Application wouldn't load - blank screen on startup

## Attempted Fixes

We tried 3 different implementations:

1. **useMemo with full dependencies** - Failed with circular dependency
2. **useMemo with empty dependencies** - Still failed with same error
3. **Complete rewrite without useMemo** - STILL failed with same error

Even `madge` tool confirmed no circular imports exist at the file level, suggesting the issue is in how Vite's minifier handles the complex callback structure.

## Root Cause Analysis

The issue appears to be related to how Vite's production minifier (esbuild/Rollup) handles:
- Complex React hooks with many callback dependencies
- Functions passed as props that reference component state
- Nested closures in the minified output

The error occurs specifically in production builds, not development mode, which makes it a minification-specific issue.

## Decision

**Keyboard shortcuts disabled for Beta.6 release** to ship a working product to users.

Feature will be re-implemented for Beta.7 with a different architecture that avoids this minification issue.

## What Was Removed

- `useKeyboardShortcuts` hook (code remains in codebase but unused)
- Keyboard shortcuts help dialog (`KeyboardShortcutsHelp` component)
- All keyboard shortcut handlers in `ComfortableApp.tsx`

## Beta.7 Plan

For Beta.7, we will:

1. **Investigate Vite build options** - Try different minification settings
2. **Simplify implementation** - Use native browser keyboard events instead of React hooks
3. **Alternative architecture** - Implement shortcuts as a separate service/context
4. **Test minified builds earlier** - Catch minification issues before release

## Files Modified

- `auralis-web/frontend/src/ComfortableApp.tsx` - Keyboard shortcuts disabled
- `auralis-web/frontend/src/hooks/useKeyboardShortcuts.ts` - Remains for future use

## Bundle Impact

- **With keyboard shortcuts**: 789.18 kB
- **Without keyboard shortcuts**: 781.14 kB
- **Savings**: 8.04 kB (1%)

## Timeline

- **Oct 30, 2025**: Feature developed (Phase 2.4)
- **Oct 30, 2025**: Bug discovered in production build
- **Oct 30, 2025**: 3 fix attempts failed
- **Oct 30, 2025**: Feature disabled to unblock Beta.6 release
- **Target**: Re-enable in Beta.7 (TBD)

## Lessons Learned

1. **Test production builds early** - Development mode doesn't catch minification issues
2. **Simplicity > Cleverness** - Complex React hook patterns can break in production
3. **Ship working software** - Better to ship without a feature than not ship at all
4. **Defer non-critical features** - Keyboard shortcuts are nice-to-have, not essential

---

**Status**: Beta.6 ships WITHOUT keyboard shortcuts
**Next Steps**: Investigate alternative implementation for Beta.7
