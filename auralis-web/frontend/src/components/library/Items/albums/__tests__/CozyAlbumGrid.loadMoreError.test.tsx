/**
 * A failed later page keeps the loaded albums (#5870)
 *
 * TanStack keeps `data` when fetchNextPage fails, but CozyAlbumGrid returned
 * the "Error Loading Albums" EmptyState on any `error`, so one transient 503
 * while scrolling discarded every loaded album and the scroll position, with
 * no retry.
 */

import { vi, describe, it, expect, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import { render, screen } from '@/test/test-utils';

const query = vi.hoisted(() => ({ current: {} as Record<string, unknown> }));

vi.mock('@/hooks/library/useInfiniteAlbums', () => ({
  useInfiniteAlbums: () => query.current,
}));
vi.mock('@/hooks/fingerprint/useAlbumFingerprint', () => ({
  useAlbumFingerprints: () => ({ fingerprints: new Map(), isLoading: false, error: null }),
}));

import { CozyAlbumGrid } from '../CozyAlbumGrid';

const page = {
  albums: [
    { id: 1, title: 'Selected Ambient Works', artist: 'Aphex Twin', trackCount: 13 },
    { id: 2, title: 'Geogaddi', artist: 'Boards of Canada', trackCount: 23 },
  ],
};

const state = (overrides: Record<string, unknown>) => ({
  data: { pages: [page] },
  isLoading: false,
  error: null,
  hasNextPage: true,
  isFetchNextPageError: false,
  isFetchingNextPage: false,
  fetchNextPage: vi.fn(),
  refetch: vi.fn(),
  ...overrides,
});

describe('CozyAlbumGrid load-more failure (#5870)', () => {
  beforeEach(() => {
    query.current = state({});
  });

  it('keeps the loaded albums and offers an inline Retry that refetches the next page', async () => {
    const user = userEvent.setup();
    query.current = state({ error: new Error('Library database is locked'), isFetchNextPageError: true });
    render(<CozyAlbumGrid />);

    expect(screen.getByText('Selected Ambient Works')).toBeInTheDocument();
    expect(screen.getByText('Geogaddi')).toBeInTheDocument();
    expect(screen.queryByText('Error Loading Albums')).not.toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent("Couldn't load more albums.");

    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(query.current.fetchNextPage).toHaveBeenCalledTimes(1);
  });

  it('a failed initial load is an announced error whose Retry refetches', async () => {
    const user = userEvent.setup();
    query.current = state({ data: undefined, hasNextPage: false, error: new Error('boom') });
    render(<CozyAlbumGrid />);

    expect(screen.getByRole('alert')).toHaveTextContent('Error Loading Albums');
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(query.current.refetch).toHaveBeenCalledTimes(1);
  });
});
