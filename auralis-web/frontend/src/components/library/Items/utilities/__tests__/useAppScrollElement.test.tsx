/**
 * useAppScrollElement (#6631): the one way a library view finds the app scroll container.
 */

import { describe, it, expect, afterEach } from 'vitest';
import { render } from '@testing-library/react';
import { useAppScrollElement } from '../useGridVirtualizer';
import { APP_MAIN_SCROLL_ID } from '@/components/core/appScroll';

const seen: Array<HTMLElement | null> = [];

const Probe = () => {
  seen.push(useAppScrollElement());
  return null;
};

afterEach(() => {
  seen.length = 0;
  document.getElementById(APP_MAIN_SCROLL_ID)?.remove();
});

describe('useAppScrollElement', () => {
  it('resolves the container before the first paint, by re-rendering from the layout effect', () => {
    const container = document.createElement('div');
    container.id = APP_MAIN_SCROLL_ID;
    document.body.appendChild(container);

    render(<Probe />);

    // render() flushes layout effects synchronously: the mount render sees null, the re-render
    // the layout effect triggers sees the element, both before the browser would paint.
    expect(seen).toEqual([null, container]);
  });

  it('stays null when the app shell is not mounted', () => {
    render(<Probe />);

    expect(seen.every((element) => element === null)).toBe(true);
  });
});
