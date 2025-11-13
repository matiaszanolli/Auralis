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
import { keyboardShortcuts, ShortcutDefinition, ShortcutHandler } from '../services/keyboardShortcutsService';

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
 */
const configToServiceShortcuts = (config: KeyboardShortcutsConfig): Array<KeyboardShortcut & { definition: ShortcutDefinition }> => {
  const shortcuts: Array<KeyboardShortcut & { definition: ShortcutDefinition }> = [];

  // Playback controls
  if (config.onPlayPause) {
    shortcuts.push({
      definition: { key: ' ', description: 'Play/Pause', category: 'Playback' },
      handler: config.onPlayPause,
      key: ' ',
      description: 'Play/Pause',
      category: 'Playback'
    });
  }
  if (config.onNext) {
    shortcuts.push({
      definition: { key: 'ArrowRight', description: 'Next track', category: 'Playback' },
      handler: config.onNext,
      key: 'ArrowRight',
      description: 'Next track',
      category: 'Playback'
    });
  }
  if (config.onPrevious) {
    shortcuts.push({
      definition: { key: 'ArrowLeft', description: 'Previous track', category: 'Playback' },
      handler: config.onPrevious,
      key: 'ArrowLeft',
      description: 'Previous track',
      category: 'Playback'
    });
  }
  if (config.onSeekForward) {
    shortcuts.push({
      definition: { key: 'ArrowRight', shift: true, description: 'Seek forward', category: 'Playback' },
      handler: config.onSeekForward,
      key: 'ArrowRight',
      shift: true,
      description: 'Seek forward',
      category: 'Playback'
    });
  }
  if (config.onSeekBackward) {
    shortcuts.push({
      definition: { key: 'ArrowLeft', shift: true, description: 'Seek backward', category: 'Playback' },
      handler: config.onSeekBackward,
      key: 'ArrowLeft',
      shift: true,
      description: 'Seek backward',
      category: 'Playback'
    });
  }
  if (config.onVolumeUp) {
    shortcuts.push({
      definition: { key: 'ArrowUp', description: 'Volume up', category: 'Playback' },
      handler: config.onVolumeUp,
      key: 'ArrowUp',
      description: 'Volume up',
      category: 'Playback'
    });
  }
  if (config.onVolumeDown) {
    shortcuts.push({
      definition: { key: 'ArrowDown', description: 'Volume down', category: 'Playback' },
      handler: config.onVolumeDown,
      key: 'ArrowDown',
      description: 'Volume down',
      category: 'Playback'
    });
  }
  if (config.onMute) {
    // Support both '0' and Ctrl+M for mute
    shortcuts.push({
      definition: { key: '0', description: 'Mute/Unmute', category: 'Playback' },
      handler: config.onMute,
      key: '0',
      description: 'Mute/Unmute',
      category: 'Playback'
    });
    shortcuts.push({
      definition: { key: 'm', ctrl: true, description: 'Mute/Unmute', category: 'Playback' },
      handler: config.onMute,
      key: 'm',
      ctrl: true,
      description: 'Mute/Unmute',
      category: 'Playback'
    });
  }

  // Enhancement and display toggles
  if (config.onToggleEnhancement) {
    shortcuts.push({
      definition: { key: 'm', description: 'Toggle enhancement', category: 'Global' },
      handler: config.onToggleEnhancement,
      key: 'm',
      description: 'Toggle enhancement',
      category: 'Global'
    });
  }

  if (config.onToggleLyrics) {
    shortcuts.push({
      definition: { key: 'l', description: 'Toggle lyrics', category: 'Global' },
      handler: config.onToggleLyrics,
      key: 'l',
      description: 'Toggle lyrics',
      category: 'Global'
    });
  }

  // Preset selection
  if (config.onPresetChange) {
    const presets = [
      { key: '1', name: 'adaptive' },
      { key: '2', name: 'gentle' },
      { key: '3', name: 'warm' },
      { key: '4', name: 'bright' },
      { key: '5', name: 'punchy' },
    ];

    presets.forEach(({ key, name }) => {
      shortcuts.push({
        definition: { key, description: `${name} preset`, category: 'Global' },
        handler: () => config.onPresetChange?.(name),
        key,
        description: `${name} preset`,
        category: 'Global'
      });
    });
  }

  // Navigation
  if (config.onShowSongs) {
    shortcuts.push({
      definition: { key: '1', description: 'Show Songs', category: 'Navigation' },
      handler: config.onShowSongs,
      key: '1',
      description: 'Show Songs',
      category: 'Navigation'
    });
  }
  if (config.onShowAlbums) {
    shortcuts.push({
      definition: { key: '2', description: 'Show Albums', category: 'Navigation' },
      handler: config.onShowAlbums,
      key: '2',
      description: 'Show Albums',
      category: 'Navigation'
    });
  }
  if (config.onShowArtists) {
    shortcuts.push({
      definition: { key: '3', description: 'Show Artists', category: 'Navigation' },
      handler: config.onShowArtists,
      key: '3',
      description: 'Show Artists',
      category: 'Navigation'
    });
  }
  if (config.onShowPlaylists) {
    shortcuts.push({
      definition: { key: '4', description: 'Show Playlists', category: 'Navigation' },
      handler: config.onShowPlaylists,
      key: '4',
      description: 'Show Playlists',
      category: 'Navigation'
    });
  }
  if (config.onFocusSearch) {
    // Support '/', Ctrl+K (Windows/Linux), and Cmd+K (Mac)
    shortcuts.push({
      definition: { key: '/', description: 'Focus search', category: 'Navigation' },
      handler: config.onFocusSearch,
      key: '/',
      description: 'Focus search',
      category: 'Navigation'
    });
    shortcuts.push({
      definition: { key: 'k', ctrl: true, description: 'Quick search', category: 'Navigation' },
      handler: config.onFocusSearch,
      key: 'k',
      ctrl: true,
      description: 'Quick search',
      category: 'Navigation'
    });
    shortcuts.push({
      definition: { key: 'k', meta: true, description: 'Quick search', category: 'Navigation' },
      handler: config.onFocusSearch,
      key: 'k',
      meta: true,
      description: 'Quick search',
      category: 'Navigation'
    });
  }
  if (config.onEscape) {
    shortcuts.push({
      definition: { key: 'Escape', description: 'Clear search / Close dialogs', category: 'Navigation' },
      handler: config.onEscape,
      key: 'Escape',
      description: 'Clear search / Close dialogs',
      category: 'Navigation'
    });
  }

  // Library actions
  if (config.onPlaySelected) {
    shortcuts.push({
      definition: { key: 'Enter', description: 'Play selected', category: 'Library' },
      handler: config.onPlaySelected,
      key: 'Enter',
      description: 'Play selected',
      category: 'Library'
    });
  }
  if (config.onToggleFavorite) {
    shortcuts.push({
      definition: { key: 'l', description: 'Toggle favorite', category: 'Library' },
      handler: config.onToggleFavorite,
      key: 'l',
      description: 'Toggle favorite',
      category: 'Library'
    });
  }
  if (config.onAddToPlaylist) {
    shortcuts.push({
      definition: { key: 'p', description: 'Add to playlist', category: 'Library' },
      handler: config.onAddToPlaylist,
      key: 'p',
      description: 'Add to playlist',
      category: 'Library'
    });
  }
  if (config.onAddToQueue) {
    shortcuts.push({
      definition: { key: 'q', description: 'Add to queue', category: 'Library' },
      handler: config.onAddToQueue,
      key: 'q',
      description: 'Add to queue',
      category: 'Library'
    });
  }
  if (config.onShowInfo) {
    shortcuts.push({
      definition: { key: 'i', description: 'Show info', category: 'Library' },
      handler: config.onShowInfo,
      key: 'i',
      description: 'Show info',
      category: 'Library'
    });
  }
  if (config.onDelete) {
    shortcuts.push({
      definition: { key: 'Delete', description: 'Delete', category: 'Library' },
      handler: config.onDelete,
      key: 'Delete',
      description: 'Delete',
      category: 'Library'
    });
  }

  // Queue management
  if (config.onClearQueue) {
    shortcuts.push({
      definition: { key: 'c', ctrl: true, shift: true, description: 'Clear queue', category: 'Queue' },
      handler: config.onClearQueue,
      key: 'c',
      ctrl: true,
      shift: true,
      description: 'Clear queue',
      category: 'Queue'
    });
  }
  if (config.onShuffleQueue) {
    shortcuts.push({
      definition: { key: 's', ctrl: true, shift: true, description: 'Shuffle queue', category: 'Queue' },
      handler: config.onShuffleQueue,
      key: 's',
      ctrl: true,
      shift: true,
      description: 'Shuffle queue',
      category: 'Queue'
    });
  }

  // Global
  if (config.onShowHelp) {
    shortcuts.push({
      definition: { key: '?', description: 'Show keyboard shortcuts', category: 'Global' },
      handler: config.onShowHelp,
      key: '?',
      description: 'Show keyboard shortcuts',
      category: 'Global'
    });
  }
  if (config.onOpenSettings) {
    shortcuts.push({
      definition: { key: ',', ctrl: true, description: 'Open settings', category: 'Global' },
      handler: config.onOpenSettings,
      key: ',',
      ctrl: true,
      description: 'Open settings',
      category: 'Global'
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
