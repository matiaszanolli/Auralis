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
 * A stop that no play follows also tells the backend (#6559): stopPlayback()
 * is client-only, and only a following play_* cancels the server's stream
 * task, so a removed last track (or a cleared queue, #6561) used to keep the
 * server rendering every remaining chunk and holding its stream slot.
 *
 * @module contexts/useFollowRemovedTrack
 */

import { useCallback, useRef } from 'react';
import { useDispatch, useStore } from 'react-redux';
import type { AppDispatch, RootState } from '@/store';
import { setCurrentTrack } from '@/store/slices/playerSlice';
import { setCurrentTrackAndSyncQueue } from '@/store/slices/playerQueueSync';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
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
  const { send } = useWebSocketContext();

  return useCallback(
    async (index: number, removedTrackId: number) => {
      const follow = async () => {
        // The queue is read after the removal: `index` now holds the successor.
        const { player, queue } = store.getState();
        if (player.currentTrack?.id !== removedTrackId) return; // not the playing track
        const wasRunning = isRunningRef.current;
        const successor = queue.tracks[index];
        stopPlayback();
        // No play follows: cancel the server's stream task too (#6559).
        if (!successor || !wasRunning) send({ type: 'stop', data: {} });
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
    [store, dispatch, send, stopPlayback, startTrackForSettings, runTransportCommand, pendingCommandRef]
  );
}

/**
 * Stop the session after Clear Queue (#6561). The cleared queue has no track to
 * follow, and the backend's clear only stops its shadow engine, so the browser
 * stream kept playing under an empty queue with no control left to stop it.
 * Runs even if the player_state broadcast already nulled the current track.
 */
export function useStopForClearedQueue({
  gate,
  stopPlayback,
  isPlaybackActive,
}: Pick<FollowRemovedTrackInputs, 'gate' | 'stopPlayback'> & { isPlaybackActive: boolean }): () => Promise<void> {
  const dispatch = useDispatch<AppDispatch>();
  const { send } = useWebSocketContext();
  const activeRef = useRef(isPlaybackActive);
  activeRef.current = isPlaybackActive;
  const { runTransportCommand, pendingCommandRef } = gate;

  return useCallback(async () => {
    const stop = async () => {
      if (activeRef.current) {
        stopPlayback();
        send({ type: 'stop', data: {} });
      }
      dispatch(setCurrentTrack(null));
    };
    if (await runTransportCommand(stop)) return;
    await pendingCommandRef.current;
    await runTransportCommand(stop);
  }, [dispatch, send, stopPlayback, runTransportCommand, pendingCommandRef]);
}
