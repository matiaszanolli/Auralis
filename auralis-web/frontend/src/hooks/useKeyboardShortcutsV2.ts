/**
 * useKeyboardShortcutsV2 Hook
 *
 * Simple wrapper around keyboardShortcutsService.
 * Avoids circular dependency issues by using service pattern.
 *
 * This is V2 - a complete rewrite that fixes the minification issue
 * that disabled keyboard shortcuts in Beta 6.
 */

import { useEffect, useState } from 'react';
import { keyboardShortcuts, ShortcutDefinition, ShortcutHandler } from '../services/keyboardShortcutsService';

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
 * Register keyboard shortcuts with the service
 * Returns cleanup function and help dialog state
 */
export const useKeyboardShortcutsV2 = (
  shortcuts: KeyboardShortcut[],
  enabled: boolean = true
): UseKeyboardShortcutsReturn => {
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [isEnabled, setIsEnabled] = useState(enabled);

  // Register/unregister shortcuts
  useEffect(() => {
    // Register all shortcuts
    shortcuts.forEach(({ handler, ...definition }) => {
      keyboardShortcuts.register(definition, handler);
    });

    // Start listening
    keyboardShortcuts.startListening();

    // Cleanup: unregister and stop listening
    return () => {
      shortcuts.forEach(({ handler, ...definition }) => {
        keyboardShortcuts.unregister(definition);
      });
      keyboardShortcuts.stopListening();
    };
  }, []); // Empty deps - shortcuts are registered once on mount

  // Enable/disable based on prop
  useEffect(() => {
    if (isEnabled) {
      keyboardShortcuts.enable();
    } else {
      keyboardShortcuts.disable();
    }
  }, [isEnabled]);

  return {
    shortcuts: keyboardShortcuts.getShortcuts(),
    isHelpOpen,
    openHelp: () => setIsHelpOpen(true),
    closeHelp: () => setIsHelpOpen(false),
    enable: () => setIsEnabled(true),
    disable: () => setIsEnabled(false),
    isEnabled,
    formatShortcut: (shortcut) => keyboardShortcuts.formatShortcut(shortcut)
  };
};
