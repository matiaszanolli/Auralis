/**
 * useWebSocketConnection - Connection lifecycle & reconnect/backoff
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Owns the transport half of the app's single WebSocket:
 * - Singleton WebSocketManager lifecycle (survives StrictMode double-mount)
 * - Exponential-backoff reconnection (delegated to WebSocketManager)
 * - Connection state (isConnected / connectionStatus)
 * - Outgoing send + message queue during disconnection
 * - Stream re-issue on reconnect + mid-stream config change (#2385/#3185/#3759)
 *
 * Inbound-frame parsing (binary PCM pairing, ping/pong) and the on-reconnect
 * queue replay live in `websocketConnectionCore` alongside the singleton state.
 * This hook is deliberately decoupled from the subscription/dispatch surface:
 * incoming messages are handed to the injected `dispatchMessage` callback, which
 * the WebSocketProvider wires to its subscription maps. Extracted from the
 * 605-line WebSocketContext so the reconnect path can be reviewed alone (#4297).
 */

import { DEFAULT_MAX_RECONNECT_ATTEMPTS, DEV_MAX_RECONNECT_ATTEMPTS } from '@/config/timing';
import { useCallback, useEffect, useRef, useState } from 'react';
import { WebSocketManager } from '@/utils/errorHandling';
import {
  closeCurrentManager,
  connState,
  handleSocketFrame,
  replayQueueAndResume,
  type ConnectionStatus,
  type DispatchMessage,
  type OutgoingWebSocketMessage,
} from '@/hooks/websocket/websocketConnectionCore';
import { useOutgoingChannel } from './useOutgoingChannel';

// Re-export the shared connection types + test reset so existing importers
// (WebSocketContext and its consumers) have a single import site.
export type {
  ConnectionStatus,
  DispatchMessage,
  OutgoingWebSocketMessage,
} from '@/hooks/websocket/websocketConnectionCore';
export { resetConnectionSingletons } from '@/hooks/websocket/websocketConnectionCore';

// ============================================================================
// Hook
// ============================================================================

export interface UseWebSocketConnectionOptions {
  /** Fully-resolved WebSocket URL to connect to. */
  url: string;
  /** Fan-out for parsed inbound messages. MUST be identity-stable. */
  dispatchMessage: DispatchMessage;
}

export interface UseWebSocketConnection {
  isConnected: boolean;
  connectionStatus: ConnectionStatus;
  connect: () => Promise<void>;
  disconnect: () => void;
  send: (message: OutgoingWebSocketMessage) => void;
  setResumePositionGetter: (streamType: string, getter: (() => number) | null) => void;
  reissueActiveStreamAs: (
    type: 'play_enhanced' | 'play_normal',
    dataOverrides?: Record<string, unknown>,
    startPositionOverride?: number
  ) => boolean;
}

export function useWebSocketConnection({
  url,
  dispatchMessage,
}: UseWebSocketConnectionOptions): UseWebSocketConnection {
  const wsManagerRef = useRef<WebSocketManager | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');

  // Message queue for sending during disconnection
  const messageQueueRef = useRef<OutgoingWebSocketMessage[]>([]);

  // Track if component is mounted to prevent setState after unmount
  const mountedRef = useRef(true);

  // Keep the latest dispatch callback reachable from the (stable) message
  // handler without rebuilding `connect`. The provider passes a stable
  // callback, but a ref keeps this robust if that ever changes.
  const dispatchRef = useRef(dispatchMessage);
  dispatchRef.current = dispatchMessage;

  /**
   * Wire this hook instance's state and dispatch onto a manager.
   *
   * Applied on the reuse path too (#4522), not just at construction.
   * `WebSocketManager.on()` assigns a single handler slot per event rather than
   * appending, so re-attaching replaces — it cannot duplicate dispatches. A
   * consumer that took the reuse path without this kept its `mountedRef` and
   * `dispatchRef` unwired: it would never see inbound frames and its
   * `isConnected` / `connectionStatus` would never move.
   */
  const attachHandlers = useCallback((manager: WebSocketManager) => {
    // Inbound frames (text JSON + binary PCM) — parsing/pairing/ping lives in
    // the core helper; it dispatches via the latest provider callback.
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
      // Only update state if component is still mounted
      if (mountedRef.current) {
        setConnectionStatus('error');
      }
    });

    manager.on('close', () => {
      console.log('🔌 WebSocket disconnected (will auto-reconnect)');
      // Only update state if component is still mounted
      if (mountedRef.current) {
        setIsConnected(false);
        setConnectionStatus('disconnected');
      }
    });
  }, []);

  /**
   * Connect to WebSocket (Uses WebSocketManager with singleton pattern).
   */
  const connect = useCallback(async () => {
    // Increment ref count (for cleanup tracking)
    connState.refCount++;
    console.log(`🔌 WebSocket provider mounted (ref count: ${connState.refCount})`);

    // A manager built for a DIFFERENT url is the one case where replacement is
    // genuinely intended — tear the old one down rather than overwrite it
    // (#4522). Every other path below reuses.
    if (connState.manager && connState.url !== url) {
      console.log('🔌 WebSocket URL changed - closing previous connection');
      closeCurrentManager();
    }

    // Reuse the existing singleton whenever one EXISTS — not only when it is
    // fully connected (#4522). The old `isConnected()` guard let any connect()
    // landing during the handshake or during reconnect backoff (up to 30 s per
    // attempt) build a second manager and overwrite the singleton reference,
    // orphaning the first with its live socket, its handlers and its reconnect
    // timer. Nothing could reach the orphan to close it, and its message
    // handler kept dispatching a duplicate copy of every inbound frame.
    if (connState.manager) {
      const manager = connState.manager;
      wsManagerRef.current = manager;
      attachHandlers(manager);

      if (manager.isConnected()) {
        console.log('✅ Reusing existing WebSocket connection (singleton)');
        setIsConnected(true);
        setConnectionStatus('connected');
        return;
      }

      // Handshaking or backing off: await the SAME handshake instead of
      // starting a competing one.
      console.log('⏳ Joining in-flight WebSocket connection (singleton)');
      setConnectionStatus('connecting');
      if (connState.connectPromise) {
        try {
          await connState.connectPromise;
        } catch {
          // The owning caller already reported it; our state comes from the
          // handlers attached above.
        }
      }
      return;
    }

    // Create new singleton connection if none exists
    console.log('🔌 Creating new WebSocket connection:', url);
    setConnectionStatus('connecting');

    try {
      // Create WebSocketManager with Phase 3c error handling.
      // In development, limit reconnection attempts to reduce console spam.
      const maxAttempts = import.meta.env.DEV
        ? DEV_MAX_RECONNECT_ATTEMPTS
        : DEFAULT_MAX_RECONNECT_ATTEMPTS;
      const manager = new WebSocketManager(url, {
        // Backoff delays and multiplier come from WebSocketManager's defaults
        // (utils/errorHandling.ts); only the dev attempt cap is overridden here.
        maxReconnectAttempts: maxAttempts,
        onReconnectAttempt: (attempt, delay) => {
          console.log(`🔄 Reconnection attempt ${attempt}/${maxAttempts} (waiting ${delay}ms)`);
        },
        onMaxAttemptsExceeded: () => {
          // Retire the exhausted manager (#4522). Widening the reuse guard to
          // "a manager exists" would otherwise strand the app on one that has
          // permanently given up — it never reconnects and, because it is still
          // the singleton, no later connect() would ever replace it.
          console.warn('🔌 WebSocket gave up reconnecting - retiring the singleton');
          if (connState.manager === manager) {
            closeCurrentManager();
          }
          if (mountedRef.current) {
            setIsConnected(false);
            setConnectionStatus('error');
          }
        },
      });

      // Store as singleton
      connState.manager = manager;
      connState.url = url;
      wsManagerRef.current = manager;

      attachHandlers(manager);

      const pending = manager.connect();
      connState.connectPromise = pending;
      try {
        await pending;
      } finally {
        // Only clear if we still own the slot — a URL change or a retirement
        // may have replaced it while we awaited.
        if (connState.connectPromise === pending) {
          connState.connectPromise = null;
        }
      }
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      setConnectionStatus('error');
    }
  }, [url, attachHandlers]);

  /**
   * Disconnect from WebSocket (with reference counting for singleton).
   */
  const disconnect = useCallback(() => {
    // Decrement ref count
    connState.refCount = Math.max(0, connState.refCount - 1);
    console.log(`🔌 WebSocket provider unmounted (ref count: ${connState.refCount})`);

    // Only close singleton when last provider unmounts
    if (connState.refCount === 0 && connState.manager) {
      console.log('🔌 Last provider unmounted - closing singleton WebSocket connection');
      // Routed through the shared teardown so `url` and `connectPromise` are
      // cleared with the manager (#4522) — a stale connectPromise would make
      // the next connect() await a handshake for a socket that no longer exists.
      closeCurrentManager();
    }

    // Clear local ref
    wsManagerRef.current = null;
    setIsConnected(false);
    setConnectionStatus('disconnected');
  }, []);

  // Connect on mount
  useEffect(() => {
    // Reset the mounted flag on every (re)mount. Under StrictMode the
    // mount→cleanup→remount cycle sets it false in the first cleanup; without
    // this reset it stays false forever and the re-subscribed open/close/error
    // handlers (all gated on mountedRef) never update isConnected/
    // connectionStatus again (#4436).
    mountedRef.current = true;
    connect();

    // Cleanup on unmount
    return () => {
      mountedRef.current = false;
      disconnect();
    };
  }, [connect, disconnect]);

  const { send, setResumePositionGetter, reissueActiveStreamAs } = useOutgoingChannel(
    wsManagerRef,
    messageQueueRef
  );

  return {
    isConnected,
    connectionStatus,
    connect,
    disconnect,
    send,
    setResumePositionGetter,
    reissueActiveStreamAs,
  };
}
