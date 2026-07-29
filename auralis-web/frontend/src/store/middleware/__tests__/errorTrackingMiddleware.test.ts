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

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { configureStore } from '@reduxjs/toolkit';
import playerReducer, {
  setError as playerSetError,
  setVolume,
  setStreamingError,
} from '@/store/slices/playerSlice';
import queueReducer, { setError as queueSetError } from '@/store/slices/queueSlice';
import cacheReducer, { setError as cacheSetError } from '@/store/slices/cacheSlice';
import connectionReducer, {
  setError as connectionSetError,
  setWSConnected,
  setAPIConnected,
} from '@/store/slices/connectionSlice';
import {
  createErrorTrackingMiddleware,
  ErrorCategory,
  generateErrorId,
  getErrorStats,
  retryAction,
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

    store.dispatch(playerSetError('Playback failed'));

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

    store.dispatch(setVolume(50));

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

    store.dispatch(connectionSetError('Connection timeout'));
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

    store.dispatch(queueSetError('Invalid track format'));
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

    store.dispatch(cacheSetError('Internal server error 500'));
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
    store.dispatch(playerSetError('Test error'));
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

    store.dispatch(playerSetError('Error 1'));
    store.dispatch(playerSetError('Error 2'));

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

    store.dispatch(playerSetError('Playback failed'));

    expect(trackedError).toBeDefined();
    expect(trackedError!.action).toBe('player/setError');
  });

  // ============================================================================
  // Recovery Tests
  // ============================================================================

  it('defers connection recovery for a non-connection network error (#4455)', async () => {
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

    // A NETWORK-category error from a non-`connection/*` action. The middleware
    // must schedule a deferred connection/setError to trigger auto-recovery.
    // (A `connection/setError` action is excluded by the guard, so it would
    // NOT exercise this path — the pre-#4455 test used exactly that and passed
    // only via the connection reducer, never the recovery dispatch.)
    //
    // #4430 narrowed the forward from "any non-connection action" to actions
    // that genuinely describe the transport, so the vehicle here changed from
    // `player/setError` (a domain error that merely *reads* as network-ish) to
    // `player/setStreamingError` (the WebSocket audio stream). #4455's point —
    // that the deferred recovery dispatch really fires — is unchanged.
    store.dispatch(
      setStreamingError({ streamType: 'enhanced', error: 'Network connection lost' })
    );

    // The recovery dispatch is deferred to a microtask (#3023) — before it runs,
    // connection state is untouched by the player action.
    expect(store.getState().connection.lastError).toBeNull();

    // Flush the microtask; the deferred connectionActions.setError now runs.
    await Promise.resolve();

    expect(store.getState().connection.lastError).toBe('Network connection lost');
  });

  it('does not defer recovery for a connection-namespaced error (guard) (#4455)', async () => {
    const dispatchSpy = vi.fn();
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
            onError: () => dispatchSpy(),
          })
        ),
    });

    // A connection/* NETWORK error is handled by its own reducer but must NOT
    // trigger the deferred connection/setError recovery (guard avoids a loop).
    store.dispatch(connectionSetError('Network connection lost'));
    await Promise.resolve();

    // Reducer set it directly; there is no second (recovery) dispatch to observe,
    // but the value is present and tracking still fired exactly once.
    expect(store.getState().connection.lastError).toBe('Network connection lost');
    expect(dispatchSpy).toHaveBeenCalledTimes(1);
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

    store.dispatch(playerSetError('Test error'));

    expect(onError).toHaveBeenCalledWith(expect.objectContaining({
      category: expect.any(String),
      message: 'Test error',
      action: 'player/setError',
    }));
  });

  // ============================================================================
  // Configuration Tests
  // ============================================================================

  it('does not track when enabled is false (#4453)', () => {
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

    store.dispatch(playerSetError('Test error'));

    // With tracking disabled the onError callback must never fire...
    expect(onError).not.toHaveBeenCalled();
    // ...but the action itself must still reach the reducer (pure passthrough).
    expect(store.getState().player.error).toBe('Test error');
  });

  it('tracks when enabled is true (#4453 counterpart)', () => {
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
          createErrorTrackingMiddleware({ enabled: true, onError })
        ),
    });

    store.dispatch(playerSetError('Test error'));

    expect(onError).toHaveBeenCalledTimes(1);
  });
});

// ============================================================================
// retryAction — #3241 regression coverage
// ============================================================================

describe('retryAction (#3241)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns the executor result on first success without retrying', async () => {
    const executor = vi.fn(async () => 'ok');

    const result = await retryAction(executor, 3);

    expect(result).toBe('ok');
    expect(executor).toHaveBeenCalledTimes(1);
  });

  it('runs the configured number of attempts before giving up', async () => {
    const executor = vi.fn(async () => {
      throw new Error('boom');
    });

    const promise = retryAction(executor, 3);
    // Drain the exponential backoff sleeps (1s + 2s = 3s between the three
    // attempts). Pre-#3241 the loop returned on the first iteration so the
    // executor was only ever called once — this guards against that.
    await vi.runAllTimersAsync();

    await expect(promise).rejects.toThrow('boom');
    expect(executor).toHaveBeenCalledTimes(3);
  });

  it('returns the value from a later attempt when an earlier one fails', async () => {
    let calls = 0;
    const executor = vi.fn(async () => {
      calls += 1;
      if (calls < 2) throw new Error('transient');
      return 'recovered';
    });

    const promise = retryAction(executor, 3);
    await vi.runAllTimersAsync();
    const result = await promise;

    expect(result).toBe('recovered');
    expect(executor).toHaveBeenCalledTimes(2);
  });
});

describe('generateErrorId (#4623)', () => {
  // The `.substr(2, 9)` → `.slice(2, 11)` migration is the one place a
  // mechanical find/replace introduces a bug: substr takes (start, length),
  // slice takes (start, end). These tests pin the resulting ID shape.

  it('matches the err_<timestamp>_<9 chars> shape', () => {
    expect(generateErrorId()).toMatch(/^err_\d+_[a-z0-9]{9}$/);
  });

  it('keeps the random suffix at exactly 9 characters', () => {
    for (let i = 0; i < 200; i++) {
      const suffix = generateErrorId().split('_')[2];
      expect(suffix).toHaveLength(9);
    }
  });

  it('takes the suffix from index 2, skipping the "0." of the random string', () => {
    // Math.random().toString(36) is "0.xxxxxxxx…"; starting at 2 drops "0."
    const spy = vi.spyOn(Math, 'random').mockReturnValue(0.5);
    try {
      const expected = (0.5).toString(36).slice(2, 11);
      expect(generateErrorId().split('_')[2]).toBe(expected);
      expect(generateErrorId()).not.toContain('.');
    } finally {
      spy.mockRestore();
    }
  });

  it('produces distinct ids across successive calls', () => {
    const ids = new Set(Array.from({ length: 200 }, () => generateErrorId()));
    expect(ids.size).toBeGreaterThan(190);
  });
});

describe('connection error forwarding (#4430)', () => {
  // Two defects lived in the deferred forward at the bottom of the middleware:
  //
  // 1. categorizeError() works on message TEXT alone, and the forward was gated
  //    only on `!actionType.startsWith('connection/')`. So any slice's error
  //    whose wording happened to contain network/connection/offline/timeout was
  //    written into connection.lastError and surfaced through useAppErrors /
  //    useConnectionHealth as though the socket were down.
  //
  // 2. The forward is deferred to a microtask, so it could land AFTER a
  //    setWSConnected(true) that synchronously cleared lastError — resurrecting
  //    a stale error onto a freshly reconnected connection.

  const makeStore = () =>
    configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(createErrorTrackingMiddleware({ logToConsole: false })),
    });

  const lastError = (s: ReturnType<typeof makeStore>) => s.getState().connection.lastError;

  it('does not forward a queue error whose message merely says "timeout"', async () => {
    const store = makeStore();

    store.dispatch(queueSetError('Request timeout while loading queue'));
    await Promise.resolve();

    expect(lastError(store)).toBeNull();
  });

  it('does not forward cache or player errors with network-flavoured wording', async () => {
    const store = makeStore();

    store.dispatch(cacheSetError('connection reset while warming cache'));
    store.dispatch(playerSetError('offline: could not load artwork'));
    await Promise.resolve();

    expect(lastError(store)).toBeNull();
  });

  it('still forwards a genuine streaming transport failure', async () => {
    const store = makeStore();

    store.dispatch(
      setStreamingError({ streamType: 'enhanced', error: 'WebSocket connection lost' })
    );
    await Promise.resolve();

    expect(lastError(store)).toBe('WebSocket connection lost');
  });

  it('does not forward a streaming failure that is not network-categorized', async () => {
    const store = makeStore();

    store.dispatch(
      setStreamingError({ streamType: 'enhanced', error: 'Unsupported sample format' })
    );
    await Promise.resolve();

    expect(lastError(store)).toBeNull();
  });

  it('a reconnect cannot be overwritten by a late deferred setError', async () => {
    const store = makeStore();

    // Queue the forward, then reconnect before the microtask flushes.
    store.dispatch(
      setStreamingError({ streamType: 'enhanced', error: 'WebSocket connection lost' })
    );
    store.dispatch(setWSConnected(true));

    await Promise.resolve();
    await Promise.resolve();

    expect(lastError(store)).toBeNull();
    expect(store.getState().connection.wsConnected).toBe(true);
  });

  it('setAPIConnected(true) also invalidates a pending forward', async () => {
    const store = makeStore();

    store.dispatch(
      setStreamingError({ streamType: 'enhanced', error: 'network unreachable' })
    );
    store.dispatch(setAPIConnected(true));

    await Promise.resolve();
    await Promise.resolve();

    expect(lastError(store)).toBeNull();
  });

  it('forwards again after a reconnect once a new failure occurs', async () => {
    const store = makeStore();

    store.dispatch(setWSConnected(true));
    await Promise.resolve();

    store.dispatch(
      setStreamingError({ streamType: 'enhanced', error: 'connection dropped' })
    );
    await Promise.resolve();

    // The generation guard must not latch — a failure after the reconnect is
    // real and still belongs in connection.lastError.
    expect(lastError(store)).toBe('connection dropped');
  });

  it('does not forward connection-slice errors back into itself', async () => {
    const store = makeStore();

    store.dispatch(connectionSetError('network down'));
    await Promise.resolve();

    // Written directly by the reducer, not re-forwarded by the middleware.
    expect(lastError(store)).toBe('network down');
  });
});
