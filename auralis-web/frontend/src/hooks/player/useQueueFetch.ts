/**
 * useQueueFetch Hook
 * ~~~~~~~~~~~~~~~~~~
 *
 * Fetches the initial playback queue on mount and dispatches it into Redux.
 * Extracted from usePlaybackQueue (#4292) to give the fetch path its own
 * focused, independently-testable home.
 *
 * @module hooks/player/useQueueFetch
 */

import { useEffect } from 'react';
import { useDispatch } from 'react-redux';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import {
  setQueue as reduxSetQueue,
  setCurrentIndex as reduxSetCurrentIndex,
  setIsShuffled as reduxSetIsShuffled,
  setRepeatMode as reduxSetRepeatMode,
  isRepeatMode,
} from '@/store/slices/queueSlice';
import type { Track, QueueTrack } from '@/types/domain';
import type { AppDispatch } from '@/store';

/**
 * Fetch the current queue from the backend on mount and seed Redux with it.
 *
 * Gated on a per-effect `isActive` flag (fixes #3925): without it, React 18
 * Strict Mode's mount->cleanup->remount double-invoke fires two overlapping
 * requests, and whichever resolves last wins — a stale first response can
 * overwrite freshly-mounted Redux state if it resolves after the second.
 */
export function useQueueFetch(): void {
  const { get } = useRestAPI();
  const dispatch = useDispatch<AppDispatch>();

  useEffect(() => {
    let isActive = true;

    const fetchInitialQueue = async () => {
      try {
        const response = await get<Record<string, unknown>>('/api/player/queue');

        if (response && isActive) {
          // Backend sends snake_case; map to our state shape
          dispatch(reduxSetQueue((response.tracks as (Track | QueueTrack)[]) || []));
          dispatch(reduxSetCurrentIndex(
            (response.current_index as number) ?? (response.currentIndex as number) ?? 0
          ));
          dispatch(reduxSetIsShuffled(
            (response.is_shuffled as boolean) ?? (response.isShuffled as boolean) ?? false
          ));
          const initialRepeatMode = isRepeatMode(response.repeat_mode)
            ? response.repeat_mode
            : isRepeatMode(response.repeatMode)
              ? response.repeatMode
              : 'off';
          dispatch(reduxSetRepeatMode(initialRepeatMode));
        }
      } catch (err) {
        // Silently fail - user can still interact with empty queue
        console.warn('Failed to fetch initial queue:', err);
      }
    };

    fetchInitialQueue();

    return () => {
      isActive = false;
    };
  }, [get, dispatch]);
}
