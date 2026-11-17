/**
 * Removing the playing row from the queue moves playback on (#6016).
 *
 * The queue slice keeps `currentIndex` on the removed slot, which now holds
 * the track that followed, while the stream kept playing the removed track:
 * the panel highlighted a track that was not playing, and Next/auto-advance
 * (`currentIndex + 1`) then skipped that successor. The backend engine already
 * loads the successor on remove-current (#2403), so the session does the same:
 * stop, select the track now in the slot, and start it if playback was running
 * (a paused session just selects it). With nothing after it, playback stops.
 *
 * @module contexts/useFollowRemovedTrack
 */

import { useCallback, useRef } from 'react';
import { useDispatch, useStore } from 'react-redux';
import type { AppDispatch, RootState } from '@/store';
import { setCurrentTrack } from '@/store/slices/playerSlice';
import { setCurrentTrackAndSyncQueue } from '@/store/slices/playerQueueSync';
import type { TransportCommandGate } from './usePlaybackSessionHooks';

export interface FollowRemovedTrackInputs {
  gate: Pick<TransportCommandGate, 'runTransportCommand' | 'pendingCommandRef'>;
  stopPlayback: () => void;
  startTrackForSettings: (trackId: number) => void | Promise<void>;
  /** Audio is running (not paused): the successor starts rather than just being selected. */
  isRunning: boolean;
}

export function useFollowRemovedTrack({
  gate,
  stopPlayback,
  startTrackForSettings,
  isRunning,
}: FollowRemovedTrackInputs): (index: number, removedTrackId: number) => Promise<void> {
  const dispatch = useDispatch<AppDispatch>();
  const store = useStore<RootState>();
  // Read when the command runs, not when the caller captured the callback.
  const isRunningRef = useRef(isRunning);
  isRunningRef.current = isRunning;
  const { runTransportCommand, pendingCommandRef } = gate;

  return useCallback(
    async (index: number, removedTrackId: number) => {
      const follow = async () => {
        // The queue is read after the removal: `index` now holds the successor.
        const { player, queue } = store.getState();
        if (player.currentTrack?.id !== removedTrackId) return; // not the playing track
        const wasRunning = isRunningRef.current;
        stopPlayback();
        const successor = queue.tracks[index];
        if (!successor) {
          dispatch(setCurrentTrack(null));
          return;
        }
        dispatch(setCurrentTrackAndSyncQueue(successor, index));
        if (wasRunning) await startTrackForSettings(successor.id);
      };
      // Like startTrack's retry (#5613): a command already in flight must not
      // leave the removed track playing.
      if (await runTransportCommand(follow)) return;
      await pendingCommandRef.current;
      await runTransportCommand(follow);
    },
    [store, dispatch, stopPlayback, startTrackForSettings, runTransportCommand, pendingCommandRef]
  );
}
