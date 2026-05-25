/**
 * AlbumActionButtons — accessibility regression tests (#2813)
 *
 * The three icon-only buttons (favorite, add to queue, more options) rely
 * solely on `Tooltip` for sighted users. Screen-reader users can only
 * discover the button purpose via `aria-label`. These tests pin the
 * presence of the labels so a future refactor that drops them — say a
 * codemod migrating Tooltip → title or replacing IconButton — gets caught.
 */

import { render, screen, fireEvent } from '@/test/test-utils';
import { describe, it, expect, vi } from 'vitest';
import { AlbumActionButtons } from '../AlbumActionButtons';


const baseProps = {
  isPlaying: false,
  isFavorite: false,
  savingFavorite: false,
  firstTrackId: 1,
  albumId: 1,
  onPlay: vi.fn(),
  onToggleFavorite: vi.fn(),
  onAddToQueue: vi.fn(),
  onMoreOptions: vi.fn(),
};


describe('AlbumActionButtons accessibility (#2813)', () => {
  it('exposes the favorite button with descriptive aria-label (unfavorited)', () => {
    render(<AlbumActionButtons {...baseProps} isFavorite={false} />);
    // "Album is not favorited. Press to add" — full sentence is more
    // useful for SR users than just "Favorite".
    const btn = screen.getByRole('button', { name: /not favorited/i });
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAttribute('aria-pressed', 'false');
  });

  it('exposes the favorite button with descriptive aria-label (favorited)', () => {
    render(<AlbumActionButtons {...baseProps} isFavorite={true} />);
    const btn = screen.getByRole('button', { name: /is favorited/i });
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAttribute('aria-pressed', 'true');
  });

  it('exposes the Add to Queue button via aria-label', () => {
    render(<AlbumActionButtons {...baseProps} />);
    const btn = screen.getByRole('button', { name: /add to queue/i });
    expect(btn).toBeInTheDocument();

    fireEvent.click(btn);
    expect(baseProps.onAddToQueue).toHaveBeenCalled();
  });

  it('exposes the More Options button via aria-label', () => {
    render(<AlbumActionButtons {...baseProps} />);
    const btn = screen.getByRole('button', { name: /more options/i });
    expect(btn).toBeInTheDocument();

    fireEvent.click(btn);
    expect(baseProps.onMoreOptions).toHaveBeenCalled();
  });
});
