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
export interface EnhancementToggledMessage extends WebSocketMessage {
  type: 'enhancement_toggled';
  data: {
    enabled: boolean;
    preset: string;
    intensity: number;
  };
}

export interface EnhancementPresetChangedMessage extends WebSocketMessage {
  type: 'enhancement_preset_changed';
  data: {
    preset: string;
    enabled: boolean;
    intensity: number;
  };
}

export interface EnhancementIntensityChangedMessage extends WebSocketMessage {
  type: 'enhancement_intensity_changed';
  data: {
    intensity: number;
    enabled: boolean;
    preset: string;
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
    status: string;
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

// Union type of all possible messages
export type AuralisWebSocketMessage =
  | PlayerStateMessage
  | EnhancementToggledMessage
  | EnhancementPresetChangedMessage
  | EnhancementIntensityChangedMessage
  | LibraryUpdatedMessage
  | ScanProgressMessage
  | PlaylistCreatedMessage
  | PlaylistUpdatedMessage
  | PlaylistDeletedMessage
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
// WebSocket Provider Component
// ============================================================================

interface WebSocketProviderProps {
  children: React.ReactNode;
  url?: string;
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({
  children,
  url = 'ws://localhost:8765/ws'
}) => {
  const wsManagerRef = useRef<WebSocketManager | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'connecting' | 'disconnected' | 'error'>('disconnected');

  // Subscription management
  const subscriptionsRef = useRef<Map<string, Set<MessageHandler>>>(new Map());
  const globalHandlersRef = useRef<Set<MessageHandler>>(new Set());

  // Message queue for sending during disconnection
  const messageQueueRef = useRef<any[]>([]);

  // Track if component is mounted to prevent setState after unmount
  const mountedRef = useRef(true);

  /**
   * Connect to WebSocket (Phase 4c: Uses WebSocketManager)
   */
  const connect = useCallback(async () => {
    // Don't create multiple managers
    if (wsManagerRef.current?.isConnected()) {
      console.log('WebSocket already connected or connecting');
      return;
    }

    console.log('🔌 Connecting to WebSocket:', url);
    setConnectionStatus('connecting');

    try {
      // Create WebSocketManager with Phase 3c error handling
      wsManagerRef.current = new WebSocketManager(url, {
        maxReconnectAttempts: 10,
        initialReconnectDelayMs: 1000,
        backoffMultiplier: 2,
        maxReconnectDelayMs: 30000,
        onReconnectAttempt: (attempt, delay) => {
          console.log(`🔄 Reconnection attempt ${attempt}/10 (waiting ${delay}ms)`);
        },
      });

      // Setup message handler
      wsManagerRef.current.on('message', ((event: MessageEvent) => {
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
      wsManagerRef.current.on('open', () => {
        console.log('✅ WebSocket connected');
        if (mountedRef.current) {
          setIsConnected(true);
          setConnectionStatus('connected');
        }

        // Send queued messages
        while (messageQueueRef.current.length > 0) {
          const message = messageQueueRef.current.shift();
          wsManagerRef.current?.send(JSON.stringify(message));
        }
      });

      // Setup error handler
      wsManagerRef.current.on('error', (event: Event) => {
        console.error('❌ WebSocket error:', event);
        // Only update state if component is still mounted
        if (mountedRef.current) {
          setConnectionStatus('error');
        }
      });

      // Setup close handler
      wsManagerRef.current.on('close', () => {
        console.log('🔌 WebSocket disconnected (will auto-reconnect)');
        // Only update state if component is still mounted
        if (mountedRef.current) {
          setIsConnected(false);
          setConnectionStatus('disconnected');
        }
      });

      await wsManagerRef.current.connect();
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      setConnectionStatus('error');
    }
  }, [url]);

  /**
   * Disconnect from WebSocket
   */
  const disconnect = useCallback(() => {
    console.log('Disconnecting WebSocket');

    // Close WebSocket using WebSocketManager
    if (wsManagerRef.current) {
      wsManagerRef.current.close();
      wsManagerRef.current = null;
    }

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
      wsManagerRef.current.send(JSON.stringify(message));
    } else {
      // Queue message for sending when connected
      console.warn('WebSocket not connected, queueing message');
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
