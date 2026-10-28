/**
 * Virtualized lists tell assistive tech their real size (#5672)
 *
 * Only the visible window of rows is mounted, so a screen reader counted the DOM and announced a
 * list of ~20 items for a library of thousands. Each row now carries aria-setsize (the whole list)
 * and aria-posinset (its place in it).
 */

import { describe, it, expect, vi } from 'vitest';
import { render } from '@/test/test-utils';
import { screen } from '@testing-library/react';
import TrackRow from '@/components/library/Items/tracks/TrackRow';
import { QueueTrackItem } from '@/components/player/QueuePanel/QueueTrackItem';

const track = {
  id: 7, title: 'Oktubre', artist: 'Patricio Rey', album: 'Oktubre', duration: 200,
} as never;

describe('TrackRow set size (#5672)', () => {
  it('exposes its position within the whole list', () => {
    render(<TrackRow track={track} index={41} setSize={5000} onPlay={vi.fn()} />);

    const option = screen.getByRole('option');
    expect(option).toHaveAttribute('aria-setsize', '5000');
    expect(option).toHaveAttribute('aria-posinset', '42');
  });

  it('omits both attributes when the list size is not known', () => {
    render(<TrackRow track={track} index={0} onPlay={vi.fn()} />);

    const option = screen.getByRole('option');
    expect(option).not.toHaveAttribute('aria-setsize');
    expect(option).not.toHaveAttribute('aria-posinset');
  });
});

describe('QueueTrackItem set size (#5672)', () => {
  it('exposes its position within the whole queue', () => {
    render(
      <ul>
        <QueueTrackItem
          track={track}
          index={2}
          setSize={300}
          isCurrentTrack={false}
          isDragging={false}
          isHovered={false}
          onRemove={vi.fn()}
          onReorder={vi.fn()}
          onDragStart={vi.fn()}
          onDragEnd={vi.fn()}
          onDragOver={vi.fn()}
          onHover={vi.fn()}
          disabled={false}
        />
      </ul>,
    );

    const item = screen.getByRole('listitem');
    expect(item).toHaveAttribute('aria-setsize', '300');
    expect(item).toHaveAttribute('aria-posinset', '3');
  });
});
