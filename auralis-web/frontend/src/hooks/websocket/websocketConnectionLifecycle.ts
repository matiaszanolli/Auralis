/**
 * Singleton-manager construction and handler wiring for useWebSocketConnection (#6275).
 *
 * Neither piece touches React: the hook passes in the refs and setters it owns, so the reconnect
 * and handler logic can be read (and tested) apart from the mount/unmount bookkeeping.
 */

import type { MutableRefObject } from 'react';
import { DEFAULT_MAX_RECONNECT_ATTEMPTS, DEV_MAX_RECONNECT_ATTEMPTS } from '@/config/timing';
import { WebSocketManager } from '@/utils/errorHandling';
import {
  closeCurrentManager,
  connState,
  handleSocketFrame,
  replayQueueAndResume,
  type ConnectionStatus,
  type DispatchMessage,
  type OutgoingWebSocketMessage,
} from './websocketConnectionCore';

export interface SocketHandlerTargets {
  dispatchRef: MutableRefObject<DispatchMessage>;
  /** Guards setState after unmount. */
  mountedRef: MutableRefObject<boolean>;
  messageQueueRef: MutableRefObject<OutgoingWebSocketMessage[]>;
  setIsConnected: (connected: boolean) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
}

/**
 * Wire one hook instance's state and dispatch onto a manager.
 *
 * Applied on the reuse path too (#4522), not just at construction. `WebSocketManager.on()`
 * assigns a single handler slot per event rather than appending, so re-attaching replaces - it
 * cannot duplicate dispatches. A consumer that took the reuse path without this kept its
 * `mountedRef` and `dispatchRef` unwired: it would never see inbound frames and its
 * `isConnected` / `connectionStatus` would never move.
 */
export function attachSocketHandlers(
  manager: WebSocketManager,
  { dispatchRef, mountedRef, messageQueueRef, setIsConnected, setConnectionStatus }: SocketHandlerTargets
): void {
  // Inbound frames (text JSON + binary PCM): parsing/pairing/ping live in the core helper,
  // which dispatches via the latest provider callback.
  manager.on('message', (event) => {
    handleSocketFrame(event, manager, dispatchRef.current);
  });

  manager.on('open', () => {
    console.log('✅ WebSocket connected (singleton)');
    if (mountedRef.current) {
      setIsConnected(true);
      setConnectionStatus('connected');
    }
    // Flush the offline queue and re-issue the active stream (#2385/#3185/#3345).
    replayQueueAndResume(manager, messageQueueRef.current);
  });

  manager.on('error', (event: Event) => {
    console.error('❌ WebSocket error:', event);
    if (mountedRef.current) setConnectionStatus('error');
  });

  manager.on('close', () => {
    console.log('🔌 WebSocket disconnected (will auto-reconnect)');
    if (mountedRef.current) {
      setIsConnected(false);
      setConnectionStatus('disconnected');
    }
  });
}

/**
 * Build the app's WebSocketManager. Backoff delays and multiplier come from the manager's
 * defaults (utils/errorHandling.ts); only the dev attempt cap is overridden, to limit console
 * spam. ``onGaveUp`` runs after the exhausted manager has been retired.
 */
export function createSingletonManager(url: string, onGaveUp: () => void): WebSocketManager {
  const maxAttempts = import.meta.env.DEV ? DEV_MAX_RECONNECT_ATTEMPTS : DEFAULT_MAX_RECONNECT_ATTEMPTS;
  const manager: WebSocketManager = new WebSocketManager(url, {
    maxReconnectAttempts: maxAttempts,
    onReconnectAttempt: (attempt, delay) => {
      console.log(`🔄 Reconnection attempt ${attempt}/${maxAttempts} (waiting ${delay}ms)`);
    },
    onMaxAttemptsExceeded: () => {
      // Retire the exhausted manager (#4522). Widening the reuse guard to "a manager exists"
      // would otherwise strand the app on one that has permanently given up: it never
      // reconnects and, still being the singleton, no later connect() would replace it.
      console.warn('🔌 WebSocket gave up reconnecting - retiring the singleton');
      if (connState.manager === manager) closeCurrentManager();
      onGaveUp();
    },
  });
  return manager;
}
