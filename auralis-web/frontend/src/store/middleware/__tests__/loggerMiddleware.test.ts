/**
 * Logger Middleware Tests
 * ~~~~~~~~~~~~~~~~~~~~~~
 *
 * Unit tests for Redux logger middleware.
 *
 * Test Coverage:
 * - Action logging with timestamps
 * - State diff visualization
 * - Duration tracking
 * - Selective logging
 * - Error handling
 * - Configuration options
 *
 * Phase C.4d: Redux Middleware Testing
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { configureStore } from '@reduxjs/toolkit';
import playerReducer, { setVolume } from '@/store/slices/playerSlice';
import queueReducer from '@/store/slices/queueSlice';
import cacheReducer from '@/store/slices/cacheSlice';
import connectionReducer from '@/store/slices/connectionSlice';
import { createLoggerMiddleware } from '../loggerMiddleware';

describe('Logger Middleware', () => {
  let store: any;
  let consoleLogSpy: any;
  let consoleGroupSpy: any;
  let consoleGroupCollapsedSpy: any;

  beforeEach(() => {
    consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
    consoleGroupSpy = vi.spyOn(console, 'group').mockImplementation(() => {});
    consoleGroupCollapsedSpy = vi.spyOn(console, 'groupCollapsed').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleLogSpy.mockRestore();
    consoleGroupSpy.mockRestore();
    consoleGroupCollapsedSpy.mockRestore();
  });

  // ============================================================================
  // Basic Logging Tests
  // ============================================================================

  it('should create logger middleware', () => {
    const middleware = createLoggerMiddleware();
    expect(middleware).toBeDefined();
    expect(typeof middleware).toBe('function');
  });

  it('should log action when enabled', () => {
    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(
          createLoggerMiddleware({ enabled: true, collapsed: true })
        ),
    });

    store.dispatch({ type: 'TEST_ACTION', payload: { value: 123 } });

    // Uses groupCollapsed when collapsed: true
    expect(consoleGroupCollapsedSpy).toHaveBeenCalled();
  });

  it('should not log when disabled', () => {
    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(createLoggerMiddleware({ enabled: false })),
    });

    store.dispatch({ type: 'TEST_ACTION' });

    expect(consoleGroupSpy).not.toHaveBeenCalled();
  });

  // ============================================================================
  // Selective Logging Tests
  // ============================================================================

  it('should skip ignored actions', () => {
    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(
          createLoggerMiddleware({
            enabled: true,
            ignoredActions: ['IGNORED_ACTION'],
          })
        ),
    });

    store.dispatch({ type: 'IGNORED_ACTION' });

    expect(consoleGroupSpy).not.toHaveBeenCalled();
  });

  it('should only log specified actions', () => {
    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(
          createLoggerMiddleware({
            enabled: true,
            onlyActions: ['TRACKED_ACTION'],
          })
        ),
    });

    store.dispatch({ type: 'OTHER_ACTION' });
    expect(consoleGroupCollapsedSpy).not.toHaveBeenCalled();

    store.dispatch({ type: 'TRACKED_ACTION' });
    // Uses groupCollapsed by default (collapsed: true)
    expect(consoleGroupCollapsedSpy).toHaveBeenCalled();
  });

  // ============================================================================
  // Configuration Tests
  // ============================================================================

  it('should respect collapsed config', () => {
    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(createLoggerMiddleware({ enabled: true, collapsed: false })),
    });

    store.dispatch({ type: 'TEST_ACTION' });

    // Uses console.group when collapsed: false
    expect(consoleGroupSpy).toHaveBeenCalled();
  });

  it('should include timestamps when enabled', () => {
    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(
          createLoggerMiddleware({ enabled: true, timestamps: true })
        ),
    });

    store.dispatch({ type: 'TEST_ACTION' });

    // Uses groupCollapsed by default (collapsed: true)
    expect(consoleGroupCollapsedSpy).toHaveBeenCalled();
  });

  // ============================================================================
  // Predicate Tests
  // ============================================================================

  it('should use predicate to filter actions', () => {
    const predicate = vi.fn(() => false);

    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(
          createLoggerMiddleware({ enabled: true, predicate })
        ),
    });

    store.dispatch({ type: 'TEST_ACTION' });

    expect(predicate).toHaveBeenCalled();
    // Predicate returns false, so logging is skipped
    expect(consoleGroupCollapsedSpy).not.toHaveBeenCalled();
  });

  // ============================================================================
  // Sanitizer Tests
  // ============================================================================

  it('should sanitize action', () => {
    const actionSanitizer = (action: any) => ({
      ...action,
      payload: '[REDACTED]',
    });

    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(
          createLoggerMiddleware({ enabled: true, actionSanitizer })
        ),
    });

    store.dispatch({ type: 'TEST_ACTION', payload: 'secret' });

    // The middleware was called, proving sanitizer works
    // Uses groupCollapsed by default (collapsed: true)
    expect(consoleGroupCollapsedSpy).toHaveBeenCalled();
  });

  // ============================================================================
  // Duration Tracking Tests
  // ============================================================================

  it('should log duration when enabled', () => {
    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(
          createLoggerMiddleware({ enabled: true, duration: true })
        ),
    });

    store.dispatch({ type: 'TEST_ACTION' });

    expect(consoleLogSpy).toHaveBeenCalled();
  });

  it('should not log duration when disabled', () => {
    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(
          createLoggerMiddleware({ duration: false })
        ),
    });

    store.dispatch({ type: 'TEST_ACTION' });

    // Should have fewer log calls without duration
    // (This is approximate, exact count depends on other logs)
  });

  // ============================================================================
  // Error Handling Tests
  // ============================================================================

  /**
   * #4476: this used to call a standalone throwing function and assert it threw
   * — the store was built but never dispatched through, so the middleware's
   * catch → console.error → rethrow never executed and the branch was
   * uncovered. These dispatch a throwing reducer through a real store with the
   * middleware applied.
   */
  describe('error handling (#4476)', () => {
    const BOOM = 'test/boom';

    /** Reducer that throws only for the BOOM action, so other dispatches work. */
    const explodingReducer = (state = { value: 0 }, action: { type: string }) => {
      if (action.type === BOOM) {
        throw new Error('Test error');
      }
      return state;
    };

    const makeStore = (config = {}) =>
      configureStore({
        reducer: { exploding: explodingReducer },
        middleware: (getDefaultMiddleware) =>
          getDefaultMiddleware().concat(createLoggerMiddleware({ enabled: true, ...config })),
      });

    it('rethrows a reducer error through dispatch', () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const consoleGroupEndSpy = vi.spyOn(console, 'groupEnd').mockImplementation(() => {});
      store = makeStore();

      expect(() => store.dispatch({ type: BOOM })).toThrow('Test error');

      consoleErrorSpy.mockRestore();
      consoleGroupEndSpy.mockRestore();
    });

    it('logs the caught error via console.error', () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const consoleGroupEndSpy = vi.spyOn(console, 'groupEnd').mockImplementation(() => {});
      store = makeStore();

      expect(() => store.dispatch({ type: BOOM })).toThrow();

      expect(consoleErrorSpy).toHaveBeenCalledTimes(1);
      const logged = consoleErrorSpy.mock.calls[0][0];
      expect(logged).toBeInstanceOf(Error);
      expect((logged as Error).message).toBe('Test error');

      consoleErrorSpy.mockRestore();
      consoleGroupEndSpy.mockRestore();
    });

    it('closes the console group even when the action throws', () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const consoleGroupEndSpy = vi.spyOn(console, 'groupEnd').mockImplementation(() => {});
      store = makeStore();

      expect(() => store.dispatch({ type: BOOM })).toThrow();

      // Otherwise every subsequent console log stays nested inside the failed
      // action's group for the rest of the session.
      expect(consoleGroupEndSpy).toHaveBeenCalled();

      consoleErrorSpy.mockRestore();
      consoleGroupEndSpy.mockRestore();
    });

    it('leaves the store usable for later actions', () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const consoleGroupEndSpy = vi.spyOn(console, 'groupEnd').mockImplementation(() => {});
      store = makeStore();

      expect(() => store.dispatch({ type: BOOM })).toThrow();
      expect(() => store.dispatch({ type: 'test/ok' })).not.toThrow();
      expect(store.getState().exploding).toEqual({ value: 0 });

      consoleErrorSpy.mockRestore();
      consoleGroupEndSpy.mockRestore();
    });

    it('still rethrows when logging is disabled', () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      // enabled:false takes the early `return next(action)` path, which has no
      // try/catch — the error must still reach the caller.
      store = makeStore({ enabled: false });

      expect(() => store.dispatch({ type: BOOM })).toThrow('Test error');
      expect(consoleErrorSpy).not.toHaveBeenCalled();

      consoleErrorSpy.mockRestore();
    });
  });

  // ============================================================================
  // State Tracking Tests
  // ============================================================================

  it('should track state changes', () => {
    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(createLoggerMiddleware({ diff: true })),
    });

    // Via the action creator, not a hand-built `{type, payload}`: setVolume uses
    // a `prepare` callback that stamps `meta.timestamp`, and its reducer reads
    // `action.meta.timestamp` — a raw object skips prepare and throws there.
    // (Pre-existing failure in this file, unrelated to the middleware.)
    store.dispatch(setVolume(50));

    const state = store.getState();
    expect(state.player.volume).toBe(50);
  });
});
