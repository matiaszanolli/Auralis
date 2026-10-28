/**
 * useAudioStreamingCore - a late end/error from a superseded track is ignored (#6017)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The streaming reducers already drop an action whose trackId is not the active
 * stream's, but the handlers still ran cleanupStreaming(), the recovery re-issue
 * and markStreamEnded() on the NEW track's engine and buffer.
 */

import { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import playerReducer, { startStreaming } from '@/store/slices/playerSlice';
import { useAudioStreamingCore, type StreamingCoreOptions } from '../useAudioStreamingCore';
import { connState, resetConnectionSingletons } from '@/hooks/websocket/websocketConnectionCore';

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
    reissueActiveStreamAs: vi.fn(() => true),
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

const NEW_TRACK = 2;
const OLD_TRACK = 1;

describe('useAudioStreamingCore superseded-track messages (#6017)', () => {
  let ws: ReturnType<typeof makeWs>;

  beforeEach(() => {
    ws = makeWs();
    vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    resetConnectionSingletons();
    connState.lastStreamCommand = { type: 'play_enhanced', data: { track_id: NEW_TRACK } };
    connState.streamActive = true;
  });

  afterEach(() => {
    resetConnectionSingletons();
    vi.restoreAllMocks();
  });

  function render() {
    const store = configureStore({ reducer: { player: playerReducer } });
    store.dispatch(startStreaming({ streamType: 'enhanced', trackId: NEW_TRACK, totalChunks: 10 }));
    expect(store.getState().player.streaming.enhanced.trackId).toBe(NEW_TRACK);
    const wrapper = ({ children }: { children: ReactNode }) => (
      <Provider store={store}>{children}</Provider>
    );
    const hook = renderHook(() => useAudioStreamingCore(ws as never, OPTIONS), { wrapper });
    const buffer = { dispose: vi.fn() };
    const engine = { dispose: vi.fn(), markStreamEnded: vi.fn() };
    const core = hook.result.current;
    core.pcmBufferRef.current = buffer as never;
    core.playbackEngineRef.current = engine as never;
    core.streamingMetadataRef.current = { processedChunks: 3 } as never;
    return { core, buffer, engine };
  }

  it('does not dispose the new track\'s stream or re-issue on a late error for the old track', () => {
    const { core, buffer } = render();

    act(() => {
      ws.emit('audio_stream_error', {
        data: { stream_type: 'enhanced', track_id: OLD_TRACK, error: 'late', code: 'E', recovery_position: 30 },
      });
    });

    expect(buffer.dispose).not.toHaveBeenCalled();
    expect(core.pcmBufferRef.current).toBe(buffer);
    expect(ws.reissueActiveStreamAs).not.toHaveBeenCalled();
    expect(connState.streamActive).toBe(true);
  });

  it('does not mark the new track\'s engine ended on a late end for the old track', () => {
    const { engine } = render();

    act(() => {
      ws.emit('audio_stream_end', {
        data: { stream_type: 'enhanced', track_id: OLD_TRACK, reason: 'completed', total_samples: 1, duration: 1 },
      });
    });

    expect(engine.markStreamEnded).not.toHaveBeenCalled();
    expect(connState.streamActive).toBe(true);
  });

  it('still tears down on an error for the active track', () => {
    const { core, buffer } = render();

    act(() => {
      ws.emit('audio_stream_error', {
        data: { stream_type: 'enhanced', track_id: NEW_TRACK, error: 'real', code: 'E' },
      });
    });

    expect(buffer.dispose).toHaveBeenCalled();
    expect(core.pcmBufferRef.current).toBeNull();
  });
});
