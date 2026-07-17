/**
 * WebSocketContext - Unified WebSocket Management (Phase 4c)
 *
 * Provides a single WebSocket connection shared across the entire application.
 * Features:
 * - Single connection (no duplication)
 * - Subscription system for message types
 * - Automatic reconnection with exponential backoff (via WebSocketManager)
 * - Message queueing during disconnection
 * - TypeScript type safety
 * - Centralized error handling (Phase 3c integration)
 *
 * #4297: the connection lifecycle / reconnect-backoff half lives in
 * `useWebSocketConnection`; this file is a thin provider that composes that
 * hook with the subscription/dispatch surface.
 */

import { ReactNode, createContext, useCallback, useContext, useMemo, useRef } from 'react';
import { WS_BASE_URL } from '@/config/api';
import {
  useWebSocketConnection,
  resetConnectionSingletons,
  type OutgoingWebSocketMessage,
  type ConnectionStatus,
} from '@/hooks/websocket/useWebSocketConnection';
import type { AnyWebSocketMessage, WebSocketMessage, WebSocketMessageType } from '@/types/websocket';

// Re-export message types so existing consumers can still import from here
export type { OutgoingWebSocketMessage } from '@/hooks/websocket/useWebSocketConnection';
export type { AnyWebSocketMessage } from '@/types/websocket';
export type {
  WebSocketMessage,
  AudioStreamStartMessage,
  AudioChunkMessage,
  AudioStreamEndMessage,
  AudioStreamErrorMessage,
  PlayerStateMessage,
  EnhancementSettingsChangedMessage,
  LibraryUpdatedMessage,
  ScanProgressMessage,
  PlaylistCreatedMessage,
  PlaylistUpdatedMessage,
  PlaylistDeletedMessage,
} from '@/types/websocket';

// ============================================================================
// Message Handler Type
// ============================================================================

export type MessageHandler = (message: AnyWebSocketMessage | WebSocketMessage) => void;

// ============================================================================
// WebSocket Context Interface
// ============================================================================

interface WebSocketContextValue {
  // Connection state
  isConnected: boolean;
  connectionStatus: ConnectionStatus;

  // Subscription management
  subscribe: (messageType: WebSocketMessageType, handler: MessageHandler) => () => void;
  subscribeAll: (handler: MessageHandler) => () => void;

  // Send messages
  send: (message: OutgoingWebSocketMessage) => void;

  // Manual connection control
  connect: () => void;
  disconnect: () => void;

  // Stream resumption: register a callback that returns current playback position (#3185)
  // Keyed by stream type to avoid race between usePlayEnhanced and usePlayNormal (#3373)
  setResumePositionGetter: (streamType: string, getter: (() => number) | null) => void;

  // #3759 + #3763: re-issue the active stream with updated config (preset,
  // intensity, or a stream-type swap on enhancement toggle) while
  // preserving playback position via the resume-position getter.
  // Returns false if no active stream is being tracked (e.g. nothing is
  // playing yet). The new command supersedes singletonLastStreamCommand
  // for subsequent reconnects.
  reissueActiveStreamAs: (
    type: 'play_enhanced' | 'play_normal',
    dataOverrides?: Record<string, unknown>
  ) => boolean;
}

// ============================================================================
// Create Context
// ============================================================================

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

// ============================================================================
// Singleton subscription maps (must be singletons to survive provider remounts)
// ============================================================================

/**
 * Module-level subscription maps (must be singletons to survive provider remounts)
 * When StrictMode remounts the provider, these stay intact so that
 * subscriptions registered before remount still receive messages.
 */
const singletonSubscriptions: Map<string, Set<MessageHandler>> = new Map();
const singletonGlobalHandlers: Set<MessageHandler> = new Set();

/**
 * Reset all WebSocket singletons - ONLY FOR TESTING
 * This must be called between tests to prevent memory leaks from accumulated
 * subscriptions and connections. Resets both the connection singletons (owned
 * by useWebSocketConnection) and the subscription maps owned here.
 */
export function resetWebSocketSingletons(): void {
  // Connection singletons (manager, ref count, stream command, resume getters,
  // pending binary metadata) live in the connection hook.
  resetConnectionSingletons();

  // Clear all subscriptions
  singletonSubscriptions.clear();
  singletonGlobalHandlers.clear();
}

// ============================================================================
// WebSocket Provider Component
// ============================================================================

interface WebSocketProviderProps {
  children: ReactNode;
  url?: string;
}

export const WebSocketProvider = ({
  children,
  url = (() => {
    // In development (Vite on localhost:3000+), connect directly to backend
    // Vite proxy for WebSocket can be unreliable, so we connect directly to the backend port
    // In production, use same host as frontend (backend serves both)
    if (window.location.hostname === 'localhost' && parseInt(window.location.port) >= 3000) {
      // Development: Connect directly to backend at 8765
      // Bypasses Vite proxy which can have WebSocket issues
      return `${WS_BASE_URL}/ws`
    } else {
      // Production: Use same host as frontend (backend serves both)
      return `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`
    }
  })()
}: WebSocketProviderProps) => {
  // Use module-level singleton subscriptions (survive provider remounts).
  // This fixes the bug where StrictMode remounting caused subscriptions to be lost.
  const subscriptionsRef = useRef(singletonSubscriptions);
  const globalHandlersRef = useRef(singletonGlobalHandlers);

  /**
   * Dispatch a parsed message to global and type-specific handlers. Identity is
   * stable (only closes over the module-singleton refs), so the connection hook
   * can hold it without rebuilding its socket handlers.
   */
  const dispatchMessage = useCallback((message: AnyWebSocketMessage | WebSocketMessage) => {
    // Call global handlers
    globalHandlersRef.current.forEach(handler => {
      try {
        handler(message);
      } catch (error) {
        console.error('Error in global WebSocket handler:', error);
      }
    });

    // Call type-specific handlers
    if (message.type) {
      const handlers = subscriptionsRef.current.get(message.type);
      if (handlers) {
        handlers.forEach(handler => {
          try {
            handler(message);
          } catch (error) {
            console.error(`Error in WebSocket handler for type "${message.type}":`, error);
          }
        });
      }
    }
  }, []);

  const {
    isConnected,
    connectionStatus,
    connect,
    disconnect,
    send,
    setResumePositionGetter,
    reissueActiveStreamAs,
  } = useWebSocketConnection({ url, dispatchMessage });

  /**
   * Subscribe to specific message type
   */
  const subscribe = useCallback((messageType: WebSocketMessageType, handler: MessageHandler) => {
    if (!subscriptionsRef.current.has(messageType)) {
      subscriptionsRef.current.set(messageType, new Set());
    }
    subscriptionsRef.current.get(messageType)!.add(handler);

    console.log(`📝 Subscribed to message type: ${messageType}`);

    // Return unsubscribe function
    return () => {
      const handlers = subscriptionsRef.current.get(messageType);
      if (handlers) {
        handlers.delete(handler);
        if (handlers.size === 0) {
          subscriptionsRef.current.delete(messageType);
        }
      }
      console.log(`📝 Unsubscribed from message type: ${messageType}`);
    };
  }, []);

  /**
   * Subscribe to all messages
   */
  const subscribeAll = useCallback((handler: MessageHandler) => {
    globalHandlersRef.current.add(handler);
    console.log('📝 Subscribed to all messages');

    // Return unsubscribe function
    return () => {
      globalHandlersRef.current.delete(handler);
      console.log('📝 Unsubscribed from all messages');
    };
  }, []);

  // #3730: memoize the context value so consumers of useWebSocketContext don't
  // re-render on every WebSocketProvider render. Each member is identity-stable
  // (useCallback / hook-returned), so the value identity tracks the genuine
  // state changes (isConnected, connectionStatus).
  const value = useMemo<WebSocketContextValue>(
    () => ({
      isConnected,
      connectionStatus,
      subscribe,
      subscribeAll,
      send,
      connect,
      disconnect,
      setResumePositionGetter,
      reissueActiveStreamAs,
    }),
    [
      isConnected,
      connectionStatus,
      subscribe,
      subscribeAll,
      send,
      connect,
      disconnect,
      reissueActiveStreamAs,
      setResumePositionGetter,
    ]
  );

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};

// ============================================================================
// Custom Hook to Use WebSocket Context
// ============================================================================

export const useWebSocketContext = (): WebSocketContextValue => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocketContext must be used within WebSocketProvider');
  }
  return context;
};

export default WebSocketContext;
