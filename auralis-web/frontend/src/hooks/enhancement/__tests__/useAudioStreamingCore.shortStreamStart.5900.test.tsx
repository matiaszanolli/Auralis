/**
 * useAudioStreamingCore - a stream shorter than the start threshold still plays (#5900)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * A seek into the last second (the backend clamps it to duration - 0.5 s) or a sub-second
 * track delivers fewer samples than the engine's minimum, so the auto-start rule never fired
 * and the track sat silent. The stream's end now starts whatever was delivered.
 */

import { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import playerReducer from '@/store/slices/playerSlice';
import { useAudioStreamingCore, type StreamingCoreOptions } from '../useAudioStreamingCore';

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
  getStartThreshold: () => 96000,
  throttleProgress: false,
  detectOutOfSequence: false,
  closeContextOnCleanup: false,
};

describe('short stream start (#5900)', () => {
  let ws: ReturnType<typeof makeWs>;
  let engine: { isPlaying: ReturnType<typeof vi.fn>; startPlayback: ReturnType<typeof vi.fn>;
    markStreamEnded: ReturnType<typeof vi.fn>; hasStreamEnded: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    ws = makeWs();
    engine = {
      isPlaying: vi.fn(() => false),
      startPlayback: vi.fn(),
      markStreamEnded: vi.fn(),
      hasStreamEnded: vi.fn(() => false),
    };
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  function render(bufferedSamples: number) {
    const store = configureStore({ reducer: { player: playerReducer } });
    const wrapper = ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider>;
    const hook = renderHook(() => useAudioStreamingCore(ws as never, OPTIONS), { wrapper });
    hook.result.current.streamingMetadataRef.current = {
      sampleRate: 44100, channels: 2, totalChunks: 1, processedChunks: 0,
    } as never;
    hook.result.current.pcmBufferRef.current = { getAvailableSamples: () => bufferedSamples } as never;
    hook.result.current.playbackEngineRef.current = engine as never;
    return hook;
  }

  const end = (reason: string) =>
    ws.emit('audio_stream_end', {
      data: { stream_type: 'enhanced', track_id: 1, reason, total_samples: 0, duration: 0 },
    });

  it('starts the short buffer when the stream completes', () => {
    render(44100); // 0.5 s stereo: below the 96000 threshold
    engine.markStreamEnded.mockImplementation(() => engine.hasStreamEnded.mockReturnValue(true));

    act(() => { end('completed'); });

    expect(engine.startPlayback).toHaveBeenCalledOnce();
  });

  it('does not start on a superseded stream\'s stopped end', () => {
    render(44100);

    act(() => { end('stopped'); });

    expect(engine.startPlayback).not.toHaveBeenCalled();
  });

  it('does not start an empty buffer', () => {
    render(0);
    engine.markStreamEnded.mockImplementation(() => engine.hasStreamEnded.mockReturnValue(true));

    act(() => { end('completed'); });

    expect(engine.startPlayback).not.toHaveBeenCalled();
  });
});
