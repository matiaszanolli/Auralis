/**
 * Removing a queue row hands focus to its neighbour and announces it (#6028)
 *
 * Delete/Backspace on a row (or its Remove button) unmounted the focused
 * element, dropping focus to <body> with no confirmation for screen readers.
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useQueueKeyboardReorder } from '../useQueueKeyboardReorder';

const tracks = [1, 2, 3].map((id) => ({ id, title: `Track ${id}`, artist: 'A', album: 'B', duration: 60 }));

function setup(removeTrack = vi.fn().mockResolvedValue(undefined)) {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const rows = tracks.map((_, i) => {
    const row = document.createElement('li');
    row.tabIndex = 0;
    row.setAttribute('data-queue-index', String(i));
    container.appendChild(row);
    return row;
  });
  const virtualizer = { scrollToIndex: vi.fn() };
  const hook = renderHook(() =>
    useQueueKeyboardReorder({
      queue: tracks as never,
      reorderTrack: vi.fn().mockResolvedValue(undefined),
      removeTrack,
      scrollElementRef: { current: container },
      virtualizer: virtualizer as never,
    }),
  );
  return { hook, rows, removeTrack };
}

describe('useQueueKeyboardReorder handleRemove (#6028)', () => {
  afterEach(() => {
    document.body.innerHTML = '';
    vi.restoreAllMocks();
  });

  it('announces the removal and focuses the row now at the same index', async () => {
    const { hook, rows, removeTrack } = setup();
    rows[1].focus();

    await act(async () => {
      await hook.result.current.handleRemove(1);
    });

    expect(removeTrack).toHaveBeenCalledWith(1);
    expect(hook.result.current.announcement).toBe('Track 2 removed from the queue');
    expect(rows[1]).toHaveFocus(); // the row that slid into index 1
  });

  it('focuses the previous row when the last row was removed', async () => {
    const { hook, rows } = setup();
    rows[2].focus();

    await act(async () => {
      await hook.result.current.handleRemove(2);
    });

    expect(rows[1]).toHaveFocus();
  });

  it('does not pull focus into the list when it was elsewhere', async () => {
    const { hook, rows } = setup();
    const outside = document.createElement('button');
    document.body.appendChild(outside);
    outside.focus();

    await act(async () => {
      await hook.result.current.handleRemove(1);
    });

    expect(outside).toHaveFocus();
    expect(rows[1]).not.toHaveFocus();
  });

  it('does not announce success when the removal fails', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const { hook, rows } = setup(vi.fn().mockRejectedValue(new Error('nope')));
    rows[0].focus();

    await act(async () => {
      await hook.result.current.handleRemove(0);
    });

    expect(hook.result.current.announcement).toBe('Could not remove Track 1');
    expect(rows[0]).toHaveFocus();
  });
});
