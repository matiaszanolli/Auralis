import { useKeyboardShortcuts, KeyboardShortcutsConfig, UseKeyboardShortcutsReturn } from './useKeyboardShortcuts';

/**
 * Configuration object for keyboard shortcuts handlers.
 * All handlers are optional callbacks that should be passed from the parent component.
 *
 * @deprecated Use KeyboardShortcutsConfig directly from useKeyboardShortcuts instead.
 * This interface provides backward compatibility but maps to the unified config internally.
 *
 * Migration guide:
 * - onNextTrack → onNext
 * - onPreviousTrack → onPrevious
 * - onViewSongs → onShowSongs
 * - onViewAlbums → onShowAlbums
 * - onViewArtists → onShowArtists
 * - onViewPlaylists → onShowPlaylists
 * - onSearchFocus → onFocusSearch
 * - onSearchClear → onEscape
 * - onSettingsOpen → onOpenSettings
 * - onHelpOpen → onShowHelp
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
 * Adapter function that converts AppKeyboardShortcutsConfig to unified KeyboardShortcutsConfig.
 *
 * This eliminates ~160 lines of duplicate shortcut definition code by mapping
 * the legacy config field names to the unified config interface.
 *
 * @param config Legacy app shortcuts config
 * @returns Unified keyboard shortcuts config
 */
const adaptConfigToUnified = (config: AppKeyboardShortcutsConfig): KeyboardShortcutsConfig => ({
  // Playback controls (same names)
  onPlayPause: config.onPlayPause,
  onVolumeUp: config.onVolumeUp,
  onVolumeDown: config.onVolumeDown,
  onMute: config.onMute,

  // Playback controls (renamed)
  onNext: config.onNextTrack,
  onPrevious: config.onPreviousTrack,

  // Navigation (renamed)
  onShowSongs: config.onViewSongs,
  onShowAlbums: config.onViewAlbums,
  onShowArtists: config.onViewArtists,
  onShowPlaylists: config.onViewPlaylists,
  onFocusSearch: config.onSearchFocus,
  onEscape: config.onSearchClear,

  // Global (renamed)
  onOpenSettings: config.onSettingsOpen,
  onShowHelp: config.onHelpOpen,
});

/**
 * Custom hook to set up keyboard shortcuts for the Auralis player.
 * Manages all keyboard bindings and provides handlers for help dialog.
 *
 * **Refactored (Phase 3a+)**: This hook now delegates to the unified `useKeyboardShortcuts`
 * hook via an adapter pattern, eliminating ~160 lines of duplicate shortcut definitions.
 * The legacy config interface is maintained for backward compatibility but maps to the
 * unified config internally.
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
 *
 * @see useKeyboardShortcuts For the unified implementation
 * @see KeyboardShortcutsConfig For the canonical config interface
 */
export const useAppKeyboardShortcuts = (config: AppKeyboardShortcutsConfig): UseKeyboardShortcutsReturn => {
  // Adapt legacy config to unified config format
  const unifiedConfig = adaptConfigToUnified(config);

  // Delegate to unified keyboard shortcuts hook
  // This eliminates ~160 lines of duplicate shortcut definitions
  return useKeyboardShortcuts(unifiedConfig);
};
