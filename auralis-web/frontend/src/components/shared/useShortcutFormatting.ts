import { useMemo } from 'react';
import { ShortcutDefinition } from '../../services/keyboardShortcutsService';

export interface GroupedShortcuts {
  [category: string]: ShortcutDefinition[];
}

interface ShortcutFormatConfig {
  categoryOrder: Array<ShortcutDefinition['category']>;
  categoryIcons: Record<ShortcutDefinition['category'], string>;
}

/**
 * Default formatter for keyboard shortcuts
 *
 * Converts shortcut objects to human-readable key combinations:
 * - Mac: Uses symbols (⌘, ⇧, ⌥)
 * - Other: Uses text (Ctrl, Shift, Alt)
 * - Special keys: Converted to symbols (Space, arrows, etc.)
 */
function defaultFormatShortcut(shortcut: ShortcutDefinition): string {
  const parts: string[] = [];
  const isMac = typeof navigator !== 'undefined' &&
                navigator.platform.toUpperCase().indexOf('MAC') >= 0;

  if (shortcut.ctrl || shortcut.meta) {
    parts.push(isMac ? '⌘' : 'Ctrl');
  }
  if (shortcut.shift) {
    parts.push(isMac ? '⇧' : 'Shift');
  }
  if (shortcut.alt) {
    parts.push(isMac ? '⌥' : 'Alt');
  }

  const keyMap: Record<string, string> = {
    ' ': 'Space',
    'ArrowUp': '↑',
    'ArrowDown': '↓',
    'ArrowLeft': '←',
    'ArrowRight': '→',
    'Enter': '↵',
    'Escape': 'Esc',
    'Delete': 'Del',
  };

  const keyDisplay = keyMap[shortcut.key] || shortcut.key.toUpperCase();
  parts.push(keyDisplay);

  return parts.join(isMac ? '' : '+');
}

/**
 * useShortcutFormatting - Memoized shortcut grouping and formatting
 *
 * Groups shortcuts by category and provides formatting function.
 */
export const useShortcutFormatting = (
  shortcuts: ShortcutDefinition[],
  formatShortcut?: (shortcut: ShortcutDefinition) => string
): {
  groupedShortcuts: GroupedShortcuts;
  config: ShortcutFormatConfig;
  formatFn: (shortcut: ShortcutDefinition) => string;
} => {
  return useMemo(() => {
    // Group shortcuts by category
    const groupedShortcuts: GroupedShortcuts = {};
    shortcuts.forEach((shortcut) => {
      if (!groupedShortcuts[shortcut.category]) {
        groupedShortcuts[shortcut.category] = [];
      }
      groupedShortcuts[shortcut.category].push(shortcut);
    });

    // Category order
    const categoryOrder: Array<ShortcutDefinition['category']> = [
      'Playback',
      'Navigation',
      'Library',
      'Queue',
      'Global',
    ];

    // Category icons
    const categoryIcons: Record<ShortcutDefinition['category'], string> = {
      'Playback': '🎵',
      'Navigation': '🧭',
      'Library': '📚',
      'Queue': '📝',
      'Global': '⚙️',
    };

    return {
      groupedShortcuts,
      config: { categoryOrder, categoryIcons },
      formatFn: formatShortcut || defaultFormatShortcut,
    };
  }, [shortcuts, formatShortcut]);
};
