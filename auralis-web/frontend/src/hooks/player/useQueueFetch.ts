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
import { isQueueResponseShape } from '@/api/responseGuards';
import {
  setQueue as reduxSetQueue,
  setCurrentIndex as reduxSetCurrentIndex,
  setIsShuffled as reduxSetIsShuffled,
  setRepeatMode as reduxSetRepeatMode,
  isRepeatMode,
} from '@/store/slices/queueSlice';
import type { AppDispatch } from '@/store';
import { mapTrackInfoToTrack } from './trackInfoMapper';
import type { QueueResponse } from '@/services/queueService';

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
        // Typed as the wire shape (queueService.QueueResponse) so the fields
        // read directly — this used to be `get<Record<string, unknown>>` with
        // a per-field `as` before every read, which is how the phantom
        // is_shuffled/isShuffled keys survived for months (#4787/#5637).
        const response = await get<QueueResponse>('/api/player/queue', {
          validate: isQueueResponseShape,
        });

        if (response && isActive) {
          // Backend sends snake_case (#5009: mapped via the same helper
          // usePlayerStateSync uses, not a raw cast — the resulting Redux
          // queue.tracks entries are read as-is by the track_changed WS
          // handler, so a caller-mapped shape here directly determines what
          // that live path dispatches).
          dispatch(reduxSetQueue((response.tracks ?? []).map(mapTrackInfoToTrack)));
          dispatch(reduxSetCurrentIndex(response.current_index ?? 0));
          // Backend (QueueManager.get_queue_info) only ever emits
          // shuffle_enabled — is_shuffled/isShuffled are phantom keys the
          // backend never sends, so reading them always resolved to the
          // `?? false` fallback regardless of actual server state (#4787).
          // Kept as a fallback in case a legacy payload shape is ever seen.
          dispatch(reduxSetIsShuffled(response.shuffle_enabled ?? false));
          const initialRepeatMode = isRepeatMode(response.repeat_mode)
            ? response.repeat_mode
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
