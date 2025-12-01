/**
 * useWebSocketSubscription Hook
 *
 * Low-level hook for subscribing to WebSocket messages.
 * Automatically unsubscribes on unmount.
 *
 * Usage:
 *   const unsubscribe = useWebSocketSubscription(
 *     ['player_state', 'playback_started'],
 *     (message) => {
 *       console.log('Message received:', message);
 *     }
 *   );
 */

import { useEffect, useCallback, useState } from 'react';
import type { WebSocketMessage, WebSocketMessageType } from '../../types/websocket';

// Global WebSocket connection (should be managed by WebSocketContext)
// For now, we'll accept it as a parameter or from context
interface WebSocketSubscriptionManager {
  subscribe(
    messageTypes: WebSocketMessageType[],
    callback: (message: WebSocketMessage) => void
  ): () => void;
}

let globalWebSocketManager: WebSocketSubscriptionManager | null = null;

/**
 * Set the global WebSocket subscription manager.
 * Call this in your root App component after establishing WebSocket connection.
 */
export function setWebSocketManager(manager: WebSocketSubscriptionManager): void {
  globalWebSocketManager = manager;
}

/**
 * Get the global WebSocket subscription manager.
 */
export function getWebSocketManager(): WebSocketSubscriptionManager | null {
  return globalWebSocketManager;
}

/**
 * Subscribe to WebSocket messages.
 * Automatically unsubscribes when component unmounts.
 *
 * @param messageTypes - Array of message types to subscribe to
 * @param callback - Function called when message is received
 * @returns Unsubscribe function (usually called automatically on unmount)
 */
export function useWebSocketSubscription(
  messageTypes: WebSocketMessageType[],
  callback: (message: WebSocketMessage) => void
): () => void {
  // Memoize the callback to prevent re-subscribing unnecessarily
  const memoizedCallback = useCallback(callback, [callback]);

  useEffect(() => {
    const manager = getWebSocketManager();

    if (!manager) {
      // Silently return - this hook is legacy code
      // The new WebSocketContext handles subscriptions
      return;
    }

    // Subscribe to messages
    const unsubscribe = manager.subscribe(messageTypes, memoizedCallback);

    // Unsubscribe on unmount
    return unsubscribe;
  }, [messageTypes, memoizedCallback]);

  // Return a way to manually unsubscribe (rarely used)
  return () => {
    const manager = getWebSocketManager();
    if (manager) {
      manager.subscribe(messageTypes, memoizedCallback);
    }
  };
}

/**
 * Hook to subscribe to a single message type.
 * Convenience wrapper around useWebSocketSubscription.
 */
export function useWebSocketMessage<T extends WebSocketMessageType>(
  messageType: T,
  callback: (message: Extract<WebSocketMessage, { type: T }>) => void
): void {
  useWebSocketSubscription([messageType], callback as (msg: WebSocketMessage) => void);
}

/**
 * Hook to get the latest message of a specific type.
 * Stores the most recent message in component state.
 */
export function useWebSocketLatestMessage<T extends WebSocketMessageType>(
  messageType: T
): Extract<WebSocketMessage, { type: T }> | null {
  const [latestMessage, setLatestMessage] = useState<
    Extract<WebSocketMessage, { type: T }> | null
  >(null);

  useWebSocketSubscription([messageType], (message) => {
    if (message.type === messageType) {
      setLatestMessage(message as Extract<WebSocketMessage, { type: T }>);
    }
  });

  return latestMessage;
}

/**
 * Hook to track WebSocket connection status.
 * Used by other hooks to determine if they should attempt operations.
 */
export interface WebSocketStatus {
  isConnected: boolean;
  isConnecting: boolean;
  lastError: Error | null;
  reconnectAttempts: number;
  latency: number; // milliseconds
}

let connectionStatusCallback: ((status: WebSocketStatus) => void) | null = null;

export function setConnectionStatusCallback(
  callback: (status: WebSocketStatus) => void
): void {
  connectionStatusCallback = callback;
}

export function useWebSocketStatus(): WebSocketStatus {
  const [status, setStatus] = useState<WebSocketStatus>({
    isConnected: false,
    isConnecting: false,
    lastError: null,
    reconnectAttempts: 0,
    latency: 0,
  });

  useEffect(() => {
    if (connectionStatusCallback) {
      connectionStatusCallback(status);
    }
  }, [status]);

  return status;
}
