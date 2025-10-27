/**
 * Keyboard Shortcuts Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Provides global keyboard shortcuts for player controls and navigation.
 *
 * Supported shortcuts:
 * - Space: Play/Pause
 * - →: Next track
 * - ←: Previous track
 * - /: Focus search
 * - L: Toggle lyrics
 * - M: Toggle enhancement
 * - 1-5: Switch presets
 * - Cmd/Ctrl + ,: Settings
 * - Cmd/Ctrl + K: Quick search
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3
 */

import { useEffect, useCallback } from 'react';

export interface KeyboardShortcutHandlers {
  onPlayPause?: () => void;
  onNext?: () => void;
  onPrevious?: () => void;
  onVolumeUp?: () => void;
  onVolumeDown?: () => void;
  onMute?: () => void;
  onToggleLyrics?: () => void;
  onToggleEnhancement?: () => void;
  onFocusSearch?: () => void;
  onOpenSettings?: () => void;
  onPresetChange?: (preset: string) => void;
}

const PRESET_MAP: Record<string, string> = {
  '1': 'adaptive',
  '2': 'gentle',
  '3': 'warm',
  '4': 'bright',
  '5': 'punchy'
};

/**
 * Hook for global keyboard shortcuts
 */
export const useKeyboardShortcuts = (handlers: KeyboardShortcutHandlers) => {
  const handleKeyPress = useCallback((event: KeyboardEvent) => {
    // Don't trigger shortcuts when typing in input fields
    const target = event.target as HTMLElement;
    const isInputField =
      target.tagName === 'INPUT' ||
      target.tagName === 'TEXTAREA' ||
      target.contentEditable === 'true';

    // Allow '/' to focus search even from input fields (like GitHub)
    if (event.key === '/' && !event.metaKey && !event.ctrlKey) {
      if (!isInputField || target.id === 'global-search') {
        event.preventDefault();
        handlers.onFocusSearch?.();
        return;
      }
    }

    // Don't handle other shortcuts in input fields
    if (isInputField && event.key !== '/') {
      return;
    }

    const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
    const modifierKey = isMac ? event.metaKey : event.ctrlKey;

    // Cmd/Ctrl + K: Quick search
    if ((event.key === 'k' || event.key === 'K') && modifierKey) {
      event.preventDefault();
      handlers.onFocusSearch?.();
      return;
    }

    // Cmd/Ctrl + ,: Settings
    if (event.key === ',' && modifierKey) {
      event.preventDefault();
      handlers.onOpenSettings?.();
      return;
    }

    // Space: Play/Pause (only if no modifier keys)
    if (event.code === 'Space' && !modifierKey && !event.shiftKey && !event.altKey) {
      event.preventDefault();
      handlers.onPlayPause?.();
      return;
    }

    // Arrow keys: Previous/Next track
    if (event.key === 'ArrowRight' && !modifierKey) {
      event.preventDefault();
      handlers.onNext?.();
      return;
    }

    if (event.key === 'ArrowLeft' && !modifierKey) {
      event.preventDefault();
      handlers.onPrevious?.();
      return;
    }

    // Arrow keys with Shift: Volume control
    if (event.key === 'ArrowUp' && event.shiftKey && !modifierKey) {
      event.preventDefault();
      handlers.onVolumeUp?.();
      return;
    }

    if (event.key === 'ArrowDown' && event.shiftKey && !modifierKey) {
      event.preventDefault();
      handlers.onVolumeDown?.();
      return;
    }

    // M: Toggle enhancement
    if ((event.key === 'm' || event.key === 'M') && !modifierKey) {
      event.preventDefault();
      handlers.onToggleEnhancement?.();
      return;
    }

    // L: Toggle lyrics
    if ((event.key === 'l' || event.key === 'L') && !modifierKey) {
      event.preventDefault();
      handlers.onToggleLyrics?.();
      return;
    }

    // Number keys 1-5: Preset selection
    if (event.key >= '1' && event.key <= '5' && !modifierKey) {
      event.preventDefault();
      const preset = PRESET_MAP[event.key];
      if (preset) {
        handlers.onPresetChange?.(preset);
      }
      return;
    }

    // 0 or M: Mute/unmute
    if ((event.key === '0' || (event.key === 'm' && modifierKey))) {
      event.preventDefault();
      handlers.onMute?.();
      return;
    }

  }, [handlers]);

  useEffect(() => {
    // Add event listener
    document.addEventListener('keydown', handleKeyPress);

    // Cleanup
    return () => {
      document.removeEventListener('keydown', handleKeyPress);
    };
  }, [handleKeyPress]);
};

/**
 * Get keyboard shortcut display string for current platform
 */
export const getShortcutString = (shortcut: string): string => {
  const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
  const modifierKey = isMac ? '⌘' : 'Ctrl';

  return shortcut
    .replace('Cmd', modifierKey)
    .replace('Ctrl', modifierKey);
};

/**
 * List of all available shortcuts for help/settings display
 */
export const KEYBOARD_SHORTCUTS = [
  { key: 'Space', action: 'Play/Pause', category: 'Playback' },
  { key: '→', action: 'Next track', category: 'Playback' },
  { key: '←', action: 'Previous track', category: 'Playback' },
  { key: 'Shift + ↑', action: 'Volume up', category: 'Playback' },
  { key: 'Shift + ↓', action: 'Volume down', category: 'Playback' },
  { key: '0', action: 'Mute/Unmute', category: 'Playback' },
  { key: '/', action: 'Focus search', category: 'Navigation' },
  { key: 'Cmd/Ctrl + K', action: 'Quick search', category: 'Navigation' },
  { key: 'Cmd/Ctrl + ,', action: 'Open settings', category: 'Navigation' },
  { key: 'M', action: 'Toggle enhancement', category: 'Processing' },
  { key: 'L', action: 'Toggle lyrics', category: 'Display' },
  { key: '1', action: 'Adaptive preset', category: 'Presets' },
  { key: '2', action: 'Gentle preset', category: 'Presets' },
  { key: '3', action: 'Warm preset', category: 'Presets' },
  { key: '4', action: 'Bright preset', category: 'Presets' },
  { key: '5', action: 'Punchy preset', category: 'Presets' }
];
