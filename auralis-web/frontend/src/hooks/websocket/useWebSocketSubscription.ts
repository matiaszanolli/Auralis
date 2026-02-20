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

import { useEffect, useState, useRef } from 'react';
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

// Hooks that mount before the manager is set register here so they can
// subscribe lazily once setWebSocketManager() is called (issue #2396).
type ManagerReadyListener = (manager: WebSocketSubscriptionManager) => void;
const managerReadyListeners: Set<ManagerReadyListener> = new Set();

/**
 * Set the global WebSocket subscription manager.
 * Call this in your root App component after establishing WebSocket connection.
 * Any hooks that were waiting for the manager (startup race condition) will
 * subscribe immediately when this is called.
 * Passing null clears all pending listeners (e.g. on disconnect / test teardown).
 */
export function setWebSocketManager(manager: WebSocketSubscriptionManager | null): void {
  globalWebSocketManager = manager;
  if (manager) {
    // Snapshot without clearing — listeners persist for future reconnects (#2458).
    // This prevents infinite loops if a listener itself calls setWebSocketManager.
    const snapshot = new Set(managerReadyListeners);
    snapshot.forEach((listener) => listener(manager));
  }
  // On null: leave listeners intact so hooks re-subscribe on next manager (#2458).
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
 * If the global manager is not yet set when this hook mounts, the subscription
 * is deferred until setWebSocketManager() is called (startup race condition fix
 * for issue #2396). A console.warn is emitted so the deferred state is visible
 * during development.
 *
 * @param messageTypes - Array of message types to subscribe to
 * @param callback - Function called when message is received
 * @returns Unsubscribe function (usually called automatically on unmount)
 */
export function useWebSocketSubscription(
  messageTypes: WebSocketMessageType[],
  callback: (message: WebSocketMessage) => void
): () => void {
  // Use a ref to always hold the latest callback without recreating the subscription.
  // useCallback(callback, [callback]) is a no-op for inline callbacks and causes
  // unsubscribe+resubscribe on every parent render (fixes #2464).
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  const unsubscribeRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    let isActive = true;
    // Stable wrapper that delegates to the latest callbackRef without changing identity.
    const stableCallback = (msg: WebSocketMessage) => callbackRef.current(msg);

    function subscribeToManager(manager: WebSocketSubscriptionManager): void {
      if (!isActive) return;
      // Unsubscribe from previous manager first (reconnect path, fixes #2458).
      unsubscribeRef.current?.();
      unsubscribeRef.current = null;
      const unsubscribe = manager.subscribe(messageTypes, stableCallback);
      unsubscribeRef.current = unsubscribe;
    }

    // Always register for reconnect support, even if manager already exists (#2458).
    managerReadyListeners.add(subscribeToManager);

    const manager = getWebSocketManager();
    if (manager) {
      subscribeToManager(manager);
    } else {
      // Warn so the deferred state is visible during development (issue #2396).
      console.warn(
        '[useWebSocketSubscription] WebSocket manager not available yet. ' +
        'Subscription deferred until setWebSocketManager() is called (issue #2396).'
      );
    }

    return () => {
      isActive = false;
      // Remove from listeners for reconnect support.
      managerReadyListeners.delete(subscribeToManager);
      unsubscribeRef.current?.();
      unsubscribeRef.current = null;
    };
  }, [messageTypes]); // messageTypes is the only structural dependency; callback is via ref

  // Return a way to manually unsubscribe (rarely used)
  return () => {
    unsubscribeRef.current?.();
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
