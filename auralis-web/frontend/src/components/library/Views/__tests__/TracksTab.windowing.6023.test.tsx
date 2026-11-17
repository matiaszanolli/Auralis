/**
 * TracksTab mounts only the rows near the viewport (#6023)
 *
 * It mapped every track of the artist into a MUI table row. With a measurable scroll element the
 * rows are now windowed, with spacer rows standing in for the ones above and below. jsdom has no
 * layout, so the virtualizer is stubbed to report a window.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@/test/test-utils';

const { windowState } = vi.hoisted(() => ({ windowState: { first: 10, last: 14 } }));

vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: () => ({
    getVirtualItems: () =>
      Array.from({ length: windowState.last - windowState.first + 1 }, (_, i) => ({ index: windowState.first + i })),
  }),
}));
vi.mock('@/components/library/usePlaybackState', () => ({ usePlaybackState: () => ({ currentTrackId: null, isPlaying: false }) }));

import TracksTab from '../TracksTab';

const tracks = Array.from({ length: 100 }, (_, i) => ({
  id: i + 1, title: `Track ${i + 1}`, album: 'A', duration: 100,
})) as never[];

describe('TracksTab windowing (#6023)', () => {
  let scroller: HTMLDivElement;

  beforeEach(() => {
    scroller = document.createElement('div');
    scroller.id = 'app-main-content-scroll';
    document.body.appendChild(scroller);
  });
  afterEach(() => scroller.remove());

  it('renders only the windowed rows, numbered by their position in the whole list', () => {
    render(<TracksTab tracks={tracks} onTrackClick={vi.fn()} />);

    expect(screen.queryByText('Track 1')).not.toBeInTheDocument();
    expect(screen.getByText('Track 11')).toBeInTheDocument();
    expect(screen.getByText('Track 15')).toBeInTheDocument();
    expect(screen.queryByText('Track 16')).not.toBeInTheDocument();
    expect(screen.getAllByRole('row').filter((row) => row.getAttribute('aria-label')?.startsWith('Play '))).toHaveLength(5);
    expect(screen.getByText('11')).toBeInTheDocument(); // the row's track number, not 1
  });

  it('stands in for the unrendered rows with spacers so the scroll height is preserved', () => {
    const { container } = render(<TracksTab tracks={tracks} onTrackClick={vi.fn()} />);

    const spacers = [...container.querySelectorAll('tr[aria-hidden]')] as HTMLElement[];
    expect(spacers).toHaveLength(2);
    const [before, after] = spacers.map((row) => parseFloat(row.style.height));
    expect(before).toBe(10 * 56); // ten rows above, at the seed height
    expect(after).toBe(85 * 56); // 100 - 15 rows below
  });

  it('renders every row when there is no measurable scroll element', () => {
    scroller.remove();

    render(<TracksTab tracks={tracks} onTrackClick={vi.fn()} />);

    expect(screen.getByText('Track 1')).toBeInTheDocument();
    expect(screen.getByText('Track 100')).toBeInTheDocument();
  });
});
