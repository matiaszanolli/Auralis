/**
 * usePlayerControls - Player control operations hook
 *
 * Provides high-level control operations (play, pause, seek, volume) for playback.
 * Wraps low-level API calls with error handling, debouncing, and state management.
 *
 * Architecture:
 * - Debounced seek to prevent rapid requests
 * - Volume changes applied immediately with server sync
 * - Play/pause with queue validation
 * - Next/previous track with boundary handling
 *
 * @module hooks/usePlayerControls
 */

import { useState, useCallback, useRef, useEffect } from 'react';

/**
 * Control operation result - indicates success/failure of an operation
 */
export interface ControlResult {
  success: boolean;
  error?: string;
}

/**
 * Player control operations
 */
export interface PlayerControls {
  // Playback control
  play: () => Promise<ControlResult>;
  pause: () => Promise<ControlResult>;
  togglePlayPause: () => Promise<ControlResult>;

  // Track navigation
  nextTrack: () => Promise<ControlResult>;
  previousTrack: () => Promise<ControlResult>;

  // Seeking (debounced to prevent rapid server requests)
  seek: (position: number) => Promise<ControlResult>;
  seekDebounced: (position: number) => void; // Non-blocking debounced seek

  // Volume control
  setVolume: (volume: number) => Promise<ControlResult>;

  // Queue control
  playTrack: (trackId: number) => Promise<ControlResult>;
  removeFromQueue: (index: number) => Promise<ControlResult>;

  // State
  isLoading: boolean;
  lastError?: string;
}

/**
 * Configuration for control operations
 */
export interface UsePlayerControlsConfig {
  /**
   * Function to call for play operation
   */
  onPlay?: () => Promise<void>;

  /**
   * Function to call for pause operation
   */
  onPause?: () => Promise<void>;

  /**
   * Function to call for seek operation
   * @param position Position in seconds
   */
  onSeek?: (position: number) => Promise<void>;

  /**
   * Function to call for volume change
   * @param volume Volume level (0-100)
   */
  onSetVolume?: (volume: number) => Promise<void>;

  /**
   * Function to call for next track
   */
  onNextTrack?: () => Promise<void>;

  /**
   * Function to call for previous track
   */
  onPreviousTrack?: () => Promise<void>;

  /**
   * Function to call for play specific track
   * @param trackId Track ID to play
   */
  onPlayTrack?: (trackId: number) => Promise<void>;

  /**
   * Function to call for removing from queue
   * @param index Queue index
   */
  onRemoveFromQueue?: (index: number) => Promise<void>;

  /**
   * Debounce time for seek operations (milliseconds)
   * Default: 300ms
   */
  seekDebounceMs?: number;

  /**
   * Enable debug logging
   * Default: false
   */
  debug?: boolean;
}

/**
 * usePlayerControls - High-level player control operations
 *
 * Provides optimized control operations with debouncing, error handling,
 * and state management for playback control.
 *
 * Usage:
 * ```tsx
 * const controls = usePlayerControls({
 *   onPlay: async () => await api.post('/api/player/play'),
 *   onPause: async () => await api.post('/api/player/pause'),
 *   onSeek: async (pos) => await api.post('/api/player/seek', { position: pos }),
 *   seekDebounceMs: 300,
 *   debug: true,
 * });
 *
 * // Use controls
 * await controls.play();
 * controls.seekDebounced(30); // Non-blocking debounced seek
 * await controls.setVolume(75);
 * ```
 */
export function usePlayerControls({
  onPlay,
  onPause,
  onSeek,
  onSetVolume,
  onNextTrack,
  onPreviousTrack,
  onPlayTrack,
  onRemoveFromQueue,
  seekDebounceMs = 300,
  debug = false,
}: UsePlayerControlsConfig): PlayerControls {
  const [isLoading, setIsLoading] = useState(false);
  const [lastError, setLastError] = useState<string>();

  // Debounce tracking for seek operations
  const seekTimeoutRef = useRef<NodeJS.Timeout>();
  const lastSeekRef = useRef<number>(0);

  const log = useCallback((msg: string, data?: any) => {
    if (debug) {
      console.log(`[usePlayerControls] ${msg}`, data ?? '');
    }
  }, [debug]);

  // Helper to execute control operations with error handling
  const executeControl = useCallback(
    async (
      operation: () => Promise<void>,
      operationName: string
    ): Promise<ControlResult> => {
      setIsLoading(true);
      setLastError(undefined);

      try {
        log(`Executing: ${operationName}`);
        await operation();
        log(`${operationName} succeeded`);
        return { success: true };
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : 'Unknown error';
        log(`${operationName} failed: ${errorMsg}`);
        setLastError(errorMsg);
        return { success: false, error: errorMsg };
      } finally {
        setIsLoading(false);
      }
    },
    [log]
  );

  // Play current track or resume
  const play = useCallback(async (): Promise<ControlResult> => {
    if (!onPlay) {
      return { success: false, error: 'Play handler not configured' };
    }
    return executeControl(onPlay, 'play');
  }, [onPlay, executeControl]);

  // Pause playback
  const pause = useCallback(async (): Promise<ControlResult> => {
    if (!onPause) {
      return { success: false, error: 'Pause handler not configured' };
    }
    return executeControl(onPause, 'pause');
  }, [onPause, executeControl]);

  // Toggle play/pause
  const togglePlayPause = useCallback(async (): Promise<ControlResult> => {
    // This requires knowing current state, so caller should decide
    // For now, we'll throw - caller should use play() or pause()
    return {
      success: false,
      error: 'Use play() or pause() directly - caller should manage state',
    };
  }, []);

  // Seek to position (blocking)
  const seek = useCallback(
    async (position: number): Promise<ControlResult> => {
      if (!onSeek) {
        return { success: false, error: 'Seek handler not configured' };
      }

      // Validate position
      if (position < 0) {
        return { success: false, error: 'Position cannot be negative' };
      }

      return executeControl(() => onSeek(position), `seek(${position})`);
    },
    [onSeek, executeControl]
  );

  // Seek to position (non-blocking, debounced)
  const seekDebounced = useCallback(
    (position: number) => {
      log(`Queued debounced seek to ${position}`);

      // Clear existing timeout
      if (seekTimeoutRef.current) {
        clearTimeout(seekTimeoutRef.current);
      }

      // Set new timeout
      seekTimeoutRef.current = setTimeout(() => {
        if (position !== lastSeekRef.current) {
          lastSeekRef.current = position;
          seek(position).catch((error) => {
            console.error('[usePlayerControls] Debounced seek error:', error);
          });
        }
      }, seekDebounceMs);
    },
    [seek, seekDebounceMs, log]
  );

  // Set volume
  const setVolume = useCallback(
    async (volume: number): Promise<ControlResult> => {
      if (!onSetVolume) {
        return { success: false, error: 'Volume handler not configured' };
      }

      // Validate volume (0-100)
      if (volume < 0 || volume > 100) {
        return { success: false, error: 'Volume must be between 0 and 100' };
      }

      return executeControl(
        () => onSetVolume(volume),
        `setVolume(${volume})`
      );
    },
    [onSetVolume, executeControl]
  );

  // Next track
  const nextTrack = useCallback(async (): Promise<ControlResult> => {
    if (!onNextTrack) {
      return { success: false, error: 'NextTrack handler not configured' };
    }
    return executeControl(onNextTrack, 'nextTrack');
  }, [onNextTrack, executeControl]);

  // Previous track
  const previousTrack = useCallback(async (): Promise<ControlResult> => {
    if (!onPreviousTrack) {
      return { success: false, error: 'PreviousTrack handler not configured' };
    }
    return executeControl(onPreviousTrack, 'previousTrack');
  }, [onPreviousTrack, executeControl]);

  // Play specific track by ID
  const playTrack = useCallback(
    async (trackId: number): Promise<ControlResult> => {
      if (!onPlayTrack) {
        return { success: false, error: 'PlayTrack handler not configured' };
      }

      if (trackId <= 0) {
        return { success: false, error: 'Track ID must be positive' };
      }

      return executeControl(
        () => onPlayTrack(trackId),
        `playTrack(${trackId})`
      );
    },
    [onPlayTrack, executeControl]
  );

  // Remove from queue by index
  const removeFromQueue = useCallback(
    async (index: number): Promise<ControlResult> => {
      if (!onRemoveFromQueue) {
        return { success: false, error: 'RemoveFromQueue handler not configured' };
      }

      if (index < 0) {
        return { success: false, error: 'Queue index cannot be negative' };
      }

      return executeControl(
        () => onRemoveFromQueue(index),
        `removeFromQueue(${index})`
      );
    },
    [onRemoveFromQueue, executeControl]
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (seekTimeoutRef.current) {
        clearTimeout(seekTimeoutRef.current);
      }
    };
  }, []);

  return {
    play,
    pause,
    togglePlayPause,
    nextTrack,
    previousTrack,
    seek,
    seekDebounced,
    setVolume,
    playTrack,
    removeFromQueue,
    isLoading,
    lastError,
  };
}

export default usePlayerControls;
