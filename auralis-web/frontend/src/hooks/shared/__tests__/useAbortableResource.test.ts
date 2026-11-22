/**
 * useAbortableResource (#6630): the load/abort scaffold the playlist, album and artist detail
 * hooks used to paste.
 */

import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useAbortableResource } from '../useAbortableResource';

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
};

describe('useAbortableResource', () => {
  it('starts loading, then exposes the data and calls onLoaded with it', async () => {
    const onLoaded = vi.fn();
    const { result } = renderHook(() =>
      useAbortableResource(1, async () => ({ id: 1 }), { label: 'thing', onLoaded }),
    );
    expect(result.current.loading).toBe(true);

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual({ id: 1 });
    expect(result.current.error).toBeNull();
    expect(onLoaded).toHaveBeenCalledWith({ id: 1 });
  });

  it('aborts the previous key, and its late answer never lands', async () => {
    const first = deferred<string>();
    const signals: AbortSignal[] = [];
    const { result, rerender } = renderHook(
      ({ id }) =>
        useAbortableResource(id, (signal) => {
          signals.push(signal);
          return id === 1 ? first.promise : Promise.resolve('second');
        }, { label: 'thing' }),
      { initialProps: { id: 1 } },
    );

    rerender({ id: 2 });
    await waitFor(() => expect(result.current.data).toBe('second'));
    expect(signals[0].aborted).toBe(true);

    first.resolve('first');
    await Promise.resolve();
    expect(result.current.data).toBe('second');
  });

  it('reports a failure as an ApiError and stops loading', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { result } = renderHook(() =>
      useAbortableResource(1, async () => { throw new Error('boom'); }, { label: 'thing' }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBeNull();
    expect(result.current.error?.message).toBe('boom');
    consoleError.mockRestore();
  });

  it('does not refetch when only the inline fetcher identity changes', async () => {
    const fetcher = vi.fn(async () => 'x');
    const { rerender } = renderHook(() =>
      useAbortableResource(1, () => fetcher(), { label: 'thing' }),
    );
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));

    rerender();
    rerender();

    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
