/**
 * useAudioStreamingCore - stream epoch discards superseded frames (#4563)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * On seek the client resets its PCM buffer BEFORE sending the `seek` message,
 * but the backend cancels the prior streaming task only when its receive loop
 * dispatches that frame. Frames already queued server-side plus whatever sits
 * in socket buffers (~0.9-3.5 s of pre-seek audio) therefore arrive AFTER the
 * reset and are appended to the fresh buffer — and the follow-up
 * `audio_stream_start` carries `is_seek: true`, which by design tells the client
 * to PRESERVE its buffer, so the stale audio was never discarded.
 *
 * Nothing else on the wire distinguishes them: `track_id` is the same track,
 * `chunk_index` is >= the last seen so `detectOutOfSequence` (which fires only
 * on `incoming < last - 1`) never trips, and `seq` restarts at 0 each stream.
 * The epoch is the discriminator.
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

vi.mock('@/utils/audio/pcmDecoding', () => ({
  decodeAudioChunkMessage: (message: any) => ({
    samples: new Float32Array(message.data.sample_count ?? 0),
    metadata: {
      chunkIndex: message.data.chunk_index ?? 0,
      frameIndex: message.data.frame_index ?? 0,
      frameCount: message.data.frame_count ?? 1,
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
  getStartThreshold: () => Number.POSITIVE_INFINITY,
  throttleProgress: false,
  // Deliberately ON: the point is that this guard cannot catch stale frames,
  // because a superseded stream's chunk_index is never far enough behind.
  detectOutOfSequence: true,
  closeContextOnCleanup: false,
};

function makeFakeBuffer() {
  return {
    append: vi.fn(),
    getFillPercentage: () => 0,
    getAvailableSamples: () => 0,
    reset: vi.fn(),
    dispose: vi.fn(),
  };
}

function streamStart(epoch: number | undefined, isSeek = false) {
  return {
    type: 'audio_stream_start',
    data: {
      track_id: 1,
      preset: 'balanced',
      intensity: 0.5,
      sample_rate: 44100,
      channels: 2,
      total_chunks: 4,
      chunk_duration: 15,
      total_duration: 60,
      stream_type: 'enhanced',
      ...(epoch === undefined ? {} : { stream_epoch: epoch }),
      ...(isSeek ? { is_seek: true, start_chunk: 1, seek_position: 17 } : {}),
    },
  };
}

function chunk(epoch: number | undefined, chunkIndex = 0) {
  return {
    type: 'audio_chunk',
    data: {
      stream_type: 'enhanced',
      track_id: 1,
      ...(epoch === undefined ? {} : { stream_epoch: epoch }),
      chunk_index: chunkIndex,
      frame_index: 0,
      frame_count: 1,
      sample_count: 100,
      samples: '',
    },
  };
}

describe('useAudioStreamingCore stream epoch (#4563)', () => {
  let store: ReturnType<typeof createStore>;
  let ws: ReturnType<typeof makeWs>;

  beforeEach(() => {
    store = createStore();
    ws = makeWs();
    vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  function render() {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <Provider store={store}>{children}</Provider>
    );
    const hook = renderHook(() => useAudioStreamingCore(ws as never, OPTIONS), { wrapper });
    hook.result.current.streamingMetadataRef.current = {
      sampleRate: 44100,
      channels: 2,
      totalChunks: 4,
      processedChunks: 0,
    } as never;
    const buffer = makeFakeBuffer();
    hook.result.current.pcmBufferRef.current = buffer as never;
    return { ...hook, buffer };
  }

  it('drops a chunk from a superseded stream after a seek', () => {
    const { result, buffer } = render();

    // Stream 1 opens, delivers a frame.
    act(() => { ws.emit('audio_stream_start', streamStart(1)); });
    act(() => { result.current.handleChunk(chunk(1, 3) as never); });
    expect(buffer.append).toHaveBeenCalledTimes(1);

    // Seek: stream 2 opens with is_seek (buffer deliberately preserved).
    act(() => { ws.emit('audio_stream_start', streamStart(2, true)); });

    // An in-flight frame from stream 1 lands. chunk_index 4 is AHEAD of the
    // last seen, so detectOutOfSequence cannot catch it — only the epoch can.
    act(() => { result.current.handleChunk(chunk(1, 4) as never); });

    expect(buffer.append).toHaveBeenCalledTimes(1);
  });

  it('accepts chunks from the current stream after the seek', () => {
    const { result, buffer } = render();

    act(() => { ws.emit('audio_stream_start', streamStart(1)); });
    act(() => { ws.emit('audio_stream_start', streamStart(2, true)); });
    act(() => { result.current.handleChunk(chunk(2, 1) as never); });

    expect(buffer.append).toHaveBeenCalledTimes(1);
  });

  it('drops every stale frame in a burst, not just the first', () => {
    const { result, buffer } = render();

    act(() => { ws.emit('audio_stream_start', streamStart(5)); });
    act(() => { ws.emit('audio_stream_start', streamStart(6, true)); });

    // A full send-queue's worth of pre-seek frames.
    for (let i = 0; i < 4; i++) {
      act(() => { result.current.handleChunk(chunk(5, 10 + i) as never); });
    }

    expect(buffer.append).not.toHaveBeenCalled();
  });

  it('protects a WS reconnect-resume, which is also is_seek', () => {
    const { result, buffer } = render();

    act(() => { ws.emit('audio_stream_start', streamStart(7)); });
    act(() => { ws.emit('audio_stream_start', streamStart(8, true)); });
    act(() => { result.current.handleChunk(chunk(7) as never); });

    expect(buffer.append).not.toHaveBeenCalled();
  });

  it('accepts chunks when the backend sends no epoch (older server)', () => {
    const { result, buffer } = render();

    act(() => { ws.emit('audio_stream_start', streamStart(undefined)); });
    act(() => { result.current.handleChunk(chunk(undefined) as never); });

    expect(buffer.append).toHaveBeenCalledTimes(1);
  });

  it('accepts an un-stamped chunk even when a stream epoch is known', () => {
    // Degrade to previous behaviour rather than dropping everything.
    const { result, buffer } = render();

    act(() => { ws.emit('audio_stream_start', streamStart(3)); });
    act(() => { result.current.handleChunk(chunk(undefined) as never); });

    expect(buffer.append).toHaveBeenCalledTimes(1);
  });

  it('ignores an epoch from the other stream type', () => {
    // A concurrently-mounted normal-stream core must not rebaseline this one.
    const { result, buffer } = render();

    act(() => { ws.emit('audio_stream_start', streamStart(1)); });
    act(() => {
      ws.emit('audio_stream_start', {
        ...streamStart(99),
        data: { ...streamStart(99).data, stream_type: 'normal' },
      });
    });
    act(() => { result.current.handleChunk(chunk(1, 1) as never); });

    expect(buffer.append).toHaveBeenCalledTimes(1);
  });

  it('clears the epoch on cleanup', () => {
    const { result, buffer } = render();

    act(() => { ws.emit('audio_stream_start', streamStart(4)); });
    act(() => { result.current.cleanupStreaming(); });

    // After cleanup the caller re-seeds the refs for the next stream; a chunk
    // stamped with any epoch is accepted until a new stream_start arrives.
    result.current.streamingMetadataRef.current = {
      sampleRate: 44100, channels: 2, totalChunks: 4, processedChunks: 0,
    } as never;
    result.current.pcmBufferRef.current = buffer as never;
    act(() => { result.current.handleChunk(chunk(9) as never); });

    expect(buffer.append).toHaveBeenCalledTimes(1);
  });
});
