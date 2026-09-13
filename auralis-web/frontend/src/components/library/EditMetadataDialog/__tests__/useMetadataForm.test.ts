/**
 * useMetadataForm.saveMetadata cancellation (#4175)
 *
 * #3601 added an AbortController to the GET path. saveMetadata's PUT had none,
 * so submitting then closing the dialog ran setSuccess/setSaving on a dead hook
 * (and a reopened dialog could race a stale save). These tests pin that the PUT
 * receives a signal that aborts on unmount and that no success state is set when
 * the save is aborted mid-flight.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useMetadataForm } from '../useMetadataForm';
import { DEFAULT_TIMEOUT_MS } from '@/utils/apiRequest';

/** A request that never settles until the transport's timeout aborts it. */
const hangingImpl = (_url: string, init: RequestInit) =>
  new Promise((_resolve, reject) => {
    init.signal?.addEventListener('abort', () => {
      reject(Object.assign(new Error('aborted'), { name: 'AbortError' }));
    });
  });

const initial = { title: 'Song' };
let mockFetch: ReturnType<typeof vi.fn>;

beforeEach(() => {
  mockFetch = vi.fn();
  vi.stubGlobal('fetch', mockFetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('useMetadataForm.saveMetadata (#4175)', () => {
  it('passes an AbortSignal to the PUT and aborts it on unmount', async () => {
    let capturedSignal: AbortSignal | undefined;
    mockFetch.mockImplementation((_url: string, opts: RequestInit) => {
      capturedSignal = opts.signal as AbortSignal;
      return new Promise(() => {}); // never resolves — stays in flight
    });

    const { result, unmount } = renderHook(() => useMetadataForm(1, initial));
    act(() => {
      void result.current.saveMetadata();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/metadata/tracks/1',
      expect.objectContaining({ method: 'PUT', signal: expect.any(AbortSignal) })
    );
    expect(capturedSignal!.aborted).toBe(false);

    unmount();
    expect(capturedSignal!.aborted).toBe(true);
  });

  it('sets success on a resolved save', async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({}) });

    const { result } = renderHook(() => useMetadataForm(1, initial));
    let ret: boolean | undefined;
    await act(async () => {
      ret = await result.current.saveMetadata();
    });

    expect(ret).toBe(true);
    expect(result.current.success).toBe(true);
    expect(result.current.saving).toBe(false);
  });

  it('surfaces an error and clears saving when the PUT times out (#5019)', async () => {
    // The raw fetch() had the unmount signal but no timeout, so a hung backend
    // left the dialog's spinner on with no error, forever.
    vi.useFakeTimers();
    try {
      mockFetch.mockImplementation(hangingImpl);

      const { result } = renderHook(() => useMetadataForm(1, initial));
      let savePromise!: Promise<boolean | undefined>;
      act(() => {
        savePromise = result.current.saveMetadata() as Promise<boolean | undefined>;
      });
      expect(result.current.saving).toBe(true);

      let ret: boolean | undefined;
      await act(async () => {
        await vi.advanceTimersByTimeAsync(DEFAULT_TIMEOUT_MS);
        ret = await savePromise;
      });

      expect(ret).toBe(false);
      expect(result.current.saving).toBe(false);
      expect(result.current.success).toBe(false);
      expect(result.current.error).toContain('timed out');
    } finally {
      vi.useRealTimers();
    }
  });

  it('sets an error message when the save fails with a backend detail', async () => {
    // post/put throw on non-2xx instead of returning a response to branch on;
    // the backend's `detail` must still reach the dialog (#5019).
    mockFetch.mockResolvedValue({
      ok: false,
      status: 422,
      statusText: '',
      json: async () => ({ detail: 'year must be a number' }),
    });

    const { result } = renderHook(() => useMetadataForm(1, initial));
    let ret: boolean | undefined;
    await act(async () => {
      ret = await result.current.saveMetadata();
    });

    expect(ret).toBe(false);
    expect(result.current.error).toBe('year must be a number');
    expect(result.current.saving).toBe(false);
  });

  it('does not set success when the save is aborted before it resolves', async () => {
    let resolveFetch!: () => void;
    mockFetch.mockImplementation(
      () =>
        new Promise((res) => {
          resolveFetch = () => res({ ok: true, json: async () => ({}) });
        })
    );

    const { result, unmount } = renderHook(() => useMetadataForm(1, initial));
    let savePromise!: Promise<boolean | undefined>;
    act(() => {
      savePromise = result.current.saveMetadata() as Promise<boolean | undefined>;
    });

    unmount(); // aborts the in-flight PUT

    await act(async () => {
      resolveFetch();
      await savePromise;
    });

    // setSuccess was guarded by signal.aborted, so it never ran.
    expect(result.current.success).toBe(false);
  });
});
