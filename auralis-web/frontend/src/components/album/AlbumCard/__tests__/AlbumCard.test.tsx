/**
 * AlbumCard Tests (issue #3929)
 *
 * Verifies the hover-callback contract: AlbumCard accepts the full
 * (albumId, title, artist) signature and does its own internal binding to
 * MediaCard's simpler (id) => void contract — so callers (CozyAlbumGrid,
 * EraSection) can pass a single stable callback straight through as
 * `onHoverEnter={onAlbumHover}` instead of allocating a new arrow per
 * album on every render, which previously defeated AlbumCard's own
 * React.memo on every virtualizer scroll tick.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent, screen } from '@/test/test-utils';
import { AlbumCard } from '../AlbumCard';

describe('AlbumCard', () => {
  it('calls onHoverEnter with (albumId, title, artist) on hover', () => {
    const onHoverEnter = vi.fn();

    render(
      <AlbumCard
        albumId={42}
        title="Test Album"
        artist="Test Artist"
        onHoverEnter={onHoverEnter}
      />
    );

    fireEvent.mouseEnter(screen.getByRole('button', { name: 'Test Album by Test Artist' }));

    expect(onHoverEnter).toHaveBeenCalledWith(42, 'Test Album', 'Test Artist');
  });

  it('accepts the same onHoverEnter reference across re-renders without needing a wrapper', () => {
    const onHoverEnter = vi.fn();
    const { rerender } = render(
      <AlbumCard albumId={1} title="A" artist="B" onHoverEnter={onHoverEnter} />
    );

    // Re-render with the exact same callback reference — this is the shape
    // a caller gets by passing `onHoverEnter={onAlbumHover}` directly
    // (fixes #3929), rather than `onHoverEnter={(id) => onAlbumHover(id, ...)}`
    // which allocates a new function identity every render.
    rerender(
      <AlbumCard albumId={1} title="A" artist="B" onHoverEnter={onHoverEnter} />
    );

    fireEvent.mouseEnter(screen.getByRole('button', { name: 'A by B' }));
    expect(onHoverEnter).toHaveBeenCalledWith(1, 'A', 'B');
  });

  it('does not call onHoverEnter when not provided', () => {
    render(<AlbumCard albumId={1} title="A" artist="B" />);
    // Should not throw when hovered without a handler.
    expect(() =>
      fireEvent.mouseEnter(screen.getByRole('button', { name: 'A by B' }))
    ).not.toThrow();
  });
});
