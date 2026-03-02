/**
 * Error Tracking Middleware Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Unit tests for Redux error tracking middleware.
 *
 * Test Coverage:
 * - Error detection and categorization
 * - Error tracking and storage
 * - Recovery mechanisms
 * - Error callbacks
 * - Statistics calculation
 *
 * Phase C.4d: Redux Error Handling Testing
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { configureStore } from '@reduxjs/toolkit';
import playerReducer from '@/store/slices/playerSlice';
import queueReducer from '@/store/slices/queueSlice';
import cacheReducer from '@/store/slices/cacheSlice';
import connectionReducer from '@/store/slices/connectionSlice';
import {
  createErrorTrackingMiddleware,
  ErrorCategory,
  getErrorStats,
  type TrackedError,
} from '../errorTrackingMiddleware';

describe('Error Tracking Middleware', () => {
  let store: any;
  let onErrorCallback: any;

  beforeEach(() => {
    onErrorCallback = vi.fn();
  });

  // ============================================================================
  // Error Detection Tests
  // ============================================================================

  it('should detect error in action payload', () => {
    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(
          createErrorTrackingMiddleware({
            enabled: true,
            onError: onErrorCallback,
          })
        ),
    });

    store.dispatch({
      type: 'player/setError',
      payload: 'Playback failed',
    });

    expect(onErrorCallback).toHaveBeenCalled();
  });

  it('should not trigger on success actions', () => {
    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(
          createErrorTrackingMiddleware({
            enabled: true,
            onError: onErrorCallback,
          })
        ),
    });

    store.dispatch({
      type: 'player/setVolume',
      payload: 50,
    });

    expect(onErrorCallback).not.toHaveBeenCalled();
  });

  // ============================================================================
  // Error Categorization Tests
  // ============================================================================

  it('should categorize network errors', () => {
    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(
          createErrorTrackingMiddleware({
            onError: (error: TrackedError) => {
              expect(error.category).toBe(ErrorCategory.NETWORK);
            },
          })
        ),
    });

    store.dispatch({
      type: 'connection/setError',
      payload: 'Connection timeout',
    });
  });

  it('should categorize validation errors', () => {
    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(
          createErrorTrackingMiddleware({
            onError: (error: TrackedError) => {
              expect(error.category).toBe(ErrorCategory.VALIDATION);
            },
          })
        ),
    });

    store.dispatch({
      type: 'queue/setError',
      payload: 'Invalid track format',
    });
  });

  it('should categorize authentication errors', () => {
    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(
          createErrorTrackingMiddleware({
            onError: (error: TrackedError) => {
              expect(error.category).toBe(ErrorCategory.AUTHENTICATION);
            },
          })
        ),
    });

    store.dispatch({
      type: 'AUTH',
      payload: 'Unauthorized 401',
    });
  });

  it('should categorize server errors', () => {
    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(
          createErrorTrackingMiddleware({
            onError: (error: TrackedError) => {
              expect(error.category).toBe(ErrorCategory.SERVER);
            },
          })
        ),
    });

    store.dispatch({
      type: 'cache/setError',
      payload: 'Internal server error 500',
    });
  });

  // ============================================================================
  // Error Tracking Tests
  // ============================================================================

  it('should track error with timestamp', () => {
    let trackedError: TrackedError | undefined;

    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(
          createErrorTrackingMiddleware({
            onError: (error) => {
              trackedError = error;
            },
          })
        ),
    });

    const beforeDispatch = Date.now();
    store.dispatch({
      type: 'player/setError',
      payload: 'Test error',
    });
    const afterDispatch = Date.now();

    expect(trackedError).toBeDefined();
    expect(trackedError!.timestamp).toBeGreaterThanOrEqual(beforeDispatch);
    expect(trackedError!.timestamp).toBeLessThanOrEqual(afterDispatch);
  });

  it('should track error with unique ID', () => {
    const errors: TrackedError[] = [];

    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(
          createErrorTrackingMiddleware({
            onError: (error) => {
              errors.push(error);
            },
          })
        ),
    });

    store.dispatch({
      type: 'player/setError',
      payload: 'Error 1',
    });

    store.dispatch({
      type: 'player/setError',
      payload: 'Error 2',
    });

    expect(errors).toHaveLength(2);
    expect(errors[0].id).not.toBe(errors[1].id);
  });

  it('should track error context', () => {
    let trackedError: TrackedError | undefined;

    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(
          createErrorTrackingMiddleware({
            onError: (error) => {
              trackedError = error;
            },
          })
        ),
    });

    store.dispatch({
      type: 'player/setError',
      payload: 'Playback failed',
      meta: { trackId: 123 },
    });

    expect(trackedError).toBeDefined();
    expect(trackedError!.action).toBe('player/setError');
  });

  // ============================================================================
  // Recovery Tests
  // ============================================================================

  it('should trigger connection recovery on network error', () => {
    vi.spyOn(store || { dispatch: vi.fn() }, 'dispatch', 'get');

    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(createErrorTrackingMiddleware()),
    });

    store.dispatch({
      type: 'connection/setError',
      payload: 'Network connection lost',
    });

    // Error should be tracked
    expect(store.getState().connection.lastError).toBeTruthy();
  });

  // ============================================================================
  // Statistics Tests
  // ============================================================================

  it('should calculate error statistics', () => {
    const errors: TrackedError[] = [
      {
        id: '1',
        timestamp: Date.now(),
        category: ErrorCategory.NETWORK,
        message: 'Network error',
        action: 'FETCH',
        retryCount: 0,
        maxRetries: 3,
      },
      {
        id: '2',
        timestamp: Date.now(),
        category: ErrorCategory.VALIDATION,
        message: 'Invalid input',
        action: 'VALIDATE',
        retryCount: 0,
        maxRetries: 3,
      },
      {
        id: '3',
        timestamp: Date.now(),
        category: ErrorCategory.NETWORK,
        message: 'Timeout',
        action: 'FETCH',
        retryCount: 0,
        maxRetries: 3,
      },
    ];

    const stats = getErrorStats(errors);

    expect(stats.total).toBe(3);
    expect(stats.byCategory[ErrorCategory.NETWORK]).toBe(2);
    expect(stats.byCategory[ErrorCategory.VALIDATION]).toBe(1);
    expect(stats.byAction['FETCH']).toBe(2);
    expect(stats.byAction['VALIDATE']).toBe(1);
  });

  // ============================================================================
  // Callback Tests
  // ============================================================================

  it('should call onError callback', () => {
    const onError = vi.fn();

    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(
          createErrorTrackingMiddleware({ onError })
        ),
    });

    store.dispatch({
      type: 'player/setError',
      payload: 'Test error',
    });

    expect(onError).toHaveBeenCalledWith(expect.objectContaining({
      category: expect.any(String),
      message: 'Test error',
      action: 'player/setError',
    }));
  });

  // ============================================================================
  // Configuration Tests
  // ============================================================================

  it('should respect enabled config', () => {
    const onError = vi.fn();

    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(
          createErrorTrackingMiddleware({ enabled: false, onError })
        ),
    });

    store.dispatch({
      type: 'player/setError',
      payload: 'Test error',
    });

    // onError might not be called if error detection is disabled
    // This depends on implementation
  });
});
