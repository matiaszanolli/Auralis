/**
 * PlaybackControlsContext / PlaybackProgressContext — split contexts backing
 * the single shared enhanced-audio streaming session
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * #5006: `PlaybackSessionContext` used to expose one `useMemo`'d value
 * bundling the 10Hz `currentTime` field together with low-frequency
 * handlers/booleans. React context has no partial subscription, so every
 * `usePlaybackSession()` consumer re-rendered on every 10Hz tick — including
 * `ComfortableApp` (the app root, wrapping the sidebar/top bar/library view)
 * and the detail-view consumers (`usePlayTrack`, `usePlaylistContextActions`),
 * none of which read `currentTime` at all.
 *
 * Split into two contexts so a consumer only re-renders on the frequency
 * class it actually subscribes to:
 * - `PlaybackControlsContext` — handlers, connection/command state. Changes
 *   only on user action or stream-lifecycle transitions (idle/buffering/
 *   streaming/complete/error), not per tick.
 * - `PlaybackProgressContext` — `currentTime`/`processedChunks`/`totalChunks`.
 *   Changes up to 10x/second while playing. Only `Player`/`ProgressBar`
 *   render playback position, so only `Player.tsx` subscribes to this.
 *
 * Both are provided together by the single `PlaybackSessionProvider` in
 * `./PlaybackSessionContext` — there is still exactly one `usePlayEnhanced()`
 * call site (#4541's invariant), just two narrower views onto its state.
 *
 * @module contexts/playbackSessionContexts
 */

import { createContext, useContext } from 'react';

export interface PlaybackControlsContextValue {
  /** True while a chunk is streaming or buffering. */
  isStreaming: boolean;
  /** Streaming state machine (idle, buffering, streaming, error, complete). */
  streamingState: 'idle' | 'buffering' | 'streaming' | 'error' | 'complete';
  isPaused: boolean;
  isSeeking: boolean;
  /** True while a transport command is waiting for its playback request. */
  isCommandPending: boolean;
  error: string | null;

  /** Start a track using the current enhancement enabled/preset/intensity state. */
  startTrack: (trackId: number) => Promise<void>;

  /** Seek to a position (seconds) in the current track. */
  handleSeek: (position: number) => void;
  /** Play/pause/resume the current track — the single entry point for both
   *  the transport bar and the Space shortcut. */
  handlePlayPause: () => Promise<void>;
  /** Stop current playback and play the next queue track. */
  handleNext: () => Promise<void>;
  /** Stop current playback and play the previous queue track. */
  handlePrevious: () => Promise<void>;
  /** Set the live playback volume (0-1) and persist it to Redux. */
  handleVolumeChange: (volume: number) => Promise<void>;
  /** Toggle mute, restoring the pre-mute volume on unmute. Returns the
   *  resulting muted state so callers can report it (e.g. a toast). */
  handleMuteToggle: () => Promise<boolean>;
}

export interface PlaybackProgressContextValue {
  processedChunks: number;
  totalChunks: number;
  /** Current playback position (seconds) reported by the streaming engine. */
  currentTime: number;
}

export const PlaybackControlsContext = createContext<PlaybackControlsContextValue | null>(null);
export const PlaybackProgressContext = createContext<PlaybackProgressContextValue | null>(null);

/** Low-frequency playback state and transport handlers. Safe for components
 *  that don't render live playback position (sidebar, top bar, library
 *  views) — does not re-render on the 10Hz position tick. */
export function usePlaybackControls(): PlaybackControlsContextValue {
  const ctx = useContext(PlaybackControlsContext);
  if (!ctx) {
    throw new Error('usePlaybackControls must be used within a PlaybackSessionProvider');
  }
  return ctx;
}

/** High-frequency playback position, updated up to 10x/second while
 *  playing. Only subscribe from components that actually render playback
 *  position (`Player`, `ProgressBar`) — every subscriber re-renders on
 *  every tick. */
export function usePlaybackProgress(): PlaybackProgressContextValue {
  const ctx = useContext(PlaybackProgressContext);
  if (!ctx) {
    throw new Error('usePlaybackProgress must be used within a PlaybackSessionProvider');
  }
  return ctx;
}
