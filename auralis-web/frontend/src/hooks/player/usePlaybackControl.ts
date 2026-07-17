/**
 * usePlaybackControl Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Provides playback control methods for commanding the audio player.
 * This is the control layer — observe playback state via Redux selectors
 * (playerSlice / queueSlice).
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
 * @see auralis-web/frontend/src/store/slices/playerSlice.ts for state selectors
 */

import { useCallback, useState, useRef } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import {
  selectCurrentTrack,
  selectDuration,
  setCurrentTime,
  setCurrentTrack,
  setIsPlaying,
} from '@/store/slices/playerSlice';
import {
  clearQueue,
} from '@/store/slices/queueSlice';
import type { ApiError } from '@/types/api';
import type { AppDispatch } from '@/store';
import { ApiErrorHandler } from '@/types/api';

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
  const currentTrack = useSelector(selectCurrentTrack);
  const duration = useSelector(selectDuration);
  const { send } = useWebSocketContext();
  const dispatch = useDispatch<AppDispatch>();
  // Local loading state for this hook's operations
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  // Track which command is executing (for optimistic updates)
  const executingCommand = useRef<string | null>(null);

  // Ref so the play callback can read the latest track ID without taking
  // currentTrack as a dep (position updates create new object
  // references every ~1 s, which would recreate play on every tick — #2354).
  const currentTrackRef = useRef(currentTrack);
  currentTrackRef.current = currentTrack;

  // Ref so seek reads the latest duration without taking it as a dep
  // (duration updates at ~1 Hz via WS, which would recreate seek — #2992).
  const durationRef = useRef(duration);
  durationRef.current = duration;

  /**
   * Play - Start playback or resume if paused
   * Uses WebSocket 'play_normal' message for normal (unprocessed) audio streaming
   */
  const play = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    executingCommand.current = 'play';

    try {
      // Read track ID via ref so this callback doesn't depend on the
      // currentTrack object reference (avoids re-creation on position updates).
      const trackId = currentTrackRef.current?.id;

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

      // Server broadcasts audio stream messages which are handled by WebSocket context.
      // Yield to let React commit the isLoading=true render before clearing,
      // so consumers can show a loading indicator (#3271).
      await new Promise(resolve => setTimeout(resolve, 0));
    } catch (err) {
      const apiError = ApiErrorHandler.parseWithCode(err, 'PLAY_ERROR');
      setError(apiError);
      throw apiError;
    } finally {
      setIsLoading(false);
      executingCommand.current = null;
    }
  }, [send]);

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

      // Server broadcasts 'playback_paused' message which updates the Redux player slice
    } catch (err) {
      const apiError = ApiErrorHandler.parseWithCode(err, 'PAUSE_ERROR');
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
      // Optimistic update — UI reflects stopped state before the WS
      // 'playback_stopped' broadcast arrives.
      dispatch(setIsPlaying(false));
      dispatch(setCurrentTrack(null));
      dispatch(setCurrentTime(0));
      dispatch(clearQueue());

      // send() never throws (it queues and is fire-and-forget), so the
      // catch block that was here was unreachable dead code (#3966).
      send({ type: 'stop', data: {} });
    } finally {
      setIsLoading(false);
      executingCommand.current = null;
    }
  }, [send, dispatch]);

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
    const validPosition = Math.max(0, Math.min(position, durationRef.current || position));

    try {
      // Backend expects position in JSON body
      await api.post('/api/player/seek', { position: validPosition });
      // The backend's 1Hz state_manager tick broadcasts 'position_changed',
      // which usePlayerStateSync now applies to redux.player.currentTime (#3937).
    } catch (err) {
      const apiError = ApiErrorHandler.parseWithCode(err, 'SEEK_ERROR');
      setError(apiError);
      throw apiError;
    } finally {
      setIsLoading(false);
      executingCommand.current = null;
    }
  }, [api]);

  /**
   * Next - Skip to next track in queue
   */
  const next = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    executingCommand.current = 'next';

    try {
      await api.post('/api/player/next');
      // Server broadcasts 'track_changed' message which updates the Redux player slice
    } catch (err) {
      const apiError = ApiErrorHandler.parseWithCode(err, 'NEXT_ERROR');
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
      // Server broadcasts 'track_changed' message which updates the Redux player slice
    } catch (err) {
      const apiError = ApiErrorHandler.parseWithCode(err, 'PREVIOUS_ERROR');
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
      // Backend reads volume from JSON body (SetVolumeRequest, 0-100) (fixes #2498)
      await api.post('/api/player/volume', { volume: Math.round(validVolume) });
      // Server broadcasts 'volume_changed' message which updates the Redux player slice
    } catch (err) {
      const apiError = ApiErrorHandler.parseWithCode(err, 'VOLUME_ERROR');
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
