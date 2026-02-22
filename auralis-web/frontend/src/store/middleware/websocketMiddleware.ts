/**
 * WebSocket Redux Middleware
 * ~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Middleware that bridges WebSocket protocol messages to Redux store actions.
 * Handles real-time synchronization of player state, queue, cache, and connection.
 *
 * Features:
 * - Automatic message type to Redux action mapping
 * - Real-time state synchronization
 * - Offline queue for messages when disconnected
 * - Optimistic updates with server reconciliation
 * - Error tracking and recovery
 *
 * Phase C.4a: WebSocket-Redux Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import type { Dispatch, MiddlewareAPI } from '@reduxjs/toolkit';
import type { RootState } from '../index';
import type { WSMessage } from '@/services/websocket/protocolClient';
import { MessageType } from '@/services/websocket/protocolClient';
import * as playerActions from '../slices/playerSlice';
import * as queueActions from '../slices/queueSlice';
import * as cacheActions from '../slices/cacheSlice';
import * as connectionActions from '../slices/connectionSlice';

// ============================================================================
// Offline Message Queue
// ============================================================================

/**
 * Queue for messages received while offline
 * Replayed when connection restored
 */
export class OfflineMessageQueue {
  private queue: WSMessage[] = [];
  private maxSize = 100;

  enqueue(message: WSMessage): void {
    this.queue.push(message);
    // Keep queue bounded
    if (this.queue.length > this.maxSize) {
      this.queue.shift();
    }
  }

  dequeueAll(): WSMessage[] {
    const messages = [...this.queue];
    this.queue = [];
    return messages;
  }

  clear(): void {
    this.queue = [];
  }

  size(): number {
    return this.queue.length;
  }
}

// ============================================================================
// Message Handler Registry
// ============================================================================

interface MessageHandler {
  (message: WSMessage, dispatch: Dispatch, state: RootState, getState?: () => RootState): Promise<void> | void;
}

type MessageHandlerMap = Record<MessageType | string, MessageHandler>;

/**
 * Maps WebSocket message types to Redux dispatch actions
 */
const createMessageHandlers = (): MessageHandlerMap => ({
  // ========================================================================
  // Playback Control Messages
  // ========================================================================

  [MessageType.PLAY]: (message, dispatch) => {
    const { position = 0 } = message.payload || {};
    dispatch(playerActions.setIsPlaying(true));
    dispatch(playerActions.setCurrentTime(position));
  },

  [MessageType.PAUSE]: (message, dispatch) => {
    const { position = 0 } = message.payload || {};
    dispatch(playerActions.setIsPlaying(false));
    dispatch(playerActions.setCurrentTime(position));
  },

  [MessageType.STOP]: (_message, dispatch) => {
    dispatch(playerActions.setIsPlaying(false));
    dispatch(playerActions.setCurrentTime(0));
  },

  [MessageType.SEEK]: (message, dispatch) => {
    const { position = 0 } = message.payload || {};
    dispatch(playerActions.setCurrentTime(position));
  },

  [MessageType.NEXT]: (_message, dispatch, _state, getState) => {
    dispatch(queueActions.nextTrack());
    // Read post-dispatch state to get the correct track after reducer
    // updates (avoids stale-state bug during shuffle, fixes #2178).
    const updated = getState?.();
    if (updated) {
      const { currentIndex, tracks } = updated.queue;
      const nextTrack = tracks[currentIndex];
      if (nextTrack) {
        dispatch(playerActions.setCurrentTrack(nextTrack));
      }
    }
  },

  [MessageType.PREVIOUS]: (_message, dispatch, _state, getState) => {
    dispatch(queueActions.previousTrack());
    // Read post-dispatch state to get the correct track (fixes #2178).
    const updated = getState?.();
    if (updated) {
      const { currentIndex, tracks } = updated.queue;
      const prevTrack = tracks[currentIndex];
      if (prevTrack) {
        dispatch(playerActions.setCurrentTrack(prevTrack));
      }
    }
  },

  // ========================================================================
  // Queue Management Messages
  // ========================================================================

  [MessageType.QUEUE_ADD]: (message, dispatch) => {
    const { track, index } = message.payload || {};
    if (track) {
      if (index !== undefined) {
        // Insert at specific position (not directly supported, add then reorder)
        dispatch(queueActions.addTrack(track));
      } else {
        dispatch(queueActions.addTrack(track));
      }
    }
  },

  [MessageType.QUEUE_REMOVE]: (message, dispatch) => {
    const { index } = message.payload || {};
    if (index !== undefined) {
      dispatch(queueActions.removeTrack(index));
    }
  },

  [MessageType.QUEUE_CLEAR]: (_message, dispatch) => {
    dispatch(queueActions.clearQueue());
    dispatch(playerActions.setCurrentTrack(null));
  },

  [MessageType.QUEUE_REORDER]: (message, dispatch) => {
    const { fromIndex, toIndex } = message.payload || {};
    if (fromIndex !== undefined && toIndex !== undefined) {
      dispatch(queueActions.reorderTrack({ fromIndex, toIndex }));
    }
  },

  // ========================================================================
  // Cache Management Messages
  // ========================================================================

  [MessageType.CACHE_STATS]: (message, dispatch) => {
    const stats = message.payload as any;
    if (stats) {
      dispatch(cacheActions.setCacheStats(stats));
    }
  },

  [MessageType.CACHE_STATUS]: (message, dispatch) => {
    const health = message.payload as any;
    if (health) {
      dispatch(cacheActions.setCacheHealth(health));
    }
  },

  // ========================================================================
  // Status Update Messages
  // ========================================================================

  [MessageType.STATUS_UPDATE]: (message, dispatch) => {
    const {
      playing,
      position,
      volume,
      muted,
      preset,
      currentTrack,
    } = message.payload || {};

    // Batch update playback state
    if (playing !== undefined) {
      dispatch(playerActions.setIsPlaying(playing));
    }
    if (position !== undefined) {
      dispatch(playerActions.setCurrentTime(position));
    }
    if (volume !== undefined) {
      dispatch(playerActions.setVolume(volume));
    }
    if (muted !== undefined) {
      dispatch(playerActions.setMuted(muted));
    }
    if (preset !== undefined) {
      dispatch(playerActions.setPreset(preset));
    }
    if (currentTrack !== undefined) {
      dispatch(playerActions.setCurrentTrack(currentTrack));
    }
  },

  // ========================================================================
  // Health Check / Heartbeat
  // ========================================================================

  [MessageType.HEALTH_CHECK]: (message, dispatch) => {
    // Server ping - acknowledged by connection handler
    // Update latency measurement
    const { latency = 0 } = message.payload || {};
    if (latency > 0) {
      dispatch(connectionActions.setLatency(latency));
    }
  },

  // ========================================================================
  // Notification Messages
  // ========================================================================

  [MessageType.NOTIFICATION]: (message) => {
    const { message: text, severity } = message.payload || {};
    // Notifications are typically handled by Toast provider
    // This is for Redux tracking if needed
    console.log(`[NOTIFICATION] ${severity || 'info'}: ${text}`);
  },

  // ========================================================================
  // Error Handling
  // ========================================================================

  [MessageType.ERROR]: (message, dispatch) => {
    const { error, context } = message.payload || {};

    // Route error to appropriate slice based on context
    switch (context) {
      case 'player':
        dispatch(playerActions.setError(error));
        break;
      case 'queue':
        dispatch(queueActions.setError(error));
        break;
      case 'cache':
        dispatch(cacheActions.setError(error));
        break;
      case 'connection':
        dispatch(connectionActions.setError(error));
        break;
      default:
        // Generic error
        console.error('[WS Error]', error);
    }
  },
});

// ============================================================================
// WebSocket Redux Middleware Factory
// ============================================================================

/**
 * Creates middleware that synchronizes WebSocket messages to Redux store
 */
export function createWebSocketMiddleware(protocolClient: any) {
  const offlineQueue = new OfflineMessageQueue();
  const handlers = createMessageHandlers();
  let isConnected = false;

  return (api: MiddlewareAPI<Dispatch, RootState>) => {
    // ======================================================================
    // Setup Connection Listeners
    // ======================================================================

    /**
     * Handle connection changes
     */
    const handleConnectionChange = (connected: boolean) => {
      isConnected = connected;
      api.dispatch(connectionActions.setWSConnected(connected));

      if (connected) {
        // Connection restored - process offline queue
        processOfflineQueue();
        api.dispatch(connectionActions.resetReconnectAttempts());
      } else {
        // Connection lost
        api.dispatch(connectionActions.incrementReconnectAttempts());
      }
    };

    /**
     * Handle WebSocket errors
     */
    const handleError = (error: Error) => {
      console.error('[WebSocket Error]', error.message);
      api.dispatch(connectionActions.setError(error.message));
    };

    /**
     * Process messages queued while offline
     */
    const processOfflineQueue = () => {
      const messages = offlineQueue.dequeueAll();
      console.log(`[Offline Queue] Processing ${messages.length} queued messages`);

      messages.forEach((message) => {
        processMessage(message);
      });
    };

    /**
     * Process a single WebSocket message
     */
    const processMessage = (message: WSMessage) => {
      const handler = handlers[message.type];

      if (handler) {
        try {
          const state = api.getState();
          handler(message, api.dispatch, state, api.getState);
        } catch (error) {
          console.error(`[Message Handler Error] ${message.type}:`, error);
          api.dispatch(
            connectionActions.setError(
              `Failed to process message: ${message.type}`
            )
          );
        }
      } else {
        console.warn(`[WebSocket] Unhandled message type: ${message.type}`);
      }
    };

    // Setup listeners if protocol client available
    if (protocolClient) {
      protocolClient.onConnectionChange(handleConnectionChange);
      protocolClient.onError(handleError);

      // Subscribe to all message types
      Object.values(MessageType).forEach((type) => {
        protocolClient.on(type, (message: WSMessage) => {
          if (isConnected) {
            processMessage(message);
          } else {
            // Queue message for later processing
            offlineQueue.enqueue(message);
          }
        });
      });
    }

    // ======================================================================
    // Middleware Return Function
    // ======================================================================

    return (next: (action: unknown) => unknown) => (action: unknown): unknown => {
      // Allow action to pass through
      const result = next(action);

      // Handle Redux actions that need WebSocket synchronization
      // (This would be for optimistic updates - send to server)

      // Track state mutations for debugging
      if (process.env.NODE_ENV === 'development') {
        const act = action as Record<string, any>;
        console.debug('[Redux] Action:', act.type, 'Payload:', act.payload);
      }

      return result;
    };
  };
}

// ============================================================================
// Optimistic Update Handler
// ============================================================================

/**
 * Handles optimistic updates - update local state before server confirmation
 */
export interface OptimisticUpdate {
  action: any;
  rollback: any;
  confirm?: any;
}

/**
 * Queue for tracking optimistic updates pending server confirmation
 */
export class OptimisticUpdateQueue {
  private updates: Map<string, OptimisticUpdate> = new Map();

  enqueue(correlationId: string, update: OptimisticUpdate): void {
    this.updates.set(correlationId, update);
  }

  confirm(correlationId: string): OptimisticUpdate | undefined {
    const update = this.updates.get(correlationId);
    if (update) {
      this.updates.delete(correlationId);
    }
    return update;
  }

  rollback(correlationId: string): OptimisticUpdate | undefined {
    const update = this.updates.get(correlationId);
    if (update) {
      this.updates.delete(correlationId);
    }
    return update;
  }

  clear(): void {
    this.updates.clear();
  }

  size(): number {
    return this.updates.size;
  }
}

