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
 */

import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { WebSocketManager } from '@/utils/errorHandling';
import { WS_BASE_URL } from '@/config/api';
import type { AnyWebSocketMessage, AudioChunkMessage, WebSocketMessage, WebSocketMessageType } from '@/types/websocket';

// Re-export message types so existing consumers can still import from here
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
// Outgoing (client → server) message type
// ============================================================================

export interface OutgoingWebSocketMessage {
  type: string;
  data?: Record<string, unknown>;
}

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
  connectionStatus: 'connected' | 'connecting' | 'disconnected' | 'error';

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
}

// ============================================================================
// Create Context
// ============================================================================

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

// ============================================================================
// Singleton WebSocket Manager (survives React.StrictMode double-mounting)
// ============================================================================

/**
 * Module-level singleton to ensure only ONE WebSocket connection exists
 * even when React.StrictMode causes double-mounting in development.
 *
 * This prevents multiple WebSocket connections from being created during
 * hot reload or StrictMode testing.
 */
let singletonWSManager: WebSocketManager | null = null;
let singletonRefCount = 0; // Track number of active providers

/**
 * Pending audio_chunk_meta message — paired with the next binary frame.
 * Backend sends metadata as JSON text followed by raw PCM as binary.
 */
let pendingAudioChunkMeta: AudioChunkMessage | null = null;

/**
 * Module-level subscription maps (must be singletons to survive provider remounts)
 * When React.StrictMode remounts the provider, these stay intact so that
 * subscriptions registered before remount still receive messages.
 */
const singletonSubscriptions: Map<string, Set<MessageHandler>> = new Map();
const singletonGlobalHandlers: Set<MessageHandler> = new Set();

/**
 * Last active streaming command (play_enhanced / play_normal) sent while connected.
 * Stored as a singleton so it survives provider remounts (React.StrictMode).
 * Re-issued after every reconnect to restore audio stream (issue #2385).
 * Cleared when the client sends an explicit stop or pause.
 */
let singletonLastStreamCommand: OutgoingWebSocketMessage | null = null;
const singletonResumePositionGetters: Record<string, () => number> = {};

/**
 * Reset all WebSocket singletons - ONLY FOR TESTING
 * This must be called between tests to prevent memory leaks from accumulated
 * subscriptions and connections.
 */
export function resetWebSocketSingletons(): void {
  // Close existing connection
  if (singletonWSManager) {
    try {
      singletonWSManager.close();
    } catch {
      // Ignore errors during cleanup
    }
    singletonWSManager = null;
  }

  // Reset ref count
  singletonRefCount = 0;

  // Clear last stream command and resume position getters
  singletonLastStreamCommand = null;
  for (const key in singletonResumePositionGetters) {
    delete singletonResumePositionGetters[key];
  }

  // Clear pending binary metadata
  pendingAudioChunkMeta = null;

  // Clear all subscriptions
  singletonSubscriptions.clear();
  singletonGlobalHandlers.clear();
}

// ============================================================================
// WebSocket Provider Component
// ============================================================================

interface WebSocketProviderProps {
  children: React.ReactNode;
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
  const wsManagerRef = useRef<WebSocketManager | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'connecting' | 'disconnected' | 'error'>('disconnected');

  // Use module-level singleton subscriptions (survive provider remounts)
  // This fixes the bug where StrictMode remounting caused subscriptions to be lost
  const subscriptionsRef = useRef(singletonSubscriptions);
  const globalHandlersRef = useRef(singletonGlobalHandlers);

  // Message queue for sending during disconnection
  const messageQueueRef = useRef<OutgoingWebSocketMessage[]>([]);

  // Track if component is mounted to prevent setState after unmount
  const mountedRef = useRef(true);

  /**
   * Connect to WebSocket (Phase 4c: Uses WebSocketManager with Singleton Pattern)
   */
  const connect = useCallback(async () => {
    // Increment ref count (for cleanup tracking)
    singletonRefCount++;
    console.log(`🔌 WebSocket provider mounted (ref count: ${singletonRefCount})`);

    // Reuse existing singleton connection if available
    if (singletonWSManager?.isConnected()) {
      console.log('✅ Reusing existing WebSocket connection (singleton)');
      wsManagerRef.current = singletonWSManager;
      setIsConnected(true);
      setConnectionStatus('connected');
      return;
    }

    // Create new singleton connection if none exists
    console.log('🔌 Creating new WebSocket connection:', url);
    setConnectionStatus('connecting');

    try {
      // Create WebSocketManager with Phase 3c error handling
      // In development, limit reconnection attempts to reduce console spam
      const maxAttempts = process.env.NODE_ENV === 'development' ? 3 : 10;
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
      singletonWSManager = manager;
      wsManagerRef.current = manager;

      // Dispatch a parsed message to global and type-specific handlers
      const dispatchMessage = (message: AnyWebSocketMessage | WebSocketMessage) => {
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
      };

      // Setup message handler (text JSON and binary PCM frames)
      manager.on('message', ((event: MessageEvent) => {
        try {
          // Binary frame: raw PCM data following an audio_chunk_meta message
          if (event.data instanceof ArrayBuffer) {
            if (pendingAudioChunkMeta) {
              // Attach the binary payload to the pending metadata and dispatch
              // as an 'audio_chunk' message so existing subscribers work unchanged.
              const combined: AudioChunkMessage = {
                type: 'audio_chunk',
                data: {
                  ...pendingAudioChunkMeta.data,
                  pcm_binary: event.data,
                },
              };
              pendingAudioChunkMeta = null;
              dispatchMessage(combined);
            } else {
              console.warn('[WebSocket] Received binary frame without preceding audio_chunk_meta');
            }
            return;
          }

          // Handle Blob data (some browsers send binary as Blob)
          if (event.data instanceof Blob) {
            const meta = pendingAudioChunkMeta;
            event.data.arrayBuffer().then((buffer: ArrayBuffer) => {
              if (meta) {
                const combined: AudioChunkMessage = {
                  type: 'audio_chunk',
                  data: {
                    ...meta.data,
                    pcm_binary: buffer,
                  },
                };
                pendingAudioChunkMeta = null;
                dispatchMessage(combined);
              }
            });
            return;
          }

          // Text frame: JSON message
          const message: AnyWebSocketMessage | WebSocketMessage = JSON.parse(event.data);

          // If this is an audio_chunk_meta, stash it and wait for the binary frame.
          // The meta has the same data shape as AudioChunkMessage (minus pcm_binary/samples).
          if (message.type === 'audio_chunk_meta') {
            pendingAudioChunkMeta = message as unknown as AudioChunkMessage;
            return;
          }

          dispatchMessage(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      }) as (event: MessageEvent | Event) => void);

      // Setup open handler
      manager.on('open', () => {
        console.log('✅ WebSocket connected (singleton)');
        if (mountedRef.current) {
          setIsConnected(true);
          setConnectionStatus('connected');
        }

        // Send queued messages (commands sent while disconnected).
        // Track whether any queued message supersedes the saved stream command
        // so we don't re-issue a stale play after reconnect (#3345).
        let queueHadStreamCommand = false;
        while (messageQueueRef.current.length > 0) {
          const message = messageQueueRef.current.shift();
          if (message?.type === 'play_enhanced' || message?.type === 'play_normal') {
            singletonLastStreamCommand = message;
            queueHadStreamCommand = true;
          } else if (message?.type === 'stop' || message?.type === 'pause') {
            singletonLastStreamCommand = null;
            queueHadStreamCommand = true;
          }
          manager.send(JSON.stringify(message));
        }

        // Re-issue the last active stream command after reconnect (issue #2385).
        // Skip if the queue already contained a fresh play/stop command (#3345).
        // Inject the current playback position so the backend resumes from where
        // the user is listening, not from the beginning (#3185).
        if (singletonLastStreamCommand && !queueHadStreamCommand) {
          const resumePos = singletonResumePositionGetters[singletonLastStreamCommand.type]?.() ?? 0;
          const resumeCommand = {
            ...singletonLastStreamCommand,
            data: {
              ...(singletonLastStreamCommand.data ?? {}),
              start_position: resumePos,
            },
          };
          console.log(`🔄 Reconnected - re-issuing stream command: ${singletonLastStreamCommand.type} at ${resumePos.toFixed(1)}s`);
          manager.send(JSON.stringify(resumeCommand));
        }
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
   * Disconnect from WebSocket (with reference counting for singleton)
   */
  const disconnect = useCallback(() => {
    // Decrement ref count
    singletonRefCount = Math.max(0, singletonRefCount - 1);
    console.log(`🔌 WebSocket provider unmounted (ref count: ${singletonRefCount})`);

    // Only close singleton when last provider unmounts
    if (singletonRefCount === 0 && singletonWSManager) {
      console.log('🔌 Last provider unmounted - closing singleton WebSocket connection');
      singletonWSManager.close();
      singletonWSManager = null;
    }

    // Clear local ref
    wsManagerRef.current = null;
    setIsConnected(false);
    setConnectionStatus('disconnected');
  }, []);

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

  /**
   * Send message
   */
  const send = useCallback((message: OutgoingWebSocketMessage) => {
    if (wsManagerRef.current?.isConnected()) {
      // Track last active streaming command for reconnect resume (issue #2385).
      // Only track when connected: queued commands are replayed from the queue on
      // reconnect and must not be re-issued a second time via this mechanism.
      if (message?.type === 'play_enhanced' || message?.type === 'play_normal') {
        singletonLastStreamCommand = message;
      } else if (message?.type === 'stop' || message?.type === 'pause') {
        singletonLastStreamCommand = null;
      }
      wsManagerRef.current.send(JSON.stringify(message));
    } else {
      // Queue message for sending when connected
      console.warn('WebSocket not connected, queueing message');
      // An explicit stop/pause while disconnected cancels any pending stream resume
      // so that reconnect does not silently restart stopped/paused playback (issue #2385).
      if (message?.type === 'stop' || message?.type === 'pause') {
        singletonLastStreamCommand = null;
      }
      messageQueueRef.current.push(message);
    }
  }, []);

  // Connect on mount
  useEffect(() => {
    connect();

    // Cleanup on unmount
    return () => {
      mountedRef.current = false;
      disconnect();
    };
  }, [connect, disconnect]);

  const value: WebSocketContextValue = {
    isConnected,
    connectionStatus,
    subscribe,
    subscribeAll,
    send,
    connect,
    disconnect,
    setResumePositionGetter: (streamType: string, getter: (() => number) | null) => {
      if (getter) {
        singletonResumePositionGetters[streamType] = getter;
      } else {
        delete singletonResumePositionGetters[streamType];
      }
    },
  };

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
