/**
 * usePlaybackPosition Hook Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests for the focused playback position hook that subscribes to WebSocket
 * messages for position tracking.
 *
 * Test strategy:
 *   - Mock useWebSocketSubscription to capture the callback
 *   - Invoke the captured callback with synthetic messages
 *   - Assert hook return values via renderHook
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePlaybackPosition } from '../usePlaybackState';

// ---------------------------------------------------------------------------
// Mock useWebSocketSubscription
// ---------------------------------------------------------------------------

type SubscriptionCallback = (message: any) => void;
let capturedCallback: SubscriptionCallback | null = null;

vi.mock('@/hooks/websocket/useWebSocketSubscription', () => ({
  useWebSocketSubscription: (
    _messageTypes: string[],
    callback: SubscriptionCallback,
  ) => {
    capturedCallback = callback;
    return vi.fn();
  },
}));

// ---------------------------------------------------------------------------
// usePlaybackPosition
// ---------------------------------------------------------------------------

describe('usePlaybackPosition', () => {
  beforeEach(() => {
    capturedCallback = null;
  });

  it('returns initial state { position: 0, duration: 0 }', () => {
    const { result } = renderHook(() => usePlaybackPosition());

    expect(result.current).toEqual({ position: 0, duration: 0 });
  });

  it('updates position and duration on player_state message', () => {
    const { result } = renderHook(() => usePlaybackPosition());

    act(() => {
      capturedCallback!({
        type: 'player_state',
        data: {
          current_time: 42.5,
          duration: 180.0,
        },
      });
    });

    expect(result.current.position).toBe(42.5);
    expect(result.current.duration).toBe(180.0);
  });

  it('updates position only on position_changed message', () => {
    const { result } = renderHook(() => usePlaybackPosition());

    // First set both via player_state
    act(() => {
      capturedCallback!({
        type: 'player_state',
        data: {
          current_time: 10,
          duration: 200,
        },
      });
    });

    // Then update position only
    act(() => {
      capturedCallback!({
        type: 'position_changed',
        data: {
          position: 55.3,
        },
      });
    });

    expect(result.current.position).toBe(55.3);
    expect(result.current.duration).toBe(200);
  });
});

