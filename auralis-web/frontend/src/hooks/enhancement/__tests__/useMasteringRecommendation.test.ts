/**
 * useMasteringRecommendation Hook Tests
 *
 * Tests WS subscription, cache hit/miss, trackId change, timeout, and clearRecommendation.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// Capture the subscribe callback so tests can simulate WS messages
let subscribeCb: ((data: any) => void) | null = null;
const mockUnsubscribe = vi.fn();
const mockSubscribe = vi.fn((type: string, cb: (data: any) => void) => {
  subscribeCb = cb;
  return mockUnsubscribe;
});

vi.mock('@/contexts/WebSocketContext', () => ({
  useWebSocketContext: () => ({
    subscribe: mockSubscribe,
  }),
}));

import { useMasteringRecommendation } from '../useMasteringRecommendation';
import type { MasteringRecommendationData } from '../useMasteringRecommendation';

const mockRec: MasteringRecommendationData = {
  track_id: 42,
  primary_profile_id: 'warm-master',
  primary_profile_name: 'Warm Master',
  confidence_score: 0.87,
  predicted_loudness_change: 1.2,
  predicted_crest_change: -0.3,
  predicted_centroid_change: 0.5,
  is_hybrid: true,
};

describe('useMasteringRecommendation', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    subscribeCb = null;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should subscribe to WS and set isLoading on mount with trackId', () => {
    const { result } = renderHook(() => useMasteringRecommendation(42));

    expect(mockSubscribe).toHaveBeenCalledWith('mastering_recommendation', expect.any(Function));
    expect(result.current.isLoading).toBe(true);
    expect(result.current.recommendation).toBeNull();
    expect(result.current.isHybrid).toBe(false);
  });

  it('should not subscribe when trackId is undefined', () => {
    const { result } = renderHook(() => useMasteringRecommendation(undefined));

    expect(mockSubscribe).not.toHaveBeenCalled();
    expect(result.current.isLoading).toBe(false);
  });

  it('should populate recommendation on WS message', () => {
    const { result } = renderHook(() => useMasteringRecommendation(42));

    act(() => {
      subscribeCb!({ data: mockRec });
    });

    expect(result.current.recommendation).toEqual(mockRec);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.isHybrid).toBe(true);
  });

  it('should ignore WS messages for different trackId', () => {
    const { result } = renderHook(() => useMasteringRecommendation(42));

    act(() => {
      subscribeCb!({ data: { ...mockRec, track_id: 999 } });
    });

    expect(result.current.recommendation).toBeNull();
    expect(result.current.isLoading).toBe(true);
  });

  it('should serve from cache on trackId revisit', () => {
    const { result, rerender } = renderHook(
      ({ id }) => useMasteringRecommendation(id),
      { initialProps: { id: 42 as number | undefined } }
    );

    // Simulate WS delivering recommendation
    act(() => {
      subscribeCb!({ data: mockRec });
    });
    expect(result.current.recommendation).toEqual(mockRec);

    // Switch away
    rerender({ id: 99 });

    // Switch back — should hit cache, no new subscribe for loading
    rerender({ id: 42 });
    expect(result.current.recommendation).toEqual(mockRec);
  });

  it('should time out after 10s and set isTimedOut', () => {
    const { result } = renderHook(() => useMasteringRecommendation(42));

    expect(result.current.isLoading).toBe(true);
    expect(result.current.isTimedOut).toBe(false);

    act(() => {
      vi.advanceTimersByTime(10_000);
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.isTimedOut).toBe(true);
  });

  it('should cancel timeout when WS message arrives', () => {
    const { result } = renderHook(() => useMasteringRecommendation(42));

    act(() => {
      subscribeCb!({ data: mockRec });
    });

    // Advance past timeout — should NOT set isTimedOut
    act(() => {
      vi.advanceTimersByTime(15_000);
    });

    expect(result.current.isTimedOut).toBe(false);
    expect(result.current.isLoading).toBe(false);
  });

  it('should clear recommendation and cache via clearRecommendation', () => {
    const { result } = renderHook(() => useMasteringRecommendation(42));

    act(() => {
      subscribeCb!({ data: mockRec });
    });
    expect(result.current.recommendation).toEqual(mockRec);

    act(() => {
      result.current.clearRecommendation();
    });
    expect(result.current.recommendation).toBeNull();
  });

  it('should unsubscribe on unmount', () => {
    const { unmount } = renderHook(() => useMasteringRecommendation(42));

    unmount();

    expect(mockUnsubscribe).toHaveBeenCalled();
  });
});
