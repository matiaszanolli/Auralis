/**
 * useAppShortcuts
 * ~~~~~~~~~~~~~~~
 *
 * ComfortableApp's global keyboard-shortcut table, extracted verbatim from
 * the app shell (#5631) — the ~150-line inline table was the bulk of that
 * file's 437 lines. The handlers close over the app-shell state passed in;
 * nothing about the key set, gating (isCommandPending) or toast behaviour
 * changed. Adding a shortcut here does NOT add it to any tooltip — keep
 * advertised hints and real handlers in lockstep (#5632).
 */

import { useMemo, type RefObject } from 'react';
import { KeyboardShortcut } from '@/hooks/app/useKeyboardShortcuts';

interface UseAppShortcutsArgs {
  /** Playback session slice (from usePlaybackControls). */
  session: {
    isCommandPending: boolean;
    handleMuteToggle: () => Promise<boolean>;
  };
  togglePlayPause: () => void;
  isPlaying: boolean;
  nextTrack: () => void;
  previousTrack: () => void;
  volume: number;
  setVolume: (newVolume: number) => void;
  /** Toast notifier (the shortcuts announce what they did). */
  info: (message: string) => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  settingsOpen: boolean;
  setSettingsOpen: (open: boolean) => void;
  setCurrentView: (view: string) => void;
  /**
   * Ref to the help-dialog opener, breaking the array↔hook circular
   * dependency (#3077): the '?' handler runs after the hook that receives
   * this array has produced openHelp.
   */
  openHelpRef: RefObject<(() => void) | null>;
}

export function useAppShortcuts({
  session,
  togglePlayPause,
  isPlaying,
  nextTrack,
  previousTrack,
  volume,
  setVolume,
  info,
  searchQuery,
  setSearchQuery,
  settingsOpen,
  setSettingsOpen,
  setCurrentView,
  openHelpRef,
}: UseAppShortcutsArgs): KeyboardShortcut[] {
  return useMemo(() => [
    // Playback controls
    {
      key: ' ',
      description: 'Play/Pause',
      category: 'Playback',
      handler: () => {
        // #5008: runTransportCommand's shared commandPendingRef silently
        // drops this command if a different transport command (Next/
        // Previous/Play-Pause) is still in flight — checking isCommandPending
        // here stops the confirmation toast from firing on a dropped command
        // the mouse-path buttons already refuse via the same flag.
        if (session.isCommandPending) return;
        togglePlayPause();
        info(isPlaying ? 'Paused' : 'Playing');
      }
    },
    {
      key: 'ArrowRight',
      description: 'Next track',
      category: 'Playback',
      handler: () => {
        if (session.isCommandPending) return;
        nextTrack();
        info('Next track');
      }
    },
    {
      key: 'ArrowLeft',
      description: 'Previous track',
      category: 'Playback',
      handler: () => {
        if (session.isCommandPending) return;
        previousTrack();
        info('Previous track');
      }
    },
    {
      key: 'ArrowUp',
      description: 'Volume up',
      category: 'Playback',
      handler: () => {
        const newVolume = Math.min(volume + 10, 100);
        setVolume(newVolume);
        info(`Volume: ${newVolume}%`);
      }
    },
    {
      key: 'ArrowDown',
      description: 'Volume down',
      category: 'Playback',
      handler: () => {
        const newVolume = Math.max(volume - 10, 0);
        setVolume(newVolume);
        info(`Volume: ${newVolume}%`);
      }
    },
    {
      key: 'm',
      description: 'Mute/Unmute',
      category: 'Playback',
      handler: () => {
        // Shares Player.tsx's mute/unmute semantics (restore pre-mute volume
        // rather than a hardcoded 80%) so both surfaces agree (#4541).
        session.handleMuteToggle().then((nowMuted) => {
          info(nowMuted ? 'Muted' : 'Unmuted');
        });
      }
    },
    // Navigation shortcuts
    {
      key: '1',
      description: 'Show Songs',
      category: 'Navigation',
      handler: () => {
        setCurrentView('songs');
        info('Songs view');
      }
    },
    {
      key: '2',
      description: 'Show Albums',
      category: 'Navigation',
      handler: () => {
        setCurrentView('albums');
        info('Albums view');
      }
    },
    {
      key: '3',
      description: 'Show Artists',
      category: 'Navigation',
      handler: () => {
        setCurrentView('artists');
        info('Artists view');
      }
    },
    // No '4' shortcut: it set currentView='playlists', a view that does not
    // exist — CozyLibraryView rendered the entire unfiltered library under a
    // "Playlists" heading (#5620). Playlists live in the sidebar's
    // PlaylistList; picking one routes to the playlist-N view.
    {
      key: '/',
      description: 'Focus search',
      category: 'Navigation',
      handler: () => {
        // data-search-input is set on the top-bar search field (#5662);
        // the previous placeholder-substring lookup broke whenever the
        // placeholder copy changed.
        const searchInput = document.querySelector<HTMLInputElement>('input[data-search-input]');
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
      }
    },
    {
      key: 'Escape',
      description: 'Clear search / Close dialogs',
      category: 'Navigation',
      handler: () => {
        if (searchQuery) {
          setSearchQuery('');
          info('Search cleared');
        } else if (settingsOpen) {
          setSettingsOpen(false);
        }
      }
    },
    // Global shortcuts
    {
      key: '?',
      description: 'Show keyboard shortcuts',
      category: 'Global',
      handler: () => {
        openHelpRef.current?.();
      }
    },
    {
      key: ',',
      ctrl: true,
      description: 'Open settings',
      category: 'Global',
      handler: () => {
        setSettingsOpen(true);
      }
    }
  ], [session, togglePlayPause, isPlaying, nextTrack, previousTrack, volume, setVolume,
      searchQuery, setSearchQuery, settingsOpen, setSettingsOpen, setCurrentView, info, openHelpRef]);
}

export default useAppShortcuts;
