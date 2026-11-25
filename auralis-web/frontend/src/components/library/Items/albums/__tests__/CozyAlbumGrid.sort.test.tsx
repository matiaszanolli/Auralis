import { act, render, screen, waitFor, within } from '@/test/test-utils';
import { CozyAlbumGrid } from '@/components/library/Items/albums/CozyAlbumGrid';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/hooks/fingerprint/useAlbumFingerprint', () => ({
  useAlbumFingerprints: () => ({ fingerprints: new Map() }),
}));

const album = (id: number, title: string, year: number) => ({
  id, title, year, artist: 'Artist', track_count: 1, total_duration: 60,
});
const firstPage = [album(1, 'First pressing', 2004), album(2, 'Archive', 1996)];
const nextPage = [album(3, 'Second pressing', 1995), album(4, 'Demo tape', 1981)];

describe('CozyAlbumGrid sorting', () => {
  let requests: URLSearchParams[];
  let loadNextPage: (() => void) | undefined;

  beforeEach(() => {
    requests = [];
    loadNextPage = undefined;
    const fetch = globalThis.fetch;
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = new URL(String(input), 'http://localhost');
      if (url.pathname !== '/api/albums') return fetch(input, init);
      requests.push(url.searchParams);
      const offset = Number(url.searchParams.get('offset'));
      return Response.json({
        albums: offset === 0 ? firstPage : nextPage,
        has_more: offset === 0,
        limit: 50,
        offset,
        total: 4,
      });
    });

    vi.stubGlobal('IntersectionObserver', class {
      constructor(callback: IntersectionObserverCallback, options?: IntersectionObserverInit) {
        if (options?.rootMargin === '400px') {
          loadNextPage = () => callback(
            [{ isIntersecting: true }] as IntersectionObserverEntry[],
            this as unknown as IntersectionObserver,
          );
        }
      }

      observe() {}
      unobserve() {}
      disconnect() {}
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it.each([
    ['az', 'title', 'asc'],
    ['year', 'year', 'desc'],
  ] as const)('requests %s ordering and uses the flat grid', async (sortBy, orderBy, order) => {
    render(<CozyAlbumGrid sortBy={sortBy} />);

    const grid = within(await screen.findByRole('list', { name: 'Albums' }));
    expect(grid.getAllByRole('listitem')).toHaveLength(2);
    expect(grid.getByText('First pressing')).toBeInTheDocument();
    expect(grid.queryByRole('heading', { name: '2000 - 2004' })).not.toBeInTheDocument();
    expect(Object.fromEntries(requests[0])).toMatchObject({ order_by: orderBy, order, offset: '0' });
  });

  it('streams newest-first pages into the matching era sections', async () => {
    render(<CozyAlbumGrid sortBy="era" />);

    const currentEra = await screen.findByRole('heading', { name: '2000 - 2004' });
    const earlierEra = screen.getByRole('heading', { name: '1995 - 1999' });
    expect(within(currentEra.parentElement!).getByText('First pressing')).toBeInTheDocument();
    expect(within(earlierEra.parentElement!).getByText('Archive')).toBeInTheDocument();

    await waitFor(() => expect(loadNextPage).toEqual(expect.any(Function)));
    act(() => loadNextPage!());

    expect(await within(earlierEra.parentElement!).findByText('Second pressing')).toBeInTheDocument();
    expect(within(earlierEra.parentElement!).getByText('Archive')).toBeInTheDocument();
    const olderEra = screen.getByRole('heading', { name: '1980 - 1984' });
    expect(within(olderEra.parentElement!).getByText('Demo tape')).toBeInTheDocument();
    expect(screen.getAllByRole('heading', { name: '1995 - 1999' })).toHaveLength(1);
    expect(requests.map((query) => [query.get('order_by'), query.get('order'), query.get('offset')]))
      .toEqual([['year', 'desc', '0'], ['year', 'desc', '50']]);
  });
});
