/**
 * ArtistHeader renders only real data (#5153)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The header used to carry a second metadata line reading the literal string
 * "Artist" — a self-described placeholder that bound to nothing. The album
 * header next to it renders year/track count/duration/genre through
 * `AlbumMetadata` because those fields exist on `Album`; `Artist` has no
 * equivalent, so the line was filler rather than an unfinished binding.
 *
 * This pins that it stays gone: a future contributor adding artist stats
 * should add the backend field and an `ArtistMetadata` component, not
 * re-fill a literal.
 */

import { describe, it, expect, vi } from 'vitest';

// The design-system Button/IconButton emit `border: 1px solid var(--app-…)`,
// and the jsdom/cssstyle pairing in this repo throws parsing a border
// shorthand whose value is a CSS variable ("Cannot create property
// 'border-width' on string"). That is an environment limit, not a fact about
// ArtistHeader — and this file is about what the header renders as *metadata*,
// so stub the two primitives rather than skip the component.
vi.mock('@/design-system', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/design-system')>();
  return {
    ...actual,
    Button: ({ children, ...props }: Record<string, unknown> & { children?: React.ReactNode }) => (
      <button {...(props as object)}>{children}</button>
    ),
    IconButton: ({ children, ...props }: Record<string, unknown> & { children?: React.ReactNode }) => (
      <button {...(props as object)}>{children}</button>
    ),
  };
});

import { render, screen } from '@/test/test-utils';
import { ArtistHeader } from '../ArtistHeader';
import type { Artist } from '@/types/domain';

function artist(overrides: Partial<Artist> = {}): Artist {
  return {
    id: 1,
    name: 'Portishead',
    albumCount: 3,
    trackCount: 34,
    ...overrides,
  } as Artist;
}

function renderHeader(a: Artist = artist()) {
  return render(
    <ArtistHeader artist={a} onPlayAll={vi.fn()} onShuffle={vi.fn()} />
  );
}

describe('ArtistHeader (#5153)', () => {
  it('does not render the placeholder literal', () => {
    renderHeader();
    expect(screen.queryByText('Artist')).toBeNull();
  });

  it('still renders the artist name and the primary stats line', () => {
    renderHeader();

    expect(screen.getByText('Portishead')).toBeInTheDocument();
    // Counts share one Typography, so match on the composed line.
    expect(screen.getByText(/3 Albums/)).toBeInTheDocument();
    expect(screen.getByText(/34 Tracks/)).toBeInTheDocument();
  });

  it('singularises a one-album, one-track artist', () => {
    renderHeader(artist({ albumCount: 1, trackCount: 1 }));

    const line = screen.getByText(/1 Album/);
    expect(line.textContent).toContain('1 Album');
    expect(line.textContent).toContain('1 Track');
    expect(line.textContent).not.toContain('Albums');
    expect(line.textContent).not.toContain('Tracks');
  });

  it('renders without the counts rather than falling back to filler', () => {
    // The placeholder used to be the only thing on screen in this case.
    renderHeader(artist({ albumCount: undefined, trackCount: undefined }));

    expect(screen.getByText('Portishead')).toBeInTheDocument();
    expect(screen.queryByText('Artist')).toBeNull();
  });
});
