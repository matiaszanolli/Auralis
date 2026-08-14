/**
 * usePlayTrack Tests (#4151)
 *
 * usePlayTrack is the single "play this track now" entry point (replaces
 * onTrackPlay prop drilling, #3940). It combines a REST queue POST with a
 * shared PlaybackSession start, gated by an ok-guard so a failed queue POST
 * never starts a ghost stream (#3953). It also aborts the in-flight POST on
 * unmount so a stray stream doesn't fire after navigating away (#4161).
 *
 * These tests pin that contract:
 *   - success: POST then shared-session start, with no premature success toast
 *   - failed queue POST: NO start, error toast (ghost-stream guard)
 *   - network rejection: error toast, no start
 *   - AbortError: silent (no toast, no start)
 *   - unmount mid-POST: no start
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePlayTrack } from '../usePlayTrack';
import { usePlaybackControls } from '@/contexts/PlaybackSessionContext';
import { useToast } from '@/components/shared/Toast';

// Mock collaborators. getApiUrl is mocked to identity so the fetch URL is
// asserted as the bare path regardless of the configured API base.
vi.mock('@/contexts/PlaybackSessionContext', () => ({ usePlaybackControls: vi.fn() }));
vi.mock('@/components/shared/Toast', () => ({ useToast: vi.fn() }));
vi.mock('@/config/api', () => ({ getApiUrl: (path: string) => path }));

const mockStartTrack = vi.fn().mockResolvedValue(undefined);
const mockError = vi.fn();
let mockFetch: ReturnType<typeof vi.fn>;

const track = { id: 42, title: 'Test Song' };

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(usePlaybackControls).mockReturnValue({ startTrack: mockStartTrack } as any);
  vi.mocked(useToast).mockReturnValue({ error: mockError } as any);
  mockFetch = vi.fn();
  vi.stubGlobal('fetch', mockFetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('usePlayTrack', () => {
  it('on success: POSTs the queue, then starts through the shared session', async () => {
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
    expect(mockStartTrack).toHaveBeenCalledWith(42);
    expect(mockError).not.toHaveBeenCalled();
  });

  it('does NOT start and shows an error toast when the queue POST fails (ghost-stream guard)', async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500, statusText: 'Internal Server Error' });

    const { result } = renderHook(() => usePlayTrack());
    await act(async () => {
      await result.current.playTrack(track);
    });

    expect(mockStartTrack).not.toHaveBeenCalled();
    expect(mockError).toHaveBeenCalledTimes(1);
    expect(mockError).toHaveBeenCalledWith(expect.stringContaining('500'));
  });

  // #5121: the failure branch used to throw a hardcoded
  // `Failed to set queue: {status} {statusText}`, discarding the backend's
  // HTTPException detail. Routed through httpErrorFromResponse (the same fix
  // #4831 applied to useRestAPI.ts) so the toast names the real cause.
  it("surfaces the backend's error detail rather than a bare status line (#5121)", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      json: async () => ({ detail: 'Track 42 not found' }),
    });

    const { result } = renderHook(() => usePlayTrack());
    await act(async () => {
      await result.current.playTrack(track);
    });

    expect(mockStartTrack).not.toHaveBeenCalled();
    expect(mockError).toHaveBeenCalledWith('Track 42 not found');
  });

  it('falls back to the status line when the body carries no detail (#5121)', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 503,
      statusText: 'Service Unavailable',
      json: async () => {
        throw new Error('not json');
      },
    });

    const { result } = renderHook(() => usePlayTrack());
    await act(async () => {
      await result.current.playTrack(track);
    });

    expect(mockError).toHaveBeenCalledWith(expect.stringContaining('503'));
  });

  it('delegates the selected track id to PlaybackSession', async () => {
    mockFetch.mockResolvedValue({ ok: true, status: 200 });

    const { result } = renderHook(() => usePlayTrack());
    await act(async () => {
      await result.current.playTrack({ id: 7 });
    });

    expect(mockStartTrack).toHaveBeenCalledWith(7);
  });

  it('shows an error toast and does not send on a network rejection', async () => {
    mockFetch.mockRejectedValue(new Error('network down'));

    const { result } = renderHook(() => usePlayTrack());
    await act(async () => {
      await result.current.playTrack(track);
    });

    expect(mockStartTrack).not.toHaveBeenCalled();
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

    expect(mockStartTrack).not.toHaveBeenCalled();
    expect(mockError).not.toHaveBeenCalled();
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

    expect(mockStartTrack).not.toHaveBeenCalled();
  });
});

describe('usePlayTrack — rapid switches abort the previous request (#4426)', () => {
  // playTrack assigned a new AbortController to abortRef on every call but
  // never aborted the previous one, so two rapid clicks both ran to completion
  // and whichever queue POST *resolved* last started its track last — reverting
  // playback to the older selection with no error surfaced.

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

  it('starts only the second track when both POSTs resolve', async () => {
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

    expect(mockStartTrack.mock.calls.map(([trackId]) => trackId)).toEqual([trackB.id]);
    expect(signals[0].aborted).toBe(true);
  });

  it('does not surface an abort as a user-facing failure', async () => {
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

    expect(mockStartTrack).toHaveBeenCalledTimes(1);
    expect(mockError).not.toHaveBeenCalled();
  });

  it('leaves a single call unaffected', async () => {
    mockFetch.mockResolvedValue({ ok: true, status: 200, statusText: 'OK' });
    const { result } = renderHook(() => usePlayTrack());

    await act(async () => {
      await result.current.playTrack(trackA);
    });

    expect(mockStartTrack).toHaveBeenCalledWith(trackA.id);
  });
});
