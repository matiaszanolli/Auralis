/**
 * replaceAbortController / fetchLoadedPages (#6275): the request bookkeeping that
 * useLibraryPagination's fetch, refresh and load-more paths used to each spell out.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockGet = vi.fn();
vi.mock('@/utils/apiRequest', () => ({
  get: (...args: unknown[]) => mockGet(...args),
  APIRequestError: class APIRequestError extends Error {},
}));

import { PAGE_LIMIT, fetchLoadedPages, replaceAbortController } from '../libraryPageFetch';

const track = (id: number) => ({ id, title: `T${id}`, artist: 'A', album: 'B', duration: 10 });
const page = (ids: number[], hasMore: boolean, total: number) => ({
  tracks: ids.map(track),
  has_more: hasMore,
  total,
});

describe('replaceAbortController', () => {
  it('aborts the held controller and installs a live one', () => {
    const first = new AbortController();
    const ref: { current: AbortController | null } = { current: first };

    const next = replaceAbortController(ref);

    expect(first.signal.aborted).toBe(true);
    expect(next).not.toBe(first);
    expect(next.signal.aborted).toBe(false);
    expect(ref.current).toBe(next);
  });

  it('works from an empty ref', () => {
    const ref: { current: AbortController | null } = { current: null };
    expect(replaceAbortController(ref).signal.aborted).toBe(false);
    expect(ref.current).toBeInstanceOf(AbortController);
  });
});

describe('fetchLoadedPages', () => {
  beforeEach(() => mockGet.mockReset());

  it('re-fetches exactly as many pages as are loaded and reports where loadMore continues', async () => {
    mockGet
      .mockResolvedValueOnce(page([1, 2], true, 6))
      .mockResolvedValueOnce(page([3, 4], true, 6))
      .mockResolvedValueOnce(page([5, 6], false, 6));

    // 3 loaded -> two pages cover it; the third is never requested.
    const result = await fetchLoadedPages('songs', '', 3, () => new AbortController().signal, () => false);

    expect(mockGet).toHaveBeenCalledTimes(2);
    expect(result?.tracks.map((t) => t.id)).toEqual([1, 2, 3, 4]);
    expect(result).toMatchObject({ offset: 2 * PAGE_LIMIT, hasMore: true, total: 6 });
  });

  it('stops early when the server has no more pages', async () => {
    mockGet.mockResolvedValueOnce(page([1], false, 1));

    const result = await fetchLoadedPages('songs', '', 50, () => new AbortController().signal, () => false);

    expect(mockGet).toHaveBeenCalledTimes(1);
    expect(result).toMatchObject({ hasMore: false, total: 1 });
  });

  it('takes a fresh signal for every page', async () => {
    mockGet.mockResolvedValueOnce(page([1], true, 2)).mockResolvedValueOnce(page([2], false, 2));
    const nextSignal = vi.fn(() => new AbortController().signal);

    await fetchLoadedPages('songs', '', 2, nextSignal, () => false);

    expect(nextSignal).toHaveBeenCalledTimes(2);
  });

  it('returns null, applying nothing, once the request is superseded mid-way', async () => {
    mockGet.mockResolvedValue(page([1, 2], true, 9));
    let calls = 0;

    const result = await fetchLoadedPages('songs', '', 6, () => new AbortController().signal, () => ++calls > 1);

    expect(result).toBeNull();
    expect(mockGet).toHaveBeenCalledTimes(2);
  });
});
