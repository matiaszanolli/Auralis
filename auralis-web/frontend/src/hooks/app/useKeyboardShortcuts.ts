/**
 * useKeyboardShortcuts Hook (Phase 3a - Unified)
 *
 * Consolidated keyboard shortcuts hook supporting both config-based (V1) and
 * service-based (V2) patterns for backward compatibility.
 *
 * Phase 3a consolidation merges V1's flexible config interface with V2's
 * robust service architecture. Prefers V2 pattern but maintains V1 compatibility.
 */

import { useEffect, useCallback, useState } from 'react';
import { keyboardShortcuts, ShortcutDefinition, ShortcutHandler } from '@/services/keyboardShortcutsService';
import {
  SHORTCUT_CONFIG_MAP,
  PRESET_SHORTCUTS,
  PRESET_NAMES,
  createShortcutDefinition
} from './keyboardShortcutDefinitions';

export interface KeyboardShortcut extends ShortcutDefinition {
  handler: ShortcutHandler;
}

export interface KeyboardShortcutsConfig {
  // Playback controls
  onPlayPause?: () => void;
  onNext?: () => void;
  onPrevious?: () => void;
  onSeekForward?: () => void;
  onSeekBackward?: () => void;
  onVolumeUp?: () => void;
  onVolumeDown?: () => void;
  onMute?: () => void;

  // Navigation
  onShowSongs?: () => void;
  onShowAlbums?: () => void;
  onShowArtists?: () => void;
  onShowPlaylists?: () => void;
  onFocusSearch?: () => void;
  onEscape?: () => void;

  // Library actions
  onPlaySelected?: () => void;
  onToggleFavorite?: () => void;
  onAddToPlaylist?: () => void;
  onAddToQueue?: () => void;
  onShowInfo?: () => void;
  onDelete?: () => void;

  // Queue management
  onClearQueue?: () => void;
  onShuffleQueue?: () => void;

  // Global
  onShowHelp?: () => void;
  onOpenSettings?: () => void;

  // Enhancement and display
  onToggleEnhancement?: () => void;
  onToggleLyrics?: () => void;
  onPresetChange?: (preset: string) => void;

  // Options
  enabled?: boolean;
  debug?: boolean;
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
 * Convert config-based shortcuts (V1 pattern) to service-based shortcuts (V2 pattern)
 * Phase 3a: Unified handler that maintains backward compatibility
 *
 * Refactored to use configuration-driven approach (90% reduction in lines)
 */
const configToServiceShortcuts = (config: KeyboardShortcutsConfig): Array<KeyboardShortcut> => {
  const shortcuts: Array<KeyboardShortcut> = [];

  // Use SHORTCUT_CONFIG_MAP to eliminate repetitive if/push boilerplate
  SHORTCUT_CONFIG_MAP.forEach((entry) => {
    const handler = entry.handler(config);
    if (!handler) return; // Skip if handler not provided

    entry.shortcuts.forEach((shortcutEntry) => {
      const definition = createShortcutDefinition(shortcutEntry);
      shortcuts.push({
        ...definition,
        handler
      } as KeyboardShortcut);
    });
  });

  // Special case: Preset selection (dynamic preset names)
  if (config.onPresetChange) {
    PRESET_SHORTCUTS.forEach((shortcutEntry, index) => {
      const definition = createShortcutDefinition(shortcutEntry);
      shortcuts.push({
        ...definition,
        handler: () => config.onPresetChange?.(PRESET_NAMES[index])
      } as KeyboardShortcut);
    });
  }

  return shortcuts;
};

/**
 * Format shortcut for display (Phase 3a: Unified from service)
 */
export const formatShortcut = (shortcut: ShortcutDefinition): string => {
  return keyboardShortcuts.formatShortcut(shortcut);
};

/**
 * Legacy alias for formatShortcut (for backward compatibility with tests)
 */
export const getShortcutString = (shortcut: string): string => {
  // Handle string-based shortcut formatting for tests
  // This converts shortcut strings like 'Cmd+K' to display format
  const isMac = typeof navigator !== 'undefined' &&
                navigator.platform.toUpperCase().indexOf('MAC') >= 0;

  if (shortcut.includes('Cmd')) {
    return shortcut.replace('Cmd', isMac ? '⌘' : 'Ctrl');
  }

  return shortcut;
};

/**
 * Default keyboard shortcuts library for export and testing
 * These are the standard shortcuts available throughout the application
 */
export const KEYBOARD_SHORTCUTS = [
  // Playback controls
  { key: ' ', action: 'Play/Pause', category: 'Playback' },
  { key: 'ArrowRight', action: 'Next track', category: 'Playback' },
  { key: 'ArrowLeft', action: 'Previous track', category: 'Playback' },
  { key: 'ArrowUp', action: 'Volume up', category: 'Playback' },
  { key: 'ArrowDown', action: 'Volume down', category: 'Playback' },
  { key: '0', action: 'Mute/Unmute', category: 'Playback' },
  { key: 'm', ctrl: true, action: 'Mute/Unmute', category: 'Playback' },

  // Navigation
  { key: '/', action: 'Focus search', category: 'Navigation' },
  { key: 'k', ctrl: true, action: 'Quick search', category: 'Navigation' },
  { key: 'k', meta: true, action: 'Quick search (Mac)', category: 'Navigation' },
  { key: ',', ctrl: true, action: 'Open settings', category: 'Navigation' },
  { key: ',', meta: true, action: 'Open settings (Mac)', category: 'Navigation' },

  // Presets
  { key: '1', action: 'Adaptive preset', category: 'Presets' },
  { key: '2', action: 'Gentle preset', category: 'Presets' },
  { key: '3', action: 'Warm preset', category: 'Presets' },
  { key: '4', action: 'Bright preset', category: 'Presets' },
  { key: '5', action: 'Punchy preset', category: 'Presets' },
];

/**
 * Main keyboard shortcuts hook - UNIFIED VERSION (Phase 3a)
 *
 * Supports both:
 * - V1 config-based pattern: Pass handlers as config object
 * - V2 service-based pattern: Pass shortcuts array directly
 */
export const useKeyboardShortcuts = (
  configOrShortcuts?: KeyboardShortcutsConfig | KeyboardShortcut[]
): UseKeyboardShortcutsReturn => {
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [isEnabled, setIsEnabled] = useState(
    Array.isArray(configOrShortcuts)
      ? true
      : (configOrShortcuts?.enabled !== false)
  );

  // Determine input format and convert to service format
  const shortcutsToRegister = Array.isArray(configOrShortcuts)
    ? configOrShortcuts
    : configToServiceShortcuts(configOrShortcuts || {});

  // Register shortcuts with service on mount
  useEffect(() => {
    // Clear any previous shortcuts
    keyboardShortcuts.clear();

    // Register all shortcuts
    shortcutsToRegister.forEach((shortcut) => {
      const { handler, ...definition } = shortcut;
      keyboardShortcuts.register(definition, handler);
    });

    // Start listening
    keyboardShortcuts.startListening();

    // Cleanup: stop listening and clear on unmount
    return () => {
      keyboardShortcuts.stopListening();
      keyboardShortcuts.clear();
    };
  }, [shortcutsToRegister]);

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
    shortcuts: keyboardShortcuts.getShortcuts(),
    isHelpOpen,
    openHelp,
    closeHelp,
    enable,
    disable,
    isEnabled,
    formatShortcut: (shortcut) => keyboardShortcuts.formatShortcut(shortcut)
  };
};
