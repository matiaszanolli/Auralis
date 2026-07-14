/**
 * useAudioStreamingCore - per-content-chunk progress accounting (#4414)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The backend splits each processed CONTENT chunk into frameCount ~300 KB
 * binary sub-frames, each arriving as its own `audio_chunk` message. The
 * progress counter (processedChunks) is divided by totalChunks = the CONTENT
 * chunk count from audio_stream_start, so incrementing once per frame made the
 * numerator climb ~frameCount× too fast and the buffering bar hit 100% during
 * roughly the first content chunk. It must advance once per content chunk (on
 * its final frame).
 */

import { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import playerReducer from '@/store/slices/playerSlice';
import {
  useAudioStreamingCore,
  type StreamingCoreOptions,
} from '../useAudioStreamingCore';

// Isolate the increment logic from base64/PCM decoding: return metadata straight
// from the message's frame fields (decoding has its own dedicated tests).
vi.mock('@/utils/audio/pcmDecoding', () => ({
  decodeAudioChunkMessage: (message: any) => ({
    samples: new Float32Array(0),
    metadata: {
      chunkIndex: message.data.chunk_index ?? 0,
      frameIndex: message.data.frame_index ?? 0,
      frameCount: message.data.frame_count ?? 1,
      crossfadeSamples: 0,
      sampleCount: message.data.sample_count ?? 0,
    },
  }),
}));

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
  getStartThreshold: () => Number.POSITIVE_INFINITY, // never auto-start playback
  throttleProgress: false,
  detectOutOfSequence: false,
  closeContextOnCleanup: false,
};

function makeFakeBuffer() {
  return {
    append: vi.fn(),
    getFillPercentage: () => 0,
    getAvailableSamples: () => 0,
    reset: vi.fn(),
  };
}

function chunkMessage(chunkIndex: number, frameIndex: number, frameCount: number) {
  return {
    type: 'audio_chunk',
    data: {
      stream_type: 'enhanced',
      track_id: 1,
      chunk_index: chunkIndex,
      frame_index: frameIndex,
      frame_count: frameCount,
      sample_count: 100,
      samples: '',
    },
  };
}

describe('useAudioStreamingCore progress accounting (#4414)', () => {
  let store: ReturnType<typeof createStore>;
  let ws: ReturnType<typeof makeWs>;

  beforeEach(() => {
    store = createStore();
    ws = makeWs();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  function render(totalChunks: number) {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <Provider store={store}>{children}</Provider>
    );
    const hook = renderHook(() => useAudioStreamingCore(ws as never, OPTIONS), { wrapper });
    // Stand in for the caller's handleStreamStart, which normally seeds these
    // refs. playbackEngineRef stays null so the auto-start branch is skipped.
    hook.result.current.streamingMetadataRef.current = {
      sampleRate: 44100,
      channels: 2,
      totalChunks,
      processedChunks: 0,
    } as never;
    hook.result.current.pcmBufferRef.current = makeFakeBuffer() as never;
    return hook;
  }

  it('advances processedChunks once per content chunk, not once per frame', () => {
    const N = 3;   // content chunks
    const F = 5;   // frames per content chunk
    const { result } = render(N);

    for (let c = 0; c < N; c++) {
      for (let f = 0; f < F; f++) {
        act(() => { result.current.handleChunk(chunkMessage(c, f, F) as never); });
      }
    }

    // The bug counted N*F (=15); the fix counts N (=3). processedChunks is the
    // progress numerator (progress = processedChunks / totalChunks), so this is
    // the root of the "bar hits 100% during the first chunk" symptom.
    expect(result.current.streamingMetadataRef.current!.processedChunks).toBe(N);
  });

  it('does not pin progress at 100% partway through the stream', () => {
    const N = 4;
    const F = 6;
    const { result } = render(N);

    // Feed only the first content chunk (all its frames).
    for (let f = 0; f < F; f++) {
      act(() => { result.current.handleChunk(chunkMessage(0, f, F) as never); });
    }

    // One of four content chunks done → numerator 1 (25%), not ~F/4·100 as the
    // per-frame bug gave, which pinned the bar near 100% during the first chunk.
    expect(result.current.streamingMetadataRef.current!.processedChunks).toBe(1);
  });

  it('counts a single-frame content chunk exactly once (frameCount=1)', () => {
    const { result } = render(2);

    act(() => { result.current.handleChunk(chunkMessage(0, 0, 1) as never); });
    act(() => { result.current.handleChunk(chunkMessage(1, 0, 1) as never); });

    expect(result.current.streamingMetadataRef.current!.processedChunks).toBe(2);
  });
});
