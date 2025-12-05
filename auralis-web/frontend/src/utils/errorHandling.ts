/**
 * Error Handling Utilities for Frontend Services
 *
 * Provides standardized error handling patterns across services:
 * - Retry policies with exponential backoff
 * - WebSocket error handling and reconnection
 * - Error recovery strategies
 * - Timeout management
 *
 * Used by: processingService, RealTimeAnalysisStream, AnalysisExportService
 * WebSocket streaming: handled by usePlayEnhanced hook + WebSocketContext
 */

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

export interface ErrorRecoveryStrategy {
  name: string;
  canRecover: (error: Error) => boolean;
  recover: () => Promise<void>;
}

export type ErrorSeverity = 'low' | 'medium' | 'high' | 'critical';

export interface ErrorContext {
  error: Error;
  context: string;
  severity: ErrorSeverity;
  timestamp: number;
  retryCount?: number;
  lastAttemptTime?: number;
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

export const DEFAULT_WEBSOCKET_CONFIG: WebSocketErrorConfig = {
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
      lastError = err as Error;

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
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private heartbeatInterval: NodeJS.Timeout | null = null;
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
// Error Classification & Recovery
// ============================================================================

/**
 * Classify error severity based on error type
 */
export function classifyErrorSeverity(error: Error): ErrorSeverity {
  const message = error.message.toLowerCase();

  if (
    message.includes('network') ||
    message.includes('connection') ||
    message.includes('timeout')
  ) {
    return 'medium';
  }

  if (
    message.includes('authentication') ||
    message.includes('unauthorized') ||
    message.includes('forbidden')
  ) {
    return 'high';
  }

  if (message.includes('fatal') || message.includes('critical')) {
    return 'critical';
  }

  return 'low';
}

/**
 * Determine if an error is retryable
 */
export function isRetryableError(error: Error): boolean {
  const message = error.message.toLowerCase();

  // Retryable errors
  const retryablePatterns = [
    'network',
    'timeout',
    'connection',
    'econnrefused',
    '503',
    '502',
    '429', // Rate limit
  ];

  return retryablePatterns.some(pattern => message.includes(pattern));
}

/**
 * Create a timeout promise that rejects after specified time
 */
export function createTimeoutPromise<T>(
  promise: Promise<T>,
  timeoutMs: number,
  timeoutMessage: string = 'Operation timed out'
): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) =>
      setTimeout(() => reject(new Error(timeoutMessage)), timeoutMs)
    ),
  ]);
}

// ============================================================================
// Error Recovery Strategies
// ============================================================================

/**
 * Create an error recovery chain
 */
export class ErrorRecoveryChain {
  private strategies: ErrorRecoveryStrategy[] = [];

  /**
   * Add a recovery strategy
   */
  add(strategy: ErrorRecoveryStrategy): this {
    this.strategies.push(strategy);
    return this;
  }

  /**
   * Try to recover from an error
   */
  async tryRecover(error: Error): Promise<boolean> {
    for (const strategy of this.strategies) {
      if (strategy.canRecover(error)) {
        try {
          console.log(`[ErrorRecovery] Using strategy: ${strategy.name}`);
          await strategy.recover();
          return true;
        } catch (err) {
          console.error(`[ErrorRecovery] Strategy ${strategy.name} failed:`, err);
        }
      }
    }
    return false;
  }
}

// ============================================================================
// Error Logging & Monitoring
// ============================================================================

export class ErrorLogger {
  private errors: ErrorContext[] = [];
  private maxErrors = 1000;

  /**
   * Log an error
   */
  log(error: Error, context: string): ErrorContext {
    const errorContext: ErrorContext = {
      error,
      context,
      severity: classifyErrorSeverity(error),
      timestamp: Date.now(),
    };

    this.errors.push(errorContext);

    // Keep only recent errors
    if (this.errors.length > this.maxErrors) {
      this.errors = this.errors.slice(-this.maxErrors);
    }

    console.error(`[Error] ${context}: ${error.message}`, error);

    return errorContext;
  }

  /**
   * Get error history
   */
  getHistory(limit: number = 100): ErrorContext[] {
    return this.errors.slice(-limit);
  }

  /**
   * Clear history
   */
  clear(): void {
    this.errors = [];
  }

  /**
   * Get errors by severity
   */
  getErrorsBySeverity(severity: ErrorSeverity): ErrorContext[] {
    return this.errors.filter(e => e.severity === severity);
  }
}

// ============================================================================
// Global Error Logger Instance
// ============================================================================

export const globalErrorLogger = new ErrorLogger();

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Wrap a function with error logging
 */
export function withErrorLogging<T extends (...args: any[]) => Promise<any>>(
  fn: T,
  context: string
): T {
  return (async (...args: any[]) => {
    try {
      return await fn(...args);
    } catch (error) {
      globalErrorLogger.log(error as Error, context);
      throw error;
    }
  }) as T;
}

/**
 * Create a resilient fetch with retry logic
 */
export async function resilientFetch(
  url: string,
  options: RequestInit = {},
  retryPolicy?: Partial<RetryPolicy>
): Promise<Response> {
  return retryWithBackoff(
    async () => {
      const response = await fetch(url, options);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return response;
    },
    {
      ...DEFAULT_RETRY_POLICY,
      ...retryPolicy,
      shouldRetry: (error) => isRetryableError(error),
    }
  );
}
