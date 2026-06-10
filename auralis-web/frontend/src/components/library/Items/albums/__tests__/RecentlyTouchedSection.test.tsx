/**
 * Regression test for #4142
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * `RecentlyTouchedSection` used to call `useAlbumFingerprints` AFTER an early
 * `return null` for the empty list. That violates the Rules of Hooks: the hook
 * count differed between the empty render (0 hooks) and the populated render
 * (1 hook), so React threw "Rendered more hooks than during the previous
 * render" on the empty -> non-empty transition, crashing the Albums view.
 *
 * The hook is now called unconditionally above the guard. These tests pin that
 * the empty <-> non-empty transition no longer throws.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { RecentlyTouchedSection } from '../RecentlyTouchedSection';
import type { RecentlyTouchedEntry } from '@/hooks/library/useRecentlyTouched';

const entry = (id: number): RecentlyTouchedEntry => ({
  albumId: id,
  albumTitle: `Album ${id}`,
  artist: `Artist ${id}`,
  touchedAt: 1_700_000_000_000 + id,
});

describe('RecentlyTouchedSection (#4142 Rules of Hooks)', () => {
  it('renders nothing for an empty list without throwing', () => {
    const { container } = render(<RecentlyTouchedSection recentAlbums={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders the section when albums are present', () => {
    render(<RecentlyTouchedSection recentAlbums={[entry(1), entry(2)]} />);
    expect(screen.getByText('Recently Touched')).toBeInTheDocument();
  });

  it('does not throw on the empty -> non-empty transition (the original crash)', () => {
    const { rerender } = render(<RecentlyTouchedSection recentAlbums={[]} />);
    // Before the fix this rerender threw "Rendered more hooks than during the
    // previous render" because the hook went from not-called to called.
    expect(() =>
      rerender(<RecentlyTouchedSection recentAlbums={[entry(1), entry(2), entry(3)]} />)
    ).not.toThrow();
    expect(screen.getByText('Recently Touched')).toBeInTheDocument();
  });

  it('does not throw on the non-empty -> empty transition', () => {
    const { rerender } = render(
      <RecentlyTouchedSection recentAlbums={[entry(1)]} />
    );
    expect(() =>
      rerender(<RecentlyTouchedSection recentAlbums={[]} />)
    ).not.toThrow();
  });
});
