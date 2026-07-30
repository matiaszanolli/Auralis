/**
 * useScanProgress Hook Tests
 *
 * Tests for library scan progress tracking via WebSocket messages.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { useScanProgress } from '../useScanProgress';
import type { WebSocketMessage } from '@/types/websocket';

vi.mock('@/contexts/WebSocketContext');

// Capture subscription callbacks so we can simulate messages. useScanProgress
// now subscribes via WebSocketContext (#4380), which registers one handler per
// message type (useWebSocketMessages loops over the type array).
type Callback = (message: WebSocketMessage) => void;

function createMockManager() {
  const subscriptions: { type: string; callback: Callback }[] = [];

  return {
    subscribe: vi.fn((type: string, callback: Callback) => {
      const entry = { type, callback };
      subscriptions.push(entry);
      return () => {
        const idx = subscriptions.indexOf(entry);
        if (idx !== -1) subscriptions.splice(idx, 1);
      };
    }),
    /** Deliver a message to all matching subscribers */
    deliver(message: WebSocketMessage) {
      for (const sub of subscriptions) {
        if (sub.type === message.type) {
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
    vi.mocked(useWebSocketContext).mockReturnValue({ subscribe: manager.subscribe } as any);
  });

  describe('initial state', () => {
    it('returns idle scan status', () => {
      const { result } = renderHook(() => useScanProgress());

      expect(result.current.isScanning).toBe(false);
      expect(result.current.current).toBe(0);
      expect(result.current.total).toBe(0);
      // #4616: null, not 0 — nothing is known before the first frame, and
      // seeding 0 made the value flip 0 → null on every scan's first frame.
      expect(result.current.percentage).toBeNull();
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
      // Indeterminate until the scanner's counting pass yields a total (#4616).
      expect(result.current.percentage).toBeNull();
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

    it('keeps a 0 percentage distinct from indeterminate (#4616)', () => {
      const { result } = renderHook(() => useScanProgress());

      act(() => {
        manager.deliver({
          type: 'scan_progress',
          data: { current: 0, total: 200, percentage: 0 },
        } as unknown as WebSocketMessage);
      });

      // The scanner's first post-count frame is a truthful 0%, not "unknown".
      expect(result.current.percentage).toBe(0);
      expect(result.current.total).toBe(200);
    });

    it('propagates an indeterminate frame as null (#4616)', () => {
      const { result } = renderHook(() => useScanProgress());

      act(() => {
        manager.deliver({
          type: 'scan_progress',
          data: { current: 3, total: 0, percentage: null },
        } as unknown as WebSocketMessage);
      });

      expect(result.current.percentage).toBeNull();
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
        filesFailed: 0,
        filesSkipped: 0,
        duration: 3.5,
      });
    });

    it('surfaces files_failed / files_skipped from scan_complete (#4412)', () => {
      const { result } = renderHook(() => useScanProgress());

      act(() => {
        manager.deliver({
          type: 'scan_complete',
          data: { files_added: 4, files_failed: 3, files_skipped: 2, duration: 1 },
        } as unknown as WebSocketMessage);
      });

      expect(result.current.lastResult?.filesFailed).toBe(3);
      expect(result.current.lastResult?.filesSkipped).toBe(2);
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
        filesFailed: 0,
        filesSkipped: 0,
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
        filesFailed: 0,
        filesSkipped: 0,
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
      expect(result.current.percentage).toBeNull();
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

  describe('reconnect resync (#4821)', () => {
    const originalFetch = global.fetch;

    afterEach(() => {
      global.fetch = originalFetch;
    });

    function mockConnected(fetchImpl: typeof fetch) {
      global.fetch = vi.fn(fetchImpl) as unknown as typeof fetch;
      vi.mocked(useWebSocketContext).mockReturnValue({
        subscribe: manager.subscribe,
        connectionStatus: 'connected',
      } as any);
    }

    function jsonResponse(body: unknown): Response {
      return { ok: true, json: async () => body } as Response;
    }

    it('clears a stuck isScanning when the server reports no active scan', async () => {
      mockConnected(async () => jsonResponse({ is_scanning: false }));
      const { result } = renderHook(() => useScanProgress());

      // Simulate having missed the terminal frame while disconnected: the
      // last thing this client heard was library_scan_started.
      act(() => {
        manager.deliver({ type: 'library_scan_started' } as WebSocketMessage);
      });
      expect(result.current.isScanning).toBe(true);

      await waitFor(() => expect(result.current.isScanning).toBe(false));
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/library/scan/status',
        expect.objectContaining({ signal: expect.anything() })
      );
    });

    it('preserves lastResult when clearing a stuck isScanning', async () => {
      mockConnected(async () => jsonResponse({ is_scanning: false }));
      const { result } = renderHook(() => useScanProgress());

      act(() => {
        manager.deliver({
          type: 'scan_complete',
          data: { files_added: 9, duration: 1 },
        } as unknown as WebSocketMessage);
      });
      act(() => {
        manager.deliver({ type: 'library_scan_started' } as WebSocketMessage);
      });
      expect(result.current.isScanning).toBe(true);

      await waitFor(() => expect(result.current.isScanning).toBe(false));
      // The resync endpoint has no knowledge of file counts — it must not
      // clobber the real result from the scan before the missed one.
      expect(result.current.lastResult?.filesAdded).toBe(9);
    });

    it('sets isScanning when the server reports an active scan this client missed', async () => {
      mockConnected(async () => jsonResponse({ is_scanning: true }));
      const { result } = renderHook(() => useScanProgress());

      expect(result.current.isScanning).toBe(false);
      await waitFor(() => expect(result.current.isScanning).toBe(true));
    });

    it('leaves state untouched when no scan is active and none was stuck', async () => {
      mockConnected(async () => jsonResponse({ is_scanning: false }));
      const { result } = renderHook(() => useScanProgress());

      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      expect(result.current.isScanning).toBe(false);
      expect(result.current.lastResult).toBeNull();
    });

    it('does not fetch when not connected', () => {
      global.fetch = vi.fn() as unknown as typeof fetch;
      vi.mocked(useWebSocketContext).mockReturnValue({
        subscribe: manager.subscribe,
        connectionStatus: 'disconnected',
      } as any);

      renderHook(() => useScanProgress());

      expect(global.fetch).not.toHaveBeenCalled();
    });

    it('tolerates a fetch failure without throwing', async () => {
      mockConnected(async () => {
        throw new Error('network down');
      });

      expect(() => renderHook(() => useScanProgress())).not.toThrow();
    });
  });
});
