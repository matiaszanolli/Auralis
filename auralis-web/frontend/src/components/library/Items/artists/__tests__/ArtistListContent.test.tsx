/**
 * ArtistListContent virtualization regression tests (#3957)
 *
 * The artist list now flattens its alphabet headers + artist rows into a single
 * useVirtualizer (external #app-main-content-scroll, the album-view pattern) so
 * the rendered DOM stays bounded on large libraries — previously it appended
 * every section via InfiniteScroll + per-section map() with no windowing.
 *
 * jsdom has no measurable layout, so the virtualizer falls back to rendering
 * every row; these tests assert the flatten preserves the list content (headers
 * + artists, grouped) and that the infinite-loader/end-message render correctly.
 */

import { vi, describe, it, expect } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { ArtistListContent } from '../ArtistListContent';
import type { Artist } from '@/types/domain';

const artist = (id: number, name: string): Artist =>
  ({ id, name, albumCount: 1, trackCount: 3 } as Artist);

const baseProps = {
  totalArtists: 3,
  isLoadingMore: false,
  hasMore: false,
  fetchMore: vi.fn().mockResolvedValue(undefined),
  contextMenuState: { isOpen: false },
  contextActions: [],
  onArtistClick: vi.fn(),
  onContextMenuOpen: vi.fn(),
  onContextMenuClose: vi.fn(),
};

const grouped = {
  A: [artist(1, 'Aphex Twin'), artist(2, 'Arcade Fire')],
  B: [artist(3, 'Boards of Canada')],
};
const artists = [...grouped.A, ...grouped.B];

describe('ArtistListContent (#3957 virtualization)', () => {
  it('renders alphabet headers and every artist (flattened content preserved)', () => {
    render(
      <ArtistListContent
        {...baseProps}
        artists={artists}
        groupedArtists={grouped}
        sortedLetters={['A', 'B']}
      />
    );

    // Letter headers
    expect(screen.getByText('A')).toBeInTheDocument();
    expect(screen.getByText('B')).toBeInTheDocument();
    // Artist rows
    expect(screen.getByText('Aphex Twin')).toBeInTheDocument();
    expect(screen.getByText('Arcade Fire')).toBeInTheDocument();
    expect(screen.getByText('Boards of Canada')).toBeInTheDocument();
  });

  it('shows the end-of-list message when there is no more to load', () => {
    render(
      <ArtistListContent
        {...baseProps}
        hasMore={false}
        artists={artists}
        groupedArtists={grouped}
        sortedLetters={['A', 'B']}
      />
    );
    expect(screen.getByText(/Showing all 3 artists/i)).toBeInTheDocument();
  });

  it('does not show the end message while more pages remain', () => {
    render(
      <ArtistListContent
        {...baseProps}
        hasMore={true}
        artists={artists}
        groupedArtists={grouped}
        sortedLetters={['A', 'B']}
      />
    );
    expect(screen.queryByText(/Showing all/i)).not.toBeInTheDocument();
  });

  it('renders nothing extra for an empty library', () => {
    render(
      <ArtistListContent
        {...baseProps}
        totalArtists={0}
        artists={[]}
        groupedArtists={{}}
        sortedLetters={[]}
      />
    );
    // No artists, no end message (guarded by artists.length > 0).
    expect(screen.queryByText(/Showing all/i)).not.toBeInTheDocument();
  });
});
