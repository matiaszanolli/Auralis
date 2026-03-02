/**
 * usePlayNormal Tests
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Covers the PCM audio streaming pipeline managed by usePlayNormal:
 * - audio_stream_start: PCMStreamBuffer + AudioPlaybackEngine lifecycle
 * - audio_chunk: decode, accumulate, auto-start threshold (issue #2268)
 * - audio_stream_end: Redux complete dispatch
 * - audio_stream_error: error dispatch + cleanup
 * - Buffer threshold uses sampleRate * channels * 2 (not sampleRate * 1)
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import React from 'react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { usePlayNormal } from '../usePlayNormal';
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
      sample_rate: 44100,
      channels: 2,
      total_chunks: 10,
      chunk_duration: 30,
      total_duration: 300,
      stream_type: 'normal' as const,
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
      stream_type: 'normal' as const,
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
      stream_type: 'normal' as const,
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
      stream_type: 'normal' as const,
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
    samples: new Float32Array(44100),
    metadata: {
      chunkIndex: 0,
      frameIndex: 0,
      frameCount: 1,
      sampleCount: 44100,
      crossfadeSamples: 0,
    },
  } as any);

  // AudioContext mock
  mockAudioContextInstance = {
    sampleRate: 44100,
    close: vi.fn(),
    state: 'running',
  };
  vi.stubGlobal('AudioContext', vi.fn().mockImplementation(() => mockAudioContextInstance));
  vi.stubGlobal('webkitAudioContext', undefined);

  // fetch mock (used by playNormal to load track data)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: false,
    json: vi.fn().mockResolvedValue({}),
  }));

  // WebSocket context mock
  vi.mocked(WebSocketContextModule.useWebSocketContext).mockReturnValue({
    isConnected: mockWsConnected,
    send: mockSend,
    subscribe: vi.fn().mockImplementation((type: string, handler: any) => {
      handlers[type] = handler;
      mockUnsubscribers[type] = vi.fn();
      return mockUnsubscribers[type];
    }),
  } as any);
}

// ============================================================================
// Tests
// ============================================================================

describe('usePlayNormal', () => {
  let store: TestStore;
  let wrapper: ReturnType<typeof makeWrapper>;

  beforeEach(() => {
    setupMocks();
    store = createTestStore();
    wrapper = makeWrapper(store);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  // --------------------------------------------------------------------------
  // Subscription lifecycle
  // --------------------------------------------------------------------------

  describe('subscription lifecycle', () => {
    it('subscribes to audio_stream_start, audio_chunk, audio_stream_end, audio_stream_error on playNormal()', async () => {
      const { result } = renderHook(() => usePlayNormal(), { wrapper });

      await act(async () => {
        await result.current.playNormal(1);
      });

      expect(handlers['audio_stream_start']).toBeDefined();
      expect(handlers['audio_chunk']).toBeDefined();
      expect(handlers['audio_stream_end']).toBeDefined();
      expect(handlers['audio_stream_error']).toBeDefined();
    });

    it('sends play_normal WebSocket message with trackId', async () => {
      const { result } = renderHook(() => usePlayNormal(), { wrapper });

      await act(async () => {
        await result.current.playNormal(42);
      });

      expect(mockSend).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'play_normal', data: { track_id: 42 } })
      );
    });
  });

  // --------------------------------------------------------------------------
  // Stream start
  // --------------------------------------------------------------------------

  describe('audio_stream_start handling', () => {
    it('initializes PCMStreamBuffer with sample_rate and channels', async () => {
      const { result } = renderHook(() => usePlayNormal(), { wrapper });
      await act(async () => { await result.current.playNormal(1); });

      act(() => { handlers['audio_stream_start'](makeStreamStartMsg()); });

      expect(PCMStreamBuffer).toHaveBeenCalledTimes(1);
      expect(mockBufferInstance.initialize).toHaveBeenCalledWith(44100, 2);
    });

    it('creates AudioPlaybackEngine after PCMStreamBuffer', async () => {
      const { result } = renderHook(() => usePlayNormal(), { wrapper });
      await act(async () => { await result.current.playNormal(1); });

      act(() => { handlers['audio_stream_start'](makeStreamStartMsg()); });

      expect(AudioPlaybackEngine).toHaveBeenCalledTimes(1);
      expect(mockEngineInstance.onStateChanged).toHaveBeenCalled();
      expect(mockEngineInstance.onUnderrun).toHaveBeenCalled();
    });

    it('filters out non-normal stream_type', async () => {
      const { result } = renderHook(() => usePlayNormal(), { wrapper });
      await act(async () => { await result.current.playNormal(1); });

      act(() => {
        handlers['audio_stream_start'](makeStreamStartMsg({ stream_type: 'enhanced' }));
      });

      // PCMStreamBuffer must NOT have been created for an enhanced message
      expect(PCMStreamBuffer).not.toHaveBeenCalled();
    });
  });

  // --------------------------------------------------------------------------
  // Buffer threshold — issue #2268
  // --------------------------------------------------------------------------

  describe('buffer threshold — issue #2268', () => {
    // setupStream always starts with 0 buffered samples so that handleStreamStart
    // does NOT trigger the auto-start threshold; individual tests then set the
    // desired buffer level before sending the chunk message.
    async function setupStream(overrides: Record<string, any> = {}) {
      mockBufferInstance.getAvailableSamples.mockReturnValue(0);
      const { result } = renderHook(() => usePlayNormal(), { wrapper });
      await act(async () => { await result.current.playNormal(1); });
      act(() => { handlers['audio_stream_start'](makeStreamStartMsg(overrides)); });
      return result;
    }

    it('does NOT auto-start for stereo audio with only 1× sampleRate samples buffered', async () => {
      // 44100 samples == 0.5 seconds of stereo audio — below the 2s × 2ch threshold
      await setupStream({ sample_rate: 44100, channels: 2 });

      mockBufferInstance.getAvailableSamples.mockReturnValue(44100);
      act(() => { handlers['audio_chunk'](makeChunkMsg()); });

      expect(mockEngineInstance.startPlayback).not.toHaveBeenCalled();
    });

    it('auto-starts for stereo audio once sampleRate * channels * 2 samples are buffered', async () => {
      // 44100 * 2 * 2 = 176400 samples == 2 seconds of stereo audio
      await setupStream({ sample_rate: 44100, channels: 2 });

      mockBufferInstance.getAvailableSamples.mockReturnValue(44100 * 2 * 2);
      act(() => { handlers['audio_chunk'](makeChunkMsg()); });

      expect(mockEngineInstance.startPlayback).toHaveBeenCalledTimes(1);
    });

    it('auto-starts for mono audio once sampleRate * 1 * 2 samples are buffered', async () => {
      // For mono (channels=1): threshold = 44100 * 1 * 2 = 88200
      await setupStream({ sample_rate: 44100, channels: 1 });

      mockBufferInstance.getAvailableSamples.mockReturnValue(44100 * 1 * 2);
      act(() => { handlers['audio_chunk'](makeChunkMsg()); });

      expect(mockEngineInstance.startPlayback).toHaveBeenCalledTimes(1);
    });

    it('does NOT auto-start when already playing', async () => {
      await setupStream({ sample_rate: 44100, channels: 2 });

      // Pretend the engine is already playing before the chunk arrives
      mockEngineInstance.isPlaying.mockReturnValue(true);
      mockEngineInstance.startPlayback.mockClear();

      mockBufferInstance.getAvailableSamples.mockReturnValue(44100 * 2 * 2);
      act(() => { handlers['audio_chunk'](makeChunkMsg()); });

      expect(mockEngineInstance.startPlayback).not.toHaveBeenCalled();
    });

    it('threshold matches usePlayEnhanced formula: sampleRate * channels * 2', async () => {
      // Verify the boundary: exactly (threshold - 1) does not start,
      // exactly threshold does start.
      const sr = 48000;
      const ch = 2;
      const threshold = sr * ch * 2;  // 192000

      // One sample below threshold — no start
      await setupStream({ sample_rate: sr, channels: ch });
      mockBufferInstance.getAvailableSamples.mockReturnValue(threshold - 1);
      act(() => { handlers['audio_chunk'](makeChunkMsg()); });
      expect(mockEngineInstance.startPlayback).not.toHaveBeenCalled();

      // New hook instance at exactly the threshold — does start
      setupMocks();
      store = createTestStore();
      wrapper = makeWrapper(store);
      mockBufferInstance.getAvailableSamples.mockReturnValue(0);
      const { result: result2 } = renderHook(() => usePlayNormal(), { wrapper });
      await act(async () => { await result2.current.playNormal(1); });
      act(() => { handlers['audio_stream_start'](makeStreamStartMsg({ sample_rate: sr, channels: ch })); });
      mockBufferInstance.getAvailableSamples.mockReturnValue(threshold);
      act(() => { handlers['audio_chunk'](makeChunkMsg()); });
      expect(mockEngineInstance.startPlayback).toHaveBeenCalledTimes(1);
    });
  });

  // --------------------------------------------------------------------------
  // Stream end
  // --------------------------------------------------------------------------

  describe('audio_stream_end handling', () => {
    it('dispatches completeStreaming on stream end', async () => {
      const { result } = renderHook(() => usePlayNormal(), { wrapper });
      await act(async () => { await result.current.playNormal(1); });
      act(() => { handlers['audio_stream_start'](makeStreamStartMsg()); });

      act(() => { handlers['audio_stream_end'](makeStreamEndMsg()); });

      await waitFor(() => {
        const state = store.getState().player;
        expect(state.streaming.normal.state).toBe('complete');
      });
    });

    it('filters out non-normal stream_end', async () => {
      const { result } = renderHook(() => usePlayNormal(), { wrapper });
      await act(async () => { await result.current.playNormal(1); });

      act(() => {
        handlers['audio_stream_end'](makeStreamEndMsg({ stream_type: 'enhanced' }));
      });

      const state = store.getState().player;
      expect(state.streaming.normal.state).not.toBe('complete');
    });
  });

  // --------------------------------------------------------------------------
  // Stream error
  // --------------------------------------------------------------------------

  describe('audio_stream_error handling', () => {
    it('dispatches setStreamingError on error', async () => {
      const { result } = renderHook(() => usePlayNormal(), { wrapper });
      await act(async () => { await result.current.playNormal(1); });
      act(() => { handlers['audio_stream_start'](makeStreamStartMsg()); });

      act(() => { handlers['audio_stream_error'](makeStreamErrorMsg()); });

      await waitFor(() => {
        const state = store.getState().player;
        expect(state.streaming.normal.error).toContain('Encode failed');
      });
    });

    it('filters out non-normal stream_error', async () => {
      const { result } = renderHook(() => usePlayNormal(), { wrapper });
      await act(async () => { await result.current.playNormal(1); });

      act(() => {
        handlers['audio_stream_error'](makeStreamErrorMsg({ stream_type: 'enhanced' }));
      });

      const state = store.getState().player;
      expect(state.streaming.normal.error).toBeNull();
    });
  });

  // --------------------------------------------------------------------------
  // Playback control
  // --------------------------------------------------------------------------

  describe('playback controls', () => {
    async function setupWithEngine() {
      const { result } = renderHook(() => usePlayNormal(), { wrapper });
      await act(async () => { await result.current.playNormal(1); });
      act(() => { handlers['audio_stream_start'](makeStreamStartMsg()); });
      return result;
    }

    it('pausePlayback calls engine.pausePlayback', async () => {
      const result = await setupWithEngine();
      // The Redux isPlaying=false effect may auto-call pausePlayback when the engine
      // is created (same as usePlayEnhanced — clear before the explicit call).
      mockEngineInstance.pausePlayback.mockClear();
      act(() => { result.current.pausePlayback(); });
      expect(mockEngineInstance.pausePlayback).toHaveBeenCalled();
    });

    it('resumePlayback calls engine.resumePlayback', async () => {
      const result = await setupWithEngine();
      act(() => { result.current.resumePlayback(); });
      expect(mockEngineInstance.resumePlayback).toHaveBeenCalledTimes(1);
    });

    it('stopPlayback calls engine.stopPlayback', async () => {
      const result = await setupWithEngine();
      act(() => { result.current.stopPlayback(); });
      expect(mockEngineInstance.stopPlayback).toHaveBeenCalledTimes(1);
    });

    it('setVolume clamps and passes value to engine', async () => {
      const result = await setupWithEngine();
      act(() => { result.current.setVolume(0.7); });
      expect(mockEngineInstance.setVolume).toHaveBeenCalledWith(0.7);
    });
  });

  // --------------------------------------------------------------------------
  // WebSocket not connected
  // --------------------------------------------------------------------------

  describe('error when WebSocket disconnected', () => {
    it('dispatches streaming error when WS is not connected', async () => {
      vi.mocked(WebSocketContextModule.useWebSocketContext).mockReturnValue({
        isConnected: false,
        send: mockSend,
        subscribe: vi.fn().mockImplementation((type: string, handler: any) => {
          handlers[type] = handler;
          return vi.fn();
        }),
      } as any);

      const { result } = renderHook(() => usePlayNormal(), { wrapper });
      await act(async () => { await result.current.playNormal(1); });

      await waitFor(() => {
        const state = store.getState().player;
        expect(state.streaming.normal.error).toContain('WebSocket not connected');
      });
    });
  });
});
