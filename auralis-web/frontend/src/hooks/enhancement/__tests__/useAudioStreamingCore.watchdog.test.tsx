/**
 * useAudioStreamingCore - first-stream watchdog (#4433)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * After a play command, if no stream message arrives within
 * STREAM_START_WATCHDOG_MS the core surfaces a streaming error instead of
 * leaving the UI stuck in 'buffering' forever. The first incoming stream
 * message disarms the watchdog.
 */

import { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import playerReducer, { startStreaming } from '@/store/slices/playerSlice';
import {
  useAudioStreamingCore,
  STREAM_START_WATCHDOG_MS,
  type StreamingCoreOptions,
} from '../useAudioStreamingCore';

function createStore() {
  return configureStore({ reducer: { player: playerReducer } });
}

function makeWs() {
  const handlers: Record<string, (m: unknown) => void> = {};
  return {
    isConnected: true,
    connectionStatus: 'connected' as const,
    subscribe: vi.fn((type: string, h: (m: unknown) => void) => {
      handlers[type] = h;
      return () => { delete handlers[type]; };
    }),
    subscribeAll: vi.fn(() => () => {}),
    send: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
    setResumePositionGetter: vi.fn(),
    reissueActiveStreamAs: vi.fn(() => false),
    emit: (type: string, m: unknown) => handlers[type]?.(m),
  };
}

const OPTIONS: StreamingCoreOptions = {
  streamType: 'enhanced',
  sendType: 'play_enhanced',
  logPrefix: '[test]',
  getStartThreshold: () => 1,
  throttleProgress: true,
  detectOutOfSequence: true,
  closeContextOnCleanup: false,
};

describe('useAudioStreamingCore watchdog (#4433)', () => {
  let store: ReturnType<typeof createStore>;
  let ws: ReturnType<typeof makeWs>;

  beforeEach(() => {
    vi.useFakeTimers();
    store = createStore();
    ws = makeWs();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  function render() {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <Provider store={store}>{children}</Provider>
    );
    return renderHook(() => useAudioStreamingCore(ws as never, OPTIONS), { wrapper });
  }

  it('surfaces a streaming error when no stream message arrives before the timeout', () => {
    const { result } = render();

    act(() => {
      store.dispatch(startStreaming({ streamType: 'enhanced', trackId: 1, totalChunks: 0, intensity: 50 }));
    });
    expect(store.getState().player.streaming.enhanced.state).toBe('buffering');

    act(() => { result.current.armStreamStartWatchdog(); });

    // Just before the deadline: still buffering.
    act(() => { vi.advanceTimersByTime(STREAM_START_WATCHDOG_MS - 1); });
    expect(store.getState().player.streaming.enhanced.state).toBe('buffering');

    // At the deadline: error surfaced.
    act(() => { vi.advanceTimersByTime(1); });
    expect(store.getState().player.streaming.enhanced.state).toBe('error');
    expect(store.getState().player.streaming.enhanced.error).toMatch(/timed out/i);
  });

  it('is disarmed by the first incoming stream message', () => {
    const { result } = render();

    act(() => {
      store.dispatch(startStreaming({ streamType: 'enhanced', trackId: 1, totalChunks: 0, intensity: 50 }));
      result.current.armStreamStartWatchdog();
    });

    // A stream_start arrives before the deadline → watchdog cleared.
    act(() => {
      ws.emit('audio_stream_start', { data: { stream_type: 'enhanced', track_id: 1, total_chunks: 0 } });
    });

    act(() => { vi.advanceTimersByTime(STREAM_START_WATCHDOG_MS + 1000); });

    // No error — the stream responded in time.
    expect(store.getState().player.streaming.enhanced.state).not.toBe('error');
  });

  it('re-arming replaces the prior timer (no double-fire)', () => {
    const { result } = render();
    act(() => {
      store.dispatch(startStreaming({ streamType: 'enhanced', trackId: 1, totalChunks: 0, intensity: 50 }));
    });

    act(() => { result.current.armStreamStartWatchdog(); });
    act(() => { vi.advanceTimersByTime(STREAM_START_WATCHDOG_MS / 2); });
    // Re-arm (e.g. a new play command) — the first timer must not also fire.
    act(() => { result.current.armStreamStartWatchdog(); });
    act(() => { vi.advanceTimersByTime(STREAM_START_WATCHDOG_MS / 2 + 1); });
    expect(store.getState().player.streaming.enhanced.state).toBe('buffering');

    act(() => { vi.advanceTimersByTime(STREAM_START_WATCHDOG_MS / 2); });
    expect(store.getState().player.streaming.enhanced.state).toBe('error');
  });
});
