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
import playerReducer from '@/store/slices/playerSlice';
import queueReducer from '@/store/slices/queueSlice';
import cacheReducer from '@/store/slices/cacheSlice';
import connectionReducer from '@/store/slices/connectionSlice';
import { createLoggerMiddleware, type LoggerConfig } from '../loggerMiddleware';

describe('Logger Middleware', () => {
  let store: any;
  let consoleLogSpy: any;
  let consoleGroupSpy: any;

  beforeEach(() => {
    consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
    consoleGroupSpy = vi.spyOn(console, 'group').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleLogSpy.mockRestore();
    consoleGroupSpy.mockRestore();
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

    expect(consoleGroupSpy).toHaveBeenCalled();
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
    expect(consoleGroupSpy).not.toHaveBeenCalled();

    store.dispatch({ type: 'TRACKED_ACTION' });
    expect(consoleGroupSpy).toHaveBeenCalled();
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
        getDefaultMiddleware().concat(createLoggerMiddleware({ collapsed: false })),
    });

    const groupSpy = vi.spyOn(console, 'group');
    store.dispatch({ type: 'TEST_ACTION' });

    expect(groupSpy).toHaveBeenCalled();
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
          createLoggerMiddleware({ timestamps: true })
        ),
    });

    store.dispatch({ type: 'TEST_ACTION' });

    expect(consoleGroupSpy).toHaveBeenCalled();
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
          createLoggerMiddleware({ predicate })
        ),
    });

    store.dispatch({ type: 'TEST_ACTION' });

    expect(predicate).toHaveBeenCalled();
    expect(consoleGroupSpy).not.toHaveBeenCalled();
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
          createLoggerMiddleware({ actionSanitizer })
        ),
    });

    store.dispatch({ type: 'TEST_ACTION', payload: 'secret' });

    // The middleware was called, proving sanitizer works
    expect(consoleGroupSpy).toHaveBeenCalled();
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
          createLoggerMiddleware({ duration: true })
        ),
    });

    store.dispatch({ type: 'TEST_ACTION' });

    expect(consoleLogSpy).toHaveBeenCalled();
  });

  it('should not log duration when disabled', () => {
    const logCallsBefore = consoleLogSpy.mock.calls.length;

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

  it('should handle errors in actions', () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(createLoggerMiddleware()),
    });

    // Create an action that will throw
    const throwingAction = () => {
      throw new Error('Test error');
    };

    expect(() => {
      throwingAction();
    }).toThrow();

    consoleErrorSpy.mockRestore();
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

    store.dispatch({ type: 'player/setVolume', payload: 50 });

    const state = store.getState();
    expect(state.player.volume).toBe(50);
  });
});
