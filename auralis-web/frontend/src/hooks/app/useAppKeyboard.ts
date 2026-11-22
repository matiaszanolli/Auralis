import { useCallback, useRef } from 'react';
import { useStore } from 'react-redux';
import { usePlaybackControls } from '@/contexts/PlaybackSessionContext';
import { selectVolume } from '@/store/slices/playerSlice';
import type { RootState } from '@/store';
import { useAppShortcuts } from './useAppShortcuts';
import { useKeyboardShortcuts } from './useKeyboardShortcuts';

interface AppKeyboardArgs {
  info: (message: string) => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  settingsOpen: boolean;
  setSettingsOpen: (open: boolean) => void;
  setCurrentView: (view: string) => void;
}

/**
 * Binds the global keyboard shortcuts to the playback session and the shell's
 * state, and returns the help-dialog surface (#6703). The shortcut table
 * itself is useAppShortcuts (#5631).
 */
export function useAppKeyboard(args: AppKeyboardArgs) {
  // The volume shortcuts' +/-10 step reads the store at keypress time instead of subscribing:
  // a subscription re-rendered the whole shell on every slider input event (#6067).
  const store = useStore<RootState>();
  const getVolume = useCallback(() => selectVolume(store.getState()), [store]);

  // #4541: global shortcuts must operate on the SAME enhanced-audio session
  // Player.tsx drives, not a disconnected legacy control plane — sending
  // 'play_normal' (the old usePlaybackControl.play()) cancelled the user's
  // own in-flight enhanced stream server-side with no visible error.
  const session = usePlaybackControls();
  const setVolume = useCallback(
    // handleVolumeChange expects 0.0-1.0 — clamp + scale the 0-100 value
    // used by the keyboard-shortcut UI.
    (newVolume: number) =>
      session.handleVolumeChange(Math.max(0, Math.min(100, newVolume)) / 100),
    [session]
  );

  // Ref to break circular dependency: the shortcut array references openHelp,
  // but openHelp comes from the hook that receives the array (fixes #3077).
  const openHelpRef = useRef<(() => void) | null>(null);

  const shortcutTable = useAppShortcuts({
    ...args,
    session,
    togglePlayPause: session.handlePlayPause,
    isPlaying: session.isPlaybackActive && !session.isPaused,
    nextTrack: session.handleNext,
    previousTrack: session.handlePrevious,
    getVolume,
    setVolume,
    openHelpRef,
  });

  const keyboard = useKeyboardShortcuts(shortcutTable);
  // Keep ref in sync with latest openHelp
  openHelpRef.current = keyboard.openHelp;
  return keyboard;
}
