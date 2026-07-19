/**
 * useArtworkRevision Hook Tests
 *
 * Tests for WebSocket-driven artwork revision tracking and cache busting.
 * The subscription is a single module-level, refcounted subscription backed by
 * WebSocketContext (#4380) — one WS subscription regardless of album count.
 *
 * @module hooks/library/__tests__/useArtworkUpdates.test
 */

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useArtworkRevision, _internal } from '../useArtworkUpdates';
import { useWebSocketContext } from '@/contexts/WebSocketContext';

vi.mock('@/contexts/WebSocketContext');

describe('useArtworkRevision', () => {
  // The single module-level handler passed to context.subscribe('artwork_updated', ...).
  let capturedCallback: ((message: any) => void) | null;
  let subscribe: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    _internal.reset(); // clear module-level revisionMap + refcount between tests
    capturedCallback = null;

    subscribe = vi.fn((_type: string, handler: (message: any) => void) => {
      capturedCallback = handler;
      return vi.fn(); // unsubscribe
    });

    vi.mocked(useWebSocketContext).mockReturnValue({ subscribe } as any);
  });

  it('should return initial revision of 0', () => {
    const { result } = renderHook(() => useArtworkRevision(1));
    expect(result.current).toBe(0);
  });

  it('should subscribe once to the artwork_updated message type', () => {
    renderHook(() => useArtworkRevision(1));
    expect(subscribe).toHaveBeenCalledWith('artwork_updated', expect.any(Function));
    expect(subscribe).toHaveBeenCalledTimes(1);
  });

  it('should install only ONE subscription across many consumers (perf #3575)', () => {
    renderHook(() => useArtworkRevision(1));
    renderHook(() => useArtworkRevision(2));
    renderHook(() => useArtworkRevision(3));
    // Refcounted: a single WS subscription regardless of consumer count.
    expect(subscribe).toHaveBeenCalledTimes(1);
  });

  it('should increment revision when matching album message arrives', () => {
    const { result } = renderHook(() => useArtworkRevision(42));

    act(() => {
      capturedCallback!({ type: 'artwork_updated', data: { album_id: 42 } });
    });

    expect(result.current).toBe(1);
  });

  it('should not increment revision for different album', () => {
    const { result } = renderHook(() => useArtworkRevision(42));

    act(() => {
      capturedCallback!({ type: 'artwork_updated', data: { album_id: 99 } });
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

    const urlBefore = result.current > 0
      ? `/api/albums/42/artwork?v=${result.current}`
      : `/api/albums/42/artwork`;
    expect(urlBefore).toBe('/api/albums/42/artwork');

    act(() => {
      capturedCallback!({ type: 'artwork_updated', data: { album_id: 42 } });
    });

    const urlAfter = result.current > 0
      ? `/api/albums/42/artwork?v=${result.current}`
      : `/api/albums/42/artwork`;
    expect(urlAfter).toBe('/api/albums/42/artwork?v=1');
  });

  it('should track separate revisions for different album IDs via the shared handler', () => {
    const { result: result1 } = renderHook(() => useArtworkRevision(1));
    const { result: result2 } = renderHook(() => useArtworkRevision(2));

    // One shared subscription; the single handler fans out by album_id.
    act(() => {
      capturedCallback!({ type: 'artwork_updated', data: { album_id: 1 } });
    });

    expect(result1.current).toBe(1);
    expect(result2.current).toBe(0);
  });

  it('should reset revision tracking per album on albumId change', () => {
    const { result, rerender } = renderHook(
      ({ albumId }) => useArtworkRevision(albumId),
      { initialProps: { albumId: 1 } }
    );

    act(() => {
      capturedCallback!({ type: 'artwork_updated', data: { album_id: 1 } });
    });
    expect(result.current).toBe(1);

    // Re-render reading a different album's slot.
    rerender({ albumId: 2 });
    act(() => {
      capturedCallback!({ type: 'artwork_updated', data: { album_id: 1 } });
    });
    const currentRevision = result.current;
    act(() => {
      capturedCallback!({ type: 'artwork_updated', data: { album_id: 2 } });
    });
    expect(result.current).toBe(currentRevision + 1);
  });
});
