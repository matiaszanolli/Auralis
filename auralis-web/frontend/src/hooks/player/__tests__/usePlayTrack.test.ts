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

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePlayTrack } from '../usePlayTrack';
import { usePlaybackControls } from '@/contexts/PlaybackSessionContext';
import { useToast } from '@/components/shared/Toast';
import { post } from '@/utils/apiRequest';

// Mock collaborators. The queue POST goes through the shared transport
// (#5649), so it is mocked at that boundary; status/detail parsing and the
// 30 s timeout are the transport's own contract (apiRequest tests).
vi.mock('@/contexts/PlaybackSessionContext', () => ({ usePlaybackControls: vi.fn() }));
vi.mock('@/components/shared/Toast', () => ({ useToast: vi.fn() }));
vi.mock('@/utils/apiRequest', () => ({ post: vi.fn() }));

const mockStartTrack = vi.fn().mockResolvedValue(undefined);
const mockError = vi.fn();
const mockPost = vi.mocked(post);

const track = { id: 42, title: 'Test Song' };

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(usePlaybackControls).mockReturnValue({ startTrack: mockStartTrack } as any);
  vi.mocked(useToast).mockReturnValue({ error: mockError } as any);
  mockPost.mockResolvedValue(undefined);
});

describe('usePlayTrack', () => {
  it('on success: POSTs the queue, then starts through the shared session', async () => {
    const { result } = renderHook(() => usePlayTrack());
    await act(async () => {
      await result.current.playTrack(track);
    });

    expect(mockPost).toHaveBeenCalledWith(
      '/api/player/queue',
      { tracks: [42], start_index: 0 },
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
    expect(mockStartTrack).toHaveBeenCalledWith(42);
    expect(mockError).not.toHaveBeenCalled();
  });

  it('does NOT start and shows an error toast when the queue POST fails (ghost-stream guard)', async () => {
    mockPost.mockRejectedValue(new Error('HTTP 500: Internal Server Error'));

    const { result } = renderHook(() => usePlayTrack());
    await act(async () => {
      await result.current.playTrack(track);
    });

    expect(mockStartTrack).not.toHaveBeenCalled();
    expect(mockError).toHaveBeenCalledTimes(1);
    expect(mockError).toHaveBeenCalledWith(expect.stringContaining('500'));
  });

  // #5121: the toast names the backend's HTTPException `detail`; the shared
  // transport extracts it into the thrown error's message.
  it("surfaces the transport error's message (the backend detail) in the toast (#5121)", async () => {
    mockPost.mockRejectedValue(new Error('Track 42 not found'));

    const { result } = renderHook(() => usePlayTrack());
    await act(async () => {
      await result.current.playTrack(track);
    });

    expect(mockStartTrack).not.toHaveBeenCalled();
    expect(mockError).toHaveBeenCalledWith('Track 42 not found');
  });

  it('delegates the selected track id to PlaybackSession', async () => {
    const { result } = renderHook(() => usePlayTrack());
    await act(async () => {
      await result.current.playTrack({ id: 7 });
    });

    expect(mockStartTrack).toHaveBeenCalledWith(7);
  });

  it('shows an error toast and does not send on a network rejection', async () => {
    mockPost.mockRejectedValue(new Error('network down'));

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
    mockPost.mockRejectedValue(abortErr);

    const { result } = renderHook(() => usePlayTrack());
    await act(async () => {
      await result.current.playTrack(track);
    });

    expect(mockStartTrack).not.toHaveBeenCalled();
    expect(mockError).not.toHaveBeenCalled();
  });

  it('does not send or toast if unmounted while the POST is in flight (#4161)', async () => {
    let resolvePost!: (value: undefined) => void;
    mockPost.mockReturnValue(
      new Promise((resolve) => {
        resolvePost = resolve;
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
      resolvePost(undefined);
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

  /** A POST whose resolution is controlled by the test, capturing each signal. */
  const deferredPost = () => {
    const signals: AbortSignal[] = [];
    const resolvers: ((v: undefined) => void)[] = [];
    mockPost.mockImplementation((async (_url: string, _body: unknown, options?: { signal?: AbortSignal }) => {
      signals.push(options?.signal as AbortSignal);
      return new Promise((resolve, reject) => {
        resolvers.push(resolve as (v: undefined) => void);
        options?.signal?.addEventListener('abort', () => {
          reject(Object.assign(new Error('aborted'), { name: 'AbortError' }));
        });
      });
    }) as any);
    return { signals, resolvers };
  };

  it("aborts the first call's controller when a second call starts", async () => {
    const { signals } = deferredPost();
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
    const { signals, resolvers } = deferredPost();
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
      resolvers[1](undefined);
      resolvers[0](undefined);
      await Promise.resolve();
    });

    expect(mockStartTrack.mock.calls.map(([trackId]) => trackId)).toEqual([trackB.id]);
    expect(signals[0].aborted).toBe(true);
  });

  it('does not surface an abort as a user-facing failure', async () => {
    const { resolvers } = deferredPost();
    const { result } = renderHook(() => usePlayTrack());

    await act(async () => {
      void result.current.playTrack(trackA);
    });
    await act(async () => {
      void result.current.playTrack(trackB);
    });

    await act(async () => {
      resolvers[1](undefined);
      resolvers[0](undefined);
      await Promise.resolve();
    });

    expect(mockStartTrack).toHaveBeenCalledTimes(1);
    expect(mockError).not.toHaveBeenCalled();
  });

  it('leaves a single call unaffected', async () => {
    const { result } = renderHook(() => usePlayTrack());

    await act(async () => {
      await result.current.playTrack(trackA);
    });

    expect(mockStartTrack).toHaveBeenCalledWith(trackA.id);
  });
});
