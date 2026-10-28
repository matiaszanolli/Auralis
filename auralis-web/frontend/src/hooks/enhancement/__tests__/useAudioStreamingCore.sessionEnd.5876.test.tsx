/**
 * useAudioStreamingCore - every session-end path ends the tracked stream (#5876)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The client never sends WS stop/pause, so the stream command tracked for
 * reconnect resume and the enhancement re-issue outlived stops, natural ends
 * and failures. Each of those paths now ends it; a superseded stream's
 * 'stopped' end and a recoverable error do not.
 */

import { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import playerReducer from '@/store/slices/playerSlice';
import {
  useAudioStreamingCore,
  STREAM_START_WATCHDOG_MS,
  type StreamingCoreOptions,
} from '../useAudioStreamingCore';
import { connState, resetConnectionSingletons } from '@/hooks/websocket/websocketConnectionCore';

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

describe('useAudioStreamingCore session end (#5876)', () => {
  let store: ReturnType<typeof createStore>;
  let ws: ReturnType<typeof makeWs>;

  beforeEach(() => {
    vi.useFakeTimers();
    store = createStore();
    ws = makeWs();
    vi.spyOn(console, 'error').mockImplementation(() => {});
    resetConnectionSingletons();
    connState.lastStreamCommand = { type: 'play_enhanced', data: { track_id: 1 } };
    connState.streamActive = true;
  });

  afterEach(() => {
    resetConnectionSingletons();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  function render() {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <Provider store={store}>{children}</Provider>
    );
    return renderHook(() => useAudioStreamingCore(ws as never, OPTIONS), { wrapper });
  }

  const end = (reason: string, trackId = 1) =>
    ws.emit('audio_stream_end', {
      data: { stream_type: 'enhanced', track_id: trackId, reason, total_samples: 0, duration: 0 },
    });

  it('a client-side stop ends it', () => {
    const { result } = render();
    act(() => { result.current.stopPlayback(); });
    expect(connState.streamActive).toBe(false);
  });

  it.each(['completed', 'errored'])('a stream that finished (%s) ends it', (reason) => {
    render();
    act(() => { end(reason); });
    expect(connState.streamActive).toBe(false);
  });

  it("a superseded stream's 'stopped' end, or another track's end, does not", () => {
    render();
    act(() => { end('stopped'); });
    act(() => { end('completed', 99); });
    expect(connState.streamActive).toBe(true);
  });

  it('a terminal stream error ends it; an auto-resumed one does not', () => {
    render();
    ws.reissueActiveStreamAs.mockReturnValueOnce(true);
    act(() => {
      ws.emit('audio_stream_error', {
        data: { stream_type: 'enhanced', track_id: 1, error: 'x', code: 'E', recovery_position: 20 },
      });
    });
    expect(connState.streamActive).toBe(true);

    act(() => {
      ws.emit('audio_stream_error', { data: { stream_type: 'enhanced', track_id: 1, error: 'x', code: 'E' } });
    });
    expect(connState.streamActive).toBe(false);
  });

  it('a stream that never started (watchdog) ends it', () => {
    const { result } = render();
    act(() => { result.current.armStreamStartWatchdog(); });
    act(() => { vi.advanceTimersByTime(STREAM_START_WATCHDOG_MS); });
    expect(connState.streamActive).toBe(false);
  });
});
