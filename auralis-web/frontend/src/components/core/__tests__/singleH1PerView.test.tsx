/**
 * Exactly one <h1> per library view (#5013)
 *
 * #4958 made AppTopBar's title an <h1>, believing none existed anywhere in
 * the app — a premise that was already stale: ViewContainer.tsx (mounted on
 * every library view) had rendered its own per-view <h1> since before that
 * fix. The two mounted simultaneously, giving screen-reader heading
 * navigation two unrelated level-1 headings on every view.
 *
 * AppTopBar and ViewContainer are siblings under ComfortableApp, not nested,
 * so rendering them together (rather than mocking one out) is what actually
 * proves the fix — a per-component test could pass on each side while still
 * regressing the combination.
 *
 * #5391: the Album and Artist detail views are rendered by LibraryViewRouter
 * WITHOUT ViewContainer, so they had no <h1> at all — DetailViewHeader's
 * title was an <h2>. Its title is now the view's <h1>, pinned below with the
 * same AppTopBar pairing.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { render as renderWithProviders } from '@/test/test-utils';

import { AppTopBar } from '../AppTopBar';
import { ViewContainer } from '@/components/library/Views/ViewContainer';
import { AlbumHeaderActions } from '@/components/library/Details/AlbumHeaderActions';
import { ArtistHeader } from '@/components/library/Details/ArtistHeader';
import type { Artist } from '@/types/domain';

// The design-system buttons use a CSS-variable border shorthand that this
// jsdom/cssstyle pairing cannot parse (see ArtistHeader.test.tsx); headings
// are what this file is about, so stub the two primitives.
vi.mock('@/design-system', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/design-system')>();
  const Stub = ({ children }: { children?: React.ReactNode }) => <button>{children}</button>;
  return { ...actual, Button: Stub, IconButton: Stub };
});

const topBar = (
  <AppTopBar
    onSearch={vi.fn()}
    onOpenMobileDrawer={vi.fn()}
    title="Your Music"
    connectionStatus="connected"
    isMobile={false}
  />
);

describe('single h1 per library view (#5013)', () => {
  it('AppTopBar + ViewContainer together expose exactly one level-one heading', () => {
    render(
      <>
        <AppTopBar
          onSearch={vi.fn()}
          onOpenMobileDrawer={vi.fn()}
          title="Your Music"
          connectionStatus="connected"
          isMobile={false}
        />
        <ViewContainer icon="🎵" title="Songs" subtitle="All tracks">
          <div>content</div>
        </ViewContainer>
      </>
    );

    const headings = screen.getAllByRole('heading', { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent('Songs');
  });
});

describe('detail views expose exactly one h1 (#5391)', () => {
  it('Album detail: the album title is the only level-one heading', () => {
    renderWithProviders(
      <>
        {topBar}
        <AlbumHeaderActions
          album={{ id: 7, title: 'Dummy', artist: 'Portishead', track_count: 11, total_duration: 2940 }}
          isFavorite={false}
          savingFavorite={false}
          onPlay={vi.fn()}
          onToggleFavorite={vi.fn()}
        />
      </>
    );

    const headings = screen.getAllByRole('heading', { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent('Dummy');
    expect(screen.getByRole('heading', { level: 2, name: 'Portishead' })).toBeInTheDocument();
  });

  it('Artist detail: the artist name is the only level-one heading', () => {
    renderWithProviders(
      <>
        {topBar}
        <ArtistHeader
          artist={{ id: 1, name: 'Portishead', albumCount: 3, trackCount: 34 } as Artist}
          onPlayAll={vi.fn()}
          onShuffle={vi.fn()}
        />
      </>
    );

    const headings = screen.getAllByRole('heading', { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent('Portishead');
  });
});
