/**
 * Redux State Hooks Tests
 * ~~~~~~~~~~~~~~~~~~~~~~
 *
 * Unit tests for Redux state and action hooks.
 *
 * Test Coverage:
 * - Player hooks (play, pause, seek, volume)
 * - Queue hooks (add, remove, reorder)
 * - Cache hooks (stats, health)
 * - Connection hooks (status, latency)
 * - Convenience hooks (loading, errors, health)
 *
 * Phase C.4a: Redux Hooks Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import playerReducer from '@/store/slices/playerSlice';
import queueReducer from '@/store/slices/queueSlice';
import cacheReducer from '@/store/slices/cacheSlice';
import connectionReducer from '@/store/slices/connectionSlice';
import {
  useQueue,
  useConnection,
  usePlayerActions,
  usePlayerState,
  useQueueState,
  useCacheState,
  useConnectionState,
  useAppState,
  useConnectionHealth,
} from '../useReduxState';
import type React from 'react';

describe('Redux State Hooks', () => {
  let store: any;
  let wrapper: (props: { children: React.ReactNode }) => React.ReactElement | null;

  beforeEach(() => {
    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
    });

    wrapper = ({ children }) => <Provider store={store}>{children}</Provider>;
  });

  // ============================================================================
  // Player Hooks Tests
  // ============================================================================

  // #5354: the usePlayer() describe block was deleted with the hook itself —
  // zero production callers, surfacing isLoading/error fields that could
  // never change. usePlayerActions keeps its own dedicated test file.

  // ============================================================================
  // Queue Hooks Tests
  // ============================================================================

  describe('useQueue', () => {
    it('should return queue state and actions', () => {
      const { result } = renderHook(() => useQueue(), { wrapper });

      expect(result.current.tracks).toEqual([]);
      expect(result.current.queueLength).toBe(0);
      expect(result.current.currentIndex).toBe(0);
    });

    it('should add track to queue', () => {
      const { result } = renderHook(() => useQueue(), { wrapper });
      const track = { id: 1, title: 'Track', artist: 'Artist', duration: 180 };

      act(() => {
        result.current.add(track);
      });

      expect(result.current.queueLength).toBe(1);
      expect(result.current.tracks[0]).toEqual(track);
    });

    it('should add multiple tracks', () => {
      const { result } = renderHook(() => useQueue(), { wrapper });
      const tracks = [
        { id: 1, title: 'Track 1', artist: 'Artist', duration: 180 },
        { id: 2, title: 'Track 2', artist: 'Artist', duration: 200 },
      ];

      act(() => {
        result.current.addMany(tracks);
      });

      expect(result.current.queueLength).toBe(2);
    });

    it('should remove track from queue', () => {
      const { result } = renderHook(() => useQueue(), { wrapper });
      const tracks = [
        { id: 1, title: 'Track 1', artist: 'Artist', duration: 180 },
        { id: 2, title: 'Track 2', artist: 'Artist', duration: 200 },
      ];

      act(() => {
        result.current.addMany(tracks);
      });

      expect(result.current.queueLength).toBe(2);

      act(() => {
        result.current.remove(0);
      });

      expect(result.current.queueLength).toBe(1);
    });

    it('should calculate remaining time', () => {
      const { result } = renderHook(() => useQueue(), { wrapper });
      const tracks = [
        { id: 1, title: 'Track 1', artist: 'Artist', duration: 180 },
        { id: 2, title: 'Track 2', artist: 'Artist', duration: 200 },
        { id: 3, title: 'Track 3', artist: 'Artist', duration: 150 },
      ];

      act(() => {
        result.current.addMany(tracks);
        result.current.setCurrentIndex(0);
      });

      // Remaining time = track 2 + track 3 = 200 + 150 = 350
      expect(result.current.remainingTime).toBe(350);
    });

    it('should clear queue', () => {
      const { result } = renderHook(() => useQueue(), { wrapper });
      const track = { id: 1, title: 'Track', artist: 'Artist', duration: 180 };

      act(() => {
        result.current.add(track);
      });

      expect(result.current.queueLength).toBe(1);

      act(() => {
        result.current.clear();
      });

      expect(result.current.queueLength).toBe(0);
    });
  });

  // ============================================================================
  // Cache Hooks Tests
  // ============================================================================

  // #5354: the useCache() describe block was deleted with the hook itself —
  // zero production callers, surfacing isLoading/error/clearError on state
  // nothing ever dispatched.

  // ============================================================================
  // Connection Hooks Tests
  // ============================================================================

  describe('useConnection', () => {
    it('should return connection state', () => {
      const { result } = renderHook(() => useConnection(), { wrapper });

      expect(result.current.wsConnected).toBe(false);
      expect(result.current.apiConnected).toBe(false);
      expect(result.current.isFullyConnected).toBe(false);
      expect(result.current.latency).toBe(0);
    });

    it('should update connection status', () => {
      const { result } = renderHook(() => useConnection(), { wrapper });

      act(() => {
        result.current.setWSConnected(true);
        result.current.setLatency(25);
      });

      expect(result.current.wsConnected).toBe(true);
      expect(result.current.latency).toBe(25);
    });

    it('should track connection health', () => {
      const { result } = renderHook(() => useConnection(), { wrapper });

      expect(result.current.connectionHealth).toBe('disconnected');

      act(() => {
        result.current.setWSConnected(true);
      });

      expect(result.current.connectionHealth).toBe('degraded');

      act(() => {
        result.current.setAPIConnected(true);
      });

      expect(result.current.connectionHealth).toBe('healthy');
    });
  });

  // ============================================================================
  // Convenience Hooks Tests
  // ============================================================================

  describe('Convenience Hooks', () => {
    // #5354: useIsLoading/useAppErrors tests were deleted with the hooks —
    // they could only ever report "idle, no errors".

    it('useConnectionHealth should provide detailed status', () => {
      const { result } = renderHook(() => useConnectionHealth(), { wrapper });

      expect(result.current.connected).toBe(false);
      expect(result.current.health).toBe('disconnected');
    });
  });

  // ============================================================================
  // Combined State Tests
  // ============================================================================

  describe('useAppState', () => {
    it('should return all state slices', () => {
      const { result } = renderHook(() => useAppState(), { wrapper });

      expect(result.current.player).toBeDefined();
      expect(result.current.queue).toBeDefined();
      expect(result.current.cache).toBeDefined();
      expect(result.current.connection).toBeDefined();
    });

    it('should reflect changes across slices', () => {
      const { result: actionsResult } = renderHook(() => usePlayerActions(), { wrapper });
      const { result: appStateResult } = renderHook(() => useAppState(), { wrapper });

      act(() => {
        actionsResult.current.play();
      });

      expect(appStateResult.current.player.isPlaying).toBe(true);
    });
  });

  // ============================================================================
  // State Selector Tests
  // ============================================================================

  describe('State Selectors', () => {
    it('usePlayerState should return player slice', () => {
      const { result } = renderHook(() => usePlayerState(), { wrapper });

      expect(result.current.isPlaying).toBe(false);
      expect(result.current.volume).toBe(70);
    });

    it('useQueueState should return queue slice', () => {
      const { result } = renderHook(() => useQueueState(), { wrapper });

      expect(result.current.tracks).toEqual([]);
      expect(result.current.currentIndex).toBe(0);
    });

    it('useCacheState should return cache slice', () => {
      const { result } = renderHook(() => useCacheState(), { wrapper });

      expect(result.current.stats).toBeNull();
      expect(result.current.health).toBeNull();
    });

    it('useConnectionState should return connection slice', () => {
      const { result } = renderHook(() => useConnectionState(), { wrapper });

      expect(result.current.wsConnected).toBe(false);
      expect(result.current.apiConnected).toBe(false);
    });
  });
});
