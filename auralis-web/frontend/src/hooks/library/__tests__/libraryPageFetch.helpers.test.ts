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

  /** A server of `total` rows that honours the limit/offset in the URL. */
  const serve = (total: number) =>
    mockGet.mockImplementation(async (url: string) => {
      const params = new URL(url, 'http://x').searchParams;
      const limit = Number(params.get('limit'));
      const offset = Number(params.get('offset'));
      const ids = Array.from({ length: Math.max(0, Math.min(limit, total - offset)) }, (_, i) => offset + i + 1);
      return page(ids, offset + limit < total, total);
    });
  const fresh = () => new AbortController().signal;

  it('reads the loaded rows in requests as large as the server allows', async () => {
    serve(1000);

    // 500 loaded rows = ten pages: 200 + 200 + 100 rows, three requests.
    const result = await fetchLoadedPages('songs', '', 500, fresh, () => false);

    expect(mockGet.mock.calls.map((c) => new URL(String(c[0]), 'http://x').searchParams.get('limit'))).toEqual([
      '200', '200', '100',
    ]);
    expect(result?.tracks).toHaveLength(500);
    expect(result).toMatchObject({ offset: 9 * PAGE_LIMIT, hasMore: true, total: 1000 }); // start of the last page read
  });

  it('reports the last page start for a single loaded page', async () => {
    serve(1000);

    const result = await fetchLoadedPages('songs', '', PAGE_LIMIT, fresh, () => false);

    expect(mockGet).toHaveBeenCalledTimes(1);
    expect(result).toMatchObject({ offset: 0, hasMore: true });
  });

  it('stops when the library shrank below what was loaded', async () => {
    serve(70);

    const result = await fetchLoadedPages('songs', '', 150, fresh, () => false);

    expect(mockGet).toHaveBeenCalledTimes(1);
    expect(result?.tracks).toHaveLength(70);
    expect(result).toMatchObject({ offset: PAGE_LIMIT, hasMore: false, total: 70 });
  });

  it('takes a fresh signal for every request', async () => {
    serve(1000);
    const nextSignal = vi.fn(fresh);

    await fetchLoadedPages('songs', '', 250, nextSignal, () => false);

    expect(nextSignal).toHaveBeenCalledTimes(2); // 200 + 50 rows
  });

  it('returns null, applying nothing, once the request is superseded mid-way', async () => {
    serve(1000);
    let calls = 0;

    const result = await fetchLoadedPages('songs', '', 500, fresh, () => ++calls > 1);

    expect(result).toBeNull();
    expect(mockGet).toHaveBeenCalledTimes(2);
  });
});
