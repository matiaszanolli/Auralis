/**
 * WebSocket Protocol Client
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * TypeScript client implementing the Phase B.3 WebSocket protocol
 * with message handling, connection management, and heartbeat support.
 *
 * Phase C.1: Frontend Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { v4 as uuidv4 } from 'uuid';

// ============================================================================
// Protocol Types (matching backend)
// ============================================================================

export enum MessageType {
  PING = 'ping',
  PONG = 'pong',
  CONNECT = 'connect',
  DISCONNECT = 'disconnect',
  ERROR = 'error',

  PLAY = 'play',
  PAUSE = 'pause',
  STOP = 'stop',
  SEEK = 'seek',
  NEXT = 'next',
  PREVIOUS = 'previous',

  QUEUE_ADD = 'queue_add',
  QUEUE_REMOVE = 'queue_remove',
  QUEUE_CLEAR = 'queue_clear',
  QUEUE_REORDER = 'queue_reorder',

  LIBRARY_SYNC = 'library_sync',
  LIBRARY_SEARCH = 'library_search',

  CACHE_STATUS = 'cache_status',
  CACHE_STATS = 'cache_stats',

  NOTIFICATION = 'notification',

  STATUS_UPDATE = 'status_update',
  HEALTH_CHECK = 'health_check',
}

export enum MessagePriority {
  CRITICAL = 'critical',
  HIGH = 'high',
  NORMAL = 'normal',
  LOW = 'low',
}

export interface WSMessage {
  type: MessageType | string;
  correlation_id: string;
  timestamp: string;
  priority: MessagePriority;
  payload?: Record<string, any>;
  response_required?: boolean;
  timeout_seconds?: number;
  retry_count?: number;
  max_retries?: number;
}

// ============================================================================
// Message Handler Types
// ============================================================================

export type MessageHandler = (message: WSMessage) => Promise<void> | void;
export type ErrorHandler = (error: Error) => void;
export type ConnectionHandler = (connected: boolean) => void;

// ============================================================================
// WebSocket Protocol Client
// ============================================================================

export class WebSocketProtocolClient {
  private ws: WebSocket | null = null;
  private url: string;
  private messageHandlers: Map<MessageType | string, Set<MessageHandler>> = new Map();
  private pendingResponses: Map<string, { resolve: Function; reject: Function; timeout: NodeJS.Timeout }> =
    new Map();
  private connectionHandlers: Set<ConnectionHandler> = new Set();
  private errorHandlers: Set<ErrorHandler> = new Set();
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private heartbeatTimeout: NodeJS.Timeout | null = null;
  // Unsubscribe fn for the PONG handler registered by startHeartbeat().
  // Stored so stopHeartbeat() can remove it; without this, each reconnect
  // adds an extra anonymous handler that is never garbage-collected (fixes #2486).
  private pongUnsubscribe: (() => void) | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private isIntentionallyClosed = false;

  constructor(url: string) {
    this.url = url;
  }

  /**
   * Connect to WebSocket server
   */
  async connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url);
        this.isIntentionallyClosed = false;

        this.ws.onopen = () => {
          console.log('[WS] Connected to server');
          this.reconnectAttempts = 0;
          this.startHeartbeat();
          this.notifyConnectionHandlers(true);
          resolve();
        };

        this.ws.onmessage = (event) => {
          this.handleMessage(JSON.parse(event.data));
        };

        this.ws.onerror = (_event) => {
          const error = new Error('WebSocket error');
          this.notifyErrorHandlers(error);
          reject(error);
        };

        this.ws.onclose = () => {
          console.log('[WS] Disconnected from server');
          this.stopHeartbeat();
          this.notifyConnectionHandlers(false);

          // Attempt to reconnect if not intentionally closed
          if (!this.isIntentionallyClosed) {
            this.attemptReconnect();
          }
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    this.isIntentionallyClosed = true;
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Send a message to the server
   */
  async send(
    type: MessageType | string,
    payload?: Record<string, any>,
    options?: {
      priority?: MessagePriority;
      responseRequired?: boolean;
      timeout?: number;
    }
  ): Promise<WSMessage | undefined> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket not connected');
    }

    const message: WSMessage = {
      type,
      correlation_id: uuidv4(),
      timestamp: new Date().toISOString(),
      priority: options?.priority ?? MessagePriority.NORMAL,
      payload,
      response_required: options?.responseRequired ?? false,
      timeout_seconds: options?.timeout ?? 30,
    };

    this.ws.send(JSON.stringify(message));

    // If response is required, wait for it
    if (message.response_required) {
      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          this.pendingResponses.delete(message.correlation_id);
          reject(new Error(`Response timeout for ${type}`));
        }, (options?.timeout ?? 30) * 1000);

        this.pendingResponses.set(message.correlation_id, { resolve, reject, timeout });
      });
    }

    return undefined;
  }

  /**
   * Subscribe to a message type
   */
  on(type: MessageType | string, handler: MessageHandler): () => void {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, new Set());
    }
    this.messageHandlers.get(type)!.add(handler);

    // Return unsubscribe function
    return () => {
      this.messageHandlers.get(type)?.delete(handler);
    };
  }

  /**
   * Subscribe to connection events
   */
  onConnectionChange(handler: ConnectionHandler): () => void {
    this.connectionHandlers.add(handler);
    return () => this.connectionHandlers.delete(handler);
  }

  /**
   * Subscribe to errors
   */
  onError(handler: ErrorHandler): () => void {
    this.errorHandlers.add(handler);
    return () => this.errorHandlers.delete(handler);
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  // ============================================================================
  // Private Methods
  // ============================================================================

  private async handleMessage(message: WSMessage): Promise<void> {
    // Handle response to pending request
    if (this.pendingResponses.has(message.correlation_id)) {
      const { resolve, timeout } = this.pendingResponses.get(message.correlation_id)!;
      clearTimeout(timeout);
      this.pendingResponses.delete(message.correlation_id);
      resolve(message);
      return;
    }

    // Route to message handlers
    const handlers = this.messageHandlers.get(message.type) ?? new Set();
    for (const handler of handlers) {
      try {
        await handler(message);
      } catch (error) {
        this.notifyErrorHandlers(
          error instanceof Error ? error : new Error(String(error))
        );
      }
    }
  }

  private startHeartbeat(): void {
    this.heartbeatInterval = setInterval(() => {
      if (this.isConnected()) {
        this.send(MessageType.PING, {}, { priority: MessagePriority.CRITICAL }).catch((error) => {
          this.notifyErrorHandlers(error);
        });

        // Set timeout for pong response
        this.heartbeatTimeout = setTimeout(() => {
          if (this.isConnected()) {
            console.warn('[WS] Heartbeat timeout - reconnecting');
            this.ws?.close();
          }
        }, 10000);
      }
    }, 30000);

    // Remove any stale PONG handler from a previous connection before registering
    // a fresh one. Without this, each reconnect accumulates an extra handler in the
    // Set that is never removed for the lifetime of the singleton (fixes #2486).
    this.pongUnsubscribe?.();
    this.pongUnsubscribe = this.on(MessageType.PONG, () => {
      if (this.heartbeatTimeout) {
        clearTimeout(this.heartbeatTimeout);
      }
    });
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
    if (this.heartbeatTimeout) {
      clearTimeout(this.heartbeatTimeout);
      this.heartbeatTimeout = null;
    }
    this.pongUnsubscribe?.();
    this.pongUnsubscribe = null;
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WS] Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

    console.log(`[WS] Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);

    setTimeout(() => {
      this.connect().catch((error) => {
        this.notifyErrorHandlers(error);
      });
    }, delay);
  }

  private notifyConnectionHandlers(connected: boolean): void {
    for (const handler of this.connectionHandlers) {
      try {
        handler(connected);
      } catch (error) {
        console.error('[WS] Error in connection handler:', error);
      }
    }
  }

  private notifyErrorHandlers(error: Error): void {
    for (const handler of this.errorHandlers) {
      try {
        handler(error);
      } catch (err) {
        console.error('[WS] Error in error handler:', err);
      }
    }
  }
}

// ============================================================================
// Singleton Instance
// ============================================================================

let protocolClient: WebSocketProtocolClient | null = null;

export function initializeWebSocketProtocol(url: string): WebSocketProtocolClient {
  if (!protocolClient) {
    protocolClient = new WebSocketProtocolClient(url);
  }
  return protocolClient;
}

export function getWebSocketProtocol(): WebSocketProtocolClient {
  if (!protocolClient) {
    throw new Error('WebSocket protocol not initialized. Call initializeWebSocketProtocol first.');
  }
  return protocolClient;
}

export function resetWebSocketProtocol(): void {
  if (protocolClient) {
    protocolClient.disconnect();
    protocolClient = null;
  }
}
