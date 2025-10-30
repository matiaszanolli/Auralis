/**
 * useKeyboardShortcuts Hook
 *
 * Simplified version to avoid circular dependency issues.
 * Uses event handlers directly instead of building a shortcuts array.
 */

import { useEffect, useCallback, useState } from 'react';

export interface KeyboardShortcut {
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  meta?: boolean;
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

  // Options
  enabled?: boolean;
  debug?: boolean;
}

export interface UseKeyboardShortcutsReturn {
  shortcuts: KeyboardShortcut[];
  isHelpOpen: boolean;
  openHelp: () => void;
  closeHelp: () => void;
  enable: () => void;
  disable: () => void;
  isEnabled: boolean;
}

/**
 * Check if element is an input that should block shortcuts
 */
const isInputElement = (target: EventTarget | null): boolean => {
  if (!target || !(target instanceof HTMLElement)) return false;

  const tagName = target.tagName.toLowerCase();
  const isInput = ['input', 'textarea', 'select'].includes(tagName);
  const isContentEditable = target.contentEditable === 'true';

  return isInput || isContentEditable;
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
};

/**
 * Main keyboard shortcuts hook - SIMPLIFIED VERSION
 */
export const useKeyboardShortcuts = (config: KeyboardShortcutsConfig = {}): UseKeyboardShortcutsReturn => {
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [isEnabled, setIsEnabled] = useState(config.enabled !== false);

  // Keyboard event handler - handles keys directly
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (!isEnabled) return;
      if (isInputElement(event.target)) return;

      const key = event.key;
      const ctrl = event.ctrlKey || event.metaKey;
      const shift = event.shiftKey;
      const alt = event.altKey;

      // Playback controls
      if (key === ' ' && !ctrl && !shift && !alt && config.onPlayPause) {
        event.preventDefault();
        config.onPlayPause();
        return;
      }
      if (key === 'ArrowRight' && !shift && !ctrl && !alt && config.onNext) {
        event.preventDefault();
        config.onNext();
        return;
      }
      if (key === 'ArrowLeft' && !shift && !ctrl && !alt && config.onPrevious) {
        event.preventDefault();
        config.onPrevious();
        return;
      }
      if (key === 'ArrowRight' && shift && !ctrl && !alt && config.onSeekForward) {
        event.preventDefault();
        config.onSeekForward();
        return;
      }
      if (key === 'ArrowLeft' && shift && !ctrl && !alt && config.onSeekBackward) {
        event.preventDefault();
        config.onSeekBackward();
        return;
      }
      if (key === 'ArrowUp' && !shift && !ctrl && !alt && config.onVolumeUp) {
        event.preventDefault();
        config.onVolumeUp();
        return;
      }
      if (key === 'ArrowDown' && !shift && !ctrl && !alt && config.onVolumeDown) {
        event.preventDefault();
        config.onVolumeDown();
        return;
      }
      if (key === 'm' && !shift && !ctrl && !alt && config.onMute) {
        event.preventDefault();
        config.onMute();
        return;
      }

      // Navigation
      if (key === '1' && !shift && !ctrl && !alt && config.onShowSongs) {
        event.preventDefault();
        config.onShowSongs();
        return;
      }
      if (key === '2' && !shift && !ctrl && !alt && config.onShowAlbums) {
        event.preventDefault();
        config.onShowAlbums();
        return;
      }
      if (key === '3' && !shift && !ctrl && !alt && config.onShowArtists) {
        event.preventDefault();
        config.onShowArtists();
        return;
      }
      if (key === '4' && !shift && !ctrl && !alt && config.onShowPlaylists) {
        event.preventDefault();
        config.onShowPlaylists();
        return;
      }
      if (key === '/' && !shift && !ctrl && !alt && config.onFocusSearch) {
        event.preventDefault();
        config.onFocusSearch();
        return;
      }
      if (key === 'Escape' && !shift && !ctrl && !alt && config.onEscape) {
        event.preventDefault();
        config.onEscape();
        return;
      }

      // Library actions
      if (key === 'Enter' && !shift && !ctrl && !alt && config.onPlaySelected) {
        event.preventDefault();
        config.onPlaySelected();
        return;
      }
      if (key === 'l' && !shift && !ctrl && !alt && config.onToggleFavorite) {
        event.preventDefault();
        config.onToggleFavorite();
        return;
      }
      if (key === 'p' && !shift && !ctrl && !alt && config.onAddToPlaylist) {
        event.preventDefault();
        config.onAddToPlaylist();
        return;
      }
      if (key === 'q' && !shift && !ctrl && !alt && config.onAddToQueue) {
        event.preventDefault();
        config.onAddToQueue();
        return;
      }
      if (key === 'i' && !shift && !ctrl && !alt && config.onShowInfo) {
        event.preventDefault();
        config.onShowInfo();
        return;
      }
      if (key === 'Delete' && !shift && !ctrl && !alt && config.onDelete) {
        event.preventDefault();
        config.onDelete();
        return;
      }

      // Queue management
      if (key === 'c' && ctrl && shift && !alt && config.onClearQueue) {
        event.preventDefault();
        config.onClearQueue();
        return;
      }
      if (key === 's' && ctrl && shift && !alt && config.onShuffleQueue) {
        event.preventDefault();
        config.onShuffleQueue();
        return;
      }

      // Global
      if (key === '?' && !ctrl && !alt && config.onShowHelp) {
        event.preventDefault();
        config.onShowHelp();
        return;
      }
      if (key === ',' && ctrl && !shift && !alt && config.onOpenSettings) {
        event.preventDefault();
        config.onOpenSettings();
        return;
      }
    },
    [isEnabled, config]
  );

  // Register global keyboard listener
  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Build shortcuts array for display only (not used for handling)
  const shortcuts: KeyboardShortcut[] = [];
  if (config.onPlayPause) shortcuts.push({ key: ' ', description: 'Play/Pause', category: 'Playback', handler: config.onPlayPause });
  if (config.onNext) shortcuts.push({ key: 'ArrowRight', description: 'Next track', category: 'Playback', handler: config.onNext });
  if (config.onPrevious) shortcuts.push({ key: 'ArrowLeft', description: 'Previous track', category: 'Playback', handler: config.onPrevious });
  if (config.onVolumeUp) shortcuts.push({ key: 'ArrowUp', description: 'Volume up', category: 'Playback', handler: config.onVolumeUp });
  if (config.onVolumeDown) shortcuts.push({ key: 'ArrowDown', description: 'Volume down', category: 'Playback', handler: config.onVolumeDown });
  if (config.onMute) shortcuts.push({ key: 'm', description: 'Mute/Unmute', category: 'Playback', handler: config.onMute });
  if (config.onShowSongs) shortcuts.push({ key: '1', description: 'Show Songs', category: 'Navigation', handler: config.onShowSongs });
  if (config.onShowAlbums) shortcuts.push({ key: '2', description: 'Show Albums', category: 'Navigation', handler: config.onShowAlbums });
  if (config.onShowArtists) shortcuts.push({ key: '3', description: 'Show Artists', category: 'Navigation', handler: config.onShowArtists });
  if (config.onShowPlaylists) shortcuts.push({ key: '4', description: 'Show Playlists', category: 'Navigation', handler: config.onShowPlaylists });
  if (config.onFocusSearch) shortcuts.push({ key: '/', description: 'Focus search', category: 'Navigation', handler: config.onFocusSearch });
  if (config.onEscape) shortcuts.push({ key: 'Escape', description: 'Clear search / Close dialogs', category: 'Navigation', handler: config.onEscape });
  if (config.onShowHelp) shortcuts.push({ key: '?', description: 'Show keyboard shortcuts', category: 'Global', handler: config.onShowHelp });
  if (config.onOpenSettings) shortcuts.push({ key: ',', ctrl: true, description: 'Open settings', category: 'Global', handler: config.onOpenSettings });

  const openHelp = useCallback(() => setIsHelpOpen(true), []);
  const closeHelp = useCallback(() => setIsHelpOpen(false), []);
  const enable = useCallback(() => setIsEnabled(true), []);
  const disable = useCallback(() => setIsEnabled(false), []);

  return {
    shortcuts,
    isHelpOpen,
    openHelp,
    closeHelp,
    enable,
    disable,
    isEnabled,
  };
};
