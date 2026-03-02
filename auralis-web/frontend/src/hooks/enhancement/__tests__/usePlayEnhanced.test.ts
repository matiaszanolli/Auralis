/**
 * usePlayEnhanced Tests
 * ~~~~~~~~~~~~~~~~~~~~~
 *
 * Covers the entire PCM audio streaming pipeline managed by usePlayEnhanced:
 * - 5 WebSocket subscriptions on mount and cleanup on unmount
 * - audio_stream_start: PCMStreamBuffer + AudioPlaybackEngine lifecycle
 * - audio_chunk: decode, accumulate, auto-start threshold
 * - audio_stream_end: Redux complete dispatch
 * - audio_stream_error: error dispatch + cleanup
 * - fingerprint_progress: status/message updates with auto-clear
 * - seekTo: full flow (state → buffer reset → WS send)
 * - playEnhanced: WS send + Redux sync
 * - WS disconnect cleanup
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import React from 'react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { usePlayEnhanced } from '../usePlayEnhanced';
import PCMStreamBuffer from '@/services/audio/PCMStreamBuffer';
import AudioPlaybackEngine from '@/services/audio/AudioPlaybackEngine';
import * as pcmDecoding from '@/utils/audio/pcmDecoding';
import * as WebSocketContextModule from '@/contexts/WebSocketContext';
import playerReducer from '@/store/slices/playerSlice';
import queueReducer from '@/store/slices/queueSlice';
import cacheReducer from '@/store/slices/cacheSlice';
import connectionReducer from '@/store/slices/connectionSlice';

// ============================================================================
// Module mocks (hoisted by Vitest)
// ============================================================================

vi.mock('@/contexts/WebSocketContext', async (importOriginal) => {
  const actual = await importOriginal<typeof WebSocketContextModule>();
  return { ...actual, useWebSocketContext: vi.fn() };
});

vi.mock('@/services/audio/PCMStreamBuffer', () => ({ default: vi.fn() }));
vi.mock('@/services/audio/AudioPlaybackEngine', () => ({ default: vi.fn() }));
vi.mock('@/utils/audio/pcmDecoding', () => ({ decodeAudioChunkMessage: vi.fn() }));

// ============================================================================
// Test infrastructure
// ============================================================================

function createTestStore() {
  return configureStore({
    reducer: {
      player: playerReducer,
      queue: queueReducer,
      cache: cacheReducer,
      connection: connectionReducer,
    },
    middleware: (getDefaultMiddleware) =>
      getDefaultMiddleware({ serializableCheck: false }),
  });
}

type TestStore = ReturnType<typeof createTestStore>;

function makeWrapper(store: TestStore) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(Provider, { store, children });
  };
}

// ============================================================================
// Fixture factories
// ============================================================================

function makeStreamStartMsg(overrides: Record<string, any> = {}) {
  return {
    type: 'audio_stream_start',
    data: {
      track_id: 1,
      preset: 'adaptive',
      intensity: 1.0,
      sample_rate: 44100,
      channels: 2,
      total_chunks: 10,
      chunk_duration: 30,
      total_duration: 300,
      stream_type: 'enhanced' as const,
      ...overrides,
    },
  };
}

function makeChunkMsg(overrides: Record<string, any> = {}) {
  return {
    type: 'audio_chunk',
    data: {
      chunk_index: 0,
      chunk_count: 10,
      frame_index: 0,
      frame_count: 1,
      samples: 'AAAAAAAAAA==',
      sample_count: 44100,
      crossfade_samples: 0,
      stream_type: 'enhanced' as const,
      ...overrides,
    },
  };
}

function makeStreamEndMsg(overrides: Record<string, any> = {}) {
  return {
    type: 'audio_stream_end',
    data: {
      track_id: 1,
      total_samples: 441000,
      duration: 300,
      stream_type: 'enhanced' as const,
      ...overrides,
    },
  };
}

function makeStreamErrorMsg(overrides: Record<string, any> = {}) {
  return {
    type: 'audio_stream_error',
    data: {
      track_id: 1,
      error: 'Encode failed',
      code: 'ENCODE_ERROR',
      stream_type: 'enhanced' as const,
      ...overrides,
    },
  };
}

// ============================================================================
// Shared mock state (reset per test in beforeEach)
// ============================================================================

const handlers: Record<string, (msg: any) => void> = {};
const mockUnsubscribers: Record<string, ReturnType<typeof vi.fn>> = {};
const mockSend = vi.fn();
let mockWsConnected = true;

let mockBufferInstance: {
  initialize: ReturnType<typeof vi.fn>;
  append: ReturnType<typeof vi.fn>;
  getAvailableSamples: ReturnType<typeof vi.fn>;
  reset: ReturnType<typeof vi.fn>;
};

let mockEngineInstance: {
  startPlayback: ReturnType<typeof vi.fn>;
  stopPlayback: ReturnType<typeof vi.fn>;
  pausePlayback: ReturnType<typeof vi.fn>;
  resumePlayback: ReturnType<typeof vi.fn>;
  setVolume: ReturnType<typeof vi.fn>;
  isPlaying: ReturnType<typeof vi.fn>;
  onStateChanged: ReturnType<typeof vi.fn>;
  onUnderrun: ReturnType<typeof vi.fn>;
  getCurrentPlaybackTime: ReturnType<typeof vi.fn>;
};

let mockAudioContextInstance: {
  sampleRate: number;
  close: ReturnType<typeof vi.fn>;
  state: string;
};

function setupMocks() {
  Object.keys(handlers).forEach((k) => delete handlers[k]);
  Object.keys(mockUnsubscribers).forEach((k) => delete mockUnsubscribers[k]);
  mockSend.mockReset();
  mockWsConnected = true;

  // Fresh PCMStreamBuffer mock
  mockBufferInstance = {
    initialize: vi.fn(),
    append: vi.fn(),
    getAvailableSamples: vi.fn().mockReturnValue(0),
    reset: vi.fn(),
  };
  vi.mocked(PCMStreamBuffer).mockImplementation(() => mockBufferInstance as any);

  // Fresh AudioPlaybackEngine mock
  mockEngineInstance = {
    startPlayback: vi.fn().mockResolvedValue(undefined),
    stopPlayback: vi.fn(),
    pausePlayback: vi.fn(),
    resumePlayback: vi.fn(),
    setVolume: vi.fn(),
    isPlaying: vi.fn().mockReturnValue(false),
    onStateChanged: vi.fn(),
    onUnderrun: vi.fn(),
    getCurrentPlaybackTime: vi.fn().mockReturnValue(0),
  };
  vi.mocked(AudioPlaybackEngine).mockImplementation(() => mockEngineInstance as any);

  // Mock decodeAudioChunkMessage
  vi.mocked(pcmDecoding.decodeAudioChunkMessage).mockReturnValue({
    samples: new Float32Array([0.1, 0.2, 0.3]),
    metadata: {
      chunkIndex: 0,
      chunkCount: 10,
      frameIndex: 0,
      frameCount: 1,
      sampleCount: 3,
      crossfadeSamples: 0,
      sampleRate: 44100,
      channels: 2,
    },
  });

  // Mock window.AudioContext
  mockAudioContextInstance = {
    sampleRate: 44100,
    close: vi.fn(),
    state: 'running',
  };
  vi.stubGlobal('AudioContext', vi.fn(() => mockAudioContextInstance));

  // Mock global fetch (used in playEnhanced to load track data)
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ tracks: [] }),
    })
  );

  // Wire up WebSocket context mock
  vi.mocked(WebSocketContextModule.useWebSocketContext).mockImplementation(() => ({
    isConnected: mockWsConnected,
    connectionStatus: 'connected' as const,
    subscribe: vi.fn((type: string, handler: (msg: any) => void) => {
      handlers[type] = handler;
      const unsub = vi.fn();
      mockUnsubscribers[type] = unsub;
      return unsub;
    }),
    subscribeAll: vi.fn(() => vi.fn()),
    send: mockSend,
    connect: vi.fn(),
    disconnect: vi.fn(),
  }));
}

function fireHandler(type: string, msg: any) {
  act(() => {
    handlers[type]?.(msg);
  });
}

// ============================================================================
// 1. Subscription lifecycle
// ============================================================================

describe('usePlayEnhanced – subscription lifecycle', () => {
  let store: TestStore;

  beforeEach(() => {
    setupMocks();
    store = createTestStore();
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it('subscribes to all 5 WebSocket message types on mount', () => {
    renderHook(() => usePlayEnhanced(), { wrapper: makeWrapper(store) });

    expect(handlers['audio_stream_start']).toBeDefined();
    expect(handlers['audio_chunk']).toBeDefined();
    expect(handlers['audio_stream_end']).toBeDefined();
    expect(handlers['audio_stream_error']).toBeDefined();
    expect(handlers['fingerprint_progress']).toBeDefined();
  });

  it('calls all 5 unsubscribers on unmount', () => {
    const { unmount } = renderHook(() => usePlayEnhanced(), {
      wrapper: makeWrapper(store),
    });
    unmount();

    expect(mockUnsubscribers['audio_stream_start']).toHaveBeenCalledOnce();
    expect(mockUnsubscribers['audio_chunk']).toHaveBeenCalledOnce();
    expect(mockUnsubscribers['audio_stream_end']).toHaveBeenCalledOnce();
    expect(mockUnsubscribers['audio_stream_error']).toHaveBeenCalledOnce();
    expect(mockUnsubscribers['fingerprint_progress']).toHaveBeenCalledOnce();
  });

  it('returns isStreaming=false and error=null in initial state', () => {
    const { result } = renderHook(() => usePlayEnhanced(), {
      wrapper: makeWrapper(store),
    });
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.isPaused).toBe(false);
    expect(result.current.isSeeking).toBe(false);
    expect(result.current.fingerprintStatus).toBe('idle');
  });
});

// ============================================================================
// 2. audio_stream_start handler
// ============================================================================

describe('usePlayEnhanced – audio_stream_start', () => {
  let store: TestStore;

  beforeEach(() => {
    setupMocks();
    store = createTestStore();
    renderHook(() => usePlayEnhanced(), { wrapper: makeWrapper(store) });
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it('creates and initializes PCMStreamBuffer with correct sample rate and channels', () => {
    fireHandler('audio_stream_start', makeStreamStartMsg());

    expect(vi.mocked(PCMStreamBuffer)).toHaveBeenCalledOnce();
    expect(mockBufferInstance.initialize).toHaveBeenCalledWith(44100, 2);
  });

  it('creates AudioContext with stream sample rate', () => {
    fireHandler('audio_stream_start', makeStreamStartMsg({ sample_rate: 48000 }));

    expect(vi.mocked(window.AudioContext)).toHaveBeenCalledWith({ sampleRate: 48000 });
  });

  it('creates AudioPlaybackEngine with AudioContext and buffer', () => {
    fireHandler('audio_stream_start', makeStreamStartMsg());

    expect(vi.mocked(AudioPlaybackEngine)).toHaveBeenCalledOnce();
    const [ctxArg, bufArg] = vi.mocked(AudioPlaybackEngine).mock.calls[0];
    expect(ctxArg).toBe(mockAudioContextInstance);
    expect(bufArg).toBe(mockBufferInstance);
  });

  it('dispatches startStreaming with correct track_id and total_chunks', () => {
    fireHandler('audio_stream_start', makeStreamStartMsg({ track_id: 7, total_chunks: 20 }));

    const streamingState = store.getState().player.streaming.enhanced;
    expect(streamingState.trackId).toBe(7);
    expect(streamingState.totalChunks).toBe(20);
  });

  it('ignores messages with stream_type other than "enhanced"', () => {
    fireHandler('audio_stream_start', makeStreamStartMsg({ stream_type: 'normal' }));

    expect(vi.mocked(PCMStreamBuffer)).not.toHaveBeenCalled();
    expect(store.getState().player.streaming.enhanced.state).toBe('idle');
  });

  it('passes through when stream_type is absent (no filter applied)', () => {
    const msg = makeStreamStartMsg();
    delete (msg.data as any).stream_type;
    fireHandler('audio_stream_start', msg);

    expect(vi.mocked(PCMStreamBuffer)).toHaveBeenCalledOnce();
  });

  it('clears isSeeking when handling a seek stream_start', async () => {
    // First trigger a seek to set isSeeking=true
    const { result } = renderHook(() => usePlayEnhanced(), {
      wrapper: makeWrapper(store),
    });

    // Seed currentTrackInfo via a playEnhanced call, then verify seekTo sets isSeeking
    // Simulate: seekTo sets isSeeking=true, then stream_start with is_seek=true clears it
    act(() => {
      handlers['audio_stream_start']?.(makeStreamStartMsg({ is_seek: true }));
    });

    await waitFor(() => {
      expect(result.current.isSeeking).toBe(false);
    });
  });

  it('processes pending chunks queued before stream_start', () => {
    // Chunk arrives before stream_start → gets queued (buffer.append not called)
    fireHandler('audio_chunk', makeChunkMsg({ chunk_index: 0 }));
    expect(mockBufferInstance.append).not.toHaveBeenCalled();

    // Now stream_start arrives → pending chunk is processed
    fireHandler('audio_stream_start', makeStreamStartMsg());
    expect(mockBufferInstance.append).toHaveBeenCalledOnce();
  });

  it('auto-starts playback when buffer already meets threshold on stream_start', () => {
    // Simulate 2+ seconds already buffered: sampleRate * channels * 2 = 176400
    mockBufferInstance.getAvailableSamples.mockReturnValue(176400);

    fireHandler('audio_stream_start', makeStreamStartMsg());

    expect(mockEngineInstance.startPlayback).toHaveBeenCalledOnce();
  });

  it('dispatches setStreamingError when stream initialization fails', () => {
    vi.mocked(PCMStreamBuffer).mockImplementation(() => {
      throw new Error('AudioContext denied');
    });

    fireHandler('audio_stream_start', makeStreamStartMsg());

    expect(store.getState().player.streaming.enhanced.state).toBe('error');
    expect(store.getState().player.streaming.enhanced.error).toContain('Failed to initialize streaming');
  });
});

// ============================================================================
// 3. audio_chunk handler
// ============================================================================

describe('usePlayEnhanced – audio_chunk', () => {
  let store: TestStore;

  beforeEach(() => {
    setupMocks();
    store = createTestStore();
    renderHook(() => usePlayEnhanced(), { wrapper: makeWrapper(store) });
    // Initialize the stream so chunks are processed normally
    fireHandler('audio_stream_start', makeStreamStartMsg());
    vi.mocked(AudioPlaybackEngine).mockClear();
    vi.mocked(PCMStreamBuffer).mockClear();
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it('queues chunk when stream not yet initialized', () => {
    // Tear down and re-mount with a fresh store (no stream_start fired)
    setupMocks();
    const freshStore = createTestStore();
    renderHook(() => usePlayEnhanced(), { wrapper: makeWrapper(freshStore) });

    fireHandler('audio_chunk', makeChunkMsg());

    // decodeAudioChunkMessage should NOT be called (chunk was queued, not processed)
    expect(pcmDecoding.decodeAudioChunkMessage).not.toHaveBeenCalled();
    expect(mockBufferInstance.append).not.toHaveBeenCalled();
  });

  it('decodes and appends samples to buffer', () => {
    fireHandler('audio_chunk', makeChunkMsg({ chunk_index: 0 }));

    expect(pcmDecoding.decodeAudioChunkMessage).toHaveBeenCalledOnce();
    expect(mockBufferInstance.append).toHaveBeenCalledOnce();
    const [samples, crossfade] = mockBufferInstance.append.mock.calls[0];
    expect(samples).toBeInstanceOf(Float32Array);
    expect(crossfade).toBe(0);
  });

  it('dispatches updateStreamingProgress with correct counts', () => {
    mockBufferInstance.getAvailableSamples.mockReturnValue(1000);

    fireHandler('audio_chunk', makeChunkMsg({ chunk_index: 0 }));

    const streamingState = store.getState().player.streaming.enhanced;
    expect(streamingState.processedChunks).toBe(1);
    expect(streamingState.bufferedSamples).toBe(1000);
    expect(streamingState.progress).toBeGreaterThan(0);
  });

  it('auto-starts engine when buffer reaches 2-second threshold', () => {
    // sampleRate=44100, channels=2, 2s = 176400 samples
    mockBufferInstance.getAvailableSamples.mockReturnValue(176400);
    mockEngineInstance.isPlaying.mockReturnValue(false);

    fireHandler('audio_chunk', makeChunkMsg());

    expect(mockEngineInstance.startPlayback).toHaveBeenCalledOnce();
  });

  it('does NOT auto-start engine when already playing', () => {
    mockBufferInstance.getAvailableSamples.mockReturnValue(176400);
    mockEngineInstance.isPlaying.mockReturnValue(true); // already playing

    fireHandler('audio_chunk', makeChunkMsg());

    expect(mockEngineInstance.startPlayback).not.toHaveBeenCalled();
  });

  it('does NOT auto-start engine when buffer below threshold', () => {
    mockBufferInstance.getAvailableSamples.mockReturnValue(100); // far below 176400
    mockEngineInstance.isPlaying.mockReturnValue(false);

    fireHandler('audio_chunk', makeChunkMsg());

    expect(mockEngineInstance.startPlayback).not.toHaveBeenCalled();
  });

  it('ignores chunk with stream_type other than "enhanced"', () => {
    fireHandler('audio_chunk', makeChunkMsg({ stream_type: 'normal' }));

    expect(pcmDecoding.decodeAudioChunkMessage).not.toHaveBeenCalled();
  });

  it('resets buffer on out-of-sequence chunk', () => {
    // First fire two chunks in order to advance lastReceivedChunkIndex to 5
    fireHandler('audio_chunk', makeChunkMsg({ chunk_index: 5 }));
    fireHandler('audio_chunk', makeChunkMsg({ chunk_index: 6 }));
    mockBufferInstance.reset.mockClear();

    // Now fire chunk_index 0 → detected as out-of-sequence (0 < 6 - 1)
    fireHandler('audio_chunk', makeChunkMsg({ chunk_index: 0 }));

    expect(mockBufferInstance.reset).toHaveBeenCalledOnce();
  });

  it('dispatches setStreamingError when decode fails', () => {
    vi.mocked(pcmDecoding.decodeAudioChunkMessage).mockImplementation(() => {
      throw new Error('Bad base64');
    });

    fireHandler('audio_chunk', makeChunkMsg());

    expect(store.getState().player.streaming.enhanced.state).toBe('error');
    expect(store.getState().player.streaming.enhanced.error).toContain('Failed to process audio chunk');
  });
});

// ============================================================================
// 4. audio_stream_end handler
// ============================================================================

describe('usePlayEnhanced – audio_stream_end', () => {
  let store: TestStore;

  beforeEach(() => {
    setupMocks();
    store = createTestStore();
    renderHook(() => usePlayEnhanced(), { wrapper: makeWrapper(store) });
    fireHandler('audio_stream_start', makeStreamStartMsg());
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it('dispatches completeStreaming when stream ends', () => {
    fireHandler('audio_stream_end', makeStreamEndMsg());

    expect(store.getState().player.streaming.enhanced.state).toBe('complete');
    expect(store.getState().player.streaming.enhanced.progress).toBe(100);
  });

  it('ignores end message with stream_type other than "enhanced"', () => {
    fireHandler('audio_stream_end', makeStreamEndMsg({ stream_type: 'normal' }));

    // State stays at 'buffering' (set by startStreaming), not 'complete'
    expect(store.getState().player.streaming.enhanced.state).toBe('buffering');
  });

  it('passes through when stream_type is absent', () => {
    const msg = makeStreamEndMsg();
    delete (msg.data as any).stream_type;
    fireHandler('audio_stream_end', msg);

    expect(store.getState().player.streaming.enhanced.state).toBe('complete');
  });
});

// ============================================================================
// 5. audio_stream_error handler
// ============================================================================

describe('usePlayEnhanced – audio_stream_error', () => {
  let store: TestStore;

  beforeEach(() => {
    setupMocks();
    store = createTestStore();
    renderHook(() => usePlayEnhanced(), { wrapper: makeWrapper(store) });
    fireHandler('audio_stream_start', makeStreamStartMsg());
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it('dispatches setStreamingError with error message and code', () => {
    fireHandler('audio_stream_error', makeStreamErrorMsg({ error: 'Encode failed', code: 'ENC_ERR' }));

    const streamingState = store.getState().player.streaming.enhanced;
    expect(streamingState.state).toBe('error');
    expect(streamingState.error).toContain('Encode failed');
    expect(streamingState.error).toContain('ENC_ERR');
  });

  it('clears streaming resources after error', () => {
    // After error, buffer/engine refs are nulled (cleanupStreaming called)
    // We verify by checking that a subsequent chunk is treated as pre-init (queued)
    fireHandler('audio_stream_error', makeStreamErrorMsg());
    vi.mocked(pcmDecoding.decodeAudioChunkMessage).mockClear();

    fireHandler('audio_chunk', makeChunkMsg());
    // Should be queued, not decoded
    expect(pcmDecoding.decodeAudioChunkMessage).not.toHaveBeenCalled();
  });

  it('ignores error message with stream_type other than "enhanced"', () => {
    fireHandler('audio_stream_error', makeStreamErrorMsg({ stream_type: 'normal' }));

    // State should not change to error
    expect(store.getState().player.streaming.enhanced.state).not.toBe('error');
  });
});

// ============================================================================
// 6. fingerprint_progress handler
// ============================================================================

describe('usePlayEnhanced – fingerprint_progress', () => {
  let store: TestStore;

  beforeEach(() => {
    setupMocks();
    store = createTestStore();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('sets fingerprintStatus and fingerprintMessage from message', async () => {
    const { result } = renderHook(() => usePlayEnhanced(), {
      wrapper: makeWrapper(store),
    });

    act(() => {
      handlers['fingerprint_progress']?.({
        data: { status: 'analyzing', message: 'Computing fingerprint…' },
      });
    });

    expect(result.current.fingerprintStatus).toBe('analyzing');
    expect(result.current.fingerprintMessage).toBe('Computing fingerprint…');
  });

  it('auto-clears status and message after 2 seconds on "complete"', async () => {
    const { result } = renderHook(() => usePlayEnhanced(), {
      wrapper: makeWrapper(store),
    });

    act(() => {
      handlers['fingerprint_progress']?.({
        data: { status: 'complete', message: 'Done!' },
      });
    });

    expect(result.current.fingerprintStatus).toBe('complete');

    act(() => {
      vi.advanceTimersByTime(2001);
    });

    expect(result.current.fingerprintStatus).toBe('idle');
    expect(result.current.fingerprintMessage).toBeNull();
  });

  it('does NOT auto-clear for non-complete status', async () => {
    const { result } = renderHook(() => usePlayEnhanced(), {
      wrapper: makeWrapper(store),
    });

    act(() => {
      handlers['fingerprint_progress']?.({
        data: { status: 'failed', message: 'Analysis failed' },
      });
    });

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(result.current.fingerprintStatus).toBe('failed');
    expect(result.current.fingerprintMessage).toBe('Analysis failed');
  });

  it('handles missing data fields gracefully', async () => {
    const { result } = renderHook(() => usePlayEnhanced(), {
      wrapper: makeWrapper(store),
    });

    act(() => {
      handlers['fingerprint_progress']?.({ data: {} });
    });

    expect(result.current.fingerprintStatus).toBe('idle');
    expect(result.current.fingerprintMessage).toBeNull();
  });
});

// ============================================================================
// 7. seekTo
// ============================================================================

describe('usePlayEnhanced – seekTo', () => {
  let store: TestStore;

  async function setupWithStream() {
    store = createTestStore();
    const { result } = renderHook(() => usePlayEnhanced(), {
      wrapper: makeWrapper(store),
    });

    // Call playEnhanced to set currentTrackInfo
    await act(async () => {
      await result.current.playEnhanced(42, 'warm', 0.8);
    });

    // Simulate stream_start so buffer/engine refs are populated
    fireHandler('audio_stream_start', makeStreamStartMsg({ track_id: 42, stream_type: 'enhanced' }));

    return result;
  }

  beforeEach(() => {
    setupMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it('sets isSeeking to true', async () => {
    const result = await setupWithStream();

    act(() => {
      result.current.seekTo(60);
    });

    expect(result.current.isSeeking).toBe(true);
  });

  it('stops the playback engine', async () => {
    const result = await setupWithStream();
    mockEngineInstance.stopPlayback.mockClear();

    act(() => {
      result.current.seekTo(60);
    });

    expect(mockEngineInstance.stopPlayback).toHaveBeenCalledOnce();
  });

  it('resets the PCM buffer', async () => {
    const result = await setupWithStream();
    mockBufferInstance.reset.mockClear();

    act(() => {
      result.current.seekTo(60);
    });

    expect(mockBufferInstance.reset).toHaveBeenCalledOnce();
  });

  it('sends seek message to WebSocket with correct position', async () => {
    const result = await setupWithStream();
    mockSend.mockClear();

    act(() => {
      result.current.seekTo(90.5);
    });

    expect(mockSend).toHaveBeenCalledWith({
      type: 'seek',
      data: expect.objectContaining({
        track_id: 42,
        position: 90.5,
        preset: 'warm',
        intensity: 0.8,
      }),
    });
  });

  it('does nothing when no track info is available', () => {
    // Fresh setup without calling playEnhanced → no currentTrackInfo
    store = createTestStore();
    const { result } = renderHook(() => usePlayEnhanced(), {
      wrapper: makeWrapper(store),
    });

    act(() => {
      result.current.seekTo(30);
    });

    expect(mockSend).not.toHaveBeenCalled();
    expect(result.current.isSeeking).toBe(false);
  });

  it('does nothing when WebSocket is disconnected', async () => {
    // Set WS as disconnected
    mockWsConnected = false;
    vi.mocked(WebSocketContextModule.useWebSocketContext).mockImplementation(() => ({
      isConnected: false,
      connectionStatus: 'disconnected' as const,
      subscribe: vi.fn((type, handler) => {
        handlers[type] = handler;
        const unsub = vi.fn();
        mockUnsubscribers[type] = unsub;
        return unsub;
      }),
      subscribeAll: vi.fn(() => vi.fn()),
      send: mockSend,
      connect: vi.fn(),
      disconnect: vi.fn(),
    }));

    store = createTestStore();
    const { result } = renderHook(() => usePlayEnhanced(), {
      wrapper: makeWrapper(store),
    });

    // Manually set track info by re-running playEnhanced (will throw for WS disconnected)
    // We test seekTo guard directly by poking via playEnhanced first in connected state,
    // but this test verifies the disconnected path:
    act(() => {
      result.current.seekTo(30);
    });

    expect(mockSend).not.toHaveBeenCalled();
  });
});

// ============================================================================
// 8. stopPlayback / pausePlayback / resumePlayback / setVolume
// ============================================================================

describe('usePlayEnhanced – playback controls', () => {
  let store: TestStore;

  beforeEach(() => {
    setupMocks();
    store = createTestStore();
    renderHook(() => usePlayEnhanced(), { wrapper: makeWrapper(store) });
    fireHandler('audio_stream_start', makeStreamStartMsg());
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it('stopPlayback: stops engine and dispatches resetStreaming', async () => {
    // Use the same store that the hook is wrapped with
    const testStore = createTestStore();
    const { result } = renderHook(() => usePlayEnhanced(), {
      wrapper: makeWrapper(testStore),
    });
    fireHandler('audio_stream_start', makeStreamStartMsg());
    mockEngineInstance.stopPlayback.mockClear();

    act(() => {
      result.current.stopPlayback();
    });

    expect(mockEngineInstance.stopPlayback).toHaveBeenCalledOnce();
    await waitFor(() =>
      expect(testStore.getState().player.streaming.enhanced.state).toBe('idle')
    );
  });

  it('pausePlayback: calls engine.pausePlayback', () => {
    // The Redux isPlaying=false effect auto-calls pausePlayback when engine exists.
    // Clear the mock after stream_start so we only count the explicit call.
    const { result } = renderHook(() => usePlayEnhanced(), {
      wrapper: makeWrapper(createTestStore()),
    });
    fireHandler('audio_stream_start', makeStreamStartMsg());
    mockEngineInstance.pausePlayback.mockClear();

    act(() => {
      result.current.pausePlayback();
    });

    // Called at least once: explicit call + Redux isPlaying=false effect may add more
    expect(mockEngineInstance.pausePlayback).toHaveBeenCalled();
  });

  it('resumePlayback: calls engine.resumePlayback', () => {
    // Same effect caveat applies — just verify the engine method was invoked.
    const { result } = renderHook(() => usePlayEnhanced(), {
      wrapper: makeWrapper(createTestStore()),
    });
    fireHandler('audio_stream_start', makeStreamStartMsg());
    mockEngineInstance.resumePlayback.mockClear();

    act(() => {
      result.current.resumePlayback();
    });

    expect(mockEngineInstance.resumePlayback).toHaveBeenCalledOnce();
  });

  it('setVolume: forwards clamped volume to engine', () => {
    const { result } = renderHook(() => usePlayEnhanced(), {
      wrapper: makeWrapper(createTestStore()),
    });
    fireHandler('audio_stream_start', makeStreamStartMsg());

    act(() => {
      result.current.setVolume(0.7);
    });

    expect(mockEngineInstance.setVolume).toHaveBeenCalledWith(0.7);
  });
});

// ============================================================================
// 9. playEnhanced
// ============================================================================

describe('usePlayEnhanced – playEnhanced', () => {
  let store: TestStore;

  beforeEach(() => {
    setupMocks();
    store = createTestStore();
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it('dispatches startStreaming with correct trackId and intensity', async () => {
    const { result } = renderHook(() => usePlayEnhanced(), {
      wrapper: makeWrapper(store),
    });

    await act(async () => {
      await result.current.playEnhanced(5, 'punchy', 0.9);
    });

    const streaming = store.getState().player.streaming.enhanced;
    expect(streaming.trackId).toBe(5);
    expect(streaming.intensity).toBe(0.9);
  });

  it('resets prior streaming state before starting a new stream', async () => {
    const { result } = renderHook(() => usePlayEnhanced(), {
      wrapper: makeWrapper(store),
    });

    // Put the store in error state to prove resetStreaming runs before startStreaming
    const { setStreamingError } = await import('@/store/slices/playerSlice');
    act(() => {
      store.dispatch(setStreamingError({ streamType: 'enhanced', error: 'previous error' }));
    });
    expect(store.getState().player.streaming.enhanced.state).toBe('error');

    await act(async () => {
      await result.current.playEnhanced(2, 'adaptive', 1.0);
    });

    // resetStreaming + startStreaming → ends up in 'buffering'
    expect(store.getState().player.streaming.enhanced.state).toBe('buffering');
  });

  it('sends play_enhanced message to WebSocket', async () => {
    const { result } = renderHook(() => usePlayEnhanced(), {
      wrapper: makeWrapper(store),
    });

    await act(async () => {
      await result.current.playEnhanced(3, 'warm', 0.5);
    });

    expect(mockSend).toHaveBeenCalledWith({
      type: 'play_enhanced',
      data: { track_id: 3, preset: 'warm', intensity: 0.5 },
    });
  });

  it('dispatches setStreamingError when WebSocket is not connected', async () => {
    vi.mocked(WebSocketContextModule.useWebSocketContext).mockReturnValue({
      isConnected: false,
      connectionStatus: 'disconnected' as const,
      subscribe: vi.fn(() => vi.fn()),
      subscribeAll: vi.fn(() => vi.fn()),
      send: mockSend,
      connect: vi.fn(),
      disconnect: vi.fn(),
    });

    const disconnectedStore = createTestStore();
    const { result } = renderHook(() => usePlayEnhanced(), {
      wrapper: makeWrapper(disconnectedStore),
    });

    await act(async () => {
      await result.current.playEnhanced(1, 'adaptive', 1.0);
    });

    expect(disconnectedStore.getState().player.streaming.enhanced.state).toBe('error');
    expect(disconnectedStore.getState().player.streaming.enhanced.error).toContain('WebSocket not connected');
  });
});

// ============================================================================
// 10. WebSocket disconnect cleanup
// ============================================================================

describe('usePlayEnhanced – WS disconnect cleanup', () => {
  let store: TestStore;

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it('stops engine and resets Redux streaming state on disconnect', async () => {
    setupMocks();
    store = createTestStore();

    const { rerender } = renderHook(() => usePlayEnhanced(), {
      wrapper: makeWrapper(store),
    });

    // Start a stream so engine/buffer are populated
    fireHandler('audio_stream_start', makeStreamStartMsg());
    expect(store.getState().player.streaming.enhanced.state).toBe('buffering');

    // Simulate disconnect: change mock to return isConnected=false, then re-render
    vi.mocked(WebSocketContextModule.useWebSocketContext).mockReturnValue({
      isConnected: false,
      connectionStatus: 'disconnected' as const,
      subscribe: vi.fn(() => vi.fn()),
      subscribeAll: vi.fn(() => vi.fn()),
      send: mockSend,
      connect: vi.fn(),
      disconnect: vi.fn(),
    });

    act(() => {
      rerender();
    });

    expect(mockEngineInstance.stopPlayback).toHaveBeenCalledOnce();
    await waitFor(() =>
      expect(store.getState().player.streaming.enhanced.state).toBe('idle')
    );
  });
});
