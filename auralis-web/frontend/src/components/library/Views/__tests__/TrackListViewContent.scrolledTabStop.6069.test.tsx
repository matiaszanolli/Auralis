/**
 * TrackListViewContent keeps a tab stop on a mounted row after scrolling (#6069)
 *
 * The roving tabIndex=0 sat on activeIndex (initially 0). After wheel/scrollbar
 * scrolling unmounted that row, every mounted row was tabIndex=-1 and Tab
 * skipped the whole listbox.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import type { LibraryTrack } from '@/types/domain';
import { TrackListViewContent } from '../TrackListViewContent';

const windowState = { start: 0, end: 3 };

vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: (opts: { count: number }) => ({
    getVirtualItems: () =>
      Array.from({ length: windowState.end - windowState.start }, (_, i) => ({
        index: windowState.start + i,
        size: 56,
        start: (windowState.start + i) * 56,
      })),
    getTotalSize: () => opts.count * 56,
    options: { scrollMargin: 0 },
    scrollToIndex: vi.fn(),
  }),
}));

const tracks = Array.from({ length: 10 }, (_, i) => ({
  id: i + 1, title: `Track ${i + 1}`, artist: 'A', album: 'B', duration: 60, filepath: `/m/${i}.flac`,
}) as LibraryTrack);

function list() {
  return (
    <TrackListViewContent
      tracks={tracks}
      hasMore={false}
      isLoadingMore={false}
      totalTracks={tracks.length}
      isPlaying={false}
      selectedTracks={new Set()}
      isSelected={() => false}
      onToggleSelect={vi.fn()}
      onTrackPlay={vi.fn()}
      onPause={vi.fn()}
      onEditMetadata={vi.fn()}
    />
  );
}

const tabStops = () => screen.getAllByRole('option').filter((o) => o.getAttribute('tabindex') === '0');

describe('TrackListViewContent tab stop after scrolling (#6069)', () => {
  it('has one tab stop on the first row while the active row is mounted', () => {
    windowState.start = 0; windowState.end = 3;
    render(list());

    expect(tabStops()).toHaveLength(1);
    expect(tabStops()[0]).toHaveTextContent('Track 1');
  });

  it('moves the tab stop to a mounted row once the active row is scrolled out', () => {
    windowState.start = 0; windowState.end = 3;
    const { rerender } = render(list());

    windowState.start = 6; windowState.end = 9; // scrolled far below row 0
    rerender(list());

    expect(tabStops()).toHaveLength(1);
    expect(tabStops()[0]).toHaveTextContent('Track 7');
  });
});
