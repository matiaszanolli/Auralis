/**
 * Error Handling Utilities for Frontend Services
 *
 * Provides:
 * - Retry policies with exponential backoff
 * - WebSocket error handling and reconnection
 *
 * Used by: WebSocketManager — hooks/websocket (websocketConnectionCore,
 * useWebSocketConnection). isRetryableError / retryWithBackoff have no
 * production caller; wiring them in or deleting them is #5387.
 */

import { APIRequestError } from '@/utils/apiRequest';
import { toError } from '@/utils/errorGuards';

// ============================================================================
// Types
// ============================================================================

export interface RetryPolicy {
  maxRetries: number;
  initialDelayMs: number;
  maxDelayMs: number;
  backoffMultiplier: number;
  jitterFraction: number;
  shouldRetry?: (error: Error) => boolean;
}

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

export const DEFAULT_RETRY_POLICY: RetryPolicy = {
  maxRetries: 3,
  initialDelayMs: 100,
  maxDelayMs: 10000,
  backoffMultiplier: 2,
  jitterFraction: 0.1,
};

const DEFAULT_WEBSOCKET_CONFIG: WebSocketErrorConfig = {
  maxReconnectAttempts: 10,
  initialReconnectDelayMs: 1000,
  maxReconnectDelayMs: 30000,
  backoffMultiplier: 1.5,
};

// ============================================================================
// Retry Logic with Exponential Backoff
// ============================================================================

/**
 * Retry a function with exponential backoff
 */
export async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  policy: Partial<RetryPolicy> = {}
): Promise<T> {
  const config = { ...DEFAULT_RETRY_POLICY, ...policy };
  let lastError: Error | null = null;

  for (let attempt = 0; attempt < config.maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = toError(err);

      // Check if we should retry this error
      if (config.shouldRetry && !config.shouldRetry(lastError)) {
        throw lastError;
      }

      // If this is the last attempt, throw
      if (attempt === config.maxRetries - 1) {
        throw lastError;
      }

      // Calculate delay with exponential backoff + jitter
      const exponentialDelay = config.initialDelayMs * Math.pow(config.backoffMultiplier, attempt);
      const cappedDelay = Math.min(exponentialDelay, config.maxDelayMs);
      const jitter = cappedDelay * config.jitterFraction * Math.random();
      const delay = Math.floor(cappedDelay + jitter);

      console.warn(
        `[Retry] Attempt ${attempt + 1}/${config.maxRetries} failed. ` +
        `Retrying in ${delay}ms. Error: ${lastError.message}`
      );

      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }

  throw lastError || new Error('Retry failed: Unknown error');
}

// ============================================================================
// WebSocket Connection Management
// ============================================================================

export class WebSocketManager {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;
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
   */
  async connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url);
        // Receive binary frames as ArrayBuffer (not Blob) for zero-copy PCM decoding
        this.ws.binaryType = 'arraybuffer';

        this.ws.onopen = () => {
          console.log('[WebSocketManager] Connected');
          this.reconnectAttempts = 0;
          this.startHeartbeat();
          this.onOpen?.();
          resolve();
        };

        this.ws.onerror = (error) => {
          console.error('[WebSocketManager] Error:', error);
          this.onError?.(error);
          reject(error);
        };

        this.ws.onmessage = (event) => {
          this.onMessage?.(event);
        };

        this.ws.onclose = () => {
          console.log('[WebSocketManager] Disconnected');
          this.stopHeartbeat();
          this.onClose?.();
          this.attemptReconnect();
        };
      } catch (err) {
        reject(err);
      }
    });
  }

  /**
   * Attempt to reconnect with exponential backoff
   */
  private attemptReconnect(): void {
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
      this.connect().catch(err => {
        console.error('[WebSocketManager] Reconnection failed:', err);
        this.attemptReconnect();
      });
    }, delay);
  }

  /**
   * Start heartbeat to detect stale connections
   */
  private startHeartbeat(): void {
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
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
    }
    this.stopHeartbeat();
    if (this.ws) {
      // Null out onclose before closing to prevent reconnection attempts
      // triggered by the close event — intentional disconnects should not reconnect
      this.ws.onclose = null;
      this.ws.onopen = null;
      this.ws.onerror = null;
      this.ws.onmessage = null;
      this.ws.close();
    }
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
