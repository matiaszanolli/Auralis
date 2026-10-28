/**
 * The queue list is one tab stop with arrow-key navigation (#6027)
 *
 * Every row was tabIndex=0 and plain arrows did nothing, so a queue of N tracks
 * was N Tab stops. Roving tabindex: one row is the stop, arrows/Home/End move.
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import type { FocusEvent, KeyboardEvent } from 'react';
import { useQueueRovingFocus } from '../useQueueRovingFocus';

const LENGTH = 5;

function setup(window = { start: 0, end: LENGTH }) {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const rows = Array.from({ length: LENGTH }, (_, i) => {
    const row = document.createElement('li');
    row.tabIndex = -1;
    row.dataset.queueIndex = String(i);
    container.appendChild(row);
    return row;
  });
  const virtualizer = {
    getVirtualItems: () =>
      Array.from({ length: window.end - window.start }, (_, i) => ({ index: window.start + i })),
    scrollToIndex: vi.fn(),
  };
  const hook = renderHook(() =>
    useQueueRovingFocus({
      queueLength: LENGTH,
      scrollElementRef: { current: container },
      virtualizer: virtualizer as never,
    }),
  );
  return { hook, rows, virtualizer };
}

const key = (target: HTMLElement, k: string, mods: Partial<KeyboardEvent> = {}) =>
  ({ key: k, target, altKey: false, ctrlKey: false, metaKey: false, preventDefault: vi.fn(), ...mods }) as unknown as KeyboardEvent<HTMLElement>;

describe('useQueueRovingFocus (#6027)', () => {
  afterEach(() => { document.body.innerHTML = ''; });

  it('starts with the first row as the single tab stop', () => {
    const { hook } = setup();
    expect(hook.result.current.tabStopIndex).toBe(0);
  });

  it('ArrowDown / ArrowUp / End / Home move focus and the tab stop', () => {
    const { hook, rows } = setup();

    act(() => { hook.result.current.onListKeyDown(key(rows[0], 'ArrowDown')); });
    expect(rows[1]).toHaveFocus();
    expect(hook.result.current.tabStopIndex).toBe(1);

    act(() => { hook.result.current.onListKeyDown(key(rows[1], 'End')); });
    expect(rows[LENGTH - 1]).toHaveFocus();
    expect(hook.result.current.tabStopIndex).toBe(LENGTH - 1);

    act(() => { hook.result.current.onListKeyDown(key(rows[LENGTH - 1], 'ArrowUp')); });
    expect(rows[LENGTH - 2]).toHaveFocus();

    act(() => { hook.result.current.onListKeyDown(key(rows[LENGTH - 2], 'Home')); });
    expect(rows[0]).toHaveFocus();
  });

  it('stops at the ends instead of wrapping', () => {
    const { hook, rows } = setup();
    act(() => { hook.result.current.onListKeyDown(key(rows[0], 'ArrowUp')); });
    expect(hook.result.current.tabStopIndex).toBe(0);
  });

  it('leaves Alt+Arrow (reorder) and keys aimed at a control inside a row alone', () => {
    const { hook, rows } = setup();
    const altDown = key(rows[0], 'ArrowDown', { altKey: true });
    act(() => { hook.result.current.onListKeyDown(altDown); });
    expect(altDown.preventDefault).not.toHaveBeenCalled();

    const button = document.createElement('button');
    rows[0].appendChild(button); // no data-queue-index: not a row
    const inner = key(button, 'ArrowDown');
    act(() => { hook.result.current.onListKeyDown(inner); });
    expect(inner.preventDefault).not.toHaveBeenCalled();
    expect(hook.result.current.tabStopIndex).toBe(0);
  });

  it('a row that receives focus becomes the tab stop', () => {
    const { hook, rows } = setup();
    act(() => { hook.result.current.onListFocus({ target: rows[3] } as unknown as FocusEvent<HTMLElement>); });
    expect(hook.result.current.tabStopIndex).toBe(3);
  });

  it('parks the tab stop on a mounted row when the active row scrolled out of the window', () => {
    const window = { start: 0, end: 3 };
    const { hook, rows } = setup(window);
    act(() => { hook.result.current.onListFocus({ target: rows[0] } as unknown as FocusEvent<HTMLElement>); });

    window.start = 3; window.end = 5;
    const { hook: after } = setup(window);

    expect(after.result.current.tabStopIndex).toBe(3);
  });
});
