/**
 * Queue Redux Hooks
 * ~~~~~~~~~~~~~~~~~
 *
 * Queue-slice state and action hooks. Split out of useReduxState.ts (#5239),
 * which re-exports everything here.
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import { useSelector, useDispatch, shallowEqual } from 'react-redux';
import { useCallback, useMemo } from 'react';
import type { RootState, AppDispatch } from '@/store';
import type { QueueTrack } from '@/types/domain';
import * as queueActions from '@/store/slices/queueSlice';
import { selectFormattedRemainingTime } from '@/store/selectors';

/**
 * Access entire queue state
 */
export const useQueueState = () => {
  return useSelector((state: RootState) => state.queue, shallowEqual);
};

/**
 * Access queue management controls
 */
export const useQueue = () => {
  const dispatch = useDispatch<AppDispatch>();
  const state = useSelector((state: RootState) => state.queue, shallowEqual);

  // Memoize O(n) queue duration computations — only recalculate when tracks or
  // currentIndex change, not on every 10Hz position_changed re-render (fixes #2545).
  const remainingTime = useMemo(
    () => state.tracks.slice(state.currentIndex + 1).reduce((sum, t) => sum + t.duration, 0),
    [state.tracks, state.currentIndex]
  );
  const totalTime = useMemo(
    () => state.tracks.reduce((sum, t) => sum + t.duration, 0),
    [state.tracks]
  );

  const add = useCallback(
    (track: QueueTrack, position?: number) => dispatch(queueActions.addTrack(track, position)),
    [dispatch]
  );
  const addMany = useCallback(
    (tracks: QueueTrack[]) => dispatch(queueActions.addTracks(tracks)),
    [dispatch]
  );
  const remove = useCallback(
    (index: number) => dispatch(queueActions.removeTrack(index)),
    [dispatch]
  );
  const reorder = useCallback(
    (fromIndex: number, toIndex: number) =>
      dispatch(queueActions.reorderTrack({ fromIndex, toIndex })),
    [dispatch]
  );
  const setCurrentIndex = useCallback(
    (index: number) => dispatch(queueActions.setCurrentIndex(index)),
    [dispatch]
  );
  // #4660: `next`/`previous` used to live here, dispatching queueSlice's
  // nextTrack/previousTrack — reducers that moved currentIndex client-side
  // with no API call and no track_changed round-trip, so the UI could show a
  // different track than the engine was streaming. The real skip path is
  // usePlaybackControl().next()/.previous(); use that.
  const clear = useCallback(() => dispatch(queueActions.clearQueue()), [dispatch]);
  const setQueue = useCallback(
    (tracks: QueueTrack[]) => dispatch(queueActions.setQueue(tracks)),
    [dispatch]
  );

  // #3619: stable object identity across renders when nothing relevant
  // changed — matches the usePlayer pattern from #2537.
  return useMemo(
    () => ({
      tracks: state.tracks,
      currentIndex: state.currentIndex,
      currentTrack: state.tracks[state.currentIndex] || null,
      queueLength: state.tracks.length,
      isLoading: state.isLoading,
      error: state.error,
      remainingTime,
      totalTime,
      add,
      addMany,
      remove,
      reorder,
      setCurrentIndex,
      clear,
      setQueue,
    }),
    [
      state.tracks,
      state.currentIndex,
      state.isLoading,
      state.error,
      remainingTime,
      totalTime,
      add,
      addMany,
      remove,
      reorder,
      setCurrentIndex,
      clear,
      setQueue,
    ]
  );
};

/**
 * Format remaining time in queue (memoized via createSelector, #2812)
 */
export const useQueueTimeRemaining = () => {
  return useSelector(selectFormattedRemainingTime);
};
