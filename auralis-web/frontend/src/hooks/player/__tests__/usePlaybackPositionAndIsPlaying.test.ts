/**
 * usePlaybackPosition & useIsPlaying Hook Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests for the two focused playback hooks that subscribe to WebSocket
 * messages for position tracking and play/pause state.
 *
 * Test strategy:
 *   - Mock useWebSocketSubscription to capture the callback
 *   - Invoke the captured callback with synthetic messages
 *   - Assert hook return values via renderHook
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePlaybackPosition, useIsPlaying } from '../usePlaybackState';

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

// ---------------------------------------------------------------------------
// useIsPlaying
// ---------------------------------------------------------------------------

describe('useIsPlaying', () => {
  beforeEach(() => {
    capturedCallback = null;
  });

  it('returns false as initial state', () => {
    const { result } = renderHook(() => useIsPlaying());

    expect(result.current).toBe(false);
  });

  it('returns true on player_state with is_playing=true', () => {
    const { result } = renderHook(() => useIsPlaying());

    act(() => {
      capturedCallback!({
        type: 'player_state',
        data: {
          is_playing: true,
        },
      });
    });

    expect(result.current).toBe(true);
  });

  it('returns false on playback_paused message', () => {
    const { result } = renderHook(() => useIsPlaying());

    // Start playing first
    act(() => {
      capturedCallback!({
        type: 'player_state',
        data: { is_playing: true },
      });
    });
    expect(result.current).toBe(true);

    // Pause
    act(() => {
      capturedCallback!({
        type: 'playback_paused',
        data: {},
      });
    });

    expect(result.current).toBe(false);
  });

  it('returns true on playback_started message', () => {
    const { result } = renderHook(() => useIsPlaying());

    act(() => {
      capturedCallback!({
        type: 'playback_started',
        data: {},
      });
    });

    expect(result.current).toBe(true);
  });
});
