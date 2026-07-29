/**
 * usePlayTrack Tests (#4151)
 *
 * usePlayTrack is the single "play this track now" entry point (replaces
 * onTrackPlay prop drilling, #3940). It combines a REST queue POST with a
 * `play_enhanced` WebSocket send, gated by an ok-guard so a failed queue POST
 * never starts a ghost stream (#3953). It also aborts the in-flight POST on
 * unmount so a stray stream/toast doesn't fire after navigating away (#4161).
 *
 * These tests pin that contract:
 *   - success: POST then send(play_enhanced) then success toast
 *   - failed queue POST: NO send, error toast (ghost-stream guard)
 *   - correct play_enhanced payload (track_id / preset / intensity)
 *   - network rejection: error toast, no send
 *   - AbortError: silent (no toast, no send)
 *   - unmount mid-POST: no send, no toast
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePlayTrack } from '../usePlayTrack';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { useToast } from '@/components/shared/Toast';

// Mock collaborators. getApiUrl is mocked to identity so the fetch URL is
// asserted as the bare path regardless of the configured API base.
vi.mock('@/contexts/WebSocketContext', () => ({ useWebSocketContext: vi.fn() }));
vi.mock('@/components/shared/Toast', () => ({ useToast: vi.fn() }));
vi.mock('@/config/api', () => ({ getApiUrl: (path: string) => path }));

const mockSend = vi.fn();
const mockSuccess = vi.fn();
const mockError = vi.fn();
let mockFetch: ReturnType<typeof vi.fn>;

const track = { id: 42, title: 'Test Song' };

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(useWebSocketContext).mockReturnValue({ send: mockSend } as any);
  vi.mocked(useToast).mockReturnValue({ success: mockSuccess, error: mockError } as any);
  mockFetch = vi.fn();
  vi.stubGlobal('fetch', mockFetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('usePlayTrack', () => {
  it('on success: POSTs the queue, then sends play_enhanced, then toasts', async () => {
    mockFetch.mockResolvedValue({ ok: true, status: 200 });

    const { result } = renderHook(() => usePlayTrack());
    await act(async () => {
      await result.current.playTrack(track);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/player/queue',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ tracks: [42], start_index: 0 }),
      })
    );
    expect(mockSend).toHaveBeenCalledWith({
      type: 'play_enhanced',
      data: { track_id: 42, preset: 'adaptive', intensity: 1.0 },
    });
    expect(mockSuccess).toHaveBeenCalledWith('Now playing: Test Song');
    expect(mockError).not.toHaveBeenCalled();
  });

  it('does NOT send and shows an error toast when the queue POST fails (ghost-stream guard)', async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500, statusText: 'Internal Server Error' });

    const { result } = renderHook(() => usePlayTrack());
    await act(async () => {
      await result.current.playTrack(track);
    });

    expect(mockSend).not.toHaveBeenCalled();
    expect(mockSuccess).not.toHaveBeenCalled();
    expect(mockError).toHaveBeenCalledTimes(1);
    expect(mockError).toHaveBeenCalledWith(expect.stringContaining('500'));
  });

  it('sends the correct play_enhanced payload (track_id / preset / intensity)', async () => {
    mockFetch.mockResolvedValue({ ok: true, status: 200 });

    const { result } = renderHook(() => usePlayTrack());
    await act(async () => {
      await result.current.playTrack({ id: 7, title: 'Another' });
    });

    expect(mockSend.mock.calls[0][0].data).toEqual({
      track_id: 7,
      preset: 'adaptive',
      intensity: 1.0,
    });
  });

  it('shows an error toast and does not send on a network rejection', async () => {
    mockFetch.mockRejectedValue(new Error('network down'));

    const { result } = renderHook(() => usePlayTrack());
    await act(async () => {
      await result.current.playTrack(track);
    });

    expect(mockSend).not.toHaveBeenCalled();
    expect(mockError).toHaveBeenCalledWith('network down');
  });

  it('stays silent on AbortError (no error toast, no send)', async () => {
    const abortErr = new Error('aborted');
    abortErr.name = 'AbortError';
    mockFetch.mockRejectedValue(abortErr);

    const { result } = renderHook(() => usePlayTrack());
    await act(async () => {
      await result.current.playTrack(track);
    });

    expect(mockSend).not.toHaveBeenCalled();
    expect(mockError).not.toHaveBeenCalled();
    expect(mockSuccess).not.toHaveBeenCalled();
  });

  it('does not send or toast if unmounted while the POST is in flight (#4161)', async () => {
    let resolveFetch!: (value: { ok: boolean; status: number }) => void;
    mockFetch.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      })
    );

    const { result, unmount } = renderHook(() => usePlayTrack());
    let pending!: Promise<void>;
    act(() => {
      pending = result.current.playTrack(track);
    });

    // Navigate away mid-POST, then let the POST resolve.
    unmount();
    await act(async () => {
      resolveFetch({ ok: true, status: 200 });
      await pending;
    });

    expect(mockSend).not.toHaveBeenCalled();
    expect(mockSuccess).not.toHaveBeenCalled();
  });
});

describe('usePlayTrack — rapid switches abort the previous request (#4426)', () => {
  // playTrack assigned a new AbortController to abortRef on every call but
  // never aborted the previous one, so two rapid clicks both ran to completion
  // and whichever queue POST *resolved* last sent its play_enhanced last —
  // reverting playback to the older track, with the losing track's title in the
  // success toast and no error surfaced.

  const trackA = { id: 1, title: 'Track A' };
  const trackB = { id: 2, title: 'Track B' };

  /** A fetch whose resolution is controlled by the test, capturing each signal. */
  const deferredFetch = () => {
    const signals: AbortSignal[] = [];
    const resolvers: ((v: unknown) => void)[] = [];
    mockFetch.mockImplementation((_url: string, init: RequestInit) => {
      signals.push(init.signal as AbortSignal);
      return new Promise((resolve, reject) => {
        resolvers.push(resolve);
        init.signal?.addEventListener('abort', () => {
          reject(Object.assign(new Error('aborted'), { name: 'AbortError' }));
        });
      });
    });
    return { signals, resolvers };
  };

  it("aborts the first call's controller when a second call starts", async () => {
    const { signals } = deferredFetch();
    const { result } = renderHook(() => usePlayTrack());

    act(() => {
      void result.current.playTrack(trackA);
    });
    expect(signals).toHaveLength(1);
    expect(signals[0].aborted).toBe(false);

    act(() => {
      void result.current.playTrack(trackB);
    });

    expect(signals).toHaveLength(2);
    expect(signals[0].aborted).toBe(true);
    expect(signals[1].aborted).toBe(false);
  });

  it('sends play_enhanced only for the second track when both POSTs resolve', async () => {
    const { signals, resolvers } = deferredFetch();
    const { result } = renderHook(() => usePlayTrack());

    await act(async () => {
      void result.current.playTrack(trackA);
    });
    await act(async () => {
      void result.current.playTrack(trackB);
    });

    // Resolve B first, then A — the losing call resolving LAST is exactly the
    // ordering that used to revert playback to the older track.
    await act(async () => {
      resolvers[1]({ ok: true, status: 200, statusText: 'OK' });
      resolvers[0]({ ok: true, status: 200, statusText: 'OK' });
      await Promise.resolve();
    });

    const sentTrackIds = mockSend.mock.calls
      .filter(([msg]) => msg.type === 'play_enhanced')
      .map(([msg]) => msg.data.track_id);

    expect(sentTrackIds).toEqual([trackB.id]);
    expect(signals[0].aborted).toBe(true);
  });

  it('does not toast the superseded track', async () => {
    const { resolvers } = deferredFetch();
    const { result } = renderHook(() => usePlayTrack());

    await act(async () => {
      void result.current.playTrack(trackA);
    });
    await act(async () => {
      void result.current.playTrack(trackB);
    });

    await act(async () => {
      resolvers[1]({ ok: true, status: 200, statusText: 'OK' });
      resolvers[0]({ ok: true, status: 200, statusText: 'OK' });
      await Promise.resolve();
    });

    expect(mockSuccess).toHaveBeenCalledTimes(1);
    expect(mockSuccess).toHaveBeenCalledWith(`Now playing: ${trackB.title}`);
    // An abort is not a user-facing failure.
    expect(mockError).not.toHaveBeenCalled();
  });

  it('leaves a single call unaffected', async () => {
    mockFetch.mockResolvedValue({ ok: true, status: 200, statusText: 'OK' });
    const { result } = renderHook(() => usePlayTrack());

    await act(async () => {
      await result.current.playTrack(trackA);
    });

    expect(mockSend).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'play_enhanced' })
    );
    expect(mockSuccess).toHaveBeenCalledWith(`Now playing: ${trackA.title}`);
  });
});
