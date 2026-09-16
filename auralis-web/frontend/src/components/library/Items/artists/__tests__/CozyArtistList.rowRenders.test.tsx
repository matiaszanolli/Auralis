/**
 * Opening/closing the artist context menu re-renders no row (#5389)
 *
 * ArtistListItem was the only virtualized row without memo, and the
 * callbacks it received changed identity on every CozyArtistList render
 * (useContextMenu's handlers and the inline onContextMenuClose), so every
 * mounted row re-rendered whenever the menu opened or closed.
 *
 * Fixing that surfaced a worse bug in the same path: ArtistListContent passed
 * useVirtualizer a new getItemKey closure every render, and virtual-core
 * re-renders from inside render whenever getItemKey changes, so ANY re-render
 * after mount (menu open, next page) threw "Too many re-renders".
 */

import { vi, describe, it, expect, beforeEach } from 'vitest';
import type { ComponentProps } from 'react';
import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@/test/test-utils';
import type { Artist } from '@/types/domain';

const renders = vi.hoisted(() => new Map<string, number>());
const fetchMore = vi.hoisted(() => vi.fn());

vi.mock('@/components/library/Styles/ArtistList.styles', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/components/library/Styles/ArtistList.styles')>();
  const Original = actual.ArtistName;
  const CountingArtistName = (props: ComponentProps<typeof Original>) => {
    const name = String(props.children);
    renders.set(name, (renders.get(name) ?? 0) + 1);
    return <Original {...props} />;
  };
  return { ...actual, ArtistName: CountingArtistName };
});

const artists: Artist[] = [
  { id: 1, name: 'Aphex Twin', albumCount: 1, trackCount: 3 } as Artist,
  { id: 2, name: 'Arcade Fire', albumCount: 2, trackCount: 20 } as Artist,
  { id: 3, name: 'Boards of Canada', albumCount: 1, trackCount: 9 } as Artist,
];

vi.mock('@/hooks/library', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/hooks/library')>();
  return {
    ...actual,
    useArtistsQuery: () => ({
      data: artists,
      isLoading: false,
      error: null,
      total: artists.length,
      hasMore: false,
      fetchMore,
    }),
  };
});

import { CozyArtistList } from '../CozyArtistList';
import { ArtistListContent } from '../ArtistListContent';

describe('CozyArtistList row re-renders (#5389)', () => {
  beforeEach(() => renders.clear());

  it('opening and closing the context menu re-renders no artist row', async () => {
    const user = userEvent.setup();
    render(<CozyArtistList onArtistClick={vi.fn()} />);
    await screen.findByText('Boards of Canada');
    const before = new Map(renders);
    expect(before.get('Aphex Twin')).toBeGreaterThan(0);

    await user.pointer({ keys: '[MouseRight]', target: screen.getByText('Arcade Fire') });
    expect(await screen.findByRole('menu')).toBeInTheDocument();
    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('menu')).not.toBeInTheDocument());

    expect(Object.fromEntries(renders)).toEqual(Object.fromEntries(before));
  });
});

describe('ArtistListContent re-renders after mount (#5389)', () => {
  const props = {
    totalArtists: 4,
    isLoadingMore: false,
    hasMore: false,
    fetchMore: vi.fn().mockResolvedValue(undefined),
    contextActions: [],
    onArtistClick: vi.fn(),
    onContextMenuOpen: vi.fn(),
    onContextMenuClose: vi.fn(),
  };
  const grouped = (list: Artist[]) => ({
    groupedArtists: { A: list.filter((a) => a.name.startsWith('A')), B: list.filter((a) => a.name.startsWith('B')) },
    sortedLetters: ['A', 'B'],
  });

  it('survives a props change and a new page without a render loop', () => {
    const { rerender } = render(
      <ArtistListContent {...props} artists={artists} {...grouped(artists)} contextMenuState={{ isOpen: false }} />
    );
    rerender(
      <ArtistListContent {...props} artists={artists} {...grouped(artists)}
        contextMenuState={{ isOpen: true, mousePosition: { top: 1, left: 1 } }} />
    );
    const nextPage = [...artists, { id: 4, name: 'Beach House', albumCount: 1, trackCount: 8 } as Artist];
    rerender(
      <ArtistListContent {...props} artists={nextPage} {...grouped(nextPage)} contextMenuState={{ isOpen: false }} />
    );
    expect(screen.getByText('Beach House')).toBeInTheDocument();
  });
});
