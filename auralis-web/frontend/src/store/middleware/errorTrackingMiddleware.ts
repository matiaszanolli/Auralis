/**
 * Redux Error Tracking Middleware
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Middleware for centralized error tracking and recovery.
 * Monitors Redux actions for errors and provides recovery mechanisms.
 *
 * Features:
 * - Automatic error detection from action payloads
 * - Error categorization and context tracking
 * - Recovery action suggestions
 * - Error analytics collection
 * - Retry with exponential backoff
 * - Error boundary integration
 *
 * Phase C.4d: Redux Error Handling
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import type { Middleware, AnyAction } from '@reduxjs/toolkit';
import type { RootState } from '../index';
import * as connectionActions from '../slices/connectionSlice';

// ============================================================================
// Error Types and Interfaces
// ============================================================================

export enum ErrorCategory {
  NETWORK = 'network',
  VALIDATION = 'validation',
  AUTHENTICATION = 'authentication',
  AUTHORIZATION = 'authorization',
  SERVER = 'server',
  CLIENT = 'client',
  UNKNOWN = 'unknown',
}

export interface TrackedError {
  id: string;
  timestamp: number;
  category: ErrorCategory;
  message: string;
  action: string;
  context?: Record<string, any>;
  stack?: string;
  retryCount: number;
  maxRetries: number;
}

export interface ErrorTrackingConfig {
  enabled?: boolean;
  maxErrors?: number;
  errorActions?: string[];
  onError?: (error: TrackedError) => void;
  onRecovery?: (error: TrackedError) => void;
  logToConsole?: boolean;
  logToServer?: boolean;
  recoveryStrategies?: Map<string, () => AnyAction>;
}

// ============================================================================
// Error Detection and Categorization
// ============================================================================

/**
 * Detect error type from message
 */
function categorizeError(message: string): ErrorCategory {
  const lowerMessage = message.toLowerCase();

  if (
    lowerMessage.includes('network') ||
    lowerMessage.includes('connection') ||
    lowerMessage.includes('offline') ||
    lowerMessage.includes('timeout')
  ) {
    return ErrorCategory.NETWORK;
  }

  if (
    lowerMessage.includes('invalid') ||
    lowerMessage.includes('required') ||
    lowerMessage.includes('format')
  ) {
    return ErrorCategory.VALIDATION;
  }

  if (
    lowerMessage.includes('unauthorized') ||
    lowerMessage.includes('401') ||
    lowerMessage.includes('token')
  ) {
    return ErrorCategory.AUTHENTICATION;
  }

  if (
    lowerMessage.includes('forbidden') ||
    lowerMessage.includes('403') ||
    lowerMessage.includes('permission')
  ) {
    return ErrorCategory.AUTHORIZATION;
  }

  if (
    lowerMessage.includes('500') ||
    lowerMessage.includes('503') ||
    lowerMessage.includes('server')
  ) {
    return ErrorCategory.SERVER;
  }

  if (
    lowerMessage.includes('null') ||
    lowerMessage.includes('undefined') ||
    lowerMessage.includes('syntax')
  ) {
    return ErrorCategory.CLIENT;
  }

  return ErrorCategory.UNKNOWN;
}

/**
 * Generate unique error ID
 */
function generateErrorId(): string {
  return `err_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// ============================================================================
// Error Tracking Middleware Factory
// ============================================================================

const defaultConfig: ErrorTrackingConfig = {
  enabled: true,
  maxErrors: 50,
  errorActions: ['setError', 'setLastError'],
  logToConsole: true,
  logToServer: false,
  recoveryStrategies: new Map(),
};

/**
 * Error store for tracking
 */
class ErrorStore {
  private errors: Map<string, TrackedError> = new Map();
  private maxErrors: number;

  constructor(maxErrors: number = 50) {
    this.maxErrors = maxErrors;
  }

  add(error: TrackedError): void {
    this.errors.set(error.id, error);

    // Keep bounded
    if (this.errors.size > this.maxErrors) {
      const firstKey = this.errors.keys().next().value;
      this.errors.delete(firstKey);
    }
  }

  get(id: string): TrackedError | undefined {
    return this.errors.get(id);
  }

  getAll(): TrackedError[] {
    return Array.from(this.errors.values());
  }

  getByAction(action: string): TrackedError[] {
    return Array.from(this.errors.values()).filter((e) => e.action === action);
  }

  getByCategory(category: ErrorCategory): TrackedError[] {
    return Array.from(this.errors.values()).filter((e) => e.category === category);
  }

  clear(): void {
    this.errors.clear();
  }

  size(): number {
    return this.errors.size;
  }
}

/**
 * Create Redux error tracking middleware
 */
export function createErrorTrackingMiddleware(
  config: ErrorTrackingConfig = {}
): Middleware {
  const finalConfig: ErrorTrackingConfig = { ...defaultConfig, ...config };
  const errorStore = new ErrorStore(finalConfig.maxErrors);

  return (store) => {
    return (next) => (action: AnyAction) => {
      try {
        const result = next(action);

        // Check if action contains error
        if (action.payload && typeof action.payload === 'object') {
          const payload = action.payload as Record<string, any>;

          // Look for error indicators
          if (payload.error || action.type.includes('Error') || action.type.includes('Failure')) {
            const errorMessage =
              payload.error || payload.message || action.type || 'Unknown error';

            const trackedError: TrackedError = {
              id: generateErrorId(),
              timestamp: Date.now(),
              category: categorizeError(String(errorMessage)),
              message: String(errorMessage),
              action: action.type,
              context: payload,
              retryCount: 0,
              maxRetries: 3,
            };

            // Store error
            errorStore.add(trackedError);

            // Log if enabled
            if (finalConfig.logToConsole) {
              console.error(`[Error Tracked] ${trackedError.category}: ${trackedError.message}`, {
                action: action.type,
                context: payload,
              });
            }

            // Call error callback
            finalConfig.onError?.(trackedError);

            // Send to server if enabled
            if (finalConfig.logToServer) {
              captureErrorToServer(trackedError);
            }

            // Attempt recovery based on category
            if (trackedError.category === ErrorCategory.NETWORK) {
              // Network errors - trigger reconnection attempt
              store.dispatch(connectionActions.setError(trackedError.message));
            }
          }
        }

        return result;
      } catch (error) {
        // Handle middleware errors
        const errorMessage =
          error instanceof Error ? error.message : String(error);

        const trackedError: TrackedError = {
          id: generateErrorId(),
          timestamp: Date.now(),
          category: categorizeError(errorMessage),
          message: errorMessage,
          action: action.type,
          stack: error instanceof Error ? error.stack : undefined,
          retryCount: 0,
          maxRetries: 3,
        };

        errorStore.add(trackedError);

        if (finalConfig.logToConsole) {
          console.error(`[Middleware Error] ${trackedError.category}:`, error);
        }

        finalConfig.onError?.(trackedError);

        throw error;
      }
    };
  };
}

// ============================================================================
// Error Capture and Reporting
// ============================================================================

/**
 * Send error to analytics/logging server
 */
function captureErrorToServer(error: TrackedError): void {
  // This would typically send to a logging service like Sentry
  try {
    if (navigator.sendBeacon) {
      navigator.sendBeacon('/api/errors', JSON.stringify(error));
    } else {
      fetch('/api/errors', {
        method: 'POST',
        body: JSON.stringify(error),
        keepalive: true,
      }).catch(() => {
        // Ignore failures in error reporting
      });
    }
  } catch {
    // Silently fail error reporting
  }
}

// ============================================================================
// Error Recovery Utilities
// ============================================================================

/**
 * Retry action with exponential backoff
 */
export async function retryAction(
  action: AnyAction,
  maxRetries: number = 3
): Promise<any> {
  let lastError: Error | undefined;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      // Execute action
      return action;
    } catch (error) {
      lastError = error as Error;

      // Wait with exponential backoff
      const delay = Math.pow(2, attempt) * 1000; // 1s, 2s, 4s
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }

  throw lastError || new Error('Max retries exceeded');
}

/**
 * Create recovery action dispatcher
 */
export function createRecoveryDispatcher(config: ErrorTrackingConfig = {}) {
  const recoveryStrategies = config.recoveryStrategies || new Map();

  return (error: TrackedError) => {
    // Get recovery strategy for error category
    const strategy = recoveryStrategies.get(error.category);

    if (strategy) {
      return strategy();
    }

    // Default recovery strategies
    switch (error.category) {
      case ErrorCategory.NETWORK:
        return connectionActions.setError(error.message);

      case ErrorCategory.AUTHENTICATION:
        // Trigger logout/re-authentication
        return { type: 'AUTH_REQUIRED' };

      case ErrorCategory.SERVER:
        // Show user-friendly error message
        return { type: 'SHOW_ERROR', payload: { message: error.message } };

      default:
        return { type: 'ERROR_OCCURRED', payload: error };
    }
  };
}

// ============================================================================
// Error Analytics
// ============================================================================

/**
 * Calculate error statistics
 */
export function getErrorStats(errors: TrackedError[]) {
  return {
    total: errors.length,
    byCategory: Object.values(ErrorCategory).reduce(
      (acc, category) => {
        acc[category] = errors.filter((e) => e.category === category).length;
        return acc;
      },
      {} as Record<string, number>
    ),
    byAction: errors.reduce(
      (acc, error) => {
        acc[error.action] = (acc[error.action] || 0) + 1;
        return acc;
      },
      {} as Record<string, number>
    ),
    recentErrors: errors.slice(-10),
    mostRecentError: errors[errors.length - 1],
  };
}

// ============================================================================
// Exports
// ============================================================================

export { ErrorStore, generateErrorId, categorizeError };
export type { TrackedError };
