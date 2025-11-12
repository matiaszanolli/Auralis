/**
 * useKeyboardShortcutsV2 Hook (DEPRECATED - Phase 3a)
 *
 * ⚠️ DEPRECATED: Use `useKeyboardShortcuts` from './useKeyboardShortcuts.ts' instead
 *
 * This file is maintained for backward compatibility only.
 * Phase 3a consolidation unified V1 (config-based) and V2 (service-based) patterns
 * into a single hook that supports both interfaces.
 *
 * Migration guide:
 * - OLD: import { useKeyboardShortcutsV2 } from './useKeyboardShortcutsV2'
 * - NEW: import { useKeyboardShortcuts } from './useKeyboardShortcuts'
 *
 * The unified hook maintains backward compatibility while delegating to the
 * keyboardShortcutsService, exactly like this V2 implementation.
 */

// Re-export unified hook as V2 for backward compatibility
export { useKeyboardShortcuts as useKeyboardShortcutsV2 } from './useKeyboardShortcuts';
export type { UseKeyboardShortcutsReturn, KeyboardShortcut } from './useKeyboardShortcuts';
