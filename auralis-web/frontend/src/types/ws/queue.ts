/**
 * WebSocket message types — queue domain.
 * Split from the former monolithic types/websocket.ts (#4081); consumers import
 * via the '@/types/websocket' barrel which re-exports every ws/* module.
 */


import type { RepeatMode } from '@/types/domain';
import type { WebSocketMessage, TrackInfo } from './base';

/** Message-type literals owned by the queue domain. */
export type QueueMessageType =
  | 'queue_changed'
  | 'queue_shuffled'
  | 'repeat_mode_changed';


// ============================================================================
// Queue Messages
// ============================================================================

// No `queue_updated` message type exists — its backend emitter is gone
// (#3492/#4680), so a subscription key here could never fire. Subscribe to
// `queue_changed` below.


/**
 * Broadcast when queue contents change (add, remove, reorder, or clear)
 */
export interface QueueChangedMessage extends WebSocketMessage {
  type: 'queue_changed';
  data: {
    // Most emitters include the hydrated queue. The history-undo emitter only
    // carries the restored index and queue size, so this is genuinely optional.
    tracks?: TrackInfo[]; // Full queue after change
    current_index?: number;
    action?:
      | 'added'
      | 'removed'
      | 'reordered'
      | 'shuffled'
      | 'unshuffled'
      | 'cleared'
      | 'undo';
    track_id?: number;
    position?: number | null;
    index?: number;
    queue_size?: number;
    from_index?: number;
    to_index?: number;
  };
}


/**
 * Broadcast when shuffle mode is toggled
 */
export interface QueueShuffledMessage extends WebSocketMessage {
  type: 'queue_shuffled';
  data: {
    is_shuffled?: boolean;
    isShuffled?: boolean;
    tracks?: TrackInfo[]; // Reordered queue if shuffled
  };
}


/**
 * Broadcast when repeat mode changes
 */
export interface RepeatModeChangedMessage extends WebSocketMessage {
  type: 'repeat_mode_changed';
  data: {
    repeat_mode?: RepeatMode;
    repeatMode?: RepeatMode;
  };
}
