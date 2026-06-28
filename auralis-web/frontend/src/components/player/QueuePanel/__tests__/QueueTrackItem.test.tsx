/**
 * QueueTrackItem memoization (#4177)
 *
 * QueuePanel virtualizes the list and re-renders the whole virtual window on
 * each hover (setHoveredIndex). QueueTrackItem must be memoized so unaffected
 * rows skip re-render — even though the virtualizer hands a fresh style object
 * (same values) every render and the parent must pass stable handlers.
 *
 * formatDuration is called once per render (aria-label + duration span), so its
 * call count is a render counter for the item.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { CSSProperties } from 'react';

vi.mock('@/utils/timeFormat', () => ({
  formatDuration: vi.fn((d: number) => `${d}s`),
}));

import { formatDuration } from '@/utils/timeFormat';
import { QueueTrackItem, type QueueTrackItemProps } from '../QueueTrackItem';

const track = { id: 1, title: 'Song', artist: 'Artist', album: 'A', duration: 200 } as any;

// Stable handler identities, defined once (mirrors the parent's useCallbacks).
const handlers = {
  onRemove: vi.fn(),
  onDragStart: vi.fn(),
  onDragEnd: vi.fn(),
  onDragOver: vi.fn(),
  onHover: vi.fn(),
};

const baseStyle: CSSProperties = {
  position: 'absolute',
  top: 0,
  left: 0,
  width: '100%',
  transform: 'translateY(0px)',
};

function props(overrides: Partial<QueueTrackItemProps> = {}): QueueTrackItemProps {
  return {
    track,
    index: 0,
    isCurrentTrack: false,
    isDragging: false,
    isHovered: false,
    disabled: false,
    style: { ...baseStyle },
    ...handlers,
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(formatDuration).mockClear();
});

describe('QueueTrackItem memoization (#4177)', () => {
  it('skips re-render when handed a fresh style object with identical values', () => {
    const { rerender } = render(<ul><QueueTrackItem {...props()} /></ul>);
    const initial = vi.mocked(formatDuration).mock.calls.length;
    expect(initial).toBeGreaterThan(0);

    // New style OBJECT, identical values + same stable handlers → memo holds.
    rerender(<ul><QueueTrackItem {...props({ style: { ...baseStyle } })} /></ul>);
    expect(vi.mocked(formatDuration).mock.calls.length).toBe(initial);
  });

  it('re-renders when its own hover state changes', () => {
    const { rerender } = render(<ul><QueueTrackItem {...props()} /></ul>);
    const initial = vi.mocked(formatDuration).mock.calls.length;

    rerender(<ul><QueueTrackItem {...props({ isHovered: true })} /></ul>);
    expect(vi.mocked(formatDuration).mock.calls.length).toBeGreaterThan(initial);
  });

  it('re-renders when the track changes', () => {
    const { rerender } = render(<ul><QueueTrackItem {...props()} /></ul>);
    const initial = vi.mocked(formatDuration).mock.calls.length;

    const other = { ...track, id: 2, title: 'Other', duration: 123 };
    rerender(<ul><QueueTrackItem {...props({ track: other })} /></ul>);
    expect(vi.mocked(formatDuration).mock.calls.length).toBeGreaterThan(initial);
  });
});
