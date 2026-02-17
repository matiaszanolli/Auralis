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
import { WebSocketManager } from '../utils/errorHandling';

// ============================================================================
// TypeScript Types for WebSocket Messages
// ============================================================================

export interface WebSocketMessage {
  type: string;
  data?: any;
  timestamp?: number;
}

// Player State Messages
export interface PlayerStateMessage extends WebSocketMessage {
  type: 'player_state';
  data: {
    state: string;
    is_playing: boolean;
    is_paused: boolean;
    current_track: any;
    current_time: number;
    duration: number;
    volume: number;
    is_muted: boolean;
    queue: any[];
    queue_index: number;
    queue_size: number;
    shuffle_enabled: boolean;
    repeat_mode: string;
    mastering_enabled: boolean;
    current_preset: string;
  };
}

// Enhancement Messages
export interface EnhancementSettingsChangedMessage extends WebSocketMessage {
  type: 'enhancement_settings_changed';
  data: {
    enabled: boolean;
    preset: string;
    intensity: number;
  };
}

// Library Messages
export interface LibraryUpdatedMessage extends WebSocketMessage {
  type: 'library_updated';
  data: {
    action: string;
    track_count?: number;
  };
}

export interface ScanProgressMessage extends WebSocketMessage {
  type: 'scan_progress';
  data: {
    current: number;
    total: number;
    percentage: number;
    current_file?: string;
  };
}

// Playlist Messages
export interface PlaylistCreatedMessage extends WebSocketMessage {
  type: 'playlist_created';
  data: {
    playlist_id: number;
    name: string;
  };
}

export interface PlaylistUpdatedMessage extends WebSocketMessage {
  type: 'playlist_updated';
  data: {
    playlist_id: number;
    action: string;
  };
}

export interface PlaylistDeletedMessage extends WebSocketMessage {
  type: 'playlist_deleted';
  data: {
    playlist_id: number;
  };
}

// ============================================================================
// Audio Streaming Messages (Phase 2.2)
// ============================================================================

/**
 * Sent by backend when audio stream starts
 * Contains metadata needed to initialize PCMStreamBuffer and playback
 */
export interface AudioStreamStartMessage extends WebSocketMessage {
  type: 'audio_stream_start';
  data: {
    track_id: number;
    preset: string;
    intensity: number;
    sample_rate: number;
    channels: number;
    total_chunks: number;
    chunk_duration: number;
    total_duration: number;
    stream_type?: 'enhanced' | 'normal';
  };
}

/**
 * Sent by backend for each chunk of PCM audio
 * Contains base64-encoded PCM samples and frame metadata
 * Large chunks are split into multiple frames to stay under WebSocket 1MB limit
 */
export interface AudioChunkMessage extends WebSocketMessage {
  type: 'audio_chunk';
  data: {
    chunk_index: number;
    chunk_count: number;
    frame_index: number;
    frame_count: number;
    samples: string; // Base64-encoded float32 PCM samples
    sample_count: number; // Number of samples in this frame
    crossfade_samples: number; // Overlap duration at chunk boundary (only for first frame)
    stream_type?: 'enhanced' | 'normal';
  };
}

/**
 * Sent by backend when audio stream completes
 */
export interface AudioStreamEndMessage extends WebSocketMessage {
  type: 'audio_stream_end';
  data: {
    track_id: number;
    total_samples: number;
    duration: number;
    stream_type?: 'enhanced' | 'normal';
  };
}

/**
 * Sent by backend if stream fails
 */
export interface AudioStreamErrorMessage extends WebSocketMessage {
  type: 'audio_stream_error';
  data: {
    track_id: number;
    error: string;
    code: string;
    stream_type?: 'enhanced' | 'normal';
  };
}

// Union type of all possible messages
export type AuralisWebSocketMessage =
  | PlayerStateMessage
  | EnhancementSettingsChangedMessage
  | LibraryUpdatedMessage
  | ScanProgressMessage
  | PlaylistCreatedMessage
  | PlaylistUpdatedMessage
  | PlaylistDeletedMessage
  | AudioStreamStartMessage
  | AudioChunkMessage
  | AudioStreamEndMessage
  | AudioStreamErrorMessage
  | WebSocketMessage; // Fallback for unknown messages

// ============================================================================
// Message Handler Type
// ============================================================================

export type MessageHandler = (message: AuralisWebSocketMessage) => void;

// ============================================================================
// WebSocket Context Interface
// ============================================================================

interface WebSocketContextValue {
  // Connection state
  isConnected: boolean;
  connectionStatus: 'connected' | 'connecting' | 'disconnected' | 'error';

  // Subscription management
  subscribe: (messageType: string, handler: MessageHandler) => () => void;
  subscribeAll: (handler: MessageHandler) => () => void;

  // Send messages (for future use if needed)
  send: (message: any) => void;

  // Manual connection control
  connect: () => void;
  disconnect: () => void;
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
let singletonLastStreamCommand: any = null;

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

  // Clear last stream command
  singletonLastStreamCommand = null;

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

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({
  children,
  url = (() => {
    // In development (Vite on localhost:3000+), connect directly to backend
    // Vite proxy for WebSocket can be unreliable, so we connect directly to the backend port
    // In production, use same host as frontend (backend serves both)
    if (window.location.hostname === 'localhost' && parseInt(window.location.port) >= 3000) {
      // Development: Connect directly to backend at 8765
      // Bypasses Vite proxy which can have WebSocket issues
      return `ws://localhost:8765/ws`
    } else {
      // Production: Use same host as frontend (backend serves both)
      return `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`
    }
  })()
}) => {
  const wsManagerRef = useRef<WebSocketManager | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'connecting' | 'disconnected' | 'error'>('disconnected');

  // Use module-level singleton subscriptions (survive provider remounts)
  // This fixes the bug where StrictMode remounting caused subscriptions to be lost
  const subscriptionsRef = useRef(singletonSubscriptions);
  const globalHandlersRef = useRef(singletonGlobalHandlers);

  // Message queue for sending during disconnection
  const messageQueueRef = useRef<any[]>([]);

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

      // Setup message handler
      manager.on('message', ((event: MessageEvent) => {
        try {
          const message: AuralisWebSocketMessage = JSON.parse(event.data);

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

        // Send queued messages (commands sent while disconnected)
        while (messageQueueRef.current.length > 0) {
          const message = messageQueueRef.current.shift();
          manager.send(JSON.stringify(message));
        }

        // Re-issue the last active stream command after reconnect (issue #2385).
        // Only re-issues commands that were sent while connected (not queued ones,
        // which are already flushed above). Cleared by explicit stop/pause.
        if (singletonLastStreamCommand) {
          console.log(`🔄 Reconnected - re-issuing stream command: ${singletonLastStreamCommand.type}`);
          manager.send(JSON.stringify(singletonLastStreamCommand));
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
  const subscribe = useCallback((messageType: string, handler: MessageHandler) => {
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
  const send = useCallback((message: any) => {
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
    disconnect
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
