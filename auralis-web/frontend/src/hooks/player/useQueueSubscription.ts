/**
 * useQueueSubscription Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Subscribes to real-time queue updates via WebSocket and dispatches them
 * into Redux. Extracted from usePlaybackQueue (#4292) to give the
 * WS-subscription path its own focused, independently-testable home.
 *
 * @module hooks/player/useQueueSubscription
 */

import { useDispatch, useSelector } from 'react-redux';
import { useWebSocketMessages } from '@/hooks/websocket/useWebSocketMessages';
import type {
  QueueChangedMessage,
  QueueShuffledMessage,
  RepeatModeChangedMessage,
} from '@/types/websocket';
import {
  setQueue as reduxSetQueue,
  setCurrentIndex as reduxSetCurrentIndex,
  setIsShuffled as reduxSetIsShuffled,
  setRepeatMode as reduxSetRepeatMode,
  isRepeatMode,
} from '@/store/slices/queueSlice';
import { playerSelectors } from '@/store/selectors';
import { selectQueueTracks } from '@/store/slices/queueSlice';
import { mapTrackInfoToTrack } from './trackInfoMapper';
import { reconcileQueueIndex } from './queueIndexReconciliation';
import type { AppDispatch } from '@/store';

/**
 * Subscribe to `queue_changed` / `queue_shuffled` / `repeat_mode_changed`
 * WebSocket events and dispatch them to Redux so all consumers see the same
 * data.
 */
export function useQueueSubscription(): void {
  const dispatch = useDispatch<AppDispatch>();
  // The track the session is actually playing — the authority the engine's
  // stale queue pointer gets reconciled against (#5601). queueTracks serves
  // the same reconciliation when a frame carries only an index.
  const playingTrackId = useSelector(playerSelectors.selectCurrentTrack)?.id;
  const queueTracks = useSelector(selectQueueTracks);

  useWebSocketMessages(
    ['queue_changed', 'queue_shuffled', 'repeat_mode_changed'],
    (message) => {
      const msg = message;

      switch (msg.type) {
        case 'queue_changed': {
          // `data` is required by the type but arrives off the wire — a frame
          // without it must not throw out of the shared WS dispatch loop
          // (#4639). tracks go through the shared snake_case→camelCase mapper
          // (#5606, same contract as useQueueFetch/usePlayerStateSync — #5009):
          // dispatching them raw left every queue entry without artworkUrl,
          // and track_changed then copied such an entry into player.currentTrack.
          const data = msg.data ?? ({} as QueueChangedMessage['data']);
          const mappedTracks = data.tracks?.map(mapTrackInfoToTrack);
          const engineIndex = data.current_index;
          // setQueue FIRST: setCurrentIndex's reducer silently drops any index
          // outside the current tracks array, so an empty/replaced queue must
          // land before the index does.
          if (mappedTracks) dispatch(reduxSetQueue(mappedTracks));
          if (engineIndex != null) {
            // #5601: engineIndex is the ENGINE's pointer, which still sits on
            // the pre-skip track after a local Next/Previous. Reconcile it
            // against what the session is playing — against the incoming
            // tracks when the frame carries them, else the live queue.
            const reconciled = reconcileQueueIndex(
              mappedTracks ?? queueTracks,
              engineIndex,
              playingTrackId,
            );
            if (reconciled != null) dispatch(reduxSetCurrentIndex(reconciled));
          }
          break;
        }

        case 'queue_shuffled': {
          const data = msg.data ?? ({} as QueueShuffledMessage['data']);
          if (data.is_shuffled != null) dispatch(reduxSetIsShuffled(data.is_shuffled));
          else if (data.isShuffled != null) dispatch(reduxSetIsShuffled(data.isShuffled));
          if (data.tracks) dispatch(reduxSetQueue(data.tracks.map(mapTrackInfoToTrack)));
          break;
        }

        case 'repeat_mode_changed': {
          const data = msg.data ?? ({} as RepeatModeChangedMessage['data']);
          if (isRepeatMode(data.repeat_mode)) dispatch(reduxSetRepeatMode(data.repeat_mode));
          else if (isRepeatMode(data.repeatMode)) dispatch(reduxSetRepeatMode(data.repeatMode));
          break;
        }
      }
    }
  );
}
