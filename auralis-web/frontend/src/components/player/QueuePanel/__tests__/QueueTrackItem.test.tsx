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
import { render, fireEvent } from '@testing-library/react';
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
  onReorder: vi.fn(),
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

/**
 * Keyboard reorder (#4536)
 *
 * The row's only reorder path used to be native drag-and-drop; onKeyDown
 * handled Delete/Backspace and nothing else, so reorderTrack was unreachable
 * without a pointer. #2350 specified this half and only the remove half landed.
 */
describe('QueueTrackItem keyboard reorder (#4536)', () => {
  const row = (container: HTMLElement) =>
    container.querySelector('li') as HTMLElement;

  beforeEach(() => {
    handlers.onReorder.mockClear();
    handlers.onRemove.mockClear();
  });

  it('moves up on Alt+ArrowUp', () => {
    const { container } = render(<ul><QueueTrackItem {...props({ index: 3 })} /></ul>);

    fireEvent.keyDown(row(container), { key: 'ArrowUp', altKey: true });

    expect(handlers.onReorder).toHaveBeenCalledWith(3, 2);
  });

  it('moves down on Alt+ArrowDown', () => {
    const { container } = render(<ul><QueueTrackItem {...props({ index: 3 })} /></ul>);

    fireEvent.keyDown(row(container), { key: 'ArrowDown', altKey: true });

    expect(handlers.onReorder).toHaveBeenCalledWith(3, 4);
  });

  it('ignores unmodified arrows, which belong to list navigation', () => {
    const { container } = render(<ul><QueueTrackItem {...props({ index: 3 })} /></ul>);

    fireEvent.keyDown(row(container), { key: 'ArrowUp' });
    fireEvent.keyDown(row(container), { key: 'ArrowDown' });

    expect(handlers.onReorder).not.toHaveBeenCalled();
  });

  it('does not reorder while disabled', () => {
    const { container } = render(
      <ul><QueueTrackItem {...props({ index: 3, disabled: true })} /></ul>,
    );

    fireEvent.keyDown(row(container), { key: 'ArrowDown', altKey: true });

    expect(handlers.onReorder).not.toHaveBeenCalled();
  });

  it('leaves Delete/Backspace removal unchanged', () => {
    const { container } = render(<ul><QueueTrackItem {...props({ index: 3 })} /></ul>);

    fireEvent.keyDown(row(container), { key: 'Delete' });
    expect(handlers.onRemove).toHaveBeenCalledWith(3);
    expect(handlers.onReorder).not.toHaveBeenCalled();

    handlers.onRemove.mockClear();
    fireEvent.keyDown(row(container), { key: 'Backspace' });
    expect(handlers.onRemove).toHaveBeenCalledWith(3);
  });

  it('advertises the shortcut and exposes its index for focus restoration', () => {
    const { container } = render(<ul><QueueTrackItem {...props({ index: 3 })} /></ul>);

    expect(row(container).getAttribute('aria-keyshortcuts')).toBe(
      'Alt+ArrowUp Alt+ArrowDown',
    );
    // QueuePanel locates the moved row by this attribute after the remount.
    expect(row(container).getAttribute('data-queue-index')).toBe('3');
  });
});
