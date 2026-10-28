/**
 * useAudioStreamingCore - a skipped chunk does not end playback (#5867)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * After a per-chunk processing error the backend skips the chunk and keeps
 * streaming (#3190), marking that audio_stream_error `continues: true`. The
 * client used to tear down its engine and buffer on every error, so playback
 * ended at the bad chunk and the rest of the track queued in pendingChunksRef
 * without bound. A continuing error now keeps the stream; the queue is capped.
 */

import { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import playerReducer from '@/store/slices/playerSlice';
import { useAudioStreamingCore, type StreamingCoreOptions } from '../useAudioStreamingCore';
import { MAX_PENDING_CHUNK_FRAMES } from '../audioChunkIngest';
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

const chunkError = (extra: Record<string, unknown>) => ({
  data: { stream_type: 'enhanced', track_id: 1, error: 'Failed to process audio chunk 3', code: 'E', ...extra },
});

describe('useAudioStreamingCore chunk errors (#5867)', () => {
  let ws: ReturnType<typeof makeWs>;

  beforeEach(() => {
    ws = makeWs();
    vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    resetConnectionSingletons();
    connState.lastStreamCommand = { type: 'play_enhanced', data: { track_id: 1 } };
    connState.streamActive = true;
  });

  afterEach(() => {
    resetConnectionSingletons();
    vi.restoreAllMocks();
  });

  function render() {
    const store = configureStore({ reducer: { player: playerReducer } });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <Provider store={store}>{children}</Provider>
    );
    const hook = renderHook(() => useAudioStreamingCore(ws as never, OPTIONS), { wrapper });
    // A playing stream: buffer, engine and metadata in place.
    const buffer = { dispose: vi.fn() };
    const engine = { dispose: vi.fn() };
    const core = hook.result.current;
    core.pcmBufferRef.current = buffer as never;
    core.playbackEngineRef.current = engine as never;
    core.streamingMetadataRef.current = { processedChunks: 3 } as never;
    return { core, buffer, engine };
  }

  it('keeps the engine and buffer on an error the backend continues past', () => {
    const { core, buffer, engine } = render();

    act(() => { ws.emit('audio_stream_error', chunkError({ recovery_position: 30, continues: true })); });

    expect(buffer.dispose).not.toHaveBeenCalled();
    expect(engine.dispose).not.toHaveBeenCalled();
    expect(core.pcmBufferRef.current).toBe(buffer);
    expect(core.streamingMetadataRef.current).not.toBeNull();
    // No restart from the failed chunk: the stream never stopped.
    expect(ws.reissueActiveStreamAs).not.toHaveBeenCalled();
    expect(connState.streamActive).toBe(true);
  });

  it('still tears down and auto-resumes when the stream stopped', () => {
    const { core, buffer } = render();

    act(() => { ws.emit('audio_stream_error', chunkError({ recovery_position: 30 })); });

    expect(buffer.dispose).toHaveBeenCalled();
    expect(core.pcmBufferRef.current).toBeNull();
    expect(ws.reissueActiveStreamAs).toHaveBeenCalledWith('play_enhanced', {}, 30);
  });

  it('bounds the frames queued while no stream is initialized', () => {
    const { core } = render();
    act(() => { ws.emit('audio_stream_error', chunkError({})); }); // terminal: teardown

    for (let i = 0; i < MAX_PENDING_CHUNK_FRAMES + 40; i++) {
      act(() => {
        ws.emit('audio_chunk', { data: { stream_type: 'enhanced', track_id: 1, chunk_index: i } });
      });
    }

    expect(core.pendingChunksRef.current).toHaveLength(MAX_PENDING_CHUNK_FRAMES);
  });
});
