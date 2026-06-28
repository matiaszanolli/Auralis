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
