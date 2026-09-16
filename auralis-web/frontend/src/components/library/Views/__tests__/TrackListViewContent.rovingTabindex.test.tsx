/**
 * TrackListViewContent roving tabindex + selection ARIA (#5011)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The listbox declared aria-multiselectable, but options never exposed
 * aria-selected and there was no arrow-key roving navigation -- two of the
 * properties aria-multiselectable exists for. This renders the real
 * SelectableTrackRow/TrackRow chain (not stubbed, per the issue's own WIRING
 * completeness check: "check via a rendered-output test, not just
 * prop-passing") against a virtualizer mock that renders every row, so
 * keyboard navigation can be exercised without fighting real scroll layout
 * in jsdom.
 */

import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
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

function makeTrack(id: number): LibraryTrack {
  return {
    id,
    title: `Track ${id}`,
    artist: `Artist ${id}`,
    album: 'Album',
    duration: 180,
    filepath: `/music/${id}.flac`,
  } as LibraryTrack;
}

const tracks = [makeTrack(1), makeTrack(2), makeTrack(3)];

function renderList(selected: Set<number> = new Set()) {
  return render(
    <TrackListViewContent
      tracks={tracks}
      hasMore={false}
      isLoadingMore={false}
      totalTracks={tracks.length}
      isPlaying={false}
      selectedTracks={selected}
      isSelected={(id) => selected.has(id)}
      onToggleSelect={vi.fn()}
      onTrackPlay={vi.fn()}
      onPause={vi.fn()}
      onEditMetadata={vi.fn()}
    />
  );
}

describe('TrackListViewContent roving tabindex + aria-selected (#5011)', () => {
  it('reflects selection state via aria-selected on the real rendered option', () => {
    renderList(new Set([2]));

    expect(screen.getByRole('option', { name: /Track 1/ })).toHaveAttribute('aria-selected', 'false');
    expect(screen.getByRole('option', { name: /Track 2/ })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('option', { name: /Track 3/ })).toHaveAttribute('aria-selected', 'false');
  });

  it('starts with exactly one option as the roving tabindex stop', () => {
    renderList();

    const options = screen.getAllByRole('option');
    const tabbable = options.filter((o) => o.getAttribute('tabindex') === '0');
    expect(tabbable).toHaveLength(1);
    expect(tabbable[0]).toHaveTextContent('Track 1');
    expect(options.filter((o) => o.getAttribute('tabindex') === '-1')).toHaveLength(2);
  });

  it('ArrowDown moves both DOM focus and the roving tabindex to the next option', async () => {
    const user = userEvent.setup();
    renderList();

    const first = screen.getByRole('option', { name: /Track 1/ });
    first.focus();
    expect(first).toHaveFocus();

    await user.keyboard('{ArrowDown}');

    const second = screen.getByRole('option', { name: /Track 2/ });
    expect(second).toHaveFocus();
    expect(second).toHaveAttribute('tabindex', '0');
    expect(first).toHaveAttribute('tabindex', '-1');
  });

  it('ArrowUp at the first option stays put (no wraparound past the start)', async () => {
    const user = userEvent.setup();
    renderList();

    const first = screen.getByRole('option', { name: /Track 1/ });
    first.focus();

    await user.keyboard('{ArrowUp}');

    expect(first).toHaveFocus();
    expect(first).toHaveAttribute('tabindex', '0');
  });

  it('End moves focus to the last option, Home back to the first', async () => {
    const user = userEvent.setup();
    renderList();

    screen.getByRole('option', { name: /Track 1/ }).focus();
    await user.keyboard('{End}');

    const last = screen.getByRole('option', { name: /Track 3/ });
    expect(last).toHaveFocus();
    expect(last).toHaveAttribute('tabindex', '0');

    await user.keyboard('{Home}');

    const first = screen.getByRole('option', { name: /Track 1/ });
    expect(first).toHaveFocus();
    expect(first).toHaveAttribute('tabindex', '0');
    expect(last).toHaveAttribute('tabindex', '-1');
  });

  it('clicking a row updates the roving stop so ArrowDown continues from there', async () => {
    const user = userEvent.setup();
    renderList();

    const second = screen.getByRole('option', { name: /Track 2/ });
    second.focus(); // simulates the DOM focus a real click would also cause

    await user.keyboard('{ArrowDown}');

    const third = screen.getByRole('option', { name: /Track 3/ });
    expect(third).toHaveFocus();
    expect(third).toHaveAttribute('tabindex', '0');
    expect(second).toHaveAttribute('tabindex', '-1');
  });
});
