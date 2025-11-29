/**
 * useWebSocketProtocol Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * React hook for managing WebSocket connections using the Phase B.3 protocol.
 *
 * Phase C.1: Frontend Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import {
  getWebSocketProtocol,
  initializeWebSocketProtocol,
  MessageType,
  MessagePriority,
  WSMessage,
} from '@/services/websocket/protocolClient';

export interface UseWebSocketProtocolOptions {
  /**
   * WebSocket server URL (default: ws://localhost:8765/ws)
   */
  url?: string;
  /**
   * Auto-connect on mount
   */
  autoConnect?: boolean;
  /**
   * Callback on connection change
   */
  onConnectionChange?: (connected: boolean) => void;
  /**
   * Callback on error
   */
  onError?: (error: Error) => void;
}

/**
 * Hook for using WebSocket protocol
 */
export function useWebSocketProtocol(options: UseWebSocketProtocolOptions = {}) {
  const {
    url = `ws://${window.location.host}/ws`,
    autoConnect = true,
    onConnectionChange,
    onError,
  } = options;

  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const clientRef = useRef(getWebSocketProtocol());

  // Initialize and connect
  useEffect(() => {
    if (autoConnect) {
      (async () => {
        try {
          const client = initializeWebSocketProtocol(url);
          clientRef.current = client;

          // Set up connection handler
          const unsubscribeConnection = client.onConnectionChange((isConnected) => {
            setConnected(isConnected);
            onConnectionChange?.(isConnected);
          });

          // Set up error handler
          const unsubscribeError = client.onError((err) => {
            setError(err);
            onError?.(err);
          });

          // Connect
          await client.connect();

          // Clean up handlers on unmount
          return () => {
            unsubscribeConnection();
            unsubscribeError();
          };
        } catch (err) {
          const error = err instanceof Error ? err : new Error(String(err));
          setError(error);
          onError?.(error);
        }
      })();
    }

    return () => {
      // Don't disconnect on unmount - keep connection alive
    };
  }, [autoConnect, url, onConnectionChange, onError]);

  /**
   * Send a message
   */
  const send = useCallback(
    async (
      type: MessageType | string,
      payload?: Record<string, any>,
      options?: {
        priority?: MessagePriority;
        responseRequired?: boolean;
        timeout?: number;
      }
    ): Promise<WSMessage | undefined> => {
      try {
        return await clientRef.current.send(type, payload, options);
      } catch (err) {
        const error = err instanceof Error ? err : new Error(String(err));
        setError(error);
        onError?.(error);
        throw error;
      }
    },
    [onError]
  );

  /**
   * Subscribe to a message type
   */
  const subscribe = useCallback(
    (type: MessageType | string, handler: (message: WSMessage) => Promise<void> | void) => {
      return clientRef.current.on(type, handler);
    },
    []
  );

  /**
   * Disconnect
   */
  const disconnect = useCallback(() => {
    clientRef.current.disconnect();
    setConnected(false);
  }, []);

  /**
   * Reconnect
   */
  const reconnect = useCallback(async () => {
    try {
      await clientRef.current.connect();
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      setError(error);
      onError?.(error);
      throw error;
    }
  }, [onError]);

  return {
    connected,
    error,
    send,
    subscribe,
    disconnect,
    reconnect,
  };
}

// ============================================================================
// Specialized Hooks
// ============================================================================

/**
 * Hook for cache stats updates
 */
export function useCacheStatsUpdates(onUpdate?: (stats: any) => void) {
  const { subscribe } = useWebSocketProtocol({ autoConnect: true });

  useEffect(() => {
    const unsubscribe = subscribe(MessageType.CACHE_STATS, (message) => {
      onUpdate?.(message.payload);
    });

    return unsubscribe;
  }, [subscribe, onUpdate]);
}

/**
 * Hook for cache status updates
 */
export function useCacheStatusUpdates(onUpdate?: (status: any) => void) {
  const { subscribe } = useWebSocketProtocol({ autoConnect: true });

  useEffect(() => {
    const unsubscribe = subscribe(MessageType.CACHE_STATUS, (message) => {
      onUpdate?.(message.payload);
    });

    return unsubscribe;
  }, [subscribe, onUpdate]);
}

/**
 * Hook for player state updates
 */
export function usePlayerStateUpdates(onUpdate?: (state: any) => void) {
  const { subscribe } = useWebSocketProtocol({ autoConnect: true });

  useEffect(() => {
    const unsubscribe = subscribe(MessageType.STATUS_UPDATE, (message) => {
      onUpdate?.(message.payload);
    });

    return unsubscribe;
  }, [subscribe, onUpdate]);
}

/**
 * Hook for notifications
 */
export function useNotifications(onNotification?: (notification: any) => void) {
  const { subscribe } = useWebSocketProtocol({ autoConnect: true });

  useEffect(() => {
    const unsubscribe = subscribe(MessageType.NOTIFICATION, (message) => {
      onNotification?.(message.payload);
    });

    return unsubscribe;
  }, [subscribe, onNotification]);
}

/**
 * Hook for sending player commands
 */
export function usePlayerCommands() {
  const { send } = useWebSocketProtocol({ autoConnect: true });

  return {
    play: async (trackId?: number) =>
      send(MessageType.PLAY, { track_id: trackId }, { priority: MessagePriority.HIGH }),
    pause: async () =>
      send(MessageType.PAUSE, {}, { priority: MessagePriority.HIGH }),
    seek: async (position: number) =>
      send(MessageType.SEEK, { position }, { priority: MessagePriority.HIGH }),
    next: async () =>
      send(MessageType.NEXT, {}, { priority: MessagePriority.HIGH }),
    previous: async () =>
      send(MessageType.PREVIOUS, {}, { priority: MessagePriority.HIGH }),
  };
}

/**
 * Hook for queue operations
 */
export function useQueueCommands() {
  const { send } = useWebSocketProtocol({ autoConnect: true });

  return {
    add: async (trackIds: number[]) =>
      send(MessageType.QUEUE_ADD, { track_ids: trackIds }, { priority: MessagePriority.NORMAL }),
    remove: async (indices: number[]) =>
      send(MessageType.QUEUE_REMOVE, { indices }, { priority: MessagePriority.NORMAL }),
    clear: async () =>
      send(MessageType.QUEUE_CLEAR, {}, { priority: MessagePriority.NORMAL }),
    reorder: async (fromIndex: number, toIndex: number) =>
      send(
        MessageType.QUEUE_REORDER,
        { from_index: fromIndex, to_index: toIndex },
        { priority: MessagePriority.NORMAL }
      ),
  };
}

/**
 * Hook for library operations
 */
export function useLibraryCommands() {
  const { send } = useWebSocketProtocol({ autoConnect: true });

  return {
    sync: async () =>
      send(MessageType.LIBRARY_SYNC, {}, { priority: MessagePriority.NORMAL }),
    search: async (query: string) =>
      send(MessageType.LIBRARY_SEARCH, { query }, { priority: MessagePriority.NORMAL }),
  };
}
