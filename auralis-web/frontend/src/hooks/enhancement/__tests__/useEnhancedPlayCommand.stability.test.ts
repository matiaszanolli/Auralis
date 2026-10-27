/**
 * useEnhancedPlayCommand callback-identity tests (#4608)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * `useAudioStreamingCore` returns a bare object literal, so `core` has a new
 * identity on every render. `useEnhancedPlayCommand` listed the whole `core`
 * object in its dep array, so `playEnhanced` never stabilized — which cascaded
 * into Player.tsx's handleNext/handlePrevious/handlePlayPause and the
 * auto-advance effect keyed on them.
 *
 * The regression these tests lock in: a re-render that produces a fresh `core`
 * wrapper around the SAME underlying refs must NOT produce a new `playEnhanced`.
 *
 * Note this is why memoizing useAudioStreamingCore's return object would not
 * have fixed it — that object also carries `currentTime`, which changes ~10x/s
 * during playback, so the memo would invalidate just as often.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { useEnhancedPlayCommand } from '../useEnhancedPlayCommand';

vi.mock('@/contexts/WebSocketContext', () => ({
  useWebSocketContext: () => ({ isConnected: true, send: vi.fn() }),
}));

/**
 * Stable ref containers, mirroring useAudioStreamingCore's useRef fields.
 * Created once and shared across every simulated render.
 */
function makeStableRefs() {
  return {
    handleStreamStartRef: { current: null },
    pcmBufferRef: { current: null },
    playbackEngineRef: { current: null },
    audioContextRef: { current: null },
    abortRef: { current: null },
    pendingChunksRef: { current: [] },
    streamingMetadataRef: { current: null },
    flowPausedRef: { current: false },
    lastReceivedChunkIndexRef: { current: -1 },
    lastDispatchedProgressRef: { current: 0 },
  };
}

describe('useEnhancedPlayCommand identity stability (#4608)', () => {
  it('keeps playEnhanced stable when core is a fresh object over the same refs', () => {
    const refs = makeStableRefs();
    const armStreamStartWatchdog = vi.fn();
    const dispatch = vi.fn() as any;
    const currentTrackInfoRef = { current: null } as any;
    const resetFingerprint = vi.fn();

    // Each render rebuilds the wrapper object exactly as useAudioStreamingCore
    // does — new identity, same refs, and a changing `currentTime`.
    let tick = 0;
    const buildCore = () =>
      ({
        ...refs,
        currentTime: tick++,
        setCurrentTime: vi.fn(),
        isPaused: false,
        setIsPaused: vi.fn(),
        cleanupStreaming: vi.fn(),
        armStreamStartWatchdog,
        handleChunk: vi.fn(),
        handleStreamEnd: vi.fn(),
        handleStreamError: vi.fn(),
        stopPlayback: vi.fn(),
        pausePlayback: vi.fn(),
        resumePlayback: vi.fn(),
        setVolume: vi.fn(),
      }) as any;

    // Stable across renders, as in the real app (WebSocketContext's value is
    // memoized and dispatch is stable) — so `core` is the only variable here.
    const wsContext = { isConnected: true, send: vi.fn() } as any;

    const { result, rerender } = renderHook(() =>
      useEnhancedPlayCommand({
        wsContext,
        dispatch,
        core: buildCore(),
        currentTrackInfoRef,
        resetFingerprint,
      })
    );

    const first = result.current;
    rerender();
    const second = result.current;
    rerender();
    const third = result.current;

    expect(second).toBe(first);
    expect(third).toBe(first);
  });

  it('produces a new playEnhanced when a ref container actually changes', () => {
    const armStreamStartWatchdog = vi.fn();
    let refs = makeStableRefs();

    const build = () =>
      ({
        ...refs,
        currentTime: 0,
        setCurrentTime: vi.fn(),
        isPaused: false,
        setIsPaused: vi.fn(),
        cleanupStreaming: vi.fn(),
        armStreamStartWatchdog,
        handleChunk: vi.fn(),
        handleStreamEnd: vi.fn(),
        handleStreamError: vi.fn(),
        stopPlayback: vi.fn(),
        pausePlayback: vi.fn(),
        resumePlayback: vi.fn(),
        setVolume: vi.fn(),
      }) as any;

    // Everything except the refs is held stable, so a changed identity can only
    // be attributed to the ref swap below.
    const wsContext = { isConnected: true, send: vi.fn() } as any;
    const dispatch = vi.fn() as any;
    const currentTrackInfoRef = { current: null } as any;
    const resetFingerprint = vi.fn();

    const { result, rerender } = renderHook(() =>
      useEnhancedPlayCommand({
        wsContext,
        dispatch,
        core: build(),
        currentTrackInfoRef,
        resetFingerprint,
      })
    );

    const before = result.current;

    // Swap the ref containers — a genuine input change, so the callback SHOULD
    // be rebuilt. Guards against "stable" being achieved by an empty dep array.
    refs = makeStableRefs();
    rerender();

    expect(result.current).not.toBe(before);
  });
});

describe('useEnhancedPlayCommand metadata load is non-blocking (#5649)', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  function setup() {
    const refs = makeStableRefs();
    const send = vi.fn();
    const dispatch = vi.fn() as any;
    const core = {
      ...refs,
      pauseHoldRef: { current: false },
      armStreamStartWatchdog: vi.fn(),
    } as any;
    const wsContext = { isConnected: true, send } as any;
    const { result } = renderHook(() =>
      useEnhancedPlayCommand({
        wsContext,
        dispatch,
        core,
        currentTrackInfoRef: { current: null } as any,
        resetFingerprint: vi.fn(),
      })
    );
    return { result, send, dispatch, core };
  }

  it('sends the play command and starts buffering while the metadata GET never resolves', async () => {
    // A REST path that never answers must not hold playback hostage.
    global.fetch = vi.fn().mockImplementation(() => new Promise<Response>(() => {}));
    const { result, send, dispatch, core } = setup();

    await act(async () => {
      await result.current(7, 'adaptive' as any, 1);
    });

    expect(send).toHaveBeenCalledWith({
      type: 'play_enhanced',
      data: { track_id: 7, preset: 'adaptive', intensity: 1 },
    });
    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({ type: expect.stringContaining('startStreaming') })
    );
    expect(core.armStreamStartWatchdog).toHaveBeenCalled();
  });

  it('a failed metadata GET is logged and does not stop playback or raise a streaming error', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      headers: new Headers(),
      json: () => Promise.resolve({ detail: 'boom' }),
      text: () => Promise.resolve('{"detail":"boom"}'),
    });
    const { result, send, dispatch } = setup();

    await act(async () => {
      await result.current(7, 'adaptive' as any, 1);
    });

    expect(send).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(warn).toHaveBeenCalled());
    expect(dispatch).not.toHaveBeenCalledWith(
      expect.objectContaining({ type: expect.stringContaining('setStreamingError') })
    );
  });

  it('aborts the previous invocation\'s metadata request when a new play starts', async () => {
    const signals: AbortSignal[] = [];
    global.fetch = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      if (init?.signal) signals.push(init.signal);
      return new Promise<Response>(() => {});
    });
    const { result } = setup();

    await act(async () => {
      await result.current(1, 'adaptive' as any, 1);
    });
    await waitFor(() => expect(signals).toHaveLength(1));
    await act(async () => {
      await result.current(2, 'adaptive' as any, 1);
    });
    await waitFor(() => expect(signals).toHaveLength(2));

    expect(signals[0].aborted).toBe(true);
    expect(signals[1].aborted).toBe(false);
  });
});
