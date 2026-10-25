/**
 * Error Handling Utilities for Frontend Services
 *
 * Provides:
 * - WebSocket error handling and reconnection
 *
 * The React Query retry rule (isRetryableError, shouldRetryQuery) moved to
 * `queryRetry.ts` (#5841).
 *
 * Used by: WebSocketManager — hooks/websocket (websocketConnectionCore,
 * useWebSocketConnection).
 */

import { DEFAULT_MAX_RECONNECT_ATTEMPTS } from '@/config/timing';

// ============================================================================
// Types
// ============================================================================

export interface WebSocketErrorConfig {
  maxReconnectAttempts: number;
  initialReconnectDelayMs: number;
  maxReconnectDelayMs: number;
  backoffMultiplier: number;
  onReconnectAttempt?: (attempt: number, delay: number) => void;
  onMaxAttemptsExceeded?: () => void;
}

// ============================================================================
// Default Configurations
// ============================================================================

const DEFAULT_WEBSOCKET_CONFIG: WebSocketErrorConfig = {
  maxReconnectAttempts: DEFAULT_MAX_RECONNECT_ATTEMPTS,
  initialReconnectDelayMs: 1000,
  maxReconnectDelayMs: 30000,
  backoffMultiplier: 2,
};

/**
 * Close codes whose rejection is permanent policy rather than transient
 * failure: the server refused this client and will refuse every retry, so
 * reconnecting cannot succeed (#5469). The backend closes with 1008 (Policy
 * Violation) for an untrusted or empty non-loopback Origin
 * (auralis-web/backend/config/globals.py). Transient codes (1000/1001/1006,
 * server errors) keep the normal retry path.
 */
const POLICY_CLOSE_CODES: ReadonlySet<number> = new Set([1008]);

// ============================================================================
// WebSocket Connection Management
// ============================================================================

/**
 * Handler shapes per event (#5639). `on()` keys its parameters on this map,
 * so registering a handler whose shape doesn't match its event — a `message`
 * handler of `() => void`, an `open` handler expecting an event — is a
 * compile error instead of something the old switch force-cast into place.
 * Fewer parameters still compiles (any `() => void` handler is valid for
 * `message` too), which is ordinary function variance, not a loophole.
 */
export interface WebSocketEventHandlers {
  open: () => void;
  close: () => void;
  message: (event: MessageEvent) => void;
  error: (error: Event) => void;
}

export class WebSocketManager {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  /** Set by close(): an intentional disconnect must never schedule a retry (#5602). */
  private closed = false;
  private config: WebSocketErrorConfig;
  private url: string;
  /** One handler slot per event, keyed by name (#5639). */
  private handlers: Partial<WebSocketEventHandlers> = {};

  constructor(url: string, config: Partial<WebSocketErrorConfig> = {}) {
    this.url = url;
    this.config = { ...DEFAULT_WEBSOCKET_CONFIG, ...config };
  }

  /**
   * Connect to WebSocket with automatic reconnection
   *
   * Retries are driven solely by the socket's `close` event via
   * attemptReconnect(); the returned promise only reports this attempt's
   * outcome to the caller (#5602). A refused connection fires `error` then
   * `close`, so scheduling from both used to burn the retry budget twice per
   * failure and leave several timers (and live sockets) racing.
   */
  async connect(): Promise<void> {
    this.closed = false;
    this.detachSocket();
    return new Promise((resolve, reject) => {
      try {
        const ws = new WebSocket(this.url);
        this.ws = ws;
        // Receive binary frames as ArrayBuffer (not Blob) for zero-copy PCM decoding
        ws.binaryType = 'arraybuffer';

        ws.onopen = () => {
          console.log('[WebSocketManager] Connected');
          this.reconnectAttempts = 0;
          this.startHeartbeat();
          this.handlers.open?.();
          resolve();
        };

        ws.onerror = (error) => {
          console.error('[WebSocketManager] Error:', error);
          this.handlers.error?.(error);
          reject(error);
        };

        ws.onmessage = (event) => {
          this.handlers.message?.(event);
        };

        ws.onclose = (event: CloseEvent) => {
          console.log(`[WebSocketManager] Disconnected (code ${event.code})`);
          this.stopHeartbeat();
          this.handlers.close?.();
          if (POLICY_CLOSE_CODES.has(event.code)) {
            // Retry-futile rejection: signal permanent failure immediately
            // through the same channel as exhausting the retry budget, so the
            // hook retires the singleton and surfaces its 'error' status
            // instead of looping a connection the server will keep rejecting.
            console.error(`[WebSocketManager] Close code ${event.code} is permanent — not reconnecting`);
            this.config.onMaxAttemptsExceeded?.();
            return;
          }
          this.attemptReconnect();
        };
      } catch (err) {
        // No socket was created, so no close event will ever drive a retry.
        this.attemptReconnect();
        reject(err);
      }
    });
  }

  /**
   * Detach and close the current socket so a replaced one cannot dispatch
   * messages, fire onOpen, or schedule reconnects behind the new socket's back.
   */
  private detachSocket(): void {
    const ws = this.ws;
    if (!ws) return;
    ws.onclose = null;
    ws.onopen = null;
    ws.onerror = null;
    ws.onmessage = null;
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
      ws.close();
    }
    this.ws = null;
  }

  /**
   * Attempt to reconnect with exponential backoff.
   *
   * Idempotent: at most one retry timer is pending, and nothing is scheduled
   * after close().
   */
  private attemptReconnect(): void {
    if (this.closed || this.reconnectTimeout !== null) return;

    if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
      console.error('[WebSocketManager] Max reconnection attempts exceeded');
      this.config.onMaxAttemptsExceeded?.();
      return;
    }

    const exponentialDelay = this.config.initialReconnectDelayMs *
      Math.pow(this.config.backoffMultiplier, this.reconnectAttempts);
    const delay = Math.min(exponentialDelay, this.config.maxReconnectDelayMs);

    this.reconnectAttempts++;

    console.log(`[WebSocketManager] Reconnection attempt ${this.reconnectAttempts}/${this.config.maxReconnectAttempts} in ${delay}ms`);
    this.config.onReconnectAttempt?.(this.reconnectAttempts, delay);

    this.reconnectTimeout = setTimeout(() => {
      this.reconnectTimeout = null;
      // The failed attempt's close event schedules the next retry; this catch
      // only keeps the rejection from surfacing as unhandled.
      this.connect().catch(err => {
        console.error('[WebSocketManager] Reconnection failed:', err);
      });
    }, delay);
  }

  /**
   * Start heartbeat to detect stale connections
   */
  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        try {
          this.ws.send(JSON.stringify({ type: 'heartbeat' }));
        } catch (err) {
          console.warn('[WebSocketManager] Failed to send heartbeat:', err);
        }
      }
    }, 30000); // Every 30 seconds
  }

  /**
   * Stop heartbeat
   */
  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  /**
   * Register the handler for an event (#5639).
   *
   * The mapped signature ties `handler` to `event`: `on('message', handler)`
   * requires a `(event: MessageEvent) => void` handler, `on('open', ...)`
   * a `() => void` one. Assigning into the same-keyed record needs no cast —
   * the old `(eventName, any-handler)` union signature forced one `as` per
   * switch arm and accepted every mismatch silently.
   */
  on<E extends keyof WebSocketEventHandlers>(
    event: E,
    handler: WebSocketEventHandlers[E]
  ): void {
    this.handlers[event] = handler;
  }

  /**
   * Send message if connected
   */
  send(data: string | ArrayBufferLike): boolean {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(data);
        return true;
      } catch (err) {
        console.error('[WebSocketManager] Failed to send message:', err);
        return false;
      }
    }
    return false;
  }

  /**
   * Close connection
   */
  close(): void {
    this.closed = true;
    if (this.reconnectTimeout !== null) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    this.stopHeartbeat();
    // Handlers are nulled before closing so the close event cannot trigger a
    // reconnect — intentional disconnects must not retry.
    this.detachSocket();
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }
}

// ============================================================================
// Error Classification
// ============================================================================
