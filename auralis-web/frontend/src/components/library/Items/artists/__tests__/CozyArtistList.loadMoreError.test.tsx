/**
 * A failed later page keeps the loaded artists (#5870); a library change
 * refreshes them in place (#5871)
 *
 * fetchMore stored a page failure in the same `error` the initial load used,
 * and CozyArtistList rendered the error EmptyState whenever `error` was set,
 * so one transient 503 while scrolling (a SQLite lock during a scan) replaced
 * hundreds of loaded rows with "Error Loading Artists" and no way to retry.
 */

import { vi, describe, it, expect, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import { render, screen } from '@/test/test-utils';
import type { Artist } from '@/types/domain';
import type { ApiError } from '@/types/api';

const query = vi.hoisted(() => ({
  current: {} as Record<string, unknown>,
}));

let deliver: ((message: unknown) => void) | undefined;
vi.mock('@/hooks/websocket/useWebSocketMessages', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/hooks/websocket/useWebSocketMessages')>()),
  useWebSocketMessages: (_types: string[], callback: (msg: unknown) => void) => {
    deliver = callback;
  },
}));

vi.mock('@/hooks/library', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/hooks/library')>();
  return { ...actual, useArtistsQuery: () => query.current };
});

import { CozyArtistList } from '../CozyArtistList';

const artists: Artist[] = [
  { id: 1, name: 'Aphex Twin', albumCount: 1, trackCount: 3 } as Artist,
  { id: 2, name: 'Boards of Canada', albumCount: 1, trackCount: 9 } as Artist,
];
const locked = { message: 'Library database is locked', code: 'FETCH_MORE_ERROR' } as ApiError;

const state = (overrides: Record<string, unknown>) => ({
  data: artists,
  isLoading: false,
  isLoadingMore: false,
  error: null,
  loadMoreError: null,
  total: 300,
  hasMore: true,
  fetchMore: vi.fn().mockResolvedValue(undefined),
  refetch: vi.fn().mockResolvedValue(undefined),
  refresh: vi.fn().mockResolvedValue(undefined),
  ...overrides,
});

describe('CozyArtistList load-more failure (#5870)', () => {
  beforeEach(() => {
    query.current = state({});
  });

  it('keeps the loaded rows and offers an inline Retry that fetches the failed page', async () => {
    const user = userEvent.setup();
    query.current = state({ loadMoreError: locked });
    render(<CozyArtistList />);

    expect(screen.getByText('Aphex Twin')).toBeInTheDocument();
    expect(screen.getByText('Boards of Canada')).toBeInTheDocument();
    expect(screen.queryByText('Error Loading Artists')).not.toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent("Couldn't load more artists.");

    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(query.current.fetchMore).toHaveBeenCalledTimes(1);
  });

  it('shows the hook\'s isLoadingMore as the loading-more indicator', () => {
    query.current = state({ isLoadingMore: true });
    render(<CozyArtistList />);

    expect(screen.getByText(/Loading more artists/i)).toBeInTheDocument();
  });

  it('a failed initial load is an announced error with a Retry', async () => {
    const user = userEvent.setup();
    query.current = state({ data: [], total: 0, hasMore: false, error: locked });
    render(<CozyArtistList />);

    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Error Loading Artists');
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(query.current.refetch).toHaveBeenCalledTimes(1);
  });
});

describe('CozyArtistList library changes (#5871)', () => {
  it('refreshes the loaded artists in place when the library changes while mounted', () => {
    query.current = state({});
    render(<CozyArtistList />);

    deliver?.({ type: 'library_updated', data: { action: 'scan' } });

    expect(query.current.refresh).toHaveBeenCalledTimes(1);
    expect(query.current.refetch).not.toHaveBeenCalled();
  });
});
