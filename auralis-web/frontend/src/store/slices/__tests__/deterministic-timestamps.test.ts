/**
 * Tests for deterministic Redux reducer timestamps (fixes #2232)
 *
 * Verifies that reducers are pure functions that don't call Date.now() directly,
 * instead receiving timestamps via action.meta from prepare callbacks.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { configureStore } from '@reduxjs/toolkit';
import queueReducer, { addTrack, setIsLoading as setQueueLoading } from '../queueSlice';
import playerReducer, { setIsPlaying, setVolume } from '../playerSlice';
import cacheReducer, { setCacheStats } from '../cacheSlice';
import connectionReducer, { setWSConnected } from '../connectionSlice';
import type { Track } from '../playerSlice';
import type { CacheStats } from '@/services/api/standardizedAPIClient';

describe('Deterministic Timestamps (fixes #2232)', () => {
  describe('Queue Slice', () => {
    const createQueueStore = () => configureStore({
      reducer: { queue: queueReducer },
    });
    let store: ReturnType<typeof createQueueStore>;

    beforeEach(() => {
      store = createQueueStore();
    });

    it('should include timestamp in action meta, not call Date.now() in reducer', () => {
      const mockTrack: Track = {
        id: 1,
        title: 'Test Track',
        artist: 'Test Artist',
        duration: 180,
      };

      // Freeze time
      const fixedTime = 1234567890;
      vi.spyOn(Date, 'now').mockReturnValue(fixedTime);

      // Dispatch action
      const action = addTrack(mockTrack);

      // Verify timestamp is in meta (set by prepare callback)
      expect(action.meta).toHaveProperty('timestamp');
      expect(action.meta.timestamp).toBe(fixedTime);

      // Dispatch to store
      store.dispatch(action);

      // Verify lastUpdated matches the timestamp from meta
      const state = store.getState().queue;
      expect(state.lastUpdated).toBe(fixedTime);
      expect(state.tracks).toHaveLength(1);

      vi.restoreAllMocks();
    });

    it('should be deterministic when replaying actions with same timestamp', () => {
      const mockTrack: Track = {
        id: 1,
        title: 'Test Track',
        artist: 'Test Artist',
        duration: 180,
      };

      // Create action with fixed timestamp
      const fixedTime = 9876543210;
      vi.spyOn(Date, 'now').mockReturnValue(fixedTime);
      const action = addTrack(mockTrack);
      vi.restoreAllMocks();

      // Dispatch same action multiple times
      store.dispatch(action);
      store.getState().queue;

      store.dispatch(setQueueLoading(false));
      store.dispatch(action);
      const state2 = store.getState().queue;

      // lastUpdated should be identical (deterministic)
      expect(state2.lastUpdated).toBe(fixedTime);
      // Not the current time
      expect(state2.lastUpdated).not.toBe(Date.now());
    });
  });

  describe('Player Slice', () => {
    const createPlayerStore = () => configureStore({
      reducer: { player: playerReducer },
    });
    let store: ReturnType<typeof createPlayerStore>;

    beforeEach(() => {
      store = createPlayerStore();
    });

    it('should include timestamp in action meta for all actions', () => {
      const fixedTime = 5555555555;
      vi.spyOn(Date, 'now').mockReturnValue(fixedTime);

      const playAction = setIsPlaying(true);
      const volumeAction = setVolume(50);

      expect(playAction.meta.timestamp).toBe(fixedTime);
      expect(volumeAction.meta.timestamp).toBe(fixedTime);

      vi.restoreAllMocks();
    });

    it('should allow time-travel debugging (state replay)', () => {
      const time1 = 1111111111;
      const time2 = 2222222222;

      // Create actions at different "times"
      vi.spyOn(Date, 'now').mockReturnValue(time1);
      const action1 = setIsPlaying(true);

      vi.spyOn(Date, 'now').mockReturnValue(time2);
      const action2 = setVolume(75);

      vi.restoreAllMocks();

      // Replay actions
      store.dispatch(action1);
      const state1 = store.getState().player;
      expect(state1.lastUpdated).toBe(time1);

      store.dispatch(action2);
      const state2 = store.getState().player;
      expect(state2.lastUpdated).toBe(time2);

      // Replay again - should get same result (deterministic)
      const store2 = createPlayerStore();
      store2.dispatch(action1);
      store2.dispatch(action2);

      const replayedState = store2.getState().player;
      expect(replayedState.lastUpdated).toBe(state2.lastUpdated);
      expect(replayedState.isPlaying).toBe(state2.isPlaying);
      expect(replayedState.volume).toBe(state2.volume);
    });
  });

  describe('Cache Slice', () => {
    const createCacheStore = () => configureStore({
      reducer: { cache: cacheReducer },
    });
    let store: ReturnType<typeof createCacheStore>;

    beforeEach(() => {
      store = createCacheStore();
    });

    it('should set lastUpdate from action meta timestamp', () => {
      const fixedTime = 7777777777;
      vi.spyOn(Date, 'now').mockReturnValue(fixedTime);

      const mockStats: CacheStats = {
        tier1: { chunks: 5, size_mb: 10, hits: 100, misses: 10, hit_rate: 0.9 },
        tier2: { chunks: 3, size_mb: 20, hits: 50, misses: 5, hit_rate: 0.91 },
        overall: {
          total_chunks: 8,
          total_size_mb: 30,
          total_hits: 150,
          total_misses: 15,
          overall_hit_rate: 0.9,
          tracks_cached: 5,
        },
        tracks: {},
      };

      const action = setCacheStats(mockStats);
      expect(action.meta.timestamp).toBe(fixedTime);

      store.dispatch(action);
      const state = store.getState().cache;
      expect(state.lastUpdate).toBe(fixedTime);

      vi.restoreAllMocks();
    });
  });

  describe('Connection Slice', () => {
    const createConnectionStore = () => configureStore({
      reducer: { connection: connectionReducer },
    });
    let store: ReturnType<typeof createConnectionStore>;

    beforeEach(() => {
      store = createConnectionStore();
    });

    it('should set lastUpdated from action meta timestamp', () => {
      const fixedTime = 3333333333;
      vi.spyOn(Date, 'now').mockReturnValue(fixedTime);

      const action = setWSConnected(true);
      expect(action.meta.timestamp).toBe(fixedTime);

      store.dispatch(action);
      const state = store.getState().connection;
      expect(state.lastUpdated).toBe(fixedTime);

      vi.restoreAllMocks();
    });
  });

  describe('Timestamp determinism', () => {
    it('should produce identical state when dispatching pre-created actions', () => {
      const mockTrack: Track = {
        id: 1,
        title: 'Test',
        artist: 'Artist',
        duration: 100,
      };

      // Freeze time and create actions
      const fixedTime = 9999999999;
      vi.spyOn(Date, 'now').mockReturnValue(fixedTime);

      const actions = [
        addTrack(mockTrack),
        setIsPlaying(true),
        setVolume(50),
        setWSConnected(true),
      ];

      vi.restoreAllMocks();

      // Create two stores and dispatch same actions
      const createFullStore = () => configureStore({
        reducer: {
          queue: queueReducer,
          player: playerReducer,
          cache: cacheReducer,
          connection: connectionReducer,
        },
      });
      const store1 = createFullStore();
      const store2 = createFullStore();

      // Dispatch same actions to both stores
      actions.forEach((action) => {
        store1.dispatch(action);
        store2.dispatch(action);
      });

      // States should be identical (deterministic)
      const state1 = store1.getState();
      const state2 = store2.getState();

      expect(state1.queue.lastUpdated).toBe(state2.queue.lastUpdated);
      expect(state1.player.lastUpdated).toBe(state2.player.lastUpdated);
      expect(state1.connection.lastUpdated).toBe(state2.connection.lastUpdated);

      // All timestamps should be the fixed time, not current time
      expect(state1.queue.lastUpdated).toBe(fixedTime);
      expect(state1.player.lastUpdated).toBe(fixedTime);
      expect(state1.connection.lastUpdated).toBe(fixedTime);
    });
  });
});
