/**
 * WebSocket Middleware Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Unit tests for WebSocket Redux middleware.
 *
 * Test Coverage:
 * - Message type to Redux action mapping
 * - Offline message queue
 * - Connection state transitions
 * - Error handling and recovery
 * - Optimistic updates
 *
 * Phase C.4a: WebSocket-Redux Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { configureStore } from '@reduxjs/toolkit';
import playerReducer, { setDuration as setPlayerDuration } from '@/store/slices/playerSlice';
import queueReducer from '@/store/slices/queueSlice';
import cacheReducer from '@/store/slices/cacheSlice';
import connectionReducer from '@/store/slices/connectionSlice';
import {
  createWebSocketMiddleware,
  OfflineMessageQueue,
  OptimisticUpdateQueue,
} from '../websocketMiddleware';
import { MessageType } from '@/services/websocket/protocolClient';
import type { WSMessage } from '@/services/websocket/protocolClient';

describe('WebSocket Middleware', () => {
  let store: any;
  let mockProtocolClient: any;

  beforeEach(() => {
    // Create mock protocol client
    mockProtocolClient = {
      on: vi.fn(),
      onConnectionChange: vi.fn(),
      onError: vi.fn(),
    };

    // Create store with middleware
    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
        cache: cacheReducer,
        connection: connectionReducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(createWebSocketMiddleware(mockProtocolClient)),
    });
  });

  // ============================================================================
  // Offline Queue Tests
  // ============================================================================

  describe('OfflineMessageQueue', () => {
    it('should enqueue messages', () => {
      const queue = new OfflineMessageQueue();
      const message: WSMessage = {
        type: MessageType.PLAY,
        correlation_id: '123',
        timestamp: new Date().toISOString(),
        priority: 'high' as any,
        payload: { position: 0 },
      };

      queue.enqueue(message);
      expect(queue.size()).toBe(1);
    });

    it('should dequeue all messages in order', () => {
      const queue = new OfflineMessageQueue();
      const messages = [
        { type: MessageType.PLAY, correlation_id: '1' },
        { type: MessageType.SEEK, correlation_id: '2' },
        { type: MessageType.PAUSE, correlation_id: '3' },
      ] as WSMessage[];

      messages.forEach((m) => queue.enqueue(m));

      const dequeued = queue.dequeueAll();
      expect(dequeued).toHaveLength(3);
      expect(dequeued[0].type).toBe(MessageType.PLAY);
      expect(queue.size()).toBe(0);
    });

    it('should bound queue size', () => {
      const queue = new OfflineMessageQueue();

      // Add 101 messages (exceeds default max of 100)
      for (let i = 0; i < 101; i++) {
        const message: WSMessage = {
          type: MessageType.PLAY,
          correlation_id: `${i}`,
          timestamp: new Date().toISOString(),
          priority: 'normal' as any,
        };
        queue.enqueue(message);
      }

      // Should have at most 100
      expect(queue.size()).toBeLessThanOrEqual(100);
    });

    it('should clear queue', () => {
      const queue = new OfflineMessageQueue();
      const message: WSMessage = {
        type: MessageType.PLAY,
        correlation_id: '123',
        timestamp: new Date().toISOString(),
        priority: 'high' as any,
      };

      queue.enqueue(message);
      expect(queue.size()).toBe(1);

      queue.clear();
      expect(queue.size()).toBe(0);
    });
  });

  // ============================================================================
  // Optimistic Update Queue Tests
  // ============================================================================

  describe('OptimisticUpdateQueue', () => {
    it('should track optimistic updates', () => {
      const queue = new OptimisticUpdateQueue();
      const update = {
        action: { type: 'TEST' },
        rollback: { type: 'ROLLBACK' },
      };

      queue.enqueue('123', update);
      expect(queue.size()).toBe(1);
    });

    it('should confirm and remove update', () => {
      const queue = new OptimisticUpdateQueue();
      const update = {
        action: { type: 'TEST' },
        rollback: { type: 'ROLLBACK' },
      };

      queue.enqueue('123', update);
      const confirmed = queue.confirm('123');

      expect(confirmed).toBeDefined();
      expect(queue.size()).toBe(0);
    });

    it('should rollback update', () => {
      const queue = new OptimisticUpdateQueue();
      const update = {
        action: { type: 'TEST' },
        rollback: { type: 'ROLLBACK' },
      };

      queue.enqueue('123', update);
      const rolledBack = queue.rollback('123');

      expect(rolledBack).toBeDefined();
      expect(queue.size()).toBe(0);
    });

    it('should return undefined for unknown update', () => {
      const queue = new OptimisticUpdateQueue();
      const confirmed = queue.confirm('unknown');
      expect(confirmed).toBeUndefined();
    });
  });

  // ============================================================================
  // Message Handler Tests
  // ============================================================================

  describe('Message Handlers', () => {
    // Simulate connection being established so messages are processed
    // (middleware only processes messages when isConnected is true)
    beforeEach(() => {
      const connectionCallback = mockProtocolClient.onConnectionChange.mock.calls[0]?.[0];
      if (connectionCallback) {
        connectionCallback(true);
      }
      // Set a duration so setCurrentTime works (it uses Math.min(position, duration))
      store.dispatch(setPlayerDuration(300));
    });

    it('should handle PLAY message', () => {
      const message: WSMessage = {
        type: MessageType.PLAY,
        correlation_id: '123',
        timestamp: new Date().toISOString(),
        priority: 'high' as any,
        payload: { position: 30 },
      };

      // Simulate message handler call
      const handler = mockProtocolClient.on.mock.calls.find(
        (call: any) => call[0] === MessageType.PLAY
      );

      if (handler) {
        handler[1](message);

        const state = store.getState();
        expect(state.player.isPlaying).toBe(true);
        expect(state.player.currentTime).toBe(30);
      }
    });

    it('should handle PAUSE message', () => {
      const message: WSMessage = {
        type: MessageType.PAUSE,
        correlation_id: '123',
        timestamp: new Date().toISOString(),
        priority: 'high' as any,
        payload: { position: 60 },
      };

      const handler = mockProtocolClient.on.mock.calls.find(
        (call: any) => call[0] === MessageType.PAUSE
      );

      if (handler) {
        handler[1](message);

        const state = store.getState();
        expect(state.player.isPlaying).toBe(false);
      }
    });

    it('should handle SEEK message', () => {
      const message: WSMessage = {
        type: MessageType.SEEK,
        correlation_id: '123',
        timestamp: new Date().toISOString(),
        priority: 'high' as any,
        payload: { position: 120 },
      };

      const handler = mockProtocolClient.on.mock.calls.find(
        (call: any) => call[0] === MessageType.SEEK
      );

      if (handler) {
        handler[1](message);

        const state = store.getState();
        expect(state.player.currentTime).toBe(120);
      }
    });

    it('should handle QUEUE_ADD message', () => {
      const track = { id: 1, title: 'Track', artist: 'Artist', duration: 180 };
      const message: WSMessage = {
        type: MessageType.QUEUE_ADD,
        correlation_id: '123',
        timestamp: new Date().toISOString(),
        priority: 'normal' as any,
        payload: { track },
      };

      const handler = mockProtocolClient.on.mock.calls.find(
        (call: any) => call[0] === MessageType.QUEUE_ADD
      );

      if (handler) {
        handler[1](message);

        const state = store.getState();
        expect(state.queue.tracks).toHaveLength(1);
        expect(state.queue.tracks[0].id).toBe(1);
      }
    });

    it('should handle CACHE_STATS message', () => {
      const stats = {
        tier1: { chunks: 4, size_mb: 6, hits: 100, misses: 5, hit_rate: 0.95 },
        tier2: { chunks: 8, size_mb: 120, hits: 50, misses: 50, hit_rate: 0.5 },
        overall: {
          total_chunks: 12,
          total_size_mb: 225,
          total_hits: 150,
          total_misses: 55,
          overall_hit_rate: 0.73,
          tracks_cached: 42,
        },
        tracks: {},
      };

      const message: WSMessage = {
        type: MessageType.CACHE_STATS,
        correlation_id: '123',
        timestamp: new Date().toISOString(),
        priority: 'normal' as any,
        payload: stats,
      };

      const handler = mockProtocolClient.on.mock.calls.find(
        (call: any) => call[0] === MessageType.CACHE_STATS
      );

      if (handler) {
        handler[1](message);

        const state = store.getState();
        expect(state.cache.stats).toBeDefined();
        expect(state.cache.stats?.overall.total_chunks).toBe(12);
      }
    });

    it('should handle ERROR message with context', () => {
      const message: WSMessage = {
        type: MessageType.ERROR,
        correlation_id: '123',
        timestamp: new Date().toISOString(),
        priority: 'critical' as any,
        payload: { error: 'Playback failed', context: 'player' },
      };

      const handler = mockProtocolClient.on.mock.calls.find(
        (call: any) => call[0] === MessageType.ERROR
      );

      if (handler) {
        handler[1](message);

        const state = store.getState();
        expect(state.player.error).toBe('Playback failed');
      }
    });
  });

  // ============================================================================
  // Connection State Tests
  // ============================================================================

  describe('Connection State Management', () => {
    it('should update connection state when connected', () => {
      const connectionHandler = mockProtocolClient.onConnectionChange.mock.calls[0][0];

      if (connectionHandler) {
        connectionHandler(true);

        const state = store.getState();
        expect(state.connection.wsConnected).toBe(true);
      }
    });

    it('should update connection state when disconnected', () => {
      const connectionHandler = mockProtocolClient.onConnectionChange.mock.calls[0][0];

      if (connectionHandler) {
        // First connect
        connectionHandler(true);
        let state = store.getState();
        expect(state.connection.wsConnected).toBe(true);

        // Then disconnect
        connectionHandler(false);
        state = store.getState();
        expect(state.connection.wsConnected).toBe(false);
      }
    });

    it('should reset reconnect attempts on successful connection', () => {
      const connectionHandler = mockProtocolClient.onConnectionChange.mock.calls[0][0];

      if (connectionHandler) {
        // Disconnect and increment attempts
        connectionHandler(false);
        let state = store.getState();
        expect(state.connection.reconnectAttempts).toBeGreaterThan(0);

        // Reconnect - should reset attempts
        connectionHandler(true);
        state = store.getState();
        expect(state.connection.reconnectAttempts).toBe(0);
      }
    });

    it('should handle connection errors', () => {
      const errorHandler = mockProtocolClient.onError.mock.calls[0][0];

      if (errorHandler) {
        errorHandler(new Error('Connection timeout'));

        const state = store.getState();
        expect(state.connection.lastError).toBe('Connection timeout');
      }
    });
  });

  // ============================================================================
  // Batch Update Tests
  // ============================================================================

  describe('Batch Updates', () => {
    // Simulate connection being established so messages are processed
    beforeEach(() => {
      const connectionCallback = mockProtocolClient.onConnectionChange.mock.calls[0]?.[0];
      if (connectionCallback) {
        connectionCallback(true);
      }
      // Set a duration so setCurrentTime works (it uses Math.min(position, duration))
      store.dispatch(setPlayerDuration(300));
    });

    it('should handle STATUS_UPDATE with multiple fields', () => {
      const message: WSMessage = {
        type: MessageType.STATUS_UPDATE,
        correlation_id: '123',
        timestamp: new Date().toISOString(),
        priority: 'high' as any,
        payload: {
          playing: true,
          position: 90,
          volume: 60,
          muted: false,
          preset: 'warm',
        },
      };

      const handler = mockProtocolClient.on.mock.calls.find(
        (call: any) => call[0] === MessageType.STATUS_UPDATE
      );

      if (handler) {
        handler[1](message);

        const state = store.getState();
        expect(state.player.isPlaying).toBe(true);
        expect(state.player.currentTime).toBe(90);
        expect(state.player.volume).toBe(60);
        expect(state.player.isMuted).toBe(false);
        expect(state.player.preset).toBe('warm');
      }
    });
  });

  // ============================================================================
  // Integration Tests
  // ============================================================================

  describe('Integration', () => {
    // Simulate connection being established so messages are processed
    beforeEach(() => {
      const connectionCallback = mockProtocolClient.onConnectionChange.mock.calls[0]?.[0];
      if (connectionCallback) {
        connectionCallback(true);
      }
      // Set a duration so setCurrentTime works (it uses Math.min(position, duration))
      store.dispatch(setPlayerDuration(300));
    });

    it('should queue messages when offline', () => {
      const queue = new OfflineMessageQueue();

      const messages = [
        {
          type: MessageType.PLAY,
          correlation_id: '1',
          timestamp: new Date().toISOString(),
          priority: 'high' as any,
          payload: { position: 0 },
        },
        {
          type: MessageType.SEEK,
          correlation_id: '2',
          timestamp: new Date().toISOString(),
          priority: 'high' as any,
          payload: { position: 60 },
        },
      ] as WSMessage[];

      messages.forEach((m) => queue.enqueue(m));
      expect(queue.size()).toBe(2);

      const dequeued = queue.dequeueAll();
      expect(dequeued).toHaveLength(2);
      expect(queue.size()).toBe(0);
    });

    it('should handle rapid message sequences', () => {
      const message1: WSMessage = {
        type: MessageType.PLAY,
        correlation_id: '1',
        timestamp: new Date().toISOString(),
        priority: 'high' as any,
        payload: { position: 0 },
      };

      const message2: WSMessage = {
        type: MessageType.SEEK,
        correlation_id: '2',
        timestamp: new Date().toISOString(),
        priority: 'high' as any,
        payload: { position: 120 },
      };

      const message3: WSMessage = {
        type: MessageType.PAUSE,
        correlation_id: '3',
        timestamp: new Date().toISOString(),
        priority: 'high' as any,
        payload: { position: 120 },
      };

      // Process messages in sequence
      [message1, message2, message3].forEach((msg) => {
        const handler = mockProtocolClient.on.mock.calls.find(
          (call: any) => call[0] === msg.type
        );
        if (handler) {
          handler[1](msg);
        }
      });

      const state = store.getState();
      expect(state.player.isPlaying).toBe(false);
      expect(state.player.currentTime).toBe(120);
    });
  });
});
