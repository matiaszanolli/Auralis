/**
 * useKeyboardShortcuts Hook
 *
 * Provides global keyboard shortcut handling for the application.
 * Supports playback controls, navigation, library actions, and more.
 *
 * Usage:
 * ```tsx
 * const shortcuts = useKeyboardShortcuts({
 *   onPlayPause: () => player.togglePlayPause(),
 *   onNext: () => player.next(),
 *   // ... other handlers
 * });
 * ```
 *
 * Features:
 * - Prevents conflicts with input fields (automatically disabled when typing)
 * - Supports modifier keys (Ctrl/Cmd, Shift, Alt)
 * - Cross-platform (handles Cmd on Mac, Ctrl on Windows/Linux)
 * - Customizable shortcuts
 * - Help dialog with all shortcuts
 */

import { useEffect, useCallback, useState, useMemo } from 'react';

// Keyboard shortcut configuration
export interface KeyboardShortcut {
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  meta?: boolean; // Cmd on Mac
  description: string;
  category: 'Playback' | 'Navigation' | 'Library' | 'Queue' | 'Global';
  handler: () => void;
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

  // Library actions (require track selection)
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

  // Configuration
  enabled?: boolean; // Default: true
  debug?: boolean; // Log shortcut triggers
}

export interface UseKeyboardShortcutsReturn {
  shortcuts: KeyboardShortcut[];
  isHelpOpen: boolean;
  openHelp: () => void;
  closeHelp: () => void;
  isEnabled: boolean;
  setEnabled: (enabled: boolean) => void;
}

/**
 * Check if the target element is an input field where we should ignore shortcuts
 */
const isInputElement = (target: EventTarget | null): boolean => {
  if (!target || !(target instanceof HTMLElement)) return false;

  const tagName = target.tagName.toLowerCase();
  const isInput = tagName === 'input' || tagName === 'textarea' || tagName === 'select';
  const isContentEditable = target.contentEditable === 'true';

  return isInput || isContentEditable;
};

/**
 * Check if modifier keys match
 */
const matchesModifiers = (
  event: KeyboardEvent,
  shortcut: { ctrl?: boolean; shift?: boolean; alt?: boolean; meta?: boolean }
): boolean => {
  const ctrlOrMeta = shortcut.ctrl || shortcut.meta;
  const eventCtrlOrMeta = event.ctrlKey || event.metaKey;

  // Check Ctrl/Cmd
  if (ctrlOrMeta && !eventCtrlOrMeta) return false;
  if (!ctrlOrMeta && eventCtrlOrMeta) return false;

  // Check Shift
  if (shortcut.shift && !event.shiftKey) return false;
  if (!shortcut.shift && event.shiftKey) return false;

  // Check Alt
  if (shortcut.alt && !event.altKey) return false;
  if (!shortcut.alt && event.altKey) return false;

  return true;
};

/**
 * Format shortcut key for display
 */
export const formatShortcut = (shortcut: KeyboardShortcut): string => {
  const parts: string[] = [];

  const isMac = typeof navigator !== 'undefined' && navigator.platform.toUpperCase().indexOf('MAC') >= 0;

  if (shortcut.ctrl || shortcut.meta) {
    parts.push(isMac ? '⌘' : 'Ctrl');
  }
  if (shortcut.shift) {
    parts.push(isMac ? '⇧' : 'Shift');
  }
  if (shortcut.alt) {
    parts.push(isMac ? '⌥' : 'Alt');
  }

  // Format key display
  let keyDisplay = shortcut.key;
  const keyMap: Record<string, string> = {
    ' ': 'Space',
    'ArrowUp': '↑',
    'ArrowDown': '↓',
    'ArrowLeft': '←',
    'ArrowRight': '→',
    'Enter': '↵',
    'Escape': 'Esc',
    'Delete': 'Del',
    '/': '/',
    '?': '?',
    ',': ',',
  };

  if (keyMap[shortcut.key]) {
    keyDisplay = keyMap[shortcut.key];
  } else {
    keyDisplay = shortcut.key.toUpperCase();
  }

  parts.push(keyDisplay);

  return parts.join(isMac ? '' : '+');
};

/**
 * Main keyboard shortcuts hook
 */
export const useKeyboardShortcuts = (config: KeyboardShortcutsConfig = {}): UseKeyboardShortcutsReturn => {
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [isEnabled, setIsEnabled] = useState(config.enabled !== false);

  // Build shortcuts array (memoized to prevent circular dependencies)
  const shortcuts = useMemo(() => {
    const result: KeyboardShortcut[] = [];

    // Playback controls
    if (config.onPlayPause) {
      result.push({
        key: ' ',
        description: 'Play/Pause',
        category: 'Playback',
        handler: config.onPlayPause,
      });
    }
    if (config.onNext) {
      result.push({
        key: 'ArrowRight',
        description: 'Next track',
        category: 'Playback',
        handler: config.onNext,
      });
    }
    if (config.onPrevious) {
      result.push({
        key: 'ArrowLeft',
        description: 'Previous track',
        category: 'Playback',
        handler: config.onPrevious,
      });
    }
    if (config.onSeekForward) {
      result.push({
        key: 'ArrowRight',
        shift: true,
        description: 'Seek forward 10s',
        category: 'Playback',
        handler: config.onSeekForward,
      });
    }
    if (config.onSeekBackward) {
      result.push({
        key: 'ArrowLeft',
        shift: true,
        description: 'Seek backward 10s',
        category: 'Playback',
        handler: config.onSeekBackward,
      });
    }
    if (config.onVolumeUp) {
      result.push({
        key: 'ArrowUp',
        description: 'Volume up',
        category: 'Playback',
        handler: config.onVolumeUp,
      });
    }
    if (config.onVolumeDown) {
      result.push({
        key: 'ArrowDown',
        description: 'Volume down',
        category: 'Playback',
        handler: config.onVolumeDown,
      });
    }
    if (config.onMute) {
      result.push({
        key: 'm',
        description: 'Mute/Unmute',
        category: 'Playback',
        handler: config.onMute,
      });
    }

    // Navigation
    if (config.onShowSongs) {
      result.push({
        key: '1',
        description: 'Show Songs',
        category: 'Navigation',
        handler: config.onShowSongs,
      });
    }
    if (config.onShowAlbums) {
      result.push({
        key: '2',
        description: 'Show Albums',
        category: 'Navigation',
        handler: config.onShowAlbums,
      });
    }
    if (config.onShowArtists) {
      result.push({
        key: '3',
        description: 'Show Artists',
        category: 'Navigation',
        handler: config.onShowArtists,
      });
    }
    if (config.onShowPlaylists) {
      result.push({
        key: '4',
        description: 'Show Playlists',
        category: 'Navigation',
        handler: config.onShowPlaylists,
      });
    }
    if (config.onFocusSearch) {
      result.push({
        key: '/',
        description: 'Focus search',
        category: 'Navigation',
        handler: config.onFocusSearch,
      });
    }
    if (config.onEscape) {
      result.push({
        key: 'Escape',
        description: 'Clear search / Close dialogs',
        category: 'Navigation',
        handler: config.onEscape,
      });
    }

    // Library actions
    if (config.onPlaySelected) {
      result.push({
        key: 'Enter',
        description: 'Play selected track',
        category: 'Library',
        handler: config.onPlaySelected,
      });
    }
    if (config.onToggleFavorite) {
      result.push({
        key: 'l',
        description: 'Like/Unlike track',
        category: 'Library',
        handler: config.onToggleFavorite,
      });
    }
    if (config.onAddToPlaylist) {
      result.push({
        key: 'p',
        description: 'Add to playlist',
        category: 'Library',
        handler: config.onAddToPlaylist,
      });
    }
    if (config.onAddToQueue) {
      result.push({
        key: 'q',
        description: 'Add to queue',
        category: 'Library',
        handler: config.onAddToQueue,
      });
    }
    if (config.onShowInfo) {
      result.push({
        key: 'i',
        description: 'Show track info',
        category: 'Library',
        handler: config.onShowInfo,
      });
    }
    if (config.onDelete) {
      result.push({
        key: 'Delete',
        description: 'Remove from playlist/queue',
        category: 'Library',
        handler: config.onDelete,
      });
    }

    // Queue management
    if (config.onClearQueue) {
      result.push({
        key: 'c',
        ctrl: true,
        shift: true,
        description: 'Clear queue',
        category: 'Queue',
        handler: config.onClearQueue,
      });
    }
    if (config.onShuffleQueue) {
      result.push({
        key: 's',
        ctrl: true,
        shift: true,
        description: 'Shuffle queue',
        category: 'Queue',
        handler: config.onShuffleQueue,
      });
    }

    // Global
    if (config.onShowHelp) {
      result.push({
        key: '?',
        description: 'Show keyboard shortcuts',
        category: 'Global',
        handler: config.onShowHelp,
      });
    }
    if (config.onOpenSettings) {
      result.push({
        key: ',',
        ctrl: true,
        description: 'Open settings',
        category: 'Global',
        handler: config.onOpenSettings,
      });
    }

    return result;
  }, [
    config.onPlayPause,
    config.onNext,
    config.onPrevious,
    config.onSeekForward,
    config.onSeekBackward,
    config.onVolumeUp,
    config.onVolumeDown,
    config.onMute,
    config.onShowSongs,
    config.onShowAlbums,
    config.onShowArtists,
    config.onShowPlaylists,
    config.onFocusSearch,
    config.onEscape,
    config.onPlaySelected,
    config.onToggleFavorite,
    config.onAddToPlaylist,
    config.onAddToQueue,
    config.onShowInfo,
    config.onDelete,
    config.onClearQueue,
    config.onShuffleQueue,
    config.onShowHelp,
    config.onOpenSettings,
  ]);

  // Keyboard event handler
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      // Don't handle if disabled
      if (!isEnabled) return;

      // Don't handle if typing in input field
      if (isInputElement(event.target)) return;

      // Special case: ? requires Shift+/ on US keyboards
      const key = event.key === '?' ? '?' : event.key;

      // Find matching shortcut
      const matchingShortcut = shortcuts.find(
        (shortcut) =>
          shortcut.key.toLowerCase() === key.toLowerCase() &&
          matchesModifiers(event, shortcut)
      );

      if (matchingShortcut) {
        event.preventDefault();
        event.stopPropagation();

        if (config.debug) {
          console.log('[Keyboard Shortcut]', formatShortcut(matchingShortcut), matchingShortcut.description);
        }

        matchingShortcut.handler();
      }
    },
    [shortcuts, isEnabled, config.debug]
  );

  // Register global keyboard listener
  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const openHelp = useCallback(() => setIsHelpOpen(true), []);
  const closeHelp = useCallback(() => setIsHelpOpen(false), []);

  return {
    shortcuts,
    isHelpOpen,
    openHelp,
    closeHelp,
    isEnabled,
    setEnabled,
  };
};

export default useKeyboardShortcuts;
