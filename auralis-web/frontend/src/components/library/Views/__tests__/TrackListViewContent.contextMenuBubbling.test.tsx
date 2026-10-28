/**
 * A row's context menu must not drive the listbox or the row selection (#6024)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * TrackRow renders <ContextMenu> (a MUI Menu portalled to document.body) as a
 * sibling of its row, so it sits inside the listbox in the REACT tree. React
 * synthetic events bubble along that tree, not the DOM, so every keydown and click
 * in the open menu reached the listbox's arrow-key handler (stealing focus into the
 * list) and the row container's click handler (toggling selection).
 */

import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@/test/test-utils';
import type { LibraryTrack } from '@/types/domain';
import { TrackListViewContent } from '../TrackListViewContent';

vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: (opts: { count: number }) => ({
    getVirtualItems: () =>
      Array.from({ length: opts.count }, (_, i) => ({ index: i, size: 56, start: i * 56 })),
    getTotalSize: () => opts.count * 56,
    options: { scrollMargin: 0 },
    scrollToIndex: vi.fn(),
  }),
}));

const tracks = [1, 2, 3].map((id) => ({
  id, title: `Track ${id}`, artist: `Artist ${id}`, album: 'Album', duration: 180, filepath: `/music/${id}.flac`,
}) as LibraryTrack);

function renderList(onToggleSelect = vi.fn()) {
  render(
    <TrackListViewContent
      tracks={tracks}
      hasMore={false}
      isLoadingMore={false}
      totalTracks={tracks.length}
      isPlaying={false}
      selectedTracks={new Set()}
      isSelected={() => false}
      onToggleSelect={onToggleSelect}
      onTrackPlay={vi.fn()}
      onPause={vi.fn()}
      onEditMetadata={vi.fn()}
    />
  );
  return onToggleSelect;
}

function openMenuOnFirstRow() {
  fireEvent.contextMenu(screen.getByRole('option', { name: /Track 1/ }));
  return screen.getByRole('menu');
}

describe('context menu events do not leak into the track list', () => {
  it('arrow keys inside the open menu do not move focus into the listbox', () => {
    renderList();
    const menu = openMenuOnFirstRow();
    const item = within(menu).getAllByRole('menuitem')[0];

    fireEvent.keyDown(item, { key: 'ArrowDown' });
    fireEvent.keyDown(item, { key: 'End' });

    const rows = screen.getAllByRole('option', { hidden: true });
    expect(rows.every((row) => row !== document.activeElement)).toBe(true);
    // The roving stop did not move off the first row.
    expect(rows[0]).toHaveAttribute('tabindex', '0');
    expect(rows[1]).toHaveAttribute('tabindex', '-1');
    expect(rows[2]).toHaveAttribute('tabindex', '-1');
  });

  it('clicking a menu item does not toggle the row selection', () => {
    const onToggleSelect = renderList();
    const menu = openMenuOnFirstRow();

    fireEvent.click(within(menu).getAllByRole('menuitem')[0]);

    expect(onToggleSelect).not.toHaveBeenCalled();
  });

  it('keyboard navigation inside the listbox still works', () => {
    renderList();
    const first = screen.getByRole('option', { name: /Track 1/ });
    first.focus();

    fireEvent.keyDown(first, { key: 'ArrowDown' });

    expect(screen.getByRole('option', { name: /Track 2/ })).toHaveAttribute('tabindex', '0');
  });

  it('clicking a row still toggles its selection', () => {
    const onToggleSelect = renderList();

    fireEvent.click(screen.getByRole('option', { name: /Track 2/ }));

    expect(onToggleSelect).toHaveBeenCalledTimes(1);
  });
});
