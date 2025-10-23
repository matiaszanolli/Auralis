/**
 * WebSocketContext - Unified WebSocket Management
 *
 * Provides a single WebSocket connection shared across the entire application.
 * Features:
 * - Single connection (no duplication)
 * - Subscription system for message types
 * - Automatic reconnection with exponential backoff
 * - Message queueing during disconnection
 * - TypeScript type safety
 */

import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';

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
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'connecting' | 'disconnected' | 'error'>('disconnected');

  // Subscription management
  const subscriptionsRef = useRef<Map<string, Set<MessageHandler>>>(new Map());
  const globalHandlersRef = useRef<Set<MessageHandler>>(new Set());

  // Reconnection management
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 10;
  const baseReconnectDelay = 1000; // 1 second

  // Message queue for sending during disconnection
  const messageQueueRef = useRef<any[]>([]);

  /**
   * Calculate exponential backoff delay
   */
  const getReconnectDelay = useCallback(() => {
    const attempt = reconnectAttemptsRef.current;
    const delay = Math.min(baseReconnectDelay * Math.pow(2, attempt), 30000); // Max 30 seconds
    return delay;
  }, []);

  /**
   * Connect to WebSocket
   */
  const connect = useCallback(() => {
    // Don't create multiple connections
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) {
      console.log('WebSocket already connected or connecting');
      return;
    }

    console.log('🔌 Connecting to WebSocket:', url);
    setConnectionStatus('connecting');

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('✅ WebSocket connected');
        setIsConnected(true);
        setConnectionStatus('connected');
        reconnectAttemptsRef.current = 0;

        // Send queued messages
        while (messageQueueRef.current.length > 0) {
          const message = messageQueueRef.current.shift();
          ws.send(JSON.stringify(message));
        }
      };

      ws.onmessage = (event) => {
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
      };

      ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        setConnectionStatus('error');
      };

      ws.onclose = () => {
        console.log('🔌 WebSocket disconnected');
        setIsConnected(false);
        setConnectionStatus('disconnected');
        wsRef.current = null;

        // Attempt reconnection with exponential backoff
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = getReconnectDelay();
          console.log(`🔄 Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1}/${maxReconnectAttempts})`);

          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current++;
            connect();
          }, delay);
        } else {
          console.error('❌ Max reconnection attempts reached');
          setConnectionStatus('error');
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      setConnectionStatus('error');
    }
  }, [url, getReconnectDelay]);

  /**
   * Disconnect from WebSocket
   */
  const disconnect = useCallback(() => {
    console.log('Disconnecting WebSocket');

    // Clear reconnection timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
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
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
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
