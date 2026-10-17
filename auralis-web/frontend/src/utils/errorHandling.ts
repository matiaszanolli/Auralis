/**
 * Error Handling Utilities for Frontend Services
 *
 * Provides:
 * - WebSocket error handling and reconnection
 * - The status-aware retry rule for React Query (isRetryableError,
 *   shouldRetryQuery)
 *
 * Used by: WebSocketManager — hooks/websocket (websocketConnectionCore,
 * useWebSocketConnection); shouldRetryQuery — App.tsx's QueryClient (#5387).
 * retryWithBackoff / DEFAULT_RETRY_POLICY were deleted in #5387: they had no
 * caller, and React Query already applies exponential backoff between the
 * retries shouldRetryQuery allows.
 */

import { APIRequestError } from '@/utils/apiRequest';
import { toError } from '@/utils/errorGuards';

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
  maxReconnectAttempts: 10,
  initialReconnectDelayMs: 1000,
  maxReconnectDelayMs: 30000,
  backoffMultiplier: 1.5,
};

// ============================================================================
// WebSocket Connection Management
// ============================================================================

export class WebSocketManager {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  /** Set by close(): an intentional disconnect must never schedule a retry (#5602). */
  private closed = false;
  private config: WebSocketErrorConfig;
  private url: string;
  private onOpen: (() => void) | null = null;
  private onClose: (() => void) | null = null;
  private onMessage: ((event: MessageEvent) => void) | null = null;
  private onError: ((error: Event) => void) | null = null;

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
          this.onOpen?.();
          resolve();
        };

        ws.onerror = (error) => {
          console.error('[WebSocketManager] Error:', error);
          this.onError?.(error);
          reject(error);
        };

        ws.onmessage = (event) => {
          this.onMessage?.(event);
        };

        ws.onclose = () => {
          console.log('[WebSocketManager] Disconnected');
          this.stopHeartbeat();
          this.onClose?.();
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
   * Register event handlers
   */
  on(event: 'open' | 'close' | 'message' | 'error',
     handler: (() => void) | ((event: MessageEvent | Event) => void)): void {
    switch (event) {
      case 'open':
        this.onOpen = handler as () => void;
        break;
      case 'close':
        this.onClose = handler as () => void;
        break;
      case 'message':
        this.onMessage = handler as (event: MessageEvent) => void;
        break;
      case 'error':
        this.onError = handler as (error: Event) => void;
        break;
    }
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

/**
 * Determine if an error is retryable.
 *
 * #4467: this used to substring-match `error.message` for `network`, `503`,
 * `502`, `429` and so on. That retried a non-transient 4xx whose detail text
 * happened to contain one of those digit strings, and could not retry a
 * transient failure whose text lacked the hardcoded words. Errors from
 * `apiRequest` carry the real HTTP status, so eligibility now comes from that:
 *
 * - `0`   — apiRequest's code for a transport failure before any response
 *           (timeout or network error): retryable.
 * - `408` / `429` — request timeout / rate limited: retryable.
 * - `5xx` — server-side, except `501 Not Implemented`, which will not change
 *           on a retry.
 * - anything else, including a 200 that failed the response-shape check:
 *           not retryable.
 *
 * Only an error that did not come through apiRequest — and so has no status —
 * falls back to message wording, restricted to transport-failure words.
 */
export function isRetryableError(error: Error): boolean {
  if (error instanceof APIRequestError) {
    const status = error.statusCode;
    if (status === 0 || status === 408 || status === 429) return true;
    return status >= 500 && status !== 501;
  }

  const message = error.message.toLowerCase();
  return ['network', 'timeout', 'timed out', 'connection', 'econnrefused', 'failed to fetch']
    .some((pattern) => message.includes(pattern));
}

// #5388: classifyErrorSeverity, createTimeoutPromise, ErrorLogger and
// globalErrorLogger were deleted, along with the ErrorSeverity / ErrorContext /
// ErrorRecoveryStrategy types only they used. None had a caller in src/, tests
// included; errors are reported through console + toasts, not a logger store.

/** Retries React Query allows after the first failure (#5387). */
export const MAX_QUERY_RETRIES = 1;

/**
 * React Query `retry` callback (#5387): retry at most MAX_QUERY_RETRIES
 * times, and only errors isRetryableError accepts. A 404/400 fails at once
 * instead of costing a second identical round trip.
 */
export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  return failureCount < MAX_QUERY_RETRIES && isRetryableError(toError(error));
}
