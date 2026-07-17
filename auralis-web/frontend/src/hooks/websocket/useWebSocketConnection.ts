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

import { useCallback, useEffect, useRef, useState } from 'react';
import { WebSocketManager } from '@/utils/errorHandling';
import {
  connState,
  handleSocketFrame,
  replayQueueAndResume,
  type ConnectionStatus,
  type DispatchMessage,
  type OutgoingWebSocketMessage,
} from '@/hooks/websocket/websocketConnectionCore';

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
    dataOverrides?: Record<string, unknown>
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
   * Connect to WebSocket (Uses WebSocketManager with singleton pattern).
   */
  const connect = useCallback(async () => {
    // Increment ref count (for cleanup tracking)
    connState.refCount++;
    console.log(`🔌 WebSocket provider mounted (ref count: ${connState.refCount})`);

    // Reuse existing singleton connection if available
    if (connState.manager?.isConnected()) {
      console.log('✅ Reusing existing WebSocket connection (singleton)');
      wsManagerRef.current = connState.manager;
      setIsConnected(true);
      setConnectionStatus('connected');
      return;
    }

    // Create new singleton connection if none exists
    console.log('🔌 Creating new WebSocket connection:', url);
    setConnectionStatus('connecting');

    try {
      // Create WebSocketManager with Phase 3c error handling.
      // In development, limit reconnection attempts to reduce console spam.
      const maxAttempts = import.meta.env.DEV ? 3 : 10;
      const manager = new WebSocketManager(url, {
        maxReconnectAttempts: maxAttempts,
        initialReconnectDelayMs: 1000,
        backoffMultiplier: 2,
        maxReconnectDelayMs: 30000,
        onReconnectAttempt: (attempt, delay) => {
          console.log(`🔄 Reconnection attempt ${attempt}/${maxAttempts} (waiting ${delay}ms)`);
        },
      });

      // Store as singleton
      connState.manager = manager;
      wsManagerRef.current = manager;

      // Inbound frames (text JSON + binary PCM) — parsing/pairing/ping lives in
      // the core helper; it dispatches via the latest provider callback.
      manager.on('message', ((event: MessageEvent) => {
        handleSocketFrame(event, manager, dispatchRef.current);
      }) as (event: MessageEvent | Event) => void);

      // Setup open handler
      manager.on('open', () => {
        console.log('✅ WebSocket connected (singleton)');
        if (mountedRef.current) {
          setIsConnected(true);
          setConnectionStatus('connected');
        }
        // Flush the offline queue and re-issue the active stream (#2385/#3185/#3345).
        replayQueueAndResume(manager, messageQueueRef.current);
      });

      // Setup error handler
      manager.on('error', (event: Event) => {
        console.error('❌ WebSocket error:', event);
        // Only update state if component is still mounted
        if (mountedRef.current) {
          setConnectionStatus('error');
        }
      });

      // Setup close handler
      manager.on('close', () => {
        console.log('🔌 WebSocket disconnected (will auto-reconnect)');
        // Only update state if component is still mounted
        if (mountedRef.current) {
          setIsConnected(false);
          setConnectionStatus('disconnected');
        }
      });

      await manager.connect();
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      setConnectionStatus('error');
    }
  }, [url]);

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
      connState.manager.close();
      connState.manager = null;
    }

    // Clear local ref
    wsManagerRef.current = null;
    setIsConnected(false);
    setConnectionStatus('disconnected');
  }, []);

  /**
   * Send message (or queue it if disconnected).
   */
  const send = useCallback((message: OutgoingWebSocketMessage) => {
    if (wsManagerRef.current?.isConnected()) {
      // Track last active streaming command for reconnect resume (issue #2385).
      // Only track when connected: queued commands are replayed from the queue on
      // reconnect and must not be re-issued a second time via this mechanism.
      if (message?.type === 'play_enhanced' || message?.type === 'play_normal') {
        connState.lastStreamCommand = message;
      } else if (message?.type === 'stop' || message?.type === 'pause') {
        connState.lastStreamCommand = null;
      }
      wsManagerRef.current.send(JSON.stringify(message));
    } else {
      // Queue message for sending when connected
      console.warn('WebSocket not connected, queueing message');
      // An explicit stop/pause while disconnected cancels any pending stream resume
      // so that reconnect does not silently restart stopped/paused playback (issue #2385).
      if (message?.type === 'stop' || message?.type === 'pause') {
        connState.lastStreamCommand = null;
      }
      messageQueueRef.current.push(message);
    }
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

  // #3730: stable identity for setResumePositionGetter so the memoized context
  // value doesn't break on every render. The singleton getter map is
  // module-level so this callback never needs to close over component state.
  const setResumePositionGetter = useCallback(
    (streamType: string, getter: (() => number) | null) => {
      if (getter) {
        connState.resumeGetters[streamType] = getter;
      } else {
        delete connState.resumeGetters[streamType];
      }
    },
    []
  );

  // #3759 + #3763: re-issue the active stream with updated config.
  // Used when the user changes enhancement enabled/preset/intensity
  // mid-stream — backend binds those at processor construction so we
  // restart the stream from the current resume position. Reuses the
  // existing #3185 plumbing (lastStreamCommand + resumeGetters).
  const reissueActiveStreamAs = useCallback(
    (
      type: 'play_enhanced' | 'play_normal',
      dataOverrides: Record<string, unknown> = {}
    ): boolean => {
      const last = connState.lastStreamCommand;
      if (!last) return false;
      const prevData = (last.data ?? {}) as Record<string, unknown>;
      const trackId = prevData.track_id;
      if (trackId == null) return false;

      const resumePos = connState.resumeGetters[type]?.() ?? 0;
      const next: OutgoingWebSocketMessage = {
        type,
        data: {
          track_id: trackId,
          ...dataOverrides,
          start_position: resumePos,
        },
      };

      if (wsManagerRef.current?.isConnected()) {
        connState.lastStreamCommand = next;
        wsManagerRef.current.send(JSON.stringify(next));
      } else {
        // While disconnected, queue so the reconnect path picks the
        // most-recent config; update the tracked command so we don't
        // double-send on reconnect.
        connState.lastStreamCommand = next;
        messageQueueRef.current.push(next);
      }
      return true;
    },
    []
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
