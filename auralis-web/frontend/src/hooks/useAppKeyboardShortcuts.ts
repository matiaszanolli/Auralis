import { useEffect } from 'react';
import { useKeyboardShortcuts, KeyboardShortcut } from './useKeyboardShortcuts';

/**
 * Configuration object for keyboard shortcuts handlers.
 * All handlers are optional callbacks that should be passed from the parent component.
 */
export interface AppKeyboardShortcutsConfig {
  // Playback controls
  onPlayPause?: () => void;
  onNextTrack?: () => void;
  onPreviousTrack?: () => void;
  onVolumeUp?: () => void;
  onVolumeDown?: () => void;
  onMute?: () => void;

  // Navigation
  onViewSongs?: () => void;
  onViewAlbums?: () => void;
  onViewArtists?: () => void;
  onViewPlaylists?: () => void;
  onSearchFocus?: () => void;
  onSearchClear?: () => void;

  // Global
  onSettingsOpen?: () => void;
  onHelpOpen?: () => void;
}

/**
 * Custom hook to set up keyboard shortcuts for the Auralis player.
 * Manages all keyboard bindings and provides handlers for help dialog.
 *
 * Shortcuts include:
 * - Playback: Space (play/pause), Arrow keys (next/prev/volume), M (mute)
 * - Navigation: 1-4 (view selection), / (search focus)
 * - Global: ? (help), Ctrl+, (settings), Escape (clear/close)
 *
 * @param config Configuration object with callback handlers
 * @returns Object containing shortcuts array and help dialog state
 *
 * @example
 * const shortcuts = useAppKeyboardShortcuts({
 *   onPlayPause: () => setIsPlaying(!isPlaying),
 *   onNextTrack: () => playNextTrack(),
 *   onSettingsOpen: () => setSettingsOpen(true),
 * });
 *
 * return (
 *   <>
 *     <KeyboardShortcutsHelp
 *       open={shortcuts.isHelpOpen}
 *       shortcuts={shortcuts.shortcuts}
 *       onClose={shortcuts.closeHelp}
 *     />
 *   </>
 * );
 */
export const useAppKeyboardShortcuts = (config: AppKeyboardShortcutsConfig) => {
  // Define all keyboard shortcuts
  const keyboardShortcutsArray: KeyboardShortcut[] = [
    // ============================================
    // PLAYBACK CONTROLS
    // ============================================
    {
      key: ' ',
      description: 'Play/Pause',
      category: 'Playback',
      handler: () => config.onPlayPause?.(),
    },
    {
      key: 'ArrowRight',
      description: 'Next track',
      category: 'Playback',
      handler: () => config.onNextTrack?.(),
    },
    {
      key: 'ArrowLeft',
      description: 'Previous track',
      category: 'Playback',
      handler: () => config.onPreviousTrack?.(),
    },
    {
      key: 'ArrowUp',
      description: 'Volume up',
      category: 'Playback',
      handler: () => config.onVolumeUp?.(),
    },
    {
      key: 'ArrowDown',
      description: 'Volume down',
      category: 'Playback',
      handler: () => config.onVolumeDown?.(),
    },
    {
      key: 'm',
      description: 'Mute/Unmute',
      category: 'Playback',
      handler: () => config.onMute?.(),
    },

    // ============================================
    // NAVIGATION
    // ============================================
    {
      key: '1',
      description: 'Show Songs',
      category: 'Navigation',
      handler: () => config.onViewSongs?.(),
    },
    {
      key: '2',
      description: 'Show Albums',
      category: 'Navigation',
      handler: () => config.onViewAlbums?.(),
    },
    {
      key: '3',
      description: 'Show Artists',
      category: 'Navigation',
      handler: () => config.onViewArtists?.(),
    },
    {
      key: '4',
      description: 'Show Playlists',
      category: 'Navigation',
      handler: () => config.onViewPlaylists?.(),
    },
    {
      key: '/',
      description: 'Focus search',
      category: 'Navigation',
      handler: () => config.onSearchFocus?.(),
    },
    {
      key: 'Escape',
      description: 'Clear search / Close dialogs',
      category: 'Navigation',
      handler: () => config.onSearchClear?.(),
    },

    // ============================================
    // GLOBAL SHORTCUTS
    // ============================================
    {
      key: '?',
      description: 'Show keyboard shortcuts',
      category: 'Global',
      handler: () => {
        // Will be set dynamically below via openHelp
      },
    },
    {
      key: ',',
      ctrl: true,
      description: 'Open settings',
      category: 'Global',
      handler: () => config.onSettingsOpen?.(),
    },
  ];

  // Initialize the keyboard shortcuts hook
  const {
    shortcuts,
    isHelpOpen,
    openHelp,
    closeHelp,
    formatShortcut,
  } = useKeyboardShortcuts(keyboardShortcutsArray);

  // Set the help shortcut handler after hook initialization
  // This is needed because we need the openHelp function from the hook
  useEffect(() => {
    const helpShortcut = keyboardShortcutsArray.find((s) => s.key === '?');
    if (helpShortcut) {
      helpShortcut.handler = openHelp;
    }
  }, [openHelp]);

  return {
    shortcuts,
    isHelpOpen,
    openHelp,
    closeHelp,
    formatShortcut,
  };
};
