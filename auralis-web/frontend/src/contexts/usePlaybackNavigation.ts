/**
 * Next / previous track navigation for PlaybackSessionProvider (#6275).
 *
 * One stepping routine serves both directions: it moves along the displayed queue order (which is
 * already the shuffled sequence under shuffle), wraps only under repeat 'all' (#5605), then stops
 * the current stream, syncs queue index + player.currentTrack atomically (#3587) and starts the
 * new track with the live enhancement settings.
 *
 * @module contexts/usePlaybackNavigation
 */

import { useCallback } from 'react';
import { useDispatch } from 'react-redux';
import type { AppDispatch } from '@/store';
import type { RepeatMode } from '@/types/domain';
import type { QueueTrack } from '@/types/domain';
import { setCurrentTrackAndSyncQueue } from '@/store/slices/playerQueueSync';

const DEBUG = import.meta.env.DEV;

interface UsePlaybackNavigationArgs {
  queueTracks: readonly QueueTrack[];
  currentQueueIndex: number;
  repeatMode: RepeatMode;
  runTransportCommand: (command: () => Promise<void>) => Promise<boolean>;
  stopPlayback: () => void;
  startTrackForSettings: (trackId: number) => Promise<unknown> | unknown;
}

export function usePlaybackNavigation({
  queueTracks,
  currentQueueIndex,
  repeatMode,
  runTransportCommand,
  stopPlayback,
  startTrackForSettings,
}: UsePlaybackNavigationArgs) {
  const dispatch = useDispatch<AppDispatch>();

  /** Resolves whether the command actually started (false = the gate was busy and dropped it). */
  const step = useCallback(
    (delta: 1 | -1): Promise<boolean> => {
      const label = delta > 0 ? 'Next' : 'Previous';
      return runTransportCommand(async () => {
        try {
          let index = currentQueueIndex + delta;
          if (index < 0 || index >= queueTracks.length) {
            // repeat 'one' is a track-END mode, not a navigation mode: Next/Previous still move
            // off the end of the queue (#5605).
            if (repeatMode !== 'all' || queueTracks.length === 0) {
              DEBUG && console.log(`[PlaybackSession] Already at ${delta > 0 ? 'last' : 'first'} track in queue`);
              return;
            }
            index = delta > 0 ? 0 : queueTracks.length - 1;
          }

          const target = queueTracks[index];
          if (!target) return;

          stopPlayback();
          dispatch(setCurrentTrackAndSyncQueue(target, index));
          await startTrackForSettings(target.id);
        } catch (err) {
          console.error(`[PlaybackSession] ${label} command error:`, err);
        }
      });
    },
    [currentQueueIndex, queueTracks, repeatMode, stopPlayback, dispatch, runTransportCommand, startTrackForSettings]
  );

  const advanceNext = useCallback(() => step(1), [step]);
  // The transport handlers await-and-discard `started` (#5613): coalescing is their desired
  // behaviour, so a drop needs no reaction - they only keep the Promise<void> contract.
  const handleNext = useCallback(async () => { await step(1); }, [step]);
  const handlePrevious = useCallback(async () => { await step(-1); }, [step]);

  return { advanceNext, handleNext, handlePrevious };
}
