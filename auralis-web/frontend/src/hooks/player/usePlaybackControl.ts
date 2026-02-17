/**
 * usePlaybackControl Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Provides playback control methods for commanding the audio player.
 * This is the control layer - usePlaybackState is the observation layer.
 *
 * Usage:
 * ```typescript
 * const { play, pause, seek, next, previous, setVolume, isLoading, error } = usePlaybackControl();
 *
 * await play();
 * await seek(120); // Seek to 2:00
 * await setVolume(0.8);
 * ```
 *
 * Features:
 * - Type-safe API calls via useRestAPI
 * - Automatic loading/error state tracking
 * - Optimistic UI updates with error rollback
 * - Proper error handling and messages
 * - Memoized callback functions
 *
 * @module hooks/player/usePlaybackControl
 * @see usePlaybackState for reading player state
 */

import { useCallback, useState, useRef } from 'react';
import { useDispatch } from 'react-redux';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import { usePlaybackState } from '@/hooks/player/usePlaybackState';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { setIsPlaying } from '@/store/slices/playerSlice';
import type { ApiError } from '@/types/api';
import type { AppDispatch } from '@/store';

/**
 * Return type for usePlaybackControl hook
 */
export interface PlaybackControlActions {
  /** Start playback (resume if paused) */
  play: () => Promise<void>;

  /** Pause playback */
  pause: () => Promise<void>;

  /** Stop playback and clear queue */
  stop: () => Promise<void>;

  /** Seek to position in seconds */
  seek: (position: number) => Promise<void>;

  /** Skip to next track */
  next: () => Promise<void>;

  /** Skip to previous track */
  previous: () => Promise<void>;

  /** Set playback volume (0.0-1.0) */
  setVolume: (volume: number) => Promise<void>;

  /** True while a command is executing */
  isLoading: boolean;

  /** Last error from a command, null if no error */
  error: ApiError | null;

  /** Clear error state */
  clearError: () => void;
}

/**
 * Hook for controlling audio playback
 *
 * @returns PlaybackControlActions with play, pause, seek, etc. methods
 *
 * @example
 * ```typescript
 * const { play, pause, seek, isLoading, error } = usePlaybackControl();
 *
 * const handlePlayClick = async () => {
 *   try {
 *     await play();
 *   } catch (err) {
 *     console.error('Failed to play:', error?.message);
 *   }
 * };
 * ```
 */
export function usePlaybackControl(): PlaybackControlActions {
  const api = useRestAPI();
  const playbackState = usePlaybackState();
  const { send } = useWebSocketContext();
  const dispatch = useDispatch<AppDispatch>();

  // Local loading state for this hook's operations
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  // Track which command is executing (for optimistic updates)
  const executingCommand = useRef<string | null>(null);

  /**
   * Play - Start playback or resume if paused
   * Uses WebSocket 'play_normal' message for normal (unprocessed) audio streaming
   */
  const play = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    executingCommand.current = 'play';

    try {
      // Get current track from playback state
      const trackId = playbackState.currentTrack?.id;

      if (!trackId) {
        throw new Error('No track selected. Set queue first.');
      }

      // Send WebSocket message for normal (unprocessed) audio playback
      send({
        type: 'play_normal',
        data: {
          track_id: trackId,
        },
      });

      // Server broadcasts audio stream messages which are handled by WebSocket context
      // No need to manually update - it happens via WebSocket listeners
    } catch (err) {
      const apiError = err instanceof Error ? { message: err.message, code: 'PLAY_ERROR', status: 500 } : err as ApiError;
      setError(apiError);
      throw apiError;
    } finally {
      setIsLoading(false);
      executingCommand.current = null;
    }
  }, [send, playbackState.currentTrack]);

  /**
   * Pause - Pause playback
   * Uses WebSocket 'pause' message to pause audio streaming
   */
  const pause = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    executingCommand.current = 'pause';

    try {
      // Update Redux state immediately so playback engines can respond
      dispatch(setIsPlaying(false));

      // Send WebSocket message to pause backend streaming
      send({
        type: 'pause',
        data: {},
      });

      // Server broadcasts 'playback_paused' message which updates usePlaybackState
    } catch (err) {
      const apiError = err instanceof Error ? { message: err.message, code: 'PAUSE_ERROR', status: 500 } : err as ApiError;
      setError(apiError);
      throw apiError;
    } finally {
      setIsLoading(false);
      executingCommand.current = null;
    }
  }, [send, dispatch]);

  /**
   * Stop - Stop playback completely
   * Uses WebSocket 'stop' message to stop audio streaming
   */
  const stop = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    executingCommand.current = 'stop';

    try {
      // Update Redux state immediately so playback engines can respond
      dispatch(setIsPlaying(false));

      // Send WebSocket message to stop backend streaming
      send({
        type: 'stop',
        data: {},
      });

      // Server broadcasts 'playback_stopped' message which updates usePlaybackState
    } catch (err) {
      const apiError = err instanceof Error ? { message: err.message, code: 'STOP_ERROR', status: 500 } : err as ApiError;
      setError(apiError);
      throw apiError;
    } finally {
      setIsLoading(false);
      executingCommand.current = null;
    }
  }, [send]);

  /**
   * Seek - Seek to position in seconds
   *
   * @param position Position in seconds
   * @throws Error if seek fails
   */
  const seek = useCallback(async (position: number): Promise<void> => {
    setIsLoading(true);
    setError(null);
    executingCommand.current = 'seek';

    // Validate position
    const validPosition = Math.max(0, Math.min(position, playbackState.duration || position));

    try {
      // Backend expects position as query parameter
      await api.post('/api/player/seek', undefined, { position: validPosition });
      // Server broadcasts 'position_changed' message which updates usePlaybackState
    } catch (err) {
      const apiError = err instanceof Error ? { message: err.message, code: 'SEEK_ERROR', status: 500 } : err as ApiError;
      setError(apiError);
      throw apiError;
    } finally {
      setIsLoading(false);
      executingCommand.current = null;
    }
  }, [api, playbackState.duration]);

  /**
   * Next - Skip to next track in queue
   */
  const next = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    executingCommand.current = 'next';

    try {
      await api.post('/api/player/next');
      // Server broadcasts 'track_changed' message which updates usePlaybackState
    } catch (err) {
      const apiError = err instanceof Error ? { message: err.message, code: 'NEXT_ERROR', status: 500 } : err as ApiError;
      setError(apiError);
      throw apiError;
    } finally {
      setIsLoading(false);
      executingCommand.current = null;
    }
  }, [api]);

  /**
   * Previous - Skip to previous track in queue
   */
  const previous = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    executingCommand.current = 'previous';

    try {
      await api.post('/api/player/previous');
      // Server broadcasts 'track_changed' message which updates usePlaybackState
    } catch (err) {
      const apiError = err instanceof Error ? { message: err.message, code: 'PREVIOUS_ERROR', status: 500 } : err as ApiError;
      setError(apiError);
      throw apiError;
    } finally {
      setIsLoading(false);
      executingCommand.current = null;
    }
  }, [api]);

  /**
   * SetVolume - Set playback volume
   *
   * @param volume Volume level 0.0-1.0
   * @throws Error if volume change fails
   */
  const setVolume = useCallback(async (volume: number): Promise<void> => {
    setIsLoading(true);
    setError(null);
    executingCommand.current = 'setVolume';

    // Clamp volume to valid range (convert to 0-100 for API)
    const validVolume = Math.max(0.0, Math.min(1.0, volume)) * 100;

    try {
      // Backend expects volume as query parameter (0-100)
      await api.post(`/api/player/volume?volume=${Math.round(validVolume)}`);
      // Server broadcasts 'volume_changed' message which updates usePlaybackState
    } catch (err) {
      const apiError = err instanceof Error ? { message: err.message, code: 'VOLUME_ERROR', status: 500 } : err as ApiError;
      setError(apiError);
      throw apiError;
    } finally {
      setIsLoading(false);
      executingCommand.current = null;
    }
  }, [api]);

  /**
   * Clear error state
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    play,
    pause,
    stop,
    seek,
    next,
    previous,
    setVolume,
    isLoading,
    error,
    clearError,
  };
}

/**
 * Convenience hook for only play/pause without other controls
 *
 * @example
 * ```typescript
 * const { play, pause, isLoading } = usePlayPauseControl();
 * ```
 */
export function usePlayPauseControl() {
  const { play, pause, isLoading, error, clearError } = usePlaybackControl();

  return {
    play,
    pause,
    isLoading,
    error,
    clearError,
  };
}

/**
 * Convenience hook for seek control only
 *
 * @example
 * ```typescript
 * const { seek, isLoading } = useSeekControl();
 * ```
 */
export function useSeekControl() {
  const { seek, isLoading, error, clearError } = usePlaybackControl();

  return {
    seek,
    isLoading,
    error,
    clearError,
  };
}

/**
 * Convenience hook for volume control only
 *
 * @example
 * ```typescript
 * const { setVolume, isLoading } = useVolumeControl();
 * ```
 */
export function useVolumeControl() {
  const { setVolume, isLoading, error, clearError } = usePlaybackControl();

  return {
    setVolume,
    isLoading,
    error,
    clearError,
  };
}

/**
 * Convenience hook for skip control (next/previous)
 *
 * @example
 * ```typescript
 * const { next, previous, isLoading } = useSkipControl();
 * ```
 */
export function useSkipControl() {
  const { next, previous, isLoading, error, clearError } = usePlaybackControl();

  return {
    next,
    previous,
    isLoading,
    error,
    clearError,
  };
}
