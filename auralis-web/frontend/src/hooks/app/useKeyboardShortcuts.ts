/**
 * useKeyboardShortcuts Hook
 *
 * Registers a caller-supplied array of keyboard shortcuts with the shared
 * KeyboardShortcutsService, keeping handlers current across re-renders
 * without re-registering on every render (#4692).
 *
 * #5231: this used to also accept a `KeyboardShortcutsConfig` object (a
 * fixed set of named handlers like `onPlayPause`/`onNext`) as a "V1
 * backward-compatible" input alongside the array form. That branch had zero
 * production callers — the sole call site (ComfortableApp.tsx) always
 * passed the array form — and was exercised only by this hook's own test
 * suite, so it was deleted along with the sibling `KeyboardShortcutsConfig`
 * config-map machinery in keyboardShortcutDefinitions.ts (also deleted
 * wholesale, including its `PRESET_SHORTCUTS`/`PRESET_NAMES`, which turned
 * out to be reachable only through the dead V1 path — not the live
 * keyboard-shortcut path a prior audit assumed).
 */

import { useEffect, useLayoutEffect, useCallback, useState, useRef } from 'react';
import { keyboardShortcuts, ShortcutDefinition, ShortcutHandler } from '@/services/keyboardShortcutsService';

export interface KeyboardShortcut extends ShortcutDefinition {
  handler: ShortcutHandler;
}

export interface UseKeyboardShortcutsReturn {
  shortcuts: ShortcutDefinition[];
  isHelpOpen: boolean;
  openHelp: () => void;
  closeHelp: () => void;
  enable: () => void;
  disable: () => void;
  isEnabled: boolean;
  formatShortcut: (shortcut: ShortcutDefinition) => string;
}

/**
 * Format shortcut for display.
 */
export const formatShortcut = (shortcut: ShortcutDefinition): string => {
  return keyboardShortcuts.formatShortcut(shortcut);
};

/**
 * Register `shortcuts` with the shared KeyboardShortcutsService for as long
 * as this hook is mounted.
 */
export const useKeyboardShortcuts = (
  shortcuts: KeyboardShortcut[] = []
): UseKeyboardShortcutsReturn => {
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [isEnabled, setIsEnabled] = useState(true);

  // Stabilize: only re-register when the set of shortcut keys actually changes,
  // not when handler identity changes (which happens every render).
  const serializedKey = shortcuts
    .map((s: KeyboardShortcut) => `${s.key}:${s.ctrl ?? ''}:${s.meta ?? ''}:${s.alt ?? ''}:${s.shift ?? ''}`)
    .join('|');

  // The live shortcut array, refreshed every commit. Handler closures change
  // identity on every render while the shortcut *structure* rarely does, so
  // the two are decoupled: this ref carries the current handlers, and the
  // effect below registers a stable trampoline that reads through it.
  //
  // Done in a layout effect (post-commit) rather than the render body so
  // render stays pure — a render-body side effect double-fired under
  // Concurrent/Strict mode (#4160). It runs before the passive effect below
  // on the same commit, so a structure change sees the new handlers.
  const shortcutsRef = useRef(shortcuts);
  useLayoutEffect(() => {
    shortcutsRef.current = shortcuts;
  });

  // Register shortcuts with the service when the shortcut *keys* change.
  //
  // #4692: this used to be two registration paths with different gating,
  // one of which re-registered on every render for the (now-deleted, #5231)
  // config-object form because it built a fresh array each render. The
  // trampoline below resolves both at once: registration happens once per
  // structure change, and the handler it registers reads the latest closure
  // out of the ref at call time. Index lookup is safe because serializedKey
  // encodes every shortcut's key and modifiers in order, so any change that
  // could reorder or resize the array also changes the key and re-runs this
  // effect.
  useEffect(() => {
    // Clear any previous shortcuts
    keyboardShortcuts.clear();

    // Register all shortcuts
    shortcutsRef.current.forEach((shortcut: KeyboardShortcut, index: number) => {
      const { handler: _handler, ...definition } = shortcut;
      keyboardShortcuts.register(definition, () => {
        shortcutsRef.current[index]?.handler();
      });
    });

    // Start listening
    keyboardShortcuts.startListening();

    // Cleanup: stop listening and clear on unmount
    return () => {
      keyboardShortcuts.stopListening();
      keyboardShortcuts.clear();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- serializedKey tracks shortcut structure; handlers stay current via shortcutsRef
  }, [serializedKey]);

  // Enable/disable based on state
  useEffect(() => {
    if (isEnabled) {
      keyboardShortcuts.enable();
    } else {
      keyboardShortcuts.disable();
    }
  }, [isEnabled]);

  const openHelp = useCallback(() => setIsHelpOpen(true), []);
  const closeHelp = useCallback(() => setIsHelpOpen(false), []);
  const enable = useCallback(() => setIsEnabled(true), []);
  const disable = useCallback(() => setIsEnabled(false), []);

  return {
    shortcuts: shortcuts.map(({ handler, ...definition }) => definition),
    isHelpOpen,
    openHelp,
    closeHelp,
    enable,
    disable,
    isEnabled,
    formatShortcut: (shortcut) => keyboardShortcuts.formatShortcut(shortcut)
  };
};
