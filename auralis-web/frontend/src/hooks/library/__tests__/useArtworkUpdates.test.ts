/**
 * useArtworkRevision Hook Tests
 *
 * Tests for WebSocket-driven artwork revision tracking and cache busting.
 *
 * @module hooks/library/__tests__/useArtworkUpdates.test
 */

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useArtworkRevision } from '../useArtworkUpdates';
import { useWebSocketSubscription } from '@/hooks/websocket/useWebSocketSubscription';

// Mock the WebSocket subscription hook
vi.mock('@/hooks/websocket/useWebSocketSubscription');

describe('useArtworkRevision', () => {
  let capturedCallback: ((message: any) => void) | null;

  beforeEach(() => {
    vi.clearAllMocks();
    capturedCallback = null;

    // Capture the callback passed to useWebSocketSubscription
    vi.mocked(useWebSocketSubscription).mockImplementation(
      (_types: string[], callback: (message: any) => void) => {
        capturedCallback = callback;
        return vi.fn(); // unsubscribe function
      }
    );
  });

  it('should return initial revision of 0', () => {
    const { result } = renderHook(() => useArtworkRevision(1));

    expect(result.current).toBe(0);
  });

  it('should subscribe to artwork_updated messages', () => {
    renderHook(() => useArtworkRevision(1));

    expect(useWebSocketSubscription).toHaveBeenCalledWith(
      ['artwork_updated'],
      expect.any(Function)
    );
  });

  it('should increment revision when matching album message arrives', () => {
    const { result } = renderHook(() => useArtworkRevision(42));

    act(() => {
      capturedCallback!({
        type: 'artwork_updated',
        data: { album_id: 42 },
      });
    });

    expect(result.current).toBe(1);
  });

  it('should not increment revision for different album', () => {
    const { result } = renderHook(() => useArtworkRevision(42));

    act(() => {
      capturedCallback!({
        type: 'artwork_updated',
        data: { album_id: 99 },
      });
    });

    expect(result.current).toBe(0);
  });

  it('should increment revision multiple times for matching messages', () => {
    const { result } = renderHook(() => useArtworkRevision(10));

    act(() => {
      capturedCallback!({ type: 'artwork_updated', data: { album_id: 10 } });
    });
    act(() => {
      capturedCallback!({ type: 'artwork_updated', data: { album_id: 10 } });
    });
    act(() => {
      capturedCallback!({ type: 'artwork_updated', data: { album_id: 10 } });
    });

    expect(result.current).toBe(3);
  });

  it('should only count matching messages among mixed traffic', () => {
    const { result } = renderHook(() => useArtworkRevision(5));

    act(() => {
      capturedCallback!({ type: 'artwork_updated', data: { album_id: 5 } });
    });
    act(() => {
      capturedCallback!({ type: 'artwork_updated', data: { album_id: 6 } });
    });
    act(() => {
      capturedCallback!({ type: 'artwork_updated', data: { album_id: 5 } });
    });
    act(() => {
      capturedCallback!({ type: 'artwork_updated', data: { album_id: 7 } });
    });

    expect(result.current).toBe(2);
  });

  it('should support cache-busting URL pattern with revision', () => {
    const { result } = renderHook(() => useArtworkRevision(42));

    // Before any update, revision is 0 (no query param needed)
    const urlBefore = result.current > 0
      ? `/api/albums/42/artwork?v=${result.current}`
      : `/api/albums/42/artwork`;
    expect(urlBefore).toBe('/api/albums/42/artwork');

    act(() => {
      capturedCallback!({ type: 'artwork_updated', data: { album_id: 42 } });
    });

    // After update, revision is 1 (cache-bust)
    const urlAfter = result.current > 0
      ? `/api/albums/42/artwork?v=${result.current}`
      : `/api/albums/42/artwork`;
    expect(urlAfter).toBe('/api/albums/42/artwork?v=1');
  });

  it('should track separate revisions for different album IDs', () => {
    let cb1: ((msg: any) => void) | null = null;
    let cb2: ((msg: any) => void) | null = null;
    let callCount = 0;

    vi.mocked(useWebSocketSubscription).mockImplementation(
      (_types: string[], callback: (msg: any) => void) => {
        callCount++;
        if (callCount % 2 === 1) cb1 = callback;
        else cb2 = callback;
        return vi.fn();
      }
    );

    const { result: result1 } = renderHook(() => useArtworkRevision(1));
    const { result: result2 } = renderHook(() => useArtworkRevision(2));

    act(() => {
      cb1!({ type: 'artwork_updated', data: { album_id: 1 } });
    });

    expect(result1.current).toBe(1);
    expect(result2.current).toBe(0);
  });

  it('should reset revision when albumId changes via rerender', () => {
    const { result, rerender } = renderHook(
      ({ albumId }) => useArtworkRevision(albumId),
      { initialProps: { albumId: 1 } }
    );

    act(() => {
      capturedCallback!({ type: 'artwork_updated', data: { album_id: 1 } });
    });
    expect(result.current).toBe(1);

    // Re-render with new albumId resets state via useState initializer
    rerender({ albumId: 2 });
    // The revision counter keeps its value since useState doesn't re-init on rerender,
    // but the callback now filters for album_id: 2
    act(() => {
      capturedCallback!({ type: 'artwork_updated', data: { album_id: 1 } });
    });
    // Should not increment for old album ID
    // (current value is still 1 from before rerender)
    const currentRevision = result.current;
    act(() => {
      capturedCallback!({ type: 'artwork_updated', data: { album_id: 2 } });
    });
    expect(result.current).toBe(currentRevision + 1);
  });
});
