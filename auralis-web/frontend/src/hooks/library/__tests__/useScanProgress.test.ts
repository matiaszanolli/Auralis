/**
 * useScanProgress Hook Tests
 *
 * Tests for library scan progress tracking via WebSocket messages.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import {
  setWebSocketManager,
} from '../../websocket/useWebSocketSubscription';
import { useScanProgress } from '../useScanProgress';
import type { WebSocketMessage } from '../../../types/websocket';

// Capture subscription callbacks so we can simulate messages
type Callback = (message: WebSocketMessage) => void;

function createMockManager() {
  const subscriptions: { types: string[]; callback: Callback }[] = [];

  return {
    subscribe: vi.fn((types: string[], callback: Callback) => {
      const entry = { types, callback };
      subscriptions.push(entry);
      return () => {
        const idx = subscriptions.indexOf(entry);
        if (idx !== -1) subscriptions.splice(idx, 1);
      };
    }),
    /** Deliver a message to all matching subscribers */
    deliver(message: WebSocketMessage) {
      for (const sub of subscriptions) {
        if (sub.types.includes(message.type)) {
          sub.callback(message);
        }
      }
    },
  };
}

describe('useScanProgress', () => {
  let manager: ReturnType<typeof createMockManager>;

  beforeEach(() => {
    manager = createMockManager();
    setWebSocketManager(manager);
  });

  afterEach(() => {
    setWebSocketManager(null);
  });

  describe('initial state', () => {
    it('returns idle scan status', () => {
      const { result } = renderHook(() => useScanProgress());

      expect(result.current.isScanning).toBe(false);
      expect(result.current.current).toBe(0);
      expect(result.current.total).toBe(0);
      expect(result.current.percentage).toBe(0);
      expect(result.current.currentFile).toBeNull();
      expect(result.current.lastResult).toBeNull();
    });
  });

  describe('library_scan_started', () => {
    it('sets isScanning to true and resets progress', () => {
      const { result } = renderHook(() => useScanProgress());

      act(() => {
        manager.deliver({ type: 'library_scan_started' } as WebSocketMessage);
      });

      expect(result.current.isScanning).toBe(true);
      expect(result.current.current).toBe(0);
      expect(result.current.total).toBe(0);
      expect(result.current.percentage).toBe(0);
    });

    it('preserves lastResult from a previous scan', () => {
      const { result } = renderHook(() => useScanProgress());

      // Complete a scan first
      act(() => {
        manager.deliver({
          type: 'scan_complete',
          data: { files_added: 5, duration: 1.2 },
        } as unknown as WebSocketMessage);
      });

      expect(result.current.lastResult).not.toBeNull();

      // Start a new scan
      act(() => {
        manager.deliver({ type: 'library_scan_started' } as WebSocketMessage);
      });

      expect(result.current.isScanning).toBe(true);
      expect(result.current.lastResult).toEqual(
        expect.objectContaining({ filesAdded: 5 })
      );
    });
  });

  describe('scan_progress', () => {
    it('updates progress fields', () => {
      const { result } = renderHook(() => useScanProgress());

      act(() => {
        manager.deliver({ type: 'library_scan_started' } as WebSocketMessage);
      });

      act(() => {
        manager.deliver({
          type: 'scan_progress',
          data: { current: 10, total: 50, percentage: 20, current_file: '/music/song.mp3' },
        } as unknown as WebSocketMessage);
      });

      expect(result.current.isScanning).toBe(true);
      expect(result.current.current).toBe(10);
      expect(result.current.total).toBe(50);
      expect(result.current.percentage).toBe(20);
      expect(result.current.currentFile).toBe('/music/song.mp3');
    });

    it('handles missing current_file', () => {
      const { result } = renderHook(() => useScanProgress());

      act(() => {
        manager.deliver({
          type: 'scan_progress',
          data: { current: 1, total: 10, percentage: 10 },
        } as unknown as WebSocketMessage);
      });

      expect(result.current.currentFile).toBeNull();
    });
  });

  describe('scan_complete', () => {
    it('resets scanning state and stores result', () => {
      const { result } = renderHook(() => useScanProgress());

      act(() => {
        manager.deliver({ type: 'library_scan_started' } as WebSocketMessage);
      });

      act(() => {
        manager.deliver({
          type: 'scan_complete',
          data: { files_added: 12, duration: 3.5 },
        } as unknown as WebSocketMessage);
      });

      expect(result.current.isScanning).toBe(false);
      expect(result.current.current).toBe(0);
      expect(result.current.lastResult).toEqual({
        filesAdded: 12,
        filesRemoved: 0,
        duration: 3.5,
      });
    });

    it('preserves filesRemoved when library_tracks_removed arrived during this scan', () => {
      const { result } = renderHook(() => useScanProgress());

      // Start scan
      act(() => {
        manager.deliver({ type: 'library_scan_started' } as WebSocketMessage);
      });

      // Tracks removed during this scan
      act(() => {
        manager.deliver({
          type: 'library_tracks_removed',
          data: { count: 3 },
        } as unknown as WebSocketMessage);
      });

      // Scan completes — should preserve filesRemoved from this scan
      act(() => {
        manager.deliver({
          type: 'scan_complete',
          data: { files_added: 2, duration: 0.5 },
        } as unknown as WebSocketMessage);
      });

      expect(result.current.lastResult?.filesRemoved).toBe(3);
    });

    it('resets stale filesRemoved when no removals in current scan (fixes #2868)', () => {
      const { result } = renderHook(() => useScanProgress());

      // First scan with removals
      act(() => {
        manager.deliver({ type: 'library_scan_started' } as WebSocketMessage);
      });
      act(() => {
        manager.deliver({
          type: 'library_tracks_removed',
          data: { count: 5 },
        } as unknown as WebSocketMessage);
      });
      act(() => {
        manager.deliver({
          type: 'scan_complete',
          data: { files_added: 10, duration: 2 },
        } as unknown as WebSocketMessage);
      });

      expect(result.current.lastResult?.filesRemoved).toBe(5);

      // Second scan with NO removals
      act(() => {
        manager.deliver({ type: 'library_scan_started' } as WebSocketMessage);
      });
      act(() => {
        manager.deliver({
          type: 'scan_complete',
          data: { files_added: 1, duration: 0.3 },
        } as unknown as WebSocketMessage);
      });

      // Should NOT carry over the 5 from the previous scan
      expect(result.current.lastResult?.filesRemoved).toBe(0);
    });
  });

  describe('library_tracks_removed', () => {
    it('updates filesRemoved in lastResult', () => {
      const { result } = renderHook(() => useScanProgress());

      // Complete a scan first
      act(() => {
        manager.deliver({
          type: 'scan_complete',
          data: { files_added: 5, duration: 1 },
        } as unknown as WebSocketMessage);
      });

      act(() => {
        manager.deliver({
          type: 'library_tracks_removed',
          data: { count: 7 },
        } as unknown as WebSocketMessage);
      });

      expect(result.current.lastResult).toEqual({
        filesAdded: 5,
        filesRemoved: 7,
        duration: 1,
      });
    });

    it('creates lastResult if none existed', () => {
      const { result } = renderHook(() => useScanProgress());

      act(() => {
        manager.deliver({
          type: 'library_tracks_removed',
          data: { count: 2 },
        } as unknown as WebSocketMessage);
      });

      expect(result.current.lastResult).toEqual({
        filesAdded: 0,
        filesRemoved: 2,
        duration: 0,
      });
    });
  });

  describe('library_scan_error', () => {
    it('resets isScanning to false on scan error (fixes #2869)', () => {
      const { result } = renderHook(() => useScanProgress());

      // Start scanning
      act(() => {
        manager.deliver({ type: 'library_scan_started' } as WebSocketMessage);
      });
      expect(result.current.isScanning).toBe(true);

      // Scan error arrives
      act(() => {
        manager.deliver({
          type: 'library_scan_error',
          data: { error: 'Permission denied' },
        } as unknown as WebSocketMessage);
      });

      expect(result.current.isScanning).toBe(false);
      expect(result.current.percentage).toBe(0);
    });

    it('preserves lastResult from previous scan on error', () => {
      const { result } = renderHook(() => useScanProgress());

      // Complete a scan first
      act(() => {
        manager.deliver({ type: 'library_scan_started' } as WebSocketMessage);
      });
      act(() => {
        manager.deliver({
          type: 'scan_complete',
          data: { files_added: 10, duration: 2 },
        } as unknown as WebSocketMessage);
      });
      expect(result.current.lastResult?.filesAdded).toBe(10);

      // Start new scan that fails
      act(() => {
        manager.deliver({ type: 'library_scan_started' } as WebSocketMessage);
      });
      act(() => {
        manager.deliver({
          type: 'library_scan_error',
          data: { error: 'Disk full' },
        } as unknown as WebSocketMessage);
      });

      // Previous result preserved
      expect(result.current.isScanning).toBe(false);
      expect(result.current.lastResult?.filesAdded).toBe(10);
    });
  });

  describe('full lifecycle', () => {
    it('handles start → progress → complete sequence', () => {
      const { result } = renderHook(() => useScanProgress());

      act(() => {
        manager.deliver({ type: 'library_scan_started' } as WebSocketMessage);
      });
      expect(result.current.isScanning).toBe(true);

      act(() => {
        manager.deliver({
          type: 'scan_progress',
          data: { current: 50, total: 100, percentage: 50, current_file: 'a.mp3' },
        } as unknown as WebSocketMessage);
      });
      expect(result.current.percentage).toBe(50);

      act(() => {
        manager.deliver({
          type: 'scan_complete',
          data: { files_added: 100, duration: 10 },
        } as unknown as WebSocketMessage);
      });
      expect(result.current.isScanning).toBe(false);
      expect(result.current.lastResult?.filesAdded).toBe(100);
    });
  });
});
