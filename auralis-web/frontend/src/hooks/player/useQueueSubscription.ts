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

import { useDispatch } from 'react-redux';
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
import type { AppDispatch } from '@/store';

type QueueWSMessage =
  | QueueChangedMessage
  | QueueShuffledMessage
  | RepeatModeChangedMessage;

/**
 * Subscribe to `queue_changed` / `queue_shuffled` / `repeat_mode_changed`
 * WebSocket events and dispatch them to Redux so all consumers see the same
 * data.
 */
export function useQueueSubscription(): void {
  const dispatch = useDispatch<AppDispatch>();

  useWebSocketMessages(
    ['queue_changed', 'queue_shuffled', 'repeat_mode_changed'],
    (message) => {
      const msg = message as QueueWSMessage;

      switch (msg.type) {
        case 'queue_changed': {
          const { data } = msg;
          if (data.tracks) dispatch(reduxSetQueue(data.tracks));
          if (data.current_index != null) dispatch(reduxSetCurrentIndex(data.current_index));
          else if (data.currentIndex != null) dispatch(reduxSetCurrentIndex(data.currentIndex));
          break;
        }

        case 'queue_shuffled': {
          const { data } = msg;
          if (data.is_shuffled != null) dispatch(reduxSetIsShuffled(data.is_shuffled));
          else if (data.isShuffled != null) dispatch(reduxSetIsShuffled(data.isShuffled));
          if (data.tracks) dispatch(reduxSetQueue(data.tracks));
          break;
        }

        case 'repeat_mode_changed': {
          const { data } = msg;
          if (isRepeatMode(data.repeat_mode)) dispatch(reduxSetRepeatMode(data.repeat_mode));
          else if (isRepeatMode(data.repeatMode)) dispatch(reduxSetRepeatMode(data.repeatMode));
          break;
        }
      }
    }
  );
}
