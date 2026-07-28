/**
 * AlbumsTab keyboard accessibility (#4537)
 *
 * The artist page's Albums tab rendered a local `styled(Paper)` AlbumCard with
 * `onClick` and `cursor: pointer` but no `role`, `tabIndex` or `onKeyDown`, so
 * artist -> album navigation was impossible without a pointer — while the same
 * navigation from the main library grid worked, because that grid already used
 * the unified MediaCard. These tests pin the keyboard path so the tab cannot
 * silently regress to a local card again.
 */

import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@/test/test-utils';
import AlbumsTab from '@/components/library/Views/AlbumsTab';

const ALBUMS = [
  { id: 1, title: 'Oktubre', year: 1986, track_count: 8, total_duration: 2400 },
  { id: 2, title: 'Un Baion Para El Ojo Idiota', year: 1987, track_count: 9, total_duration: 2700 },
];

const ARTIST = 'Patricio Rey';

const renderTab = (onAlbumClick = vi.fn()) => {
  render(
    <AlbumsTab albums={ALBUMS} artistName={ARTIST} onAlbumClick={onAlbumClick} />,
  );
  return onAlbumClick;
};

/**
 * The card element itself, addressed by MediaCard's "<title> by <artist>"
 * accessible name.
 *
 * Scoped deliberately: MediaCard also renders a hover-overlay "Play <title>"
 * IconButton per card, so a bare getAllByRole('button') returns two nodes per
 * album. That overlay is pre-existing MediaCard behaviour shared with the main
 * library grid, not something this tab introduces.
 */
const cardFor = (album: (typeof ALBUMS)[number]) =>
  screen.getByRole('button', { name: `${album.title} by ${ARTIST}` });

describe('AlbumsTab accessibility (#4537)', () => {
  it('exposes every album card as a button', () => {
    renderTab();
    const cards = screen.getAllByRole('button', { name: new RegExp(`by ${ARTIST}$`) });
    expect(cards).toHaveLength(ALBUMS.length);
  });

  it('gives each card an accessible name including the album title', () => {
    renderTab();
    for (const album of ALBUMS) {
      expect(cardFor(album)).toBeInTheDocument();
    }
  });

  it('includes the artist in the accessible name', () => {
    renderTab();
    expect(
      screen.getByRole('button', { name: /Oktubre by Patricio Rey/i }),
    ).toBeInTheDocument();
  });

  it('reaches the first card with Tab', async () => {
    const user = userEvent.setup();
    renderTab();

    await user.tab();

    // The regression: with no tabIndex the card was skipped entirely and focus
    // stayed on body.
    expect(document.body).not.toHaveFocus();
    expect(cardFor(ALBUMS[0])).toHaveFocus();
  });

  it('activates the focused card with Enter', async () => {
    const user = userEvent.setup();
    const onAlbumClick = renderTab();

    await user.tab();
    await user.keyboard('{Enter}');

    expect(onAlbumClick).toHaveBeenCalledTimes(1);
    expect(onAlbumClick).toHaveBeenCalledWith(ALBUMS[0].id);
  });

  it('activates the focused card with Space', async () => {
    const user = userEvent.setup();
    const onAlbumClick = renderTab();

    await user.tab();
    await user.keyboard(' ');

    expect(onAlbumClick).toHaveBeenCalledTimes(1);
    expect(onAlbumClick).toHaveBeenCalledWith(ALBUMS[0].id);
  });

  it('passes the id of the card that was actually activated, not the first', async () => {
    const user = userEvent.setup();
    const onAlbumClick = renderTab();

    // Focus the second card directly rather than counting Tab stops: each card
    // contributes both itself and its overlay play button to the tab order.
    cardFor(ALBUMS[1]).focus();
    await user.keyboard('{Enter}');

    expect(onAlbumClick).toHaveBeenCalledTimes(1);
    expect(onAlbumClick).toHaveBeenCalledWith(ALBUMS[1].id);
  });

  it('still navigates on mouse click (regression)', async () => {
    const user = userEvent.setup();
    const onAlbumClick = renderTab();

    await user.click(cardFor(ALBUMS[0]));

    expect(onAlbumClick).toHaveBeenCalledTimes(1);
    expect(onAlbumClick).toHaveBeenCalledWith(ALBUMS[0].id);
  });

  it('renders the empty state without any card buttons', () => {
    render(<AlbumsTab albums={[]} artistName="Nobody" onAlbumClick={vi.fn()} />);

    expect(screen.getByText(/No albums found for this artist/i)).toBeInTheDocument();
    expect(screen.queryAllByRole('button')).toHaveLength(0);
  });
});
