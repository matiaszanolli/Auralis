/**
 * usePlaybackState Hook Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests for all 8 WebSocket event handlers in the player usePlaybackState hook.
 * Uses the same mock-capture pattern as usePlaybackPositionAndIsPlaying.test.ts.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePlaybackState } from '../usePlaybackState';

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

function sendMessage(type: string, data: any = {}) {
  expect(capturedCallback).not.toBeNull();
  act(() => {
    capturedCallback!({ type, data });
  });
}

describe('usePlaybackState', () => {
  beforeEach(() => {
    capturedCallback = null;
  });

  it('returns initial state', () => {
    const { result } = renderHook(() => usePlaybackState());

    expect(result.current.isPlaying).toBe(false);
    expect(result.current.currentTrack).toBeNull();
    expect(result.current.volume).toBe(80);
    expect(result.current.position).toBe(0);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('handles player_state message with full state transform', () => {
    const { result } = renderHook(() => usePlaybackState());

    sendMessage('player_state', {
      is_playing: true,
      current_track: { id: 1, title: 'Song', artist: 'Artist', duration: 200 },
      current_time: 42,
      duration: 200,
      volume: 65,
      queue: [],
      queue_index: 0,
      shuffle_enabled: false,
      repeat_mode: 'off',
      mastering_enabled: false,
      current_preset: 'adaptive',
    });

    expect(result.current.isPlaying).toBe(true);
    expect(result.current.currentTrack?.title).toBe('Song');
    expect(result.current.position).toBe(42);
    expect(result.current.duration).toBe(200);
    expect(result.current.volume).toBe(65);
    expect(result.current.isLoading).toBe(false);
  });

  it('handles playback_started → isPlaying true', () => {
    const { result } = renderHook(() => usePlaybackState());

    sendMessage('playback_started', { state: 'playing' });

    expect(result.current.isPlaying).toBe(true);
    expect(result.current.isLoading).toBe(false);
  });

  it('handles playback_resumed → isPlaying true', () => {
    const { result } = renderHook(() => usePlaybackState());

    sendMessage('playback_resumed', { state: 'playing' });

    expect(result.current.isPlaying).toBe(true);
  });

  it('handles playback_paused → isPlaying false', () => {
    const { result } = renderHook(() => usePlaybackState());

    // First start playing
    sendMessage('playback_started', { state: 'playing' });
    expect(result.current.isPlaying).toBe(true);

    // Then pause
    sendMessage('playback_paused', { state: 'paused' });
    expect(result.current.isPlaying).toBe(false);
  });

  it('handles playback_stopped → resets track and position', () => {
    const { result } = renderHook(() => usePlaybackState());

    // Set up some state first
    sendMessage('playback_started', { state: 'playing' });

    // Stop
    sendMessage('playback_stopped', { state: 'stopped' });

    expect(result.current.isPlaying).toBe(false);
    expect(result.current.currentTrack).toBeNull();
    expect(result.current.position).toBe(0);
    expect(result.current.queue).toEqual([]);
    expect(result.current.queueIndex).toBe(-1);
  });

  it('handles track_loaded → clears loading/error', () => {
    const { result } = renderHook(() => usePlaybackState());

    sendMessage('track_loaded', {});

    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('handles track_changed → resets position to 0', () => {
    const { result } = renderHook(() => usePlaybackState());

    // Set position via player_state
    sendMessage('player_state', {
      is_playing: true,
      current_track: null,
      current_time: 120,
      duration: 300,
      volume: 80,
      queue: [],
      queue_index: 0,
      shuffle_enabled: false,
      repeat_mode: 'off',
      mastering_enabled: false,
      current_preset: 'adaptive',
    });
    expect(result.current.position).toBe(120);

    // Track change resets position
    sendMessage('track_changed', { action: 'next' });
    expect(result.current.position).toBe(0);
  });

  it('handles volume_changed → updates volume', () => {
    const { result } = renderHook(() => usePlaybackState());

    sendMessage('volume_changed', { volume: 42 });

    expect(result.current.volume).toBe(42);
  });

  it('ignores unknown message types', () => {
    const { result } = renderHook(() => usePlaybackState());

    const before = { ...result.current };
    sendMessage('unknown_type', { foo: 'bar' });

    expect(result.current).toEqual(before);
  });
});
