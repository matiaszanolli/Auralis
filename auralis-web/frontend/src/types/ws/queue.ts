/**
 * WebSocket message types — queue domain.
 * Split from the former monolithic types/websocket.ts (#4081); consumers import
 * via the '@/types/websocket' barrel which re-exports every ws/* module.
 */


import type { WebSocketMessage, TrackInfo } from './base';

/** Message-type literals owned by the queue domain. */
export type QueueMessageType =
  | 'queue_updated'
  | 'queue_changed'
  | 'queue_shuffled'
  | 'repeat_mode_changed';


// ============================================================================
// Queue Messages
// ============================================================================

export interface QueueUpdatedMessage extends WebSocketMessage {
  type: 'queue_updated';
  data: {
    action: 'added' | 'removed' | 'reordered' | 'cleared' | 'shuffled';
    track_path?: string; // For "added" action
    index?: number; // For "removed" action
    queue_size: number;
  };
}


/**
 * Broadcast when queue contents change (add, remove, reorder, or clear)
 */
export interface QueueChangedMessage extends WebSocketMessage {
  type: 'queue_changed';
  data: {
    tracks: TrackInfo[]; // Full queue after change
    // Both naming conventions are accepted: the backend currently emits
    // snake_case, but some emitters historically used camelCase; consumers
    // (usePlaybackQueue) prefer snake_case and fall back to camelCase.
    current_index?: number;
    currentIndex?: number;
    action?: 'added' | 'removed' | 'reordered' | 'cleared';
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
    repeat_mode?: 'off' | 'all' | 'one';
    repeatMode?: 'off' | 'all' | 'one';
  };
}
